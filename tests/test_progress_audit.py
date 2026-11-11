"""Tests for the research-plan round audit (progress_audit.py)."""
import importlib.util
import json
import os
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(
    HERE, os.pardir,
    'skills', 'research-plan-supervised-run', 'scripts', 'progress_audit.py')


def _load():
    spec = importlib.util.spec_from_file_location('progress_audit', SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    sys.modules['progress_audit'] = mod
    spec.loader.exec_module(mod)
    return mod


PA = _load()

PLAN = """# 测试规划

### BC01：登记问题并整理入口

**要回答：** 这里回答什么。

**做什么：** 做一些事。

**产出：** `01_问题/问题登记.md`、`01_问题/来源索引.csv`。

**完成标准：** 两个文件都在。

### BC02：第二块

**要回答：** 另一个。

**做什么：** 做别的。

**产出：** `02_预期/预期.md`、裸名相对文件.csv、`可重复程序`。

**完成标准：** 三个都在。

### BC03：没有产物的块

**要回答：** 问。

**做什么：** 做。

**产出：** 官方PDF和类别图、两月原件与哈希。

**完成标准：** 有说明。
"""

PLAN_PROSE = """# 规划

### BC01：带后续散文的块

**要回答：** 问。

**做什么：** 做。

**产出：** `01_问题/登记.md`。

**完成标准：** 有。

## 说明

这一段散文提到 BC01/03的原ID与QC，以及 Plan/water 这种斜杠词，
它们不是文件，绝不能被当成产物。
"""


@pytest.fixture
def round_dir(tmp_path):
    d = tmp_path / 'round'
    (d / '01_问题').mkdir(parents=True)
    (d / '02_预期').mkdir(parents=True)
    (d / '01_问题' / '问题登记.md').write_text('# x', encoding='utf-8')
    (d / '01_问题' / '来源索引.csv').write_text('a,b', encoding='utf-8')
    (d / '02_预期' / '预期.md').write_text('# y', encoding='utf-8')
    (d / '02_预期' / '裸名相对文件.csv').write_text('a', encoding='utf-8')
    (d / '00_先看这里_入口.md').write_text('# e', encoding='utf-8')
    (d / '完成状态.json').write_text('{}', encoding='utf-8')
    (d / '后续agent接续说明.md').write_text('# c', encoding='utf-8')
    return str(d)


# ---------- task-block parsing ----------

def test_parses_task_codes_in_order():
    blocks = PA.parse_task_blocks(PLAN)
    assert [b[0] for b in blocks] == ['BC01', 'BC02', 'BC03']


def test_parses_titles():
    blocks = PA.parse_task_blocks(PLAN)
    assert blocks[0][1] == '登记问题并整理入口'


def test_artefacts_are_backticked_paths():
    blocks = PA.parse_task_blocks(PLAN)
    toks = PA.artefact_tokens(blocks[0][2])
    assert '01_问题/问题登记.md' in toks
    assert '01_问题/来源索引.csv' in toks


def test_bare_name_with_extension_is_an_artefact():
    blocks = PA.parse_task_blocks(PLAN)
    toks = PA.artefact_tokens(blocks[1][2])
    assert '裸名相对文件.csv' in toks


def test_backticked_without_extension_is_an_artefact():
    blocks = PA.parse_task_blocks(PLAN)
    toks = PA.artefact_tokens(blocks[1][2])
    assert '可重复程序' in toks


def test_prose_field_gives_no_artefacts():
    blocks = PA.parse_task_blocks(PLAN)
    assert PA.artefact_tokens(blocks[2][2]) == []


# ---------- prose must never become artefacts ----------

def test_prose_after_block_is_not_an_artefact():
    blocks = PA.parse_task_blocks(PLAN_PROSE)
    toks = PA.artefact_tokens(blocks[0][2])
    assert toks == ['01_问题/登记.md'], toks
    assert not any('BC01/03' in t for t in toks)
    assert not any('Plan/water' in t for t in toks)


def test_slash_words_without_extension_are_ignored():
    found = PA.artefact_tokens(['**产出：** a/b、c/d、以及现场T/RH/降水。'])
    assert found == []


# ---------- resolution ----------

def test_resolve_present_at_declared_path(round_dir):
    status, detail = PA.resolve(round_dir, '01_问题/问题登记.md')
    assert status == 'present'
    assert detail.replace('\\', '/') == '01_问题/问题登记.md'


def test_resolve_found_elsewhere(round_dir):
    status, detail = PA.resolve(round_dir, '09_有限关系/来源索引.csv')
    assert status == 'found-elsewhere'
    assert detail.replace('\\', '/') == '01_问题/来源索引.csv'


def test_resolve_missing(round_dir):
    status, detail = PA.resolve(round_dir, '09_有限关系/从未写过.md')
    assert status == 'missing'
    assert detail is None


def test_resolve_bare_name_via_anchor(round_dir):
    # the plan abbreviates the second artefact to a bare name
    status, detail = PA.resolve(round_dir, '裸名相对文件.csv', anchors=('02_预期',))
    assert status == 'present'
    assert detail.replace('\\', '/') == '02_预期/裸名相对文件.csv'


def test_resolve_finds_file_at_round_root(round_dir):
    status, _ = PA.resolve(round_dir, '完成状态.json')
    assert status == 'present'


# ---------- handoff artefacts ----------

def test_scan_handoff_finds_all_three(round_dir):
    hand = PA.scan_handoff(round_dir)
    assert any('先看这里' in f for f in hand['entry_point'])
    assert any(f.endswith('.json') for f in hand['status_json'])
    assert any('接续' in f for f in hand['continuation'])


def test_scan_handoff_ignores_pycache(tmp_path):
    d = tmp_path / 'r'
    (d / '__pycache__').mkdir(parents=True)
    (d / '__pycache__' / '完成状态.json').write_text('{}', encoding='utf-8')
    hand = PA.scan_handoff(str(d))
    assert hand['status_json'] == []


# ---------- whole-round audit ----------

def test_audit_reports_states(round_dir, tmp_path):
    plan = tmp_path / 'plan.md'
    plan.write_text(PLAN, encoding='utf-8')
    report = PA.audit(str(plan), round_dir)

    assert report['task_codes'] == ['BC01', 'BC02', 'BC03']
    states = {t['code']: t['state'] for t in report['tasks']}
    assert states['BC01'] == 'complete'
    assert states['BC02'] == 'partial'      # 可重复程序 is not on disk
    assert states['BC03'] == 'no-artefact'  # plan named no file
    assert report['summary']['total'] == 3


def test_audit_complete_when_everything_present(round_dir, tmp_path):
    # give BC02's third artefact a real file so the block goes complete
    with open(os.path.join(round_dir, '可重复程序'), 'w', encoding='utf-8') as fh:
        fh.write('# prog')
    plan = tmp_path / 'plan.md'
    plan.write_text(PLAN, encoding='utf-8')
    report = PA.audit(str(plan), round_dir)
    states = {t['code']: t['state'] for t in report['tasks']}
    assert states['BC01'] == 'complete'
    assert states['BC02'] == 'complete'


def test_audit_not_started_when_dir_empty(tmp_path):
    empty = tmp_path / 'empty'
    empty.mkdir()
    plan = tmp_path / 'plan.md'
    plan.write_text(PLAN, encoding='utf-8')
    report = PA.audit(str(plan), str(empty))
    states = {t['code']: t['state'] for t in report['tasks']}
    assert states['BC01'] == 'not-started'
    assert states['BC02'] == 'not-started'


def test_audit_json_is_serialisable(round_dir, tmp_path):
    plan = tmp_path / 'plan.md'
    plan.write_text(PLAN, encoding='utf-8')
    report = PA.audit(str(plan), round_dir)
    text = json.dumps(report, ensure_ascii=False)
    assert 'BC01' in text
    assert 'artefacts_elsewhere' in json.loads(text)['tasks'][0]


# ---------- CLI contract ----------

def test_cli_missing_plan_returns_2(tmp_path, capsys):
    code = PA.main([str(tmp_path / 'nope.md'), str(tmp_path)])
    assert code == 2


def test_cli_missing_round_dir_returns_2(tmp_path, capsys):
    plan = tmp_path / 'plan.md'
    plan.write_text(PLAN, encoding='utf-8')
    code = PA.main([str(plan), str(tmp_path / 'nodir')])
    assert code == 2


def test_cli_writes_json_report(round_dir, tmp_path):
    plan = tmp_path / 'plan.md'
    plan.write_text(PLAN, encoding='utf-8')
    out = tmp_path / 'report.json'
    code = PA.main([str(plan), round_dir, '--json', str(out)])
    assert code == 0
    data = json.loads(out.read_text(encoding='utf-8'))
    assert data['summary']['total'] == 3

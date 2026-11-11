#!/usr/bin/env python3
"""Audit a research-plan round against its own plan file.

Usage:
    python progress_audit.py <plan.md> <round-dir> [--json OUT.json]

Reads the numbered task blocks out of a research plan (the format produced by
the `numbering-research-planning-writing` skill), then reports which of each
task's declared artefacts actually exist on disk. This is the mechanical form of
the supervisor's "I read your rollout AND your output directory" step: it
answers "what is really there", not "what was announced".

Three states per task code:

  complete        every declared artefact exists on disk
  partial         some declared artefacts exist, some are missing
  not-started     no declared artefact exists
  no-artefact     the plan named no file for this task (a plan defect)

Nothing is written to the round directory; the audit is read-only.
"""
import argparse
import json
import os
import re
import sys

# A task-block heading, e.g. "### BC01：登记问题并整理原始资料入口"
TASK_HEADING = re.compile(
    r'^#{2,4}\s+(?P<code>[A-Za-z]{1,4}[0-9]{1,2}(?:-[A-Za-z0-9]{1,4})?)'
    r'[:：]?\s*(?P<title>\S.*)$')

# The artefact field label, in any of the spellings the house format uses.
ARTEFACT_FIELD = re.compile(
    r'^\s*(?:[-*+]\s*)?(?:\*\*)?(?:产出|输出)(?:\*\*)?\s*[:：]')

# Any field label, used to find where a field ends.
ANY_FIELD = re.compile(
    r'^\s*(?:[-*+]\s*)?(?:\*\*)?'
    r'(?:要回答|重点回答|这一项回答|回答|做什么|具体操作|操作|方法|产出|输出|'
    r'完成标准|完成条件|验收标准|通过条件|目的|已知锚点|预期耗时|前置条件|注意|为什么做)'
    r'(?:\*\*)?\s*[:：]')

# A file-like token inside an artefact line. The house format backticks its
# artefacts, so a backticked token is always one; an unbackticked token counts
# only when it carries a real document extension. That keeps prose fragments
# such as "BC01/03的原ID与QC" or "Plan/water" out of the artefact list.
BACKTICKED = re.compile(r'`([^`]+)`')
DOC_EXT = (r'md|csv|tsv|xlsx|xls|json|py|png|svg|pdf|docx|txt|zip|nc|h5')
UNBACKTICKED_FILE = re.compile(
    r'(?:^|[\s、，,；;（(])((?:[\w\u4e00-\u9fff.\-]+[\\/])*'
    r'[\w\u4e00-\u9fff.\-]+\.(?:' + DOC_EXT + r'))(?=$|[\s、，,；;。)）])')

# The handoff artefacts the automation contract requires of every round.
HANDOFF = {
    'entry_point': re.compile(r'00_?先看这里|先看这里', re.I),
    'status_json': re.compile(r'完成状态.*\.json$'),
    'continuation': re.compile(r'接续说明|后续agent接续', re.I),
}


def parse_task_blocks(text):
    """Return [(code, title, [artefact_tokens])] in document order."""
    lines = text.splitlines()
    blocks, current = [], None
    in_fence = False
    for line in lines:
        stripped = line.lstrip()
        if stripped.startswith('```') or stripped.startswith('~~~'):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        m = TASK_HEADING.match(line)
        if m:
            if current:
                blocks.append(current)
            current = [m.group('code'), m.group('title').strip(), []]
            continue
        if current is None:
            continue
        if ARTEFACT_FIELD.match(line):
            current[2].append(line)
        elif current[2] and line.strip() and not ANY_FIELD.match(line):
            # continuation of the artefact field; a blank line ends it, so prose
            # after the block is never mistaken for an artefact list
            current[2].append(line)
        elif not line.strip() and current[2]:
            current[2].append('')   # closes the artefact field once it has started
    if current:
        blocks.append(current)
    return [(c, t, art) for c, t, art in blocks]


def artefact_tokens(art_lines):
    """Pull file-like tokens out of the artefact prose.

    A blank entry in `art_lines` marks where the field closed, so everything
    after it belongs to the next block of prose and is ignored.
    """
    clipped = []
    for line in art_lines:
        if not line.strip():
            break
        clipped.append(line)
    text = ' '.join(clipped)

    found = []
    for m in BACKTICKED.findall(text):
        t = m.strip()
        if t:
            found.append(t)
    consumed = set(found)
    for m in UNBACKTICKED_FILE.finditer(text):
        t = m.group(1).strip()
        if t and t not in consumed and not any(t in c for c in consumed):
            found.append(t)
    # de-duplicate, keep order
    out, seen = [], set()
    for f in found:
        if f not in seen:
            seen.add(f)
            out.append(f)
    return out


def resolve(round_dir, token, anchors=()):
    """Does this artefact exist under the round directory?

    Returns (status, detail). Three outcomes, and the distinction matters to a
    supervisor: 'present' at the declared path, 'found-elsewhere' when the file
    exists at some other path (a real defect worth naming), or 'missing' when it
    is not on disk at all. Those are different things and must not be merged.

    `anchors` are directories the task's other artefacts landed in. Plans often
    prefix the first artefact with its subdirectory and abbreviate the rest to
    bare names, so bare names are tried there before being called missing.
    """
    norm = token.replace('\\', '/').lstrip('./')
    candidates = [
        os.path.join(round_dir, *norm.split('/')),
        os.path.join(round_dir, os.path.basename(norm)),
    ]
    for anchor in anchors:
        candidates.append(os.path.join(round_dir, anchor, os.path.basename(norm)))
    for c in candidates:
        if os.path.isfile(c) or os.path.isdir(c):
            return 'present', os.path.relpath(c, round_dir).replace(os.sep, '/')

    want = os.path.basename(norm).lower()
    for base, dirs, names in os.walk(round_dir):
        dirs[:] = [d for d in dirs if d not in ('.git', '__pycache__')]
        for n in names:
            if n.lower() == want:
                found = os.path.relpath(os.path.join(base, n), round_dir).replace(os.sep, '/')
                return 'found-elsewhere', found
    return 'missing', None


def scan_handoff(round_dir):
    """Find the round-level handoff artefacts the automation contract requires."""
    hits = {'entry_point': [], 'status_json': [], 'continuation': []}
    for base, dirs, names in os.walk(round_dir):
        dirs[:] = [d for d in dirs if d not in ('.git', '__pycache__')]
        for n in names:
            rel = os.path.relpath(os.path.join(base, n), round_dir).replace(os.sep, '/')
            for key, pat in HANDOFF.items():
                if pat.search(n):
                    hits[key].append(rel)
    return {k: sorted(v) for k, v in hits.items()}


def audit(plan_path, round_dir):
    with open(plan_path, encoding='utf-8') as fh:
        text = fh.read()
    blocks = parse_task_blocks(text)

    tasks = []
    for code, title, art_lines in blocks:
        tokens = artefact_tokens(art_lines)
        if not tokens:
            state = 'no-artefact'
            present, misplaced, missing = [], [], []
        else:
            # pass 1 without anchors, to learn where this task keeps its files
            results = {t: resolve(round_dir, t) for t in tokens}
            anchors = sorted({
                os.path.dirname(p) for t, r in results.items()
                if r[0] == 'present' for p in [r[1]]
                if p and os.path.dirname(p)
            })
            # pass 2 retries the bare names inside those directories
            if anchors:
                results = {t: (r if r[0] == 'present' else resolve(round_dir, t, anchors))
                           for t, r in results.items()}
            present = [t for t, r in results.items() if r[0] == 'present']
            misplaced = [t for t, r in results.items() if r[0] == 'found-elsewhere']
            missing = [t for t, r in results.items() if r[0] == 'missing']
            if not missing and not misplaced:
                state = 'complete'
            elif not present and not misplaced:
                state = 'not-started'
            else:
                state = 'partial'
        tasks.append({
            'code': code,
            'title': title,
            'artefacts_named': tokens,
            'artefacts_present': present,
            'artefacts_elsewhere': {t: results[t][1] for t in misplaced} if tokens else {},
            'artefacts_missing': missing,
            'state': state,
        })

    counts = {}
    for t in tasks:
        counts[t['state']] = counts.get(t['state'], 0) + 1

    return {
        'plan': os.path.basename(plan_path),
        'round_dir': round_dir,
        'task_codes': [t['code'] for t in tasks],
        'tasks': tasks,
        'summary': {'total': len(tasks), 'by_state': counts},
        'handoff': scan_handoff(round_dir),
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('plan', help='the research plan markdown file')
    ap.add_argument('round_dir', help='the round output directory to audit')
    ap.add_argument('--json', dest='json_out', help='also write the full report to this path')
    args = ap.parse_args(argv)

    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')

    if not os.path.isfile(args.plan):
        print(f'error: plan not found: {args.plan}', file=sys.stderr)
        return 2
    if not os.path.isdir(args.round_dir):
        print(f'error: round directory not found: {args.round_dir}', file=sys.stderr)
        return 2

    report = audit(args.plan, args.round_dir)
    s = report['summary']
    codes = ', '.join(report['task_codes']) or '(none)'
    print(f'plan : {report["plan"]}')
    print(f'dir  : {report["round_dir"]}')
    print(f'tasks: {s["total"]}  [{codes}]')
    print(f'state: ' + ', '.join(f'{k}={v}' for k, v in sorted(s['by_state'].items())))
    print()
    for t in report['tasks']:
        mark = {'complete': 'OK  ', 'partial': 'PART', 'not-started': 'TODO',
                'no-artefact': 'PLAN'}[t['state']]
        print(f'{mark}  {t["code"]:10} {t["title"][:34]}')
        for p in t['artefacts_present']:
            print(f'        + {p}')
        for m, where in t['artefacts_elsewhere'].items():
            print(f'        ? {m}   -> found at {where}')
        for m in t['artefacts_missing']:
            print(f'        - {m}   (MISSING)')
        if t['state'] == 'no-artefact':
            print('        ! plan names no file for this task')

    print('\nhandoff artefacts:')
    for key, label in (('entry_point', 'entry point (00_先看这里)'),
                       ('status_json', 'status json (完成状态)'),
                       ('continuation', 'continuation note (接续说明)')):
        found = report['handoff'][key]
        print(f'  {label}: {len(found)}')
        for f in found[:6]:
            print(f'      {f}')

    if args.json_out:
        with open(args.json_out, 'w', encoding='utf-8') as fh:
            json.dump(report, fh, ensure_ascii=False, indent=2)
        print(f'\njson written: {args.json_out}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

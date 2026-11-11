# research-plan-supervised-run

An agent skill for **keeping a numbered research plan running to its stage
decision** across quota resets, context overflows and interruptions.

- **Name:** `research-plan-supervised-run`
- **Repo:** [xiwang-geo/research-plan-supervised-run](https://github.com/xiwang-geo/research-plan-supervised-run)
- **License:** MIT
- **Languages:** SKILL.md in English; field names and sample artefacts in Chinese,
  matching the research workflow it runs.

> 简体中文说明见 [README_ZH-CN.md](README_ZH-CN.md)。

---

## What problem this solves

A research plan written as numbered task blocks is worth little if the blocks are
never finished. Real rounds get interrupted: quota runs out mid-block, the
session closes, someone returns days later and starts the plan over from the
first block. The plan survives as a document; the work does not.

This skill is the **execution layer** for such plans. It defines a supervised
run: a working agent that executes task blocks, a supervisor agent that audits
what is actually on disk, and a queued-reminder channel that fires when work can
resume. Its central discipline is that **progress is measured against files on
disk, not against announcements**.

---

## How this relates to `numbering-research-planning-writing`

This is the second half of one workflow. The first half is
**[numbering-research-planning-writing](https://github.com/xiwang-geo/numbering-research-planning-writing)**,
the skill for *writing* the plan in the first place — the one that turns a
question into a plan of numbered task blocks (`BC01`, `WB03`, `R2-C02`), each
carrying four fields: 要回答 / 做什么 / 产出 / 完成标准.

| | `numbering-research-planning-writing` | `research-plan-supervised-run` |
| --- | --- | --- |
| **Stage** | before execution | during execution |
| **Job** | write the plan as numbered task blocks | run those blocks to a stage decision |
| **Unit of work** | the task block | the same task block |
| **Artefact produced** | `<plan>.md` with 产出 paths per block | the 产出 files themselves, plus handoff state |
| **Failure mode it prevents** | an ad-hoc plan with no completion criteria | a plan abandoned part-way, or a resumption that redoes finished work |
| **Its checker** | `check_plan.py` — is the plan well-formed? | `progress_audit.py` — is the plan actually done? |

**They share one contract: the task block.** The `产出：` file paths the writing
skill records become exactly what this skill's audit checks on disk. The
`完成标准：` gates the writing skill sets become exactly what the supervisor
restates as reminders — without inventing new thresholds. The stage-decision
block the writing skill writes is where this skill's run terminates.

In other words: **the writing skill defines what "done" means; this skill
enforces it.** Neither is useful without the other. A plan that no run supervises
rots after two blocks; a supervised run with no plan has nothing to audit against
and will happily re-run finished work.

**Practical order of use:**

```sh
# 1. write the plan, validate its structure
npx skills add xiwang-geo/numbering-research-planning-writing --agent claude-code --global
python .../check_plan.py <plan.md>

# 2. run it under supervision
npx skills add xiwang-geo/research-plan-supervised-run --agent claude-code --global
python .../progress_audit.py <plan.md> <round-dir>
```

`progress_audit.py` will report `no-artefact` for any task whose 产出 was never
named — which is a defect the writing skill's `check_plan.py` should have caught.
That is the hand-off point between the two skills, stated mechanically.

---

## Install

```sh
# Claude Code
npx skills add xiwang-geo/research-plan-supervised-run --skill research-plan-supervised-run --agent claude-code --global

# Codex CLI
npx skills add xiwang-geo/research-plan-supervised-run --skill research-plan-supervised-run --agent codex --global
```

Verified with `npx skills add` 0.6.6. Or copy
`skills/research-plan-supervised-run/` into `~/.claude/skills/` or
`~/.codex/skills/` by hand.

---

## What a supervised run consists of

1. **Set up before the first interruption** — name the task range, point both
   agents at one plan file, agree three handoff artefacts
   (`00_先看这里*.md`, `完成状态.json`, `后续接续说明*.md`), and announce the
   supervisor to the worker up front.
2. **Probe the channel** — the first automated message is a connectivity probe
   that expects no reply. If it does not arrive, the automation is theatre.
3. **Supervisor reminders** — a five-part message whose order is the deliverable:
   *this is not a new task* → *I read your disk, not your announcements* →
   *three-state accounting per task code* → *gates restated from the plan* →
   *entry point + status JSON after each item*, closing with 「请开始，不必回复说明」.
4. **Anti-fabrication rules** — stated explicitly in the reminder, because an
   unattended run has no human to catch a fabricated result.
5. **Resumption** — read the continuation note and status JSON, ask the audit
   what is really on disk, skip every `complete` block, continue from the first
   that is not.
6. **Stage decision** — the run ends at the plan's decision block
   (`继续 / 补资料 / 暂停`), not at the last task code.

The full procedure, with the reasoning behind each rule, is in
[`skills/research-plan-supervised-run/SKILL.md`](skills/research-plan-supervised-run/SKILL.md).
Ready-to-copy message templates are in
[`references/supervisor-message-templates.md`](skills/research-plan-supervised-run/references/supervisor-message-templates.md)
and the handoff contract in
[`references/handoff-artifacts.md`](skills/research-plan-supervised-run/references/handoff-artifacts.md).

---

## `progress_audit.py`

Read-only audit of a round directory against the plan that describes it.

```sh
python skills/research-plan-supervised-run/scripts/progress_audit.py <plan.md> <round-dir> [--json report.json]
```

It answers three questions a supervisor must ask before prompting anyone:

- **Which declared artefacts exist?** `present` / `found-elsewhere` / `missing`
  per artefact — deliberately three states, because "written to the wrong
  folder" and "never written" call for different messages.
- **Which tasks are complete?** `complete` / `partial` / `not-started` /
  `no-artefact`.
- **Are the handoff artefacts there?** entry point, status JSON, continuation
  note.

Exit 2 if the plan or directory is missing.

### Measured on a real round

Against a 12-task research plan (BC01–BC12) and its actual output directory —
12 task codes, 40 declared artefacts:

| state | tasks | detail |
| --- | --- | --- |
| `complete` | 10 | BC01–BC06, BC08, BC10–BC12 |
| `partial` | 2 | BC07 missing `可重复模拟程序`; BC09 missing `全部过程关系图.png` |

38 of the 40 declared artefacts are on disk; 2 are genuinely absent.

Handoff artefacts found in the same directory: **18** entry points,
**29** completion-status JSONs, **3** continuation notes.

Two things the audit has to get right, both of which a naive check gets wrong:

- **Plans abbreviate.** The first artefact of a block is prefixed with its
  subdirectory, the rest are bare names. On this round 26 of the 38 present
  artefacts are bare names, and not one of them exists at the round root — they
  only resolve inside the block's own folder. Without anchor-directory
  resolution all 26 report as "missing", and the supervisor's message tells the
  worker to redo work that is finished.
- **`missing` and `found-elsewhere` must stay distinct.** A file written to the
  wrong folder is a different problem from a file never written, and calls for a
  different reminder. An earlier version of this script reported a file as
  misplaced when it was in fact at its declared path and the scanner had found a
  different same-named file first; keeping the declared path authoritative and
  only falling back to a directory walk is what separates the two cases.

---

## Repository layout

```
research-plan-supervised-run/
├── skills/research-plan-supervised-run/
│   ├── SKILL.md
│   ├── scripts/progress_audit.py
│   ├── references/
│   │   ├── supervisor-message-templates.md
│   │   └── handoff-artifacts.md
│   └── templates/
│       ├── status.json
│       └── continuation-note.md
├── tests/test_progress_audit.py
├── .github/workflows/test.yml
└── README.md / README_ZH-CN.md
```

## Tests

```sh
python -m pip install pytest
python -m pytest tests/ -q
```

22 tests covering task-block parsing, artefact extraction, the three-state
resolution, handoff detection and the CLI contract.

## Related

- **[numbering-research-planning-writing](https://github.com/xiwang-geo/numbering-research-planning-writing)** —
  writes the plan this skill runs (the other half of the workflow)
- **[hermes-history-claude](https://github.com/xiwang-geo/hermes-history-claude)** /
  **[hermes-history-codex](https://github.com/xiwang-geo/hermes-history-codex)** —
  read prior session history, useful when reconstructing what a round actually did

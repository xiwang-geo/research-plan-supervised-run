# Handoff artefacts

Three files make a round survivable. They are the only things a resumption has to
read, so they must be written **before** an interruption, not reconstructed after.

## 1. `00_先看这里_<主题>.md` — entry point

Written by the worker, updated as the round progresses. Its job is to let a
stranger (the supervisor, a later session, the researcher) orient in under a
minute.

It should answer, in this order:

1. 本轮是什么、对应计划文件的哪一段
2. 已完成到哪个任务码
3. 正在做什么、停在哪一步
4. 下一步做什么
5. 有哪些资料缺口挡着
6. **不要做的事**（防止误把模型输出当观测、防止重复拟合）

Point 6 is the one people skip and the one that matters most after a break.

## 2. `<范围>_完成状态.json` — machine-readable state

Field conventions, taken from real rounds:

```json
{
  "version": 1,
  "finished_at_local": "2026-10-28T23:10:00+08:00",

  "BC05": "complete",
  "BC06": "complete",
  "BC08": "pending_actual_common_time_T_RH_QC",
  "BC09": "not_evaluable_until_BC08_gates_pass",

  "formal_scientific_gate_passed": false,

  "old_time_aggregation_rerun": false,
  "old_models_refit": false,
  "new_isotope_relationships_fit": 0,

  "round1_checks": {},
  "round2_checks": {},
  "audit_checks_passed": true
}
```

Rules:

- **One key per task code**, value = its state. Free-text states are allowed
  (`not_evaluable_until_…`) because they carry the reason; the audit script does
  not parse them, the supervisor reads them.
- **`formal_scientific_gate_passed`** is the round's overall gate. While it is
  `false`, no formal inference may be reported.
- **The three counters** are the anti-fabrication record: whether old
  aggregations were re-run, whether old models were refit, how many new isotope
  relationships were fitted. In a round that must not re-fit anything, these are
  the proof it did not.
- **`round1_checks` / `round2_checks`** record the two verification rounds; keep
  them as objects even when empty so the shape is stable across rounds.
- `finished_at_local` with an explicit offset. Rounds span quota resets and get
  revisited days later.

## 3. `后续接续说明_<范围>.md` — continuation note

The single most important artefact for surviving an interruption. Written by the
worker *while it is still running*, in the same turn as the work it describes.

It must say:

1. **任务状态** — per code: 已完成 / 进行中 / 未开始
2. **禁止重复做的事** — which steps are done and must not be re-run, and what
   would count as re-running them (e.g. "已完成的时窗聚合和既有拟合保持不变",
   "不要把归档的重拟合结果重新引成新拟合")
3. **断点位置** — the exact file and line/step where work stopped
4. **下一步** — the next concrete action, in terms the plan uses

Point 2 is what turns a reminder into "continue" instead of "redo". Without it
the resumption will happily re-fit a model that was already fitted and quietly
replace a result.

## How the audit ties them together

```sh
python scripts/progress_audit.py <plan.md> <round-dir> --json report.json
```

The audit reports, per task code:

- `present` — declared artefact exists (including inside the task's own
  subdirectory, where plans usually put them)
- `found-elsewhere` — the file exists but at a path the plan did not name; the
  actual path is reported so you can move it or correct the plan
- `missing` — not on disk at all

and at round level whether all three handoff artefacts are present. Use it in two
places: before resuming (so you skip finished work) and before declaring the
round finished (so you do not announce something that is not there).

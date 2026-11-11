---
name: research-plan-supervised-run
description: Use when a numbered research plan must keep running to a stage decision across quota resets and interruptions. Sets up a supervisor agent and a queued-reminder channel, audits on-disk progress instead of trusting announcements, and resumes a plan without re-running finished task blocks. Pairs with numbering-research-planning-writing, which writes the plan this skill executes.
---

# Supervised research-plan runs

A research plan written as numbered task blocks only pays off if the blocks
actually get finished. In practice they don't: the run is interrupted by quota
reset, the agent's context fills, someone leaves, and the plan is abandoned at
BC06 with the rest never attempted.

This skill is the **execution layer** that keeps a plan moving to its stage
decision. It is not a planner. It assumes a plan already exists.

## Relationship to `numbering-research-planning-writing`

That skill writes the plan; this one runs it. The contract between them is the
task block itself:

| produced by the planning skill | consumed here |
| --- | --- |
| numbered task codes (`BC01`, `WB03`, `R2-C02`) | the unit of work and of progress accounting |
| `产出：` artefact paths | what the audit checks on disk |
| `完成标准：` gates | what the supervisor restates as reminders |
| the stage-decision block | where the run terminates |

If the plan was written by hand, the four fields must still be present
(`要回答` / `做什么` / `产出` / `完成标准`). The planning skill's
`check_plan.py` validates that; run it before starting a supervised run, because
an audit cannot recover a task whose artefacts were never named.

## The shape of a supervised run

```
  user  ──declares task range──▶  working agent   (Codex / Claude Code)
   │                                  │  runs BC05, BC06 …
   │                                  │  writes 00_先看这里 + 完成状态.json
   │  ◀──writes a continuation note───┘  before quota runs out
   │
   └─spawns──▶  supervisor agent  ──queues reminder──▶  working agent
                    │                                       │
                    └─ reads plan + output directory ───────┘
                       (not the announcements)
```

Three parties, three jobs. The **working agent** executes blocks. The
**supervisor** audits and prompts. The **scheduler** (whatever fires the
supervisor — a timed job, a quota-reset hook, a human returning) decides *when*.

## 1. Set up before the first interruption

Do this in the same session that starts the work, while there is still quota.

1. **Name the task range.** "本轮执行 BC05 到 BC12." A run without a bounded
   range cannot be audited for completion.
2. **Point at one plan file.** The plan path is the single source of truth for
   what is in scope. Both agents must read the same file.
3. **Agree the handoff artefacts.** Three files, and they are not optional:

   | file | written by | purpose |
   | --- | --- | --- |
   | `00_先看这里_<主题>.md` | worker | entry point: what is done, what is next |
   | `<范围>_完成状态.json` | worker | machine-readable per-code state |
   | `后续接续说明_<范围>.md` | worker | how to resume without duplicating |

   Write the continuation note **before** you run out of quota, not after. It is
   the only thing that turns a later reminder into "continue" instead of "redo".
4. **Say who will prompt whom.** Announce the supervisor's existence to the
   worker up front — "另一个 agent 会在额度重置后提醒你继续" — so the incoming
   message is expected rather than derailing.

## 2. Probe the channel first

The first automated message is a connectivity probe, not work:

> （监督 agent 连通性探测：这是一条自动队列消息，用于确认消息通道可用。
> 收到后请忽略，无需回复。）

Send it and expect silence. If it does not arrive, the channel is broken and the
whole automation is theatre — fix that before queueing real reminders.

## 3. The supervisor's message

This is the deliverable of the automation, and its structure matters more than
its prose. Five parts, in this order:

1. **Framing — this is not a new task.**
   > 这是来自监督 agent 的提醒，不是新任务。
   Without this line the worker may treat the message as a fresh request and
   restart the plan from scratch.

2. **State the evidence basis.**
   > 我刚读过你的 rollout 和产出目录，不只是看公告。
   The claim of authority is "I read the disk", not "I read what you said".

3. **Three-state accounting per task code.** Never two states. Always three:
   - **已正式宣布完成** — announced complete in the worker's output
   - **磁盘上已有产出但未宣布** — on disk but never announced, with the concrete
     file named
   - **缺失** — genuinely not written

   The middle state is where the value is. A supervisor that collapses it into
   "not done" tells the worker to redo finished work. Run
   `scripts/progress_audit.py` to produce this mechanically; it reports
   `present` / `found-elsewhere` / `missing` per artefact and will not confuse a
   file written to the wrong folder with a file that was never written.

4. **Reminders restated from the plan's own gates.** Quote the `完成标准`, do not
   invent new thresholds. Conditional tasks stay conditional: if the plan says a
   task only proceeds when a condition holds, the reminder says so.

5. **Artefacts after each item.** Entry point file plus completion-status JSON,
   per item, as you go. Then a suggested order.

Close with **请开始，不必回复说明.** The worker should work, not narrate.

## 4. Anti-fabrication rules

State these explicitly in the reminder; they are the rules that keep an automated
run honest:

- 不追阈值直到显著
- 不合并不同尺度和采样器
- 每一步留下输入输出与停止位置
- 资料不足的步骤写「未通过 / 未执行」加缺什么，不要伪造完成
- 不要用零值或空表伪装成已算过

An automated run has no human watching each step, so these are the only thing
standing between a resumption and a fabricated result.

## 5. Resuming after interruption

When the reminder arrives, the worker must:

1. Read the continuation note and the completion-status JSON **before** acting.
2. Ask `progress_audit.py` what is really on disk.
3. Skip every block the audit reports `complete`.
4. Continue from the first block that is not `complete`.

Never trust "I was working on BC06" from memory. The audit is the answer.

## 6. Ending the run

The run ends at the stage decision, not at the last task code. A wrap-up message
should:

- verify every task code in range is `complete` **on disk**, naming the files
- confirm the stage decision was written (`继续 / 补资料 / 暂停`)
- flag any literature collision or external finding that must flow into that
  decision
- then move to the next-step question with concrete options and a recommended
  choice

If some codes cannot complete because data is missing, that is a legitimate
end state — record it as `未通过 / 未执行 + 缺什么`, which is exactly what the
plan's gates ask for.

## Scripts

`scripts/progress_audit.py` — read-only audit of a round directory against the
plan that describes it.

```sh
python scripts/progress_audit.py <plan.md> <round-dir> [--json report.json]
```

Exit 2 when the plan or directory is missing. Prints per-task artefact state
plus the three handoff artefacts, and writes full JSON when asked. Use it before
resuming and before declaring a round finished.

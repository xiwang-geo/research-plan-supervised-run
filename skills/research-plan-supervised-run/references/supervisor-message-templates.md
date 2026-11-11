# Supervisor message templates

Drawn from real supervised runs of the BC01–BC12 research plan. Copy the
structure; the wording adapts to the plan. The **order of the five parts is the
deliverable** — a message with the right content in the wrong order reads as a
new task and derails the worker.

---

## Template 1 — connectivity probe

Send before queueing any real work. Expect no reply.

```text
（监督 agent 连通性探测：这是一条自动队列消息，用于确认消息通道可用。
收到后请忽略，无需回复。）
```

If this never arrives, stop: the channel is broken and every later reminder is
speculative.

---

## Template 2 — resumption reminder

```text
这是来自监督 agent 的提醒，不是新任务。

我刚读过你的 rollout 和产出目录，不只是看公告。BC05 和 BC06 你已在磁盘上
完成，但未正式宣布，需要补一份简短完成声明，并补上以下内容：

- BC05 未提供的 05_汽雨诊断/派生公式与单位字典.md、05_汽雨诊断/测量与温度误差来源.csv
- BC06 未提供的 06_条件支持/RH_雨强共同分布.png、06_条件支持/可估范围与进入理由.md

当前剩余任务：

1. BC07 建立小型、守恒的雨滴过程模拟
2. BC08 冻结唯一主要比较与资料用途
3. BC09 开展第一版有限观测分析
4. BC10 用独立过程检查重复性
5. BC11 把观测和模拟放回物理问题
6. BC12 两轮核验，决定继续、补资料或暂停

请按 <PLAN_PATH> 逐项执行并按完成标准自检。提醒几点与原规划一致：

- BC08 是条件步骤。水汽双同位素、现场温度、相对湿度、降水或降水率、时钟、
  QC 或可构造的合格样本缺失时，不要推进正式统计，只登记缺什么。
- BC09 只在冻结资料、固定模型和真实现场共同支持成立后执行，若尚未通过就
  标为未执行并进入 BC12 决定。
- 资料不足的步骤请写未通过或未执行加缺什么，不要伪造完成，不要用零值或
  磁盘上不存在的空表伪装成已算过。
- 不追阈值直到显著，不合并不同尺度和采样器，每一步留下输入输出与停止位置。

每完成一项，保存：

- 先看这里入口文件
- 完成状态.json，包含逐任务状态、数据缺口、参数和禁止结论

建议顺序：BC07 → BC08 → BC09 → BC10 → BC11 → BC12。

请开始，不必回复说明。
```

### Why each part is there

| part | function | what breaks without it |
| --- | --- | --- |
| 「不是新任务」 | frames the message as continuation | worker restarts the plan from BC01 |
| 「读过你的 rollout 和产出目录」 | grounds authority in disk state | the worker can talk its way past a missing file |
| 三态账目 | names files the worker forgot to announce | finished work gets redone |
| 与原规划一致的门槛 | restates `完成标准`, invents nothing | thresholds drift between resumptions |
| 反伪造规则 | the only honesty control in an unattended run | a resumption produces a fabricated result |
| 入口文件 + 完成状态.json | the handoff contract | the next resumption has nothing to read |
| 「不必回复说明」 | converts talk into work | quota is spent narrating instead of executing |

---

## Template 3 — round wrap-up and stage decision

Send when the audit reports every code in range `complete`, or when the data
gates have genuinely stopped the run.

```text
这是监督 agent 的第二轮消息。BC01 到 BC12 我已逐项核对磁盘产出，确认全部
完成，阶段决定已成立：进入。下轮首先处理资料缺口 BC13 到 BC16。

下一步研究讨论的实体内容围绕四点：

1. 问题定义是否要收敛到汽雨混合比或分馏量随云下垂直尺度的连续变化；
2. 把补充资料缺口拆成水汽双同位素、现场温湿、降水与滴谱等可逐项补齐项；
3. 立刻可做的工作是跑通 BC13 到 BC16 并恢复后台执行；
4. 下一步优先选择“补齐现场温湿、水汽双同位素、滴谱，再做收敛研究”，而不是
   新开全量气候学论文，也不回归只研究两场个例。

后续讨论必须满足三点：以现有真实结果和具体路径为基础；未经你确认，不启动
新的资料下载或正式拟合；本轮引用需要更正：云的分类与生成机制是既有博士论文
已有内容，不应标成老师首次提出，现已删除。

请开始，不必回复说明。
```

### Requirements for this message

- Verify **on disk**, per code, and name the files. "All complete" is a claim the
  reader can check.
- Name the stage decision that was reached (`继续 / 补资料 / 暂停`) and where it
  is written.
- Carry forward any literature collision or citation correction into the
  decision. An automated run is exactly where such a correction gets lost.
- Then give the next-step question as **concrete options with a recommended
  choice**, not as an open question.

---

## Template 4 — second-round probe after an interruption

Use when a resumption happened and you need to confirm the worker picked up the
thread correctly, before it claims completion.

```text
这是来自监督 agent 的核对，不是新任务。

在你宣布本轮结束前，我按 <PLAN_PATH> 核对了产出目录。以下产物在磁盘上找不到：

- <missing-1>
- <missing-2>

请补齐后再宣布完成；若因资料缺口无法补齐，请在 <范围>_完成状态.json 里写
"未执行 / 未通过 + 缺什么"，并把这一条带进阶段决定。不要补一张空表来代替。

请开始，不必回复说明。
```

# research-plan-supervised-run

让一份**编号研究规划**在额度重置、上下文溢出、人员离开之后，仍然跑完到阶段决定的 agent skill。

- **技能名：** `research-plan-supervised-run`
- **仓库：** [xiwang-geo/research-plan-supervised-run](https://github.com/xiwang-geo/research-plan-supervised-run)
- **License：** MIT
- **语言：** SKILL.md 用英文写；字段名与示例产物用中文，与它实际执行的研究流程一致。

> English documentation: [README.md](README.md).

---

## 解决什么问题

把研究规划写成编号任务块，如果块跑不完，规划就白写了。真实的一轮会被打断：额度用尽时正好跑到一半、会话关掉了、几天后回来把规划从第一个块重做一遍。规划作为文档留下了，工作没留下。

本 skill 是这类规划的**执行层**。它定义「受监督的一轮」：一个干活的 agent 执行任务块，一个监督 agent 审计磁盘上**实际**有什么，一条队列提醒通道在可以继续时触发。核心纪律是——**进度以磁盘文件为准，不以声明为准**。

---

## 和 `numbering-research-planning-writing` 的关系

这是同一条工作流的后半段。前半段是
**[numbering-research-planning-writing](https://github.com/xiwang-geo/numbering-research-planning-writing)**，
也就是**写规划**的那一份技能：把一个问题变成一份编号任务块规划（`BC01`、`WB03`、`R2-C02`），每块带四个字段——要回答 / 做什么 / 产出 / 完成标准。

| | `numbering-research-planning-writing` | `research-plan-supervised-run` |
| --- | --- | --- |
| **阶段** | 执行之前 | 执行之中 |
| **职责** | 把规划写成编号任务块 | 把这些块跑到阶段决定 |
| **工作单位** | 任务块 | 同一个任务块 |
| **产出** | `<plan>.md`，每块记录 `产出` 路径 | `产出` 文件本身，加上交接状态 |
| **防止哪种失败** | 即兴规划、没有完成标准 | 规划半途而废；恢复时重做已完成的工作 |
| **它的校验器** | `check_plan.py`——规划写得对不对 | `progress_audit.py`——规划做完了没有 |

**两者共用同一个契约：任务块。** 写作技能记录的 `产出：` 文件路径，正是本技能审计要在磁盘上核对的东西。写作技能设定的 `完成标准：` 门槛，正是监督 agent 在提醒里复述的东西——而不是另发明新的阈值。写作技能写下的阶段决定块，就是本技能这一轮跑的终点。

换句话说：**写作技能定义「什么算完成」，本技能去执行这个定义。** 缺谁都只剩一半：没人监督的规划，跑两个块就烂尾；没有规划的受监督一轮，没有可审计的依据，会心安理得地重跑已经做完的工作。

**实际使用顺序：**

```sh
# 1. 写规划，校验结构
npx skills add xiwang-geo/numbering-research-planning-writing --agent claude-code --global
python .../check_plan.py <plan.md>

# 2. 在监督下跑这份规划
npx skills add xiwang-geo/research-plan-supervised-run --agent claude-code --global
python .../progress_audit.py <plan.md> <round-dir>
```

任何 `产出` 从来没写名字的任务，`progress_audit.py` 都会报 `no-artefact`——这恰恰是写作技能的 `check_plan.py` 该拦住的缺陷。这就是两个技能的交接点，而且是机械化地交接。

---

## 安装

```sh
# Claude Code
npx skills add xiwang-geo/research-plan-supervised-run --skill research-plan-supervised-run --agent claude-code --global

# Codex CLI
npx skills add xiwang-geo/research-plan-supervised-run --skill research-plan-supervised-run --agent codex --global
```

已用 `npx skills add` 0.6.6 实测。也可以手动把
`skills/research-plan-supervised-run/` 拷进 `~/.claude/skills/` 或
`~/.codex/skills/`。

---

## 受监督的一轮包含什么

1. **在第一次被打断之前就搭好**——划定任务码范围；两个 agent 读同一份规划文件；约定三份交接产物（`00_先看这里*.md`、`完成状态.json`、`后续接续说明*.md`）；并且**事先**告诉干活的 agent 会有监督 agent 来提醒。
2. **先探通道**——第一条自动消息是连通性探测，预期无人回复。它不来，说明通道是坏的，后面全是演戏。
3. **监督提醒**——五段结构的消息，**顺序本身就是交付物**：*这不是新任务* → *我读的是你的磁盘不是你的声明* → *每个任务码的三态账目* → *从规划原文复述门槛* → *每完成一项就存入口文件与完成状态 JSON*，最后以「请开始，不必回复说明」收尾。
4. **反伪造规则**——必须在提醒里明写，因为无人值守的一轮里没有人工去拦一个编造的结果。
5. **恢复**——先读接续说明和完成状态 JSON，问审计磁盘上真有什么，跳过所有 `complete` 的块，从第一个不是 `complete` 的块继续。
6. **阶段决定**——这一轮的终点是规划里的决定块（`继续 / 补资料 / 暂停`），不是最后一个任务码。

完整流程与每条规则背后的理由，见
[`skills/research-plan-supervised-run/SKILL.md`](skills/research-plan-supervised-run/SKILL.md)；
可直接复制的消息模板见
[`references/supervisor-message-templates.md`](skills/research-plan-supervised-run/references/supervisor-message-templates.md)，
交接契约见
[`references/handoff-artifacts.md`](skills/research-plan-supervised-run/references/handoff-artifacts.md)。

---

## `progress_audit.py`

把一轮的产出目录对着描述它的规划做只读审计。

```sh
python skills/research-plan-supervised-run/scripts/progress_audit.py <plan.md> <round-dir> [--json report.json]
```

它回答监督者在开口提醒任何人之前必须问的三个问题：

- **声明过的产物哪些真的存在？** 每个产物三态：`present` / `found-elsewhere` / `missing`——刻意保留三态，因为「写错目录」和「根本没写」要发的提醒不一样。
- **哪些任务算完成？** `complete` / `partial` / `not-started` / `no-artefact`。
- **交接产物在不在？** 入口文件、完成状态 JSON、接续说明。

规划文件或目录不存在时退出码 2。

### 在真实一轮上的实测

对着一份 12 任务规划（BC01–BC12）和它真实的产出目录——12 个任务码、40 个声明产物：

| 状态 | 任务数 | 明细 |
| --- | --- | --- |
| `complete` | 10 | BC01–BC06、BC08、BC10–BC12 |
| `partial` | 2 | BC07 缺 `可重复模拟程序`；BC09 缺 `全部过程关系图.png` |

40 个声明产物里 38 个在磁盘上，2 个真的不存在。

同一目录里找到的交接产物：**18** 个入口文件、**29** 个完成状态 JSON、**3** 份接续说明。

有两件事审计必须做对，而朴素的检查都会做错：

- **规划会省略。** 一个块的第一个产物带子目录前缀，其余都写裸文件名。这一轮 38 个在盘产物里有 26 个是裸文件名，而且**没有一个**在轮次根目录下存在——它们只在各自块的子目录里能解析出来。没有锚点目录解析，这 26 个全会被报成「缺失」，监督者就会让干活的 agent 把已经做完的工作重做一遍。
- **`missing` 和 `found-elsewhere` 必须分开。** 写错目录的文件和没写的文件是两种问题，要发的提醒也不同。本脚本早先的版本就误报过一次：一个文件其实就在它声明的位置上，扫描器却先找到了另一个同名文件就判成「放错地方」。让声明路径具有权威性、只在兜底时才走目录遍历，才是把这两种情况分开的做法。

---

## 仓库结构

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

## 测试

```sh
python -m pip install pytest
python -m pytest tests/ -q
```

22 项测试，覆盖任务块解析、产物提取、三态解析、交接产物探测、CLI 契约。

## 相关技能

- **[numbering-research-planning-writing](https://github.com/xiwang-geo/numbering-research-planning-writing)** —
  写本技能要跑的那份规划（同一条工作流的另一半）
- **[hermes-history-claude](https://github.com/xiwang-geo/hermes-history-claude)** /
  **[hermes-history-codex](https://github.com/xiwang-geo/hermes-history-codex)** —
  读历史会话记录；要重建一轮到底做过什么时有用

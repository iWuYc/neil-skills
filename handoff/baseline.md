# handoff skill — baseline（RED phase drift 记录）

> 本文件记录 skill 创建时的"基线假设"——即在没有 skill 时，AI 在用户说"今天先到这儿"时会自然犯哪些错。skill 的每条核心规则都是为了堵这些错而写。
>
> 记录时间：2026-07-16

## RED phase：未读 SKILL.md 时 AI 会犯的错

### Baseline 假设 1 — AI 会输出"工作总结"而非"交接文档"

无 skill 时，AI 听到"今天先到这儿"，会立刻写一段"刚才我们完成了 1. …，2. …，3. …"的**回顾型摘要**。

**为什么错**：用户要的不是"刚才做了什么"，是"下次怎么接着做"。工作总结无法让零上下文的未来 AI 接手。

**skill 对应规则**：核心原则 §1（"交接文档是给零上下文的未来 AI 看的"）、Do NOT use（"用户只是要一个普通的工作总结"）。

---

### Baseline 假设 2 — AI 会把大段代码贴进 handoff

无 skill 时，AI 倾向于把"正在改的函数"完整复制粘贴到 handoff 里，让下次 AI"看一眼就知道"。

**为什么错**：复制 200 行代码到 handoff = 文档膨胀，下次 Read 浪费 token；更重要的是，代码会过期，下次 AI 看 handoff 时代码可能已经又改过了。

**skill 对应规则**：核心原则 §2（"写路径，不抄代码"）、Common pitfalls 表第 1 行。

---

### Baseline 假设 3 — AI 会用"我们刚才……"这种主语

无 skill 时，AI 写"我们刚才讨论了 X，决定用 Y"。

**为什么错**：下次 AI 没有"我们"——它和上次 AI 是不同实例。这种主语下次读起来像在读别人日记。

**skill 对应规则**：核心原则 §3（"不假定下次是同一个 AI"）、§8 重启指南里也强调。

---

### Baseline 假设 4 — AI 不会问"写到哪儿"

无 skill 时，AI 默认写到 `cwd/`，不问用户。

**为什么错**：用户可能在临时目录 / scratch 目录 / 全局笔记目录里，不一定想写到 cwd。Obsidian 用户想 link 到 daily note；多项目用户想集中管理。

**skill 对应规则**：Step 1 Q1 强制 AskUserQuestion 3 选 1（项目内/全局/Obsidian）。

---

### Baseline 假设 5 — AI 不会主动列出"未决问题"

无 skill 时，AI 会把"用户还没拍板的事"埋在已完成/进行中列表里。

**为什么错**：下次 AI 不知道哪些是"已完成"，哪些是"用户绕开但没确认"。这两类信息需要不同的处理——已完成的不动，未决的应主动问。

**skill 对应规则**：Step 2.5 单独成 §5、未决问题用 ❓ 标签。

---

### Baseline 假设 6 — AI 不会考虑 secrets

无 skill 时，AI 可能把刚调通过的 API token、刚生成的 SSH key、刚收到的 webhook 密钥复制进 handoff。

**为什么错**：handoff 可能进 git（用户可能没意识到）、可能 world-readable（全局目录）、可能 sync 到云端——任何一种情况都泄露。

**skill 对应规则**：核心原则 §6（"secrets 不进 handoff"）、Step 4 收尾汇报时提醒用户、Quick reference 提供 grep 自检命令。

---

### Baseline 假设 7 — AI 不会记 git 状态

无 skill 时，AI 写"commit 了 X / Y / Z"，但不写当前 commit hash、工作区 dirty 状态。

**为什么错**：下次开会话，`git status` 可能已经变（用户又改了别的、切换了分支）。下次 AI 不知道"上次做完时分支在哪个 commit"。

**skill 对应规则**：Step 2.1 元信息表 5 个字段（branch / commit / dirty / 未推送 / session ID）、§1 元信息章节强制包含。

---

### Baseline 假设 8 — AI 不会写"重启指南"

无 skill 时，handoff 是"档案柜"风格——堆事实，但不说"下次 AI 该按什么顺序读 / 怎么用这些事实"。

**为什么错**：下次 AI 拿到 handoff，要么不知道从哪读起，要么读完不知道第一步做什么。

**skill 对应规则**：§8 重启指南强制包含 6 步骤 + "不要做的事"清单。

---

### Baseline 假设 9 — AI 不会覆盖同名文件

无 skill 时，AI 直接 Write 同名文件 → 丢内容。

**为什么错**：用户可能在前一会话已经写过同名 handoff，覆盖后无法恢复。

**skill 对应规则**：Step 3 写入规则——同名加 `-1` 后缀（除非用户明确选"覆盖"）。

---

### Baseline 假设 10 — AI 不会处理"用户要的是项目文档不是会话交接"

无 skill 时，AI 不区分"任务中断要 resume"和"项目文档给团队看"——两者都按 handoff 流程写，结果可能把个人 session 信息泄露到团队文档。

**为什么错**：handoff 是私人上下文（未决问题、调试草稿、临时 commit），不是项目文档。混着用会让团队文档噪声很大、个人草稿误进 git。

**skill 对应规则**：Do NOT use 表第 4 行、Common pitfalls 表最后一行（"二次确认"）。

---

## GREEN phase：SKILL.md 的每条规则对应的 baseline 错

| skill 规则 | 防的 baseline 错 |
|---|---|
| 核心原则 §1（面向零上下文未来 AI） | Baseline 假设 1 |
| 核心原则 §2（写路径不抄代码） | Baseline 假设 2 |
| 核心原则 §3（不用"我们刚才"） | Baseline 假设 3 |
| Step 1 Q1（问写到哪儿） | Baseline 假设 4 |
| Step 2.5 / §5（未决问题独立成节） | Baseline 假设 5 |
| 核心原则 §6 + Step 4 收尾（secrets 自检） | Baseline 假设 6 |
| Step 2.1 / §1 元信息（git 状态） | Baseline 假设 7 |
| Step 2.8 / §8 重启指南 | Baseline 假设 8 |
| Step 3 写入规则（同名加 `-1`） | Baseline 假设 9 |
| Do NOT use + Common pitfalls（区分 session handoff vs 项目文档） | Baseline 假设 10 |

---

## REFACTOR phase：skill 还可能漏的洞

- **AI 主动触发**：用户没说要中断，但 AI 觉得上下文过长——skill 已加 Step 0 的"AI 主动触发"判断表，但**未充分测试**主动触发时机的准确性（"中信号"边界）。
- **Obsidian vault 路径检测**：skill 假设用户有 vault，但没规定如何探测默认 vault 路径。可能用户想用 vault 但 skill 跳到了全局目录。
- **多任务并发**：用户在同一会话里同时推进 2+ 个任务（如"任务 A 做到一半切到任务 B，现在要交接 B"）——skill 默认一个 handoff 一个任务，未规定如何拆分多任务。
- **handoff 进 git 的例外处理**：项目内 `.handoff/` 默认 gitignore，但如果用户**明确要进 git**（如交接给远程协作者），skill 只说"建议 gitignore"，没说"用户拒绝怎么办"。

下次有人发现 baseline 假设 11+，请追加到本文件。

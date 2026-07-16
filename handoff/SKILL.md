---
name: handoff
description: Use when the user wants to pause an in-progress task and resume later in a future session — signals include "今天先到这 / 我先下了 / 明天接着做 / 留个交接文档 / save my context / create a handoff / 任务中断先存起来". Default trigger is proactive — fires at two critical points (context near exhaustion / task nearly done with open tails), NOT in the middle of active work. Pause-style phrases ("暂停一下 / 等下回来 / brb") are explicitly excluded as triggers since they mean "5-minute break", not "session end". Produces a single Markdown handoff file capturing task goal, progress, decisions, open questions, next steps, and a restart guide so the next Claude (with zero prior context) can pick up exactly where the current session left off. Distinct from session summary skills and commit skills.
---

# handoff

> 把"当前会话 + 当前任务"的状态沉淀到一个 markdown 文件，下次开新会话时 AI 能凭它立刻接着干。

## When to use this skill

**Use this skill when ANY of the following is true:**

- 用户明确说"今天先到这儿"、"我先下了"、"明天接着做"、"交接一下"、"保存上下文"、"先把状态存起来"、"save the context"、"create a handoff"、"留个交接文档"、"任务中断先存起来"
- 用户即将关闭会话、做超时休息、被叫去开会，明显要中断手头任务
- AI 自己判断上下文已经接近耗尽（用户翻看历史很慢 / 反复要求总结 / 工具结果累积过多），主动建议"先生成一份交接文档吧"
- 用户在长任务（多步骤 / 跨多个文件 / 跨多个 commit）中途说"等下回来再说"

**Do NOT use this skill when:**

- 用户只是要一个普通的工作总结 / 会议纪要 / 进度汇报（用 `internal-comms` 或直接写总结即可）—— handoff 必须**面向"下次怎么接着干"**，不是"刚才做了什么"
- 用户只想做一次 commit（用 `git-commit-helper`）
- 任务已经全部完成，没有"未完成的部分"——handoff 至少要有一个 §"下一步行动"项，否则无意义
- 用户希望把交接文档发给团队成员阅读（这是**项目文档**而非**会话交接**——用普通的 markdown 写作）
- 用户只问"刚才我们聊了啥"——这是回顾而非交接，直接给个简短摘要即可

## 核心原则

1. **交接文档是给"零上下文的未来 AI"看的**，不是给用户自己看的。下次新会话的 AI 没有任何本次会话的 memory；handoff 必须是它能照着执行的剧本。
2. **写路径，不抄代码**：禁止把大段代码贴到 handoff 里。用 `file:line` 引用，下次 AI 直接 `Read` 即可。把整个 `xxx.java` 复制粘贴会立刻让文档膨胀到 5000+ 行，浪费 token 且容易过期。
3. **不假定下次是同一个 AI**：避免"我们刚才……"这种主语——改成"任务背景：……"。文件名、commit hash、文件路径必须绝对路径，避免相对歧义。
4. **决策要带理由**：每个"为什么这么做"必须写明当时在选 A/B/C，最终选了 X，理由是 Y。下次 AI 才有依据判断"如果 Y 变了，是不是该回头改成 Z"。
5. **未决问题必须显式列**：用户没说清 / 当时绕开的事项，**单独成一节**，下次回来第一件事就是看这一节。
6. **secrets 不进 handoff**：API key / token / 密码 / 私钥 / `.env` 内容**绝不写**。引用文件路径即可（如"读取 `~/.config/myapp/credentials` "），让下次 AI 自己读。
7. **写到哪里问一次用户**：默认写到项目内的 `.handoff/`，但用户可能想要全局 handoffs 目录、或想写到 obsidian vault 里——**必须用 `AskUserQuestion` 问一次**。

## Workflow（5 步法）

```
Step 0 — 中断信号识别（inline 或 AI 主动建议）
   ↓
Step 1 — 与用户确认 3 件事（AskUserQuestion，必做）
   ↓
Step 2 — 收集状态（inline，从会话上下文 + git + 工作区）
   ↓
Step 3 — 生成 handoff markdown（Write）
   ↓
Step 4 — 收尾汇报（终端输出：路径 + 摘要 + 如何重启）
```

---

## Step 0 — 触发判断（主动优先）

> **核心策略**：本 skill 默认**主动触发**。AI 在上下文即将耗尽 / 任务接近完成时才问"要不要交接"。用户主动说"暂停一下"/"等下回来再说"这种 5 分钟休息词**不算触发**——必须用户明确说要中断会话、留交接文档才触发。

### 触发模式 A：AI 主动触发（默认）

**只在以下两个临界点之一同时满足时，才主动建议生成 handoff**：

**临界点 1 — 上下文即将耗尽**（任一满足）：
- 用户**连续**要求 AI 总结前文 ≥ 2 次（"总结下刚才我们做了什么"/"再帮我回顾一下"）
- AI 已经反复重新读同一个文件 ≥ 3 次（自己都觉得"我先看下刚才那个文件"）
- 工具结果累积导致响应变慢 / 输出截断 / 系统提示 token 紧张
- 当前会话已 ≥ 30 轮，且未完成的任务跨 ≥ 3 个文件

**临界点 2 — 任务接近完成但还有未关闭的尾巴**（任一满足）：
- 已 commit 数 ≥ 3，git log 显示进度稳定推进
- 当前改的文件已通过 lint / test 局部验证，但整体功能还没串起来
- 用户已经把任务拆成 todo list 且 ≥ 70% 完成

**两个临界点都满足 + 任务尚未全部完成** → 主动建议。话术模板：

> "我们这个任务已经推进了相当多步（改了 N 个文件，做了 M 个 commit），上下文也累积了挺多。任务看起来接近完成了但还有未关闭的部分——**要不要我现在生成一份交接文档存到 `.handoff/`，下次接着干？** 如果今天能一鼓作气做完，咱们就继续。"

**关键约束**：
- 用户说"不用 / 继续 / 接着干" → 不生成，**本会话剩余时间内不再主动问**（最多只在每次 commit 后提一次"要不要现在生成？"）
- 任务正在活跃推进时（AI 刚答完问题 / 用户刚发新指令 / 工具结果刚返回）**绝不触发**——只在"自然间隙"问
- 用户最近一次 commit 距离现在 ≤ 5 分钟 → 也不触发（任务显然还在进行中）

### 触发模式 B：用户主动触发（兜底）

**只接收强信号词**——中信号词显式排除。

**强信号词（立即触发）**：

| 中文 | 英文 |
|---|---|
| 今天先到这儿 / 今天就到这儿 / 今天就到这 | let's stop for today / done for today |
| 我先下了 / 我先走了 / 收工 / 回家了 | I'm signing off / I'm heading out |
| 明天接着做 / 下次再弄 / 下次继续 | resume tomorrow / continue later / pick this up tomorrow |
| 交接一下 / 留个交接文档 / 保存上下文 / 写个 handoff | handoff / save context / create a handoff doc |
| 任务中断先存起来 / 这个先存一下 | park this task |

**中信号词（**绝不触发**——用户只是 5 分钟休息，还要继续干）**：

| 中文 | 英文 | 为什么排除 |
|---|---|---|
| 暂停一下 / 等一下 | pause / hold on | 5 分钟休息，不是会话终止 |
| 等下回来再说 / 一会儿回来 | back in a bit / be right back | 同上 |
| 我去喝杯水 / 接个电话 | brb / grabbing coffee | 同上 |

**识别规则**：
- 用户消息里出现**任一强信号词** → 立即触发 Step 1
- 只有中信号词 → **完全不响应**，等用户回来继续；如果用户真要交接，他下次会说强信号词
- 用户没说任何中断词 + 触发模式 A 也不满足 → 继续正常推进，不生成 handoff

---

## Step 1 — 与用户确认 3 件事（必做）

**用一次 `AskUserQuestion` 问齐 3 个问题，不要分多次问**：

### Q1: 写到哪儿（location）

- **项目内 `.handoff/`**（Recommended）—— 跟代码一起版本化（**注意：通常应该 gitignore `.handoff/`**，见 §"gitignore 规则"）
- **全局 `~/.claude/handoffs/`** —— 不进项目仓库，跨项目保留
- **Obsidian vault** —— 用户通常有 vault 路径，handoff 可链接到 daily note

预填推荐项时根据当前 `cwd` 判断：

| 当前 cwd | 默认推荐 |
|---|---|
| 在某个 git 仓库里 | 项目内 `.handoff/` |
| 在 `~/` 或不在任何 git 仓库 | 全局 `~/.claude/handoffs/` |
| 用户最近用过 Obsidian（detected by `~/.config/obsidian` 存在） | Obsidian vault |

### Q2: 文件名 slug

- **基于任务主题**（Recommended）—— 如 `feat04-label-sync`、`bug-2026-07-13-login-fail`
- **时间戳** —— 如 `2026-07-16T15-30`
- **连续序列号** —— 在目录里扫已有 handoff，编号 `001-...`、`002-...`

### Q3: secrets 处理

- **不包含敏感信息**（Recommended）—— 引用路径，不抄 token
- **包含临时调试值**（仅本地密钥环里的）—— 标 `local-only`，写到 .gitignore 保护

如果用户已经在消息里明确写了"交接到 `<path>`"或"用任务主题命名"等问题答案，可以**直接跳过对应问题**，但**至少要问 Q1**（不知道写哪儿就是猜）。

### 写入路径示例

| Q1 选择 | 实际写入路径 |
|---|---|
| 项目内 `.handoff/` | `<cwd>/.handoff/<slug>.md` |
| 全局 `~/.claude/handoffs/` | `~/.claude/handoffs/<project-slug>-<slug>.md` |
| Obsidian vault | `<vault>/Handoffs/<date>-<slug>.md` |

记录用户回答后，进入 Step 2。

---

## Step 2 — 收集状态（inline）

**不要派 subagent**——状态收集必须 inline 做，因为 subagent 看不到本次会话上下文。可以用辅助工具，但内容靠主 agent 整理。

### 2.1 — 元信息收集

| 字段 | 来源 |
|---|---|
| 生成时间 | `date` 工具或本地时区（用 ISO 8601） |
| 项目名 | `<cwd>` 的 basename |
| 项目根绝对路径 | `pwd` / `Bash` |
| git branch | `git rev-parse --abbrev-ref HEAD` |
| git commit hash | `git rev-parse HEAD` |
| git dirty 状态 | `git status --porcelain` |
| 未推送 commit 数 | `git log --oneline @{u}..` 或 `git status -sb` |

如果 `git status --porcelain` 输出非空 → §"当前进度"必须包含"工作区有未提交改动（见 §上下文文件）"。

### 2.2 — 任务目标

从会话中提取：

- 用户**最初**说的目标（1-3 句话，不超过 200 字）
- 涉及的范围（哪些文件 / 哪些模块 / 哪些子系统）
- 成功的判定标准（用户说过"做完 X 就算 OK"的——这种话必须记下来）

### 2.3 — 当前进度

按"已完成 / 进行中 / 待开始"三段：

```markdown
### ✅ 已完成
- [x] xxx（commit abc1234 / file path:line）
- [x] yyy（commit def5678）

### 🔄 进行中
- [ ] zzz（已做了一半，见 file path:line，下一步：……）

### ⏳ 待开始
- [ ] 后续步骤 1
- [ ] 后续步骤 2
```

### 2.4 — 关键决策

按时间顺序，每条决策含 4 个字段：

```markdown
### 决策 N — <标题>
- **时间点**：约 ISO 时间（估算）
- **选项**：A / B / C
- **选择**：A
- **理由**：……（引用当时的取舍）
- **反悔条件**：如果 X 变了 → 改成 B
- **代码位置**：file path:line（commit hash）
```

### 2.5 — 未决问题

每个未决问题必须**显式列出**，带 "等待用户回答" 标签：

```markdown
- ❓ Q1: <问题>（等待用户回答）
- ❓ Q2: <问题>（已用占位符 X 继续推进，但应回问）
```

### 2.6 — 上下文文件路径

按重要程度排序，每条带说明：

```markdown
| 文件 | 行号/方法 | 说明 |
|---|---|---|
| `<绝对路径>`:123 | `methodName` | 当前正在修改的函数 |
| `<绝对路径>`:456 | `class X` | 决策相关的关键类 |
| `<绝对路径>`:789 | N/A | 配置文件，下次改这里 |
```

**绝对路径优先**——相对路径下次 cd 不同就会错。`<绝对路径>` = `<cwd>` 解析后的路径。

### 2.7 — 下一步行动

按执行顺序，**每步必须可被下次 AI 直接执行**（不是"完善功能"这种虚的）：

```markdown
1. <第一步>——具体动作（"在 file:line 处把 X 改成 Y"）
2. <第二步>
3. ...
```

### 2.8 — 重启指南

给下次 AI 看的一段简短 instruction：

```markdown
## 重启指南（给下次 AI）

你接手了一个中断的任务。请按以下顺序：

1. **先读本文档全文** —— 这是本次会话所有上下文。
2. **检查 §元信息** —— 确认 git 状态、commit hash 是否仍一致。
3. **扫 §未决问题** —— 这些是用户还没拍板的事，开局先问。
4. **按 §下一步行动 顺序执行** —— 不要并行、不要自作主张换顺序。
5. **执行前用 git status --porcelain 比对** —— 工作区是否干净？如有未提交改动，先 `git diff` 看看是不是上次留下的。
6. **任何决策冲突时** —— 优先信 §关键决策 里的"反悔条件"。

不要做的事：
- 不要重读整个仓库（除非 §上下文文件 不够用）
- 不要重做已完成项（看 §当前进度 ✅ 列表）
- 不要修改 secrets 相关文件（用户没让你碰）
```

---

## Step 3 — 生成 handoff markdown（Write）

### 文件 frontmatter（YAML）

```markdown
---
type: handoff
date: 2026-07-16T15:30+08:00
project: <project-name>
project_root: <绝对路径>
branch: <branch>
commit: <hash>
session: <如能取到 session id，否则 "unknown">
tags: [handoff, <project-name>, <feature-slug>]
---
```

### 正文骨架（强制 8 节）

```markdown
# Handoff: <任务标题>

> 1-3 句话概述：什么任务、进展到哪、下次回来第一步做什么。

## 1. 元信息

- **生成时间**：<ISO 8601>
- **项目**：<name>（<绝对路径>）
- **分支**：<branch>
- **Commit**：<hash>（<short message>）
- **工作区状态**：clean / dirty（<N> 个未提交改动）
- **未推送 commit**：<N> 个（`git log @{u}..`）
- **会话 ID**：<session id 或 "unknown">

## 2. 任务目标

<1-3 句话，引用用户最初的表述>

成功标准：<用户说过的"做完 X 就算 OK"的话>

涉及范围：
- 模块 / 文件：xxx
- 模块 / 文件：yyy

## 3. 当前进度

### ✅ 已完成
- [x] xxx（commit abc1234 / file:line）
- [x] yyy（commit def5678）

### 🔄 进行中
- [ ] zzz（已做了一半，见 file:line，下一步：……）

### ⏳ 待开始
- [ ] 后续步骤 1
- [ ] 后续步骤 2

## 4. 关键决策

### 决策 1 — <标题>
- **时间点**：约 <ISO>
- **选项**：A / B / C
- **选择**：A
- **理由**：……
- **反悔条件**：如果 X 变了 → 改成 B
- **代码位置**：file:line（commit hash）

### 决策 2 — ...

## 5. 未决问题

- ❓ Q1: <问题>（等待用户回答）
- ❓ Q2: <问题>（已用占位符 X 继续推进，但应回问）

## 6. 上下文文件路径

| 文件 | 行号/方法 | 说明 |
|---|---|---|
| `<绝对路径>`:123 | `methodName` | 当前正在修改的函数 |
| `<绝对路径>`:456 | `class X` | 决策相关的关键类 |

## 7. 下一步行动

1. <具体动作>
2. <具体动作>
3. ...

## 8. 重启指南

<见 Step 2.8>
```

### 写入规则

- 用 `Write` 工具，**绝不覆盖**已有 handoff（同名时改为 `<slug>-1.md`、`<slug>-2.md`）
- 用 `Edit` 改写已存在的同名 handoff（如果用户在 Step 1 Q2 选了基于任务主题命名，且想覆盖）—— **默认不覆盖**
- 项目内 `.handoff/` 写入后**提醒用户**："建议把 `.handoff/` 加到 `.gitignore`"（见下方 gitignore 规则）
- 全局 `~/.claude/handoffs/` 写入后**自动**检查文件权限（不应 world-readable）

### gitignore 规则

handoff 文件**通常不应该进 git**，因为它包含"未完成任务的上下文"，会污染 commit history。建议：

```gitignore
# 在项目根 .gitignore 里追加：
.handoff/
```

**例外**：如果 handoff 是"项目文档"而非"会话交接"（用户在 `Do NOT use` 里看到的场景），那它该进 git，由用户自己管。

---

## Step 4 — 收尾汇报（终端输出）

完成后给用户一个简短摘要（≤ 15 行）：

```text
✅ Handoff 已生成：<绝对路径>

包含 8 节：元信息 / 任务目标 / 当前进度 / 关键决策 / 未决问题 / 上下文文件 / 下一步 / 重启指南。

关键摘要：
- 任务：<一句话>
- 进度：已完成 N 项 / 进行中 M 项 / 待开始 K 项
- 待决策：<N> 个未决问题（见 §5）
- 下次第一步：<一句话>

⚠️ 提醒：
- 建议把 `.handoff/` 加到 `.gitignore`（handoff 通常不应进 git）
- 不要在 handoff 里留 secrets；如已留，用 sed 或编辑工具移除

重启方式：下次开会话时说"读 `<handoff path>` 然后按 §7 接着做"。
```

---

## Common pitfalls

| 陷阱 | 后果 | 防范 |
|---|---|---|
| 抄大段代码到 handoff | 文档膨胀到 5000+ 行，下次 Read 浪费 token | 用 `file:line` 引用，让下次 AI 自己 Read |
| secrets 进 handoff | API key/token/密码泄露 | Step 2.7 显式提醒"不要写 secrets"；自检时 grep `sk-` / `password` / `token` / `Bearer ` |
| 写相对路径 | 下次 cd 不同就找不到 | 强制 `<绝对路径>` |
| 未决问题被埋进行动列表 | 下次 AI 直接跳过 | §5 单独成一节，开局先读 |
| 决策不带反悔条件 | 下次 AI 不知何时该推翻 | §4 每条决策都加"反悔条件" |
| 覆盖已有 handoff | 丢了之前的内容 | 默认不覆盖；同名加 `-1` 后缀 |
| 不问写到哪儿 | 写到错误位置（项目内 vs 全局） | Step 1 Q1 必问 |
| 工作区 dirty 不记 | 下次 git status 一脸懵 | §1 元信息必含 git status |
| 没 commit hash | 下次不知道"上次做完在哪" | §1 元信息必含 commit hash |
| 用户在做的事是"项目文档"不是"会话交接" | 误把 handoff 当文档进 git | Do NOT use 列表已明确，但 AI 仍可能误判；触发时用 AskUserQuestion 二次确认"你是要 resume 时用的 handoff，还是要给团队看的项目文档？" |

---

## Quick reference

### 一行命令清单

```bash
# 项目内 handoff（默认）
mkdir -p .handoff && write .handoff/<slug>.md

# 全局 handoff
mkdir -p ~/.claude/handoffs && write ~/.claude/handoffs/<project>-<slug>.md

# 自检：handoff 里没 secrets
grep -iE "sk-[a-zA-Z0-9]{20,}|password|token|api[_-]?key|bearer " <handoff>.md
# 命中 → 必须删除
```

### 8 节清单（自检用）

- [ ] §1 元信息（时间/项目/分支/commit/工作区/未推送/会话ID）
- [ ] §2 任务目标（含成功标准 + 涉及范围）
- [ ] §3 当前进度（已完成/进行中/待开始）
- [ ] §4 关键决策（每个含选项/选择/理由/反悔条件/位置）
- [ ] §5 未决问题（至少 1 个 ❓ 标签，或明确"无"）
- [ ] §6 上下文文件路径（绝对路径 + 行号 + 说明）
- [ ] §7 下一步行动（每步可被下次 AI 直接执行）
- [ ] §8 重启指南（不要重读全仓、不要重做已完成项）

---

## What this skill does NOT do

- 不修改任何代码
- 不创建 commit（除非用户明确说"顺手 commit 一下"——那是 `git-commit-helper` 的活）
- 不发送邮件 / 通知（除非用户明确要求）
- 不修改 `.gitignore`（只提醒用户加）
- 不清理工作区 dirty 改动（那是用户的活）
- 不删已有 handoff 文件
- 不做项目文档（Do NOT use 列表里的场景）
- 不做工作总结 / 会议纪要（用 `internal-comms`）

---

## Related skills

- `git-commit-helper` —— 如果 handoff 完成后用户想顺手 commit 一下
- `internal-comms` —— 如果用户其实要的是工作总结，不是会话交接
- `superpowers:verification-before-completion` —— Step 3 自检"不漏 8 节"时参照

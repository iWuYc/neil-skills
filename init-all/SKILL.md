---
name: init-all
description: 'Use when the user is in a parent directory bundling multiple sub-projects (a "workspace" / "monorepo root" / "iWork" style parent) and wants EVERY sub-project onboarded at once — not just the parent. Scans direct children, filters noise (dotfile dirs, node_modules, .venv, dist, build, target), asks the user via AskUserQuestion which to init and how to handle existing CLAUDE.md/AGENTS.md files, then dispatches one sub-agent per chosen sub-project in parallel — each sub-agent calls the `init` skill (or writes a minimal fallback CLAUDE.md/AGENTS.md). After all sub-agents finish, runs `init` in the parent to produce a top-level CLAUDE.md/AGENTS.md that LINKS to per-project docs and does NOT re-summarize them (anti-summary check: no `npm run` / `uvicorn` / `pytest` / `cargo` / `go test` / `pip install` in the parent file). Triggered when the user says "init this whole workspace / /init-all / 这个工作区全部 init 一下 / 父目录 + 所有子工程都 init / 把每个子工程都生成 CLAUDE.md / 顶层和子目录都跑一遍 init".'
---

# init-all

> 父目录 = 多个子工程并排的工作区（"iWork" / "monorepo root" / "workspace" / "incubator"）。
> 一个父 `/init` 只看到父目录自己，看不到子工程。本技能让"父 + 所有子"一次性 onboard。

## When to use this skill

**Use this skill when ANY of the following is true:**

- 用户在父目录里运行 `/init`，且这个父目录下挂着多个并列的子工程
- 用户说"这个工作区全部 init 一下 / 把所有子项目都生成 CLAUDE.md / 顶层 + 子目录都跑一遍 init"
- 用户说"父目录 init，子工程也一起 init / 把当前文件夹下的工程都 onboard"
- 父目录里有混合内容：若干代码工程 + 一些噪音目录（`.obsidian`、`node_modules`、`.idea`、`.vscode`、`dist`、`build`、`.venv`、`__pycache__`、纯 dotfile 目录、纯文档目录）

**Do NOT use this skill when:**

- 当前目录本身就是单个工程，没有并列子目录（直接跑 `/init` 即可）
- 用户只想对某个**已知**子目录初始化（直接 `cd` 进去跑 `/init`）
- 用户要的是批量"装依赖 / 跑构建 / 跑测试"——那是 `git-commit-helper` / `list-git-repos` 之类的活，不是 init
- 父目录下子工程数量很多（≥ 30）且每个都很庞大——本技能会同时打满并发槽位；先让用户按业务域拆成几次跑

## The three core problems this skill solves

1. **识别**：哪些子目录是"真正的工程"，哪些是噪音？默认走黑名单剔除，**对黑名单以外的"看起来像但又不确定"的目录用 AskUserQuestion 让用户拍板**。
2. **并发**：N 个子工程 → N 个子 agent 并行处理——主 agent 上下文不被 N 份子工程代码撑爆。
3. **总纲形态**：父目录生成的 CLAUDE.md/AGENTS.md **必须**是索引型，只列工作区元信息 + 指向每个子 CLAUDE.md/AGENTS.md 的相对路径，**禁止**把每个子工程的核心内容再抄一遍到父总纲（抄出来必过期，且会爆 token）。v3 起，写完父总纲后**做一次反摘要自检**——自动捕捉常见 build/test 命令泄漏。

## Workflow

### Step 1 — 扫描 + 候选清单

在父目录里：

1. 用 `Bash` 跑 `ls -la` 拿到所有顶层子条目；**不递归**——只看直接子项，避免误把子工程内部的 `node_modules` 当成顶层噪音。
2. 对每个子项分类：
   - **黑名单目录（自动剔除，不展示）**——任何匹配下列任一规则的子项直接跳过：
     - 名称以 `.` 开头（`.obsidian`、`.git`、`.idea`、`.vscode`、`.cache`、`.config` 等）
     - `node_modules` / `__pycache__` / `.venv` / `venv` / `target` / `build` / `dist` / `out` / `.next` / `.nuxt` / `.parcel-cache` / `.turbo`
   - **明显是工程（自动加入候选，无需询问）**——存在以下任一标记文件：
     - `.git/` 目录
     - 包管理/构建标记：`package.json`、`pyproject.toml`、`Cargo.toml`、`go.mod`、`pom.xml`、`build.gradle` / `build.gradle.kts`、`Gemfile`、`composer.json`、`mix.exs`、`Project.toml`、`setup.py`
     - 源码占位：`src/`、`lib/`、`cmd/`、`app/`、`internal/`、`Sources/`
   - **其余目录（生成"可能工程"清单）**——例如纯 `README.md` 目录、`docs/` 目录、`scripts/` 目录、空目录、单文件 `xxx.sql` / `xxx.csv` 目录。**这些必须列入 AskUserQuestion 候选让用户拍板**。
3. 准备一张候选清单，按字母序：
   - `[AUTO] <dir>` —— 符合"明显是工程"标准，无需确认
   - `[ASK ] <dir>` —— 不确定，需要用户确认
4. **如果筛选后候选数 = 0**：告诉用户"没找到任何子工程"，停在这里，不要走到 Step 2。

### Step 2 — 与用户确认三件事（一次 AskUserQuestion 解决）

**必须用一次 AskUserQuestion 问齐 3 个问题，不要分多次问**：

1. **哪些子目录要 init**（多选）：
   - 预填所有 `[AUTO]` 为勾选、 `[ASK ]` 为不勾选
   - 选项是按"目录名 + 1 行理由"展示，例如 `project-a (含 package.json + .git)`
2. **怎么处理已有 CLAUDE.md / AGENTS.md**：
   - **跳过**（保留人工内容，Recommended）—— 默认推荐
   - **覆盖**（强制重新 init，会丢失人工修改）
   - **逐个确认**（每个子目录单独问，安全但打断流程）
3. **并发上限**（默认 5，选项 3 / 5 / 10）：
   - 并行 dispatch 数 — 系统并发槽位有限，太多反而慢

记录用户回答后，进入 Step 3。如果用户在第 1 题里**取消了所有勾选**，礼貌问一句"那父目录本身还要 init 吗？"——用户可能本来就只想跑父。

### Step 3 — 并行 dispatch 子 agent

对每个**被选中**的子目录 `sub_dir`，**用一次消息里多个 Agent 调用**并发派发：

```
Agent(
  subagent_type="general-purpose",
  prompt="""
你的工作目录是 <父>/<sub_dir>。
任务：在该目录下生成 CLAUDE.md 和 AGENTS.md。

首选方式：用 Skill 工具调用名为 `init` 的技能（传 skill 参数 "init"）。
  - 成功后核对：CLAUDE.md 和 AGENTS.md 真的写出来了
  - 如果 init skill 返回 "no file produced" / 没有写文件 / 报错 → 走 fallback

Fallback（init skill 不可用时）：
  1. 用 Bash 跑 `ls -la` 列出子目录
  2. Read 关键文件：README.md / package.json / pyproject.toml / 入口文件
  3. Write 一个最小 CLAUDE.md，包含：项目名、一句话描述、技术栈、关键文件
  4. Write 一个 AGENTS.md（与 CLAUDE.md 内容相同——AGENTS.md 是兼容别名）

约束：
- 你的修改只允许落在 <父>/<sub_dir>/ 下
- 不要递归 init
- <已有文件策略>
- 完成后输出一句话：<sub> 初始化结果：init-skill-成功 / fallback-成功 / 失败原因

汇报尽量简短，<8 行。
"""
)
```

**派发规则**：

- **每条消息最多 dispatch `concurrency_limit` 个**（默认 5）。多于 5 个时，分批派发：等当前批全部完成，再派下一批。
- 每批派发用**单条消息里的多个 Agent 调用**——禁止一条一条 dispatch，会退化成串行。

### Step 4 — 收集结果 + 主 agent 兜底

每批返回后：

- **成功**：`{dir: sub_dir, method: init-skill|fallback, files: [...]}` 加入成功列表
- **失败**：错误信息加入失败列表
- **跳过**（用户选跳过策略且子工程已有文件）：记录跳过原因
- **子 agent 谎报**（v3 必做）：**主 agent 复核每个被 init 的子目录**——用 Bash 跑 `ls <父>/<sub>/CLAUDE.md <父>/<sub>/AGENTS.md` 确认文件真的在。如果子 agent 报"成功"但文件不在，**主 agent 立即手写兜底 CLAUDE.md + AGENTS.md**（用 Read 看关键文件 → Write 最小内容）。v2 实测发现子 agent 可能"成功"地写到一个看不见的目录里。

所有批次跑完后，给用户一份**派发总结**：

```
init-all 完成（N 个子工程）：
✅ project-a (CLAUDE.md, AGENTS.md) — init skill
✅ project-b (CLAUDE.md, AGENTS.md) — fallback
⏭️  project-c (跳过：已有 CLAUDE.md + 跳过策略)
❌ project-d (失败：<错误摘要>)
🔧 project-e (兜底：子 agent 谎报成功，主 agent 重写)
```

### Step 5 — 父目录 init（索引型总纲 + 反摘要自检）

**只有在 Step 4 至少有一个子目录成功初始化后**，父目录才需要 init。如果全部失败 / 全部跳过，**也**应该 init 父目录——父目录仍然值得有自己的总纲。

在父目录里**优先**用 Skill 工具调用 `init` skill 生成父 CLAUDE.md/AGENTS.md。**如果 init skill 不写文件**（同子 agent 的 fallback 模式）：**主 agent 自己手写一个最小索引型 CLAUDE.md**。

**v3 新增：反摘要自检（写完父总纲后必做）**

在保存父 CLAUDE.md/AGENTS.md 之前，主 agent 用 `Read` 读一遍自己写的内容，**用 Grep 搜这些反模式**：

- `npm run` / `pnpm ` / `yarn ` —— 触发 = 重写
- `uvicorn ` / `pytest` / `python -m pip` —— 触发 = 重写
- `cargo run` / `go test` / `mvn ` / `gradle ` —— 触发 = 重写
- 子工程具体入口路径如 `main.py:app` / `src/index.js:line` —— 触发 = 重写

自检不通过就**改写那部分**再保存。**v2 实测**：eval-1 主 agent 初版父总纲含 "React + Vite"、"FastAPI"，自检命中后改写为中性"代码工程脚手架"——这就是这条规则要防的事。

**索引型模板示例**（自检通过后对照保存）：

```markdown
# <父目录名> — 工作区

## 工作区元信息
- 用途：<一句话>
- 约束：<关键约束列表>

## 子工程索引

| 子目录 | 描述 | 本地入口 |
|---|---|---|
| project-a/ | <一句话> | [CLAUDE.md](project-a/CLAUDE.md) / [AGENTS.md](project-a/AGENTS.md) |
| project-b/ | <一句话> | [CLAUDE.md](project-b/CLAUDE.md) / [AGENTS.md](project-b/AGENTS.md) |

## 如何在此工作
- 进入子工程：`cd project-a/`
- 详细技术栈、构建/测试命令见各子工程自己的 CLAUDE.md
```

### Step 6 — 收尾汇报

最后给用户一个完整总结（派发结果 + 父总纲位置 + 反摘要自检结果 + 跳过的子目录说明 + 失败子目录的错误 + 哪些用了 fallback + 主 agent 兜底了哪些），不要只说一句"完成"。

## Common pitfalls

- **递归 init**：禁止。本技能只看父目录的**直接**子项；子工程内部的子目录由子 agent 自己处理。
- **忽略黑名单**：`.obsidian`、`node_modules`、`.venv` 等是用户最常踩的噪音目录，必须在 Step 1 剔除，不要进入候选清单。
- **串行 dispatch**：一条消息一个 Agent 调用 = 串行。所有子 agent 必须**一批**派发。
- **子 agent 谎报成功**：v2 实测发现子 agent 在某些情况下"成功"地写到了隔离副本的子目录里，主 agent 看不见。**v3 起：主 agent 必复核**子目录的文件存在性，缺了主 agent 手写兜底。
- **init skill 不可用就崩**：实测 init skill 在子 agent 里"返回成功但没写文件"——必须 fallback。子 agent 的 prompt 写明 fallback，主 agent 的 Step 5 也写明 fallback。
- **父总纲抄子工程**：用户最反感的事。父总纲只做索引，不做摘要。**v3 起：写完必做反摘要自检**，grep 命中就重写。
- **已有 CLAUDE.md 的子目录被默默覆盖**：除非用户明确选"覆盖"，否则一律跳过。**注意**：跳过是"完全不写新文件"，不是"保留 CLAUDE.md 但补 AGENTS.md"——后者也是污染。
- **候选 0 还继续跑**：扫描不到任何子工程时停住，不要硬跑 `/init` 父目录。
- **隔离临时副本**：v2 实测 worktree 隔离（`git worktree add -b init-all-X`）会创建 orphan 分支不带源文件，导致子 agent 在空目录里"成功"——**v3 起不要用 worktree 隔离，直接派子 agent 到源子目录**。

## Compatibility

**需要的工具/能力：**

- `Bash`（跑 `ls` 扫描、文件存在性复核）
- `AskUserQuestion`（Step 2 三问一次性问齐）
- `Agent`（Step 3 dispatch 子 agent，general-purpose 类型）
- `Skill`（Step 5 调 `init` skill，可能 fallback 到手写）
- `Read` / `Write` / `Edit`（子 agent 与主 agent 写 CLAUDE.md/AGENTS.md）
- `Grep`（Step 5 反摘要自检）

**前置条件：** 父目录下至少 1 个候选子目录。

**未提供的环境：** 没有代码索引 MCP 也能跑，本技能不依赖代码索引。

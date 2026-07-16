# neil-skills

本仓库收录 Neil 常用的 Claude Code Skills。每个 skill 是一个独立的目录，包含一个 `SKILL.md` 文件（YAML frontmatter + 行为规范）、`scripts/` 实现、以及 `tests/` 回归测试套件。

仓库同时作为 **Claude Code skills 集合**使用：根目录下任何一个含 `SKILL.md` 的目录都会被 Claude Code 的 skill loader 自动发现并加载。

## Skills 列表

### git-commit-helper

- **路径**：`git-commit-helper/SKILL.md`
- **触发场景**：当 AI 代表用户执行 `git commit` 时使用 —— 始终先读取当前仓库的 git identity（`--local` 优先，fallback `--global`），通过 `--author` 在 `user.name` 末尾追加 `(Ai)` 后缀；绝不通过 `-c` 参数覆盖身份；绝不临时修改 `git config`；绝不允许任何形式的 `git push`。

**核心规则**：

1. **身份标识**：每次提交都必须从 `git config` 中读取真实的 `user.name` 与 `user.email`，然后以 `"${NAME} (Ai) <${EMAIL}>"` 作为 `--author` 参数提交。邮箱保持不变，仅在用户名后追加 `(Ai)` 后缀，以便在 `git log` 中区分 AI 生成与人工提交的 commit。
2. **禁止 Push**：AI 不得执行任何形式的 `git push`（包括 `git push --force`、`git push --tags`、`gh pr merge` 等所有会发布到远端的命令）。本地 commit 完全 OK，但远端推送必须由用户本人执行。
3. **强制中文 body**：每条 commit 必须有 `- ` 开头的 bullet body，描述改了什么、为什么改。一行修复也算，零豁免。
4. **Header 格式**：`{type}({branchName}): {abstractDescription}` —— `()` 是分支名槽，不是 scope。`feat(auth):` 错（scope 进了槽），`feat(auth)title` 错（冒号位置错），`feat(feature/login):` 对。
5. **`featName:` / `fix:` 元数据**：`featName: N/A` / `fix: 未知` 等占位符整行拒绝，**整行省略**而不是塞个 placeholder。

**使用方式**：

调用仓库自带的 `scripts/ai_commit.py` 脚本提交，避免手工 `git commit` 漂移。脚本在 identity 为 placeholder 时会主动拒绝。

```bash
python git-commit-helper/scripts/ai_commit.py \
    "feat(feature/login): 新增登录功能" \
    --feat-name "登录功能" \
    --message-file MSG.txt

# 或：把整条 message 写到文件里（推荐，跨行更稳）
python git-commit-helper/scripts/ai_commit.py --message-file MSG.txt
```

### staged-doc-naming

- **路径**：`staged-doc-naming/SKILL.md`
- **触发场景**：根据源文档生成带"生命周期阶段标记"的衍生文件名时使用 —— 在源文件名的"序号"和"主体"之间插入固定阶段单词（`pm` / `dev` / `plan` / `case` / `case.data` / `实施纪要`），原扩展名保留。覆盖"需求梳理 → 开发设计 → 开发计划 → 测试计划 → 测试数据 → 实施纪要"六个文档生命周期阶段。

**核心规则**：

1. **三段切分**：源 basename 切成 `<index?>.<name-body><ext?>` 三个部分 —— 序号（开头标识，无则空）、主体（中间部分，原样保留，不增删字）、最后一个扩展名（保留，不拆多扩展名）。
2. **三种序号形式**（按优先级匹配首个）：
   - 纯数字（含点分）：`001`、`12`、`1.2`、`99.99.99`
   - `v` 前缀 + 点分数字：`v1.2`、`v1.2.3`（**必须点分**；`v1` 不算）
   - 1-5 字母 + `-` + 数字（可选点分）：`rev-1`、`r-2`、`v-1`、`rev-3.0.1`（字母超 5 个如 `release-3.0` 不算）
3. **六个阶段标记是封闭列表**：未注册的阶段（如 `review`、`release`）必须拒绝并提示用户登记，不允许凭直觉生成。
4. **路径不在此 skill 范围**：只负责命名，写入路径由调用方决定。
5. **同名冲突**：目标文件已存在时，添加 `(1)`、`(2)` 后缀，不覆盖、不报错。

**使用方式**：

```bash
python staged-doc-naming/scripts/stage_naming.py "001.三月开发需求说明.md" pm
# -> 001.pm.三月开发需求说明.md

python staged-doc-naming/scripts/stage_naming.py --list-stages
python staged-doc-naming/scripts/stage_naming.py --exists-check "/path/to/001.pm.x.md"
```

### list-git-repos

- **路径**：`list-git-repos/SKILL.md`
- **触发场景**：当用户希望扫一个目录、盘点工作区、`/init` 接手新工作区、或发起跨多个 repo 的批量操作前使用 —— 用 `python scripts/list_git_repos.py` 输出一个剪枝后的 ASCII 树，每个仓库节点带当前分支名和 `*` dirty 标记。

**核心规则**：

1. **剪枝**：只输出子树中存在 git 仓库的目录；纯非 git 子树整段不显示。
2. **路径统一正斜杠**：即使在 Windows 上，输出也用 `/`，便于跨平台 pipeline。
3. **仓库判定**：以目录的**直接子项**中是否存在 `.git`（文件或目录都算）为准，正确处理 `git worktree` 的 `.git` 链接文件。
4. **状态采集可选**：默认不调 git 命令；带 `--with-status` 时才调 `git status --porcelain --branch`，单仓库 5 秒超时降级为 `unknown`。
5. **Skip 列表硬编码**：`.git`、`node_modules`、`target`、`build`、`dist`、`out`、`__pycache__`、`.venv`、`venv`、`.idea`、`.vscode` 一律不下钻、不渲染；扩展时需同步修改 `scripts/list_git_repos.py` 与 `SKILL.md`，单次 commit。

**使用方式**：

```bash
# 当前工作区，含分支与 dirty 标记
python list-git-repos/scripts/list_git_repos.py . --with-status

# 只输出绝对路径（一行一个），便于管道
python list-git-repos/scripts/list_git_repos.py E:/Workspace --format paths
```

### plan-doc-sequence

- **路径**：`plan-doc-sequence/SKILL.md`
- **触发场景**：当用户说"我要规划一个需求 / 一个 feat"、"按流程生成规划文档 / 生成 8 个规划文档 / 一次性把规划文档全列出来"时使用 —— 一次性生成 8 份规划文档的命名：001 原始需求 + 002-005（pm/dev/plan/case 计划阶段）+ 006 impl（实施）+ 007-008（audit/impl-note 实施后）。

**核心规则**：

1. **封闭 8 项序列**：001 原始、002 pm、003 dev、004 plan、005 case、006 impl、007 audit、008 impl-note。**禁止增删改顺序**——新增需同时改脚本 `SEQUENCE`、SKILL.md 表格、frontmatter stage 列表，一次 commit。
2. **001 无 stage tag**：001 是根需求，不带阶段标记。`001.root.{date}.{feat}.md` 是错的；正确为 `001.{date}.{feat}.md`。
3. **`--date` 必须 8 位纯数字**：`20260707` 对，`2026-07-07` / `2026/07/07` 错。日期由调用方决定（不是脚本取今天），保证一轮规划的所有文档同一天。
4. **`--feat` 原样保留**：脚本不 slugify、不翻译 CJK、不加前缀。`feat04动态改写` 进去、`feat04动态改写` 出来。
5. **`impl-note` 不可拆**：是单一两段 tag，不是 `impl.note`。`impl` / `audit` / `impl-note` 是本 skill 私有，不进 `staged-doc-naming` 的 `STAGE_TAGS`。
6. **002.pm 无假设规则**：脚本只发文件名；写 002.pm 内容时**禁止**编造需求澄清问题——遇到开放问题必须回问用户，列出问题清单，让用户逐条解答后再落笔。

**使用方式**：

```bash
# 生成 8 个文件名
python plan-doc-sequence/scripts/plan_doc_sequence.py \
    --feat "feat04动态改写" \
    --date 20260707

# 实际创建文件：管道到 touch
python plan-doc-sequence/scripts/plan_doc_sequence.py \
    --feat "feat04动态改写" \
    --date 20260707 | xargs -I{} touch "{}"

# 打印封闭序列表
python plan-doc-sequence/scripts/plan_doc_sequence.py --list-sequence
```

### analysis-api

- **路径**：`analysis-api/SKILL.md`
- **触发场景**：当用户在 Java Spring Boot 多模块 monorepo 里要求分析 / 梳理 / trace 一个 REST 接口的完整调用链时使用（例如 "分析 /api/v1/xxx/sync 接口的整体流程"、"梳理 X 接口的调用链"、"trace the call flow of POST /xxx"）。覆盖 Controller → Service → RPC Provider → Service → Mapper → DB，以及 MQ 生产者 / 消费者、出站 HTTP（第三方 / 外部 API）调用，输出带 Mermaid 流程图的 Markdown 报告。触发词包含任何 "跨模块接口调用链 / 业务链路 / MQ 消息流" 梳理请求，即使是 "分析下这个接口" 或 "这个同步链路是怎么走的"。

**核心规则**：

1. **目标栈假定**：被分析的项目是 Java 后端 + RPC 框架（Dubbo / gRPC / Thrift）+ 消息队列（RabbitMQ / RocketMQ / Kafka）之一。如果不是，先确认项目栈再决定是否调整报告模板。
2. **7 步法固定**：入口定位 → 模块拆分 → Provider / Mapper 下钻 → MQ 反向追踪 → 第三方 HTTP 追踪 → 主进程汇总 → 报告输出。每一步都有独立的 subagent 负责，**禁止**让一个 subagent 跨多步。
3. **subagent 强制约束**：用代码索引 MCP（如 codegraph），禁止 grep/read 循环（除非代码索引不可用）；返回结构化的接口签名 / 实现类 / 表名 / XML 路径；不跨模块扩散；完成后只返结论 + 关键代码块，不返 agent metadata。
4. **模糊边界优雅降级**：MQ 目的表 / 跨服务边界不清晰时，**停下回问用户**而不是凭直觉编造；与 `plan-doc-sequence` 的 002.pm 无假设规则属同一原则。
5. **报告承载于 references/**：本 skill 没有可执行脚本，行为规范全部在 `SKILL.md`，可复用资产放在 `references/`（`subagent-prompts.md` 通用 Prompt 模板、`provider-index.md` 模块索引模板、`report-template.md` 报告模板、`case-study-2026-07-13-label-sync.md` 实战经验教训）。

**使用方式**：

按 `SKILL.md` 的 7 步法走；subagent 的具体 prompt 与报告骨架参考 `references/` 下的四个文件。

```text
Step 1: entry-locator subagent (references/subagent-prompts.md 模板 1)
Step 2: per-module provider subagents (模板 2，按 modules 列表派发)
Step 3: mq-consumer-tracer subagent (模板 3，反向追踪消费者)
...
最终报告：按 references/report-template.md 填充，并附 Mermaid flowchart
```

### init-all

- **路径**：`init-all/SKILL.md`
- **触发场景**：当用户在父目录里挂着多个并列子工程（"workspace" / "monorepo root" / "iWork" 风格的父目录），想要一次性把"父目录 + 所有子工程"都 onboard（即每个子工程各自生成 `CLAUDE.md` / `AGENTS.md`，父目录再生成一份索引型总纲），而不是只 init 父目录。触发词包含 "/init-all"、中文 "这个工作区全部 init 一下 / 父目录 + 所有子工程都 init / 把每个子工程都生成 CLAUDE.md / 顶层和子目录都跑一遍 init"。

**核心规则**：

1. **直接子项 only**：只看父目录的直接子项，禁止递归下钻——子工程内部的子目录由子 agent 各自处理。
2. **黑名单剔除**（不展示、不询问）：`.` 开头的目录（`.obsidian` / `.git` / `.idea` / `.vscode` 等）+ 常见工具/构建目录（`node_modules` / `__pycache__` / `.venv` / `target` / `build` / `dist` / `out` / `.next` / `.nuxt` / `.parcel-cache` / `.turbo`）。
3. **一次 AskUserQuestion 问齐 3 件事**：① 哪些子目录要 init（预填 [AUTO] 勾选 / [ASK ] 不勾选）；② 已有 `CLAUDE.md`/`AGENTS.md` 怎么办（推荐"跳过"——完全不动该目录；另支持"覆盖"或"逐个确认"）；③ 并发上限（默认 5）。
4. **并行 dispatch 子 agent**：单条消息里多个 `Agent` 调用，每个子 agent 在其目标子目录里调 `init` skill（首选）或手写最小 `CLAUDE.md`/`AGENTS.md`（fallback）。**禁止**逐条 dispatch（会退化成串行）。
5. **主 agent 兜底**：子 agent 报告"成功"后，主 agent 用 `ls <sub>/CLAUDE.md <sub>/AGENTS.md` 复核文件存在；缺了主 agent 立即手写兜底——v2 实测发现子 agent 可能谎报。
6. **父总纲 = 索引型**（不抄子工程）：父 `CLAUDE.md`/`AGENTS.md` 只列工作区元信息 + 子工程相对路径表（`<sub>` → `<sub>/CLAUDE.md` / `<sub>/AGENTS.md` 链接），**禁止**在父总纲里复述任何子工程技术栈、入口路径、build/test 命令——这些信息属于子工程自己的 CLAUDE.md。写完必须做反摘要自检（grep `npm run` / `uvicorn` / `pytest` / `cargo run` / `go test` / `pip install` 等，命中就改写）。
7. **跳过策略 = 完全不写新文件**：选"跳过"时若子工程已有 `CLAUDE.md`，整个目录**不能**新增 `AGENTS.md` 或任何文件——"补一个 AGENTS.md"也是污染。
8. **不推荐 worktree 隔离**：v2 实测 `git worktree add -b init-all-X`（orphan 分支）不带源文件，子 agent 在空目录"成功"——v3 起禁止用 worktree 隔离，直接派子 agent 到源子目录。

**使用方式**：

按 `SKILL.md` 的 6 步法走（扫描 → AskUserQuestion → 并行 dispatch → 主 agent 兜底 → 父目录 init + 反摘要自检 → 收尾汇报）。子 agent 走 fallback 时直接用 `Bash` 跑 `ls` + `Read` 关键文件 + `Write` 最小内容。

### handoff

- **路径**：`handoff/SKILL.md`
- **触发场景**：当用户要中断当前任务并把会话状态沉淀下来供下次恢复时使用（例如 "今天先到这儿 / 交接一下 / 我先下了 / 明天接着做 / 留个交接文档 / save my context / create a handoff / 任务中断先存起来"）。**默认主动触发** —— AI 在两个临界点（上下文即将耗尽 / 任务接近完成但有未关闭尾巴）才主动建议生成 handoff；任务正在活跃推进时**绝不触发**。"暂停一下"/"等下回来"/"brb" 等 5 分钟休息词**显式排除**为触发信号 —— 用户只是去喝杯水还要继续干，不是会话终止。**与"工作总结 / 会议纪要 / 项目文档"严格区分**——handoff 必须是面向"零上下文的未来 AI 接着干"的剧本，不是回顾型摘要。

**核心规则**：

1. **触发策略 = 主动优先 + 强信号兜底**：
   - **触发模式 A（默认 / AI 主动）**：仅在两个临界点**同时满足**才建议——① 上下文即将耗尽（连续 ≥ 2 次总结请求 / 重复读同一文件 ≥ 3 次 / 工具结果累积 / ≥ 30 轮对话）或② 任务接近完成但还有尾巴（≥ 3 个 commit / 局部 lint+test 通过但功能未串 / todo 完成 ≥ 70%）。任务活跃推进中 / 最近 commit ≤ 5 分钟 / 用户刚发新指令 → **绝不触发**。
   - **触发模式 B（兜底 / 用户主动）**：只接收强信号词（"今天先到这 / 我先下了 / 明天接着做 / 留个交接文档"等）。中信号词（"暂停一下 / 等下回来 / 接个电话"）**显式排除**。
   - 用户说"不用 / 继续" → 本会话剩余时间不再主动问，最多在每次 commit 后提一次。
2. **强制 8 节骨架**：§1 元信息（时间/项目/分支/commit/工作区/未推送/会话ID） → §2 任务目标（含成功标准） → §3 当前进度（✅已完成 / 🔄进行中 / ⏳待开始） → §4 关键决策（每个含选项/选择/理由/**反悔条件**/位置） → §5 未决问题（❓ 标签） → §6 上下文文件路径（绝对路径 + 行号） → §7 下一步行动（每步可被下次 AI 直接执行） → §8 重启指南（6 步骤 + 不要做的事）。
3. **Step 1 必用 AskUserQuestion 问齐 3 件事**：① 写到哪儿（项目内 `.handoff/` / 全局 `~/.claude/handoffs/` / Obsidian vault）；② 文件名 slug（任务主题 / 时间戳 / 序列号）；③ secrets 处理（默认**不包含**，引用路径代替）。
4. **写路径不抄代码**：禁止把大段代码贴到 handoff，用 `<绝对路径>:line` 引用即可。复制粘贴会立刻让文档膨胀到 5000+ 行，浪费 token 且易过期。
5. **不假定下次是同一个 AI**：避免"我们刚才……"这种主语，改成"任务背景：……"；文件名 / commit hash / 文件路径必须绝对路径。
6. **secrets 零容忍**：API key / token / 密码 / 私钥 / `.env` 内容**绝不写**到 handoff。引用 `~/.config/xxx/credentials` 或 env var 名（如 `SK_PROD_TOKEN`）即可。Step 4 收尾汇报里 grep 自检 `sk-` / `password` / `token` / `Bearer `。
7. **决策带反悔条件**：每个关键决策 §4 必须含"如果 X 变了 → 改成 Y"——下次 AI 才有依据判断是否要推翻。
8. **未决问题独立成节**：§5 单独列，至少 1 个 ❓ 标签（即使为"无"，也要显式声明）。未决问题**禁止**埋进 §3 进度列表。
9. **同名不覆盖**：默认同名 handoff 加 `-1` / `-2` 后缀，绝不覆盖已有内容。如要覆盖，用户必须在 Step 1 明确选。
10. **gitignore 提醒**：项目内 `.handoff/` 默认应加到 `.gitignore`（handoff 是个人 session 上下文，不是项目文档）。skill 只提醒，不自动改 `.gitignore`。

**使用方式**：

按 `SKILL.md` 的 5 步法走（触发判断 → AskUserQuestion 三问 → inline 收集状态 → Write handoff → 收尾汇报）。`baseline.md` 记录了 RED 阶段预判的 11 个 AI 自然犯错点及对应堵漏规则（含 v2 新增的"中途误触发"）；`evals/evals.json` 包含 6 个自测用例覆盖主动触发、中信号排除、secrets 处理、写入位置选择等关键场景。

```text
Step 0: 触发判断（主动优先 — 临界点才问；用户说强信号词才响应；中信号词/活跃推进中绝不触发）
Step 1: AskUserQuestion 问齐 3 件事（location / slug / secrets）
Step 2: inline 收集状态（git/任务/进度/决策/未决/上下文/下一步/重启指南）
Step 3: Write handoff 到目标路径（同名加 -1 后缀，不覆盖）
Step 4: 收尾汇报（路径 + 摘要 + gitignore 提醒 + secrets 自检提醒）
```

### repairer

- **路径**：`repairer/SKILL.md`
- **触发场景**：当用户给出一份"问题清单"（Obsidian URL、markdown 路径、或口头枚举一组绑定到某个 commit / branch 的独立问题），希望一次性批量修完时使用 —— 读取 issue 文档、把每个问题切成独立作用域、单条消息并行 dispatch N 个 subagent、各自 fix + commit、最后回写到 issue 源文档的 checklist + 「解决方案」段落。触发词包括 "请修复其中问题 / fix issue 列表 / 修问题反馈 00X / 批量修复 / 每个问题都用独立的 subagent 修复"。天然搭档 `git-commit-helper`（每个 fix 一个 `(Ai)` commit）与 `obsidian-cli`（issue 文档读 / 写往返）。

**核心规则**：

1. **每个问题 = 一个 subagent + 一个 commit + 一段 issue 文档回写**：互不阻塞、互不干扰、上下文隔离。串行 N 轮 vs 并行单条消息派 N 个 Agent，时间差至少 N 倍。
2. **文件范围必须互斥**：每个 subagent 的 prompt 必须显式列「白名单 + 黑名单」——`不要修改与本任务无关的文件、不要触碰其他 N-1 个任务的代码`。共享底座（API 暴露 / 镜像同步）由一个 subagent 顺带做，不让并行 fix 各自顺手加。
3. **obsidian URL ≠ 磁盘真实路径**：先 Glob/Grep 在已知 vault 根目录下确认 issue 文件**唯一一份**；vault 可能存在副本（worktree / iCloud / OneDrive / Claude 隐式缓存），`obsidian read` 输出不一定等于磁盘真实文件。`obsidian append` 必须带 `file=<完整路径>`，不带可能写到 active file。
4. **subagent 必须带 commit 规则**：每个 fix 必须按项目 CLAUDE.md / 全局 CLAUDE.md 走 `git-commit-helper`（author 加 `(Ai)` 后缀、header `type(branch): 中文描述`、body 是 `- ` 开头的 bullet）——subagent 不能凭直觉 `git commit -m "fix"`。
5. **禁止 push 是全局默认**：所有 subagent 收到明确「**禁止 push**」指令；除非用户在主 agent 里显式说可以，否则不能 `git push` / `git push --force` / `gh pr merge`。
6. **回写 issue 文档不能少**：subagent 自我回报"已完成"不等于 issue 已勾选 —— 主 agent 工作流 §5 必须用 `obsidian read` 或 `Read` 工具**重新读 issue 源文件**，确认 checklist `- [x]` + 「解决方案」段落齐全。
7. **回写位置要明确到小节**：subagent prompt 必须写「用 `obsidian append file=<完整路径>` 在 `<具体小节>` 后追加」，不写「在 issue 文档里追加」（会被路由到文件末尾或 active file）。
8. **何时不要用本 skill**：单 bug → 直接 Read + Edit + git-commit-helper；问题之间有强依赖（一个 fix 依赖另一个 fix 的产物）→ 单 agent 串行处理；用户没说要批量 / 多问题。
9. **并行 ≠ 串糖葫芦**：并行 dispatch 的前提是「文件范围互斥 + 无运行时依赖」。如果 subagent 都在 `preload.js` 改 API 暴露，要么合并为一个 subagent，要么先暴露再写调用方（基础设施先行）。

**使用方式**：

按 `SKILL.md` 的 7 步法走（定位 issue → 读 issue 拆问题 → 设计 subagent 切分 → 并行 dispatch → 收尾验证 → 回写源文件 → 汇总回报）。`baseline.md` 记录了 RED 阶段预判的 10 个 AI 自然犯错点（串行单 agent / 共享工作区 / obsidian URL 直信 / 基础设施各自顺手做 / working tree 中间态 / commit 不带规则 / 顺手 push / subagent 自我汇报等于勾选 / 单 bug 误触发 / 回写位置模糊）；`evals/evals.json` 包含 5 个自测用例覆盖并行 dispatch 验证、vault 副本回问、单 bug 不触发、强依赖不并行、commit 身份 + push 禁令。

```text
Step 1: 定位 issue 源文件（Glob 验证唯一，不直信 obsidian URL）
Step 2: 读 issue，拆问题（输出问题清单数组）
Step 3: 设计 subagent 切分（白名单 + 黑名单 + commit 规则 + push 禁令 + 回写位置）
Step 4: 单条消息并行 dispatch N 个 Agent（subagent_type: general-purpose, run_in_background: true）
Step 5: 收尾验证（git log --oneline + git status + 抽查 API 一致性 + obsidian read 重新确认）
Step 6: 回写源文件（- [ ] → - [x] + 「解决方案」四级标题段落）
Step 7: 汇总回报（commit hash + 文件清单 + build/test 结果 + checklist 截图）
```

---

## 目录结构

```
neil-skills/
├── README.md                                       # 本文件，仓库总览
├── pytest.ini                                      # pytest 配置（testpaths 覆盖所有 skill 的 tests/）
├── docs/
│   └── superpowers/
│       ├── specs/                                  # 设计 spec
│       └── plans/                                  # 实施计划
├── git-commit-helper/                              # git commit 辅助（51 个回归测试）
│   ├── SKILL.md
│   ├── scripts/ai_commit.py
│   ├── tests/test_ai_commit.py
│   └── docs/.gitkeep
├── staged-doc-naming/                              # 阶段标记命名（23 个回归测试）
│   ├── SKILL.md
│   ├── scripts/stage_naming.py
│   ├── tests/test_stage_naming.py
│   └── docs/.gitkeep
├── list-git-repos/                                 # 仓库扫描 + ASCII 树（5 个回归测试）
│   ├── SKILL.md
│   ├── scripts/list_git_repos.py
│   ├── tests/test_list_git_repos.py
│   └── docs/baseline.md                            # RED 阶段基线
├── plan-doc-sequence/                              # 8 份规划文档命名（7 个回归测试）
│   ├── SKILL.md
│   ├── scripts/plan_doc_sequence.py
│   └── tests/test_plan_doc_sequence.py
├── analysis-api/                                   # Java 接口调用链分析（文档驱动）
│   ├── SKILL.md
│   └── references/
│       ├── subagent-prompts.md                     # 通用 subagent prompt 模板
│       ├── provider-index.md                       # Provider 模块索引模板
│       ├── report-template.md                      # 报告骨架模板
│       └── case-study-2026-07-13-label-sync.md    # 实战经验教训
├── init-all/                                       # 工作区批量 init：父目录 + 所有子工程（文档驱动）
│   ├── SKILL.md
│   └── evals/evals.json                            # 4 个 eval 用例
├── handoff/                                        # 任务中断交接文档（文档驱动）
│   ├── SKILL.md
│   ├── baseline.md                                 # RED 阶段预判的 10 个 baseline 错
│   └── evals/evals.json                            # 5 个 eval 用例（主动触发/secrets/位置选择等）
├── repairer/                                       # 批量修复 issue 列表（文档驱动）
│   ├── SKILL.md
│   ├── baseline.md                                 # RED 阶段预判的 10 个 baseline 错
│   └── evals/evals.json                            # 5 个 eval 用例（并行/vault 副本/强依赖/commit 规则）
├── AGENTS.md                                       # Codex 引导入口（单行指针，正文指向 CLAUDE.md）
└── CLAUDE.md                                       # 仓库指南的权威文档
```

## 运行测试

```bash
# pytest.ini testpaths 自动覆盖全部 skill 的 tests/ —— 总计 86 个回归测试
pytest                                              # 直接调用
python -m pytest                                    # 等价（如果 pytest 不在 PATH）

# 单个 skill 的测试集
pytest list-git-repos/tests/ -v

# 单条用例
pytest git-commit-helper/tests/test_ai_commit.py::test_validate_header_rejects_issue_code_in_subject -v
```

无构建步骤、无 linter、无 CI workflow。每个 skill 的 `SKILL.md` 是行为的唯一真相源，脚本是规则的可执行形式。

## 添加新 Skill

完整流程与 SKILL.md 模板规范见 `CLAUDE.md` 的 "Adding a new skill" 一节（避免在 README 与 CLAUDE.md 之间双份维护）。

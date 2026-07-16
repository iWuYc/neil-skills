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

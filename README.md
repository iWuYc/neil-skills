# neil-skills

本仓库收录 Neil 常用的 Claude Code Skills。每个 skill 是一个独立的目录，包含一个 `SKILL.md` 文件，定义了该 skill 的名称、适用场景与详细行为规范。

仓库同时作为 **Codex marketplace bundle** 打包：`plugins/neil-skills/` 是插件根，`plugins/neil-skills/.codex-plugin/plugin.json` 是 bundle 清单。`setup-marketplace.ps1` 在本机注册该 bundle 作为本地 Codex 插件源。

## Skills 列表

### git-commit-helper

- **路径**：`plugins/neil-skills/git-commit-helper/SKILL.md`
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
python plugins/neil-skills/git-commit-helper/scripts/ai_commit.py \
    "feat(feature/login): 新增登录功能" \
    --feat-name "登录功能" \
    --body "- 新增 src/auth/login.ts，校验用户名是否存在
- 新增 src/auth/password.ts，校验登录密码是否正确"

# 或：把 message 写到文件里
python plugins/neil-skills/git-commit-helper/scripts/ai_commit.py --message-file MSG.txt
```

### staged-doc-naming

- **路径**：`plugins/neil-skills/staged-doc-naming/SKILL.md`
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
python plugins/neil-skills/staged-doc-naming/scripts/stage_naming.py "001.三月开发需求说明.md" pm
# -> 001.pm.三月开发需求说明.md

python plugins/neil-skills/staged-doc-naming/scripts/stage_naming.py --list-stages
python plugins/neil-skills/staged-doc-naming/scripts/stage_naming.py --exists-check "/path/to/001.pm.x.md"
```

### list-git-repos

- **路径**：`plugins/neil-skills/list-git-repos/SKILL.md`
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
python plugins/neil-skills/list-git-repos/scripts/list_git_repos.py . --with-status

# 只输出绝对路径（一行一个），便于管道
python plugins/neil-skills/list-git-repos/scripts/list_git_repos.py E:/Workspace --format paths
```

### plan-doc-sequence

- **路径**：`plugins/neil-skills/plan-doc-sequence/SKILL.md`
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
python plugins/neil-skills/plan-doc-sequence/scripts/plan_doc_sequence.py \
    --feat "feat04动态改写" \
    --date 20260707

# 实际创建文件：管道到 touch
python plugins/neil-skills/plan-doc-sequence/scripts/plan_doc_sequence.py \
    --feat "feat04动态改写" \
    --date 20260707 | xargs -I{} touch "{}"

# 打印封闭序列表
python plugins/neil-skills/plan-doc-sequence/scripts/plan_doc_sequence.py --list-sequence
```

## 目录结构

```
neil-skills/
├── README.md                                       # 本文件，仓库总览
├── pytest.ini                                      # pytest 配置（testpaths 覆盖所有 skill 的 tests/）
├── docs/
│   └── superpowers/
│       ├── specs/                                  # 设计 spec
│       └── plans/                                  # 实施计划
├── plugins/
│   └── neil-skills/                                # Codex marketplace bundle 根
│       ├── .codex-plugin/
│       │   └── plugin.json                         # Bundle 清单（4 个 skills）
│       ├── git-commit-helper/
│       │   ├── SKILL.md
│       │   ├── scripts/ai_commit.py
│       │   └── tests/test_ai_commit.py             # 51 个回归测试
│       ├── staged-doc-naming/
│       │   ├── SKILL.md
│       │   ├── scripts/stage_naming.py
│       │   └── tests/test_stage_naming.py          # 23 个回归测试
│       ├── list-git-repos/
│       │   ├── SKILL.md
│       │   ├── scripts/list_git_repos.py
│       │   ├── tests/test_list_git_repos.py        # 5 个回归测试
│       │   └── docs/baseline.md                    # RED 阶段基线
│       └── plan-doc-sequence/
│           ├── SKILL.md
│           ├── scripts/plan_doc_sequence.py
│           └── tests/test_plan_doc_sequence.py     # 7 个回归测试
├── setup-marketplace.ps1                           # 注册本仓库为本地 Codex 插件源
├── AGENTS.md                                       # Codex agent 引导（与 CLAUDE.md 内容重叠）
└── CLAUDE.md                                       # Claude Code agent 引导
```

## 运行测试

```bash
pytest                                              # 全部 86 个测试（pytest.ini testpaths 自动覆盖 4 个 skill 的 tests/）
pytest plugins/neil-skills/list-git-repos/tests/ -v                     # 单个 skill 的测试集
pytest plugins/neil-skills/git-commit-helper/tests/test_ai_commit.py::test_validate_header_rejects_issue_code_in_subject -v   # 单条
```

无构建步骤、无 linter、无 CI workflow。每个 skill 的 `SKILL.md` 是行为的唯一真相源，脚本是规则的可执行形式。

## 添加新 Skill

完整流程与 SKILL.md 模板规范见 `CLAUDE.md` 的 "Adding a new skill" 一节（避免在 README 与 CLAUDE.md 之间双份维护）。

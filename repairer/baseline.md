# repairer skill — baseline（RED phase drift 记录）

> 本文件记录 skill 创建时的"基线假设"——即在没有 skill 时,AI 在用户说"请修复其中问题"时会自然犯哪些错。skill 的每条核心规则都是为了堵这些错而写。
>
> v1 创建:2026-07-16（11 个 baseline 假设）

---

## v1 baseline（11 条）

### Baseline 假设 1 — AI 把"修复一批问题"做成串行单 agent 串糖葫芦

无 skill 时,AI 拿到一个 5 项 issue 列表,会自然地一个一个 Read → Edit → commit,第 5 项等到前 4 项都跑完才开始。看上去"认真",实际上浪费了 4× 的 wall-clock。

**为什么错**:这 5 个问题如果在文件层面互不重叠(各自 fix 一段不同函数、不同模块),串行没意义——浪费的就是用户等待的时间。同时一个超长会话上下文会越来越脏,5 个问题下来 AI 已经记不清第 1 个问题的细节。

**skill 对应规则**:工作流 §4「并行 dispatch」——单条消息里同时派 N 个 Agent,每个 `subagent_type: general-purpose`、`run_in_background: true`。

---

### Baseline 假设 2 — AI 让所有 subagent 共享一份工作区

无 skill 时,AI 派 5 个 subagent 同时跑,5 份工作树互不知情,Git working tree 在 5 个并发 mutation 下乱套:可能 3 个 subagent 写同一个 `preload.js`,后写的覆盖先写的、冲突提示被吞掉、commit 互相吃对方的改动。

**为什么错**:并行 ≠ 让它们一起改同一份文件。文件范围必须互斥——每个 subagent 必须有"白名单 + 黑名单"两份约束。

**skill 对应规则**:工作流 §3「subagent 切分」——文件范围互斥 + 不要修改与本任务无关的文件 + 不要触碰其他 N-1 个任务的代码;`Subagent prompt 模板` 第 4 条「不要动 PROTECTED_FILES」。

---

### Baseline 假设 3 — AI 跳过「obsidian URL → 磁盘真实路径」验证,直接用 URL 写回

无 skill 时,AI 看到用户给的 `obsidian://open?vault=X&file=Y`,直接把 Y 当成 vault 文件路径,或用 `obsidian append` 不带 `file=` 参数,结果写到 active file(不一定是预期的 vault);或者 vault 有副本(worktree / Claude 隐式缓存 / 多个设备同步)时,subagent 把"解决方案"段落写到了副本,vault 源文件完全没动。

**为什么错**:Obsidian URL 是逻辑路径,磁盘文件才是真相源。vault 可能存在多份副本;`obsidian read` 输出的内容不一定等于磁盘真实文件。

**skill 对应规则**:工作流 §1「必须用磁盘搜索验证源文件真实位置」——用 Glob/Grep 在已知 vault 根目录下确认唯一一份;工作流 §6「回写位置必须用 Glob 验证过的唯一路径」+ 注意事项第 3 条「obsidian CLI 路由错误,总是带 file= 完整路径」。

---

### Baseline 假设 4 — AI 让 subagent 顺带做"基础设施"改动

无 skill 时,AI 看到多个 fix 都依赖 `preload.js` 暴露新 API,会让每个 fix 各自顺手加 API 暴露,5 份 commit 都改了 `preload.js`,merge 时炸。

**为什么错**:基础设施改动 = 共享底座,必须单 agent 串行做,不能让并行 fix 各自顺手加。"我能顺便把它做了"恰恰是冲突的来源。

**skill 对应规则**:注意事项 §多 subagent 并发常见冲突 第 1 条「让基础设施改动(API 暴露、镜像同步)由一个 subagent 顺带做」;工作流 §3「文件范围互斥」约束反向适用——共享底座必须独立成 fix。

---

### Baseline 假设 5 — AI 用 Git working tree 中间态当 commit 起点

无 skill 时,subagent A 还在改 `index.js`,subagent B 已经 commit 了 `package.json` 改了依赖版本,Git working tree 自动 recalc 让 A 的"未保存改动"看起来消失(或被错误地 include 进别人的 commit)。

**为什么错**:每个 subagent 必须在自己 verify commit 后再回写 issue 文档;不能假设 working tree 一直是稳定的。

**skill 对应规则**:注意事项 §多 subagent 并发常见冲突 第 2 条「让每个 subagent 自己 verify commit 后再回写 issue 文档」。

---

### Baseline 假设 6 — AI 让 subagent 不带 commit 规则就 commit

无 skill 时,subagent 写完代码直接 `git commit -m "fix"`——不带 `(Ai)` 后缀、不按 `type(branch): 中文 desc` header、bullet body 是英文或不带 dash,污染仓库 git identity 规则(本仓库 `git-commit-helper` skill 的核心约束)。

**为什么错**:每个 AI commit 必须按项目 CLAUDE.md / 全局 CLAUDE.md 的 commit identity 规则走;`neil-skills` 仓库明确要求走 `git-commit-helper/scripts/ai_commit.py`、author 加 `(Ai)` 后缀、禁止 push。

**skill 对应规则**:`Subagent prompt 模板` 第 5 条「用 git commit,格式严格按项目 CLAUDE.md:作者走 local + (Ai) 后缀(走 git-commit-helper skill)、header `type(branch): 中文描述` + 中文 bullet body、禁止 push」;注意事项 §Commit 规则「永远走 git-commit-helper skill 加 (Ai) 后缀」。

---

### Baseline 假设 7 — AI 在用户没禁止的情况下顺手 push

无 skill 时,subagent commit 完觉得"远程也没同步,顺手 push 一下"——这是 `git-commit-helper` skill 和全局 CLAUDE.md 都明确禁止的越权操作。

**为什么错**:push 是 outward-facing 不可逆动作,一旦推上去 team feed / CI / 别人 pull 都看到了;即使 AI 觉得合理,也不能自作主张。

**skill 对应规则**:`Subagent prompt 模板` 第 5 条子项「**禁止 push**」;注意事项 §Commit 规则「**禁止 push** 是全局默认,除非用户明确说可以」。

---

### Baseline 假设 8 — AI 让 subagent "完成了"等于 issue 已勾选

无 skill 时,subagent 自我汇报「我已完成修复,加了 4 行代码,build 通过,commit abc1234」——但 issue 文档里 checklist 还是 `- [ ]`,没有「解决方案」段落。用户的验收依赖 issue 文档,这一步漏了等于整个修复对用户不可见。

**为什么错**:subagent 自我回报不能代替 issue 文档回写;用户的"修完没"判断就是看 issue 文档的勾选状态。

**skill 对应规则**:工作流 §5「收尾验证」第 3 条「用 obsidian read 或 Read 工具**重新读 issue 源文件**,确认 checklist + 解决方案段落齐全」;注意事项 §Issue 回写不能少「subagent 自我回报『已完成』不等于 issue 已勾选,必须用 obsidian read 重新确认」。

---

### Baseline 假设 9 — AI 对「单 bug」或「强依赖问题」也启动本 skill

无 skill 时,用户说"请帮我修这个 bug",AI 也走 repairer 流程——结果就是"一个问题派 1 个 subagent",无并行收益、徒增编排开销;或者两个 fix 强依赖(第二个依赖第一个的产物,如「先改 API 暴露,再写调用方」),AI 派并行,第二个 subagent 找不到 API 直接失败。

**为什么错**:repairer 的价值前提是**多问题 + 互不依赖**;不满足这个前提,正常 Edit 流程更轻。

**skill 对应规则**:§「何时不要使用」第 1 条「单个 bug → 直接 Read + Edit + git-commit-helper」、第 2 条「问题之间有强依赖(一个 fix 依赖另一个 fix 的产物)→ 单 agent 串行处理」、第 3 条「用户没说要批量 / 多问题」。

---

### Baseline 假设 10 — AI 在 issue 回写时不指定具体小节

无 skill 时,subagent 拿到指令「在 issue 文档里追加解决方案」,要么写到文件末尾(原 issue 在文件头,新内容在尾巴,完全脱节),要么写到 active file(不是预期 vault)。

**为什么错**:回写位置不精确,等于把工作交回给用户去手工搬位置;`obsidian append` 不带 `file=` 是路由错误的高发场景。

**skill 对应规则**:注意事项 §单子 agent 处理一个 issue 时,回写位置要明确「不要写『在 issue 文档里追加』,要写『用 `obsidian append file=<完整路径>` 在 `<具体小节>` 后追加』」;`Subagent prompt 模板` 完成标准子项「用 obsidian CLI append,并指定具体小节」。

---

### Baseline 假设 11 — AI 让并行 subagent 共享 working tree 而非用 git worktree 隔离

无 skill 时,AI 派 N 个 subagent 并行编码,共享 working tree。subagent A 还在改文件 X,subagent B 已经 commit 了文件 X,Git recalc 把 A 的未保存改动覆盖,或把 A 的中间态错误地 include 进 B 的 commit。

**为什么错**:物理隔离才能真正解决并发 mutation 冲突;「文件白名单 + verify commit 顺序」只是缓解,无法应对 5+ 个并发 subagent 同时修改相互独立模块的边界文件。

**skill 对应规则**:工作流 §3.5「准备 worktree(物理隔离)」+ §4 subagent cwd 指向 worktree + §5.5 清理 worktree + Subagent prompt 模板「工作目录: <WORKTREE_PATH>」。

---

## GREEN phase:SKILL.md 的每条规则对应的 baseline 错

| skill 规则 | 防的 baseline 错 |
|---|---|
| 工作流 §4「并行 dispatch」 | Baseline 假设 1 |
| 工作流 §3「文件范围互斥」+ 模板「不要动 PROTECTED_FILES」 | Baseline 假设 2 |
| 工作流 §1「Glob 验证源文件真实位置」 + §6「回写位置必须用 Glob 验证过的唯一路径」 + 注意事项 §obsidian CLI 路由 | Baseline 假设 3 |
| 注意事项 §基础设施改动由一个 subagent 顺带做 | Baseline 假设 4 |
| 注意事项 §每个 subagent 自己 verify commit 后再回写 | Baseline 假设 5 |
| `Subagent prompt 模板` 第 5 条 commit 格式 + 注意事项 §Commit 规则 | Baseline 假设 6 |
| `Subagent prompt 模板` 第 5 条「禁止 push」+ 注意事项 §Commit 规则 | Baseline 假设 7 |
| 工作流 §5 收尾验证第 3 条 + 注意事项 §Issue 回写不能少 | Baseline 假设 8 |
| §何时不要使用 第 1/2/3 条 | Baseline 假设 9 |
| 注意事项 §单子 agent 回写位置要明确 + 模板完成标准 | Baseline 假设 10 |
| §3.5 + §4.5 + §5.5 worktree 全流程 + Subagent prompt 模板 cwd | Baseline 假设 11 |

---

## REFACTOR phase:skill 还可能漏的洞

- **vault 副本自动检测**:skill 要求人工 Glob 验证唯一路径,但没说"如何扫 vault 全部已知副本(worktree / iCloud / OneDrive / Claude 隐式缓存)";3 个 eval 都假设用户只有一个 vault。
- **跨 subagent API 对齐自检**:工作流 §5 第 3 条提到"抽查关键文件一致性",但没说"如何对 N 个 subagent 改动的同名 API 签名做交叉对比"——> 当 N ≥ 5 时人工抽查不可靠,未来可能需要一份"共享接口清单"事先给所有 subagent 看。
- **issue 文档回写原子性**:5 个 subagent 同时往同一个 issue 文件追加,虽然段落互不重叠,但 `obsidian append` 在文件级是否有锁未知——> 需要在 eval-3 实测并发回写是否丢段。
- **issue 源文件本身被列入 PROTECTED_FILES 怎么办**:用户给的 issue 路径是 `Obsidian/Vault/feedback/issue-001.md`,5 个 subagent 都必须追加它——这正好违反"文件范围互斥"原则,文档驱动式 skill 尚未规定 PROTECTED_FILES 例外清单的写法。

> v2 更新:上一版 REFACTOR 中「working tree 共享」相关条目已被 §3.5/4.5/5.5 解决（如果存在过的话）。

下次有人发现 baseline 假设 11+,请追加到本文件。
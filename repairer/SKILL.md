---
name: repairer
description: Use when the user provides an issue list (a markdown issue doc, an obsidian URL, or just a verbal enumeration of problems tied to a specific commit/branch) and wants them fixed in one shot — reads the issue, splits each item into an isolated scope, dispatches one subagent per item in parallel to fix + commit, then writes back the issue checklist + "#### 解决方案" paragraphs to the original source file. Triggers on phrases like "请修复其中问题", "fix issue 列表", "修问题反馈 00X", "批量修复", "每个问题都用独立的 subagent 修复". Pairs naturally with git-commit-helper (every fix gets a `(Ai)` commit) and obsidian-cli (issue doc round-trip). NOT for single one-line fixes — use the normal Edit/Write flow. NOT for issues that need cross-item coordination (those should be a single task).
---

# Repairer

修复一批独立问题的编排流程。核心思路：**每个问题 = 一个独立 subagent + 一个独立 commit + 一段 issue 文档回写**，互不阻塞、互不干扰、上下文隔离。

## 何时使用

- 用户给出"issue 文档"（Obsidian 链接、markdown 路径、口头枚举），里面有多个独立问题项
- 每个问题对应不同的文件 / 模块 / 子系统（**否则应该合并为一个 subagent**）
- 用户希望并行处理、每个问题单独 commit、最终回填到 issue 文档

## 何时不要使用

- 单个 bug → 直接 Read + Edit + git-commit-helper
- 问题之间有强依赖（一个 fix 依赖另一个 fix 的产物）→ 单 agent 串行处理
- 用户没说要批量 / 多问题

---

## 工作流（7 步）

### 1. 定位 issue 源文件

不要假设路径。如果用户给了 `obsidian://open?vault=X&file=Y`，先解码出 vault 名 + 文件路径。

**通用做法**（关键，踩坑过）：

```bash
# 如果是 obsidian URL：解码 vault 名 + 路径
# 如果用户给了磁盘路径：直接用
# 如果用户口头描述了问题：先 AskUserQuestion 问"是否需要落到磁盘文件"和"落到哪个路径"
```

> **必须用磁盘搜索验证源文件真实位置**。Obsidian 可能存在 vault 副本、worktree 副本、Claude 的隐式缓存副本。`obsidian read` 命令的输出不一定等于磁盘真实文件。  
> 用 `Glob` 或 `Grep` 在已知 vault 根目录下确认唯一一份。

### 2. 读 issue，拆问题

Read issue 文件，提取问题清单：

| 字段 | 提取自 |
|---|---|
| ID / 标题 | `### 问题 N.标题` 或 `- [ ]` 列表项 |
| 详细描述 | 引用块 / 描述段 |
| 解决方案段落（已存在的）| `#### 解决方案` |
| 关联文件 | 用户在描述里提到的路径、或者从问题类型推断 |

输出**问题清单数组**，每项形如：

```json
{
  "id": "P0-性能-图标",
  "title": "P0.性能问题-重构图标",
  "description": "重建图标时主进程卡死",
  "files_likely_involved": ["src/composables/useIcons.js", "src/components/IconGallery.vue"],
  "priority": "P0"
}
```

### 3. 设计 subagent 切分（关键）

每个 subagent 的 prompt **必须**满足：

- **文件范围互斥**：明确列出"你只能动这些文件 + 不要碰这些文件"
- **明确边界**：用 `不要修改与本任务无关的文件、不要触碰其他 N 个任务的代码`
- **指定验证命令**：通常是 `npm run build` + `npm test`（具体看项目 CLAUDE.md）
- **指定 commit 格式**：分支名、type、作者后缀（按项目 CLAUDE.md / `git-commit-helper` skill）
- **明示 push 规则**：项目级 / 全局级（**默认禁止 push**）
- **明示 issue 回写要求**：勾选 checklist + 追加「解决方案」段落 + commit hash

### 4. 并行 dispatch

**单条消息里同时调 N 个 Agent**，每个 `run_in_background: true`，`subagent_type: general-purpose`。

```
SendMessage 一次性发 N 个 Agent 调用
```

监控完成通知即可，不要轮询。

### 5. 收尾验证

每个 subagent 回报后，做：

- `git log --oneline -N` 确认 N 个新 commit 都在分支上
- `git status` 确认工作树干净（无未跟踪文件污染）
- 抽查关键文件一致性（如不同 fix 涉及的同名 API 签名必须对齐）
- 用 `obsidian read` 或 Read 工具**重新读 issue 源文件**，确认 checklist + 解决方案段落齐全

### 6. 回写源文件（关键，踩坑过）

**回写位置必须用 Glob 验证过的唯一路径**。踩坑案例：

> 用户给的 obsidian URL 指向 `E:\Workspace\Note\iWorknote\...`，但 claude 之前在 `E:\Workspace\iWork\utools-plugins\ibookmark\`（项目根目录）里有一份同名副本，subagent 把"解决方案"段落都写到了副本里，而 vault 源文件完全没动。

回写格式：

- checklist: `- [ ]` → `- [x]`
- 「解决方案」段落：四级标题 + 「标注」开头 + 改动 bullet + 验证 + commit hash

### 7. 汇总回报

回报给用户时包含：

- 5 个 commit 的 hash + 作者 + type
- 文件清单（每个 fix 动了哪些文件，**确认互不重叠**）
- build / test 结果
- issue 源文件 checklist 全部勾选的最终截图（`obsidian read` 输出片段）

---

## Subagent prompt 模板

每个独立 fix 的 subagent prompt 必须包含以下要素（直接复制粘贴改关键字段）：

```markdown
你是修复 subagent。任务范围严格限定：**<ISSUE_ID>**（issue 文档 `<ISSUE_FILE>`）。

工作目录：`<WORKTREE_PATH>`（已为你创建好的独立 git worktree，**不要 cd 回主仓库**）
不要修改与本任务无关的文件、不要触碰其他 <N-1> 个任务的代码、**不要触碰其他 worktree 目录**。

## 问题
<ISSUE_DESCRIPTION 引用块>

## 你必须做的事
1. Read 现有 `<FILE_1>`、`<FILE_2>` ……
2. <具体改动要求>
3. 跑 `<BUILD_CMD>` 必须通过
4. 不要动 <PROTECTED_FILES>
5. 用 git commit，格式严格按项目 CLAUDE.md：
   - 作者走 local: `<NAME> <EMAIL>` + `(Ai)` 后缀（走 git-commit-helper skill）
   - 提交格式：`<type>(<BRANCH>): <中文描述>` + 中文 bullet body
   - **禁止 push**
   - **不要尝试 merge 回主仓库**——这一步由主 agent 统一做

## 完成标准
- <SPECIFIC_OUTCOME>
- build 通过
- 已 commit（commit 会留在 worktree 自己的分支上，**不要 push**）
- **不要**操作 Obsidian issue 文档（回写统一由主 agent 收尾，避免 worktree 路径错位）
- 把 commit hash + 修改文件清单 + build 结果回报给我
```

---

## 注意事项（来自踩坑总结）

### 多 subagent 并发的常见冲突

1. **同名 API 改动**：两个 fix 都要改 `preload.js` 时，第二个 subagent 必须等第一个 commit 后再基于新版本改，否则冲突。提示：让"基础设施"改动（API 暴露、镜像同步）由一个 subagent 顺带做。
2. **工作树 reset**：subagent 完成时 Git 会自动重新计算 working tree，可能让正在编辑的 subagent 看到不完整的中间态。让每个 subagent 自己 verify commit 后再回写 issue 文档。
3. **obisidian CLI 路由错误**：`obsidian append` 不带 `file=` 参数时可能写到 active file（不一定是预期的 vault）。**总是带 `file=` 完整路径**。

### Commit 规则

永远走 `git-commit-helper` skill 加 `(Ai)` 后缀。**禁止 push** 是全局默认，除非用户明确说可以。

### Issue 回写不能少

回写 issue 文档（checklist + 「解决方案」）是用户验收的关键，**不能漏**。subagent 自我回报"已完成"不等于 issue 已勾选，必须用 `obsidian read` 重新确认。

### 单子 agent 处理一个 issue 时，回写位置要明确

不要写"在 issue 文档里追加"，要写"用 `obsidian append file=<完整路径>` 在 `<具体小节>` 后追加"。

---

## 配套使用

- **`obsidian-cli`**：读取 / 搜索 issue 文档，回写「解决方案」段落
- **`git-commit-helper`**：每个 fix 一个 `(Ai)` commit
- **`superpowers:dispatching-parallel-agents`**：当 subagent 数量 ≥ 3 时建议同时参考这个 skill 的并发策略
---
name: repairer-worktree-isolation-design
description: 给 repairer skill 增加 git worktree 隔离机制：每个 issue 一个独立 worktree 编码,主 agent 按完成时间序 merge,冲突时自动 rebase 失败再问用户,全部合并后批量清理 worktree + 临时分支。修复 baseline 假设 11(共享 working tree 互相覆盖)。
metadata:
  type: design
  date: 2026-07-16
  derived_from: repairer skill v1
---

# repairer worktree 隔离 — Design Spec

## 1. Purpose

repairer v1 在 §3-§4 已经规定了「文件范围互斥 + 并行 dispatch + subagent 自己 verify commit 后再回写」三件套,
但 baseline.md 假设 5 已经记录了痛点:5 个 subagent 共享同一份 working tree,Git 自动 recalc
让中途编辑的代码被覆盖或被错误地 include 进别人的 commit。

真实使用中确实出现了「多个 subagent 在同一 working tree 下并发 mutation,提交时互相吃对方改动」的情况。
仅靠文件白名单 + verify commit 顺序无法彻底解决——**物理隔离** 才是可靠方案。

本设计在 repairer 流程中插入 git worktree 隔离层:

- 每个 subagent 在 **独立 worktree**(独立目录 + 独立分支)编码 + commit
- 主 agent 在所有 subagent 完成后,按 **完成时间序** 逐个 merge 回 base 分支
- merge 冲突时尝试 **自动 rebase**,失败则 **停下问用户**
- 全部 merge 成功后,批量清理 worktree + 临时分支

## 2. Boundary

**In scope**

- 修改 repairer SKILL.md,新增 §3.5 / §4.5 / §5.5 三个节点
- 修改 subagent prompt 模板(工作目录 + 完成标准)
- 新增 baseline 假设 11
- 新增 eval 6

**Out of scope**

- 改变 description 字段的触发短语(worktree 是实现细节,不影响触发条件)
- 改变现有 §1 §2 §6 §7 的内容
- 改变现有 5 条注意事项(commit 规则 / 单 bug 不触发 / vault 副本处理等)
- 改变 issue 文档回写流程——只是把「subagent 自己回写」改成「主 agent 统一回写」,目标位置和格式不变

## 3. Triggering Conditions (description field)

无变化。worktree 隔离是 skill 内部的实现细节,不属于触发条件。

## 4. 流程变化(7 步 → 10 步)

### Before(v1 现有)

```
1. 定位 issue 源文件
2. 读 issue,拆问题
3. 设计 subagent 切分
4. 并行 dispatch              ← subagent 共享 working tree
5. 收尾验证
6. 回写源文件
7. 汇总回报
```

### After(v2 新流程)

```
1. 定位 issue 源文件
2. 读 issue,拆问题
3. 设计 subagent 切分(含文件互斥清单 + PROTECTED_FILES)
3.5 准备 worktree           ← 新增:主 agent 为每个 issue 建独立 worktree
4. 并行 dispatch             ← subagent 在各自 worktree 里编码 + commit
4.5 等待 + 顺序 merge       ← 新增:按完成时间序 merge,冲突停下问用户
5. 收尾验证
5.5 清理 worktree           ← 新增:批量 `worktree remove` + 删除临时分支
6. 回写源文件
7. 汇总回报
```

新增 3 个节点(3.5 / 4.5 / 5.5),其余步骤顺序与语义不变。

## 5. 关键规则

### 5.1 worktree 命名与位置

- 路径模板:`<REPO_PARENT>/<REPO_NAME>-fix-<ISSUE_ID>/`
- 示例:仓库根 `E:/Work/iWork/myrepo/`,issue `P0-性能-图标` → worktree 路径
  `E:/Work/iWork/myrepo-fix-P0-性能-图标/`
- 每个 worktree 检出独立分支:`<BASE_BRANCH>-fix-<ISSUE_ID>`
  (例:`main-fix-P0-性能-图标`)
- 主 agent **必须在 dispatch subagent 之前** 完成全部 worktree 创建,避免 subagent
  抢跑。

### 5.2 subagent cwd 约束

subagent prompt 的「工作目录」字段从 `<REPO_ROOT>` 改为 `<WORKTREE_PATH>`,
并显式追加 **「不要 cd 回主仓库」** 一条约束。

### 5.3 merge 顺序:完成时间序

主 agent 监听所有 subagent 完成通知(background run 的通知包含 `total_tokens`
和 `duration_ms`),按到达顺序逐个 merge。无预先排序。

merge 命令模板:

```
cd <REPO_ROOT>
git -C <REPO_ROOT> merge --no-ff <BRANCH_NAME>
```

`--no-ff` 强制产生 merge commit,保留分支历史,便于回滚单个 fix。

### 5.4 冲突处理:自动 rebase + fallback 问用户

merge 报错(冲突)时:

1. 主 agent 在该 worktree 里执行 `git -C <WORKTREE_PATH> rebase <BASE_BRANCH>`
2. rebase 成功 → 回到主仓库再 merge 一次
3. rebase 失败(仍有冲突)→ **停下**,用 AskUserQuestion 问用户:
   - 丢弃该 fix(删除 worktree + 分支,issue 标「未合并」)
   - 保留分支暂不合并(保留 worktree 让用户手动处理)
   - 人工介入(暂停流程,等用户指示)

### 5.5 cleanup 时机

**所有 merge 完成后** 才统一清理(不能在 merge 中途清,否则冲突回滚时找不到 worktree)。
命令模板:

```
git worktree remove --force <WORKTREE_PATH>
git branch -D <BRANCH_NAME>
```

清理后必须验证:

- `git worktree list` 只剩主仓库
- `git branch` 不再含 `-fix-` 前缀的临时分支
- 主仓库 `git status` 干净

### 5.6 subagent prompt 模板 diff

**Before**(节选):

```markdown
工作目录:`<REPO_ROOT>`
不要修改与本任务无关的文件、不要触碰其他 <N-1> 个任务的代码。
...
5. 用 git commit ...
   - **禁止 push**

## 完成标准
- <SPECIFIC_OUTCOME>
- build 通过
- 已 commit
- 在 Obsidian issue 文档中对应「<ISSUE_ID>」一节下追加四级标题「解决方案」(用 obsidian CLI
  append),并在 issue 列表里勾选 `[x]`。
```

**After**:

```markdown
工作目录:`<WORKTREE_PATH>`(已为你创建好的独立 git worktree,**不要 cd 回主仓库**)
不要修改与本任务无关的文件、不要触碰其他 <N-1> 个任务的代码、**不要触碰其他 worktree 目录**。
...
5. 用 git commit ...
   - **禁止 push**
   - **不要尝试 merge 回主仓库**——这一步由主 agent 统一做

## 完成标准
- <SPECIFIC_OUTCOME>
- build 通过
- 已 commit(commit 会留在 worktree 自己的分支上,**不要 push**)
- **不要** 操作 Obsidian issue 文档(回写统一由主 agent 收尾,避免 worktree 路径错位)
- 把 commit hash + 修改文件清单 + build 结果回报给我
```

## 6. Baseline 假设 11(新增)

> 无 skill 时,AI 派 N 个 subagent 并行编码,共享 working tree。
> subagent A 还在改文件 X,subagent B 已经 commit 了文件 X,
> Git recalc 把 A 的未保存改动覆盖,或把 A 的中间态错误地 include 进 B 的 commit。
>
> **为什么错**:物理隔离才能真正解决并发 mutation 冲突;「文件白名单 + verify commit 顺序」
> 只是缓解,无法应对 5+ 个并发 subagent 同时修改相互独立模块的边界文件。
>
> **skill 对应规则**:§3.5 准备 worktree + §4 subagent cwd 指向 worktree + §5.5 cleanup。

baseline.md 的 GREEN phase 表格新增一行:

| skill 规则 | 防的 baseline 错 |
|---|---|
| §3.5 + §4.5 + §5.5 worktree 全流程 | Baseline 假设 11 |

## 7. Eval 6(新增)

`evals/evals.json` 新增:

```json
{
  "id": 6,
  "eval_name": "worktree-isolation-must-be-enforced",
  "prompt": "用户给了一个 issue 文档,里面有 5 个互不依赖的问题,分别动 5 个不同的文件。\n\n用户说:「请按 repairer 修这 5 个问题」\n\n请按 repairer skill 把这 5 个问题修完。",
  "expected_output": "主 agent 在 dispatch 之前为每个 issue 建独立 worktree;5 个 subagent 在各自 worktree 编码 + commit;主 agent 按完成时间序 merge 全部 5 个分支到 base 分支;merge 全部完成后批量清理 worktree + 临时分支;主仓库最终干净且有 5 个新 commit。",
  "files": [],
  "expectations": [
    "主 agent 在 dispatch subagent 之前为每个 issue 创建了独立 worktree",
    "每个 subagent 的 cwd 是其 worktree 路径(不是仓库根)",
    "5 个 commit 分别落在 5 个独立的 fix 分支上(不是直接 commit 在 base 分支)",
    "主 agent 在所有 subagent 完成后按完成时间序逐个 merge 到 base 分支",
    "merge 全部完成后,`git worktree list` 只剩主仓库、5 个临时 worktree 已被 `remove --force`",
    "merge 全部完成后,5 个 fix-* 临时分支已被 `git branch -D` 删除",
    "merge 全部完成后,主仓库 `git status` 干净",
    "merge 全部完成后,主仓库 `git log --oneline -5` 显示 5 个新 commit 顺序与 subagent 完成时间序一致",
    "全程没有任何 push 动作"
  ]
}
```

## 8. Error handling & edge cases

- **worktree 已存在**:同名 worktree 路径冲突时,主 agent 应报错并要求用户清理,不应自动删除既有 worktree(可能含用户未保存工作)。
- **merge 冲突时主仓库 HEAD 处于中间态**:第 2 个 merge 一定基于第 1 个 merge 成功后的 HEAD;
  若第 1 个 merge 失败被用户选择丢弃,主仓库必须先 `git merge --abort` 回干净状态再继续。
- **subagent 在 worktree 里 `git push`**:现有 §「禁止 push」规则仍然适用,worktree 不改变 push 权限。
- **subagent 在 worktree 里 `cd ..` 试图访问主仓库**:subagent prompt 显式禁止;
  但若 subagent 违规,主 agent 在 §5 收尾时 `git status` 检查可以发现异常。
- **worktree 磁盘不足**:主 agent 创建 worktree 前可选项 `df` 检查;若失败,停下问用户。

## 9. Testing strategy

- eval 6 是核心功能性测试(worktree 全流程)
- 现有 eval 1-5 不变,但需要在 v2 skill 下重新跑一遍(因为 subagent 流程变了):
  - eval 1(parallel dispatch):worktree 不影响并行性,但 subagent cwd 必须是 worktree
  - eval 2(vault 副本):§6 回写不变,不受影响
  - eval 3(单 bug 不触发):不受影响
  - eval 4(强依赖):worktree 不能解决强依赖,该 eval 应在 v2 下仍然正确拒绝并行
  - eval 5(commit 规则):worktree 下 commit 同样要走 git-commit-helper + 禁 push
- 重新跑完后,baseline.md 的 GREEN 表格应更新为包含假设 11 的全量映射。

## 10. Open questions

无。用户在 brainstorm 阶段已逐项确认:

- 方案:A+(自动 rebase 带 fallback 问用户)
- merge 顺序:完成时间序
- 冲突处理:停下问用户(rebase 失败时)
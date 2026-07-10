---
name: list-git-repos
description: Use when scanning a directory tree for git repositories — runs a pruned ASCII tree where each repo node shows current branch and `*` dirty marker; pure stdlib Python 3. Use cases: workspace inventory, /init onboarding a new workspace, preflight before cross-repo work, finding "where are my repos" before batch ops. Default output is a tree; pass --format paths for one absolute path per line (pipeline-friendly, forward slashes even on Windows). Triggered when the user says "扫一下这个目录里的 git 仓库 / 列出我的工作区 / 盘点 workspace / 父目录里有哪些 repo / /init 这个新工作区 / 审计跨 repo 的工作 / 哪些 repo 是 dirty 的", or asks "what git repos are here / 列举 / 列出 / 盘点 / 审计 / 对所有 repo 跑一遍".
---

# list-git-repos

Scan a directory tree and print all git repositories as a pruned ASCII tree,
with current branch and a `*` dirty marker per repo. Pure stdlib Python 3
script; the script is the single source of truth so agents under pressure do
not drift.

## When to Use

- "列举 / 列出 X 目录下所有 git 仓库"
- "扫一下 / 盘点 / 审计 当前工作区"
- "/init 一个新工作区" or "接手一个新工作区, 看看里面有什么"
- "对所有 repo 跑一遍 ..." (a batch operation that needs an inventory first)
- "我工作区里有哪些 git repo / 哪些子目录是 git 仓库"

**Do NOT use this skill** for:

- A single known repo's `git status` / `git log` (run `git` directly).
- Listing git remotes or git history.
- "非 git 的项目" — this skill answers the *git* half of "what's in here".
- Creating / cloning / initializing repos.
- Network mounts or multi-host scans.

## Output Format

The tree header is `---<basename>` — the scan root's directory name only (not the full path). When the scan root is itself a git repo, the header appends the repo's label inline (e.g. `---alpha(?)` or `---alpha(master*)`). When the scan root has no git repos in its subtree, the header is bare: `---<basename>`.

Below the header, surviving directories and repos are rendered as an ASCII tree:

```
---alpha
  |____beta(master*)
  |____gamma
       |____delta(main)
```

Rules:

- Root children use `  |____` (2-space indent + bar).
- Deeper children use `    |____` (4-space indent per level, accumulating bars).
- Repo node label: `<name>(<branch>*)`.
  - `<branch>` comes from `git status --porcelain --branch` first line, stripped of `## `. Detached HEAD renders as `HEAD(<short-sha>)` (e.g. `HEAD(abc1234)`).
  - `*` is appended when the porcelain output has any line after the first (worktree is dirty — tracked changes, staged changes, OR untracked files).
  - When `--with-status` is **off**, the branch token is the literal `?` (not inspected).
  - When `--with-status` is **on** but the per-repo git command times out or errors, the label is `unknown`.
- Non-repo directory node: `<name>/` (trailing slash) when it has at least one git-repo descendant.
- **Pruning**: any subtree that contains zero git repos is omitted entirely.
- All paths use forward slashes (`/`), even on Windows.

The script also prints `scanned: <resolved-path>` to **stderr** so the user can see which directory was scanned, but stdout is unaffected and remains pipe-friendly.

## CLI Quick Reference

```
python scripts/list_git_repos.py [ROOT] [options]
```

| Flag               | Default          | Meaning                                                  |
|--------------------|------------------|----------------------------------------------------------|
| `ROOT` (positional)| cwd              | Scan root. Agent should confirm with the user.           |
| `--max-depth N`    | `3`              | Recursion depth, root = 0. `0` = root only.              |
| `--with-status`    | off              | Collect branch + dirty info per repo (one extra git call). |
| `--format {tree,paths}` | `tree`     | `tree` = ASCII tree; `paths` = one absolute path per line. |
| `--include-hidden` | off              | When off, skip dotfile directories.                      |

### Hard-coded Skip List

These directories are never descended into, never rendered:

`.git`, `node_modules`, `target`, `build`, `dist`, `out`, `__pycache__`, `.venv`, `venv`, `.idea`, `.vscode`.

## Calling the Script

```bash
# Tree of the current workspace, branch + dirty info
python list-git-repos/scripts/list_git_repos.py . --with-status

# Just paths, for piping into another tool
python list-git-repos/scripts/list_git_repos.py E:/Workspace --format paths

# Shallow scan, root only
python list-git-repos/scripts/list_git_repos.py . --max-depth 0
```

## Why Prefer the Script

The RED-phase baseline (see `docs/baseline.md`) showed agents can make
several specific errors under pressure:

- Treating `.git` *files* (worktree pointers) as a second repo
- Rendering non-git subtrees (no pruning)
- Reporting clean on untracked files (used `git diff --quiet`)
- Mixing `\` and `/` in output on Windows
- Calling `git status` for every repo even when `--with-status` is off

The script encodes every rule from the spec. Don't bypass it.

## Red Flags — STOP and Ask the User

- User asks for output that includes non-git projects → out of scope; this skill only lists git repos.
- User wants a `--json` or `--porcelain` output → deferred per spec §11; tell the user.
- `python` is not available on the user's PATH → tell the user, do not hand-roll a bash replacement.
- The user wants to scan a network mount or remote filesystem → out of scope; refuse and explain.
- The output looks wrong but the user wants to fix it by editing the script → confirm the change is intentional and update `SKIP_DIRS` in both the script and this file in one commit.

## Rationalization Table

| Excuse                                                | Reality                                                                                  |
|-------------------------------------------------------|------------------------------------------------------------------------------------------|
| "I can use `find` to find `.git` directories"         | Misses worktree `.git` files; misses pruning; misses depth limit. Use the script.        |
| "I'll just shell out to `git status` per directory"   | If `--with-status` is off, this is wasted work. The script gates git calls on the flag.  |
| "On Windows I'll use backslashes"                      | Output uses `/` everywhere. Forward slashes in code, not OS conventions.                 |
| "I'll skip pruning — it's just one extra line"        | Pruning is the whole point of the tree shape. Pruning is in `_subtree_has_repo`.         |
| "Let me just `cat` the `.git/HEAD` to get the branch"  | Detached HEAD parsing is non-trivial; the script uses `git status --porcelain --branch`. |

## Extending the Skip List

If a new directory genuinely needs to be skipped (e.g. `.terraform`):

1. Add the name to the `SKIP_DIRS` set in `scripts/list_git_repos.py`.
2. Add the name to the "Hard-coded Skip List" table above.
3. Re-run `pytest list-git-repos/tests/ -v` to confirm no regression.
4. Commit both changes in one commit with the `feat(feat/list-git-repos):` header.

**Never** add a skip-list entry ad-hoc inside a conversation without committing.

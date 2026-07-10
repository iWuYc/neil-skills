---
name: list-git-repos-design
description: Design for a Claude Code skill that scans a directory tree and prints all git repositories in an ASCII tree, with current branch and dirty marker. Trimmed (pruned) of branches that contain no git repo.
metadata:
  type: design
  date: 2026-07-02
---

# list-git-repos — Design Spec

## 1. Purpose

A user often has a workspace with many sibling projects (e.g. `E:/Workspace/iWork/...`). Before
running cross-repo work ("commit all of these", "which of my repos are dirty", "what's on each
branch"), the agent needs a one-shot inventory: *where are the git repos, what branch is each
on, and which ones have uncommitted changes?*

This skill produces that inventory as a pruned ASCII tree.

## 2. Boundary

**In scope**

- Recursive scan of a single root directory looking for git repositories.
- Per-repo: current branch + dirty marker.
- Pruning non-git subtrees from the output.
- Pure stdlib Python 3 script + a SKILL.md that documents when and how to use it.

**Out of scope**

- Listing git remotes, last commit, or anything beyond branch + dirty.
- Non-git projects (the skill explicitly answers the *git* half of "what's in here").
- Initializing / creating / cloning repositories.
- Network mounts, remote filesystems, multi-host scans.
- Mutating anything on disk.

## 3. Triggering Conditions (description field)

The skill's `description` (frontmatter) will include, verbatim or near-verbatim, these trigger
phrases. The literal token `/init` is included so that any user message containing `/init` of a
new workspace is matched by search and the skill is auto-loaded.

Trigger phrases (zh-CN, matching the existing `staged-doc-naming` style):

- "列举 / 列出 / 扫一下 X 目录下所有 git 仓库"
- "我工作区里有哪些 git repo / 哪些子目录是 git 仓库"
- "盘点 / 审计 当前工作区"
- "/init 一个新工作区" / "接手一个新工作区, 看看里面有什么"
- "对所有 repo 跑一遍 ..." (a batch operation that needs an inventory first)

**Not triggered** for:

- A single known repo's `git status` / `git log` (agent can run `git` directly).
- Listing git remotes or git history.
- "非 git 的项目" — that question is not what this skill answers.
- Creating / cloning / initializing repos.

## 4. Output Format

ASCII tree, root labeled with `---`, branches drawn with the `tree(1)`-style vertical bars:

```
---<ROOT>
  |____<dir-or-repo>
  |    |____<repo>(<branch>[*])
  |____<repo>(<branch>)
```

Rendering rules:

- The root line is `---<ROOT>` (no leading indent, no leading bar).
- Children of the root use `  |____` (two-space indent + bar).
- Each subsequent level adds one more `    |____` (4 spaces per level).
- A **git repo** node is rendered as `<name>(<branch>[*])`:
  - `<name>` is the directory's basename.
  - `<branch>` is the output of `git status --porcelain --branch` first line, stripped of the
    `## ` prefix. Detached HEAD appears as `HEAD(<short-sha>)` (e.g. `HEAD(abc1234)`).
  - `*` is appended when the porcelain output has any line after the first (i.e. the worktree
    is dirty).
  - When `--with-status` is **off**, `<branch>` is the literal token `?` (single character)
    so the user can see at a glance which nodes are un-inspected.
  - When `--with-status` is **on** but the per-repo git command times out or errors, the
    label is the literal token `unknown`. A broken repo is still reported; only its branch
    info is missing.
- A **non-repo directory** node is rendered as `<name>/` (trailing slash) when it has at
  least one git-repo descendant.
- **Pruning**: any subtree that contains zero git repos is omitted entirely. Non-git
  directories that only contain other non-git directories do not appear at all.
- All paths use forward slashes (`/`), even on Windows. The script converts `os.path.relpath`
  output to forward slashes for consistency.
- Output goes to **stdout**. The caller decides whether to redirect to a file.
- When `--with-status` is off, repo nodes render the literal `?` as the branch token; this
  visually distinguishes "not inspected" from "inspected but failed" (which uses
  `unknown`).

## 5. CLI Interface

```
python scripts/list_git_repos.py [ROOT] [options]
```

| Arg / Flag        | Default          | Meaning                                                              |
|-------------------|------------------|----------------------------------------------------------------------|
| `ROOT` (positional)| cwd              | Scan root. Agent should confirm with the user before running.        |
| `--max-depth N`   | `3`              | Recursion depth, root = 0. `0` = inspect root only.                  |
| `--with-status`   | off              | Collect branch + dirty info per repo (one extra `git status` call).  |
| `--format {tree,paths}` | `tree`      | `tree` = ASCII tree; `paths` = one absolute path per line.           |
| `--include-hidden`| off              | When off, skip dotfile directories (e.g. `.config`, `.local`).       |
| `--help`          | —                | argparse auto-generated.                                             |

### Hard-coded skip list (not overridable by CLI)

These directories are never descended into, never rendered:

- `.git` — git internals (handles the case of a git repo living *inside* another git repo's
  working tree; its `.git` is a file pointer, not a real repo)
- `node_modules`
- `target` (Rust / Java build output)
- `build`, `dist`, `out` (common build output)
- `__pycache__`
- `.venv`, `venv`
- `.idea`, `.vscode` (IDE config)

Rationale: the user can still ask to scan e.g. a `node_modules` parent with `--include-hidden`
plus an explicit override flag, but by default these are noise.

## 6. Algorithm

### Phase 1 — Build the raw tree

```
scan(dir, depth, max_depth):
    node = { path, is_git_repo: False, children: [] }
    if depth > max_depth: return node
    for entry in os.scandir(dir):
        if not entry.is_dir(follow_symlinks=False): continue
        name = entry.name
        if name in SKIP_LIST: continue
        if not include_hidden and name.startswith('.'): continue
        child = scan(entry.path, depth + 1, max_depth)
        node.children.append(child)
    node.is_git_repo = ('.git' in immediate children of `dir`
                        — both as directory and as file, to handle git worktrees)
    return node
```

`is_git_repo` is decided by the **presence of a `.git` entry** in the directory's own
immediate children, regardless of how deep the recursion has gone. This is the only
authoritative test.

### Phase 2 — Prune and render

```
render(node, prefix, has_any_repo_descendant):
    if not has_any_repo_descendant: return  # prune
    print(prefix + '|____' + label(node))
    for child in node.children:
        render(child, prefix + '    ', subtree_has_repo(child))
```

`subtree_has_repo(n)` is a memoized post-order helper that returns True iff `n` itself is
a repo OR any descendant is. This decides pruning in O(N).

### `--with-status` collection

Run **after** pruning, only on the kept repo nodes:

```
subprocess.run(
    ['git', 'status', '--porcelain', '--branch'],
    cwd=repo_path, capture_output=True, text=True, timeout=5,
)
```

Parse:

- First line: `## <branch>` → `<branch>`; or `## HEAD (detached at <sha>)` → `HEAD(<short>)`.
- Any other line → dirty → append `*`.

On `TimeoutExpired` / `CalledProcessError` / empty stdout → label as `unknown` and continue.
**A single broken repo must not stop the scan.**

## 7. Interaction with `--with-status` and Pruning

Pruning is decided **purely by phase 1's `is_git_repo` flag**. The git status command is only
invoked for kept repo nodes in phase 2. This means:

- Status failures cannot cause a repo to be pruned.
- A repo with a corrupted `.git` directory is still reported (so the user can investigate).
- The default scan (no `--with-status`) is fast and has zero git-process overhead.

## 8. Skill File Layout

```
list-git-repos/
  SKILL.md
  scripts/
    list_git_repos.py
  docs/
    baseline.md
```

`SKILL.md` chapters (mirroring `staged-doc-naming`):

1. Overview
2. When to Use (triggers + non-triggers, zh-CN)
3. Output Format (ASCII tree spec + dirty marker rules)
4. CLI Quick Reference (table from section 5)
5. Calling the Script (3 minimal examples)
6. Red Flags — STOP and Ask the User
7. Rationalization Table (built from baseline failures)
8. Common Mistakes / Extending the Skip List

`docs/baseline.md`: the RED-phase record. Five pressure scenarios run with the skill absent,
with the exact rationalizations the subagent produced. This anchors the GREEN phase.

## 9. Test Plan (TDD for Skills)

Per `superpowers:writing-skills`:

### RED — baseline (no skill present)

Five pressure scenarios, run via the Agent tool with no `list-git-repos` skill installed.
Record verbatim behavior. Each one targets a known drift:

1. **`.git` internal mistake**: a workspace where `outer/.git` is a real repo and
   `outer/sub/.git` is a worktree link file. Agent should report `outer` as one repo, not
   two.
2. **No pruning**: a workspace with a `node_modules`-less empty directory nested deep. Agent
   renders the empty branch.
3. **Wrong dirty check**: agent uses `git diff --quiet` (which ignores untracked files) and
   reports a dirty repo with new untracked files as clean.
4. **Path separator drift**: Windows path output mixes `\` and `/`.
5. **Status when not requested**: `--with-status` is off, but agent still shells out to git
   per directory and slows down the scan 10x.

### GREEN — write `list_git_repos.py`

Encodes every rule from sections 4–6. Re-run the same 5 scenarios. Agent now uses the
script and gets correct output.

### REFACTOR — bulletproof

- Add violation-symptom keywords to `description` (e.g. "non-git subtrees", "dirty
  marker", "branch label").
- Add the **Rationalization Table** to `SKILL.md` (excuse → reality), one row per observed
  drift.
- Add the **Red Flags** list (stop signs that mean "you are about to drift; rerun the
  script").

## 10. Commit Plan

Single commit using the `git-commit-helper` skill:

- Author: `吴宇春 (Ai) <wuyuchun@rainbowcn.com>` (per repo's local identity, see
  `git-identity-local-vs-global` memory).
- Subject: `feat(skills): add list-git-repos skill with tree-pruned git repo inventory`
- Body: bullet list of what was added (zh-CN, per skill convention).
- **No push** — global rule.

Files in the commit:

- `list-git-repos/SKILL.md` (new)
- `list-git-repos/scripts/list_git_repos.py` (new)
- `list-git-repos/docs/baseline.md` (new)
- `README.md` (edit: add the new skill to the Skills list, mirroring the existing entries)

## 11. Open Questions / Future Work

- A `--json` output format is deferred. If the user starts piping the output into another
  agent or tool, add it.
- A `--porcelain` mode for machine consumption (TSV) is deferred.
- A `--follow-symlinks` flag is deferred; default is to NOT follow (safer).
- The skip list is hard-coded; if the user wants to extend it, follow the staged-doc-naming
  pattern (table in SKILL.md + `SKIP_LIST` in the script, committed together).

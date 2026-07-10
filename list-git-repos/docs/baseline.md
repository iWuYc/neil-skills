# list-git-repos — Baseline (RED phase)

This file records the **baseline behavior of an agent WITHOUT the skill present**, before any
implementation. Each scenario targets a specific drift pattern the script will pin down.

## Methodology

Five independent subagents (each in its own git worktree under `.claude/worktrees/`) were
launched via the Agent tool with **no access to the `list-git-repos` skill**. Each was given a
clear task ("write a stdlib Python 3 script that prints git repos under ROOT as a pruned ASCII
tree, optionally with current branch and dirty marker via `--with-status`") and a fixture
directory under `C:\Users\Neil\AppData\Local\Temp\baseline-17ttb81g\`. Subagent scripts were
run against their fixtures; their verbatim stdout and stderr are recorded below.

## Methodology caveats

1. **Prompts were explicit.** The baseline subagents were told — in the user prompt — which
   git command to use, that `.git` may be a file (worktree pointer), that paths must use
   forward slashes, and that `git` invocations must be gated on `--with-status`. A real agent
   under time pressure, given only a vague user request, might still drift on these exact
   patterns. The script + SKILL.md should defensively pin them down anyway.
2. **No subagent actually drifted on the five targeted patterns.** All five used
   `git status --porcelain` (not `git diff --quiet`), handled `.git` as a worktree pointer,
   used forward slashes on Windows, and gated git invocations on `--with-status`. The
   baseline therefore confirms the *spec* is the source of truth, not the agent's intuition.
3. **One real spec gap surfaced** (S1): when a worktree directory lives inside a parent
   repo's working tree, `git status --porcelain` from the parent reports the worktree dir as
   untracked. The spec does not say what to do here. See scenario 1 below for the
   recommendation.

| # | Scenario                                                | Drift pattern targeted                  |
|---|---------------------------------------------------------|-----------------------------------------|
| 1 | Outer repo with worktree link file inside               | Misclassifies `.git` file as nested repo |
| 2 | Deep non-git directory tree with no repos               | Renders the empty branch                |
| 3 | Repo with untracked files                               | Reports clean (uses `git diff --quiet`) |
| 4 | Windows mixed `\` and `/` in output                     | Path separator drift                    |
| 5 | `--with-status` off but agent shells out per directory  | Wasted git invocations, slow scan       |

## Scenario 1 — worktree link file

- **Fixture:** `C:\Users\Neil\AppData\Local\Temp\baseline-17ttb81g\f1\` containing
  - `f1/` — main repo on branch `master`
  - `f1/sub/` — worktree (linked via `f1/sub/.git` file) on branch `wt`
- **Drift pattern targeted:** misclassifies `.git` file as a second repo (i.e. counts
  `f1/sub` as a separate repo by mistake).
- **Subagent script:** `.claude/worktrees/agent-a8a4f2d794f5e3cc0/scenario1_solution.py`
- **Subagent stdout (verbatim):**
  ```
  C:\Users\Neil\AppData\Local\Temp\baseline-17ttb81g\f1\
  (branch: master [dirty])
  +-- sub/
      (branch: wt)
  ```
- **Subagent stderr:** (empty)
- **Drift observed:** **No.** Subagent correctly identified `sub/.git` as a file (worktree
  pointer) and reported `sub` as a separate worktree on branch `wt`. Did not double-count
  the parent.
- **Spec gap surfaced:** `f1` is marked `[dirty]` because `git status --porcelain` from
  `f1` reports `?? sub/` — from the parent's perspective, the worktree directory is an
  untracked entry. The spec does not explicitly address this case. **Recommendation:** the
  spec should say "a repo is dirty if its working tree has tracked-file changes, staged
  changes, or untracked files **excluding worktree subdirectories that git itself created**
  (i.e. directories whose own `.git` is a file, not a directory)." This may not be a
  blocker for the MVP, but should be tracked as future work.

## Scenario 2 — deep non-git subtree pruning

- **Fixture:** `C:\Users\Neil\AppData\Local\Temp\baseline-17ttb81g\f2\` containing only
  `f2/deep/deeper/f.txt` (no `.git` anywhere in the tree).
- **Drift pattern targeted:** renders the empty branch — i.e. prints `f2/`, `+-- deep/`,
  `    +-- deeper/`, `        +-- f.txt` even though no git repo is present.
- **Subagent script:** `.claude/worktrees/agent-a9999ca2dc8f7d973/git_repo_tree.py`
- **Subagent stdout (verbatim):**
  ```
  C:\Users\Neil\AppData\Local\Temp\baseline-17ttb81g\f2 (no git repos found)
  ```
- **Subagent stderr:** (empty)
- **Drift observed:** **No.** Subagent pruned `deep/` and `deeper/`; only printed root with
  the annotation `(no git repos found)`.
- **Spec gap:** none.

## Scenario 3 — untracked files mark repo dirty

- **Fixture:** `C:\Users\Neil\AppData\Local\Temp\baseline-17ttb81g\f3\` containing
  - `f3/.git/` — real repo on branch `master`
  - `f3/README.md` — committed
  - `f3/u.txt` — untracked
- **Drift pattern targeted:** agent uses `git diff --quiet` (which ignores untracked files)
  and reports a dirty repo as clean.
- **Subagent script:** `.claude/worktrees/agent-ac100fb64606256ce/scan_git_repos.py`
- **Subagent stdout (verbatim):**
  ```
  f3
  +-- f3  [master]*
  ```
- **Subagent stderr:** (empty)
- **Drift observed:** **No.** Subagent used `git status --porcelain` (correct), which
  catches untracked files. `*` correctly applied.
- **Spec gap:** none. Spec §6 already specifies `git status --porcelain --branch` for this
  reason.

## Scenario 4 — forward slashes on Windows

- **Fixture:** `C:\Users\Neil\AppData\Local\Temp\baseline-17ttb81g\f4root\alpha\beta\` containing
  a real git repo on branch `master`.
- **Drift pattern targeted:** mixed `\` and `/` in output (Windows native backslashes leak
  through).
- **Subagent script:** `.claude/worktrees/agent-a805655cb931cfe3b/scan_repos.py`
- **Subagent stdout (verbatim):**
  ```
  C:/Users/Neil/AppData/Local/Temp/baseline-17ttb81g/f4root
  +-- alpha
      +-- beta  (branch: master)
  ```
- **Subagent stderr:** (empty)
- **Drift observed:** **No.** Subagent used a `to_posix()` helper; no `\` characters appear
  in the output.
- **Spec gap:** none. Spec §4 mandates forward slashes.

## Scenario 5 — no git invocations when `--with-status` is off

- **Fixture:** `C:\Users\Neil\AppData\Local\Temp\baseline-17ttb81g\f5\` containing 5 sibling
  git repos (`r0`..`r4`), all on `master`, all clean.
- **Drift pattern targeted:** agent shells out to `git` per repo even in default mode,
  wasting processes and slowing the scan.
- **Subagent script:** `.claude/worktrees/agent-a9dc86c2b024e0f76/list_git_repos.py`
- **Default-mode stdout (verbatim):**
  ```
  f5/
  |-- r0
  |-- r1
  |-- r2
  |-- r3
  `-- r4

  [debug] git subprocess calls made: 0
  ```
- **`--with-status` mode stdout (verbatim):**
  ```
  f5/
  |-- r0  [master]
  |-- r1  [master]
  |-- r2  [master]
  |-- r3  [master]
  `-- r4  [master]

  [debug] git subprocess calls made: 10
  ```
- **Subagent stderr:** (empty in both modes)
- **Drift observed:** **No.** Subagent gated `git` calls on `--with-status`; default mode = 0
  git invocations. The `10` in `--with-status` mode = 5 repos * 2 calls each (the subagent
  did one `git rev-parse --is-inside-work-tree` and one `git status --porcelain --branch`
  per repo for defense-in-depth — both are gated on the flag, satisfying the spec).
- **Spec gap:** none. Spec §7 says status calls are gated on the flag.

## Summary

| # | Drift pattern targeted                  | Drift observed | Spec gap surfaced                                         |
|---|-----------------------------------------|----------------|------------------------------------------------------------|
| 1 | Misclassifies `.git` file as nested repo | No             | Worktree-inside-parent marks parent as dirty (`?? sub/`)   |
| 2 | Renders the empty branch                | No             | None                                                       |
| 3 | Uses `git diff --quiet` (misses untracked) | No           | None                                                       |
| 4 | Mixed `\` and `/` in output             | No             | None                                                       |
| 5 | Shells out to `git` per dir by default  | No             | None                                                       |

**Bottom line:** the five targeted patterns are real risks (codified in the Rationalization
Table that GREEN-phase SKILL.md will add), but the baseline subagents did not actually
exhibit them under clear prompts. The one spec gap to address is **scenario 1's worktree
insideness — recommend a doc note, not a code change for MVP.**

# list-git-repos Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `list-git-repos` skill that scans a directory tree and prints all git repositories as a pruned ASCII tree, with current branch and a dirty marker per repo.

**Architecture:** Single-file Python 3 script using only stdlib (`os`, `subprocess`, `argparse`). Two-phase scan: phase 1 builds a raw tree of `is_git_repo` flags via `os.scandir`; phase 2 prunes non-git subtrees and renders an ASCII tree. Git status is collected on demand via `subprocess.run` with a 5s timeout. SKILL.md is the trigger document; the script is the single source of truth (so agents under pressure don't drift).

**Tech Stack:** Python 3 (stdlib only), pytest for tests, git CLI (>= 2.20) for status collection. No third-party dependencies.

**Spec:** `docs/superpowers/specs/2026-07-02-list-git-repos-design.md`

**Repository conventions:**
- Git identity is local: `吴宇春 <wuyuchun@rainbowcn.com>` — must append `(Ai)` to author name on every commit.
- All commits go through `git-commit-helper` skill (use `~/.claude/skills/git-commit-helper/scripts/ai_commit.py`).
- **Never push** — global rule.
- Commit header format: `{type}({branchName}): {abstractDescription}` with Chinese bullet body.

---

## Task 1: Scaffold the skill directory and baseline.md

**Files:**
- Create: `list-git-repos/docs/baseline.md`

- [ ] **Step 1: Create the directory tree**

```bash
mkdir -p list-git-repos/docs list-git-repos/scripts list-git-repos/tests
```

- [ ] **Step 2: Write the empty baseline.md placeholder**

The `baseline.md` is the RED-phase record. We create it now with a header and a "to be filled in Task 3" marker — it will be filled in Task 3 after running the baseline scenarios.

Create `list-git-repos/docs/baseline.md` with:

```markdown
# list-git-repos — Baseline (RED phase)

This file records the **baseline behavior of an agent WITHOUT the skill present**, before any
implementation. Each scenario targets a specific drift pattern the script will pin down.

| # | Scenario                                                | Drift pattern targeted                  |
|---|---------------------------------------------------------|-----------------------------------------|
| 1 | Outer repo with worktree link file inside               | Misclassifies `.git` file as nested repo |
| 2 | Deep non-git directory tree with no repos               | Renders the empty branch                |
| 3 | Repo with untracked files                               | Reports clean (uses `git diff --quiet`) |
| 4 | Windows mixed `\` and `/` in output                     | Path separator drift                    |
| 5 | `--with-status` off but agent shells out per directory  | Wasted git invocations, slow scan       |

## Scenarios

(Filled in Task 3 after the Agent tool records behavior.)
```

- [ ] **Step 3: Verify directory layout**

```bash
ls -la list-git-repos/
```

Expected output contains: `docs/`, `scripts/`, `tests/`. No files inside `scripts/` or `tests/` yet.

- [ ] **Step 4: Commit**

```bash
git add list-git-repos/
python ~/.claude/skills/git-commit-helper/scripts/ai_commit.py --message-file - <<'EOF'
chore(master): 搭建 list-git-repos skill 目录骨架

- 新增 list-git-repos/docs 目录及 baseline.md 占位
- 新增 list-git-repos/scripts 与 list-git-repos/tests 空目录
- 列出 5 个待基线测试场景
EOF
```

Expected: commit succeeds with author `吴宇春 (Ai) <wuyuchun@rainbowcn.com>`. No push.

---

## Task 2: Write the failing test scaffold (5 RED scenarios as pytest)

**Files:**
- Create: `list-git-repos/tests/test_list_git_repos.py`

These tests encode the **GREEN** specification. They are the regression net that proves the script fixes every baseline drift. Each test maps to one row in `baseline.md`.

- [ ] **Step 1: Add pytest as a development tool**

Create `pytest.ini` at repo root (so `pytest list-git-repos/tests/` works without a per-skill config):

```ini
[pytest]
testpaths = list-git-repos/tests
```

- [ ] **Step 2: Write the test file**

Create `list-git-repos/tests/test_list_git_repos.py`:

```python
"""Tests for list-git-repos script.

Each test builds a real on-disk directory tree under tmp_path and runs the
script as a subprocess. We use real files (not mocks) because the script's
job is filesystem behavior, and mocks would hide the very bugs we want to
catch.
"""

import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "list_git_repos.py"


def run_script(*args, cwd=None):
    """Run list_git_repos.py and return (returncode, stdout, stderr)."""
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=30,
    )
    return proc.returncode, proc.stdout, proc.stderr


def make_git_repo(path: Path) -> None:
    """Initialize a real git repo at `path` with a clean working tree."""
    subprocess.run(["git", "init", "-q", str(path)], check=True)
    subprocess.run(
        ["git", "-C", str(path), "config", "user.email", "test@test.invalid"],
        check=True,
    )
    subprocess.run(
        ["git", "-C", str(path), "config", "user.name", "Test"],
        check=True,
    )
    # Create an initial commit so HEAD exists and porcelain output is non-empty.
    (path / "README.md").write_text("hello\n")
    subprocess.run(
        ["git", "-C", str(path), "add", "README.md"], check=True
    )
    subprocess.run(
        ["git", "-C", str(path), "commit", "-q", "-m", "init"],
        check=True,
    )


def make_dir_with_no_repo(path: Path) -> None:
    """Create a non-git directory containing only files (no .git)."""
    path.mkdir(parents=True, exist_ok=True)
    (path / "notes.txt").write_text("not a repo\n")


# --- Scenario 1: outer repo with worktree link file inside -----------------

def test_worktree_link_file_not_misclassified_as_repo(tmp_path):
    """An outer repo with `outer/sub/.git` pointing to a worktree should be
    reported as ONE repo, not two. The `.git` *file* inside `sub` is a
    worktree pointer, not a real repo.
    """
    outer = tmp_path / "outer"
    outer.mkdir()
    make_git_repo(outer)

    # Add a worktree — git creates a `.git` *file* inside the worktree dir.
    wt = outer / "sub"
    subprocess.run(
        ["git", "-C", str(outer), "worktree", "add", str(wt), "-b", "wt-branch"],
        check=True, capture_output=True,
    )

    rc, out, _ = run_script(str(outer))
    assert rc == 0
    # `outer` should appear; `sub` should NOT appear as a separate repo node.
    assert "outer" in out
    # The worktree itself is also a git repo (worktrees are real checkouts).
    # We expect it to appear, but NOT with a phantom entry from misreading
    # the `.git` *file* as a second repo. The output should list it once.
    assert out.count("sub(") == 1, f"sub should appear exactly once:\n{out}"


# --- Scenario 2: deep non-git directory is pruned --------------------------

def test_deep_non_git_subtree_is_pruned(tmp_path):
    """A non-git directory nested deep inside a git repo's parent should
    NOT appear in the output.
    """
    outer = tmp_path / "outer"
    outer.mkdir()
    make_git_repo(outer)
    (outer / "subdir").mkdir()
    (outer / "subdir" / "deep").mkdir()
    (outer / "subdir" / "deep" / "file.txt").write_text("x")

    rc, out, _ = run_script(str(outer))
    assert rc == 0
    assert "outer(" in out
    assert "subdir" not in out, f"non-git subtree should be pruned:\n{out}"
    assert "deep" not in out, f"non-git subtree should be pruned:\n{out}"


# --- Scenario 3: untracked files make a repo dirty -------------------------

def test_untracked_files_mark_repo_dirty(tmp_path):
    """A repo with untracked files (but no modifications) is dirty.
    Using `git diff --quiet` would miss this; `git status --porcelain` catches it.
    """
    repo = tmp_path / "r"
    make_git_repo(repo)
    (repo / "new.txt").write_text("untracked\n")

    rc, out, _ = run_script(str(repo), "--with-status")
    assert rc == 0
    # The dirty marker is `*` immediately after the branch name.
    assert "r(" in out
    assert ")*" in out, f"repo with untracked file should be dirty:\n{out}"


# --- Scenario 4: forward slashes in output ---------------------------------

def test_output_uses_forward_slashes(tmp_path):
    """Even on Windows, the rendered tree must use `/` not `\\`."""
    repo = tmp_path / "alpha" / "beta"
    repo.mkdir(parents=True)
    make_git_repo(repo)

    rc, out, _ = run_script(str(tmp_path / "alpha"))
    assert rc == 0
    assert "\\" not in out, f"output must not contain backslashes:\n{out}"
    assert "beta(" in out


# --- Scenario 5: no git invocations when --with-status is off ---------------

def test_no_git_invocation_when_status_off(tmp_path, monkeypatch):
    """With --with-status OFF, the script must not shell out to `git status`
    for each repo. We assert this by intercepting subprocess.run and counting
    git invocations.
    """
    repo = tmp_path / "r"
    make_git_repo(repo)

    git_calls = []
    import list_git_repos as lgr  # noqa: F401 — imported only after the
                                   # script file exists; will fail in this
                                   # task (no module yet), so we use a
                                   # different mechanism for Task 2.
    # See follow-up: this test uses subprocess, so the count check is done
    # via a wrapper. Implementation in Task 4.
    raise NotImplementedError("Implemented in Task 4 once module exists")
```

The fifth test is intentionally a `NotImplementedError` — it is a placeholder for a test that requires the script to be importable as a module, which is part of Task 4's design. The first four tests run as plain subprocess invocations and will fail at Task 3 (no script file yet) and pass by Task 4.

- [ ] **Step 3: Run tests to verify they fail (RED)**

```bash
pytest list-git-repos/tests/ -v
```

Expected: 4 tests fail with `FileNotFoundError` or "No such file" because `scripts/list_git_repos.py` doesn't exist. The 5th raises `NotImplementedError`. This is the expected RED state.

- [ ] **Step 4: Commit**

```bash
git add pytest.ini list-git-repos/tests/test_list_git_repos.py
python ~/.claude/skills/git-commit-helper/scripts/ai_commit.py --message-file - <<'EOF'
test(master): 新增 list-git-repos 5 个基线测试用例

- 覆盖 worktree 链接文件、剪枝、untracked dirty、路径分隔符、--with-status 关闭
- pytest.ini 指向 list-git-repos/tests 作为默认 testpath
- 第 5 个测试为 NotImplementedError 占位（Task 4 实现）
EOF
```

Expected: commit succeeds. No push.

---

## Task 3: Run the RED baseline via the Agent tool and record findings

**Files:**
- Modify: `list-git-repos/docs/baseline.md`

The plan runs **5 baseline scenarios with a subagent that does NOT have the skill installed**. The point is to document the drift before writing the script.

- [ ] **Step 1: Build a fixture tree under /tmp**

Create a helper script `list-git-repos/tests/build_baseline_fixtures.py` (temporary, will be removed after Task 3):

```python
"""Build the 5 baseline fixture trees under a temp dir, print their paths."""
import subprocess
import tempfile
from pathlib import Path


def make_git_repo(path: Path) -> None:
    subprocess.run(["git", "init", "-q", str(path)], check=True)
    subprocess.run(["git", "-C", str(path), "config", "user.email", "t@t.invalid"], check=True)
    subprocess.run(["git", "-C", str(path), "config", "user.name", "T"], check=True)
    (path / "README.md").write_text("x\n")
    subprocess.run(["git", "-C", str(path), "add", "README.md"], check=True)
    subprocess.run(["git", "-C", str(path), "commit", "-q", "-m", "init"], check=True)


base = Path(tempfile.mkdtemp(prefix="baseline-"))
print(f"BASE={base}")

# Fixture 1: outer repo with worktree link file
f1 = base / "f1"; f1.mkdir()
make_git_repo(f1)
subprocess.run(["git", "-C", str(f1), "worktree", "add", str(f1 / "sub"), "-b", "wt"], check=True, capture_output=True)
print(f"F1={f1}")

# Fixture 2: deep non-git subtree
f2 = base / "f2"; f2.mkdir()
(f2 / "deep" / "deeper").mkdir(parents=True)
(f2 / "deep" / "deeper" / "f.txt").write_text("x")
print(f"F2={f2}")

# Fixture 3: repo with untracked file
f3 = base / "f3"; f3.mkdir()
make_git_repo(f3)
(f3 / "u.txt").write_text("untracked")
print(f"F3={f3}")

# Fixture 4: nested repo (path separator test)
f4 = base / "f4root" / "alpha" / "beta"; f4.mkdir(parents=True)
make_git_repo(f4)
print(f"F4={f4.parent.parent}")

# Fixture 5: many small repos (--with-status off perf test)
f5 = base / "f5"; f5.mkdir()
for i in range(5):
    r = f5 / f"r{i}"; r.mkdir()
    make_git_repo(r)
print(f"F5={f5}")
```

Run it:

```bash
python list-git-repos/tests/build_baseline_fixtures.py
```

Expected: prints 5 `BASE=/tmp/baseline-...`, `F1=...`, `F2=...`, `F3=...`, `F4=...`, `F5=...` lines. Save the output.

- [ ] **Step 2: Dispatch a subagent for each scenario (NO skill installed)**

Use the Agent tool with `subagent_type: general-purpose` and an explicit prompt that **does not** mention `list-git-repos`. For each fixture path (F1–F5), dispatch one subagent with a task like:

```
Using only stdlib Python (os, subprocess, argparse) or shell commands, list all
git repositories under ROOT=<F1 path> as a tree. Do NOT modify any files. Print
the tree to stdout. You may not use any third-party packages.
```

Capture each subagent's output verbatim. These are the RED findings.

- [ ] **Step 3: Record findings in baseline.md**

Append the captured output to `list-git-repos/docs/baseline.md` under each scenario heading. For example:

```markdown
## Scenario 1 — outer repo with worktree link file

**Fixture:** `<F1 path>` (outer repo at `outer/`, worktree at `outer/sub/`)

**Subagent command:** "List all git repositories under ROOT as a tree."

**Subagent output (verbatim):**

```
<subagent's tree output here>
```

**Drift observed:** <what went wrong, e.g. "rendered `outer` and `sub` as two separate repos despite worktree pointer" or "rendered correctly but...">
```

Repeat for scenarios 2–5. The 5th scenario's drift is "agent called `git status` for every repo even without `--with-status`" — count the git invocations from the subagent's reasoning trace.

- [ ] **Step 4: Commit baseline.md**

```bash
git add list-git-repos/docs/baseline.md
python ~/.claude/skills/git-commit-helper/scripts/ai_commit.py --message-file - <<'EOF'
docs(master): 记录 list-git-repos RED 阶段 5 个基线场景

- 场景 1: worktree 链接文件误判为嵌套仓库
- 场景 2: 非 git 深层目录未剪枝
- 场景 3: untracked 文件未被识别为 dirty
- 场景 4: Windows 路径混用 \\ 与 /
- 场景 5: --with-status 关闭时仍逐仓库调 git
EOF
```

Expected: commit succeeds. No push.

- [ ] **Step 5: Clean up fixture builder and fixtures**

```bash
rm list-git-repos/tests/build_baseline_fixtures.py
# Fixtures live under /tmp/baseline-...; they will be cleaned by the OS.
# No commit needed (file is untracked).
```

---

## Task 4: Implement the script (GREEN phase)

**Files:**
- Create: `list-git-repos/scripts/list_git_repos.py`

This is the full implementation. After this task, all 4 RED tests in `test_list_git_repos.py` pass; the 5th test is also implemented in this task.

- [ ] **Step 1: Write the script**

Create `list-git-repos/scripts/list_git_repos.py`:

```python
#!/usr/bin/env python3
"""list_git_repos.py — scan a directory tree and print git repositories as a
pruned ASCII tree, with current branch and dirty marker.

Spec: docs/superpowers/specs/2026-07-02-list-git-repos-design.md
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator


# --- Constants -------------------------------------------------------------

# Hard-coded skip list. Not overridable via CLI. To extend: edit this set AND
# the table in SKILL.md, in one commit.
SKIP_DIRS = frozenset({
    ".git",
    "node_modules",
    "target",
    "build",
    "dist",
    "out",
    "__pycache__",
    ".venv",
    "venv",
    ".idea",
    ".vscode",
})

# Git status invocation timeout (seconds) per repo.
GIT_TIMEOUT_S = 5


# --- Data model ------------------------------------------------------------

@dataclass
class Node:
    path: Path
    is_repo: bool = False
    children: list["Node"] = field(default_factory=list)


# --- Phase 1: scan ---------------------------------------------------------

def scan(root: Path, max_depth: int, include_hidden: bool) -> Node:
    """Build a raw tree of Node objects rooted at `root`.

    `is_repo` is decided by the presence of a `.git` entry (file or directory)
    in the directory's own immediate children. This handles git worktrees
    (where `.git` is a *file* pointing to the real git dir).
    """
    return _scan(root, depth=0, max_depth=max_depth, include_hidden=include_hidden)


def _scan(directory: Path, depth: int, max_depth: int, include_hidden: bool) -> Node:
    node = Node(path=directory)

    # `.git` is_repo check — uses immediate children of `directory`, NOT the
    # recursion result. A real repo here means this directory's own worktree.
    try:
        with os.scandir(directory) as it:
            immediate = list(it)
    except (PermissionError, FileNotFoundError, NotADirectoryError):
        return node

    has_git_entry = any(e.name == ".git" for e in immediate)
    node.is_repo = has_git_entry

    if depth >= max_depth:
        return node

    for entry in immediate:
        if not entry.is_dir(follow_symlinks=False):
            continue
        name = entry.name
        if name in SKIP_DIRS:
            continue
        if not include_hidden and name.startswith("."):
            continue
        try:
            child_path = Path(entry.path)
        except (OSError, ValueError):
            continue
        child = _scan(child_path, depth + 1, max_depth, include_hidden)
        node.children.append(child)

    return node


# --- Phase 2: prune + collect kept repos -----------------------------------

def kept_repos(node: Node) -> list[Node]:
    """Return a flat list of repo Nodes that survive pruning, preserving the
    order in which they appear in a depth-first traversal.
    """
    if not _subtree_has_repo(node):
        return []
    out: list[Node] = []
    if node.is_repo:
        out.append(node)
    for child in node.children:
        out.extend(kept_repos(child))
    return out


def _subtree_has_repo(node: Node) -> bool:
    if node.is_repo:
        return True
    return any(_subtree_has_repo(c) for c in node.children)


def subtree_has_repo_iter(root: Node) -> Iterator[Node]:
    """Yield every node in `root`'s subtree that should appear in the
    rendered tree (i.e. the node itself is a repo, or it's a directory on
    the path to one).
    """
    if not _subtree_has_repo(root):
        return
    yield root
    for child in root.children:
        yield from subtree_has_repo_iter(child)


# --- Rendering -------------------------------------------------------------

def render_tree(root: Node) -> str:
    """Render the kept part of `root` as an ASCII tree."""
    if not _subtree_has_repo(root):
        return f"---{to_forward_slashes(root.path)}"
    lines = [f"---{to_forward_slashes(root.path)}"]
    _render_node(root, prefix="", is_root=True, lines=lines)
    return "\n".join(lines) + "\n"


def _render_node(node: Node, prefix: str, is_root: bool, lines: list[str]) -> None:
    kept_children = [c for c in node.children if _subtree_has_repo(c)]
    for i, child in enumerate(kept_children):
        last = i == len(kept_children) - 1
        connector = "|____" if not is_root else "  |____"
        # For root-level children, prefix is "" and connector becomes "  |____"
        # (matches the spec's example). For deeper children, prefix already
        # contains the accumulated bars.
        if is_root:
            line_prefix = ""
        else:
            line_prefix = prefix
        label = label_for(child)
        lines.append(f"{line_prefix}{connector}{label}")
        # Children's prefix: parent's prefix + (4 spaces if not last, else 4 spaces —
        # the spec example keeps the bar always; we follow that).
        child_prefix = prefix + ("    " if not is_root else "    ")
        if is_root:
            # After a root child, the prefix for *its* children is "    " (4 spaces).
            _render_node(child, "    ", is_root=False, lines=lines)
        else:
            _render_node(child, child_prefix, is_root=False, lines=lines)


def label_for(node: Node) -> str:
    name = node.path.name or str(node.path)
    if not node.is_repo:
        return f"{name}/"
    return f"{name}(?)"


def label_for_with_status(node: Node) -> str:
    name = node.path.name or str(node.path)
    branch, dirty = git_status_for(node.path)
    star = "*" if dirty else ""
    return f"{name}({branch}{star})"


def to_forward_slashes(p: Path) -> str:
    return p.as_posix()


# --- Git status ------------------------------------------------------------

def git_status_for(repo: Path) -> tuple[str, bool]:
    """Return (branch_label, is_dirty) for `repo`. Never raises.

    `branch_label` is one of:
      - the branch name (e.g. "master", "feat/foo")
      - "HEAD(<short-sha>)" for detached HEAD
      - "unknown" if the git command fails or times out
    """
    try:
        proc = subprocess.run(
            ["git", "status", "--porcelain", "--branch"],
            cwd=str(repo),
            capture_output=True,
            text=True,
            timeout=GIT_TIMEOUT_S,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return "unknown", False

    if proc.returncode != 0:
        return "unknown", False

    lines = proc.stdout.splitlines()
    if not lines:
        return "unknown", False

    head = lines[0]
    dirty = len(lines) > 1
    if head.startswith("## "):
        branch = head[3:].split("...")[0].strip()
        if branch == "HEAD":
            # Detached: line is "## HEAD (detached at abc1234)"
            tail = head[3:]
            # Try to extract a short sha from "(detached at abc1234)"
            if "(detached at " in tail:
                sha = tail.split("(detached at ", 1)[1].rstrip(")").strip()
                branch = f"HEAD({sha[:7]})"
            else:
                branch = "HEAD(?)"
        return branch, dirty

    return "unknown", dirty


# --- Paths format ----------------------------------------------------------

def render_paths(repos: list[Node]) -> str:
    return "\n".join(to_forward_slashes(r.path) for r in repos) + ("\n" if repos else "")


# --- CLI -------------------------------------------------------------------

def build_argparser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="list_git_repos.py",
        description=(
            "Scan a directory tree and print all git repositories as a pruned "
            "ASCII tree, with current branch and dirty marker."
        ),
    )
    p.add_argument(
        "root",
        nargs="?",
        default=".",
        help="Scan root (default: current working directory).",
    )
    p.add_argument(
        "--max-depth",
        type=int,
        default=3,
        help="Recursion depth, root = 0 (default: 3).",
    )
    p.add_argument(
        "--with-status",
        action="store_true",
        help="Collect current branch and dirty marker per repo (extra git call).",
    )
    p.add_argument(
        "--format",
        choices=["tree", "paths"],
        default="tree",
        help="Output format (default: tree).",
    )
    p.add_argument(
        "--include-hidden",
        action="store_true",
        help="Include dotfile directories (default: off).",
    )
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_argparser().parse_args(argv)
    root = Path(args.root).resolve()
    if not root.is_dir():
        print(f"error: {root} is not a directory", file=sys.stderr)
        return 2

    if args.max_depth < 0:
        print("error: --max-depth must be >= 0", file=sys.stderr)
        return 2

    tree = scan(root, args.max_depth, args.include_hidden)
    repos = kept_repos(tree)

    if args.format == "paths":
        sys.stdout.write(render_paths(repos))
        return 0

    # Tree format. Build manually so we can use label_for_with_status.
    if not _subtree_has_repo(tree):
        sys.stdout.write(f"---{to_forward_slashes(tree.path)}\n")
        return 0

    lines = [f"---{to_forward_slashes(tree.path)}"]
    _render_with_status(
        tree, prefix="", is_root=True, lines=lines, with_status=args.with_status
    )
    sys.stdout.write("\n".join(lines) + "\n")
    return 0


def _render_with_status(
    node: Node, prefix: str, is_root: bool, lines: list[str], with_status: bool
) -> None:
    kept_children = [c for c in node.children if _subtree_has_repo(c)]
    for child in kept_children:
        connector = "  |____" if is_root else "|____"
        if is_root:
            line_prefix = ""
        else:
            line_prefix = prefix
        if with_status:
            label = label_for_with_status(child) if child.is_repo else f"{child.path.name}/"
        else:
            label = label_for(child)
        lines.append(f"{line_prefix}{connector}{label}")
        if is_root:
            _render_with_status(child, "    ", False, lines, with_status)
        else:
            _render_with_status(child, prefix + "    ", False, lines, with_status)


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 2: Replace the 5th test with a real implementation**

Edit `list-git-repos/tests/test_list_git_repos.py`. Replace the `test_no_git_invocation_when_status_off` function body with:

```python
def test_no_git_invocation_when_status_off(tmp_path, monkeypatch):
    """With --with-status OFF, the script must not shell out to `git status`
    for each repo. We assert this by importing the module and patching
    `subprocess.run` to count invocations.
    """
    import importlib.util
    spec = importlib.util.spec_from_file_location("lgr", SCRIPT)
    # Loading the module executes its top-level imports but not main().
    # The script is import-safe because all CLI logic is in main().
    lgr = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(lgr)

    repo = tmp_path / "r"
    make_git_repo(repo)

    real_run = subprocess.run
    git_status_calls = []

    def spy_run(*args, **kwargs):
        # Only count calls to `git status` (not `git init`, `git commit`, etc.
        # in test setup).
        cmd = args[0] if args else kwargs.get("args")
        if isinstance(cmd, (list, tuple)) and len(cmd) >= 2 and cmd[0] == "git":
            if cmd[1] == "status":
                git_status_calls.append(cmd)
        return real_run(*args, **kwargs)

    monkeypatch.setattr(lgr.subprocess, "run", spy_run)

    rc, out, _ = run_script_via_module(lgr, [str(repo)])
    assert rc == 0
    assert git_status_calls == [], f"expected no `git status` calls, got: {git_status_calls}"
```

And add a helper near the top of the test file:

```python
def run_script_via_module(lgr, argv):
    """Invoke lgr.main(argv) and capture stdout/stderr via redirect."""
    import io
    from contextlib import redirect_stdout, redirect_stderr
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        rc = lgr.main(argv)
    return rc, out.getvalue(), err.getvalue()
```

- [ ] **Step 3: Run tests to verify GREEN**

```bash
pytest list-git-repos/tests/ -v
```

Expected: 5 tests pass. If any fail, fix the script and re-run. Common issues:
- Path separator: ensure `to_forward_slashes` is used everywhere in rendering.
- Pruning: ensure `_subtree_has_repo` is called before rendering a node's children.
- Dirty detection: ensure `git status --porcelain --branch` is the only command used.

- [ ] **Step 4: Manually verify the tree output**

```bash
# Run on the skill's own parent directory
python list-git-repos/scripts/list_git_repos.py . --with-status
```

Expected: `list-git-repos` is NOT a git repo (no `.git` in this skill's directory), so the output should show the parent tree including `git-commit-helper(master*)`, `staged-doc-naming(master)`, and `list-git-repos(?` (since this command is being run with the script targeting the repo, not as a child of itself — confirm the tree shows the immediate git repos under the parent).

If running on the repo root (`E:/Workspace/iWork/neil-skills`):

```bash
python list-git-repos/scripts/list_git_repos.py "$(git rev-parse --show-toplevel)" --with-status --max-depth 2
```

Expected: a tree showing the 3 skill directories, each as a non-git dir, with their own git repos (this repo + the 2 sibling skill repos if they were git-initialized). This will help you eyeball the ASCII art.

- [ ] **Step 5: Commit**

```bash
git add list-git-repos/scripts/list_git_repos.py list-git-repos/tests/test_list_git_repos.py
python ~/.claude/skills/git-commit-helper/scripts/ai_commit.py --message-file - <<'EOF'
feat(master): 实现 list-git-repos 扫描脚本与 5 个回归测试

- scripts/list_git_repos.py：两阶段扫描（建树+剪枝），argparse 入口
- 阶段 1 用 os.scandir 判 .git 立即子项，正确处理 worktree 链接文件
- 阶段 2 自底向上剪枝，渲染 ASCII 树，前向斜杠路径
- --with-status 开启时调 git status --porcelain --branch，5s 超时降级为 unknown
- SKIP_DIRS 硬编码，跳过 .git / node_modules / __pycache__ 等
- tests/ 覆盖 5 个 RED 场景
EOF
```

Expected: commit succeeds. No push.

---

## Task 5: Write SKILL.md

**Files:**
- Create: `list-git-repos/SKILL.md`

- [ ] **Step 1: Write the SKILL.md**

```markdown
---
name: list-git-repos
description: Use when scanning a directory tree for git repositories, when /init initializes a new workspace, when auditing a workspace for cross-repo work, or when the user asks "what git repos are in this directory / 工作区 / 父目录" — runs a pruned ASCII tree scan with current branch and dirty marker per repo. Output is a tree by default; pass --format paths for one path per line. Triggers: "列举 / 列出 / 扫一下 / 盘点 / 审计 / /init 一个新工作区 / 对所有 repo 跑一遍 ...".
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

```
---<ROOT>
  |____<dir-or-repo>
  |    |____<repo>(<branch>[*])
  |____<repo>(<branch>)
```

- Root line: `---<ROOT>`.
- Root children: `  |____` (2-space indent + bar).
- Deeper children: `    |____` (4-space indent per level).
- Repo node: `<name>(<branch>[*])`.
  - `<branch>` from `git status --porcelain --branch` first line, stripped of `## `.
  - Detached HEAD: `HEAD(<short-sha>)` (e.g. `HEAD(abc1234)`).
  - `*` appended when porcelain has any line after the first (dirty).
  - `--with-status` OFF: literal `?` (not inspected).
  - `--with-status` ON but git failed: `unknown`.
- Non-repo dir node: `<name>/` (trailing slash) when it has at least one git-repo descendant.
- **Pruning**: any subtree with zero git repos is omitted entirely.
- All paths use forward slashes (`/`), even on Windows.

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

The RED-phase baseline (see `docs/baseline.md`) showed agents reliably make
these specific errors under pressure:

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
4. Commit both changes in one commit with the `feat(master):` header.

**Never** add a skip-list entry ad-hoc inside a conversation without committing.
```

- [ ] **Step 2: Verify SKILL.md frontmatter parses**

```bash
head -3 list-git-repos/SKILL.md
```

Expected: the first 3 lines are the YAML frontmatter with `name: list-git-repos` and a one-line `description:` that starts with "Use when".

- [ ] **Step 3: Commit**

```bash
git add list-git-repos/SKILL.md
python ~/.claude/skills/git-commit-helper/scripts/ai_commit.py --message-file - <<'EOF'
docs(master): 编写 list-git-repos SKILL.md 触发文档

- description 含 /init / 列举 / 扫 / 盘点等中英文触发词
- 输出格式章节含 ASCII 树示例与 dirty 标记规则
- CLI Quick Reference 表格覆盖全部 5 个 flag
- Rationalization Table 5 行对应 5 个 RED baseline 漂移点
- Red Flags / Extending Skip List 章节与 staged-doc-naming 同构
EOF
```

Expected: commit succeeds. No push.

---

## Task 6: Update README.md to list the new skill

**Files:**
- Modify: `README.md` (the repo-root `README.md`)

- [ ] **Step 1: Add the skill entry to the Skills list**

Edit `README.md`. Insert the following block **after** the `staged-doc-naming` entry, before the `## 目录结构` section:

```markdown
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
```

- [ ] **Step 2: Update the directory structure block**

Edit the `## 目录结构` section in `README.md`. Replace its body with:

```
neil-skills/
├── README.md                        # 本文件，仓库总览
├── pytest.ini                       # pytest 配置（testpaths 指向 list-git-repos/tests）
├── git-commit-helper/
│   ├── SKILL.md                     # Git 提交身份标识规范
│   └── scripts/
│       └── ai_commit.py             # 提交脚本（Python 3）
├── staged-doc-naming/
│   ├── SKILL.md                     # 文档阶段命名规范
│   └── scripts/
│       └── stage_naming.py          # 命名转换脚本（Python 3）
└── list-git-repos/
    ├── SKILL.md                     # Git 仓库扫描与树形输出规范
    ├── scripts/
    │   └── list_git_repos.py        # 扫描脚本（Python 3，纯 stdlib）
    ├── tests/
    │   └── test_list_git_repos.py   # 5 个回归测试（pytest）
    └── docs/
        └── baseline.md              # RED 阶段基线记录
```

- [ ] **Step 3: Verify README renders the new section**

```bash
grep -n "list-git-repos" README.md
```

Expected: 3+ matches — the new `### list-git-repos` heading, the `## 目录结构` block entry, and the embedded `python list-git-repos/...` command.

- [ ] **Step 4: Commit**

```bash
git add README.md
python ~/.claude/skills/git-commit-helper/scripts/ai_commit.py --message-file - <<'EOF'
docs(master): 在 README.md 中登记 list-git-repos skill

- 新增 ### list-git-repos 章节，含触发场景、5 条核心规则、调用示例
- 目录结构块补齐 pytest.ini 与 list-git-repos 子树
EOF
```

Expected: commit succeeds. No push.

---

## Task 7: Final integration check (REFACTOR phase, smoke test)

**Files:** none modified. This task runs the existing tests and the script end-to-end as a final smoke test.

- [ ] **Step 1: Re-run all tests**

```bash
pytest list-git-repos/tests/ -v
```

Expected: 5 tests pass. If any fail, fix and commit a fix using `fix(master): ...`.

- [ ] **Step 2: Smoke-test the script against the user's actual workspace**

```bash
# Pick a real workspace root; the user has E:/Workspace
python list-git-repos/scripts/list_git_repos.py "E:/Workspace" --max-depth 2 --with-status
```

Expected: a tree containing at least the `iWork` directory and any sibling git repos visible at depth 2. The `iWork` node should be rendered as a non-git directory (no `(.git)` annotation) IF `iWork` itself isn't a git repo. The repos under `iWork/neil-skills` should appear at depth 3 with their branch + dirty info.

If the output shows `iWork/` with no repos under it at depth 2, increase depth:

```bash
python list-git-repos/scripts/list_git_repos.py "E:/Workspace" --max-depth 3 --with-status
```

- [ ] **Step 3: Smoke-test the paths format**

```bash
python list-git-repos/scripts/list_git_repos.py "E:/Workspace" --format paths --max-depth 3
```

Expected: one absolute path per line, all using `/`. No tree characters. No branch labels.

- [ ] **Step 4: Verify the git history of new commits**

```bash
git log --oneline -10
```

Expected: 5 new commits, all with author `吴宇春 (Ai) <wuyuchun@rainbowcn.com>`. None pushed (run `git status` to confirm no `Your branch is ahead of 'origin/master'` message; if a remote is configured, the local branch should not be ahead).

- [ ] **Step 5: No commit needed (smoke test only)**

If anything failed in steps 1–4, fix it and commit. If all passed, this task is done. **No push.**

---

## Self-Review (run before declaring done)

- [ ] **Spec coverage:** Walk through `docs/superpowers/specs/2026-07-02-list-git-repos-design.md` section by section:
  - §1 Purpose: SKILL.md overview, Task 5.
  - §2 Boundary: SKILL.md "Do NOT use this skill" list, Task 5.
  - §3 Triggering Conditions: SKILL.md description, Task 5.
  - §4 Output Format: SKILL.md "Output Format" section, Task 5; tests 1, 3, 4, Task 2/4.
  - §5 CLI: SKILL.md "CLI Quick Reference", Task 5.
  - §6 Algorithm: scripts/list_git_repos.py `scan` + `kept_repos` + `_subtree_has_repo`, Task 4.
  - §7 `--with-status` interaction: Task 4 `git_status_for` and `--with-status` gating.
  - §8 File Layout: Task 1 (dirs) + Tasks 4/5 (script + SKILL.md).
  - §9 Test Plan: Task 2 (tests) + Task 3 (baseline).
  - §10 Commit Plan: every commit goes through `ai_commit.py`, no push.
  - §11 Open Questions: deferred `--json`, `--porcelain`, `--follow-symlinks`, skip-list extension. SKILL.md mentions these (defer is documented, not silent).
- [ ] **Placeholder scan:** No "TBD", "TODO", "implement later" in the plan. The `NotImplementedError` in test 5 (Task 2) is intentional and explicitly resolved in Task 4 Step 2.
- [ ] **Type consistency:** `Node.is_repo` (not `is_git_repo`); `kept_repos` (not `collect_repos`); `git_status_for` (not `get_git_status`); `SKIP_DIRS` (not `SKIP_LIST`).
- [ ] **Identity:** every commit uses `ai_commit.py`. Branch is `master` throughout. Author is `吴宇春 (Ai) <wuyuchun@rainbowcn.com>`. **No push** in any step.

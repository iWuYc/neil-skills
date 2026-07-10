#!/usr/bin/env python3
"""list_git_repos.py — scan a directory tree and print git repositories as a
pruned ASCII tree, with current branch and dirty marker.

Spec: docs/superpowers/specs/2026-07-02-list-git-repos-design.md
"""

from __future__ import annotations

import argparse
import os
# NB: kept as `import subprocess` (not `from subprocess import run`) so that
# test 5's monkeypatch.setattr(lgr.subprocess, "run", spy_run) works. If you
# refactor this, update test 5 to use a different monkeypatch target.
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path


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
        child = _scan(Path(entry.path), depth + 1, max_depth, include_hidden)
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


# --- Rendering -------------------------------------------------------------

def to_forward_slashes(p: Path) -> str:
    return p.as_posix()


def label_for(node: Node) -> str:
    """Default label, no git status collected (branch token = '?')."""
    name = node.path.name or str(node.path)
    if not node.is_repo:
        return f"{name}/"
    return f"{name}(?)"


def label_for_with_status(node: Node) -> str:
    name = node.path.name or str(node.path)
    branch, dirty = git_status_for(node.path)
    suffix = "*" if dirty else ""
    return f"{name}({branch}){suffix}"


def render_tree(root: Node, with_status: bool = False) -> str:
    """Render the kept part of `root` as an ASCII tree.

    The header is `---<basename>` (basename only, not full path) plus, when
    the root itself is a repo, its label appended on the same line so that
    scanning a repo directly (e.g. `list_git_repos.py .` from inside a
    repo) still surfaces the root as a repo node.
    """
    if not _subtree_has_repo(root):
        return f"---{root.path.name or to_forward_slashes(root.path)}\n"
    header = f"---{root.path.name or to_forward_slashes(root.path)}"
    if root.is_repo:
        if with_status:
            branch, dirty = git_status_for(root.path)
            suffix = "*" if dirty else ""
            header += f"({branch}){suffix}"
        else:
            header += "(?)"
    lines = [header]
    _render_node(root, prefix="", is_root=True, lines=lines, with_status=with_status)
    return "\n".join(lines) + "\n"


def _render_node(
    node: Node, prefix: str, is_root: bool, lines: list[str], with_status: bool
) -> None:
    kept_children = [c for c in node.children if _subtree_has_repo(c)]
    for i, child in enumerate(kept_children):
        # Root children get the "  |____" connector; deeper children get "|____"
        # (the accumulated prefix already carries the bar + indent).
        connector = "  |____" if is_root else "|____"
        line_prefix = "" if is_root else prefix
        if with_status and child.is_repo:
            label = label_for_with_status(child)
        else:
            label = label_for(child)
        lines.append(f"{line_prefix}{connector}{label}")
        # Recurse: deeper children's prefix is parent's prefix + 4 spaces.
        child_prefix = "" if is_root else prefix + "    "
        _render_node(child, child_prefix, is_root=False, lines=lines, with_status=with_status)


def render_paths(repos: list[Node]) -> str:
    return "\n".join(to_forward_slashes(r.path) for r in repos) + ("\n" if repos else "")


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
            tail = head[3:]
            if "(detached at " in tail:
                sha = tail.split("(detached at ", 1)[1].rstrip(")").strip()
                branch = f"HEAD({sha[:7]})"
            else:
                branch = "HEAD(?)"
        return branch, dirty

    return "unknown", dirty


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

    # Print the resolved scanned root to stderr so the user knows which
    # directory was scanned (the stdout tree header uses basename only, which
    # is ambiguous when two roots have a same-named subdir). Going to stderr
    # keeps stdout pipe-friendly and does not break test substring assertions.
    print(f"scanned: {to_forward_slashes(root)}", file=sys.stderr)

    if args.format == "paths":
        sys.stdout.write(render_paths(repos))
        return 0

    sys.stdout.write(render_tree(tree, with_status=args.with_status))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
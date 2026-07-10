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
    for each repo. We assert this by importing the module as a library and
    patching `subprocess.run` to count invocations.
    """
    import importlib.util
    import sys as _sys
    spec = importlib.util.spec_from_file_location("list_git_repos", SCRIPT)
    lgr = importlib.util.module_from_spec(spec)
    _sys.modules["list_git_repos"] = lgr  # dataclass needs __module__ in sys.modules
    spec.loader.exec_module(lgr)

    repo = tmp_path / "r"
    make_git_repo(repo)

    real_run = subprocess.run
    git_status_calls = []

    def spy_run(*args, **kwargs):
        cmd = args[0] if args else kwargs.get("args")
        if isinstance(cmd, (list, tuple)) and len(cmd) >= 2 and cmd[0] == "git" and cmd[1] == "status":
            git_status_calls.append(cmd)
        return real_run(*args, **kwargs)

    monkeypatch.setattr(lgr.subprocess, "run", spy_run)

    rc = lgr.main([str(repo)])  # no --with-status
    assert rc == 0
    assert git_status_calls == [], f"expected no `git status` calls, got: {git_status_calls}"

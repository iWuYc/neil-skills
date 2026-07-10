#!/usr/bin/env python3
"""
ai_commit.py — make a single AI-authored commit with the (Ai) marker
guaranteed, and the commit message format validated.

Refuses forbidden flag combinations; never pushes. Cross-platform
(Windows / Git Bash / WSL / macOS / Linux).

Usage:
    ./scripts/ai_commit.py "feat:(feature/login) 新增登录功能" \
        --feat-name "登录功能" \
        --body "- 新增 src/auth/login.ts,校验用户名是否存在
- 新增 src/auth/password.ts,校验登录密码是否正确
- 新增 src/auth/session.ts,管理登录态"

    ./scripts/ai_commit.py --message-file MSG.txt
    ./scripts/ai_commit.py -a file1 file2 -m "fix:(fix/x) 修复 ..."
    ./scripts/ai_commit.py --amend --no-edit
    ./scripts/ai_commit.py --amend -m "new message"

Exit codes:
    0 — commit succeeded; (Ai) verified present, format verified
    1 — pre-flight refusal (identity missing, forbidden flag)
    2 — post-commit verification failed ((Ai) not in author after commit)
    3 — not inside a git working tree
    4 — commit message format invalid (header / body / metadata rules)
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path
from typing import List, Optional, Tuple


# --- Exit codes (kept compatible with ai_commit.sh) ---------------------

EXIT_OK = 0
EXIT_REFUSED = 1
EXIT_POST_VERIFY = 2
EXIT_NOT_GIT = 3
EXIT_FORMAT_INVALID = 4


# --- Format rules (mirror SKILL.md, enforced in code) -------------------

# Header MUST be: {type}({branchName}): {abstractDescription}
# - {type} is one or more word chars (feat, fix, docs, refactor, chore, ci, perf, ...)
# - {branchName} is anything not containing ')' (parentheses, slashes, hyphens OK)
# - {abstractDescription} is one or more non-newline chars
HEADER_RE = re.compile(r"^([A-Za-z0-9_]+)\(([^)]+)\):\s+(\S.*)$")

# A bullet line starts with "- " (ASCII dash + space) at column 0.
# We use ASCII dash on purpose: SKILL.md examples use "- " and Chinese full-
# width dashes ("—") are not valid bullet markers.
BULLET_RE = re.compile(r"^-\s+\S")

# featName: <功能名>
FEAT_NAME_RE = re.compile(r"^featName:\s+\S")

# fix: <issueCode>
FIX_ISSUE_RE = re.compile(r"^fix:\s+\S")

# A "N/A" / "无" / "未知" / "TBD" placeholder on a metadata line — explicitly
# forbidden by SKILL.md. The whole line should have been omitted.
PLACEHOLDER_RE = re.compile(r"^(featName|fix):\s*(N/A|无|未知|TBD|NA|na|null)\s*$", re.IGNORECASE)

# issueCode (e.g. "#10028", "PROJ-1234", "JIRA-42") is forbidden inside the
# subject of a `fix` commit. It must be a separate `fix:` metadata line.
# SKILL.md explicitly rejects the convention of stuffing it into parens at
# the end of the subject line.
ISSUE_IN_SUBJECT_RE = re.compile(r"\(#\d+\)|\(([A-Z][A-Z0-9]+-\d+)\)|\(#\d+\)$")

# Latin-only line in body — used to warn (not block) on English prose bodies.
# We can't require "no English at all" (filenames, library names are allowed),
# but we can flag lines that are entirely Latin characters + ASCII punctuation
# as suspicious.
LATIN_ONLY_RE = re.compile(r"^[\x20-\x7E]+$")


# --- Pre-flight forbidden-flag scan ------------------------------------

FORBIDDEN_FLAGS = {"--reset-author"}


def fail(code: int, msg: str) -> "NoReturn":  # type: ignore[name-defined]
    print(f"ERROR: {msg}", file=sys.stderr)
    sys.exit(code)


def warn(msg: str) -> None:
    print(f"WARNING: {msg}", file=sys.stderr)


def run(cmd: List[str], check: bool = True) -> subprocess.CompletedProcess:
    # Force UTF-8 on Windows — git's output and our own Chinese messages
    # blow up under the default GBK codec.
    return subprocess.run(
        cmd,
        check=check,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


# --- Identity resolution -------------------------------------------------

def get_identity() -> Tuple[str, str, str]:
    """Return (name, email, scope) where scope is 'local' or 'global'."""
    try:
        run(["git", "rev-parse", "--is-inside-work-tree"], check=True)
    except subprocess.CalledProcessError:
        fail(EXIT_NOT_GIT, f"{Path.cwd()} is not a git repository")

    def cfg(scope: str, key: str) -> str:
        r = run(["git", "config", f"--{scope}", key], check=False)
        return (r.stdout or "").strip()

    local_name = cfg("local", "user.name")
    local_email = cfg("local", "user.email")
    global_name = cfg("global", "user.name")
    global_email = cfg("global", "user.email")

    if local_name and local_email:
        return local_name, local_email, "local"
    if global_name and global_email:
        # Per SKILL.md Red Flags: when the repo has no local config, the
        # identity came from global scope. The user may want a different
        # identity for this repo. Warn, but do not block — the marker rule
        # is identity-independent, so the (Ai) suffix is still correct.
        warn(
            "no local git identity in this repo; falling back to global "
            f"({global_name} <{global_email}>). Per SKILL.md Red Flags, this "
            "is a soft signal to confirm with the user before proceeding. "
            "Set a per-repo identity with: "
            'git config user.name  "Your Name" / '
            'git config user.email "you@example.com"'
        )
        return global_name, global_email, "global"
    fail(
        EXIT_REFUSED,
        "git identity not configured. Run:\n"
        '  git config user.name  "Your Name"\n'
        '  git config user.email "you@example.com"',
    )


# --- Commit message format validation -----------------------------------

def split_message(msg: str) -> Tuple[str, List[str], List[str]]:
    """
    Split a commit message into (header, optional_metadata_lines, body_lines).

    Per SKILL.md:
        <header>
        <blank>
        <optional featName: / fix: line>
        <optional blank>
        <body, one or more bullet lines, possibly separated by blanks>

    Walk through lines, collecting metadata up to the first blank, then body.
    """
    # Normalize CRLF → LF.
    msg = msg.replace("\r\n", "\n").rstrip("\n")
    lines = msg.split("\n")

    if not lines or not lines[0].strip():
        fail(EXIT_FORMAT_INVALID, "commit message is empty or starts with a blank line")

    header = lines[0]
    rest = lines[1:]

    metadata: List[str] = []
    body: List[str] = []

    # Skip leading blank lines (the header/body separator).
    i = 0
    while i < len(rest) and not rest[i].strip():
        i += 1

    # Collect contiguous metadata lines (featName: / fix:) at the top of
    # the body region. The metadata block ends at the first non-metadata line.
    while i < len(rest) and (FEAT_NAME_RE.match(rest[i]) or FIX_ISSUE_RE.match(rest[i])):
        metadata.append(rest[i])
        i += 1

    # Skip one optional blank line between metadata and body.
    while i < len(rest) and not rest[i].strip():
        i += 1
    body = list(rest[i:])

    return header, metadata, body


def validate_header(header: str, expected_branch: str) -> None:
    """Enforce {type}({branchName}): {abstractDescription}."""
    m = HEADER_RE.match(header)
    if not m:
        # Build a helpful error showing what's wrong.
        example = "feat(feature/login): 新增登录功能"
        if header.startswith("#"):
            fail(
                EXIT_FORMAT_INVALID,
                f"header starts with '#' (looks like a Git comment, not a header).\n"
                f"         Expected format: {{type}}:({{branchName}}) {{abstractDescription}}\n"
                f"         Example: {example!r}",
            )
        if "(" not in header or ")" not in header:
            fail(
                EXIT_FORMAT_INVALID,
                f"header missing '(branchName)' segment.\n"
                f"         Got:      {header!r}\n"
                f"         Expected: {example!r}\n"
                f"         Note: '()' is the branch-name slot, not a scope. "
                f"'feat(auth): ...' is wrong (scope in slot); 'feat(auth)title' is wrong (colon outside parens). 'feat(feature/login): ...' is right (branch in slot, colon after `)`).",
            )
        # Has parens but doesn't match the full pattern.
        fail(
            EXIT_FORMAT_INVALID,
            f"header does not match required pattern.\n"
            f"         Got:      {header!r}\n"
            f"         Expected: {example!r}\n"
            r"         Pattern:  ^([A-Za-z0-9_]+)\(([^)]+)\):\s+(\S.+)$",
        )

    _, branch, abstract = m.groups()
    if branch != expected_branch:
        fail(
            EXIT_FORMAT_INVALID,
            f"header branch name does not match the current branch.\n"
            f"         header:    ({branch})\n"
            f"         git HEAD:  ({expected_branch})\n"
            f"         If you really mean to commit on a different branch, switch first "
            f"with `git switch {branch}`.",
        )
    if not abstract.strip():
        fail(EXIT_FORMAT_INVALID, "header is missing the abstractDescription after the branch name")
    if ISSUE_IN_SUBJECT_RE.search(abstract):
        msg = (
            "issueCode must be on its own 'fix: <code>' line, not in the subject. "
            "Move '(#10028)' out of the subject - put it on its own line as 'fix: #10028'. "
            f"Got: {header!r}"
        )
        fail(EXIT_FORMAT_INVALID, msg)



def validate_metadata(metadata: List[str], header_type: str) -> None:
    """Enforce featName:/fix: rules: present-or-absent, no placeholders."""
    feat_names = [line for line in metadata if FEAT_NAME_RE.match(line)]
    fix_lines = [line for line in metadata if FIX_ISSUE_RE.match(line)]

    for line in metadata:
        if PLACEHOLDER_RE.match(line):
            # Extract the field name for the error.
            field = line.split(":", 1)[0]
            fail(
                EXIT_FORMAT_INVALID,
                f"{field}: line uses a placeholder (N/A / 无 / 未知 / TBD).\n"
                f"         The whole line should be omitted, not half-present.\n"
                f"         Got: {line!r}",
            )

    # featName: only allowed on feat.
    if feat_names and header_type != "feat":
        fail(
            EXIT_FORMAT_INVALID,
            f"featName: line is only valid on 'feat' type commits.\n"
            f"         header type: {header_type!r}\n"
            f"         Got:         {feat_names[0]!r}",
        )
    # fix: only allowed on fix.
    if fix_lines and header_type != "fix":
        fail(
            EXIT_FORMAT_INVALID,
            f"fix: line is only valid on 'fix' type commits.\n"
            f"         header type: {header_type!r}\n"
            f"         Got:         {fix_lines[0]!r}",
        )


def validate_body(body: List[str]) -> None:
    """
    Enforce: every commit has at least one bullet, in Chinese, describing
    'what changed and why' rather than just a file path.
    """
    # Strip trailing blank lines.
    while body and not body[-1].strip():
        body.pop()

    if not body:
        fail(
            EXIT_FORMAT_INVALID,
            "commit message has no body.\n"
            "         Every commit — including one-line fixes — needs at least one\n"
            "         '- ' bullet describing what changed and why. The 'change is\n"
            "         too small for a body' rationalization is exactly what this\n"
            "         rule blocks (see SKILL.md 'Body (强制 — 没有任何豁免)').",
        )

    # Find the first non-blank body line and check it's a bullet.
    first_content = next((line for line in body if line.strip()), None)
    if first_content is None:
        fail(EXIT_FORMAT_INVALID, "body is all blank lines")

    if not BULLET_RE.match(first_content):
        fail(
            EXIT_FORMAT_INVALID,
            f"first non-blank body line is not a bullet.\n"
            f"         Got:      {first_content!r}\n"
            f"         Expected: '- <变更细节>'\n"
            f"         Body must use Chinese '- ' bullets, not free-form prose.",
        )

    # Soft-warn on Latin-only body lines (filenames and library names are OK
    # in passing, but a whole-line Latin paragraph is suspicious).
    for line in body:
        stripped = line.strip()
        if not stripped:
            continue
        if not BULLET_RE.match(stripped):
            # Not a bullet at all — we've already enforced the first one is;
            # warn about the rest.
            warn(
                f"body line is not a '- ' bullet: {stripped!r}. "
                f"Body should be Chinese '- ' bullets, not free-form prose."
            )
        elif LATIN_ONLY_RE.match(stripped) and not re.search(r"[A-Za-z_./-]", stripped.replace("- ", "", 1)):
            # Whole bullet is Latin characters + spaces (no Chinese, no
            # technical identifier). This is suspicious — could be English
            # prose. Filenames and library names inside an otherwise-Chinese
            # bullet are fine.
            warn(
                f"body bullet is entirely Latin: {stripped!r}. "
                f"Body should be Chinese; technical proper nouns (NPE, dayjs, "
                f"formatDate, file paths) can stay English, but the explanation "
                f"around them must be Chinese."
            )


def validate_message(msg: str) -> None:
    """Run all format checks on a commit message string."""
    header, metadata, body = split_message(msg)

    # Get current branch.
    r = run(["git", "rev-parse", "--abbrev-ref", "HEAD"], check=False)
    expected_branch = (r.stdout or "").strip()
    if not expected_branch or expected_branch == "HEAD":
        # Detached HEAD. Allow the message through but warn.
        warn(
            "HEAD is detached — branch name cannot be verified against header. "
            "If you intended to be on a branch, switch first with `git switch <branch>`."
        )
        # Skip the branch-name check in detached mode.
        m = HEADER_RE.match(header)
        if not m:
            validate_header(header, "__never_match__")
        header_type = m.group(1) if m else ""
    else:
        validate_header(header, expected_branch)
        m = HEADER_RE.match(header)
        header_type = m.group(1) if m else ""

    validate_metadata(metadata, header_type)
    validate_body(body)


# --- Argument parsing ---------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="ai_commit.py",
        description="Make an AI-authored commit with the (Ai) marker guaranteed, and the commit message format validated.",
    )
    p.add_argument("message", nargs="?", help="commit message text (alternative to --message-file)")
    p.add_argument("--message-file", "-f", type=Path, help="read commit message from this file (recommended for Chinese bullets)")
    p.add_argument("-a", "--add", action="append", default=[], help="stage this file before committing (may be repeated)")
    p.add_argument("-m", action="append", default=[], help="(unused; positional message or --message-file is the supported path)")
    p.add_argument("--amend", action="store_true", help="amend the previous commit")
    p.add_argument("--no-edit", action="store_true", help="with --amend, keep the existing commit message")
    return p


def collect_message(args: argparse.Namespace) -> str:
    """Resolve the commit message from --message-file or positional."""
    if args.message_file and args.message:
        fail(EXIT_REFUSED, "pass either a positional message OR --message-file, not both")
    if args.message_file:
        if not args.message_file.exists():
            fail(EXIT_REFUSED, f"--message-file not found: {args.message_file}")
        return args.message_file.read_text(encoding="utf-8")
    if args.message:
        return args.message
    fail(EXIT_REFUSED, "no commit message provided (use positional arg or --message-file)")


# --- Main ---------------------------------------------------------------

def main() -> int:
    # Pre-flight scan for forbidden flags — refuse before doing anything else.
    for arg in sys.argv[1:]:
        if arg in FORBIDDEN_FLAGS:
            fail(
                EXIT_REFUSED,
                f"{arg} strips the (Ai) marker from AI commits.\n"
                f"         Use plain --amend (which preserves author by default).",
            )
        if arg == "push" or arg == "--push" or arg == "git-push":
            fail(
                EXIT_REFUSED,
                "push is forbidden in this skill — push is the user's decision only.",
            )

    args = build_parser().parse_args()

    name, email, scope = get_identity()

    # --amend --no-edit does not need a new message — preserve the existing one.
    if not (args.amend and args.no_edit):
        message = collect_message(args)
        validate_message(message)
    else:
        message = ""  # git commit --amend --no-edit will use the existing message.

    # Refuse -m when no message source — argparse allows -m without value
    # silently otherwise.
    if args.m and not (args.message or args.message_file):
        # We didn't fail in collect_message() because -m was provided; treat
        # the -m args as the message.
        message = "\n".join(args.m)
        validate_message(message)

    ai_author = f"{name} (Ai) <{email}>"
    print(f"Committing as: {ai_author}  [source: {scope} config]")

    if args.add:
        run(["git", "add", "--", *args.add])

    if args.amend:
        if args.no_edit:
            run(["git", "commit", "--amend", f"--author={ai_author}", "--no-edit"])
        else:
            run(["git", "commit", "--amend", f"--author={ai_author}", "-m", message])
    else:
        run(["git", "commit", f"--author={ai_author}", "-m", message])

    # Post-commit verification: the marker MUST be present in the final author.
    r = run(["git", "log", "-1", "--format=%an <%ae>"], check=False)
    actual_author = (r.stdout or "").strip()
    if "(Ai)" not in actual_author:
        fail(
            EXIT_POST_VERIFY,
            f"post-commit author does not contain (Ai):\n  {actual_author}",
        )

    short = run(["git", "rev-parse", "--short", "HEAD"], check=False).stdout.strip()
    print(f"OK: commit {short} author = {actual_author}")
    return EXIT_OK


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(130)

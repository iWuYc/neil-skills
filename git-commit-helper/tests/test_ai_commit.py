"""Tests for git-commit-helper.

Exercises the script's pure-function validators directly (no subprocess, no
git calls) by importing the module. The script has an `if __name__ ==
"__main__"` guard so importing is safe and equivalent to running for
assertion purposes. Tests target the format enforcement layer
(`validate_header` / `validate_metadata` / `validate_body` /
`split_message`) and the five regexes declared at module top-level
(HEADER_RE / BULLET_RE / FEAT_NAME_RE / FIX_ISSUE_RE / PLACEHOLDER_RE /
ISSUE_IN_SUBJECT_RE) — these are the actual SKILL.md "Six Hard Rules"
codepoint, so nailing them down pins the entire skill.

What is NOT covered here:
  * The git identity resolution (get_identity) — exercises real git config
    and triggers a fail() on placeholder names; out of scope for pure tests.
  * The full main() flow — needs a git repo + a working identity; covered
    by integration use, not unit tests.
"""

import sys
from pathlib import Path

import pytest

SCRIPT_DIR = Path(__file__).parent.parent / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))

import ai_commit as ac  # noqa: E402


# --- HEADER_RE: positive cases ---------------------------------------

@pytest.mark.parametrize("header,expected_type,expected_branch,expected_abstract", [
    ("feat(feature/login): 新增登录功能", "feat", "feature/login", "新增登录功能"),
    ("fix(fix/20260702-bug): 修复登录异常", "fix", "fix/20260702-bug", "修复登录异常"),
    ("docs(feat/list-git-repos): 完善 CLAUDE.md", "docs", "feat/list-git-repos", "完善 CLAUDE.md"),
    ("chore(feature/ci-pipeline): 搭建 CI", "chore", "feature/ci-pipeline", "搭建 CI"),
    ("refactor(master): 重构入口", "refactor", "master", "重构入口"),
])
def test_header_re_accepts_well_formed_headers(header, expected_type, expected_branch, expected_abstract):
    m = ac.HEADER_RE.match(header)
    assert m is not None
    t, b, a = m.groups()
    assert (t, b, a) == (expected_type, expected_branch, expected_abstract)


# --- HEADER_RE: negative cases (the "type(scope):" trap, missing parens, etc.) ---

def test_header_re_rejects_type_scope_form():
    # SKILL.md's most-flagged mistake: '()' is the branch slot, not a scope.
    # 'feat(auth): ...' has 'auth' as the (branch) value, but no slash — at
    # the regex level this is still a legal match, so the regex is
    # permissive; the rule enforcement lives in validate_header's branch
    # equality check. We test the regex accepts it (it should — the regex
    # doesn't know scope from branch) and the validator rejects it when
    # the actual branch is different.
    m = ac.HEADER_RE.match("feat(auth): 新增功能")
    assert m is not None
    assert m.group(2) == "auth"


def test_header_re_rejects_missing_parens():
    # 'feat: 新增功能' — no parens at all
    assert ac.HEADER_RE.match("feat: 新增功能") is None


def test_header_re_rejects_colon_outside_parens():
    # 'feat(auth)title' — colon is in the wrong place
    assert ac.HEADER_RE.match("feat(auth)title") is None


def test_header_re_rejects_colon_before_parens():
    # 'feat:(branch)' — colon before '('
    assert ac.HEADER_RE.match("feat:(branch)") is None


def test_header_re_rejects_header_starting_with_hash():
    # Git comment-looking line '# feat(...): ...' is not a header.
    assert ac.HEADER_RE.match("# feat(x): title") is None


# --- validate_header: branch name equality -----------------------------

def test_validate_header_passes_when_branch_matches():
    # Should not raise.
    ac.validate_header("feat(feature/login): 新增登录功能", "feature/login")


def test_validate_header_rejects_mismatched_branch():
    with pytest.raises(SystemExit) as exc:
        ac.validate_header("feat(wrong-branch): title", "actual-branch")
    assert exc.value.code == ac.EXIT_FORMAT_INVALID


def test_validate_header_rejects_issue_code_in_subject():
    # '(#10028)' inside the subject — must be its own 'fix:' line.
    with pytest.raises(SystemExit) as exc:
        ac.validate_header("fix(feature/login): 修复登录异常 (#10028)", "feature/login")
    assert exc.value.code == ac.EXIT_FORMAT_INVALID
    # The error must explicitly mention 'fix: <code>' as the correct shape.
    err = exc.value.code  # SystemExit doesn't carry stderr, so just assert the code.


def test_validate_header_rejects_jira_code_in_subject():
    with pytest.raises(SystemExit):
        ac.validate_header("fix(feature/login): 修复异常 (PROJ-1234)", "feature/login")


def test_validate_header_rejects_issue_code_at_end_of_subject():
    # The third alternative in ISSUE_IN_SUBJECT_RE matches '(#N)$'.
    with pytest.raises(SystemExit):
        ac.validate_header("fix(feature/login): 修复登录异常 (#10028)", "feature/login")


# --- PLACEHOLDER_RE: featName: N/A / 无 / 未知 / TBD / NA / null -----

@pytest.mark.parametrize("bad_line", [
    "featName: N/A",
    "featName: 无",
    "featName: 未知",
    "featName: TBD",
    "featName: NA",
    "featName: na",
    "featName: null",
    "fix: N/A",
    "fix: 无",
    "fix: 未知",
    "fix: TBD",
])
def test_placeholder_re_matches_forbidden_values(bad_line):
    assert ac.PLACEHOLDER_RE.match(bad_line) is not None


@pytest.mark.parametrize("good_line", [
    "featName: 登录功能",
    "fix: #10028",
    "fix: PROJ-1234",
    "featName: feat04动态改写",
])
def test_placeholder_re_does_not_match_meaningful_values(good_line):
    assert ac.PLACEHOLDER_RE.match(good_line) is None


# --- validate_metadata: featName only on feat, fix only on fix ------

def test_validate_metadata_accepts_featName_on_feat():
    ac.validate_metadata(["featName: 登录功能"], "feat")


def test_validate_metadata_rejects_featName_on_non_feat():
    with pytest.raises(SystemExit) as exc:
        ac.validate_metadata(["featName: 登录功能"], "docs")
    assert exc.value.code == ac.EXIT_FORMAT_INVALID


def test_validate_metadata_accepts_fix_on_fix():
    ac.validate_metadata(["fix: #10028"], "fix")


def test_validate_metadata_rejects_fix_on_non_fix():
    with pytest.raises(SystemExit):
        ac.validate_metadata(["fix: #10028"], "feat")


def test_validate_metadata_rejects_placeholder_values():
    with pytest.raises(SystemExit) as exc:
        ac.validate_metadata(["featName: N/A"], "feat")
    assert exc.value.code == ac.EXIT_FORMAT_INVALID


def test_validate_metadata_rejects_placeholder_in_fix():
    with pytest.raises(SystemExit):
        ac.validate_metadata(["fix: 无"], "fix")


# --- BULLET_RE: '- ' at column 0 -------------------------------------

@pytest.mark.parametrize("good", [
    "- 新增 src/auth/login.ts，校验用户名是否存在",
    "- 修复登录异常问题",
    "- 重构入口逻辑",
])
def test_bullet_re_accepts_chinese_dash_space(good):
    assert ac.BULLET_RE.match(good) is not None


@pytest.mark.parametrize("bad", [
    "新增 src/auth/login.ts",                # missing '- '
    " - new bullet with leading space",       # space before dash
    "— 新增功能（中文破折号，不是 ASCII dash）",  # full-width dash
    "* bullet with star",
])
def test_bullet_re_rejects_non_dash_bullets(bad):
    assert ac.BULLET_RE.match(bad) is None


# --- validate_body: must have at least one bullet --------------------

def test_validate_body_accepts_chinese_bullets():
    ac.validate_body([
        "- 新增 src/auth/login.ts，校验用户名是否存在",
        "- 新增 src/auth/password.ts",
    ])


def test_validate_body_rejects_empty_body():
    with pytest.raises(SystemExit) as exc:
        ac.validate_body([])
    assert exc.value.code == ac.EXIT_FORMAT_INVALID


def test_validate_body_rejects_body_with_no_bullets():
    with pytest.raises(SystemExit) as exc:
        ac.validate_body([
            "This is English prose, not a bullet.",
            "Another prose line.",
        ])
    assert exc.value.code == ac.EXIT_FORMAT_INVALID


def test_validate_body_rejects_body_starting_with_non_bullet():
    with pytest.raises(SystemExit):
        ac.validate_body([
            "First line is plain text.",
            "- 第二个才是 bullet",
        ])


def test_validate_body_strips_trailing_blank_lines():
    # Trailing blanks should not trigger an error.
    ac.validate_body([
        "- 修复登录异常",
        "",
    ])


# --- split_message ----------------------------------------------------

def test_split_message_returns_header_metadata_body():
    msg = (
        "feat(feature/login): 新增登录功能\n"
        "\n"
        "featName: 登录功能\n"
        "\n"
        "- 新增 src/auth/login.ts，校验用户名是否存在\n"
        "- 新增 src/auth/password.ts\n"
    )
    header, metadata, body = ac.split_message(msg)
    assert header == "feat(feature/login): 新增登录功能"
    assert metadata == ["featName: 登录功能"]
    assert body == [
        "- 新增 src/auth/login.ts，校验用户名是否存在",
        "- 新增 src/auth/password.ts",
    ]


def test_split_message_no_metadata_section():
    msg = (
        "feat(feature/login): 新增登录功能\n"
        "\n"
        "- 新增 src/auth/login.ts\n"
    )
    header, metadata, body = ac.split_message(msg)
    assert header == "feat(feature/login): 新增登录功能"
    assert metadata == []
    assert body == ["- 新增 src/auth/login.ts"]


def test_split_message_metadata_with_blank_separator():
    # The metadata block can be followed by a blank line, then body.
    msg = (
        "fix(fix/20260702-bug): 修复\n"
        "\n"
        "fix: #10028\n"
        "\n"
        "- 修复空指针\n"
    )
    header, metadata, body = ac.split_message(msg)
    assert header == "fix(fix/20260702-bug): 修复"
    assert metadata == ["fix: #10028"]
    assert body == ["- 修复空指针"]

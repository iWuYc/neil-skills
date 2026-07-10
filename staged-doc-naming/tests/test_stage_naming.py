"""Tests for staged-doc-naming.

Exercises the script's functions directly (importing the module, not via
subprocess) and pins every behavior the script's docstring and SKILL.md
promise. The script is a pure-Python module with an
`if __name__ == "__main__"` guard, so importing it and calling its
functions is equivalent to running it for assertion purposes — and avoids
the Windows subprocess handle-inheritance issue that plan-doc-sequence's
test file documents.

Coverage targets:
  * _INDEX_RE: three sub-patterns in priority order (v-dotted, letter-dash,
    pure-digits), first match wins, the rules about bare 'v1' and overlong
    letter runs ('release-3.0').
  * parse_basename: ext split uses LAST dot only (.tar.gz, .md.bak);
    leading-dot special case (.gitkeep).
  * apply_stage: layout rules, the case where name_body is empty
    (index-only file), and the leading-dot .gitkeep output (double dot).
  * generate: end-to-end with the example basenames from SKILL.md.
  * STAGE_TAGS: closed list, unknown stages raise ValueError.
  * next_available: appends (1), (2), ... before the extension.
"""

import sys
from pathlib import Path

import pytest

SCRIPT_DIR = Path(__file__).parent.parent / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))

import stage_naming as sn  # noqa: E402


# --- STAGE_TAGS closed list --------------------------------------------

def test_stage_tags_has_six_entries_in_canonical_order():
    assert sn.STAGE_TAGS == ("pm", "dev", "plan", "case", "case.data", "实施纪要")


def test_case_data_is_a_single_two_segment_tag():
    # Documented in SKILL.md: "case.data" is a single stage tag, not two.
    # If anyone splits this into "case" + ".data" the apply_stage call
    # below would produce a different filename.
    assert sn.apply_stage("001", "三月需求", ".md", "case.data") == \
        "001.case.data.三月需求.md"


def test_apply_stage_rejects_unknown_stage():
    with pytest.raises(ValueError, match="unknown stage tag 'release'"):
        sn.apply_stage("001", "x", ".md", "release")


# --- _INDEX_RE priority rules ------------------------------------------

def test_v_prefix_requires_dotted_version():
    # bare v1 is NOT an index — falls through to letter-dash (no match)
    # then to pure-digits (no match) — so 'v1' becomes part of name body.
    idx, body, ext = sn.parse_basename("v1.2.spec.md")
    assert (idx, body, ext) == ("v1.2", "spec", ".md")

    # bare v1 (no dot) is not an index
    idx, body, ext = sn.parse_basename("v1.md")
    assert (idx, body, ext) == ("", "v1", ".md")


def test_letter_dash_index_is_capped_at_5_letters():
    # 'rev-1' / 'r-2' / 'v-1' all count; 'release-3.0' has 7 letters and does not.
    assert sn.parse_basename("rev-1.spec.md") == ("rev-1", "spec", ".md")
    assert sn.parse_basename("r-2.spec.md") == ("r-2", "spec", ".md")
    assert sn.parse_basename("v-1.spec.md") == ("v-1", "spec", ".md")
    assert sn.parse_basename("rev-3.0.1.md") == ("rev-3.0.1", "", ".md")
    # 7-letter 'release' does not match letter-dash
    assert sn.parse_basename("release-3.0.md") == ("", "release-3.0", ".md")


def test_pure_digit_index_supports_dotted_form():
    assert sn.parse_basename("001.三月开发需求说明.md") == \
        ("001", "三月开发需求说明", ".md")
    assert sn.parse_basename("12.x.md") == ("12", "x", ".md")
    # Per the script's own docstring, '1.2.需求.md' yields ('1.2', '需求', '.md')
    # because the digit-index regex is \d+(\.\d+)*, greedy on the dot chain.
    assert sn.parse_basename("1.2.需求.md") == ("1.2", "需求", ".md")
    assert sn.parse_basename("99.99.99.md") == ("99.99.99", "", ".md")
    # index-only file: '42.md' -> index='42', body='', ext='.md'
    assert sn.parse_basename("42.md") == ("42", "", ".md")


def test_no_index_when_basename_does_not_start_with_a_matching_pattern():
    assert sn.parse_basename("三月开发需求.md") == ("", "三月开发需求", ".md")
    assert sn.parse_basename("README") == ("", "README", "")
    assert sn.parse_basename("spec.md") == ("", "spec", ".md")


# --- parse_basename extension rules -----------------------------------

def test_ext_is_only_the_last_dot_segment():
    # .tar.gz -> ext=.gz, body=.tar
    assert sn.parse_basename("name.tar.gz") == ("", "name.tar", ".gz")
    # .md.bak -> ext=.bak, body=name.md
    assert sn.parse_basename("name.md.bak") == ("", "name.md", ".bak")


def test_leading_dot_files_have_no_extension():
    # .gitkeep: index='', body='.gitkeep', ext=''
    assert sn.parse_basename(".gitkeep") == ("", ".gitkeep", "")


def test_basename_with_no_dot_has_no_extension():
    assert sn.parse_basename("README") == ("", "README", "")
    assert sn.parse_basename("003") == ("003", "", "")


# --- generate end-to-end ----------------------------------------------

def test_generate_basic_md_file():
    assert sn.generate("001.三月开发需求说明.md", "pm") == \
        "001.pm.三月开发需求说明.md"


def test_generate_no_index_no_ext():
    assert sn.generate("三月开发需求", "pm") == "pm.三月开发需求"


def test_generate_hidden_file_yields_double_dot():
    # SKILL.md: "Output becomes '.{stage}.gitkeep' — double dot allowed by spec."
    assert sn.generate(".gitkeep", "pm") == "pm..gitkeep"


def test_generate_strips_directory_prefix():
    # generate uses Path(source).name internally — directory prefixes are dropped.
    assert sn.generate("docs/001.x.md", "pm") == "001.pm.x.md"
    assert sn.generate(r"C:\foo\001.x.md", "pm") == "001.pm.x.md"


def test_generate_with_index_only_file():
    # '42.md' parses as index='42', body='', ext='.md'.
    # apply_stage layout: index + '.' + stage + ext = '42.pm.md'
    assert sn.generate("42.md", "pm") == "42.pm.md"


# --- apply_stage layout edge cases ------------------------------------

def test_apply_stage_no_index_no_body_yields_stage_plus_ext():
    # Edge: ('', '', '.md', 'pm') -> 'pm.md'
    assert sn.apply_stage("", "", ".md", "pm") == "pm.md"


def test_apply_stage_hidden_body_keeps_leading_dot():
    # (.gitkeep body) -> double dot is part of the spec
    assert sn.apply_stage("", ".gitkeep", "", "pm") == "pm..gitkeep"


# --- next_available collision suffix ----------------------------------

def test_next_available_returns_input_when_no_collision(tmp_path):
    p = tmp_path / "001.pm.x.md"
    assert sn.next_available(p) == p


def test_next_available_appends_increments_before_extension(tmp_path):
    p = tmp_path / "001.pm.x.md"
    p.touch()
    candidate = sn.next_available(p)
    assert candidate == tmp_path / "001.pm.x (1).md"


def test_next_available_skips_already_taken_increments(tmp_path):
    p = tmp_path / "001.pm.x.md"
    p.touch()
    (tmp_path / "001.pm.x (1).md").touch()
    candidate = sn.next_available(p)
    assert candidate == tmp_path / "001.pm.x (2).md"


def test_next_available_uses_pathlib_suffix_not_manual_extraction(tmp_path):
    # pathlib's `.stem`/`.suffix` handles ".tar.gz" correctly: stem='a.tar',
    # suffix='.gz'. The collision suffix must be inserted before '.gz'.
    p = tmp_path / "001.pm.a.tar.gz"
    p.touch()
    candidate = sn.next_available(p)
    assert candidate == tmp_path / "001.pm.a.tar (1).gz"


# --- CLI smoke: --list-stages prints the closed list ------------------

def test_cli_list_stages_outputs_canonical_six():
    import subprocess
    script = SCRIPT_DIR / "stage_naming.py"
    result = subprocess.run(
        [sys.executable, str(script), "--list-stages"],
        capture_output=True, text=True, check=True,
    )
    assert result.stdout.strip().splitlines() == list(sn.STAGE_TAGS)


def test_cli_rejects_unknown_stage_with_exit_code_1():
    import subprocess
    script = SCRIPT_DIR / "stage_naming.py"
    result = subprocess.run(
        [sys.executable, str(script), "001.x.md", "release"],
        capture_output=True, text=True,
    )
    assert result.returncode == 1
    assert "unknown stage tag 'release'" in result.stderr

"""Tests for plan-doc-sequence.

Exercises the script's functions and CLI entry point directly (no subprocess),
capturing stdout via pytest's capsys fixture. This avoids the Codex sandbox's
subprocess handle-inheritance restriction on Windows (subprocess.Popen raises
`OSError: [WinError 6] 句柄无效` in this environment) while testing the same
behavior. The script is a pure-Python module with an `if __name__ == "__main__"`
guard, so importing it and calling its functions is equivalent to running it
as a subprocess for assertion purposes.
"""

import sys
from pathlib import Path

import pytest

# Make the script importable. The script lives at
# plan-doc-sequence/scripts/plan_doc_sequence.py. We add the scripts dir
# to sys.path so `import plan_doc_sequence` resolves to our local module
# rather than anything installed system-wide.
SCRIPT_DIR = Path(__file__).parent.parent / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))

import plan_doc_sequence as pds  # noqa: E402


# --- Pure-function tests (no I/O) ---


def test_default_sequence_emits_eight_files_in_order():
    """The user's canonical example: feat04动态改写 / 20260707 -> 8 filenames,
    in workflow order. This is the single most important test — it pins the
    full shape of the output and the SEQUENCE table at once.

    `generate_sequence` returns a list of
    (index, stage, filename, meaning, phase) tuples; we extract column 2
    (filename) for comparison.
    """
    seq = pds.generate_sequence("20260707", "feat04动态改写")
    filenames = [row[2] for row in seq]
    assert len(filenames) == 8, (
        f"expected 8 rows, got {len(filenames)}: {filenames!r}"
    )
    expected = [
        "001.20260707.feat04动态改写.md",
        "002.pm.20260707.feat04动态改写.md",
        "003.dev.20260707.feat04动态改写.md",
        "004.plan.20260707.feat04动态改写.md",
        "005.case.20260707.feat04动态改写.md",
        "006.impl.20260707.feat04动态改写.md",
        "007.audit.20260707.feat04动态改写.md",
        "008.impl-note.20260707.feat04动态改写.md",
    ]
    assert filenames == expected, (
        f"sequence drift.\n  expected: {expected!r}\n  got:      {filenames!r}"
    )


def test_index_001_has_no_stage_tag():
    """Index 001 is the root requirement — no stage tag, just date.feat.md.
    Pin this separately because it's the most common drift point: agents
    add a `.root.` or `.requirement.` tag they think 'looks right'."""
    seq = pds.generate_sequence("20260707", "feat04动态改写")
    first_filename = seq[0][2]
    # Strip .md, then split by '.'. Should yield exactly 3 parts:
    # 001, 20260707, feat04动态改写.
    parts = first_filename.removesuffix(".md").split(".")
    assert len(parts) == 3, (
        f"expected 3 parts (index, date, feat), got {len(parts)}: {parts!r}. "
        f"Index 001 must NOT have a stage tag."
    )
    assert parts[0] == "001"
    assert parts[1] == "20260707"
    assert parts[2] == "feat04动态改写"


def test_impl_note_is_single_tag_at_index_008():
    """The 8th line is `008.impl-note.<date>.<feat>.md` — not
    `009.impl.note...md`. This pins TWO things at once: the index
    (008, not 009) and the tag shape (impl-note as one tag, not two)."""
    seq = pds.generate_sequence("20260707", "feat04动态改写")
    last_filename = seq[-1][2]
    assert last_filename == "008.impl-note.20260707.feat04动态改写.md", (
        f"got: {last_filename!r}. impl-note must be a single tag at "
        f"index 008, not split into impl.note and not moved to 009."
    )
    # Belt-and-suspenders: the tag must not have been split into 'impl.note'.
    assert "impl.note" not in last_filename, (
        f"impl-note must not be split into impl.note: {last_filename!r}"
    )
    # And the count of dot-separated parts (excluding .md) must be exactly 4:
    # 008, impl-note, 20260707, feat04动态改写. Anything else means a tag was
    # added, removed, or split.
    parts = last_filename.removesuffix(".md").split(".")
    assert len(parts) == 4, (
        f"expected 4 parts at index 008 (index, stage, date, feat), "
        f"got {len(parts)}: {parts!r}"
    )


def test_invalid_date_rejected():
    """--date must be exactly 8 digits. Separators, wrong length, and
    non-digit content all raise ValueError with a clear message."""
    bad_dates = (
        "2026-07-07",   # ISO with dashes
        "2026/07/07",   # slashed
        "2026070",      # 7 digits
        "202607077",    # 9 digits
        "abcd1234",     # 8 chars but not all digits
        "",             # empty
    )
    for bad in bad_dates:
        with pytest.raises(ValueError, match="invalid --date"):
            pds.generate_sequence(bad, "feat04")


def test_invalid_feat_rejected():
    """--feat must be non-empty, with no path separators, no whitespace,
    and not a directory reference. All of these raise ValueError."""
    bad_feats = (
        "",           # empty
        "feat/04",    # forward slash
        "feat\\04",   # backslash
        "feat 04",    # space
        "feat\t04",   # tab
        ".",          # current dir
        "..",         # parent dir
    )
    for bad in bad_feats:
        with pytest.raises(ValueError, match="invalid --feat"):
            pds.generate_sequence("20260707", bad)


# --- CLI tests (use capsys + monkeypatch) ---


def test_list_sequence_prints_table_with_all_eight_entries(monkeypatch, capsys):
    """--list-sequence prints a table containing all 8 stage tags and all
    3 phase labels. This is the agent's reference for 'what's the canonical
    sequence' — if any entry is missing from this output, the agent will
    silently produce incomplete plans."""
    monkeypatch.setattr(sys, "argv", ["plan_doc_sequence.py", "--list-sequence"])
    rc = pds.main()
    assert rc == 0
    out = capsys.readouterr().out
    # All 8 stage tokens (root + 7 named) must appear.
    expected_tokens = (
        "(root)", "pm", "dev", "plan", "case", "impl", "audit", "impl-note",
    )
    for token in expected_tokens:
        assert token in out, (
            f"expected token {token!r} in --list-sequence output, got:\n{out}"
        )
    # All 3 phase labels (Chinese) must appear.
    for phase in ("计划", "实施", "实施后"):
        assert phase in out, (
            f"expected phase {phase!r} in --list-sequence output, got:\n{out}"
        )
    # The table must have exactly 8 data rows (header + sep + 8 rows = 10 lines).
    lines = out.strip().splitlines()
    assert len(lines) == 10, (
        f"expected 10 lines (header + separator + 8 rows), got {len(lines)}"
    )


def test_cli_returns_one_with_stderr_message_on_validation_error(
    monkeypatch, capsys
):
    """End-to-end: passing a bad --date through the CLI returns exit 1
    and writes the validation message to stderr. Pins the main() error
    path that the script's pure-function tests don't reach."""
    monkeypatch.setattr(
        sys, "argv",
        ["plan_doc_sequence.py", "--feat", "feat04", "--date", "2026-07-07"],
    )
    rc = pds.main()
    assert rc == 1
    captured = capsys.readouterr()
    assert captured.out == "", (
        f"expected empty stdout on validation error, got: {captured.out!r}"
    )
    assert "invalid --date" in captured.err, (
        f"expected 'invalid --date' in stderr, got: {captured.err!r}"
    )


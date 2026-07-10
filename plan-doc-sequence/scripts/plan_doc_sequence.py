#!/usr/bin/env python3
"""
plan-doc-sequence: generate the canonical 8-document planning sequence
for a new feature/requirement.

Usage:
    python plan_doc_sequence.py --feat FEATURE --date YYYYMMDD
    python plan_doc_sequence.py --list-sequence

Output: 8 filenames, one per line, in workflow order:
  001.{date}.{feat-name}.md              # 原始需求 (no stage tag)
  002.pm.{date}.{feat-name}.md           # 需求梳理
  003.dev.{date}.{feat-name}.md          # 概要设计
  004.plan.{date}.{feat-name}.md         # 详细设计
  005.case.{date}.{feat-name}.md         # 测试用例
  006.impl.{date}.{feat-name}.md         # 实施
  007.audit.{date}.{feat-name}.md        # 实施后纠偏总结
  008.impl-note.{date}.{feat-name}.md    # 实施总结文档

Rules enforced (must match the SKILL.md spec):
  - The 8-entry SEQUENCE table is closed; new stages require editing it
    AND the SKILL.md table in the same commit.
  - Index 001 has NO stage tag (it is the root requirement, not a
    derivative). All other indices have a stage tag from the closed list.
  - `impl-note` is a single two-segment tag, not two tags.
  - Indices are 3-digit zero-padded (001, not 1).
  - Date is exactly 8 digits (YYYYMMDD); no separators.
  - Feat name is non-empty, has no path separators (/, \\), no whitespace.

Returns the generated filenames on stdout, exit code 0 on success, 1 on
spec violation. 002.pm is the no-assumption step; the script cannot
enforce the "do not invent answers" rule — that is the agent's job.
See SKILL.md "002.pm: no-assumption rule" for the full contract.
"""

import argparse
import re
import sys

# Canonical 8-entry sequence. Order is workflow order; index is the
# file's position in the sequence. stage is None for the root
# requirement. The (stage, meaning, phase) tuple is closed; new entries
# require editing this list AND the SKILL.md table in the same commit.
SEQUENCE = (
    # (index, stage,       meaning,            阶段)
    (1,     None,         "原始需求",          "计划"),
    (2,     "pm",         "需求梳理",          "计划"),
    (3,     "dev",        "概要设计",          "计划"),
    (4,     "plan",       "详细设计",          "计划"),
    (5,     "case",       "测试用例",          "计划"),
    (6,     "impl",       "实施",              "实施"),
    (7,     "audit",      "实施后纠偏总结",    "实施后"),
    (8,     "impl-note",  "实施总结文档",      "实施后"),
)

# Date format: exactly 8 digits, no separators (YYYYMMDD).
_DATE_RE = re.compile(r"^\d{8}$")
# Feat name: non-empty, no path separators, no whitespace. Allow CJK,
# ASCII letters, digits, dash, underscore, dot.
_FEATURE_RE = re.compile(r"^[\w.\-一-鿿]+$")


def validate_date(date: str) -> None:
    """Reject anything that is not exactly 8 digits (YYYYMMDD)."""
    if not _DATE_RE.match(date):
        raise ValueError(
            f"invalid --date {date!r}: expected exactly 8 digits "
            f"(YYYYMMDD, e.g. 20260707). Separators like '-' or '/' are "
            f"not accepted."
        )


def validate_feat(feat: str) -> None:
    """Reject empty, path-bearing, whitespace-bearing, or weird feat names."""
    if not feat:
        raise ValueError("invalid --feat: must be non-empty")
    if "/" in feat or "\\" in feat:
        raise ValueError(
            f"invalid --feat {feat!r}: path separators ('/' or '\\\\') "
            f"are not allowed. This skill emits filenames only, not paths."
        )
    if any(c.isspace() for c in feat):
        raise ValueError(
            f"invalid --feat {feat!r}: whitespace is not allowed in "
            f"feat names."
        )
    if feat in (".", ".."):
        raise ValueError(
            f"invalid --feat {feat!r}: must not be a directory reference."
        )
    if not _FEATURE_RE.match(feat):
        raise ValueError(
            f"invalid --feat {feat!r}: contains disallowed characters. "
            f"Allowed: letters, digits, dash, underscore, dot, CJK."
        )


def build_filename(index: int, stage: str | None, date: str, feat: str) -> str:
    """Build a single filename from its parts.

    Layout: {index:03d}{stage?}.{date}.{feat}.md
    Where {stage?} is omitted entirely for index 001 (root).
    """
    parts = [f"{index:03d}"]
    if stage is not None:
        parts.append(stage)
    parts.append(date)
    parts.append(feat)
    return ".".join(parts) + ".md"


def generate_sequence(date: str, feat: str) -> list[tuple[int, str | None, str, str, str]]:
    """Return the full 8-entry sequence as a list of
    (index, stage, filename, meaning, phase) tuples."""
    validate_date(date)
    validate_feat(feat)
    return [
        (idx, stage, build_filename(idx, stage, date, feat), meaning, phase)
        for (idx, stage, meaning, phase) in SEQUENCE
    ]


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Generate the canonical 8-document planning sequence for a "
            "feature/requirement."
        )
    )
    parser.add_argument(
        "--feat",
        help=(
            "Feature name (e.g. feat04动态改写). Non-empty, no path "
            "separators, no whitespace."
        ),
    )
    parser.add_argument(
        "--date",
        help=(
            "Date in YYYYMMDD (e.g. 20260707). Exactly 8 digits, no "
            "separators."
        ),
    )
    parser.add_argument(
        "--list-sequence",
        action="store_true",
        help="Print the canonical 8-entry sequence as a table and exit.",
    )
    args = parser.parse_args()

    if args.list_sequence:
        # Print the canonical sequence as a table.
        print(f"{'Index':<6} {'Stage':<11} {'阶段':<6} {'含义'}")
        print(f"{'-'*6} {'-'*11} {'-'*6} {'-'*16}")
        for idx, stage, meaning, phase in SEQUENCE:
            tag = stage if stage else "(root)"
            print(f"{idx:03d}    {tag:<11} {phase:<6} {meaning}")
        return 0

    if not args.feat or not args.date:
        parser.error(
            "--feat and --date are required (or use --list-sequence)"
        )

    try:
        seq = generate_sequence(args.date, args.feat)
    except ValueError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1

    for _idx, _stage, filename, _meaning, _phase in seq:
        print(filename)
    return 0


if __name__ == "__main__":
    sys.exit(main())


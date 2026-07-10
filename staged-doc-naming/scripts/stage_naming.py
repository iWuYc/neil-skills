#!/usr/bin/env python3
"""
staged-doc-naming: convert a source filename into a stage-tagged filename.

Source: <index?>.<name-body><.ext?>
Output: <index?>.{stage}.<name-body><.ext>

Usage:
    python stage_naming.py <source-filename> <stage> [<stage> ...]
    python stage_naming.py --exists-check <output-path>
    python stage_naming.py --list-stages

Rules enforced (must match the SKILL.md spec):
  - The "index" is the leading run of digits at the start of the basename,
    before the first dot. Empty if missing. Pure digits only — "v1.2" has
    NO index.
  - The "stage tag" is inserted between the index and the name body.
  - The "name body" is the basename minus the index prefix and minus the
    last extension. The last extension is preserved unchanged.
  - Multi-dot basenames like "a.b.md": index="a"? No — "a" is not pure
    digits, so there is no index. name-body="a.b", ext=".md".
  - Hidden files like ".gitkeep": no index, name-body=".gitkeep", ext="".
    Output becomes ".{stage}.gitkeep" — double dot allowed by spec.
  - "case.data" is a single two-segment stage tag; it must not be split.

Returns the generated filename on stdout, exit code 0 on success, 1 on
spec violation (unknown stage, missing args, etc.).
"""

import argparse
import os
import re
import sys
from pathlib import Path

# The 6 canonical stage tags. The first five are fixed English tokens;
# the last is a fixed Chinese token. Do NOT split "case.data" — it is one
# stage tag, not two.
STAGE_TAGS = ("pm", "dev", "plan", "case", "case.data", "实施纪要")

# Index patterns, tried in priority order. The FIRST match wins — never
# sum or combine. Each pattern is anchored at the start of the basename.
#
# 1. v<dot-numbers>: e.g. v1.2, v1.2.3, v0.0.1. Lowercase 'v' only.
#    Bare v1 / v12 (no dot) does NOT match — it falls through to letter-/
#    digits-only patterns and ends up as part of the name body.
# 2. <1-5 letters>-<numbers>: e.g. rev-1, r-2, v-1, rev-3.0.1. Letter
#    run length is capped at 5 to avoid matching arbitrary words like
#    'release'. The dot-separated variant (e.g. rev-3.0.1) is allowed.
#    Unlike the v-prefix pattern, letter-dash DOES NOT require a dot —
#    plain 'rev-1' / 'r-2' / 'v-1' count.
# 3. <pure-digits>[.digits...]: any leading run of digits optionally
#    followed by '.digits' segments. E.g. 001, 12, 1.2, 99.99.99. The
#    digits may be dot-separated; the first run anchors it.
_INDEX_RE = re.compile(
    r"^"
    r"(?:"
    r"(?P<v_index>v\d+(?:\.\d+)+)"            # v1.2, v1.2.3 (must be dotted)
    r"|(?P<letter_index>[A-Za-z]{1,5}-\d+(?:\.\d+)*)"  # rev-1, r-2, rev-3.0.1
    r"|(?P<digit_index>\d+(?:\.\d+)*)"        # 001, 12, 1.2
    r")"
)


def parse_basename(basename: str) -> tuple[str, str, str]:
    """Split a filename basename into (index, name_body, ext).

    - index: leading run of digits, '' if absent. Pure digits only.
    - name_body: the part between index and the LAST extension.
    - ext: the LAST extension starting at the last dot, including the dot,
      or '' if no dot is present.

    Examples:
      '001.三月开发需求说明.md' -> ('001', '三月开发需求说明', '.md')
      '三月开发需求.md'         -> ('',   '三月开发需求',       '.md')
      'name.md.bak'            -> ('',   'name.md',            '.bak')
      'name.tar.gz'            -> ('',   'name.tar',           '.gz')
      '.gitkeep'               -> ('',   '.gitkeep',           '')
      '7.feature设计.md'        -> ('7',  'feature设计',         '.md')
      'v1.2.spec.md'           -> ('',   'v1.2.spec',          '.md')  # 'v' is not digit
      '1.2.需求.md'            -> ('1',  '2.需求',              '.md')  # index = first digit run
      '99.api.dev.md'          -> ('99', 'api.dev',            '.md')
      '42.md'                  -> ('42', '',                   '.md')
      'README'                 -> ('',   'README',             '')
    """
    # Split into (head, ext) by the LAST dot only.
    if "." in basename:
        head, _, ext = basename.rpartition(".")
        ext = "." + ext
        # Hidden file: basename starts with '.' (e.g. '.gitkeep').
        # rpartition('.') on '.gitkeep' yields head='', ext='.gitkeep' —
        # that would treat the whole hidden name as an extension. Detect
        # this case by checking the original basename starts with '.',
        # then treat the whole thing as the body with no extension.
        if basename.startswith("."):
            head = basename
            ext = ""
    else:
        head, ext = basename, ""

    # Index: try v-prefix, letter-dash, then pure-digits at start of `head`.
    m = _INDEX_RE.match(head)
    if m:
        index = m.group(0)  # the entire matched prefix
        # Strip both the index AND the dot that separates it from the body.
        # e.g. head='001.三月开发需求说明' -> name_body='三月开发需求说明'
        # e.g. head='v1.2.spec.md' (already ext-split) but here head='v1.2.spec',
        #      index='v1.2', rest='.spec', name_body='spec'.
        rest = head[len(index):]
        name_body = rest[1:] if rest.startswith(".") else rest
    else:
        index = ""
        name_body = head

    return index, name_body, ext


def apply_stage(index: str, name_body: str, ext: str, stage: str) -> str:
    """Insert the stage tag between index and name body.

    Layout: {index}{sep}{stage}{sep}{name_body}{ext}
    Separator is '.' UNLESS name_body is empty (index-only file) — in that
    case there is no leading separator after index. Examples:
      ('001', 'x', '.md', 'pm') -> '001.pm.x.md'
      ('',    'x', '.md', 'pm') -> 'pm.x.md'
      ('7',   '',  '.md', 'pm') -> '7.pm.md'
      ('',    '',  '.md', 'pm') -> 'pm.md'
      ('', '.gitkeep', '',  'pm') -> 'pm..gitkeep'   (double dot allowed)
    """
    if stage not in STAGE_TAGS:
        raise ValueError(
            f"unknown stage tag '{stage}'. Allowed: {STAGE_TAGS}. "
            f"Add new stages to STAGE_TAGS first."
        )

    parts: list[str] = []
    if index:
        parts.append(index)
        parts.append(".")
    parts.append(stage)
    if name_body:
        parts.append(".")
        parts.append(name_body)
    parts.append(ext)
    return "".join(parts)


def generate(source_basename: str, stage: str) -> str:
    basename = Path(source_basename).name  # strip any directory prefix
    index, body, ext = parse_basename(basename)
    return apply_stage(index, body, ext, stage)


def next_available(path: Path) -> Path:
    """If `path` already exists on disk, append (1), (2), ... before the
    extension. Caller passes a path that includes the directory."""
    if not path.exists():
        return path
    stem = path.stem
    suffix = path.suffix
    parent = path.parent
    i = 1
    while True:
        candidate = parent / f"{stem} ({i}){suffix}"
        if not candidate.exists():
            return candidate
        i += 1


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate a stage-tagged filename from a source filename."
    )
    parser.add_argument(
        "--exists-check",
        metavar="PATH",
        help="If PATH exists, suggest next available name (stam '(1)' etc.).",
    )
    parser.add_argument(
        "--list-stages",
        action="store_true",
        help="Print the allowed stage tags and exit.",
    )
    # Note: positional `source` and `stages` are still required by argparse
    # even when --list-stages is given. We work around that by making them
    # optional and validating manually below.
    parser.add_argument("source", nargs="?", default=None, help=argparse.SUPPRESS)
    parser.add_argument(
        "stages", nargs="*", default=[], help=argparse.SUPPRESS
    )
    args = parser.parse_args()

    if args.list_stages:
        for s in STAGE_TAGS:
            print(s)
        return 0

    if not args.source or not args.stages:
        # --exists-check and --list-stages don't need source/stages
        if not (args.exists_check or args.list_stages):
            parser.error("source and at least one stage are required (or use --list-stages / --exists-check)")

    if args.exists_check:
        p = Path(args.exists_check)
        if p.exists():
            print(str(next_available(p)))
            return 0
        print(str(p))
        return 0

    for stage in args.stages:
        try:
            print(generate(args.source, stage))
        except ValueError as e:
            print(f"ERROR: {e}", file=sys.stderr)
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
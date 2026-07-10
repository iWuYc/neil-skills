---
name: staged-doc-naming
description: Use when generating a stage-tagged filename from a source document — inserts a lifecycle stage token (pm / dev / plan / case / case.data / 实施纪要) between the source file's index prefix and name body. Index supports pure digits (001 / 12 / 1.2), v-prefix dotted versions (v1.2, v1.2.3 — v1 alone is NOT an index), and 1-5 letter dash versions (rev-1, r-2, v-1, rev-3.0.1). Triggered when the user says "生成 pm/dev/plan/case/case.data/实施纪要 文档" or "把这个需求文档转成 xx 阶段", or when batch-generating project skeletons, knowledge-base files, or implementation notes from a source document.
---

# Staged Document Naming

Insert a fixed lifecycle-stage token between a source file's index prefix and its name body, preserving the original extension. The result is a derivative file name that signals which lifecycle phase the document is in, while keeping it visually paired with its source.

## When to Use

- User asks to generate a derivative document for a specific lifecycle stage: `pm` / `dev` / `plan` / `case` / `case.data` / `实施纪要`
- Batch-generating project skeletons or knowledge-base entries from a source file
- Translating a plan/spec into implementation files at named phases
- User says "把这份需求文档转成 dev 阶段"、"生成 case.data 测试数据"、"做实施纪要"

**Do NOT use this skill** when:

- The output is not a derivative file (i.e. a brand-new file unrelated to a source)
- The user wants to rename an existing file without changing its lifecycle stage
- The user asks for a stage that is not in the canonical list AND has not registered it (see "Extending the stage list" below)

## The Six Canonical Stages

| Stage token | Meaning |
|---|---|
| `pm` | 需求梳理 (requirements grooming) |
| `dev` | 开发设计 (development design) |
| `plan` | 开发计划 (development plan) |
| `case` | 测试计划 (test plan) |
| `case.data` | 测试数据 (test data) — **single tag, do not split** |
| `实施纪要` | 开发实施后 (post-implementation notes) |

The list is **closed by default**. If a user requests a stage not on this list (`review`, `release`, etc.), **stop and ask** — do not invent a new tag, do not pick the closest one, do not proceed with an unregistered stage. New tags must be added to this table in the SKILL.md AND to `STAGE_TAGS` in the script.

## Naming Algorithm

A source basename `B` is split into three parts, in this exact order:

```
B = <index?>.<name-body><ext?>
```

1. **`<index?>`** — a leading prefix that matches **one** of these patterns, in priority order:
   - **`v<dot-numbers>`** — the letter `v` (lowercase) followed by dot-separated digits, e.g. `v1.2`, `v1.2.3`, `v0.0.1`. The `v` is part of the index and **must be preserved** in the output. Bare `v1` / `v12` (no dot) does **not** count — that `v1` is part of the name body. **This is the only pattern that requires a dot.**
   - **`<1-5 letters>-<numbers>`** — 1 to 5 ASCII letters, then `-`, then a digit run optionally followed by `.digits` segments. E.g. `rev-1`, `r-2`, `v-1`, `rev-3.0.1`, `v-1.0.1`. The whole token including the letter(s) and the dash is the index. Letter run length is capped at 5 to avoid matching arbitrary words like `release-3.0` (which has 7 letters and falls through to the name body).
   - **`<pure-digits>[.digits...]`** — leading run of pure digits optionally followed by `.digits` segments, e.g. `001`, `12`, `0001`, `1.2`, `99.99.99`. The first run anchors it.
   - If none of the above match, the index is empty.

   The index is the **first** match — never sum two prefixes. `1.2.需求.md` → index `1.2`, body `需求`, ext `.md`. (`v` is a special-case rule on top of the digit rule, not a replacement for it.)
2. **`<ext?>`** — the **last** extension (the substring starting at the last `.`, including the dot). `.md`, `.bak`, `.tar.gz`'s last `.gz`. Empty if no `.` is present. **Do not split multi-dot basenames by every dot** — only the last extension is removed.
3. **`<name-body>`** — everything between the index and the last extension. **Preserve verbatim.** Do not add, remove, or rewrite characters. The example `三月开发需求.md` → `pm.三月开发需求.md` does **not** imply "add 说明" — that was a coincidence in the user's actual file. Never silently suffix the body with extra words.

The output filename is:

```
<index?>{sep}{stage}{sep}<name-body><ext?>
```

where `{sep}` is `.` **unless** the part to its left is empty (i.e. no index → no leading separator; empty name-body → no middle separator). Examples:

| Source | Stage | Output |
|---|---|---|
| `001.三月开发需求说明.md` | `pm` | `001.pm.三月开发需求说明.md` |
| `三月开发需求.md` | `pm` | `pm.三月开发需求.md` |
| `7.feature设计.md` | `dev` | `7.dev.feature设计.md` |
| `42.md` | `case` | `42.case.md` |
| `README` | `plan` | `plan.README` |
| `.gitkeep` | `pm` | `pm..gitkeep` *(double dot allowed)* |
| `name.md.bak` | `dev` | `dev.name.md.bak` |
| `1.2.需求.md` | `pm` | `1.2.pm.需求.md` *(index = `1.2`, not `1`)* |
| `v1.2.spec.md` | `pm` | `v1.2.pm.spec.md` *(v preserved)* |
| `v1.2.3.deep.md` | `pm` | `v1.2.3.pm.deep.md` |
| `v1.x.md` | `pm` | `pm.v1.x.md` *(v1 without dot is NOT an index)* |
| `v-1.2.api.md` | `pm` | `v-1.2.pm.api.md` |
| `v-1.api.md` | `pm` | `v-1.pm.api.md` *(v-1 is a letter-dash index; only v-prefix needs the dot)* |
| `rev-1.changelog.md` | `pm` | `rev-1.pm.changelog.md` |
| `r-2.bug.md` | `pm` | `r-2.pm.bug.md` |
| `release-3.0.notes.md` | `pm` | `pm.release-3.0.notes.md` *(letter run capped at 5)* |

## Path Is Not Part of This Skill

The skill produces a **filename**, not a path. The caller decides where to write it. Strip any directory prefix from the source before applying the algorithm — only the basename matters. If a caller passes `a/b/c.md`, treat it as `c.md`.

## Same-Name Collision

If the target file already exists on disk at the planned write path, **append `(1)`, `(2)`, …** before the extension. Do **not** overwrite, do **not** error out, do **not** ask. Use the `--exists-check` flag of the bundled script to resolve the next available name.

```
001.pm.x.md exists → next available is 001.pm.x (1).md
```

## Calling the Bundled Script

A Python 3 reference implementation lives at `scripts/stage_naming.py` in this skill's directory. It enforces every rule above and is the recommended entry point — agents that hand-roll filenames drift under pressure.

```bash
# Single stage
python scripts/stage_naming.py "001.三月开发需求说明.md" pm
# -> 001.pm.三月开发需求说明.md

# Multiple stages at once
python scripts/stage_naming.py "001.三月开发需求说明.md" pm dev plan case case.data 实施纪要

# Resolve collision
python scripts/stage_naming.py --exists-check "/docs/001.pm.x.md"
# -> /docs/001.pm.x (1).md  (only if the input path exists)

# Print canonical stages
python scripts/stage_naming.py --list-stages
```

**Why prefer the script over hand-rolled naming:** the RED-phase baseline test (see `docs/baseline.md` if present) showed agents reliably make these specific errors under pressure:

- Treating `.bak` / `.tar.gz` as if the *first* extension is the real one
- Inventing new stage tags instead of refusing unknown ones
- Stripping or rewriting the name body (the "add 说明" rationalization)
- Confusing `1.2.x.md`'s index (it's `1`, not `1.2.`)
- Treating `.gitkeep` as a fatal edge case rather than a normal empty-body case

The script encodes all of these decisions. Don't bypass it unless the caller has a specific reason and has read this section.

## Red Flags — STOP and Ask the User

- User asks for a stage that is **not** in the table above and is **not** already registered → refuse, show the table, ask the user to register or pick an existing stage.
- Source basename contains characters outside `[A-Za-z0-9._-]` and Chinese → warn, but proceed (Chinese is legitimate for this user).
- Source has no name body and no extension (e.g. literal `dev`) → output is `{stage}.dev`. Acceptable; do not error.
- User asks to also move / copy / delete the file → **out of scope for this skill.** Produce the new filename only; let the caller handle I/O.

## Extending the Stage List

If a new stage genuinely needs to be added (e.g. `review`, `release`):

1. Add the token to the table in this SKILL.md, with a one-line Chinese meaning.
2. Add the token to `STAGE_TAGS` in `scripts/stage_naming.py`.
3. Update the description's `pm / dev / plan / case / case.data / 实施纪要` list to include it.
4. Re-run the baseline + green test cases (see `docs/baseline.md`).

**Never** add a stage ad-hoc inside a single conversation without committing the change to this skill.
---
name: plan-doc-sequence
description: Use when planning a new feature/requirement and the user wants the canonical 8-document planning sequence generated in one shot — 001 原始需求, 002-005 计划阶段 (pm/dev/plan/case), 006 实施 (impl), 007-008 实施后 (audit/impl-note). Output filenames follow the `{index}.{stage?}.{date}.{feat-name}.md` shape with 3-digit zero-padded indices. Triggered when the user says "我要规划一个需求 / feat / 特性", "按流程生成规划文档", "开一个新需求的规划文档", "把这个 feat 的 8 个文档列出来 / 生成出来", or describes a planning workflow that walks PM → DEV → 计划 → 用例 → 实施 → 审计 → 复盘.
---

# Plan Document Sequence

Generate the canonical 8-document planning sequence for a new feature/requirement.
The script is the single source of truth — agents under pressure will skip steps,
forget to zero-pad indices, invent their own stage tags, drop the date/feat-name, or
**fill in the PM doc with their own assumptions instead of going back to the user to
clarify open questions**. This skill encodes the sequence so the agent cannot drift,
and pins the 002.pm "no assumptions" rule so the agent does not silently invent
requirements.

## When to Use

- User says "我要规划一个需求 / 一个新需求 / 一个 feat"
- User says "按流程生成规划文档 / 生成 8 个规划文档 / 一次性把规划文档全列出来"
- User says "开一个 feat04xxx 的规划" or names a feat/feature and wants planning artifacts
- User says "把这个需求转成 pm/dev/plan/case/impl/audit/impl-note" — for the FULL SEQUENCE of stages, not a single file

**Do NOT use this skill** when:

- The user only wants ONE stage tagged onto ONE existing file — that's `staged-doc-naming`.
- The user wants a partial sequence (e.g. only `pm` + `dev` + `plan`) — generate the full 8, the user discards the ones they don't need. Partial-sequence support is intentionally out of scope; see "Closed Sequence" below.
- The user wants to fill in CONTENT for the planning docs — this skill produces filenames; the agent fills the content per stage using the per-stage description in the closed sequence table.
- The user is documenting a retrospective or post-mortem (no planning happens; they want a different workflow).

## The Closed Sequence

The sequence is **closed**. Eight entries, in this exact order. New stages require editing
this table AND `SEQUENCE` in the script AND the frontmatter description in the same
commit. The agent must NOT add, remove, or reorder entries on its own.

| Index | Stage       | 阶段     | 含义                                                                |
|-------|-------------|----------|---------------------------------------------------------------------|
| 001   | (none)      | 计划     | 原始需求 (root requirement)                                          |
| 002   | `pm`        | 计划     | 需求梳理 (PM perspective — **澄清问题，禁止自作假设**)                |
| 003   | `dev`       | 计划     | 概要设计 (high-level design)                                         |
| 004   | `plan`      | 计划     | 详细设计 (detailed design)                                           |
| 005   | `case`      | 计划     | 测试用例 (test cases)                                                |
| 006   | `impl`      | 实施     | 实施 (using the plan file)                                           |
| 007   | `audit`     | 实施后   | 实施后纠偏总结 (post-impl audit)                                     |
| 008   | `impl-note` | 实施后   | 实施总结文档 (post-impl summary)                                     |

### Shape notes

- **Index 001 is the root** — it has NO stage tag. It is the original requirement as the
  user wrote it, not a derivative. Filename: `{date}.{feat-name}.md` (no stage slot).
- **阶段 is conceptual, not encoded in the filename.** "计划 / 实施 / 实施后" lives in this
  table and in the agent's mental model; the index alone tells the agent which stage a
  doc belongs to. The script does NOT add a phase prefix to the filename.
- **Stage tag `plan` means 详细设计**, not "开发计划". It is the detailed design doc that
  the implementation phase reads from. This is intentionally the same tag the existing
  `staged-doc-naming` skill uses, but the meaning is scoped narrower here.
- **Stage tag `case` means 测试用例**, not "测试计划". Same tag as `staged-doc-naming`,
  narrower meaning.
- **`impl-note` is a single two-segment tag.** Do NOT split it. This is the same
  convention `staged-doc-naming` uses for `case.data`.
- **The `impl` / `audit` / `impl-note` tags are private to this skill.** They are NOT in
  the `staged-doc-naming` `STAGE_TAGS` list and must not be added there. `audit` only
  makes sense inside this planning workflow; the generic naming skill stays generic.
- **On the example vs standard numbering.** The original example the user shared had a
  one-off `008.plan` (a revised plan produced mid-flight) and numbered impl-note as
  `009.impl-note`. That one-off `008.plan` is NOT part of the standard. In the standard
  sequence, impl-note is `008.impl-note`. If the user encounters a real mid-flight plan
  revision, they can create the extra file manually — the script always emits the 8
  standard entries.

### 002.pm: no-assumption rule

`002.pm` is the single highest-drift step. The agent's instinct is to read the original
requirement, notice some open questions, and **fill in plausible answers so the doc
looks complete**. This is the #1 source of 需求偏差 downstream — the dev/plan/case
docs then inherit the invented answer, the audit eventually catches it, and the user
has to rewind.

The correct behavior at 002.pm is:

1. List every open question the original requirement raises (boundary cases, error
   behavior, scope ambiguity, conflicting constraints, missing acceptance criteria).
2. Stop. Do NOT write answers into the PM doc.
3. Take the question list back to the user and resolve each one explicitly.
4. Only then write the PM doc, with the user's answers inlined.

If the user says "just write something, we'll fix it later" — refuse politely. Later
never comes, and the audit will surface the drift as 007.audit baggage. The script
cannot enforce this rule (it only emits filenames); the agent must enforce it by
stopping to ask.

## Naming Algorithm

Given `--feat FEATURE` and `--date YYYYMMDD`, the script emits eight filenames, one per
line, in workflow order. The format is:

```
{index}.{stage?}.{date}.{feat-name}.md
```

where:

- `{index}` is the 3-digit zero-padded index from the SEQUENCE table (e.g. `001`, `008`).
- `{stage?}` is the stage tag from the table, or **omitted entirely** for index 001.
  When omitted, the first `.` after the index is followed directly by `{date}`.
- `{date}` is the exact YYYYMMDD string passed to `--date`. The script does NOT compute
  today's date — the caller decides the date so multiple docs in the same planning round
  share a date. **Date must be exactly 8 digits**; `2026-07-07` and `2026/07/07` are
  rejected.
- `{feat-name}` is the exact string passed to `--feat`. The script does NOT slugify, add
  prefixes, or rewrite it. CJK characters are allowed. Path separators (`/`, `\`) are
  rejected — the script emits filenames only, never paths.
- All parts are joined with `.` and the extension `.md` is appended.

### Examples

For `--feat "feat04动态改写" --date 20260707`, the script emits:

```
001.20260707.feat04动态改写.md
002.pm.20260707.feat04动态改写.md
003.dev.20260707.feat04动态改写.md
004.plan.20260707.feat04动态改写.md
005.case.20260707.feat04动态改写.md
006.impl.20260707.feat04动态改写.md
007.audit.20260707.feat04动态改写.md
008.impl-note.20260707.feat04动态改写.md
```

For `--feat "feat12-支付重构" --date 20260801`, the script emits the same shape with
`feat12-支付重构` and `20260801` substituted in:

```
001.20260801.feat12-支付重构.md
002.pm.20260801.feat12-支付重构.md
003.dev.20260801.feat12-支付重构.md
004.plan.20260801.feat12-支付重构.md
005.case.20260801.feat12-支付重构.md
006.impl.20260801.feat12-支付重构.md
007.audit.20260801.feat12-支付重构.md
008.impl-note.20260801.feat12-支付重构.md
```

## Path Is Not Part of This Skill

The script produces **filenames**, not paths. The caller decides where to write them —
strip any directory prefix from the output before touching the filesystem. This matches
`staged-doc-naming` and keeps the script side-effect free.

If the caller wants the files actually created, they pipe the script's output to `touch`
(or any equivalent) and verify before committing. The script will NOT add a `--create`
flag in v1: writing to disk is a separate concern, and the script stays trivially
testable by checking stdout.

## Calling the Bundled Script

A Python 3 reference implementation lives at `scripts/plan_doc_sequence.py` in this
skill's directory. It enforces every rule above and is the recommended entry point.

```bash
# Generate the 8-file sequence for a feat
python plan-doc-sequence/scripts/plan_doc_sequence.py \
    --feat "feat04动态改写" \
    --date 20260707

# Pipe to touch to actually create the files in the current directory
python plan-doc-sequence/scripts/plan_doc_sequence.py \
    --feat "feat04动态改写" \
    --date 20260707 | xargs -I{} touch "{}"

# Print the canonical sequence as a table
python plan-doc-sequence/scripts/plan_doc_sequence.py --list-sequence
```

**Why prefer the script over hand-rolled listing:** the RED-phase baseline (see
`docs/baseline.md`) shows agents reliably make these specific errors under pressure:

- Dropping the 3-digit zero-padding (writing `1.` instead of `001.`)
- Forgetting that index 001 has NO stage tag (writing `001.root.20260707...md`)
- Splitting `impl-note` into two tags (`009.impl.note...md`)
- Using today's date instead of the caller's `--date`, breaking the "same date across
  the whole planning round" invariant
- Renumbering impl-note to `009` to mirror a one-off `008.plan` from a specific
  requirement, hard-coding that quirk into every future plan
- Inventing a 9th or 10th entry ("and then we ship it") — the sequence is closed
- **At 002.pm, inventing plausible-sounding answers to open questions instead of going
  back to the user.** The script only emits the filename; the no-assumption rule at
  002.pm is the agent's job, not the script's.

The script encodes every rule that can be encoded. The 002.pm no-assumption rule is
called out separately in "Shape notes → 002.pm: no-assumption rule" above because the
script cannot enforce it — only the agent can.

## Red Flags — STOP and Ask the User

- User wants a partial sequence (e.g. "just give me 002.pm and 003.dev") → out of scope;
  this skill always emits the full 8. The user can pick what they need from the output.
  If they really need partial, suggest `staged-doc-naming` for ad-hoc per-file tagging.
- User wants to add a new stage (e.g. `release`, `retro`) → the sequence is closed;
  refuse, point to the "Extending the Sequence" section, and ask the user to follow it.
- User wants a different cycle structure (3 cycles, or 0 cycles, or impl-note before
  audit) → out of scope; the 1-cycle / 8-entry shape is part of the contract.
- User asks for the script to write files to disk → out of scope in v1; point them to
  the `xargs touch` pipe example in the "Calling the Bundled Script" section.
- `--feat` is empty or contains `/` / `\` / other path separators → reject; the script
  refuses to emit anything with a directory prefix (per "Path Is Not Part of This Skill").
- `--date` is not exactly 8 digits → reject; the script does not accept `2026-07-07` or
  `2026/07/07`. The YYYYMMDD contract is part of the filename shape.
- User mentions a one-off `008.plan` for a specific requirement → acknowledge it as a
  one-off (per "On the example vs standard numbering" above), do NOT add it to the
  standard sequence. The user can create that file manually outside the skill.
- **At 002.pm, the user asks the agent to "just write something, we'll fix it later"**
  → refuse politely. The 002.pm no-assumption rule is non-negotiable; later never comes,
  and the drift will surface as 007.audit baggage. Take the question list back to the
  user instead.

## Extending the Sequence

If a new entry genuinely needs to be added (e.g. a 9th `release` step, or splitting the
`plan` stage into `plan-initial` and `plan-revised`):

1. Add the entry to the table in this SKILL.md with its phase and meaning.
2. Add the entry to `SEQUENCE` in `scripts/plan_doc_sequence.py`.
3. Update the frontmatter description's stage list to include the new tag.
4. Update the "8-document" wording in the frontmatter description and this file.
5. Re-run `pytest plan-doc-sequence/tests/ -v` to confirm no regression.
6. Commit all four changes in one commit.

**Never** add, remove, or reorder an entry ad-hoc inside a single conversation without
committing the change to this skill.


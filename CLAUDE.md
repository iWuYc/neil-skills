# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository Purpose

`neil-skills` is a curated collection of standalone [Claude Code skills](https://docs.claude.com/en/docs/claude-code/skills). Each skill is one self-contained subdirectory with a `SKILL.md` (frontmatter + behavior spec) plus any helper scripts and tests it ships with. The repo is a *spec + scripts* repo, not a runtime/library 鈥?there is no `setup.py`, no `package.json`, no application entry point.

Five skills are currently here, each as a top-level directory (Claude Code's standard skills layout — every directory under the repo root with a `SKILL.md` is a single skill). Layout is flat at the repo root, not nested under `plugins/neil-skills/` — the marketplace-bundle path described in the legacy "Adding a new skill" section below is no longer the convention.

- `git-commit-helper/` — enforces the `(Ai)` author marker and the strict commit-message format. Ships `scripts/ai_commit.py`.
- `staged-doc-naming/` — inserts lifecycle-stage tokens (`pm` / `dev` / `plan` / `case` / `case.data` / `实施纪要`) into derivative filenames. Ships `scripts/stage_naming.py`.
- `list-git-repos/` — scans a directory tree and prints git repos as a pruned ASCII tree. Ships `docs/baseline.md` and a pytest suite under `tests/`; `scripts/list_git_repos.py` is implemented; the 5-test pytest suite is GREEN.
- `plan-doc-sequence/` — generates the canonical 8-document planning sequence (001 raw + 002-005 pm/dev/plan/case + 006 impl + 007-008 audit/impl-note) in one shot. Ships `scripts/plan_doc_sequence.py` and a pytest suite under `tests/`.
- `analysis-api/` — **documentation-driven** Java Spring Boot multi-module monorepo REST API call-chain analyzer. No `scripts/`, no `tests/`; ships four reference files under `references/` (`subagent-prompts.md`, `provider-index.md`, `report-template.md`, `case-study-2026-07-13-label-sync.md`) plus a behavior spec in `SKILL.md`.

The user-facing index of skills lives in [`README.md`](README.md). When you add or change a skill, update that file in the same change.

## Common Commands

### Run tests

```bash
pytest                                              # all tests in the repo (root pytest.ini scopes testpaths)
pytest list-git-repos/tests/ -v                     # one skill's suite
pytest list-git-repos/tests/test_list_git_repos.py::test_worktree_link_file_not_misclassified_as_repo -v
```

Root [`pytest.ini`](pytest.ini) sets `testpaths = git-commit-helper/tests list-git-repos/tests plan-doc-sequence/tests staged-doc-naming/tests`. Each skill's `SKILL.md` is the source of truth for that skill's behavior 鈥?read it before touching anything in its directory.

### Run a skill's script directly

```bash
python staged-doc-naming/scripts/stage_naming.py "001.涓夋湀寮€鍙戦渶姹傝鏄?md" pm
python staged-doc-naming/scripts/stage_naming.py --list-stages
python staged-doc-naming/scripts/stage_naming.py --exists-check "/path/to/001.pm.x.md"

python git-commit-helper/scripts/ai_commit.py "feat(feature/login): 鏂板鐧诲綍鍔熻兘" \
    --feat-name "鐧诲綍鍔熻兘" \
    --body "- 鏂板 src/auth/login.ts锛屾牎楠岀敤鎴峰悕鏄惁瀛樺湪
- 鏂板 src/auth/password.ts锛屾牎楠岀櫥褰曞瘑鐮佹槸鍚︽纭?

python git-commit-helper/scripts/ai_commit.py --message-file MSG.txt
```

No build step. No linter configured. No CI workflow. "Linting" happens by reading the skill's `SKILL.md` against its script 鈥?the script is the executable form of the spec.

## Architecture: Skill Directory Layout

Every skill follows the same skeleton (see `staged-doc-naming/` as the canonical reference and `docs/superpowers/specs/2026-07-02-list-git-repos-design.md` 搂8 for the documented convention):

```
<skill-name>/
  SKILL.md          # REQUIRED 鈥?YAML frontmatter (name, description) + behavior spec
  scripts/          # Optional 鈥?bundled executables (Python 3 stdlib preferred)
  docs/             # Optional 鈥?design notes, RED-phase baseline records
  tests/            # Optional 鈥?pytest suites (one file per skill, real-fs fixtures)
```

`SKILL.md` frontmatter is parsed by Claude Code's skill loader 鈥?the `description` field is the *trigger contract* (zh-CN trigger phrases in this repo). Trigger phrases must be concrete user utterances, not abstract descriptions; the `list-git-repos` design spec 搂3 lists the exact trigger phrasing rule.

Each script is a **single source of truth** that the agent invokes instead of hand-rolling the behavior. The `SKILL.md` documents *when* and *why*; the script enforces *how*. This split exists because the `git-commit-helper` and `staged-doc-naming` skills were created after observing agents drift under pressure 鈥?the script is the drift-defense.

## Architecture: `git-commit-helper`

The script is the only sanctioned entry point for AI commits. The rules (`SKILL.md` "The Six Hard Rules") are enforced in code, not just documented:

- `HEADER_RE` validates `{type}({branchName}): {desc}` 鈥?`()` is the branch-name slot, not a Conventional Commits scope.
- `BULLET_RE` requires Chinese `- ` body lines; no diff-size exemption.
- `PLACEHOLDER_RE` rejects `featName: N/A` style placeholders.
- `ISSUE_IN_SUBJECT_RE` rejects ticket codes stuffed into subject parens.
- Identity is read with `git config --local user.name` first, falling back to `--global` 鈥?bare `git config` is explicitly forbidden because it silently traverses scopes.
- `--author="${NAME} (Ai) <${EMAIL}>"` is the only way to set the author; `-c user.name=...` is rejected because it overrides committer and may leak into config.
- The script enforces "no push" by simply not having any push code path 鈥?push is a separate concern handled by the harness, not this skill.

Hand-rolled `git commit` is permitted only as a fallback pattern shown in the SKILL.md, and only when the script is unavailable.

## Architecture: `staged-doc-naming`

Single Python 3 script, no I/O 鈥?it produces *filenames*, never touches disk. The caller decides the write path. The algorithm (see `SKILL.md` "Naming Algorithm") splits the source basename into three parts in fixed priority order:

1. `<index?>` 鈥?leading prefix matched by `_INDEX_RE`. Three sub-patterns tried in order: `v<dot-numbers>` (must be dotted; bare `v1` is NOT an index), `<1-5 letters>-<numbers>`, then `<pure-digits>[.digits...]`. The first match wins 鈥?never sum.
2. `<ext?>` 鈥?only the *last* `.` segment is treated as an extension. `.tar.gz` 鈫?ext `.gz`, body `.tar`. `.gitkeep` 鈫?no ext (leading-dot special case).
3. `<name-body>` 鈥?everything between, preserved verbatim. The "add 璇存槑" rationalization is explicitly called out in the SKILL.md red flags.

`STAGE_TAGS` is a **closed list** 鈥?six entries: `pm`, `dev`, `plan`, `case`, `case.data`, `瀹炴柦绾`. Adding a stage requires editing `STAGE_TAGS` AND the table in `SKILL.md` AND the trigger description's stage list, all in one change. The script refuses unknown stages; it does not pick the closest match.

`next_available(path)` handles same-name collisions by appending `(1)`, `(2)`, 鈥?before the extension 鈥?but the skill itself does not write files, so this is only used by `--exists-check`.

## Architecture: `list-git-repos`

Implementation complete. The script (`scripts/list_git_repos.py`) and the 5-test pytest suite (`tests/test_list_git_repos.py`) are both shipped; `pytest` from the repo root runs the suite green. The TDD history — RED-phase drift catalog (`docs/baseline.md`), design spec (`docs/superpowers/specs/2026-07-02-list-git-repos-design.md`), and per-task implementation plan (`docs/superpowers/plans/2026-07-02-list-git-repos.md`) — is kept in the repo as a reference for how this skill was built; new skills are expected to follow the same pattern.

Two-phase scan algorithm (from design 搂6):

1. **Phase 1** 鈥?`scan(dir, depth, max_depth)` walks with `os.scandir`, marks `is_git_repo` iff `dir` has an immediate `.git` child (as either directory or file 鈥?handles git worktree pointers). Hard-coded `SKIP_LIST` excludes `.git`, `node_modules`, `target`, `build`, `dist`, `out`, `__pycache__`, `.venv`, `venv`, `.idea`, `.vscode`.
2. **Phase 2** 鈥?prune subtrees with no repo descendant, render ASCII tree with `tree(1)`-style bars. `--with-status` collection happens **after** pruning; one `git status --porcelain --branch` per kept repo with a 5s timeout, failures degrade to `unknown` branch label, never to "repo missing".

Output uses forward slashes even on Windows (test 4 enforces this). Branch label is `?` when `--with-status` is off, distinguishing "not inspected" from "inspected but failed" (`unknown`).

## Architecture: `plan-doc-sequence`

Single Python 3 script, no I/O — it produces *filenames*, never touches disk. The 8-entry sequence is a **closed list** encoded as `SEQUENCE` in the script; agents under pressure reliably make the same six mistakes (dropping 3-digit zero-padding, adding a stage tag to 001, splitting `impl-note` into `impl.note`, using today's date instead of the caller's `--date`, renumbering impl-note to `009`, inventing a 9th entry) — the script blocks all of these.

Filename shape: `{index}.{stage?}.{date}.{feat-name}.md`. Three rules agents forget:

- Index 001 has **no** stage tag — `001.root.{date}.{feat}.md` is wrong; the script emits `001.{date}.{feat}.md`.
- `{date}` must be **exactly 8 digits** (`20260707`), no dashes or slashes — the caller picks the date so all docs in a planning round share it.
- `{feat-name}` is **passed through verbatim** — the script does not slugify, translate, or sanitize CJK. Path separators (`/`, `\`) are rejected.

`impl` / `audit` / `impl-note` are **private to this skill** — they are NOT in `staged-doc-naming`'s `STAGE_TAGS` and must not be added there. `audit` only makes sense inside the planning workflow.

The single highest-drift step is **002.pm**: agents read the original requirement, spot open questions, and invent plausible answers so the doc looks complete. This is the #1 source of downstream 需求偏差. The script cannot enforce the no-assumption rule (it only emits filenames); the agent must stop, list the open questions, and take them back to the user before writing 002.pm.

## Architecture: `analysis-api`

The four script-driven skills above are drift-defense against agents that forget rules when the user pushes back. `analysis-api` solves the same problem with **documentation + reference assets** instead of an executable script, because the work it specifies — multi-step subagent dispatch for code tracing — is procedural and judgement-heavy, not amenable to a one-shot Python entry point. Its drift-defense sits in two layers:

- **`SKILL.md`** carries the procedure: the 7-step method (entry-locator → module split → provider/mapper drill-down → MQ reverse-trace → outbound HTTP trace → main-process synthesis → Markdown report), target-stack assumptions (Java + RPC framework + MQ), subagent constraints (use code-index MCP, return structured signatures, never let one subagent span steps), and the **graceful-degradation rule** — when MQ destinations or cross-service boundaries are unclear, stop and ask the user instead of guessing (same principle as `plan-doc-sequence`'s 002.pm no-assumption rule).
- **`references/`** carries the reusable assets a subagent agent needs to follow the spec without re-deriving the prompts: `subagent-prompts.md` ships 5 drop-in templates (entry-locator, per-module provider, MQ consumer tracer, etc.) with concrete code-index query patterns; `provider-index.md` ships a fillable module → RPC Provider table; `report-template.md` ships the report skeleton (frontmatter + Mermaid flowchart slots + per-step evidence section); `case-study-2026-07-13-label-sync.md` captures the lessons from the skill's first end-to-end run (e.g. step-1 overlap with step-2 prompted the redesign that split entry-locator from provider-listing).

**Why no `scripts/` entry point and no pytest suite:** the work the skill drives is multi-agent orchestration with judgement calls (where to split modules, which MQ to follow, when to ask the user). Neither is expressible as a single CLI nor as a deterministic test — pytest would test the skill's prose, not the agent's behavior. The pytest-covered skills above have a thin, mechanical contract the script enforces; `analysis-api` has a thick, procedural contract the agent must read each invocation. Treat the `SKILL.md` + `references/` pair as its executable form.

## Repository Conventions

### Commit identity

Git identity is **local to this repo** (`Neil <iwuyc@foxmail.com>`), overriding the global default `吴宇春 <wuyuchun@rainbowcn.com>` 鈥?see `MEMORY.md` for the local-vs-global rule. All AI-authored commits go through `git-commit-helper/scripts/ai_commit.py`, which appends `(Ai)` to the user.name and validates the message format. **Never push** 鈥?global rule from the user's `~/.claude/CLAUDE.md`.

### Commit message format

`{type}({branchName}): {abstractDescription}` 鈥?the `(...)` slot is the **branch name**, not a Conventional Commits scope. `feat(auth):` is wrong; `feat(feature/login):` is right. Every commit has a Chinese `- ` bullet body, including one-line fixes. `featName:` / `fix:` metadata lines are present only when meaningful, never with `N/A` / `鏃燻 / `鏈煡` / `TBD` placeholders.

### Adding a new skill

New skills go at the **repo root** as a flat directory `<skill-name>/` (so Claude Code's skill loader finds the `SKILL.md`). Mirror `staged-doc-naming/` for the structure, then pick the artifact-style that fits:

1. Create `<skill-name>/` with `SKILL.md` (frontmatter `name` + `description` + behavior spec).
2. Pick **exactly one** artifact style:
   - **Script-driven** (like `git-commit-helper`, `staged-doc-naming`, `list-git-repos`, `plan-doc-sequence`): place the executable under `scripts/`, the pytest suite under `tests/`. Every behavior the script enforces is pinned by a test case. Use this when the contract is **mechanical and deterministic** — filename format, regex, header validation, scan-and-prune.
   - **Documentation-driven** (like `analysis-api/`): drop one `SKILL.md` plus reusable assets under `references/` (subagent prompt templates, fillable index structures, report skeletons, case-study lessons). Skip `scripts/` and `tests/`. Use this when the contract is **procedural and judgement-heavy** — multi-agent orchestration, call-chain tracing, anywhere the work splits across non-deterministic steps where pytest would test prose rather than behavior.
3. If scripts need new constants lists (like `STAGE_TAGS`), update both the script and the SKILL.md table in the same commit.
4. Add the skill to `README.md` under "Skills 列表" with path, triggers, and core rules, and append the new directory to the "目录结构" tree.
5. If the skill goes through the original RED → GREEN TDD flow (spec first, then tests as the red contract, then implementation), follow the `list-git-repos` pattern: `docs/baseline.md` for the RED-phase drift record, `tests/` for the GREEN-phase pytest cases that pin every behavior the script must enforce. **Skills retro-tested in an audit pass do not need a `docs/baseline.md`** — there is no RED-phase history to record; only the pytest suite. Mark retro-tested skills by having only a `docs/.gitkeep` (so the directory still exists in the repo, for layout uniformity).
6. **Documentation-driven skills skip items 5's pytest requirement** — they are pinned by their `SKILL.md` plus `references/` instead. A new documentation-driven skill still benefits from a case-study (`references/case-study-YYYY-MM-DD-<one-word>.md`) capturing what drift the spec was designed to prevent.

### Documents under `docs/`

`docs/superpowers/specs/` 鈥?design specs (this repo's own, written under the `superpowers` methodology). `docs/superpowers/plans/` 鈥?task-by-task implementation plans. Both follow the `YYYY-MM-DD-<skill-name>.md` naming convention.

### Working tree hygiene

`.gitignore` covers Python cache, virtualenvs, pytest cache, IDE state, and `/.claude/settings.local.json`. Each skill directory has `.gitkeep` in empty `scripts/` and `tests/` so the directories survive git checkout on a fresh clone.
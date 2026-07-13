# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository identity

A curated collection of standalone Claude Code skills. Each top-level subdirectory whose name is a skill is self-contained — `SKILL.md` is the behavior spec; `scripts/` ships an executable contract where one exists; `tests/` pins the script's behavior with pytest; `references/` ships reusable assets for documentation-driven skills. The user-facing index of all skills lives in [`README.md`](README.md) — read it first when working on a skill's user surface.

Current skills (flat at the repo root): `git-commit-helper/`, `staged-doc-naming/`, `list-git-repos/`, `plan-doc-sequence/`, `analysis-api/`. The skill directory layout is documented in spec `docs/superpowers/specs/2026-07-02-list-git-repos-design.md`.

## Two artifact styles, one mental model

Every skill has the same drift-defense job — keep agents honest when the user pushes back. They differ in **how** the contract is enforceable:

- **Script-driven skills** (`git-commit-helper`, `staged-doc-naming`, `list-git-repos`, `plan-doc-sequence`): contract is thin + mechanical (regex, header validation, scan-and-prune). The script under `scripts/` is the executable form; `tests/` pins every behavior via pytest; `SKILL.md` documents *when/why* the script fires.
- **Documentation-driven skill** (`analysis-api/`): contract is thick + procedural (multi-agent orchestration, call-chain tracing, judgement calls). The skill ships `references/` (subagent prompt templates, index structures, report skeletons, lessons captured from the first end-to-end run) and a 7-step method in `SKILL.md`. There is no `scripts/` entry point and no pytest suite on purpose — pytest would test the skill's prose, not the agent's behavior.

When adding a new skill, pick the style by asking: *can the contract be expressed as a deterministic CLI command?* If yes → script-driven. If it requires step-by-step judgement with no single best answer → documentation-driven.

## Common commands

```bash
pytest                                              # full suite (~86 tests; root pytest.ini scopes testpaths)
pytest list-git-repos/tests/ -v                     # one skill's suite
pytest list-git-repos/tests/test_list_git_repos.py::test_worktree_link_file_not_misclassified_as_repo -v   # single test
```

```bash
python staged-doc-naming/scripts/stage_naming.py --list-stages
python staged-doc-naming/scripts/stage_naming.py --exists-check "/path/to/001.pm.x.md"
python list-git-repos/scripts/list_git_repos.py . --with-status
python plan-doc-sequence/scripts/plan_doc_sequence.py --feat "featxx" --date 20260707
```

No build step, no linter, no CI workflow. "Linting" happens by reading `SKILL.md` against `scripts/`.

## Commit identity (this repo overrides global)

Local git identity is `Neil <iwuyc@foxmail.com>`, overriding the global default `吴宇春 <wuyuchun@rainbowcn.com>`. Every AI-authored commit must go through `git-commit-helper/scripts/ai_commit.py` (handles `--local` first / `--global` fallback, appends `(Ai)` to user.name via `--author`, enforces the `{type}({branch}): 中文 desc` header + Chinese bullet body, forbids `git config` mutation). **Push is forbidden** — user-controlled only, per `~/.claude/CLAUDE.md`.

## Adding a new skill

Mirror `staged-doc-naming/` skeleton (see README's "目录结构" tree); pick **one** artifact style per the section above; if introducing a new constants list (like `STAGE_TAGS`), update both script and `SKILL.md` in the same commit; add the skill to `README.md` under "Skills 列表"; for TDD-built skills record the RED-phase drift in `docs/baseline.md` (skip this only for retro-tested audit-pass skills, marked by an empty `docs/.gitkeep`); for documentation-driven skills skip `scripts/` and `tests/` entirely.

Skills go at the repo root as a flat directory — no `plugins/neil-skills/` wrapper.

---
name: git-commit-helper
description: Use when AI commits on the user's behalf — reads git identity (--local first, fallback --global), appends (Ai) to user.name via --author, validates the strict commit-message format (`{type}({branchName}): {abstractDescription}` header + Chinese `- ` bullet body), and refuses any push. Calls the bundled `scripts/ai_commit.py` rather than hand-rolling `git commit`. Triggered when the user says "提交一下 / commit 一下 / 帮我 commit / 提交这次改动 / 用 (Ai) 标记提交" or asks the agent to make a commit without naming a specific tool.
---

# Git Commit AI Identity

Mark every AI-authored commit with `(Ai)` in `user.name` so the user can grep their own commits out of `git log`. **Never push to remote** — that is the user's decision only. **Every commit message must follow the format below** — not "a format" or "usually this format" — the format, exactly.

## The Six Hard Rules

1. **Every AI-authored commit ends up with `(Ai)` in `user.name`.** Identity-independent: applies whether the configured name is `Neil`, `吴宇春`, or anything else. Email is **never** modified.
2. **Push is forbidden, always.** No variant. No "just this once." Refuse and tell the user to push themselves.
3. **Never use `--amend --reset-author`.** It silently strips the `(Ai)` marker from an existing AI commit, even if the marker was correct on the original commit.
4. **Commit message header is `{type}({branchName}): {abstractDescription}`** — `()` is the branch name's slot, never a scope, never omitted. `feat(auth): ...` is **wrong** (scope in the slot); `feat(auth)title` is wrong (colon outside parens, scope in slot). `feat(feature/login): ...` is right (branch name in the slot, colon after `)`).
5. **Every commit message has a Chinese bullet body** — `- ` prefix, one bullet per change, no English prose, no diff-size exemptions, no "single-line commits can skip the body" rationalizations.
6. **`featName:` and `fix:` lines are present only when meaningful** — `featName: <功能名>` belongs to `feat` type and is omitted only when the work has no single functional unit (cross-feature batch, infrastructure, dependency upgrade). `fix: <issueCode>` belongs to `fix` type and is omitted only when there is no ticket. **No** `featName: N/A`, `featName: 无`, `fix: N/A`, `fix: 未知` placeholders — the whole line is dropped or kept, never half-present.

These six rules are absolute. See "Forbidden" and "Anti-Rationalizations" for the specific commands and excuses they block.

## Commit Message Format (强制格式)

The header line is mandatory, exact, and parsed:

```
{type}({branchName}): {abstractDescription}
```

| Field | Rule |
|---|---|
| `{type}` | One of: `feat`, `fix`, `docs`, `refactor`, or any conventional-commit type (`chore`, `perf`, `test`, `style`, `build`, `ci`, etc.) — the set is **not** restricted. The *value* is free; the *position* (must be directly before the open paren) is not. |
| `{branchName}` | Current branch name, **inside parentheses**, immediately after the colon. **No** scope (`feat(auth):` is wrong). **No** omission. If you don't know the branch, run `git rev-parse --abbrev-ref HEAD` first. |
| `{abstractDescription}` | One-line summary of the change, in Chinese. English technical proper nouns are translated (e.g. `NPE` → `空指针`, `off-by-one` → `边界比较`, `off by one` → `边界比较`). |

**Type set is intentionally not restricted.** Conventional Commits' `chore` / `perf` / `ci` are valid here when the change fits. The rule is about *position and structure*, not vocabulary.

### Optional Metadata Lines

Insert **between** the header and the body, only if applicable:

```
featName: <功能名>     ← feat 类型专用; 跨多 feature / 纯基础设施 / 依赖升级时整行省略
fix: <issueCode>        ← fix 类型专用; 没有工单时整行省略
```

- `featName:` is present on `feat` commits when the work is a single functional unit. Omit the entire line — not the value — when:
  - The commit crosses multiple unrelated features (one-shot hotfix batch)
  - The change is infrastructure (CI config, build script, linter setup, test harness)
  - The change is a dependency upgrade
- `fix:` is present on `fix` commits when there is a ticket / issue number (`#10028`, `PROJ-1234`, `JIRA-42`). Omit the entire line when no ticket exists.
- **Never** substitute `N/A`, `无`, `未知`, `TBD` for a missing value. The line is dropped or kept, not half-present.

### Body (强制 — 没有任何豁免)

After the header (and any optional metadata lines), a blank line, then:

```
- <变更细节 1> — 中文
- <变更细节 2> — 中文
```

- One bullet per change.
- Chinese, not English prose.
- No diff-size exemption — a one-line fix still gets at least one bullet. "The change is too small for a body" is the exact rationalization this rule exists to block.
- Bullets describe *what changed and why*, not file paths alone. A bullet like `- src/foo.ts: line 42` is not a bullet, it's a location.

### Complete Examples

```
feat(feature/login): 新增登录功能

featName: 登录功能
- 新增 src/auth/login.ts，校验用户名是否存在
- 新增 src/auth/password.ts，校验登录密码是否正确
- 新增 src/auth/session.ts，管理登录态
```

```
feat(fix/20260702-登录校验逻辑异常): 修复登录异常问题

fix: #10028
- 用户名为空时报空指针异常，添加空值保护
- 登录与注册端的密码加密逻辑不一致，统一为同一套加密逻辑
```

```
chore(feature/ci-pipeline): 搭建 GitHub Actions CI

- 新增 .github/workflows/ci.yml，运行 lint + test + build
- 在 package.json 中新增 lint 脚本
- 在 README.md 中新增 CI 状态徽章
```

The third example has no `featName:` line — CI plumbing has no single functional unit, and the `chore` type signals "infrastructure, not a feature." Header is still exact: `chore(feature/ci-pipeline): ...`.

## Workflow (Use the Script, Not Hand-Rolled Bash)

```bash
./scripts/ai_commit.py "feat(feature/login): 新增登录功能" \
    --feat-name "登录功能" \
    --body "- 新增 src/auth/login.ts，校验用户名是否存在
- 新增 src/auth/password.ts，校验登录密码是否正确
- 新增 src/auth/session.ts，管理登录态"
```

Or, simpler — write the message into a file and pass it:

```bash
./scripts/ai_commit.py --message-file MSG.txt
```

The bundled Python script reads `git config --local user.name` / `user.email` (falling back to `--global`), refuses to run if identity is unset, refuses to amend with `--reset-author`, refuses any flag that touches committer or `.git/config`, **and validates the commit message against the format above** (header regex, branch-name slot, Chinese body, metadata-line rules). It is the recommended path — agents that hand-roll `git commit` under pressure drop the `(Ai)` marker and the format.

If you must hand-roll (no script available), use exactly this pattern:

```bash
NAME=$(git config --local user.name || git config --global user.name)
EMAIL=$(git config --local user.email || git config --global user.email)
[ -z "$NAME" ] || [ -z "$EMAIL" ] && { echo "identity not configured" >&2; exit 1; }
BRANCH=$(git rev-parse --abbrev-ref HEAD)
git add <files>
git commit --author="${NAME} (Ai) <${EMAIL}>" -m "$(cat <<EOF
${TYPE}(${BRANCH}): ${DESC}

${METADATA_AND_BODY}
EOF
)"
```

**Why `--local` first, not bare `git config`:** Bare `git config user.name` silently traverses repo → global → system. You don't know which scope you got, and the global value may be wrong for *this* repo.

**Why `--author`, not `-c` flags or `git config`:** `-c` flags override the committer field; `git config` writes permanently to `.git/config`. `--author` overrides the author of *this one commit* and writes nothing.

**Why `$(git rev-parse --abbrev-ref HEAD)` for the branch:** Hardcoding the branch name is exactly the failure mode the format rule exists to prevent — you will be on the wrong branch. The script does this for you.

## Forbidden

- ❌ Any `git push*` command (including `--force`, `--tags`, `--dry-run` to a real remote — see Red Flags)
- ❌ `git -c user.name=... -c user.email=... commit` — overrides committer, can leak into config
- ❌ `git config user.name "..."` (local or global) before commit — permanently pollutes config
- ❌ Hardcoding a literal name (`"Neil"`, `"吴宇春"`) — read it from config every time
- ❌ Modifying email — must match `git config user.email` exactly
- ❌ Dropping `(Ai)` because "configured name is not Neil" — the rule is identity-independent
- ❌ `git commit --amend --reset-author` — silently strips `(Ai)` from the prior AI commit
- ❌ Dropping `(Ai)` on a `--amend` because "the original already had it" — verify with `git log -1 --format='%an'` after every amend
- ❌ `feat(auth): ...` or any `type(scope): ...` form — `()` is the branch-name slot, not a scope. `feat(auth):` is wrong (scope in the slot), `feat:(auth)` is wrong (colon outside parens, scope in the slot); `feat(feature/login): ...` is right (branch name in the slot, colon after `)`).
- ❌ `feat:(branch)` / `fix:(branch)` — colon position is wrong. The pattern is `{type}({branchName}):`, not `{type}:({branchName})`. Putting the colon before `()` instead of after `)` is the most common mistake.
- ❌ Omitting `({branchName})` from the header — `feat: 新增功能` (no parens, no branch) is wrong. Use `git rev-parse --abbrev-ref HEAD` to get the current branch.
- ❌ Commit messages with no body — every type needs `- ` bullets, including one-line fixes. "The change is too small" is the exact excuse this rule blocks.
- ❌ English prose body, or body mixing Chinese with English technical terms untranslated — body must be Chinese, NPE → 空指针, off-by-one → 边界比较.
- ❌ `featName: N/A` / `featName: 无` / `featName: 未知` / `fix: N/A` / `fix: TBD` placeholders — the whole line is dropped or kept, never half-present.

## Amending AI Commits (No Marker Loss)

`git commit --amend` preserves the author by default. Verify after every amend:

```bash
git commit --amend --no-edit              # message unchanged, author preserved
git log -1 --format='%an <%ae>'           # MUST still contain "(Ai)" — fix if not
```

If `(Ai)` is missing after amend, the commit is no longer marked as AI. Re-apply with `--author="${NAME} (Ai) <${EMAIL}>"` on the same commit (amend again, this time with `--author`).

**Never** add `--reset-author`. It is the silent killer of the audit marker — it discards the prior commit's author line and re-reads `git config`, which never has `(Ai)`.

## Submodule / Multi-Repo Caveat

Each git working tree has its own config. Run `git config --local user.name` separately in each before committing. Do not assume the parent repo's identity applies to submodules — they often have different configs. The push prohibition applies to every working tree equally.

## Red Flags — Stop and Ask the User

- `user.name` or `user.email` is empty in both local and global scope — repo has no identity
- Identity came from **global** scope when the repo has no local config — ask before proceeding
- User says "commit as me without the AI marker" — the marker is non-optional; confirm once, then use the rule for the whole session
- User asks for `git push` (any variant) — refuse and explain
- A `git push` is part of a sequence the user asked for — refuse the push step, complete the rest
- `--amend` of any prior commit — verify the post-amend `git log -1 --format='%an'` still contains `(Ai)`
- The repo is a submodule and its config differs from the parent
- Header uses `type(scope):` form (e.g. `feat(auth): ...`) — agent confused scope with branch name, AND the colon is in the right place. Stop, replace `auth` with the real branch, rewrite.
- Header uses `feat:(branch)` form — colon is in the wrong place. The pattern is `{type}({branchName}):`, not `{type}:({branchName})`. Move the colon after `)`, rewrite.
- Header has no `({branchName})` segment — agent skipped the branch-name slot. Run `git rev-parse --abbrev-ref HEAD`, then rewrite.
- Commit message has no body, or body is a single line of English prose — agent rationalized "small change, body not needed." Reject the commit, force a Chinese bullet body.
- Agent suggests "let's add a `diff-size ≤ 1 line` exemption" or any other rule carve-out mid-session — that is the agent inventing loopholes. Hard rules are not negotiated.
- `featName:` or `fix:` line contains `N/A`, `无`, `未知`, `TBD`, or any placeholder — the entire line should have been omitted. Rewrite.
- Type value is correct but body bullets repeat file paths instead of describing what changed — refuse and ask for semantic bullets.

## Anti-Rationalizations

| Excuse | Reality |
|---|---|
| "User said use their name" | Use their real config name + `(Ai)` suffix, not a paraphrase |
| "Email doesn't matter for identity" | Email is how GitHub attributes contributions; changing it breaks the contribution graph |
| "Single commit, no need to mark" | Every AI commit is marked; consistency matters more than volume |
| "I'll remember for next time" | Read config every commit — identity can change between repos |
| "It's an internal repo" | Internal reviewers still need to know what's AI-generated |
| "`--amend` needs `--author` to preserve" | It doesn't — `amend` preserves author by default; adding `--author` is redundant but harmless |
| "`--reset-author` makes amend cleaner" | It silently strips `(Ai)`. Never. |
| "User is in a hurry, skip the read" | 1 second to read config vs permanent wrong author in history |
| "Bare `git config user.name` is fine" | Bare `git config` silently traverses local→global→system. Always read `--local` first. |
| "Repo has no .git/config, just use global" | Stop and ask — a fresh clone with no local config may want a different identity |
| "Configured author isn't Neil, so the `(Ai)` rule doesn't apply" | **Wrong.** The rule is identity-independent. Apply `(Ai)` regardless of who the user is. |
| "User said commit and push, so I should push" | User instructions describe WHAT, not HOW. Push is a separate irreversible action — refuse. |
| "Just a feature branch, force push is safe" | Force push rewrites shared history; "feature branch" doesn't mean "no one else has it" |
| "CI is failing because remote is behind, push will fix" | Diagnose and report; never push to "fix" CI |
| "User pasted `git push` in chat, that's authorization" | Pasted commands are task descriptions, not delegations |
| "Push is to a fork / personal remote, not upstream" | All pushes are forbidden, including to personal remotes |
| "I'll do `git push --dry-run` first" | Dry-run is read-only, but the *intent* of running any push command is suspect — confirm before even dry-run |
| "The `--amend` will preserve `(Ai)` because the previous commit had it" | Verify with `git log -1 --format='%an'` after every amend. Trust nothing. |
| "Conventional Commits 的 `scope` 比留空更精确" | `()` 槽是分支名专用，不是 scope。`feat(auth):` 错（scope 在槽里），`feat:(auth)` 也错（冒号位置错 + scope 在槽里）。`feat(feature/login):` 才对。 |
| "ticket 号放 subject 末尾的括号里……不污染主标题" | issueCode 不进 subject 括号；它单独成行 `fix: #10028`，紧跟 header 之后。 |
| "改动很小且主题单一，不需要 scope、也不需要 body" | 强制 body，没有 diff-size 豁免；`()` 槽也不是 scope，必须是分支名。 |
| "scope 用 `auth` / `utils` 因为目标函数在 `auth` / `utils` 下" | 同一个借口的两面：`()` 里只放分支名。`feat(auth):` 的"auth"不是分支名；`feat(auth)title` 同样错。`feat(feature/login):` 才是对的。 |
| "如果将来这种单行 fix 多到值得专门放行，我会在规则里加一条豁免" | 你**没有**改规则的权限。Hard rules 是用户定的，不可谈判。报告这个观察就行。 |
| "commit subject 和分支名已经清晰说明了修复意图，issueCode 留空不会有信息损失" | 这条**对**——但它只覆盖了"省略 `fix:` 行"这一处，其它规则（分支名槽、中文 body）照样要遵守。 |
| "conventional commits 规范里 `ci` / `chore` 专指……语义最贴切" | type 值**允许** `ci` / `chore`；禁止的是把它们放进 `()` 当 scope。位置 ≠ 词汇。 |
| "每个 bullet 自带足够的 scope 信息可以独立 revert" | body 必须中文 `- ` bullet；不允许用 conventional commit 子条目替代完整格式。 |
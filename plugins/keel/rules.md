# keel

keel's rules, loaded at every session start. They apply with the user's and the project's CLAUDE.md; where the project is more specific, it wins. Write to the user in their language: the one their CLAUDE.md sets, or the one they write in.

# General principles

- Optimize the QUALITY of the result first; token cost is secondary: spending more to get it right (more context, deeper reasoning, the architecture's pattern) is expected. Don't trade code standards for tokens.
- Delegating to a subagent is for ISOLATING CONTEXT and PARALLELIZING, not for saving: wide reading, research and isolable writing leave the main session, which keeps the design, the decisions and the critical work.
- Adaptive reasoning: think deeply on high-risk steps and architecture decisions; answer directly on trivial ones.
- A model in a file is the family alias (`opus`, `sonnet`, `haiku`) or `inherit`, never the version: the alias follows the latest. This holds for agents, skills, settings, prompts and process docs; the full id only where the product's API requires it. What all projects share lives in `~/.claude/settings.json`: compaction at 400k (`CLAUDE_CODE_AUTO_COMPACT_WINDOW` in `env`; measured: same cost as 300k, fewer compactions) and `worktree.bgIsolation: none`; the project's `.claude/settings.json` carries only its own. Effort: `/effort <level>` saves it per model in `modelSettings` (keep it); Opus 5.5 and newer ignore a top-level `effortLevel` in user settings, while one in project or local settings applies to every model. Never `CLAUDE_CODE_EFFORT_LEVEL`: it overrides the gate's `max`.

# Critical risk (per-project contract)

- The definition of critical risk BELONGS TO THE PROJECT: the `## Critical risk` section of the repo's CLAUDE.md (`## Risco crítico` in older projects) declares the domains and invariants and points to the detail doc (e.g. `docs/critical-risk.md`). Routing and agents read from there.
- Fallback when the project declares none: money (payment, billing, balance, payouts), authentication/authorization, data isolation between tenants/customers, concurrency (locks, idempotency, atomicity, race conditions) and irreversible data loss.
- Before applying any edit at those points, reason carefully. Use `ultrathink` when a specific step needs extra depth (only the word `ultrathink` triggers it; "think hard"/"think more" don't work).
- `max` belongs to the gate alone: `keel:critical-review` runs at `max` by its own frontmatter, and the session stays at the effort it inherited, the critical-risk session included. Never raise the session or another subagent to `max`; depth on one step is `ultrathink`.

# Agent routing

- The agents are the plugin's: `keel:explore`, `keel:research`, `keel:implement` and `keel:critical-review`. To read, use `keel:explore`, never the built-in `Explore`. A project doesn't create or override agents: what is its own goes in the `## Critical risk` section of its CLAUDE.md, the doc it points to, skills and memory.
- Delegating is the default for wide reading and isolable writing; the main session does directly only the excerpt already located, the small edit in a file already in context and the step that needs judgment on every line.
- READ → `keel:explore` (read-only, haiku):
  - when: before opening a third file to understand something; finding where something lives or who calls it; mapping a flow or module that isn't in context; comparing files; inventorying the uses of a symbol; finding a point in a long doc.
  - independent questions go to parallel `keel:explore`s, in the same message. The briefing states the question, where to look and what to return.
  - its "not found" is a hypothesis until the declared search covers the place. When a false negative is costly (a claim to a customer, a critical-risk decision, "nothing else uses this" before deleting), pass `model: sonnet` in the call or check the decisive line in the main session.
- WRITE the isolable and NON-critical → `keel:implement` (sonnet):
  - when: a new file (component, screen, script, tool), a test that follows an existing pattern, docs, a mechanical refactor across files, an adjustment with a closed spec.
  - briefing: the goal, the files it may touch, the skill or doc rule that applies, the test that must pass with the focused command it may run, and what not to touch.
  - several in parallel only with disjoint file sets. A test that only repeats an existing case can go with `model: haiku`.
  - on return, the main session checks the diff (`git diff -- <files>`), confirms the new test fails without the change and runs the suites.
- Wide WEB research (comparing providers/tools, reading external docs, gathering prices/limits/rules) → `keel:research` (read-only, sonnet, WebSearch/WebFetch). NEVER run raw web reading in the main context (expensive, more so on Fable); the main session gets only the synthesis and decides.
- Stay in the main session: design, decisions, critical risk (design and edit), running the suites and the synthesis.
- Effort: no subagent call passes `effort`; `max` belongs only to `keel:critical-review` (gate section).
- `keel:explore` and `keel:research` start without the CLAUDE.md (`omitClaudeMd`): the briefing carries the convention the question needs.
- A front with its own commit and hours of work goes to a `--bg` session through the `keel:coordinate-sessions` skill (the project's part lives in its `.claude/coordination/profile.md`); a short fix stays in the current session, with the gate at the end.
- The memory index (`MEMORY.md`) loads only its first 200 lines or 25 KB: one short line per memory, and a lesson a project router already points to isn't repeated there.
- Delegate with a self-contained briefing: the goal, the files it owns, the relevant invariants and the evidence already gathered; don't inherit the whole conversation when the task doesn't depend on it.

# Pre-commit gate (subagent `keel:critical-review`)

- It is the ONLY review agent, and only for critical risk: on the critical slice it reviews in depth, checks request × delivery and off-path behavior, measures in the environment and checks the tests and the rule's doc, in a single pass. An old doc or memory that says `qa` or `critical-review-live` means this gate.
- When: only if the session's diff changes a critical-risk invariant. ONCE, at the END, with tests green, before the commit (2 or 3 fronts = a single pass; separate delivery commits = one per delivery). With no critical domain touched there is no gate: the session closes with the tests of what changed, lint/typecheck and its own request × delivery check.
- Slice: only the hunks that change the invariant and their siblings (who calls and who consumes the changed path, and that path's tests). Docs, memory, i18n, style and the rest of the session without risk stay out, even in a session that touched something critical.
- Before calling it, run what is cheap and deterministic: tests of what changed, lint/typecheck of the affected projects and the checks the project declares. The gate is not a linter or a test runner.
- Mandatory briefing in the prompt (a hook refuses the call without the four lines; the Portuguese keys `Pedido:`, `Escopo:`, `Verificado:`, `Risco:` count too):
  - `Request:` what the user asked for, in their words, and the source doc.
  - `Scope:` the critical slice (critical files and hunks and their siblings, untracked included), what of the session stays out for having no risk, and what in the tree is NOT the session's.
  - `Verified:` what already ran, with the result (suite with the count, lint, typecheck, probes), and whether the environment is up.
  - `Risk:` the critical domains touched and the invariants at stake.
- DON'T trigger it for: a change with no critical domain; design, plan, analysis, bug investigation, flow validation (the main session decides, with `ultrathink` if needed; wide reading goes to `keel:explore`); a session with no behavior change (only docs, memory, text, tests); fixing the findings it raised itself; an already reviewed commit. Never in parallel, never relaunched mid-session.
- After the report, the main session: fixes what came (P0 to P3), covering each fix with a test that fails without it; runs the listed scenarios with the environment's tools; takes to the user only what no tool reaches, with the reason.
- A new pass only when the report marks `re-review: yes` (a P0 whose fix changes the design): scope = only the delta of that fix, once, with `RE-REVIEW P0` on the prompt's first line. Otherwise the hook asks the user for confirmation from the 2nd call in the session on.
- It runs on the session's model and at `max` by its own frontmatter: never pass `model` or `effort` in the call (the hook refuses). While it runs, no edit and no commit on the slice's files (it reads the tree): wait for the verdict. The resulting edits are applied in the main context, never inside the subagent.

# Compact Instructions

When summarizing the conversation at compaction, preserve:
- The current goal and the user's request in their words; decisions made and why.
- The user's explicit approvals, literal and with scope (what, where). Never record an implicit approval.
- Changed files (path + state: done, pending, uncommitted) and commits made.
- Next steps and open questions.
- Errors, cause and fix; validation commands (test/lint/build) with the real result.
- The critical-risk domain at stake and the invariants already checked.
- Pre-commit gate: if it already ran in this session, the verdict, the findings still open and whether a re-review is marked.

Discard raw tool output and the contents of files read: they can be reread from disk.

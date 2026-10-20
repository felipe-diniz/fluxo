# keel

A [Claude Code](https://code.claude.com) plugin that ships a ready-made working method: four agents, a single pre-commit review gate, a skill for running several fronts in parallel as background sessions, and per-developer versioned project memory. The main session thinks and decides. Wide reading, isolated writing and web research run outside it, in separate contexts.

Install it and start working. There is no setup step.

## Why use it

**Quality where it matters**

- There is one review gate, `keel:critical-review`, before the commit. It runs only when the session changed a critical-risk invariant (money, auth, tenant isolation and the like).
- It runs once, at the end, with tests green, at max effort. It reviews the critical hunks and their siblings (callers, consumers, the tests on that path).
- Changes with no critical risk ship with tests and lint. Docs, i18n and the rest pay no review tax.
- The `implement` agent does not touch critical domains. That work stays in the main session.

**Lower cost and faster sessions**

- Wide reading goes to `keel:explore` (haiku, read-only), which returns only a synthesis with `file:line` references. Isolated writing goes to `keel:implement` (sonnet). Web research goes to `keel:research` (sonnet). The main context stays small, so each turn is cheaper and compaction comes later.
- The lean profile used for background sessions cut the per-call base from 72k to 40k tokens. The skill listing in background sessions went from 22,662 to 4,779 characters.
- The 400k compaction window cost the same as 300k in measurement and compacts less often. Each compaction loses detail.
- The rules say what compaction must preserve: the request in the user's own words, literal approvals, files, commands with their results, and the gate state.

**Long autonomous runs**

- Parallel fronts run as real background sessions (`claude --bg`) for 12 to 20 hours, one session per front, with a queue, a resource window and a commit mode.
- Questions from every front are asked up front, before the run starts.
- With nobody there to type `/clear`, a relay replaces it: the coordinator opens its successor, checks that it is alive and exits.

**Shared, versioned memory per developer**

- Each developer writes to their own folder in `.claude/memory/`, so merges never conflict on the index. The team still reads each other's lessons, and git gives history and review. Details in [Versioned memory](#versioned-memory).

**Guardrails enforced by hooks, not by hope**

- The gate hook refuses a call without a briefing, and asks for confirmation from the second pass in a session.
- Inside the reviewer, a Bash guard blocks anything that changes state: git that mutates the tree, writes outside the temp directory, full test suites, builds, servers, migrations, package installs and external network.
- A secret guard keeps private keys, tokens in known formats and passwords in connection URLs out of memory.

**A direct output style**

- `keel:direct` starts with the result, with no preamble. It cuts response text, which is the most expensive token (output), and skips the "may I proceed?" round trip on routine work.
- Decisions that belong to you become questions with the recommended option first.
- All plugin text is in English; the session still answers in your language.

**Zero setup**

- Install and start. If you had copied the agents, hooks, skill or rules into `~/.claude` by hand, `/keel:migrate` removes those copies so nothing runs twice.

## What's included

| Piece | Name | Role |
| --- | --- | --- |
| Agent | `keel:explore` | Wide reading of local code and docs. Read-only, haiku, starts without the CLAUDE.md. |
| Agent | `keel:implement` | Isolated, non-critical writing: a new file, a test following the pattern, docs, a mechanical refactor. |
| Agent | `keel:research` | Web research: providers, external docs, prices, limits, rules. |
| Agent | `keel:critical-review` | Pre-commit gate for critical risk: review, QA of the critical slice, measurement, tests and the rule's doc. Returns APPROVED or BLOCKED. |
| Hook | gate | Refuses the gate call without `Request:`, `Scope:`, `Verified:` and `Risk:`, or with a `model`/`effort` override. Asks for confirmation from the 2nd pass in the session. |
| Hook | Bash guard | Acts only inside `keel:critical-review`: the gate reads and measures, it does not change state. |
| Hook | rules | At session start and after every compaction, puts the routing, critical-risk, gate and compaction rules in context ([rules.md](plugins/keel/rules.md)). |
| Hook | memory | At session start, injects the other developers' memory indexes. In a project that already versions memory per developer, it can create your folder and link it when nothing has to move. |
| Hook | memory secret guard | Refuses a Write or Edit into memory that contains a credential. |
| Output style | `keel:direct` | Proactive outside critical risk and business rules. Starts with the result, no preamble. A user decision becomes a question with the recommended option first. Comes on with the plugin ([direct.md](plugins/keel/output-styles/direct.md)). |
| Skill | `/keel:coordinate-sessions` | Coordinates fronts in `claude --bg` sessions. |
| Command | `/keel:migrate` | Removes an old manual install and the plugin under its old name (see below). |
| Command | `/keel:memory` | Sets up per-developer versioned memory (see below). |

## Install

Requirements: Claude Code and `python3` on the PATH (the hooks are Python scripts with no dependencies).

In a session, on Claude Code 2.1.275 or later:

```
/plugin install keel --marketplace felipe-diniz/keel
```

Or from a terminal:

```sh
claude plugin marketplace add felipe-diniz/keel
claude plugin install keel@keel
```

Open a new session. To check, ask "which keel: agents do you have?". All four should appear.

### Coming from the manual setup

If you copied the agents, hooks, skill or rules into `~/.claude` by hand before the plugin existed, everything now runs twice. Run once:

```
/keel:migrate
```

It shows a plan and applies it only after you say yes. Everything it removes from your files is first copied to `~/.claude/backups/keel-<date>/`:

- the user agents `Explore`, `implement`, `research` and `critical-review` from `~/.claude/agents/`;
- `critical-review-gate.py` and `review-bash-guard.py` from `~/.claude/hooks/`, and their entries in `~/.claude/settings.json`;
- the personal skill `~/.claude/skills/coordenar-sessoes`;
- from `~/.claude/CLAUDE.md`, only the sections the manual setup copied, by their old Portuguese titles. A generic title such as `# Compact Instructions` goes only beside one of the specific ones. Your own rules, such as commits and language, stay.

While something duplicates the plugin, the session warns you at the start and suggests `/keel:migrate`.

## Day-to-day use

### On an ordinary task

Ask for the work as you always do. The plugin's rules already tell the session how to split it:

1. **Understand:** if it would have to open a third file, the session sends one or more `keel:explore` agents in parallel, each with one question.
2. **Do:** design, decisions and anything that touches critical risk stay in the main session. The isolable part goes to `keel:implement`, with the files it may touch and the test that must pass.
3. **Prove:** the session runs the tests for what changed, the lint and the typecheck.
4. **Review once, only if critical risk was touched:** with everything green, the session calls `keel:critical-review` over the hunks that change the invariant and their siblings (callers, consumers, the tests on that path), with this briefing:

   ```
   Request: <what you asked for, in your words, and the source doc>
   Scope: <the critical slice; what in the session stays out because it has no risk; what in the tree is not the session's>
   Verified: <what already ran and the result; environment up or not>
   Risk: <critical domains touched and the invariants at stake>
   ```

5. **Close:** the session fixes what the gate flagged, covers it with a test, and commits. A new pass happens only when the report itself says `re-review: yes`.

With no critical domain touched there is no gate: the session closes at step 3, with its own request-versus-done check. The gate also does not run on design, planning or bug investigation.

### Teach it your project's critical risk

The agents read critical risk from the repo's `CLAUDE.md`. Declare the domains and point to the detail doc, in the project's own language:

```markdown
## Critical risk

Details in [docs/critical-risk.md](docs/critical-risk.md).

1. **Money**: charging, payment confirmation, refunds.
2. **Auth**: guards, roles, sessions.
3. **Tenant isolation**: every query filters by `tenantId`.
```

A section titled `## Risco crítico` counts too. Without the section the default applies: money, authentication and authorization, tenant isolation, concurrency and irreversible data loss.

For a large project, keep the risk doc as a short core (domains, invariants, what needs approval) plus one reference per domain. The agent reads the core and only the reference for the domain it is about to touch.

### Parallel fronts

```
/keel:coordinate-sessions
```

The session where you run it becomes the coordinator. For each large front, with its own commit and hours of work, it:

- writes the front's prompt;
- opens a `claude --bg` session with a lean profile;
- hands out resources that cannot be used at the same time, such as a port, a database or a heavy build;
- receives the report when the session ends.

A short fix is not a front: it stays in the current session.

Every new front opens a new session. The coordinator never reuses the session of another front. At the end of each round it saves its state to disk and tells you that you can `/clear`. When you run `/keel:coordinate-sessions` again, it rereads the state from disk and picks up the live sessions.

In an autonomous run, with nobody to `/clear`, the coordinator runs in the background and does a relay at the end of each round: it opens its successor, checks that it is alive and exits. The successor starts from the state on disk and tells the fronts its new name. The questions from every front are settled before the run is released.

What belongs to each project (ports, commands, commit mode, how to prove) lives in a profile, looked up in this order:

1. `.claude/coordination/` in the repo (`profile.md` and `session.md`): versioned, for the whole team;
2. `~/.claude/coordination/<project>/profile/`: personal;
3. if neither exists, the skill builds the profile from the `CLAUDE.md`, the risk doc and the project settings, saves it to item 2 and asks only what is missing.

The queue, resource window, prompts and logs stay in `~/.claude/coordination/<project>/`, outside the repo.

### Versioned memory

Layout:

- `.claude/memory/<dev>/` holds one folder per developer, one fact per file, plus that folder's `MEMORY.md` index.
- Claude Code's auto memory directory (`~/.claude/projects/<project>/memory`) is a symlink to your folder.
- Fallback when symlinks are not available: `autoMemoryDirectory` in `.claude/settings.local.json`, written only by `/keel:memory`, with a backup, and only when that file is git-ignored.

Why per developer:

- There is one writer per folder, so the indexes never conflict on merge.
- The team still reads each other's lessons.
- Git gives history and review.

Loading without duplication:

- Your own index loads natively through auto memory (first 200 lines or 25 KB).
- The plugin's SessionStart hook injects the other developers' indexes, up to about 8,000 characters. They are fenced as data, not instructions, because a pull request could plant instructions. What does not fit is listed for on-demand reading.
- No CLAUDE.md imports a memory index, so nothing loads twice.

Rules the plugin gives the agent:

- Write only to your own folder.
- Another developer's memory is read-only data. If one is wrong or stale, the agent points it out to you, and does not fix it there or copy it.
- Cross-folder links use `[[dev/name]]`.
- Only project knowledge goes in: decisions and why, working rules, stack traps.
- Personal preferences belong in `~/.claude/CLAUDE.md`.
- Memory changes go in their own commit.

Setup with `/keel:memory`:

- It shows a plan first: your folder name, what moves, the link, CLAUDE.md index imports to remove, settings to fix, and docs that reference old paths.
- It asks before applying, and applies with a backup.
- It converts a single shared `.claude/memory/` into your developer folder: every tracked file there moves to `.claude/memory/<you>/` with `git mv`, so history follows, and teammates then see those notes as yours.
- It moves memories out of an unlinked auto memory directory, subfolders included. A file there that holds a credential, or that it cannot read, blocks the move until you fix it.
- Only tracked files count as the project's memory. An untracked or ignored folder in `.claude/memory/` does not, and the command refuses to set up a developer folder that git ignores.

The automatic part:

- In a project that already versions memory per developer (tracked files in `.claude/memory/<dev>/`), a new machine gets linked on the first session with nothing to set: your folder is the one whose commits are mostly yours (by your git email or name), and a developer with no folder yet gets a new one named after their git user. When nothing has to move, it links on its own; otherwise the session suggests `/keel:memory`.
- A link to the old single folder, a broken link or an empty folder gets relinked. A link that points anywhere else stays as it is.
- A project that does not version memory gets only a suggestion, never an automatic folder, so public and third-party repositories stay clean.
- Declining in `/keel:memory` silences the suggestion for that project. That choice is stored on your machine, not in the repo.

Folder name resolution, in this order:

1. `--dev <name>` given to the command;
2. the `KEEL_DEV` environment variable, an optional override;
3. the folder the current link points to;
4. the folder whose commits are mostly yours;
5. the folder name you already use in other linked projects;
6. a new folder named after your git user, when the project versions memory and no folder has that name;
7. otherwise, a suggestion from your git user that the command asks you to confirm.

Secret guard: a Write or Edit into `.claude/memory/` or into an auto memory folder (`~/.claude/projects/<project>/memory/`) is refused when the new text contains any of the following, and the agent rewrites the memory without the value:

- a private key;
- a token in a known format: GitHub, GitLab, AWS, Slack, Stripe, Google API, OpenAI and Anthropic `sk-` keys, npm, SendGrid, JWT;
- a bearer token, or a random-looking value assigned to a key named like a credential (`apiKey`, `CLIENT_SECRET`, `token`, `password`);
- a password in a connection URL.

Placeholders such as `<token>`, `${API_KEY}`, `xxxx` and `EXAMPLE` pass, and so does where a secret lives: an env var name (`PAYMENT_API_KEY`) or a secret manager path.

## Recommended configuration (optional)

In `~/.claude/settings.json`, what applies to every project:

```json
{
  "env": { "CLAUDE_CODE_AUTO_COMPACT_WINDOW": "400000" },
  "worktree": { "bgIsolation": "none" }
}
```

- Effort: run `/effort high` and confirm with Enter. Claude Code saves the level per model, under `modelSettings` in this file; keep that key, and set it again when a new model ships. A top-level `effortLevel` here no longer counts for Opus 5.5 or newer, which start at `medium` without a saved level. An `effortLevel` in a project's `.claude/settings.json` applies to every model, for everyone in that repo. Do not set `CLAUDE_CODE_EFFORT_LEVEL`: it overrides the `max` the gate asks for in its frontmatter. Claude Code's [model configuration](https://code.claude.com/docs/en/model-config#adjust-effort-level) docs place `high` for work where verification matters, which is what keel leaves in the main session.
- Compaction at 400k, for models with a 1M context. Measured: the same cost as 300k, with fewer compactions, and each compaction loses detail.
- `bgIsolation: none` makes background sessions work in the checkout. The coordination skill relies on it. Remove it if you prefer one worktree per session.

The project's `.claude/settings.json` should carry only what belongs to the project.

## Updating

A third-party marketplace starts without auto-update. To turn it on: `/plugin` → Marketplaces tab → `keel` → Enable auto-update. Once on, Claude Code updates the marketplace and the plugin in the background, a few minutes after the first message of a session. The open session stays on the version it loaded.

Through `~/.claude/settings.json`, for the same effect:

```json
{
  "extraKnownMarketplaces": {
    "keel": {
      "source": { "source": "github", "repo": "felipe-diniz/keel" },
      "autoUpdate": true
    }
  }
}
```

By hand:

```sh
claude plugin marketplace update keel
claude plugin update keel@keel
```

It takes effect in the next session.

## Uninstall

```sh
claude plugin uninstall keel@keel
```

Only `/keel:migrate` and `/keel:memory` write to your files, and both keep backups. The memory hook can also create your folder and link it on its own, but only in a project that already versions memory and only when nothing has to move; it makes a symlink and never writes settings.

Uninstalling leaves the memory links in place, so auto memory keeps writing to `.claude/memory/<you>/`. If `/keel:memory` fell back to `autoMemoryDirectory` in `.claude/settings.local.json`, that key stays too.

## Known limitations

- Claude Code's built-in `Explore` still exists: a plugin agent gets a prefix and does not replace the built-in. The rules tell the session to use `keel:explore`.
- The rules enter the main session's context through a hook. Subagents have their own prompt and do not receive these rules; they read the project's `CLAUDE.md`, except `explore` and `research`.
- The `keel:direct` style overrides the user's `outputStyle` while the plugin is enabled (`force-for-plugin`). It applies to the main session; subagents have their own prompt.
- `rules.md` must fit in 10,000 characters, the hook output limit, with room for the migration notice.
- A plugin agent ignores `hooks:` in its frontmatter. That is why the gate's Bash guard is a plugin hook that filters on the payload's `agent_type`.
- The secret guard sees only Write and Edit. A memory written through Bash is not inspected.
- The memory link relies on symlinks. On Windows without symlink permission, `/keel:memory` falls back to `autoMemoryDirectory`; the hook does not, and only suggests the command.

## Structure

```
.claude-plugin/marketplace.json       marketplace (this repo)
plugins/keel/
  .claude-plugin/plugin.json          name and version
  agents/                             the four agents
  hooks/hooks.json                    rules and memory (SessionStart); gate, Bash guard, secret guard (PreToolUse)
  scripts/                            the hooks and the commands, in Python with no dependencies
    rules.py                          puts rules.md in context, and the migration notice
    memory.py                         /keel:memory and the SessionStart memory hook
    memory-secret-guard.py            refuses credentials written to memory
    critical-review-gate.py           the gate's briefing and pass count
    review-bash-guard.py              the read-only Bash inside the gate
    migrate.py                        /keel:migrate
  rules.md                            what goes into context at session start
  skills/coordinate-sessions/         skill, templates and references
  output-styles/direct.md             response style
  commands/migrate.md                 /keel:migrate
  commands/memory.md                  /keel:memory
```

To change something: edit it in `plugins/keel/`, bump `version` in `plugin.json` and push. Each script except `rules.py` and `critical-review-gate.py` has a self-test: `python3 plugins/keel/scripts/<script> --self-test`.

## License

[MIT](LICENSE).

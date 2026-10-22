---
name: coordinate-sessions
description: Method of the COORDINATOR session — open one `claude --bg` session per front or phase, build the prompt with the rules footer, talk by message, split resources, take decisions to the owner, resume a stalled session and close with a commit of only the session's work. Use ALWAYS when the owner asks to run fronts through sessions, "open sessions", "launch a session", "open the next phase", to coordinate the ones running, or to resume the stalled ones.
---

# Coordinate sessions

The coordinator does not implement the front: it writes the prompt, opens the session, hands out the turn on each
resource the machine has only one of, takes approvals and decisions to the owner, checks the commit against the report
and, with the owner's yes, pushes. Each front lives in its own session, with its own context, its own gate and its own
commit.

## 0. The project

The method is this file; the project comes in through three things, resolved at the start:

- **Checkout and name:** `CHECKOUT=$(git rev-parse --show-toplevel)`, `SLUG=$(basename "$CHECKOUT")`.
- **Coordination state**, outside the repo: `D=~/.claude/coordination/$SLUG/` (§3).
- **Project profile** (`profile.md`) — the session name prefix, the branch, the table of what exists only once, the
  commands for the proof levels, commit/push/PR, the deploy list, what is forbidden in production and where debt goes —
  and the **session rules** (`session.md`), the block that goes in every prompt after the global footer (§4). Look in
  this order and use the first folder that has both (`P_DIR`):
  1. `$CHECKOUT/.claude/coordination/` — versioned, applies to the whole team (project with more than one dev);
  2. `$D/profile/` — personal, outside the repo (a project that is only yours, or that should not carry a coordination
     file);
  3. none: **derive it yourself** before opening the first session, from the repo's `CLAUDE.md`, the risk doc it points
     to, `.claude/settings.json`, the lockfile/`package.json`/git hooks and `.husky/` or equivalent; write it to
     `$D/profile/` following [templates/profile.md](templates/profile.md) and ask the owner only what no file answers
     (working branch, whether there is another dev on the remote, who pushes, what is forbidden in production).
  Projects set up before the rename may still have `$CHECKOUT/.claude/coordenacao/` (`perfil.md`, `sessao.md`) and
  `$D/perfil/`: read them when the new ones are missing.
  **Read the whole profile before launching or resuming the first session.** What it says wins over this file.

Shell state does not survive from one Bash tool call to the next: resolve `CHECKOUT`, `SLUG`, `D` and `P_DIR` once and
use the literal paths in the following commands. Nothing here names a project; nothing in a session's prompt cites
another project.

## 1. Session, subagent or direct

| The work | Goes to | Why |
|---|---|---|
| Front or phase with its own commit, hours of work, several layers | **`--bg` session** | own context, gate and commit; does not bloat the coordinator |
| Wide reading, code map, "who calls" | `keel:explore` (subagent) | the coordinator only needs the synthesis |
| Web research | `keel:research` (subagent) | same |
| Short fix (≲ 5 files, one domain, no PRD phase), doc, memory, coordination tweak | **directly in the coordinator**, with the gate at the end if it touches critical risk | a new session costs the context baseline, the prompt, the skills and the gate; for little work it is more expensive and slower |

A subagent (Agent tool) dies with its answer, shares the context of whoever called it and has no gate of its own (the
`keel:critical-review` is one per session): a front never goes to a subagent. Agent teams (experimental) do not isolate
the worktree, do not resume and cost more: they do not replace `--bg` sessions in this method.

## 2. Launch, talk, resume, stop

**The binary.** `claude` may not be on the Bash tool shell's PATH. Find it and run the lines directly, without `bash -c`
(the security check blocks a script in `-c` that it cannot read):

```bash
C=$(command -v claude || ls ~/.local/bin/claude 2>/dev/null || ls -d ~/.vscode{,-server}/extensions/anthropic.claude-code-*/resources/native-binary/claude 2>/dev/null | sort -V | tail -1)
P=${CLAUDE_SKILL_DIR}/templates/background-session.settings.json
"$C" --bg -n <name> --settings "$P" --add-dir "$D" --permission-mode auto "$(cat "$D/logs/<name>.prompt.md")"
"$C" agents --json --cwd "$CHECKOUT"   # name, sessionId, state (busy, idle, working, blocked: waiting for permission or stopped)
"$C" logs <id|name>                    # recent output (raw TUI: filter the ANSI codes)
"$C" attach <id|name>                  # opens in the terminal (the owner answers a permission request here)
"$C" stop <id>                         # stops and keeps the conversation
"$C" --bg --resume <sessionId> -n <name> --settings "$P" --add-dir "$D" --permission-mode auto "<what changed and the next step>"
```

- **`--add-dir` is variadic:** always follow it with another option, or it swallows the prompt as a directory. It grants
  the session access to `$D` (HANDOFF and logs).
- **The lean profile goes on every launch, `--resume` included** (`--settings "$P"`): it removes from the background
  session what it never uses and would be reread on every call — Artifact, Workflow, ReportFindings, ScheduleWakeup,
  NotebookEdit, AskUserQuestion, the claude.ai connectors and the built-in skills in the listing. Measured: the baseline
  of each call dropped from 72k to 40k tokens ([references/context-baseline.md](references/context-baseline.md)).
  The project's skills stay. Decisions go to the coordinator by `SendMessage`.
- **Model and effort are inherited:** neither `--model` nor `--effort`, on any front, the critical-risk one included. The
  session is born at the effort its settings give its model: the level saved with `/effort` (per model, under
  `modelSettings`) or an `effortLevel` in the repo's settings; a top-level `effortLevel` in `~/.claude/settings.json`
  doesn't count for Opus 5.5 or newer, which then start at `medium`. `max` is only for the gate, through the frontmatter of
  `keel:critical-review`. Depth on a step is `ultrathink`. This rule holds by the file: an old copy of the skill in the
  context (or preserved by compaction) once ordered `--effort max` and opened four fronts at `max` (2026-10-16); before
  launching, check the command here.
- **In the checkout, no worktree to work in** when the profile says so (`"worktree": {"bgIsolation": "none"}` in the
  repo's settings). A session that asks "Call EnterWorktree first": the key is gone; take it to the owner, do not accept
  the worktree.
- **`NX_WORKSPACE_ROOT_PATH` inherited:** the background session is born with that of the daemon that opened it, which
  may belong to another checkout. Every `nx` of the session and of the proof carries
  `NX_WORKSPACE_ROOT_PATH=<checkout or worktree> NX_DAEMON=false`.
- **Name:** `<profile prefix>-<front>[-phase<n>]`, the same in the prompt, in `window.md` and in the report.
- **Talking:** `SendMessage` to the NAME; `ListAgents` shows the names, the coordinator's included (it changes with each
  session: check before building a prompt and warn the active ones if it changes). A message to an idle session wakes it
  and opens a turn that rereads its whole context: send only resource, decision and resume.
- **Knowing when it ended, without a loop or cron:** when launching, send the session a `SendMessage` with
  `notify_when_idle: true` (the notice arrives once when it goes idle or exits, without spending its tokens, and expires
  in 12 h; renew it when resuming). Cron only as a net when the notice is not possible, every 60 min, deleted when the
  last session closes. The cache keep-alive (§9) is a different cron, with no tool call.
- **Closed, stop it:** a session that delivered the final report and whose commit was checked exits with `"$C" stop <id>`.
  A closed session that stays `blocked` in the list confuses the next coordinator and the duplicate check.
- **New front, new session:** never send a second front to a session that already closed its own, nor reopen it by
  `--resume` for another front: it would reread the whole context of the previous one on every call. `--resume` is only
  to continue the SAME front.
- **Resuming** continues the same conversation; if it is still running, it opens a copy and warns. Before opening or
  resuming, check in `agents --json` that the owner has not already opened the same front.

## 3. The coordination state (`$D`)

| Path | What it is | Cap | Removed by the sweep |
|---|---|---|---|
| `queue.md` | **only what is open**: owner decisions and approvals still valid (literal, date, scope), active front, queue, owner pending items, the last line of each closed session (shas) | ~8 KB | never |
| `queue-archive/YYYY-MM.md` | the closed diary, moved out of `queue.md` when the delivery closes | never read whole; `grep` | after 90 days |
| `window.md` | **only the table** of who holds each resource that exists only once, and each one's queue | ~2 KB | never |
| `prompts/` | the front part of each session's prompt (§4); `_*.md` are shared blocks | | after 14 days; `_*.md` never |
| `logs/<session>/` | the assembled prompt and the long outputs, text only | | after 3 days |
| `handoff/<session>.md` | the HANDOFF the session maintains, for whoever resumes | | after 14 days |
| `handoff/coordinator.md` | the coordinator checkpoint (§9): decisions in progress, next step, live sessions with name and id | ~2 KB | never |

- If the state directory still has the old Portuguese names (`fila.md`, `fila-arquivo/`, `janela.md`,
  `handoff/coordenadora.md`), rename them with `mv` to `queue.md`, `queue-archive/`, `window.md` and
  `handoff/coordinator.md` before continuing, and tell the owner in one line.

**Cleanup is automatic:** at every session start the plugin's sweep hook removes, in every project's `$D`, what the
table marks, counted from the entry's last change. What stays at any age: what belongs to a session alive in
`agents --json` (when the list can't be read, age alone decides), and what `queue.md`, `window.md` or
`handoff/coordinator.md` cite by path (`logs/<name>`, `prompts/<name>`, `handoff/<name>`). So a tool, evidence or
generator that an open item still needs is cited by that path in `queue.md`; once the item closes and leaves it, the
file expires. Nobody deletes state by hand. The hook also removes the safety refs older than 14 days (§6) and prunes the
worktrees whose directory has been gone for 14 days.

The next coordinator reads `queue.md` and `window.md` — that is why they have a cap. When closing a delivery: its diary
goes to `queue-archive/`, `queue.md` keeps what is open, and the line of a returned resource leaves `window.md`.
A standing owner approval lives in the project memory, not in `queue.md`. Nothing in `$D` goes to git; what stays for
real goes to the front's PRD or doc and to memory.

## 4. A session's prompt

```bash
cat "$D/prompts/<front>.md" ${CLAUDE_SKILL_DIR}/templates/footer.md "$P_DIR/session.md" > "$D/logs/<name>.prompt.md"
```

In the assembled file replace `<COORDINATOR-NAME>`, `<SESSION-NAME>`, `<D>`, `<SKILL_DIR>` (= `${CLAUDE_SKILL_DIR}`) and the `<...>` of the front part. The front part
follows [templates/front.md](templates/front.md):

1. The owner's request **in their words**, with the date, and their decision or approval when there was one (literal text
   and scope). Implicit approval does not count.
2. The contract (PRD, plan, ADR) and the code map already checked by the coordinator, so the session does not
   rediscover them.
3. Numbered scope, with "decide and record the why" where there is a technical choice, and what is NOT in.
4. The skills of the layer (only those the front touches, and only the references of the topic), the project's
   critical-risk doc and only the reference of the domain touched, and the domain's memories.
5. The proof level (§7) and the measured gate; the close: single gate, fixes, commit (or "DO NOT COMMIT") and the report.
6. The decisions already made: the owner's literal answers to the questions raised before launch (below).

**Before launching, clear up every doubt.** The front runs with nobody watching: a doubt that only shows up midway
leaves it stalled or wakes the owner. When building the front part, list everything it may need to decide: acceptance
criterion, scope boundary, a design choice that changes the product, business rule, text the customer reads, and each
item that needs the owner's yes (database, backfill, mass script, secret/env, guard, production, push). Ask the owner
everything at once, through the question tool (up to 4 per call, the recommended one first). The answers go in literally,
with date and scope, in the prompt's decisions block and in `queue.md`. Launch only with the block closed; what could
not be foreseen follows the don't-block rule.

A decision that comes up midway, outside the block, goes back to the coordinator with the real case, the options and the
recommendation; it asks the owner through the question tool, with one option marked as recommended, and returns the
literal answer. These need the owner's yes BEFORE, always through the coordinator: what the project's profile and
`CLAUDE.md` list (database change, backfill, mass script, secret/env, business rule, a guard that blocks a response or
a sale, production). The session asks and proceeds with the rest.

## 5. What the machine and the branch have only one of

The tree is one, with WIP from other sessions and from the owner. The project's resource table is in the profile
(`$P_DIR/profile.md`); the principles always hold:

- **Git index and branch:** commit by temporary index (§6). Never stash, reset, checkout or restore of someone else's
  file, clean, `add -A`/`add .`.
- **Shared generator** (ORM client, build cache, Nx daemon, engine project): one at a time, with notice.
- **Dependencies** (`install`, lockfile): only with the window, with no suite running in another session.
- **The owner's servers:** do not stop or restart them; start another only with the window and the owner's yes.
- **Shared indexes** (i18n, `MEMORY.md`, `CLAUDE.md`, risk doc, skills, PRDs, barrels, routes): a targeted insertion
  reread at that moment, never rewrite from an old read; commit by hunk or by key.

The coordinator grants and records it in `window.md`.

## 6. Commit, proof and push

- **The session commits** only what is its own, after the gate, in the mode the profile declares
  ([references/commit-by-index.md](references/commit-by-index.md), with the holes already paid for):
  - **direct** — the front session is the only one alive and the tree has no one else's WIP on its paths: proof in the
    tree itself and `git commit -m "<msg>" -- <explicit list>` (the `--` with paths takes only those, even with
    something else staged). It is the fastest: one round of proof, no worktree.
  - **split** — there is another live session or someone else's WIP: temporary index + `commit-tree`, proof in a clean
    worktree at the sha and `update-ref` with CAS over the checked parent.
  Message: the project's commit rule, one line, no body, no trailer, no co-authoring, no amend.
- **One round of proof per level** (§7): in split mode, what already ran in the tree before the gate is not repeated in
  the worktree, except at level C.
- **Safety point before a rebase or any history rewrite:** a ref, never a branch:
  `git update-ref refs/keel/backup/<YYYY-MM-DD>-<what> HEAD`. It does not show in `git branch`, and the sweep removes it
  after 14 days; delete it earlier with `git update-ref -d` once the result is checked.
- **The push is the coordinator's, with the owner's yes**, after `git show --stat <sha>` against the report, by the path
  the profile describes (where to push from, hook, remote). Never `--no-verify` without the owner's word. PR, CI, merge
  and deploy: what the profile says; merge and deploy are the owner's.
- **No critical risk touched** (maintenance, `.claude/`, docs, memory, tests, or ordinary behavior): does not go through
  the gate.

## 7. Proof by risk

The coordinator puts the level in the prompt. The session raises the level when it sees it touches more, and never
lowers it. The commands of each level are in the profile.

| Level | When | Before the gate (in the tree) | In the commit worktree |
|---|---|---|---|
| **P** | text, one number, a screen tweak, a fix to one function; nothing critical | the tests of what changed and the lint of the files | the pre-push hook (or the profile's equivalent) and only the suites touched |
| **M** | ordinary front or phase | same | the pre-push and the suites of the affected projects |
| **C** | critical-risk domain, core with parity | the suites of the affected | the suites of the affected again (the gate may have changed the code) and the probes the profile asks for |

No doubled rounds and no whole suite that the level does not ask for.

## 8. What the coordinator checks on its own

The git state (branch, `git log`, nothing staged in the shared index by whoever committed), the report against the code
(every "done" is checked by the count in the log, not rerun), the owner's approvals against what the session did, and
the profile's deploy list. Production: only what the profile allows, read-only, only a count or id, never PII or secret.

**A gate that died midway:** the hook asks the owner to confirm the 2nd call to `keel:critical-review` in the session.
If the 1st dropped with no report, the owner confirms through `attach`, or authorizes closing the session and opening
another that continues from the HANDOFF and runs the gate once. Never work around it without the owner's word.

## 9. Coordination economy

Each call rereads the whole context, the coordinator's included. What fills it: skills invoked whole, raw Bash output,
messages between sessions and state files with no cap.

- **One front session at a time**, unless the owner asks otherwise; the next opens when the previous one has committed.
- **Coordinator checkpoint and `/clear`:** at the end of each round (the fronts of the moment closed, or run with the
  requested notice) and always when closing a delivery (commit and push), the coordinator updates `queue.md` and
  `window.md` (§3) and `handoff/coordinator.md`, and warns the owner in one line: "state saved; you can `/clear` and
  resume with `/keel:coordinate-sessions`". The `/clear` is the owner's command: it does not wait for it to proceed. The
  front session does not need this: it is born clean and exits with the `stop` (§2).
- **Checkpoint earlier, without waiting for the round:** the cost of every call and of every cache miss grows with the
  coordinator's context, so it does not wait for the round to close when the context is already heavy. After an
  automatic compaction, or once three fronts have closed since the last `/clear`, it saves the checkpoint at the next
  quiet point (no question open with the owner, no gate or commit being checked) and gives the same one-line notice,
  even with fronts still live. The resume renews each live session's `notify_when_idle` (next bullet), so nothing is
  lost.
- **Keeping the coordinator's cache warm while a front runs:** each call reads the whole context from the prompt cache.
  In Claude Code the cache lives 1 h (5 min when the account is in usage overage), and every read restarts the timer at
  no extra cost. A front often runs longer than that with the coordinator idle, so the call that handles the front's
  notice pays a cold rewrite of the whole context: 2× the input price (the 1-hour write). A cache read costs 0.05× on
  Opus 5.5, 0.1× on most models and 0.025× on Fable 5.1. One miss therefore pays for 20 to 80 keep-alive turns, which is
  10 to 40 hours at a 30-minute cadence.
  1. When it launches the first front, the coordinator arms one recurring `CronCreate` with `cron: "13,43 * * * *"`
     and the prompt `keel keep-alive: reply only "ok", with no tool call.`. Use 30 minutes, not 50 or 60: cron cannot
     express a 50-minute period, a 60-minute gap leaves no margin over the TTL, and the scheduler shifts each job by a
     fixed offset.
  2. The tick runs no tool: each tool call is another full read of the context. A tick that lands while the
     coordinator is busy waits for idle, and the cache is already warm then.
  3. The coordinator deletes the cron (`CronDelete`) when the last live front is stopped, before the `/clear` notice,
     and before the relay of an autonomous run. The successor arms its own when it takes over with fronts live.
  4. Limits:
     - in usage overage the TTL drops to 5 min, and the tick no longer prevents the miss (the coordinator cannot see
       this; accept it);
     - the cron lives only in the open session and expires after 7 days;
     - with no live front, there is no cron.
- **Resuming after the `/clear`** (or in a new coordinator): read the profile, `queue.md`, `window.md` and
  `handoff/coordinator.md`, not the previous conversation; check the live sessions in `agents --json` and renew the
  `notify_when_idle` of each (the notice requested before the `/clear` may not arrive), arm the cache keep-alive
  (below) when one is live; if the coordinator's name changed, warn the active ones.
- **Autonomous run (nobody supervising for hours): relay instead of `/clear`.** The coordinator runs as a background
  session, `<prefix>-coord-<n>`, opened with the same command as the fronts (§2) and the prompt "run the
  keel:coordinate-sessions skill and resume coordination; autonomous run, relay on". In the terminal it could not stop
  itself, and pending notices would wake it. At the end-of-round checkpoint, in place of the `/clear` notice:
  1. it writes the checkpoint (§3);
  2. it opens the successor `<prefix>-coord-<n+1>` with the same command and the same prompt;
  3. it checks in `agents --json` that it is alive;
  4. it ends itself with `"$C" stop <its own id, found by name in the same JSON>` and does nothing more.
  The successor follows "Resuming after the `/clear`" and sends the new name to each live session, with
  `notify_when_idle`. Measured on 2026-10-20: the successor is born and takes over, the old one leaves the list, and the
  front answers the new one by name. In the autonomous run nobody answers questions: the doubts of all the foreseen
  fronts are cleared before releasing the run (§4); what comes up afterwards goes to the owner's pending items in
  `queue.md`, and the coordinator moves on to another front.
- **Messages only for resource, decision and report.** Progress goes to the HANDOFF; the coordinator reads it when it
  needs to.
- **Long output to a file** (`$D/logs/<session>/`), only the summary in the context (`tail -n 5`, the grep of the count
  and the failures).
- **A skill comes in through its core** and only through the references of the topic; after compaction, only the first
  20k characters of each invoked skill come back, up to about 100k in total, and the one the next step
  asks for is reinvoked.
- **Reading goes to `keel:explore`, writing the isolable and non-critical to `keel:implement`;** critical risk and
  running the suites stay in the session.

# Coordination profile — <project>

What this project adds to the method of the global skill `coordinate-sessions`. The skill is the method; this file wins
where they diverge. The rules that go into every prompt are in `session.md`, next to it. Derived from: <CLAUDE.md,
settings, hooks…>, on <date>; what came from the owner is marked with the date and the literal text.

## Identity

- Checkout: `<path>`, branch `<working branch>`, <no new branch | branch per front>, <no worktree to work in (`worktree.bgIsolation: none`) | worktree per session>.
- Coordination state: `~/.claude/coordination/<slug>/`. Session names: `<prefix>-<front>[-phase<n>]`.
- How many front sessions at the same time: <1, owner's rule | N>.
- Front contract: <PRDs, plans, ADRs — where they live>. Tasks: <ClickUp/Jira/none, and who writes>.
- Memory: <`.claude/memory/<dev>/`, one folder per developer, auto memory linked by `/keel:memory` | where else it lives>.
- Critical risk: <doc or skill, and whether it has references per domain>.

## Commit

<direct | split> mode (skill §6 and `references/commit-by-index.md`), with these project steps: <sync with the
remote first? generate a file that only the tool writes?>. Message: <commitlint rule, language>.

## Proof (commands of each level, skill §7)

- Focused test: `<command>`. Suite of one project: `<command>`. Lint/typecheck: `<command>`. Pre-push hook: `<command>`.
- P: <…>. M: <…>. C: <…>, plus the probes of the verification environment in the risk doc.

## What the machine and the branch have only one of

| Resource | Why there is only one | Rule |
|---|---|---|
| Git index and branch | `.git/index` is one for everybody | the mode in §Commit |
| <generator: ORM client, build cache, engine project> | <…> | <…> |
| <dependencies: install, lockfile> | rewrite everybody's environment | only with the window |
| <the owner's servers and ports> | <…> | <…> |
| <shared indexes: i18n, MEMORY.md, CLAUDE.md, risk doc, barrels> | several sessions in the same file | surgical insertion reread on the spot; commit per hunk |

## Owner approval first, always through the coordinator

<database change, backfill, bulk script, secret/env, business rule, guard, production — what CLAUDE.md lists>.

## Push, PR and deploy

- Push: <who, from where (worktree at the sha or clean checkout), hook, remote>. PR: <to where; CI>. Merge and deploy: <the owner's>.
- Deploy list: <migrations, envs, templates, infra, order>.

## Production

<what is allowed: read-only, count/id only, never PII or secret>.

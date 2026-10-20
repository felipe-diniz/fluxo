# Commit by temporary index, proof in the worktree and publishing

Recipe to commit only what belongs to the session in a split tree, without touching the shared `.git/index` (checked on
2026-10-05 in a throwaway repository: the commit takes only the session's lines, another session's staged content stays
intact). What belongs to the project (pre-push hook, suites, remote, syncing with the remote first) is in the
project profile (`$P_DIR/profile.md`, skill §0) and in the session rules.

Shell state does not carry over from one Bash tool call to the next: note `OLD` and `NEW` and use the literal shas in the
following steps. The safety check blocks `rm` over a variable: literal paths.

## Direct mode (single session, no foreign WIP in your paths)

```bash
cd <checkout> && git branch --show-current && git status --short      # check: nothing foreign in your paths
<the proof-level commands, from the profile, on the tree itself, output to a file>
git commit -m "<type>(<scope>): <message>" -- <explicit list>     # with paths, takes only them, even with other staged
git show --stat HEAD && git branch --show-current
```

A file that shows up in the tree and is not yours: do not touch it, do not commit it, tell the coordinator; if it is in
your paths, switch to split mode. Never `git add -A`/`.` nor `git commit -a`.

## Split mode

### Step 1 — build the commit without touching the branch

```bash
set -e
cd <checkout> && git branch --show-current && OLD=$(git rev-parse HEAD) && echo "OLD=$OLD"
export GIT_INDEX_FILE=$PWD/.git/index-<session-name>
git read-tree "$OLD"
git add -- <files entirely from the session>
# mixed file: HEAD + only the session's lines
BLOB=$(<generate the HEAD version + the session's lines> | git hash-object -w --stdin)
git update-index --cacheinfo 100644,"$BLOB",<path>
NEW=$(git commit-tree "$(git write-tree)" -p "$OLD" -m "<type>(<scope>): <message>") && echo "NEW=$NEW"
unset GIT_INDEX_FILE; rm -f .git/index-<session-name>
```

Atomic commits in series: each `commit-tree` with `-p` on the previous one, a single `update-ref` at the end.

### Step 2 — the proof in a clean worktree at `NEW`, before the `update-ref`

In the split tree, another session's file makes pass what fails in a clone; and another session pushing the HEAD would
carry along a commit not yet proven.

```bash
git worktree add --detach <scratchpad>/proof <NEW> && ln -s <checkout>/node_modules <scratchpad>/proof/node_modules
cd <scratchpad>/proof && export NX_DAEMON=false NX_WORKSPACE_ROOT_PATH=$PWD   # without this nx runs against the main tree
<the proof-level commands, from the profile>
cd <checkout> && rm <scratchpad>/proof/node_modules && git worktree remove <scratchpad>/proof   # the symlink goes first, never rm -r
```

### Step 3 — publish to the local branch, only with the proof green

```bash
git branch --show-current                         # the same as before
test "$(git rev-parse <NEW>^)" = "$(git rev-parse HEAD)"   # the commit's parent is the current HEAD
git update-ref refs/heads/<branch> <NEW> <OLD>    # CAS: fails if HEAD moved; redo step 1 over the new one
git restore --staged -- <the same paths>      # aligns the shared index to the new HEAD, only in those paths
```

## The holes already paid for

- **The `<OLD>` of the `update-ref` is the parent of the new commit, checked.** A commit built before the gate, over a
  branch that moved during it, passed with the current HEAD, goes in and wipes the commits in the middle from the branch
  (2026-10-08).
- **The path list is checked by length before the `git add`:** a list read from the wrong path gives zero iterations and
  a silently incomplete commit.
- **The commit is checked blob by blob against the tree**, not by `git diff <sha>`.
- **After the `update-ref`, the shared index still has the old versions** of the session's files: step 3 aligns only
  those paths.
- **A generated file that only the tool writes** (the engine script's `.uid`, the ORM client) is generated in the proof
  worktree and committed along, when the project versions it.
- **A new worktree may run the install by itself** on the package manager's first command (from the store, no download):
  count on it before timing anything.
- **The ORM client comes from the checkout's `node_modules`:** with the schema changed by another session and not
  committed, the proof may diverge; say so in the report.

## Push (the coordinator's, with the owner's yes)

The pre-push hook runs in the tree you push from: from the checkout, another session's WIP brings the hook down (or
approves it). Push from a proof worktree at the sha. If the hooks directory is generated and not versioned (e.g.
`.husky/_`), the hook does not exist in the worktree and a push without `-c core.hooksPath=<checkout>/<hooks dir>` skips
the gate silently (2026-10-05). Never `--no-verify` without the owner's word. The project's exact command is in the profile.

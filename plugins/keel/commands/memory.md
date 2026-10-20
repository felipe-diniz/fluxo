---
description: Version the agent's memory in this repo, one folder per developer (.claude/memory/<dev>/), with no index loaded twice
allowed-tools: Bash(python3 *), Bash(claude agents *)
disable-model-invocation: true
---

1. Run `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/memory.py"` (add `--dev <name>` if the user gave one) and show the user the plan as it came.
2. If it says there is nothing to do, stop there. If it is blocked, say what unblocks it and stop.
3. If the developer folder came "suggested from the git user", confirm the name with the user, the suggestion first as the recommended option. The confirmed name goes in `--dev` from here on.
4. If the user doesn't want versioned memory in this project, run it with `--decline` and stop.
5. Before applying, run `claude agents --json --cwd "<repo root>"`. Another active session in this repo besides this one would race the move: name it and ask whether to wait.
6. Ask whether to apply. Only with a yes, run it again with `--apply` (and the same `--dev`), and show the result.
7. Then update the references the plan listed (paths of the old single folder), and the memory section of the project's CLAUDE.md, in that file's language: memory lives in `.claude/memory/<dev>/`, one folder per developer; each writes only in their own; and no `@` import of any `MEMORY.md` (auto memory loads your own, the plugin injects the others').
8. Commit `.claude/memory` and those files, by path, in one commit of their own, following the project's commit convention. No push.

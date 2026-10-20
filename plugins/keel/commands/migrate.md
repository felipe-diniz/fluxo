---
description: Remove what duplicates keel (the agents, hooks, skill and rules copied by hand before the plugin) so only the plugin applies
allowed-tools: Bash(python3 *)
disable-model-invocation: true
---

1. Run `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/migrate.py"` and show the user the plan as it came.
2. If the plan says there is nothing to migrate, stop there.
3. Ask whether to apply it. Only with a yes, run `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/migrate.py" --apply` and show the result.
4. Remind the user that it applies from the next session on, and where the backup is.

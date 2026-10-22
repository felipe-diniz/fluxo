---
description: Turn keel's background auto-update on or off, or show where it stands (on by default after the first session)
argument-hint: "[on|off|status]"
allowed-tools: Bash(python3 *)
disable-model-invocation: true
---

1. Run `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/auto-update.py" $ARGUMENTS` (no argument: `status`) and show the result as it came.
2. After `on` or `off`, remind the user that it applies from the next session on.

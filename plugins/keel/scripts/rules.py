#!/usr/bin/env python3
"""SessionStart: puts keel's rules into context (a plugin doesn't load a CLAUDE.md).

It also runs after compaction (source "compact"), so the rules come back into context. The output is capped at 10,000
characters: rules.md has to fit, with room for the notice. When something duplicates the plugin (a manual install
from before it, or the plugin under its old name), it adds a line asking for /keel:migrate. An internal failure
stays quiet.
"""
import os
import sys

try:
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    with open(os.path.join(root, "rules.md"), encoding="utf-8") as rules:
        sys.stdout.write(rules.read())
    sys.path.insert(0, os.path.join(root, "scripts"))
    import migrate

    if migrate.has_work(migrate.plan()):
        sys.stdout.write(
            "\nPLUGIN NOTICE: something duplicates keel (a manual install from before the plugin, or the plugin "
            "under its old name, fluxo). In the first reply, suggest the user run /keel:migrate.\n"
        )
except Exception:
    pass

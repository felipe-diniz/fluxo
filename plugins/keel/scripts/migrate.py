#!/usr/bin/env python3
"""Removes what duplicates the keel plugin, so the plugin works alone.

What goes, with a backup in ~/.claude/backups/keel-<date>/:
- user agents with the plugin's agent names (explore, implement, research, critical-review) in ~/.claude/agents/;
- the hooks copied by hand into ~/.claude/hooks/ (critical-review-gate.py, review-bash-guard.py) and their entries in
  ~/.claude/settings.json;
- the personal skill ~/.claude/skills/coordenar-sessoes;
- from ~/.claude/CLAUDE.md, only the sections the manual install copied: the old Portuguese titles, with "Princípios
  gerais" and "Compact Instructions" only beside one of the other three (and the <!-- fluxo:inicio --> block of old
  versions). The rest of the file stays;
- the old setup-version stamp.

No argument: only shows the plan. `--apply`: runs it. `--self-test`: runs the scenarios in a temporary home.
"""
import datetime
import json
import os
import re
import shutil
import sys
import tempfile

AGENT_NAMES = {"explore", "implement", "research", "critical-review"}
HOOK_FILES = ("critical-review-gate.py", "review-bash-guard.py")
LEGACY_SKILL = "coordenar-sessoes"
STAMP = ".fluxo-setup-version"
OLD_BLOCK = re.compile(r"<!-- fluxo:inicio[^>]*-->.*?<!-- fluxo:fim -->\n?", re.DOTALL)
# The rules' section titles as the manual install copied them, always the five together. The two generic ones only
# count beside a specific one: a user may have a section of their own with that title.
SPECIFIC_HEADINGS = (
    "# Risco crítico (contrato por projeto)",
    "# Roteamento de agentes",
    "# Gate de pré-commit (subagent `critical-review`)",
)
GENERIC_HEADINGS = ("# Princípios gerais", "# Compact Instructions")


def home():
    return os.path.expanduser(os.environ.get("CLAUDE_CONFIG_DIR") or "~/.claude")


def read(path):
    try:
        with open(path, encoding="utf-8") as handle:
            return handle.read()
    except (OSError, UnicodeDecodeError):
        return None


def read_json(path):
    try:
        data = json.loads(read(path) or "{}")
    except ValueError:
        return {}
    return data if isinstance(data, dict) else {}


def agent_name(text):
    match = re.match(r"---\n(.*?)\n---", text, re.DOTALL)
    if not match:
        return None
    found = re.search(r"(?m)^name:\s*['\"]?([^'\"\n]+)", match.group(1))
    return found.group(1).strip().lower() if found else None


def legacy_agents():
    folder = os.path.join(home(), "agents")
    if not os.path.isdir(folder):
        return []
    paths = []
    for file_name in sorted(os.listdir(folder)):
        path = os.path.join(folder, file_name)
        if file_name.endswith(".md") and agent_name(read(path) or "") in AGENT_NAMES:
            paths.append(path)
    return paths


def legacy_hooks():
    return [path for path in (os.path.join(home(), "hooks", name) for name in HOOK_FILES) if os.path.isfile(path)]


def legacy_skill():
    path = os.path.join(home(), "skills", LEGACY_SKILL)
    return path if os.path.isdir(path) else None


def mentions_legacy_hook(hook):
    text = json.dumps(hook)
    return any(name in text for name in HOOK_FILES)


def without_legacy_hooks(events):
    cleaned, removed = {}, 0
    for event, groups in events.items():
        if not isinstance(groups, list):
            cleaned[event] = groups
            continue
        kept = []
        for group in groups:
            hooks = group.get("hooks") if isinstance(group, dict) else None
            if not isinstance(hooks, list):
                kept.append(group)
                continue
            remaining = [hook for hook in hooks if not mentions_legacy_hook(hook)]
            removed += len(hooks) - len(remaining)
            if remaining:
                kept.append(dict(group, hooks=remaining))
        if kept or not groups:
            cleaned[event] = kept
    return cleaned, removed


def cleaned_settings():
    path = os.path.join(home(), "settings.json")
    text = read(path)
    try:
        settings = json.loads(text) if text else None
    except ValueError:
        return None
    if not isinstance(settings, dict):
        return None
    changes = []
    if isinstance(settings.get("hooks"), dict):
        events, removed = without_legacy_hooks(settings["hooks"])
        if removed:
            changes.append("{} hook entr{} of the manual install".format(removed, "y" if removed == 1 else "ies"))
            if events:
                settings["hooks"] = events
            else:
                del settings["hooks"]
    if not changes:
        return None
    return path, json.dumps(settings, ensure_ascii=False, indent=2) + "\n", changes


def normalize(heading):
    # Copies said `critical-review`, `fluxo:critical-review` or `keel:critical-review`.
    return heading.strip().replace("keel:", "").replace("fluxo:", "")


def cleaned_claude_md():
    path = os.path.join(home(), "CLAUDE.md")
    text = read(path)
    if not text:
        return None
    had_block = bool(OLD_BLOCK.search(text))
    sections = re.split(r"(?m)^(?=# )", OLD_BLOCK.sub("", text))
    titles = [normalize(section.splitlines()[0]) if section.startswith("# ") else None for section in sections]
    duplicated = {normalize(heading) for heading in SPECIFIC_HEADINGS}
    if duplicated & set(titles):
        duplicated |= {normalize(heading) for heading in GENERIC_HEADINGS}
    kept, removed = [], []
    for section, title in zip(sections, titles):
        if title in duplicated:
            removed.append(section.splitlines()[0].strip())
        else:
            kept.append(section)
    if not removed and not had_block:
        return None
    new = "".join(kept).strip("\n")
    return path, (new + "\n" if new else ""), removed or ["the old <!-- fluxo:inicio --> block"]


def plan():
    stamp = os.path.join(home(), STAMP)
    return {
        "agents": legacy_agents(),
        "hooks": legacy_hooks(),
        "skill": legacy_skill(),
        "settings": cleaned_settings(),
        "claude_md": cleaned_claude_md(),
        "stamp": stamp if os.path.isfile(stamp) else None,
    }


def has_work(steps):
    return any(steps.values())


def print_plan(steps, applying):
    print("keel migration: {}".format("applying" if applying else "plan (nothing was written; run with --apply)"))
    for path in steps["agents"]:
        print("- move to the backup the user agent {} (the plugin ships keel:{})".format(
            path, agent_name(read(path) or "")))
    for path in steps["hooks"]:
        print("- move to the backup the hook {} (the plugin registers its own)".format(path))
    if steps["skill"]:
        print("- move to the backup the personal skill {} (the plugin ships keel:coordinate-sessions)".format(
            steps["skill"]))
    if steps["settings"]:
        print("- in {}: {}".format(steps["settings"][0], "; ".join(steps["settings"][2])))
    if steps["claude_md"]:
        print("- remove from {} the sections the plugin already loads: {}".format(
            steps["claude_md"][0], "; ".join(steps["claude_md"][2])))
    if steps["stamp"]:
        print("- delete the old version stamp {}".format(steps["stamp"]))


def apply(steps):
    backup = os.path.join(home(), "backups", "keel-" + datetime.datetime.now().strftime("%Y%m%d-%H%M%S"))

    def move_to_backup(path):
        destination = os.path.join(backup, os.path.relpath(path, home()))
        os.makedirs(os.path.dirname(destination), exist_ok=True)
        shutil.move(path, destination)

    def rewrite(path, content):
        destination = os.path.join(backup, os.path.relpath(path, home()))
        os.makedirs(os.path.dirname(destination), exist_ok=True)
        shutil.copy2(path, destination)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(content)

    for path in steps["agents"] + steps["hooks"]:
        move_to_backup(path)
    if steps["skill"]:
        move_to_backup(steps["skill"])
    if steps["settings"]:
        rewrite(steps["settings"][0], steps["settings"][1])
    if steps["claude_md"]:
        rewrite(steps["claude_md"][0], steps["claude_md"][1])
    if steps["stamp"]:
        move_to_backup(steps["stamp"])
    return backup if os.path.isdir(backup) else None


def main():
    args = sys.argv[1:]
    if "--self-test" in args:
        sys.exit(self_test())
    steps = plan()
    applying = "--apply" in args
    if not has_work(steps):
        print("Nothing to migrate: nothing duplicates the keel plugin.")
        return
    print_plan(steps, applying)
    if not applying:
        return
    backup = apply(steps)
    print("Done.{} Start a new session for only the plugin to apply.".format(
        " Backup: {}.".format(backup) if backup else ""))


def self_test():
    failures = []

    def check(name, condition):
        if not condition:
            failures.append(name)

    sandbox = tempfile.mkdtemp(prefix="keel-migrate-")
    saved = {key: os.environ.get(key) for key in ("CLAUDE_CONFIG_DIR",)}

    def put(path, content):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(content)

    def fresh_home(name):
        os.environ["CLAUDE_CONFIG_DIR"] = os.path.join(sandbox, name)
        os.makedirs(home())
        return home()

    try:
        # 1. Nothing installed: no work, and a CLAUDE.md with only the user's sections stays untouched, even with
        # generic titles like the plugin's.
        root = fresh_home("empty")
        put(os.path.join(root, "CLAUDE.md"), "# Commits\n\n- mine\n\n# General principles\n\n- mine\n\n"
                                             "# Princípios gerais\n\n- mine\n\n# Compact Instructions\n\n- mine\n\n\n")
        check("empty: no work", not has_work(plan()))

        # 2. Manual install: agents, hooks, skill, settings entries and the CLAUDE.md sections go, the rest stays.
        root = fresh_home("manual")
        put(os.path.join(root, "agents", "explore.md"), "---\nname: Explore\n---\nbody\n")
        put(os.path.join(root, "agents", "mine.md"), "---\nname: mine\n---\nbody\n")
        put(os.path.join(root, "hooks", "critical-review-gate.py"), "x\n")
        put(os.path.join(root, "skills", LEGACY_SKILL, "SKILL.md"), "x\n")
        put(os.path.join(root, "settings.json"), json.dumps({"hooks": {"PreToolUse": [
            {"matcher": "Agent", "hooks": [{"type": "command", "command": "python3 ~/.claude/hooks/critical-review-gate.py"}]},
            {"matcher": "Bash", "hooks": [{"type": "command", "command": "my-hook.sh"}]},
        ]}, "theme": "dark"}))
        put(os.path.join(root, "CLAUDE.md"), "# Princípios gerais\n\n- old\n\n# Commits\n\n- mine\n\n"
                                             "# Roteamento de agentes\n\n- old\n\n"
                                             "# Gate de pré-commit (subagent `fluxo:critical-review`)\n\n- old\n\n"
                                             "# Compact Instructions\n\n- old\n")
        steps = plan()
        check("manual: plan", steps["agents"] == [os.path.join(root, "agents", "explore.md")] and steps["hooks"]
              and steps["skill"] and steps["settings"] and steps["claude_md"])
        backup = apply(steps)
        settings = read_json(os.path.join(root, "settings.json"))
        check("manual: settings keep the user's hook", settings.get("theme") == "dark" and [
            group["matcher"] for group in settings["hooks"]["PreToolUse"]] == ["Bash"])
        check("manual: CLAUDE.md keeps the user's section", read(os.path.join(root, "CLAUDE.md")) == "# Commits\n\n- mine\n")
        check("manual: moved to the backup", backup and os.path.isfile(os.path.join(backup, "agents", "explore.md"))
              and not os.path.exists(os.path.join(root, "agents", "explore.md"))
              and os.path.isfile(os.path.join(root, "agents", "mine.md")))
        check("manual: nothing left", not has_work(plan()))
    finally:
        for key, value in saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        shutil.rmtree(sandbox, ignore_errors=True)

    print("{} failure(s){}".format(len(failures), ": " + "; ".join(failures) if failures else ""))
    return 1 if failures else 0


if __name__ == "__main__":
    main()

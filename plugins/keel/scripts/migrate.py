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
- the old setup-version stamp;
- the plugin under its old name, `fluxo@fluxo`, and its marketplace (user scope), through `claude plugin`. The
  marketplace stays while another plugin installed from it remains (keel itself, as `keel@fluxo`). Without the CLI on
  the PATH, the old plugin is disabled in ~/.claude/settings.json and the commands are printed.

No argument: only shows the plan. `--apply`: runs it. `--self-test`: runs the scenarios in a temporary home.
"""
import datetime
import json
import os
import re
import shutil
import subprocess
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
OLD_PLUGIN = "fluxo@fluxo"
OLD_MARKETPLACE = "fluxo"


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


def cleaned_settings(disable_old_plugin):
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
    enabled = settings.get("enabledPlugins")
    if disable_old_plugin and isinstance(enabled, dict) and enabled.get(OLD_PLUGIN):
        enabled[OLD_PLUGIN] = False
        changes.append("disable {}".format(OLD_PLUGIN))
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


def old_plugin():
    plugins = read_json(os.path.join(home(), "plugins", "installed_plugins.json")).get("plugins")
    plugins = plugins if isinstance(plugins, dict) else {}
    installs = [entry for entry in plugins.get(OLD_PLUGIN) or [] if isinstance(entry, dict)]
    settings = read_json(os.path.join(home(), "settings.json"))
    switches = settings.get("enabledPlugins")
    switches = switches if isinstance(switches, dict) else {}
    enabled = bool(switches.get(OLD_PLUGIN))
    extra = settings.get("extraKnownMarketplaces")
    marketplace = (OLD_MARKETPLACE in read_json(os.path.join(home(), "plugins", "known_marketplaces.json"))
                   or isinstance(extra, dict) and OLD_MARKETPLACE in extra)
    # Other plugins from the old marketplace, keel itself among them when it came as `keel@fluxo`: removing the
    # marketplace would uninstall them.
    staying = sorted(key for key in set(plugins) | {key for key, on in switches.items() if on}
                     if key.endswith("@" + OLD_MARKETPLACE) and key != OLD_PLUGIN)
    if not (installs or enabled or marketplace):
        return None
    return {"installs": installs, "enabled": enabled, "marketplace": marketplace, "staying": staying}


def old_plugin_commands(old):
    """`claude plugin` commands that remove the old plugin, each with the folder to run it in (None = anywhere)."""
    commands, seen = [], set()
    for install in old["installs"] or ([{"scope": "user"}] if old["enabled"] else []):
        scope = install.get("scope") or "user"
        folder = None if scope == "user" else install.get("projectPath") or ""
        if (scope, folder) not in seen:
            seen.add((scope, folder))
            commands.append((["claude", "plugin", "uninstall", OLD_PLUGIN, "--scope", scope], folder))
    if old["marketplace"] and not old["staying"]:
        # Without a scope it would also leave the project settings of the folder it runs in.
        commands.append((["claude", "plugin", "marketplace", "remove", OLD_MARKETPLACE, "--scope", "user"], None))
    return commands


def plan():
    old = old_plugin()
    cli = shutil.which("claude")
    stamp = os.path.join(home(), STAMP)
    return {
        "agents": legacy_agents(),
        "hooks": legacy_hooks(),
        "skill": legacy_skill(),
        "settings": cleaned_settings(disable_old_plugin=bool(old and old["enabled"] and not cli)),
        "claude_md": cleaned_claude_md(),
        "stamp": stamp if os.path.isfile(stamp) else None,
        "old_plugin": old_plugin_commands(old) if old else [],
        "kept_marketplace": old["staying"] if old and old["marketplace"] else [],
        "cli": cli,
    }


def has_work(steps):
    # A marketplace kept for keel@fluxo is a note in the plan, not work: keel runs fine from it.
    return any(value for key, value in steps.items() if key not in ("cli", "kept_marketplace"))


def describe(command, folder):
    where = " (in {})".format(folder) if folder else (" (in the project it was installed for)" if folder == "" else "")
    return "`{}`{}".format(" ".join(command), where)


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
    for command, folder in steps["old_plugin"]:
        verb = "run" if steps["cli"] and folder is None else "the user runs, in a terminal,"
        print("- remove keel's old name: {} {}".format(verb, describe(command, folder)))
    if steps["kept_marketplace"]:
        print("- " + kept_marketplace_note(steps))


def kept_marketplace_note(steps):
    staying = ", ".join(steps["kept_marketplace"])
    return ("keep the marketplace `{0}`: {1} still come(s) from it. To move keel to its own, in a terminal: "
            "`claude plugin marketplace add felipe-diniz/keel`, `claude plugin install keel@keel`, then uninstall {1} "
            "and run `claude plugin marketplace remove {0} --scope user`".format(OLD_MARKETPLACE, staying))


def apply(steps):
    backup = os.path.join(home(), "backups", "keel-" + datetime.datetime.now().strftime("%Y%m%d-%H%M%S"))
    report, pending = [], []

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
    # Files first: `claude plugin` rewrites settings.json itself, and the plan's copy would undo it.
    if steps["settings"]:
        rewrite(steps["settings"][0], steps["settings"][1])
    if steps["claude_md"]:
        rewrite(steps["claude_md"][0], steps["claude_md"][1])
    if steps["stamp"]:
        move_to_backup(steps["stamp"])
    for command, folder in steps["old_plugin"]:
        if not steps["cli"] or folder is not None and not os.path.isdir(folder):
            pending.append(describe(command, folder))
            continue
        try:
            result = subprocess.run([steps["cli"]] + command[1:], cwd=folder, capture_output=True, text=True,
                                    timeout=120)
            output = (result.stdout + result.stderr).strip().replace("\n", " ")
            ok = result.returncode == 0
        except (OSError, subprocess.SubprocessError) as error:
            output, ok = str(error), False
        report.append("{}: {}".format(describe(command, folder), "done" if ok else "failed ({})".format(output[:300])))
        if not ok:
            pending.append(describe(command, folder))
    return report, pending, backup if os.path.isdir(backup) else None


def main():
    args = sys.argv[1:]
    if "--self-test" in args:
        sys.exit(self_test())
    steps = plan()
    applying = "--apply" in args
    if not has_work(steps):
        print("Nothing to migrate: nothing duplicates the keel plugin.")
        if steps["kept_marketplace"]:
            print("Note: " + kept_marketplace_note(steps))
        return
    print_plan(steps, applying)
    if not applying:
        return
    report, pending, backup = apply(steps)
    for line in report:
        print("- " + line)
    if pending:
        print("Still to do by hand, in a terminal (or in /plugin): " + "; ".join(pending))
    print("Done.{} Start a new session for only the plugin to apply.".format(
        " Backup: {}.".format(backup) if backup else ""))


def self_test():
    failures = []

    def check(name, condition):
        if not condition:
            failures.append(name)

    sandbox = tempfile.mkdtemp(prefix="keel-migrate-")
    saved = {key: os.environ.get(key) for key in ("CLAUDE_CONFIG_DIR", "PATH")}
    bin_dir = os.path.join(sandbox, "bin")
    log = os.path.join(sandbox, "claude.log")

    def put(path, content):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(content)

    def fresh_home(name):
        os.environ["CLAUDE_CONFIG_DIR"] = os.path.join(sandbox, name)
        os.makedirs(home())
        return home()

    try:
        os.makedirs(bin_dir)
        os.environ["PATH"] = bin_dir

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
              and steps["skill"] and steps["settings"] and steps["claude_md"] and not steps["old_plugin"])
        _, pending, backup = apply(steps)
        settings = read_json(os.path.join(root, "settings.json"))
        check("manual: settings keep the user's hook", settings.get("theme") == "dark" and [
            group["matcher"] for group in settings["hooks"]["PreToolUse"]] == ["Bash"])
        check("manual: CLAUDE.md keeps the user's section", read(os.path.join(root, "CLAUDE.md")) == "# Commits\n\n- mine\n")
        check("manual: moved to the backup", backup and os.path.isfile(os.path.join(backup, "agents", "explore.md"))
              and not os.path.exists(os.path.join(root, "agents", "explore.md"))
              and os.path.isfile(os.path.join(root, "agents", "mine.md")))
        check("manual: nothing pending", not pending and not has_work(plan()))

        # 3. The old plugin with the CLI on the PATH: uninstalls it and removes its marketplace.
        root = fresh_home("old-cli")
        put(os.path.join(root, "plugins", "installed_plugins.json"), json.dumps(
            {"plugins": {OLD_PLUGIN: [{"scope": "user"}], "keel@keel": [{"scope": "user"}]}}))
        put(os.path.join(root, "plugins", "known_marketplaces.json"), json.dumps({OLD_MARKETPLACE: {}, "keel": {}}))
        put(os.path.join(root, "settings.json"), json.dumps({"enabledPlugins": {OLD_PLUGIN: True, "keel@keel": True}}))
        put(os.path.join(bin_dir, "claude"), "#!/bin/sh\necho \"$@\" >> \"{}\"\n".format(log))
        os.chmod(os.path.join(bin_dir, "claude"), 0o755)
        steps = plan()
        check("old-cli: plan", [command[2] for command, _ in steps["old_plugin"]] == ["uninstall", "marketplace"]
              and not steps["settings"])
        _, pending, _ = apply(steps)
        check("old-cli: ran the CLI", (read(log) or "").splitlines() == [
            "plugin uninstall {} --scope user".format(OLD_PLUGIN),
            "plugin marketplace remove {} --scope user".format(OLD_MARKETPLACE)])
        check("old-cli: nothing pending", not pending)
        os.remove(os.path.join(bin_dir, "claude"))

        # 4. The old plugin without the CLI: disabled in settings.json, the commands stay for the user.
        steps = plan()
        check("old-no-cli: plan disables", steps["settings"] and "disable {}".format(OLD_PLUGIN) in steps["settings"][2])
        _, pending, _ = apply(steps)
        enabled = read_json(os.path.join(root, "settings.json"))["enabledPlugins"]
        check("old-no-cli: disabled", enabled == {OLD_PLUGIN: False, "keel@keel": True})
        check("old-no-cli: pending commands", len(pending) == 2)

        # 5. keel installed from the old marketplace (`keel@fluxo`): the old plugin goes, the marketplace stays, and
        # keel@fluxo alone is not work.
        root = fresh_home("keel-from-fluxo")
        installed = os.path.join(root, "plugins", "installed_plugins.json")
        put(installed, json.dumps({"plugins": {OLD_PLUGIN: [{"scope": "user"}], "keel@fluxo": [{"scope": "user"}]}}))
        put(os.path.join(root, "plugins", "known_marketplaces.json"), json.dumps({OLD_MARKETPLACE: {}}))
        put(os.path.join(bin_dir, "claude"), "#!/bin/sh\necho \"$@\" >> \"{}\"\n".format(log))
        os.chmod(os.path.join(bin_dir, "claude"), 0o755)
        os.remove(log)
        steps = plan()
        check("keel-from-fluxo: plan", [command[2] for command, _ in steps["old_plugin"]] == ["uninstall"]
              and steps["kept_marketplace"] == ["keel@fluxo"])
        apply(steps)
        check("keel-from-fluxo: marketplace kept", (read(log) or "").splitlines() == [
            "plugin uninstall {} --scope user".format(OLD_PLUGIN)])
        put(installed, json.dumps({"plugins": {"keel@fluxo": [{"scope": "user"}]}}))
        check("keel-from-fluxo: no work left", not has_work(plan()))
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

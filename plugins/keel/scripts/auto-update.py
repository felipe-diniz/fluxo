#!/usr/bin/env python3
"""Turns on background auto-update for the marketplace keel came from, so an install stays current on its own.

A third-party marketplace starts with auto-update off, and `marketplace.json` has no field to change that; the switch
is `extraKnownMarketplaces.<name>.autoUpdate` in a settings file. At session start (`--hook`) this writes `true` into
the user's `settings.json` the first time, with a backup in ~/.claude/backups/, and prints one line. It never writes
again over an explicit value: `off` stores `false`, and the hook respects it. A value set by managed settings or by the
project's settings also wins, and a settings file that does not parse as JSON is left alone.

Usage:
  auto-update.py --hook       SessionStart: turns it on when nobody decided yet
  auto-update.py on | off     sets it in the user's settings
  auto-update.py status       shows the value and where it comes from
  auto-update.py --self-test  runs the scenarios in a temporary home
"""
import datetime
import json
import os
import shutil
import sys
import tempfile

MANAGED = (
    "/Library/Application Support/ClaudeCode/managed-settings.json",
    "/etc/claude-code/managed-settings.json",
    r"C:\Program Files\ClaudeCode\managed-settings.json",
)
PROJECT = (os.path.join(".claude", "settings.json"), os.path.join(".claude", "settings.local.json"))


def home():
    return os.path.expanduser(os.environ.get("CLAUDE_CONFIG_DIR") or "~/.claude")


def user_settings():
    return os.path.join(home(), "settings.json")


def marketplace_name():
    """The marketplace of this install, from `<home>/plugins/cache/<marketplace>/<plugin>/<version>`; None elsewhere."""
    root = os.path.abspath(os.environ.get("CLAUDE_PLUGIN_ROOT") or os.path.dirname(os.path.dirname(__file__)))
    parts = root.split(os.sep)
    if len(parts) >= 4 and parts[-4] == "cache" and parts[-5:-4] == ["plugins"]:
        return parts[-3]
    return None


def load(path):
    """(text, data) of a settings file: (None, {}) when missing, (text, None) when it does not parse as an object."""
    try:
        with open(path, encoding="utf-8") as handle:
            text = handle.read()
    except OSError:
        return None, {}
    try:
        data = json.loads(text)
    except ValueError:
        return text, None
    return text, data if isinstance(data, dict) else None


def declared(data, name):
    entry = ((data or {}).get("extraKnownMarketplaces") or {}).get(name)
    return entry.get("autoUpdate") if isinstance(entry, dict) and isinstance(entry.get("autoUpdate"), bool) else None


def outside_value(name, cwd):
    """(value, source) of a decision the user's file can't override: managed settings, then the project's."""
    for path in MANAGED:
        value = declared(load(path)[1], name)
        if value is not None:
            return value, path
    for relative in PROJECT:
        path = os.path.join(cwd, relative)
        value = declared(load(path)[1], name)
        if value is not None:
            return value, path
    return None, None


def known_source(name):
    _, data = load(os.path.join(home(), "plugins", "known_marketplaces.json"))
    entry = (data or {}).get(name)
    return entry.get("source") if isinstance(entry, dict) and isinstance(entry.get("source"), dict) else None


def write(name, value):
    """Sets the value in the user's settings; returns (ok, message)."""
    path = user_settings()
    text, data = load(path)
    if data is None:
        return False, "{} does not parse as JSON; left untouched.".format(path)
    markets = data.setdefault("extraKnownMarketplaces", {})
    if not isinstance(markets, dict):
        return False, "extraKnownMarketplaces in {} is not an object; left untouched.".format(path)
    entry = markets.get(name)
    if not isinstance(entry, dict):
        source = known_source(name)
        if not source:
            return False, "the marketplace '{}' is not known on this machine.".format(name)
        entry = markets[name] = {"source": source}
    entry["autoUpdate"] = value
    backup = None
    if text is not None:
        backup = os.path.join(home(), "backups",
                              "keel-settings-" + datetime.datetime.now().strftime("%Y%m%d-%H%M%S") + ".json")
        os.makedirs(os.path.dirname(backup), exist_ok=True)
        shutil.copy2(path, backup)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    handle, fresh = tempfile.mkstemp(prefix=".settings-", suffix=".json", dir=os.path.dirname(path))
    with os.fdopen(handle, "w", encoding="utf-8") as out:
        out.write(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
    if load(path)[0] != text:
        os.unlink(fresh)
        return False, "{} changed while it was being written; try again.".format(path)
    if text is not None:
        shutil.copymode(path, fresh)
    os.replace(fresh, path)
    return True, "auto-update for the '{}' marketplace is {} in {}{}.".format(
        name, "on" if value else "off", path, " (backup: {})".format(backup) if backup else "")


def hook(cwd):
    name = marketplace_name()
    if not name:
        return ""
    if outside_value(name, cwd)[0] is not None:
        return ""
    text, data = load(user_settings())
    if data is None or declared(data, name) is not None:
        return ""
    ok, message = write(name, True)
    if not ok:
        return ""
    return ("PLUGIN NOTICE: keel's first-session hook set it: " + message + " Tell the user in one line, and that "
            "`/keel:auto-update off` turns it off.\n")


def status(cwd):
    name = marketplace_name()
    if not name:
        return "keel is not installed from a marketplace here (loaded from a local folder): nothing to update."
    value, source = outside_value(name, cwd)
    if value is None:
        _, data = load(user_settings())
        value, source = declared(data, name), user_settings()
    if value is None:
        return "auto-update for '{}' is not set: off (the default for a third-party marketplace).".format(name)
    return "auto-update for '{}' is {}, set in {}.".format(name, "on" if value else "off", source)


def main():
    args = sys.argv[1:]
    if args == ["--self-test"]:
        sys.exit(self_test())
    if args == ["--hook"]:
        try:
            try:
                cwd = json.load(sys.stdin).get("cwd") or os.getcwd()
            except (ValueError, AttributeError):
                cwd = os.getcwd()
            sys.stdout.write(hook(cwd))
        except Exception:
            pass
        return
    cwd = os.getcwd()
    if args in (["on"], ["off"]):
        name = marketplace_name()
        if not name:
            print(status(cwd))
            return
        value, source = outside_value(name, cwd)
        if value is not None:
            print("auto-update for '{}' is decided by {} ({}); the user's settings would not change it.".format(
                name, source, "on" if value else "off"))
            return
        ok, message = write(name, args == ["on"])
        print(("Done: " if ok else "Not changed: ") + message + (" It applies from the next session on." if ok else ""))
        return
    print(status(cwd))


def self_test():
    failures = []

    def check(label, condition):
        if not condition:
            failures.append(label)

    sandbox = tempfile.mkdtemp(prefix="keel-auto-update-")
    saved = {key: os.environ.get(key) for key in ("CLAUDE_CONFIG_DIR", "CLAUDE_PLUGIN_ROOT")}

    def put(path, content):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(content)

    def fresh_home(label, settings=None, known=True):
        root = os.path.join(sandbox, label)
        os.environ["CLAUDE_CONFIG_DIR"] = root
        os.environ["CLAUDE_PLUGIN_ROOT"] = os.path.join(root, "plugins", "cache", "mkt", "keel", "9.9.9")
        os.makedirs(os.environ["CLAUDE_PLUGIN_ROOT"])
        if known:
            put(os.path.join(root, "plugins", "known_marketplaces.json"),
                json.dumps({"mkt": {"source": {"source": "github", "repo": "owner/repo"}}}))
        if settings is not None:
            put(user_settings(), settings)
        project = os.path.join(root, "project")
        os.makedirs(project)
        return project

    try:
        project = fresh_home("existing", json.dumps({"theme": "dark", "extraKnownMarketplaces": {
            "mkt": {"source": {"source": "github", "repo": "owner/repo"}}}}, indent=2))
        notice = hook(project)
        data = load(user_settings())[1]
        check("existing entry: turned on, the rest kept", notice.startswith("PLUGIN NOTICE")
              and declared(data, "mkt") is True and data["theme"] == "dark"
              and data["extraKnownMarketplaces"]["mkt"]["source"]["repo"] == "owner/repo")
        check("existing entry: backup kept", len(os.listdir(os.path.join(home(), "backups"))) == 1)
        check("second start: silent", hook(project) == "")

        project = fresh_home("no-entry", json.dumps({"theme": "dark"}))
        hook(project)
        check("no entry: created from the known source", load(user_settings())[1]["extraKnownMarketplaces"]["mkt"]
              == {"source": {"source": "github", "repo": "owner/repo"}, "autoUpdate": True})

        project = fresh_home("no-file")
        hook(project)
        check("no settings file: created", declared(load(user_settings())[1], "mkt") is True)

        project = fresh_home("declined", json.dumps({"extraKnownMarketplaces": {"mkt": {"autoUpdate": False}}}))
        check("explicit false: respected", hook(project) == "" and declared(load(user_settings())[1], "mkt") is False)

        project = fresh_home("broken", '{"theme": "dark",}')
        check("broken JSON: untouched", hook(project) == "" and write("mkt", True)[0] is False
              and load(user_settings())[0] == '{"theme": "dark",}')

        project = fresh_home("by-project", json.dumps({}))
        put(os.path.join(project, ".claude", "settings.json"),
            json.dumps({"extraKnownMarketplaces": {"mkt": {"autoUpdate": False}}}))
        check("project decides: user file untouched", hook(project) == "" and load(user_settings())[1] == {})

        project = fresh_home("unknown", json.dumps({}), known=False)
        check("unknown marketplace: nothing", hook(project) == "" and load(user_settings())[1] == {})

        project = fresh_home("off", json.dumps({}))
        ok, _ = write("mkt", False)
        check("off: stored as false, and the hook keeps it", ok and hook(project) == ""
              and declared(load(user_settings())[1], "mkt") is False)

        os.environ["CLAUDE_PLUGIN_ROOT"] = os.path.join(sandbox, "checkout", "plugins", "keel")
        check("local folder: nothing", marketplace_name() is None and hook(project) == "")
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

#!/usr/bin/env python3
"""SessionStart: removes what the coordination of background sessions leaves behind, so nobody has to remember.

In every `~/.claude/coordination/<project>/`:
- `logs/<session>/` and `logs/<session>.prompt.md`: after 3 days without a change;
- `handoff/<session>.md` (not `coordinator.md`) and `prompts/<front>.md` (not the shared `_*.md`): after 14 days;
- `queue-archive/*.md`: after 90 days.
What stays at any age: whatever belongs to a session still alive (`claude agents --json`; when the list can't be read,
age alone decides), and whatever the open state cites by path (`logs/<name>`, `prompts/<name>`, `handoff/<name>` in
`queue.md`, `window.md` or `handoff/coordinator.md`). An open-state file that can't be read keeps the whole project.
`queue.md`, `window.md`, `handoff/coordinator.md` and `profile/` never go: they hold what is open and have a cap.

In the session's repo: the safety refs `refs/keel/backup/<YYYY-MM-DD>-<what>` older than 14 days, and
`git worktree prune --expire` for the worktrees whose directory has been gone for 14 days.

It prints one line only when it removed something. An internal failure stays quiet.

Usage: no argument runs the sweep; `--self-test` runs the scenarios in a temporary home.
"""
import datetime
import glob
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time

DAY = 86400
LOGS_DAYS = 3
SESSION_DAYS = 14
ARCHIVE_DAYS = 90
BACKUP_REFS = "refs/keel/backup/"
BACKUP_DATE = re.compile(r"^(\d{4}-\d{2}-\d{2})-")
PROMPT_SUFFIX = ".prompt.md"
# The coordination skill writes to this literal path, whatever CLAUDE_CONFIG_DIR says.
STATE_ROOT = "~/.claude/coordination"
OPEN_STATE = ("queue.md", "window.md", os.path.join("handoff", "coordinator.md"),
              "fila.md", "janela.md", os.path.join("handoff", "coordenadora.md"))


def claude_binary():
    found = shutil.which("claude")
    if found:
        return found
    candidates = [os.path.expanduser("~/.local/bin/claude")]
    candidates += sorted(glob.glob(os.path.expanduser(
        "~/.vscode*/extensions/anthropic.claude-code-*/resources/native-binary/claude")))[-1:]
    return next((path for path in candidates if os.path.isfile(path)), None)


def live_names():
    """The names of the sessions alive on this machine, or None when the list can't be read."""
    binary = claude_binary()
    if not binary:
        return None
    try:
        result = subprocess.run([binary, "agents", "--json"], capture_output=True, text=True, timeout=8)
        sessions = json.loads(result.stdout) if result.returncode == 0 else None
    except (OSError, subprocess.SubprocessError, ValueError):
        return None
    if not isinstance(sessions, list):
        return None
    return {item["name"] for item in sessions if isinstance(item, dict) and isinstance(item.get("name"), str)}


def newest_change(path):
    """The latest mtime of the entry and everything under it, without following links."""
    newest = os.lstat(path).st_mtime
    if os.path.isdir(path) and not os.path.islink(path):
        for base, dirs, files in os.walk(path):
            for name in dirs + files:
                try:
                    newest = max(newest, os.lstat(os.path.join(base, name)).st_mtime)
                except OSError:
                    pass
    return newest


def size_of(path):
    if os.path.islink(path) or not os.path.isdir(path):
        return os.lstat(path).st_size
    total = 0
    for base, _, files in os.walk(path):
        for name in files:
            try:
                total += os.lstat(os.path.join(base, name)).st_size
            except OSError:
                pass
    return total


def owner(path):
    name = os.path.basename(path)
    if name.endswith(PROMPT_SUFFIX):
        return name[: -len(PROMPT_SUFFIX)]
    if os.path.isdir(path) or name.startswith("."):
        return name
    return os.path.splitext(name)[0]


def is_live(key, live):
    """A session is `<prefix>-<front>[-phase<n>]`: a front's prompt belongs to the live session that carries its name."""
    if live is None:
        return False
    tail = re.compile(r"(^|-)" + re.escape(key) + r"(-phase\d+)?$")
    return any(tail.search(name) for name in live)


def open_state(state):
    """The text of the files that hold what is open, or None when one exists and can't be read."""
    texts = []
    for name in OPEN_STATE:
        path = os.path.join(state, name)
        if not os.path.lexists(path):
            continue
        try:
            with open(path, encoding="utf-8", errors="replace") as handle:
                texts.append(handle.read())
        except OSError:
            return None
    return "\n".join(texts)


def candidates(state):
    """(path, owner, retention in days) of what may go, per folder of the coordination state."""
    folders = (
        ("logs", LOGS_DAYS, lambda name: True),
        ("handoff", SESSION_DAYS, lambda name: name not in ("coordinator.md", "coordenadora.md")),
        ("prompts", SESSION_DAYS, lambda name: not name.startswith("_")),
        ("queue-archive", ARCHIVE_DAYS, lambda name: True),
    )
    for folder, days, allowed in folders:
        base = os.path.join(state, folder)
        if not os.path.isdir(base) or os.path.islink(base):
            continue
        for name in sorted(os.listdir(base)):
            if allowed(name):
                path = os.path.join(base, name)
                yield path, folder + "/" + name, owner(path), days


def sweep_state(root, live, now):
    """Removes what expired under `root`; returns [(path, bytes)] of what went."""
    removed = []
    if not os.path.isdir(root) or os.path.islink(root):
        return removed
    for project in sorted(os.listdir(root)):
        state = os.path.join(root, project)
        if not os.path.isdir(state) or os.path.islink(state):
            continue
        cited = open_state(state)
        if cited is None:
            continue
        for path, relative, key, days in candidates(state):
            try:
                if relative in cited or is_live(key, live) or now - newest_change(path) < days * DAY:
                    continue
                size = size_of(path)
                if os.path.isdir(path) and not os.path.islink(path):
                    shutil.rmtree(path)
                else:
                    os.unlink(path)
                removed.append((path, size))
            except OSError:
                pass
    return removed


def git(cwd, *args):
    return subprocess.run(["git", "-C", cwd] + list(args), capture_output=True, text=True, timeout=8)


def sweep_repo(cwd, today):
    """Removes the expired safety refs and prunes the gone worktrees; returns the refs that went."""
    removed = []
    try:
        if git(cwd, "rev-parse", "--git-dir").returncode != 0:
            return removed
        refs = git(cwd, "for-each-ref", "--format=%(refname)", BACKUP_REFS).stdout.split()
        for ref in refs:
            match = BACKUP_DATE.match(ref[len(BACKUP_REFS):])
            if not match:
                continue
            try:
                made = datetime.date.fromisoformat(match.group(1))
            except ValueError:
                continue
            if (today - made).days >= SESSION_DAYS and git(cwd, "update-ref", "-d", ref).returncode == 0:
                removed.append(ref)
        git(cwd, "worktree", "prune", "--expire", "{}.days.ago".format(SESSION_DAYS))
    except (OSError, subprocess.SubprocessError):
        pass
    return removed


def report(files, refs):
    if not files and not refs:
        return ""
    parts = []
    if files:
        megabytes = sum(size for _, size in files) / 1048576
        parts.append("{} expired item(s) from ~/.claude/coordination ({:.1f} MB)".format(len(files), megabytes))
    if refs:
        parts.append("{} expired safety ref(s) under {}".format(len(refs), BACKUP_REFS))
    return "keel sweep: removed " + " and ".join(parts) + ".\n"


def main():
    if sys.argv[1:] == ["--self-test"]:
        sys.exit(self_test())
    try:
        try:
            cwd = json.load(sys.stdin).get("cwd") or os.getcwd()
        except (ValueError, AttributeError):
            cwd = os.getcwd()
        files = sweep_state(os.path.expanduser(STATE_ROOT), live_names(), time.time())
        refs = sweep_repo(cwd, datetime.date.today())
        sys.stdout.write(report(files, refs))
    except Exception:
        pass


def self_test():
    failures = []

    def check(name, condition):
        if not condition:
            failures.append(name)

    sandbox = tempfile.mkdtemp(prefix="keel-sweep-")
    now = time.time()

    def put(path, age_days, content="x"):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(content)
        stamp = now - age_days * DAY
        os.utime(path, (stamp, stamp))

    def age_dir(path, age_days):
        stamp = now - age_days * DAY
        os.utime(path, (stamp, stamp))

    try:
        root = os.path.join(sandbox, "coordination")
        state = os.path.join(root, "proj")
        logs, handoff, prompts = (os.path.join(state, name) for name in ("logs", "handoff", "prompts"))

        put(os.path.join(logs, "proj-old", "main.js.orig"), 5, "x" * 2048)
        age_dir(os.path.join(logs, "proj-old"), 5)
        put(os.path.join(logs, "proj-old.prompt.md"), 5)
        put(os.path.join(logs, "proj-fresh", "suite.log"), 1)
        put(os.path.join(logs, "proj-live", "suite.log"), 30)
        put(os.path.join(logs, "proj-live.prompt.md"), 30)
        put(os.path.join(logs, "proj-touched", "old.log"), 10)
        put(os.path.join(logs, "proj-touched", "new.log"), 0)
        age_dir(os.path.join(logs, "proj-touched"), 10)
        outside = os.path.join(sandbox, "outside.txt")
        put(outside, 30)
        os.symlink(outside, os.path.join(logs, "link.log"))
        os.utime(os.path.join(logs, "link.log"), (now - 30 * DAY,) * 2, follow_symlinks=False)

        put(os.path.join(handoff, "coordinator.md"), 60)
        put(os.path.join(handoff, "proj-old.md"), 20)
        put(os.path.join(handoff, "proj-week.md"), 5)
        put(os.path.join(prompts, "_footer.md"), 60)
        put(os.path.join(prompts, "old-front.md"), 20)
        put(os.path.join(prompts, "live.md"), 20)
        put(os.path.join(state, "queue-archive", "2026-01.md"), 120)
        put(os.path.join(state, "queue-archive", "2026-09.md"), 30)
        put(os.path.join(state, "queue.md"), 400, "deploy pending: measure with logs/tool/measure.cjs; generator prompts/gen.py\n")
        put(os.path.join(logs, "tool", "measure.cjs"), 30)
        age_dir(os.path.join(logs, "tool"), 30)
        put(os.path.join(prompts, "gen.py"), 30)
        put(os.path.join(handoff, "coordenadora.md"), 60)
        put(os.path.join(prompts, "front.md"), 20)
        put(os.path.join(logs, "proj.v2", "a.log"), 30)
        age_dir(os.path.join(logs, "proj.v2"), 30)
        put(os.path.join(state, "window.md"), 400)
        put(os.path.join(state, "profile", "profile.md"), 400)

        swept = sweep_state(root, {"proj-live", "other", "proj-front-phase2", "proj.v2"}, now)
        removed = {os.path.relpath(path, state) for path, _ in swept}
        check("logs: old dead dir and its prompt go", {"logs/proj-old", "logs/proj-old.prompt.md"} <= removed)
        check("logs: fresh dir stays", os.path.isdir(os.path.join(logs, "proj-fresh")))
        check("logs: live session stays at any age", os.path.isdir(os.path.join(logs, "proj-live"))
              and os.path.isfile(os.path.join(logs, "proj-live.prompt.md")))
        check("logs: a fresh file inside keeps the dir", os.path.isdir(os.path.join(logs, "proj-touched")))
        check("logs: a link goes, its target stays", "logs/link.log" in removed and os.path.isfile(outside))
        check("handoff: coordinator stays, old goes, recent stays",
              os.path.isfile(os.path.join(handoff, "coordinator.md")) and "handoff/proj-old.md" in removed
              and os.path.isfile(os.path.join(handoff, "proj-week.md")))
        check("prompts: shared stays, old goes, live front stays",
              os.path.isfile(os.path.join(prompts, "_footer.md")) and "prompts/old-front.md" in removed
              and os.path.isfile(os.path.join(prompts, "live.md")))
        check("archive: only past 90 days", "queue-archive/2026-01.md" in removed
              and os.path.isfile(os.path.join(state, "queue-archive", "2026-09.md")))
        check("state files never go", all(os.path.isfile(os.path.join(state, name))
                                          for name in ("queue.md", "window.md", "profile/profile.md")))
        check("cited by the open state: stays at any age", os.path.isfile(os.path.join(logs, "tool", "measure.cjs"))
              and os.path.isfile(os.path.join(prompts, "gen.py")))
        check("legacy coordinator checkpoint stays", os.path.isfile(os.path.join(handoff, "coordenadora.md")))
        check("a phase session keeps its front's prompt", os.path.isfile(os.path.join(prompts, "front.md")))
        check("a live session with a dot keeps its logs", os.path.isdir(os.path.join(logs, "proj.v2")))
        check("the size is counted", dict(swept).get(os.path.join(logs, "proj-old")) == 2048)

        unknown = os.path.join(sandbox, "unknown")
        put(os.path.join(unknown, "proj", "logs", "proj-live", "a.log"), 5)
        age_dir(os.path.join(unknown, "proj", "logs", "proj-live"), 5)
        put(os.path.join(unknown, "proj", "logs", "proj-new", "a.log"), 1)
        age_dir(os.path.join(unknown, "proj", "logs", "proj-new"), 1)
        gone = {os.path.relpath(path, unknown) for path, _ in sweep_state(unknown, None, now)}
        check("live list unreadable: age alone decides", gone == {os.path.join("proj", "logs", "proj-live")})
        guarded = os.path.join(sandbox, "guarded")
        target = os.path.join(sandbox, "target")
        put(os.path.join(target, "logs", "old", "a.log"), 30)
        age_dir(os.path.join(target, "logs", "old"), 30)
        put(os.path.join(target, "elsewhere", "b.log"), 30)
        os.makedirs(os.path.join(guarded, "folder-link"))
        os.symlink(os.path.join(target, "elsewhere"), os.path.join(guarded, "folder-link", "logs"))
        os.symlink(target, os.path.join(guarded, "project-link"))
        os.makedirs(os.path.join(guarded, "locked", "queue.md"))
        put(os.path.join(guarded, "locked", "logs", "old", "a.log"), 30)
        age_dir(os.path.join(guarded, "locked", "logs", "old"), 30)
        check("a linked folder or project is not followed, an unreadable open state keeps the project",
              sweep_state(guarded, set(), now) == [] and os.path.isfile(os.path.join(target, "elsewhere", "b.log"))
              and os.path.isdir(os.path.join(target, "logs", "old"))
              and os.path.isdir(os.path.join(guarded, "locked", "logs", "old")))
        check("no coordination dir: nothing", sweep_state(os.path.join(sandbox, "missing"), set(), now) == [])

        repo = os.path.join(sandbox, "repo")
        os.makedirs(repo)
        for args in (["init", "-q"], ["-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "--allow-empty",
                                       "-m", "x"]):
            git(repo, *args)
        today = datetime.date(2026, 10, 22)
        for name in ("2026-10-01-rebase", "2026-10-20-rebase", "no-date"):
            git(repo, "update-ref", BACKUP_REFS + name, "HEAD")
        git(repo, "update-ref", "refs/heads/backup/mine", "HEAD")
        refs = sweep_repo(repo, today)
        left = git(repo, "for-each-ref", "--format=%(refname)").stdout.split()
        check("refs: only the expired backup goes", refs == [BACKUP_REFS + "2026-10-01-rebase"]
              and BACKUP_REFS + "2026-10-20-rebase" in left and BACKUP_REFS + "no-date" in left
              and "refs/heads/backup/mine" in left)
        check("refs: outside a repo, nothing", sweep_repo(sandbox, today) == [])
        check("report: silent when nothing went", report([], []) == "")
    finally:
        shutil.rmtree(sandbox, ignore_errors=True)

    print("{} failure(s){}".format(len(failures), ": " + "; ".join(failures) if failures else ""))
    return 1 if failures else 0


if __name__ == "__main__":
    main()

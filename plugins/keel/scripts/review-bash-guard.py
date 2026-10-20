#!/usr/bin/env python3
"""The plugin's PreToolUse (Bash) hook, which acts only inside the `critical-review` subagent (by the payload's
`agent_type`).

The gate reviews and measures; it doesn't change state or start heavy work. This guard denies, with the reason, what
the agent's rule forbids and has already cost a lot: git that changes the tree or the history (the tree is shared with
other sessions), file writes outside the temp dir, whole suites, E2E, build, lint, typecheck, servers, migrations,
seeds, package installs, process and container control, Redis writes, remote access and network outside localhost.
Everything else passes: reads, psql, local curl, node running a verification script and one focused spec.
An internal failure lets the command through: a cost guard must not block the review.

Usage: reads the PreToolUse JSON on stdin. `--self-test` runs the table of cases.
"""
import json
import os
import re
import shlex
import sys

TMP_PREFIXES = ("/tmp/", "/private/tmp/", "/var/folders/", "/dev/null", "/dev/stdout", "/dev/stderr")
LOCAL_HOSTS = ("localhost", "127.0.0.1", "0.0.0.0", "::1", "[::1]", "host.docker.internal")

GIT_READ = {
    "diff", "log", "show", "status", "blame", "annotate", "ls-files", "ls-tree", "rev-parse", "merge-base",
    "grep", "cat-file", "describe", "shortlog", "name-rev", "for-each-ref", "show-ref", "show-branch",
    "diff-tree", "diff-index", "diff-files", "rev-list", "whatchanged", "check-ignore", "count-objects",
    "version", "help", "var", "cherry", "range-diff", "verify-commit", "verify-tag",
}
GIT_BRANCH_WRITE = {
    "-d", "-D", "-m", "-M", "-c", "-C", "-f", "-u", "--delete", "--move", "--copy", "--force",
    "--set-upstream-to", "--unset-upstream", "--edit-description", "--track", "--no-track",
}
GIT_SUBMODE_READ = {
    "stash": {"list", "show"},
    "worktree": {"list"},
    "notes": {"list", "show"},
    "submodule": {"status"},
    "reflog": {"show"},
    "remote": {"-v", "show", "get-url"},
}
GIT_CONFIG_READ = {"--get", "--get-all", "--get-regexp", "--list", "-l", "--show-origin", "--show-scope"}
GIT_TAG_READ = {"-l", "--list", "--contains", "--no-contains", "--points-at", "--merged", "--no-merged", "-n"}

WRITE_COMMANDS = {"rm", "rmdir", "mv", "cp", "mkdir", "touch", "chmod", "chown", "ln", "truncate", "dd",
                  "install", "patch", "unlink", "shred", "tee"}
BLOCKED_COMMANDS = {
    "kill": "process control", "pkill": "process control", "killall": "process control",
    "systemctl": "service control", "service": "service control", "launchctl": "service control",
    "reboot": "machine control", "shutdown": "machine control", "crontab": "scheduling",
    "ssh": "remote access", "scp": "remote access", "sftp": "remote access", "rsync": "remote copy",
    "playwright": "front-end E2E (takes the dev server down)", "tsc": "typecheck (the main session's, before the gate)",
    "vue-tsc": "typecheck", "eslint": "lint (the main session's, before the gate)", "prettier": "formatting",
    "next": "Next build/server", "turbo": "build", "webpack": "build", "vite": "build/server",
    "make": "build", "kubectl": "remote infra", "gcloud": "remote infra", "aws": "remote infra",
    "az": "remote infra", "terraform": "remote infra", "vercel": "remote infra", "firebase": "remote infra",
}
PACKAGE_MANAGERS = {"pnpm", "npm", "yarn", "bun"}
PACKAGE_READ = {"ls", "list", "why", "view", "info", "--version", "-v", "outdated"}
EXEC_WRAPPERS = {"npx", "pnpx", "bunx"}
RUNTIMES = {"node", "python", "python3", "tsx", "ts-node", "jiti", "deno", "ruby"}
SHELLS = {"bash", "sh", "zsh", "dash", "fish", "eval"}
NETWORK_CLIENTS = {"curl", "wget", "http", "https", "xh", "httpie"}
PREFIX_WRAPPERS = {"sudo", "env", "time", "nohup", "nice", "command", "exec", "builtin", "stdbuf"}
WRAPPER_VALUE_FLAGS = {"-u", "-g", "-C", "-n", "-p", "-h", "--user", "--group", "--chdir", "--unset", "--adjustment"}
COPY_COMMANDS = {"cp", "ln"}
FIND_EXEC = {"-exec", "-execdir", "-ok", "-okdir"}
STATEFUL_SCRIPT = re.compile(r"(seed|migrat|publish|reset|restore|backfill|deploy|drop|purge|import|sync-prisma)",
                             re.IGNORECASE)
REDIS_WRITE = re.compile(
    r"\b(flushall|flushdb|del|unlink|set|setex|psetex|setnx|mset|msetnx|getset|getdel|append|expire|pexpire|"
    r"expireat|persist|hset|hmset|hdel|hincrby|lpush|rpush|lpop|rpop|lrem|lset|ltrim|sadd|srem|spop|smove|zadd|"
    r"zrem|zincrby|incr|incrby|decr|decrby|rename|renamenx|move|restore|migrate|copy|swapdb|xadd|xdel|xtrim|"
    r"publish|eval|evalsha|fcall|shutdown|debug|bgsave|save|bgrewriteaof)\b|\bconfig\s+set\b|\bscript\s+flush\b",
    re.IGNORECASE,
)
TEST_FOCUS = re.compile(r"--testPathPatterns?(=|\s|$)|--testFile(=|\s|$)|\.(spec|test)\.[cm]?[jt]sx?\b")
QUOTED = re.compile(r"'[^']*'|\"(?:\\.|[^\"\\])*\"")
HEREDOC = re.compile(r"<<-?\s*(['\"]?)([A-Za-z_][A-Za-z0-9_]*)\1[^\n]*\n(.*?)(?:\n[ \t]*\2[ \t]*(?=\n|$)|\Z)", re.DOTALL)
SEPARATORS = re.compile(r"\|\||&&|;|\||&(?![>&])|\n|\$\(|`|\(|\)|\{|\}")
REDIRECT = re.compile(r"(?:^|[^<>&|=-])(?:\d*>>?\|?|&>>?)\s*([^\s;&|()]+)")


def is_tmp(path):
    expanded = os.path.expandvars(path)
    tmpdir = os.environ.get("TMPDIR")
    return expanded.startswith(TMP_PREFIXES) or bool(tmpdir and expanded.startswith(tmpdir))


def strip_quotes(command):
    return QUOTED.sub("_", command)


def words_of(segment):
    try:
        return shlex.split(segment)
    except ValueError:
        return segment.split()


def unwrap(words):
    index = 0
    while index < len(words):
        word = words[index]
        if re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", word):
            index += 1
        elif word in PREFIX_WRAPPERS:
            index += 1
            while index < len(words) and words[index].startswith("-"):
                flag = words[index]
                index += 1
                if flag in WRAPPER_VALUE_FLAGS and index < len(words):
                    index += 1
        elif word == "timeout":
            index += 1
            while index < len(words) and (words[index].startswith("-") or re.match(r"^\d", words[index])):
                index += 1
        elif word == "xargs":
            index += 1
            while index < len(words) and words[index].startswith("-"):
                index += 1
        else:
            break
    return words[index:]


def check_git(args):
    index = 0
    while index < len(args) and args[index].startswith("-"):
        index += 2 if args[index] in ("-C", "-c") else 1
    if index >= len(args):
        return None
    sub, rest = args[index], args[index + 1:]
    if sub in GIT_READ:
        return None
    if sub == "branch":
        return "git branch that changes a branch" if any(arg.split("=")[0] in GIT_BRANCH_WRITE for arg in rest) else None
    if sub in GIT_SUBMODE_READ:
        if sub == "remote" and not rest:
            return None
        return None if rest and rest[0] in GIT_SUBMODE_READ[sub] else "git {} that changes state".format(sub)
    if sub == "config":
        return None if any(arg in GIT_CONFIG_READ for arg in rest) else "git config write"
    if sub == "tag":
        return None if not rest or rest[0] in GIT_TAG_READ else "git tag write"
    return "git {} changes the tree, the index or the history (the tree is shared with other sessions)".format(sub)


def check_tests(tool, args):
    if any(arg in ("--watch", "--watchAll") for arg in args):
        return "test in watch mode"
    if TEST_FOCUS.search(" ".join(args)):
        return None
    return "{} without focus: run at most one spec (--testPathPatterns=<spec> or the file path)".format(tool)


def check_nx(args):
    if not args or args[0] in ("show", "report", "list", "--version", "--help"):
        return None
    target = args[0]
    if target == "run" and len(args) > 1:
        target = args[1].split(":")[-1]
        rest = args[2:]
    else:
        rest = args[1:]
    if target == "test":
        return check_tests("nx test", rest)
    return "nx {}: suites, build, lint, typecheck, servers and cache belong to the main session, before the gate".format(target)


def check_prisma(args):
    joined = " ".join(args)
    if joined.startswith("migrate status") or args[:1] in (["validate"], ["--version"], ["-v"]):
        return None
    return "prisma {} changes the database, the schema or the client".format(joined.split(" ")[0] if joined else "")


def check_docker(args):
    if args[:1] == ["compose"] or args[:1] == ["docker-compose"]:
        args = args[1:]
        while args and args[0].startswith("-"):
            args = args[2:] if args[0] in ("-f", "--file", "-p", "--project-name") else args[1:]
        allowed = {"ps", "logs", "config", "top", "images", "version", "ls"}
    else:
        allowed = {"ps", "logs", "inspect", "exec", "images", "version", "info", "stats", "top", "port"}
    if not args or args[0] in allowed:
        return None
    return "docker {} changes a container or an image (shared environment)".format(args[0])


def check_network(raw_command, args):
    hosts = re.findall(r"[a-zA-Z][a-zA-Z0-9+.-]*://(\[[^\]]+\]|[^/\s:'\"?#]+)", raw_command)
    if not hosts:
        hosts = [re.split(r"[/:]", arg)[0] for arg in args if not arg.startswith("-") and re.search(r"[.:]", arg)]
    remote = [host for host in hosts if host and host.lower() not in LOCAL_HOSTS and not host.startswith("127.")]
    return "network outside localhost ({})".format(", ".join(sorted(set(remote)))) if remote else None


def check_segment(words, raw_command):
    words = unwrap(words)
    if not words:
        return None
    tool = os.path.basename(words[0])
    args = words[1:]

    if tool == "git":
        return check_git(args)
    if tool in BLOCKED_COMMANDS:
        return "{}: {}".format(tool, BLOCKED_COMMANDS[tool])
    if tool in WRITE_COMMANDS:
        targets = [arg for arg in args if not arg.startswith("-")]
        if tool in COPY_COMMANDS and targets and is_tmp(targets[-1]):
            return None
        if targets and all(is_tmp(target) for target in targets):
            return None
        return "{} writes or deletes a file (only in the temp dir)".format(tool)
    if tool == "find":
        if "-delete" in args:
            return "find -delete deletes files"
        for index, arg in enumerate(args):
            if arg in FIND_EXEC:
                inner = []
                for word in args[index + 1:]:
                    if word in (";", "\\;", "+", "\\"):
                        break
                    inner.append(word)
                reason = check_segment(inner, raw_command)
                if reason:
                    return "find {} {}".format(arg, reason)
        return None
    if tool in ("sed", "perl"):
        in_place = any(arg == "--in-place" or arg.startswith("--in-place=") or
                       (arg.startswith("-") and not arg.startswith("--") and "i" in arg[1:]) for arg in args)
        return "{} -i edits a file".format(tool) if in_place else None
    if tool in PACKAGE_MANAGERS:
        if args and args[0] in ("exec", "x"):
            return check_segment(args[1:], raw_command)
        if not args or args[0] in PACKAGE_READ:
            return None
        return "{} {}: installs, scripts and suites belong to the main session".format(tool, args[0])
    if tool in EXEC_WRAPPERS:
        rest = [arg for arg in args if arg not in ("-y", "--yes", "--no-install")]
        return check_segment(rest, raw_command)
    if tool == "nx":
        return check_nx(args)
    if tool in ("jest", "vitest"):
        return check_tests(tool, args)
    if tool == "prisma":
        return check_prisma(args)
    if tool in ("docker", "docker-compose", "podman"):
        return check_docker(args if tool != "docker-compose" else ["compose"] + args)
    if tool in NETWORK_CLIENTS:
        return check_network(raw_command, args)
    if tool == "gh":
        if len(args) >= 2 and (args[0], args[1]) in {
            ("pr", "view"), ("pr", "diff"), ("pr", "list"), ("pr", "checks"), ("pr", "status"),
            ("run", "view"), ("run", "list"), ("issue", "view"), ("issue", "list"),
        }:
            return None
        return "gh {} may change GitHub".format(" ".join(args[:2]))
    if tool == "redis-cli":
        return "redis-cli with a write command" if REDIS_WRITE.search(raw_command) else None
    if tool in RUNTIMES or tool.endswith((".sh", ".mjs", ".js", ".ts", ".py", ".cjs")):
        script = tool if tool not in RUNTIMES else next((arg for arg in args if not arg.startswith("-")), "")
        if args[:1] in (["-c"], ["-e"]) and tool in RUNTIMES:
            return None
        if STATEFUL_SCRIPT.search(os.path.basename(script)):
            return "a script that changes state ({})".format(os.path.basename(script))
        return None
    return None


def split_heredocs(command):
    """Drops heredoc bodies (Python code, SQL and JSON are not commands) and returns the ones that feed a shell."""
    shell_bodies = []

    def drop_body(match):
        line_start = command.rfind("\n", 0, match.start()) + 1
        lead = SEPARATORS.split(strip_quotes(command[line_start:match.start()]))[-1]
        lead_words = unwrap(words_of(lead))
        if lead_words and os.path.basename(lead_words[0]) in SHELLS:
            shell_bodies.append(match.group(3))
        return match.group(0).split("\n", 1)[0] + "\n"

    return HEREDOC.sub(drop_body, command), shell_bodies


def check_command(command, depth=0):
    command, shell_bodies = split_heredocs(command)
    if depth < 2:
        for body in shell_bodies:
            reason = check_command(body, depth + 1)
            if reason:
                return reason
    stripped = strip_quotes(command)
    for match in REDIRECT.finditer(stripped):
        target = match.group(1)
        if target.startswith("&") or is_tmp(target):
            continue
        return "a redirect writes a file ({}); only in the temp dir".format(target)
    for segment in SEPARATORS.split(stripped):
        words = words_of(segment)
        reason = check_segment(words, command)
        if reason:
            return reason
        unwrapped = unwrap(words)
        if depth < 2 and unwrapped and os.path.basename(unwrapped[0]) in SHELLS:
            for quoted in QUOTED.findall(command):
                inner = check_command(quoted[1:-1], depth + 1)
                if inner:
                    return inner
    return None


def decide(command):
    reason = check_command(command)
    if not reason:
        return None
    return ("Blocked in critical-review: {}. The gate only reads and measures (read-only git, cat/sed -n/grep, psql "
            "in a transaction that rolls back, local curl, node running a verification script, one focused spec). If "
            "the evidence depends on this, list it as a scenario for the main agent to run.").format(reason)


SELF_TEST = [
    ("git diff -- libs/backend/x.ts", True),
    ("git -C /repo log --oneline -5", True),
    ("git status --porcelain -- libs/", True),
    ("git show abc123 -- file", True),
    ("git branch --show-current", True),
    ("git stash list", True),
    ("git worktree list", True),
    ("git config --get user.name", True),
    ("git --no-pager log -3 --format='%h %s' 2>&1", True),
    ("cat file | grep -n foo | head -20", True),
    ("sed -n '1,80p' file", True),
    ("grep -rn \"git commit\" docs/", True),
    ("psql \"postgresql://app:x@localhost:5432/app\" -c \"BEGIN; SELECT 1; ROLLBACK;\"", True),
    ("curl -s http://localhost:3300/api/healthcheck", True),
    ("curl -sf -o /dev/null --max-time 3 \"http://127.0.0.1:3300/api/x\"", True),
    ("curl -s localhost:3300/api/x", True),
    ("node scripts/db/verify-rls-runtime.mjs", True),
    ("node scripts/dev/audit-passthrough-methods.mjs libs/backend/x", True),
    ("./scripts/dev/review-env.sh --check", True),
    ("NX_DAEMON=false pnpm exec nx test billing --testPathPatterns=billing.service.spec.ts", True),
    ("npx jest libs/backend/x/src/lib/x.service.spec.ts", True),
    ("git diff --stat > /tmp/review.diff", True),
    ("docker exec -i app-postgres psql -U postgres -d app -c \"select 1\"", True),
    ("docker ps --format '{{.Names}}'", True),
    ("docker compose ps", True),
    ("ls -la; wc -l file", True),
    ("python3 -c \"import json; print(1)\"", True),
    ("find . -name '*.spec.ts' | head", True),
    ("redis-cli -p 6379 GET key", True),
    ("npx prisma migrate status", True),
    ("gh pr diff 164", True),
    ("cd /repo && git log -1", True),
    ("git add -A", False),
    ("git commit -m x", False),
    ("git stash", False),
    ("git stash push -m x", False),
    ("git checkout -- file", False),
    ("git restore file", False),
    ("git reset --hard", False),
    ("git push", False),
    ("git fetch origin", False),
    ("git branch -D x", False),
    ("git clean -fd", False),
    ("git apply x.patch", False),
    ("git -C /repo checkout develop", False),
    ("cd /repo && git switch main", False),
    ("rm -rf node_modules", False),
    ("rm libs/x.ts", False),
    ("rm -f /tmp/x.diff", True),
    ("echo x > libs/a.ts", False),
    ("cat a >> b.md", False),
    ("echo x > \"libs/a.ts\"", False),
    ("sed -i 's/a/b/' file", False),
    ("sed -ie 's/a/b/' file", False),
    ("perl -pi -e 's/a/b/' f", False),
    ("pnpm test", False),
    ("pnpm install", False),
    ("npm run build", False),
    ("pnpm nx run-many -t test", False),
    ("npx nx affected -t lint", False),
    ("nx test app", False),
    ("pnpm exec playwright test", False),
    ("npx playwright test", False),
    ("npx tsc --noEmit -p x", False),
    ("pnpm typecheck", False),
    ("npx jest", False),
    ("npx prisma migrate dev", False),
    ("prisma db push", False),
    ("pnpm prisma:migrate", False),
    ("node scripts/seed-plans.mjs", False),
    ("npx tsx scripts/seed-company.ts", False),
    ("docker compose up -d", False),
    ("docker restart app-api", False),
    ("kill 1234", False),
    ("pkill -f nx", False),
    ("ssh prod 'ls'", False),
    ("curl https://api.payments.example/v3/payments", False),
    ("curl -X POST https://example.com/x", False),
    ("bash -c \"git commit -m x\"", False),
    ("sh -c 'rm -rf x'", False),
    ("redis-cli FLUSHALL", False),
    ("redis-cli -p 6379 DEL key", False),
    ("gh pr merge 1", False),
    ("gh api -X POST repos/x", False),
    ("./scripts/dev/reset-demo-schedule.ts", False),
    ("python3 - <<'PY'\nimport json\nif a > b:\n    rm = 1\nPY", True),
    ("psql \"$URL\" <<'SQL'\nBEGIN;\nSELECT count(*) FROM x WHERE a > 1;\nROLLBACK;\nSQL", True),
    ("bash <<'EOF'\ngit commit -m x\nEOF", False),
    ("cp libs/x.ts /tmp/x.ts", True),
    ("mv libs/x.ts /tmp/x.ts", False),
    ("find . -name '*.orig' -delete", False),
    ("find . -name x -exec rm {} \\;", False),
    ("find . -name '*.ts' -exec grep -l foo {} +", True),
    ("env -u FOO git commit -m x", False),
    ("sudo -u postgres git push", False),
    ("git log --format=%h->%s -3", True),
    ("ls &>/dev/null", True),
    ("git diff | tee review.diff", False),
    ("git diff | tee /tmp/review.diff", True),
    ("pnpm exec nx run app:test --testPathPatterns=x.spec.ts", True),
    ("nx run app:build", False),
    ("timeout 60 npx jest x.service.spec.ts", True),
    ("npx jest x.service.spec.ts --watch", False),
]


def self_test():
    failures = 0
    for command, allowed in SELF_TEST:
        reason = check_command(command)
        if (reason is None) != allowed:
            failures += 1
            print("FAILED: {!r} expected={} reason={}".format(command, "allow" if allowed else "block", reason))
    print("{} cases, {} failures".format(len(SELF_TEST), failures))
    return failures


def main():
    payload = json.load(sys.stdin)
    if payload.get("tool_name") != "Bash":
        return
    # A plugin agent ignores `hooks:` in its frontmatter: the plugin's hook runs on every Bash, so it filters here.
    if str(payload.get("agent_type") or "").split(":")[-1] != "critical-review":
        return
    command = (payload.get("tool_input") or {}).get("command") or ""
    reason = decide(command)
    if reason:
        print(json.dumps({
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": reason,
            }
        }, ensure_ascii=False))


if __name__ == "__main__":
    if sys.argv[1:] == ["--self-test"]:
        sys.exit(1 if self_test() else 0)
    try:
        main()
    except Exception:
        sys.exit(0)

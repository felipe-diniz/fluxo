#!/usr/bin/env python3
"""PreToolUse (Write|Edit|MultiEdit): keeps credentials out of the agent's memory.

Memory under `.claude/memory/` is versioned, and git keeps a secret forever; memory still in
`~/.claude/projects/<project>/memory/` may be brought into the repo later by /keel:memory. So a write whose new text
holds what looks like a credential is denied, with the reason, and goes back to the model to record the fact without
the value. Only high-precision patterns count, and placeholders (`<token>`, `${API_KEY}`, `xxxx`, `EXAMPLE`) pass.
Writes outside memory are not inspected. Any internal failure lets the write through.

Usage: reads the PreToolUse JSON on stdin. `--self-test` runs the cases.
"""
import json
import math
import os
import re
import sys

WRITE_TOOLS = ("Write", "Edit", "MultiEdit")
PREFIXED = (
    ("private key", re.compile(r"-----BEGIN (?:[A-Z0-9]+ )*PRIVATE KEY-----")),
    ("AWS access key", re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b")),
    ("GitHub token", re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{36,}|github_pat_[A-Za-z0-9_]{50,})")),
    ("GitLab token", re.compile(r"\bglpat-[A-Za-z0-9_\-]{20,}")),
    ("Slack token", re.compile(r"\bxox[abposr]-[A-Za-z0-9\-]{10,}")),
    ("Slack webhook", re.compile(r"https://hooks\.slack\.com/services/T[A-Z0-9]+/B[A-Z0-9]+/[A-Za-z0-9]{20,}")),
    ("Stripe key", re.compile(r"\b(?:sk|rk)_(?:live|test)_[A-Za-z0-9]{16,}")),
    ("Google API key", re.compile(r"\bAIza[0-9A-Za-z_\-]{35}")),
    ("Anthropic key", re.compile(r"\bsk-ant-[A-Za-z0-9_\-]{20,}")),
    ("OpenAI key", re.compile(r"\bsk-(?:proj-|svcacct-|admin-)?[A-Za-z0-9_\-]{32,}")),
    ("npm token", re.compile(r"\bnpm_[A-Za-z0-9]{36}\b")),
    ("SendGrid key", re.compile(r"\bSG\.[A-Za-z0-9_\-]{22}\.[A-Za-z0-9_\-]{43}")),
    ("JWT", re.compile(r"\beyJ[A-Za-z0-9_\-]{10,}\.eyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}")),
)
# A credential-named key followed by a value: `apiKey: ...`, `CLIENT_SECRET=...`, `"token": "..."`.
ASSIGNMENT = re.compile(
    r"(?i)\b[a-z0-9_.\-]*?(?:api[_\-]?key|secret|token|passw(?:or)?d|pwd|access[_\-]?key|private[_\-]?key)\b"
    r"[*_\"'`]*\s*(?:=>|[:=])\s*[\"'`]?([^\s\"'`,;)\]]+)"
)
URL_PASSWORD = re.compile(r"\b[a-z][a-z0-9+.\-]*://[^\s:/@\"'`]+:([^\s@/\"'`]+)@[^\s/\"'`]+")
BEARER = re.compile(r"(?i)\bbearer\s+([A-Za-z0-9_\-.=+/]{20,})")
PLACEHOLDER = re.compile(
    r"(?i)^(?:\$\{?[a-z0-9_]+\}?|%[a-z0-9_]+%|\{\{.*\}\}|\$\(.*\))$|x{4,}|\*{3,}|\.{3}|<|>|example|placeholder|"
    r"changeme|change_me|your[_\-]|redacted|dummy|fake|sample|process\.env|os\.environ|getenv"
)
# Where a credential lives, which is what the deny reason asks memory to keep: an env var name or a secret manager
# reference (GCP, AWS, Azure, 1Password).
REFERENCE = re.compile(
    r"^(?:[A-Z][A-Z0-9]*(?:_[A-Z0-9]+)+|projects/[^/\s]+/secrets/\S+|arn:aws:(?:secretsmanager|ssm):\S+|"
    r"https://[^/\s]+\.vault\.azure\.net/\S*|op://\S+)$"
)


def claude_home():
    return os.path.expanduser(os.environ.get("CLAUDE_CONFIG_DIR") or "~/.claude")


def entropy(value):
    counts = {}
    for char in value:
        counts[char] = counts.get(char, 0) + 1
    return -sum(count / len(value) * math.log2(count / len(value)) for count in counts.values())


def classes(value):
    return sum(bool(re.search(pattern, value)) for pattern in (r"[a-z]", r"[A-Z]", r"[0-9]", r"[^A-Za-z0-9]"))


def looks_random(value, minimum, need_digit):
    if len(value) < minimum or PLACEHOLDER.search(value) or REFERENCE.match(value) or classes(value) < 2:
        return False
    if need_digit and not re.search(r"[0-9]", value):
        return False
    return entropy(value) >= 3.0


def find_secret(text):
    """The kind of the first credential in the text, or None."""
    for kind, pattern in PREFIXED:
        for match in pattern.finditer(text):
            if not PLACEHOLDER.search(match.group(0)):
                return kind
    for match in URL_PASSWORD.finditer(text):
        if looks_random(match.group(1), 8, False):
            return "password in a connection URL"
    for match in BEARER.finditer(text):
        if looks_random(match.group(1), 20, True):
            return "bearer token"
    for match in ASSIGNMENT.finditer(text):
        if looks_random(match.group(1).rstrip("."), 10, True):
            return "credential assigned to a key"
    return None


def is_memory_path(path):
    if not path:
        return False
    real = os.path.realpath(os.path.expanduser(path))
    if "{0}.claude{0}memory{0}".format(os.sep) in real:
        return True
    projects = os.path.realpath(os.path.join(claude_home(), "projects")) + os.sep
    parts = real[len(projects):].split(os.sep) if real.startswith(projects) else []
    return len(parts) >= 3 and parts[1] == "memory"


def new_text(tool_name, tool_input):
    if tool_name == "Write":
        return tool_input.get("content") or ""
    if tool_name == "Edit":
        return tool_input.get("new_string") or ""
    return "\n".join(edit.get("new_string") or "" for edit in tool_input.get("edits") or [] if isinstance(edit, dict))


def decide(tool_name, tool_input):
    if tool_name not in WRITE_TOOLS or not is_memory_path(tool_input.get("file_path")):
        return None
    kind = find_secret(new_text(tool_name, tool_input))
    if not kind:
        return None
    return ("Not written: the new text holds what looks like a {}. Agent memory is versioned (git keeps it forever) "
            "or may be brought into the repo later. Record the fact without the value, e.g. where the credential "
            "lives (the env var or the secret manager entry). If it is not a secret, tell the user, who can write it "
            "by hand.").format(kind)


SELF_TEST = [
    ("token: ghp_" + "a1B2" * 9, "GitHub token"),
    ("key AKIA" + "ABCDEFGH12345678", "AWS access key"),
    ("AKIAIOSFODNN7EXAMPLE is the docs' sample", None),
    ("-----BEGIN RSA PRIVATE KEY-----\nMIIE...", "private key"),
    ("-----BEGIN OPENSSH PRIVATE KEY-----", "private key"),
    ("live key sk_live_" + "4eC39HqLyjWDarjtT1zdp7dc", "Stripe key"),
    ("sk_test_xxxxxxxxxxxxxxxxxxxx", None),
    ("ANTHROPIC_API_KEY=sk-ant-api03-" + "Zx9_" * 8, "Anthropic key"),
    ("export OPENAI_API_KEY=sk-proj-" + "Ab3d" * 10, "OpenAI key"),
    ("AIza" + "SyA1b2C3d4E5f6G7h8I9j0K1l2M3n4O5p6Q", "Google API key"),
    ("jwt eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dozjgNryP4J3jVmNHl0w5N_XgL0n3I9PlFUP0THsR8U", "JWT"),
    ("mongodb+srv://app:Xk9mQ2vR7t@cluster0.mongodb.net/db", "password in a connection URL"),
    ("postgresql://app:x@localhost:5432/app", None),
    ("postgres://postgres:postgres@localhost:5432/dev", None),
    ("mongodb+srv://<user>:<password>@cluster0.mongodb.net", None),
    ("Authorization: Bearer 8f3kA92jdLq0ZpX7vB4nT6yW", "bearer token"),
    ("Authorization: Bearer <token>", None),
    ('{"client_secret": "GOCSPX-4kL9mN2pQ7rS1tV8wX3y"}', "credential assigned to a key"),
    ("APP_TOKEN=EAAGm0PX4ZCpsBAKZB9rZCq1x2y3z4", "credential assigned to a key"),
    ("**Password**: Tr0ub4dor&3xyz", "credential assigned to a key"),
    ("apiKey: ${PAYMENT_API_KEY}", None),
    ("token = process.env.WEBHOOK_TOKEN", None),
    ("`APP_TOKEN` is the analytics token; sending uses the channel token", None),
    ("tokenCount: 1234567890123", None),
    ("authorId: 64f1a2b3c4d5e6f708192a3b", None),
    ("secretVersion=2026-10-20", None),
    ("password: hunter2", None),
    ("Never store the token in memory: it lives in the env.", None),
    ("commit 4b825dc642cb6eb9a060e54bf8d69288fbee4904 fixed the token refresh", None),
    ("token: ASAAS_API_KEY_V2", None),
    ("secret: projects/acme-app/secrets/payment-api-key/versions/3", None),
    ("apiKey: arn:aws:secretsmanager:us-east-1:123456789012:secret:prod/db-AbCdEf", None),
    ("client_secret: https://kv-prod2.vault.azure.net/secrets/client-secret/0f3c9a7b", None),
    ("password: op://Private/db2/password", None),
    ("totp secret: JBSWY3DPEHPK3PXP7Q", "credential assigned to a key"),
]


def self_test():
    failures = 0
    for text, expected in SELF_TEST:
        found = find_secret(text)
        if found != expected:
            failures += 1
            print("FAILED: {!r} expected={} found={}".format(text[:70], expected, found))
    home = claude_home()
    paths = [
        ("/repo/.claude/memory/ana/MEMORY.md", True),
        (os.path.join(home, "projects", "-repo", "memory", "fact.md"), True),
        (os.path.join(home, "projects", "-repo", "session.jsonl"), False),
        ("/repo/docs/memory/notes.md", False),
        ("/repo/src/app.ts", False),
    ]
    for path, expected in paths:
        if is_memory_path(path) != expected:
            failures += 1
            print("FAILED: path {} expected={}".format(path, expected))
    secret = "token: ghp_" + "a1B2" * 9
    cases = [
        (("Edit", {"file_path": "/repo/.claude/memory/ana/x.md", "old_string": secret, "new_string": "fixed"}), False),
        (("Write", {"file_path": "/repo/.claude/memory/ana/x.md", "content": secret}), True),
        (("MultiEdit", {"file_path": "/repo/.claude/memory/ana/x.md", "edits": [{"new_string": secret}]}), True),
        (("Write", {"file_path": "/repo/src/config.ts", "content": secret}), False),
    ]
    for (tool_name, tool_input), denied in cases:
        if bool(decide(tool_name, tool_input)) != denied:
            failures += 1
            print("FAILED: {} {} expected denied={}".format(tool_name, tool_input.get("file_path"), denied))
    print("{} cases, {} failures".format(len(SELF_TEST) + len(paths) + len(cases), failures))
    return failures


def main():
    payload = json.load(sys.stdin)
    reason = decide(payload.get("tool_name"), payload.get("tool_input") or {})
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

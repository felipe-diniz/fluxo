#!/usr/bin/env python3
"""PreToolUse (Agent|Task) for the `critical-review` pre-commit gate.

0. Effort: `max` belongs to the gate alone, through its frontmatter. Denies a gate call that passes `model` or
   `effort` (the call's parameter beats the frontmatter) and asks the user to confirm any other subagent called
   with `effort: max`.
1. Denies a call without the minimum briefing: lines `Request:`, `Scope:`, `Verified:` and `Risk:` (the Portuguese
   `Pedido:`, `Escopo:`, `Verificado:` and `Risco:` count too). The gate is only for critical risk: without `Risk:`
   there is nothing for it to review. Without an explicit scope the gate rederives everything from the whole tree,
   which often holds other sessions' work, and redoes what was already verified: the review's biggest cost. The
   denial goes back to the model with the briefing template, without involving the user.
2. Counts the gate's previous calls in the session (from the transcript; ignores the current one and those that
   failed, were denied or were interrupted):
   - none: the normal flow goes on;
   - one, and the prompt opens with `RE-REVIEW P0` (or `RE-REVISÃO P0`): goes on (a re-review marked by the report);
   - any other case: asks the user to confirm (a headless session denies).
Any read failure lets the call through: the hook is a cost guard and must not block the work.
"""
import json
import re
import sys
import unicodedata

AGENT_TOOLS = ("Agent", "Task")
TARGET = "critical-review"


def is_target(subagent_type):
    # The plugin's agent arrives as `keel:critical-review`; the bare name covers a copy installed as a user agent.
    return str(subagent_type or "").split(":")[-1] == TARGET
REQUIRED = (
    ("Request", ("request", "pedido")),
    ("Scope", ("scope", "escopo")),
    ("Verified", ("verified", "verificado")),
    ("Risk", ("risk", "risco")),
)
TEMPLATE = (
    "Request: <what the user asked for, in their words, and the source doc>\n"
    "Scope: <hunks that change a critical invariant and their siblings (who calls, who consumes, the tests); what "
    "stays out>\n"
    "Verified: <what already ran and the result; whether the environment is up>\n"
    "Risk: <critical domains touched and the invariants at stake>"
)
FAILED_RESULT_MARKERS = (
    "doesn't want to proceed",
    "was rejected",
    "permission denied",
    "hook denied",
    "blocked by hook",
    "interrupted by user",
    "[request interrupted",
)


def fold(text):
    normalized = unicodedata.normalize("NFKD", text)
    return "".join(char for char in normalized if not unicodedata.combining(char)).lower()


def missing_labels(prompt):
    folded = fold(prompt)
    missing = []
    for label, aliases in REQUIRED:
        pattern = r"(?m)^[\s>#*_\-]*(?:%s)\b[*_]*\s*(?::|$)" % "|".join(aliases)
        if not re.search(pattern, folded):
            missing.append(label)
    return missing


def is_marked_rereview(prompt):
    first_line = next((line for line in prompt.splitlines() if line.strip()), "")
    return bool(re.match(r"^[\s>#*_\-]*re-?(?:review|revisao)\s+p0\b", fold(first_line)))


def result_text(block):
    content = block.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return " ".join(part.get("text", "") for part in content if isinstance(part, dict))
    return ""


def previous_reviews(transcript_path, current_id, current_input):
    calls = {}
    failed = set()
    skipped_current = False
    with open(transcript_path, encoding="utf-8") as transcript:
        for line in transcript:
            try:
                entry = json.loads(line)
            except ValueError:
                continue
            message = entry.get("message") or {}
            content = message.get("content")
            if not isinstance(content, list):
                continue
            for block in content:
                if not isinstance(block, dict):
                    continue
                if block.get("type") == "tool_use" and block.get("name") in AGENT_TOOLS:
                    tool_input = block.get("input") or {}
                    if not is_target(tool_input.get("subagent_type")):
                        continue
                    block_id = block.get("id")
                    if current_id and block_id == current_id:
                        continue
                    # Without a tool_use_id in the payload, skip one occurrence identical to the current call.
                    if not current_id and not skipped_current and tool_input == current_input:
                        skipped_current = True
                        continue
                    # A call without the briefing or with an override never ran: this same hook denied it.
                    if missing_labels(tool_input.get("prompt") or ""):
                        continue
                    if tool_input.get("model") or tool_input.get("effort"):
                        continue
                    calls[block_id] = tool_input.get("description", "")
                elif block.get("type") == "tool_result":
                    text = result_text(block).lower()
                    # Denials and interruptions come back short; a gate report is long and may quote the same words.
                    rejected = len(text) < 600 and any(marker in text for marker in FAILED_RESULT_MARKERS)
                    if block.get("is_error") or rejected:
                        failed.add(block.get("tool_use_id"))
    return [description for block_id, description in calls.items() if block_id not in failed]


def emit(decision, reason):
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": decision,
            "permissionDecisionReason": reason,
        }
    }, ensure_ascii=False))


def main():
    payload = json.load(sys.stdin)
    if payload.get("tool_name") not in AGENT_TOOLS:
        return
    tool_input = payload.get("tool_input") or {}
    if not is_target(tool_input.get("subagent_type")):
        if str(tool_input.get("effort") or "").strip().lower() == "max":
            emit("ask", (
                "effort max belongs to critical-review alone, through its frontmatter; the session and the other "
                "subagents stay at the inherited effort (depth on one step is ultrathink). Approve only if the user "
                "asked for max for this subagent."
            ))
        return
    overrides = [key for key in ("model", "effort") if tool_input.get(key)]
    if overrides:
        emit("deny", (
            "critical-review called with a {keys} override: it runs on the session's model and at max through its "
            "own frontmatter, and the call's parameter would beat the frontmatter. Call it again without {keys}."
        ).format(keys=" and ".join(overrides)))
        return
    prompt = tool_input.get("prompt") or ""

    missing = missing_labels(prompt)
    if missing:
        emit("deny", (
            "Incomplete critical-review briefing: missing {missing}. The gate is only for critical risk and reviews "
            "only the declared critical slice (the critical hunks and their siblings), without redoing what was "
            "already verified. With no critical domain touched, don't call the gate: close with the tests, the lint "
            "and the request × delivery check. Otherwise, call it again with these lines in the prompt:\n{template}"
        ).format(missing=", ".join(missing), template=TEMPLATE))
        return

    transcript_path = payload.get("transcript_path")
    if not transcript_path:
        return
    previous = previous_reviews(transcript_path, payload.get("tool_use_id"), tool_input)
    if not previous:
        return
    if len(previous) == 1 and is_marked_rereview(prompt):
        return

    listed = "; ".join(description or "(no description)" for description in previous[-3:])
    emit("ask", (
        "critical-review already ran {count}x in this session ({listed}). Rule: ONE pass per delivery, at the end, "
        "before the commit, over the critical slice. A new pass only for a P0 marked 're-review: yes', over the fix's "
        "delta, once, with 'RE-REVIEW P0' on the prompt's first line. Approve only if it is a new delivery that will "
        "be committed separately."
    ).format(count=len(previous), listed=listed))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        sys.exit(0)

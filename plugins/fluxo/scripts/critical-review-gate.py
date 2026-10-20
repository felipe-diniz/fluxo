#!/usr/bin/env python3
"""PreToolUse (Agent|Task) do gate de pré-commit `critical-review`.

0. Effort: o `max` é só do gate, pelo frontmatter dele. Recusa (deny) a chamada ao gate que passe `model` ou
   `effort` (o parâmetro da chamada vence o frontmatter) e pede confirmação do usuário para qualquer outro
   subagent chamado com `effort: max`.
1. Recusa (deny) a chamada sem o briefing mínimo: linhas `Pedido:`, `Escopo:`, `Verificado:` e `Risco:`.
   O gate é só de risco crítico: sem `Risco:` não há o que ele revisar.
   Sem escopo explícito o gate rederiva tudo da árvore inteira, que costuma ter trabalho de outras
   sessões, e refaz o que já foi verificado: é a maior fonte de custo da revisão. A recusa volta ao
   modelo com o molde do briefing, sem envolver o usuário.
2. Conta as chamadas anteriores do gate na sessão (pelo transcript; ignora a atual e as que falharam,
   foram recusadas ou interrompidas):
   - nenhuma: segue o fluxo normal;
   - uma, e o prompt abre com `RE-REVISÃO P0`: segue (re-revisão marcada pelo relatório);
   - qualquer outro caso: pede confirmação do usuário (sessão headless recusa).
Qualquer falha de leitura deixa passar: o hook é guarda de custo, não pode travar o trabalho.
"""
import json
import re
import sys
import unicodedata

AGENT_TOOLS = ("Agent", "Task")
TARGET = "critical-review"


def is_target(subagent_type):
    # O agente do plugin chega como `fluxo:critical-review`; o nome sem prefixo cobre uma cópia como agente de usuário.
    return str(subagent_type or "").split(":")[-1] == TARGET
REQUIRED = (
    ("Pedido", ("pedido", "request")),
    ("Escopo", ("escopo", "scope")),
    ("Verificado", ("verificado", "verified")),
    ("Risco", ("risco", "risk")),
)
TEMPLATE = (
    "Pedido: <o que o usuário pediu, nas palavras dele, e o doc de origem>\n"
    "Escopo: <hunks que mudam invariante crítica e os irmãos (quem chama, quem consome, os testes); o que fica fora>\n"
    "Verificado: <o que já rodou e o resultado; ambiente de pé ou não>\n"
    "Risco: <domínios críticos tocados e invariantes em jogo>"
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
    return bool(re.match(r"^[\s>#*_\-]*re-?revisao\s+p0\b", fold(first_line)))


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
                    # Sem tool_use_id no payload, descarta uma ocorrência idêntica à chamada atual.
                    if not current_id and not skipped_current and tool_input == current_input:
                        skipped_current = True
                        continue
                    # Chamada sem briefing ou com override nunca rodou: este mesmo hook a recusou.
                    if missing_labels(tool_input.get("prompt") or ""):
                        continue
                    if tool_input.get("model") or tool_input.get("effort"):
                        continue
                    calls[block_id] = tool_input.get("description", "")
                elif block.get("type") == "tool_result":
                    text = result_text(block).lower()
                    # Recusa e interrupção voltam curtas; relatório do gate é longo e pode citar as mesmas palavras.
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
                "effort max é só do critical-review, pelo frontmatter dele; a sessão e os outros subagents ficam no "
                "effort herdado (profundidade num passo é ultrathink). Aprove só se o usuário pediu max para este "
                "subagent."
            ))
        return
    overrides = [key for key in ("model", "effort") if tool_input.get(key)]
    if overrides:
        emit("deny", (
            "critical-review chamado com override de {keys}: ele roda no modelo da sessão e em max pelo próprio "
            "frontmatter, e o parâmetro da chamada venceria o frontmatter. Refaça a chamada sem {keys}."
        ).format(keys=" e ".join(overrides)))
        return
    prompt = tool_input.get("prompt") or ""

    missing = missing_labels(prompt)
    if missing:
        emit("deny", (
            "Briefing do critical-review incompleto: falta {missing}. O gate é só de risco crítico e revisa só o "
            "recorte declarado (hunks críticos e irmãos), sem refazer o que já foi verificado. Sem domínio crítico "
            "tocado, não chame o gate: feche com os testes, o lint e a conferência pedido × feito. Senão, refaça a "
            "chamada com estas linhas no prompt:\n{template}"
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

    listed = "; ".join(description or "(sem descrição)" for description in previous[-3:])
    emit("ask", (
        "critical-review já rodou {count}x nesta sessão ({listed}). Regra: UMA passada por sessão, no fim, "
        "antes do commit, sobre tudo o que a sessão fez. Nova passada só para P0 marcado 're-revisão: sim', "
        "sobre o delta da correção, uma vez, com 'RE-REVISÃO P0' na primeira linha do prompt. Aprove só se "
        "for uma entrega nova que vai ser commitada à parte."
    ).format(count=len(previous), listed=listed))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        sys.exit(0)

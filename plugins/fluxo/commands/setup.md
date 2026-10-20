---
description: Instala ou atualiza a parte do fluxo que plugin não carrega (agentes de usuário, guard do gate, bloco de regras no ~/.claude/CLAUDE.md)
---

Rode `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/setup.py"` (sem argumento é só o plano, não escreve nada) e mostre ao usuário, em lista curta, o que ele vai criar, substituir ou deixar como está, e os avisos.

Peça o OK explícito do usuário. Só com o OK, rode `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/setup.py" --apply` e repasse a saída: onde ficou o backup do que foi substituído e os avisos que pedem ação manual (por exemplo, um hook do gate antigo ainda registrado no `~/.claude/settings.json`, que agora vem do plugin e rodaria duas vezes).

Não edite nada à mão, não passe outra flag e não rode o `--apply` sem o OK.

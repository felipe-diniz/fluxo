---
description: Remove a instalação manual antiga do fluxo (agentes, hooks, skill, seções do CLAUDE.md) para valer só o plugin
allowed-tools: Bash(python3 *)
disable-model-invocation: true
---

1. Rode `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/migrar.py"` e mostre o plano ao usuário como veio.
2. Se o plano disser que não há nada a migrar, pare aí.
3. Pergunte se pode aplicar. Só com o sim, rode `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/migrar.py" --apply` e mostre o resultado.
4. Lembre que vale a partir da próxima sessão e onde ficou o backup.

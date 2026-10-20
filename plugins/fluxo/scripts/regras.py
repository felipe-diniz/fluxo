#!/usr/bin/env python3
"""SessionStart: põe as regras do fluxo no contexto (plugin não carrega CLAUDE.md).

Roda também depois da compactação (source "compact"), então as regras voltam ao contexto. O stdout é limitado
a 10.000 caracteres: o regras.md tem de caber nisso. Havendo instalação manual antiga, acrescenta uma linha
pedindo o /fluxo:migrar. Falha interna fica calada.
"""
import os
import sys

try:
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    with open(os.path.join(root, "regras.md"), encoding="utf-8") as rules:
        sys.stdout.write(rules.read())
    sys.path.insert(0, os.path.join(root, "scripts"))
    import migrar

    if migrar.has_work(migrar.plan()):
        sys.stdout.write(
            "\nAVISO DO PLUGIN: há uma instalação manual antiga do fluxo (agentes, hooks, skill ou seções do "
            "~/.claude/CLAUDE.md) duplicando o plugin. Na primeira resposta, sugira ao usuário rodar /fluxo:migrar.\n"
        )
except Exception:
    pass

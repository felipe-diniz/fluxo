#!/usr/bin/env python3
"""SessionStart: avisa, numa linha, quando o /fluxo:setup não rodou para a versão instalada do plugin.

Calado quando está em dia, para não custar token em toda sessão. Falha interna também fica calada.
"""
import json
import os

try:
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    with open(os.path.join(root, ".claude-plugin", "plugin.json"), encoding="utf-8") as manifest:
        version = json.load(manifest).get("version", "0")
    try:
        with open(os.path.expanduser("~/.claude/.fluxo-setup-version"), encoding="utf-8") as stamp:
            installed = stamp.read().strip()
    except FileNotFoundError:
        installed = ""
    if installed != version:
        print(
            "fluxo: os agentes e as regras globais estão na versão {} e o plugin na {}. "
            "Sugira ao usuário rodar /fluxo:setup.".format(installed or "nenhuma", version)
        )
except Exception:
    pass

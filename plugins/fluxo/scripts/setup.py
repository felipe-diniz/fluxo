#!/usr/bin/env python3
"""Instala a parte do fluxo que um plugin não carrega.

- Agentes em ~/.claude/agents/: agente de plugin ganha prefixo (`fluxo:x`), ignora `hooks:` no frontmatter e não
  substitui o `Explore` embutido. Como agente de usuário, o `critical-review` mantém o guard de Bash e o `Explore`
  substitui o embutido.
- Guard de Bash do gate em ~/.claude/hooks/review-bash-guard.py (o frontmatter do `critical-review` aponta para lá).
- Bloco de regras no ~/.claude/CLAUDE.md, entre marcadores: o resto do arquivo do usuário fica intacto.
- Skill pessoal `coordenar-sessoes` antiga: vai para o backup, porque a do plugin a substitui.

Sem argumento: só mostra o plano. `--apply`: executa, com backup em ~/.claude/backups/fluxo-<data>/.
"""
import datetime
import difflib
import json
import os
import shutil
import sys

PLUGIN_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAYLOAD = os.path.join(PLUGIN_ROOT, "payload")
HOME_CLAUDE = os.path.expanduser("~/.claude")
STAMP = os.path.join(HOME_CLAUDE, ".fluxo-setup-version")
BEGIN = "<!-- fluxo:inicio (gerenciado pelo /fluxo:setup; edite no repo do plugin) -->"
END = "<!-- fluxo:fim -->"


def plugin_version():
    with open(os.path.join(PLUGIN_ROOT, ".claude-plugin", "plugin.json"), encoding="utf-8") as manifest:
        return json.load(manifest).get("version", "0")


def read(path):
    try:
        with open(path, encoding="utf-8") as handle:
            return handle.read()
    except FileNotFoundError:
        return None


def changed_lines(old, new):
    diff = difflib.unified_diff((old or "").splitlines(), new.splitlines(), lineterm="", n=0)
    return sum(1 for line in diff if line[:1] in "+-" and line[:3] not in ("+++", "---"))


def file_actions():
    actions = []
    for folder, target_dir in (("agents", "agents"), ("hooks", "hooks")):
        for name in sorted(os.listdir(os.path.join(PAYLOAD, folder))):
            source = os.path.join(PAYLOAD, folder, name)
            target = os.path.join(HOME_CLAUDE, target_dir, name)
            new = read(source)
            old = read(target)
            if old == new:
                actions.append(("igual", target, None))
            else:
                kind = "criar" if old is None else "substituir ({} linhas mudam)".format(changed_lines(old, new))
                actions.append((kind, target, new))
    return actions


def claude_md_action():
    target = os.path.join(HOME_CLAUDE, "CLAUDE.md")
    block_body = read(os.path.join(PAYLOAD, "CLAUDE.md")).strip("\n")
    block = "{}\n{}\n{}\n".format(BEGIN, block_body, END)
    current = read(target)
    if current is None:
        return ("criar", target, block, None)
    if BEGIN in current and END in current:
        head, rest = current.split(BEGIN, 1)
        _, tail = rest.split(END, 1)
        new = head + block + tail.lstrip("\n")
        if new == current:
            return ("igual", target, None, None)
        return ("substituir o bloco ({} linhas mudam)".format(changed_lines(current, new)), target, new, None)
    if current.strip("\n") == block_body:
        return ("envolver com os marcadores (conteúdo igual)", target, block, None)
    warning = (
        "~/.claude/CLAUDE.md não tem o bloco do fluxo: o bloco entra no FIM do arquivo. Se o arquivo já tem regras "
        "parecidas (gate, roteamento de agentes), revise depois para não ficarem duplicadas."
    )
    return ("acrescentar o bloco no fim", target, current.rstrip("\n") + "\n\n" + block, warning)


def legacy_skill():
    path = os.path.join(HOME_CLAUDE, "skills", "coordenar-sessoes")
    return path if os.path.isdir(path) else None


def legacy_settings_hook():
    settings = read(os.path.join(HOME_CLAUDE, "settings.json")) or ""
    return "critical-review-gate.py" in settings


def main():
    apply = "--apply" in sys.argv[1:]
    version = plugin_version()
    actions = file_actions()
    md_kind, md_target, md_new, md_warning = claude_md_action()
    skill = legacy_skill()
    warnings = []
    if md_warning:
        warnings.append(md_warning)
    if legacy_settings_hook():
        warnings.append(
            "~/.claude/settings.json ainda registra o critical-review-gate.py. O plugin já registra esse hook: "
            "remova a entrada do settings.json (PreToolUse, matcher Agent|Task), senão ele roda duas vezes."
        )

    print("fluxo {} — {}".format(version, "aplicando" if apply else "plano (nada foi escrito; rode com --apply)"))
    for kind, target, _ in actions:
        print("- {}: {}".format(kind, target))
    print("- {}: {}".format(md_kind, md_target))
    if skill:
        print("- mover para o backup a skill pessoal antiga: {} (a do plugin a substitui)".format(skill))
    for warning in warnings:
        print("AVISO: " + warning)
    if not apply:
        return

    backup = os.path.join(HOME_CLAUDE, "backups", "fluxo-" + datetime.datetime.now().strftime("%Y%m%d-%H%M%S"))

    def keep_copy(path):
        if os.path.exists(path):
            destination = os.path.join(backup, os.path.relpath(path, HOME_CLAUDE))
            os.makedirs(os.path.dirname(destination), exist_ok=True)
            if os.path.isdir(path):
                shutil.copytree(path, destination)
            else:
                shutil.copy2(path, destination)

    for kind, target, new in actions:
        if new is None:
            continue
        keep_copy(target)
        os.makedirs(os.path.dirname(target), exist_ok=True)
        with open(target, "w", encoding="utf-8") as handle:
            handle.write(new)
        if target.endswith(".py"):
            os.chmod(target, 0o755)
    if md_new is not None:
        keep_copy(md_target)
        with open(md_target, "w", encoding="utf-8") as handle:
            handle.write(md_new)
    if skill:
        keep_copy(skill)
        shutil.rmtree(skill)
    with open(STAMP, "w", encoding="utf-8") as handle:
        handle.write(version + "\n")
    print("feito. Backup do que foi substituído: {}".format(backup if os.path.isdir(backup) else "nada a guardar"))
    print("Abra uma sessão nova para os agentes e o CLAUDE.md valerem.")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Remove a instalação manual do fluxo (de antes do plugin), para o plugin valer sozinho.

O que sai, tudo com backup em ~/.claude/backups/fluxo-<data>/:
- agentes de usuário com os nomes do fluxo (Explore, implement, research, critical-review) em ~/.claude/agents/;
- os hooks copiados à mão em ~/.claude/hooks/ (critical-review-gate.py, review-bash-guard.py);
- a skill pessoal ~/.claude/skills/coordenar-sessoes;
- as entradas desses hooks no ~/.claude/settings.json;
- do ~/.claude/CLAUDE.md, só as seções com o mesmo título das seções do regras.md do plugin (e o bloco
  <!-- fluxo:inicio --> de versões antigas). O resto do arquivo fica.

Sem argumento: só mostra o plano. `--apply`: executa.
`--check`: sai com código 1 quando há algo a migrar, calado (usado pelo hook de início de sessão).
"""
import datetime
import json
import os
import re
import shutil
import sys

PLUGIN_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOME_CLAUDE = os.path.expanduser("~/.claude")
AGENT_NAMES = {"explore", "implement", "research", "critical-review"}
HOOK_FILES = ("critical-review-gate.py", "review-bash-guard.py")
OLD_BLOCK = re.compile(r"<!-- fluxo:inicio[^>]*-->.*?<!-- fluxo:fim -->\n?", re.DOTALL)


def read(path):
    try:
        with open(path, encoding="utf-8") as handle:
            return handle.read()
    except FileNotFoundError:
        return None


def agent_name(text):
    match = re.match(r"---\n(.*?)\n---", text, re.DOTALL)
    if not match:
        return None
    found = re.search(r"(?m)^name:\s*['\"]?([^'\"\n]+)", match.group(1))
    return found.group(1).strip().lower() if found else None


def legacy_agents():
    folder = os.path.join(HOME_CLAUDE, "agents")
    if not os.path.isdir(folder):
        return []
    paths = []
    for file_name in sorted(os.listdir(folder)):
        path = os.path.join(folder, file_name)
        if file_name.endswith(".md") and agent_name(read(path) or "") in AGENT_NAMES:
            paths.append(path)
    return paths


def legacy_hooks():
    return [path for path in (os.path.join(HOME_CLAUDE, "hooks", name) for name in HOOK_FILES) if os.path.isfile(path)]


def legacy_skill():
    path = os.path.join(HOME_CLAUDE, "skills", "coordenar-sessoes")
    return path if os.path.isdir(path) else None


def mentions_fluxo_hook(hook):
    text = json.dumps(hook)
    return any(name in text for name in HOOK_FILES)


def cleaned_settings():
    path = os.path.join(HOME_CLAUDE, "settings.json")
    text = read(path)
    if not text:
        return None
    try:
        settings = json.loads(text)
    except ValueError:
        return None
    events = settings.get("hooks")
    if not isinstance(events, dict):
        return None
    removed = 0
    for event in list(events):
        groups = []
        for group in events[event] or []:
            hooks = [hook for hook in group.get("hooks", []) if not mentions_fluxo_hook(hook)]
            removed += len(group.get("hooks", [])) - len(hooks)
            if hooks:
                groups.append(dict(group, hooks=hooks))
        if groups:
            events[event] = groups
        else:
            del events[event]
    if not removed:
        return None
    if not events:
        del settings["hooks"]
    return path, json.dumps(settings, ensure_ascii=False, indent=2) + "\n", removed


def plugin_headings():
    rules = read(os.path.join(PLUGIN_ROOT, "regras.md")) or ""
    # O regras.md diz `fluxo:critical-review`; a cópia manual antiga, `critical-review`.
    return {normalize(line) for line in rules.splitlines() if line.startswith("# ") and line.strip() != "# fluxo"}


def normalize(heading):
    return heading.strip().replace("fluxo:", "")


def cleaned_claude_md():
    path = os.path.join(HOME_CLAUDE, "CLAUDE.md")
    text = read(path)
    if not text:
        return None
    headings = plugin_headings()
    sections = re.split(r"(?m)^(?=# )", OLD_BLOCK.sub("", text))
    kept = []
    removed = []
    for section in sections:
        heading = section.splitlines()[0].strip() if section else ""
        if section.startswith("# ") and normalize(heading) in headings:
            removed.append(heading)
        else:
            kept.append(section)
    new = "".join(kept).strip("\n")
    new = new + "\n" if new else ""
    if new == text:
        return None
    return path, new, removed or ["bloco <!-- fluxo:inicio --> antigo"]


def plan():
    return {
        "agents": legacy_agents(),
        "hooks": legacy_hooks(),
        "skill": legacy_skill(),
        "settings": cleaned_settings(),
        "claude_md": cleaned_claude_md(),
        "stamp": os.path.join(HOME_CLAUDE, ".fluxo-setup-version")
        if os.path.isfile(os.path.join(HOME_CLAUDE, ".fluxo-setup-version")) else None,
    }


def has_work(steps):
    return any(steps.values())


def main():
    args = sys.argv[1:]
    steps = plan()
    if "--check" in args:
        sys.exit(1 if has_work(steps) else 0)
    apply = "--apply" in args
    if not has_work(steps):
        print("Nada a migrar: não há instalação manual antiga do fluxo.")
        return
    print("Migração do fluxo — {}".format("aplicando" if apply else "plano (nada foi escrito; rode com --apply)"))
    for path in steps["agents"]:
        print("- mover para o backup o agente de usuário {} (o plugin traz o fluxo:{})".format(
            path, agent_name(read(path) or "")))
    for path in steps["hooks"]:
        print("- mover para o backup o hook {} (o plugin registra o dele)".format(path))
    if steps["skill"]:
        print("- mover para o backup a skill pessoal {} (o plugin traz a fluxo:coordenar-sessoes)".format(steps["skill"]))
    if steps["settings"]:
        print("- tirar do {} as {} entradas de hook do fluxo".format(steps["settings"][0], steps["settings"][2]))
    if steps["claude_md"]:
        print("- tirar do {} as seções que o plugin já carrega: {}".format(
            steps["claude_md"][0], "; ".join(steps["claude_md"][2])))
    if steps["stamp"]:
        print("- apagar o carimbo de versão antigo {}".format(steps["stamp"]))
    if not apply:
        return

    backup = os.path.join(HOME_CLAUDE, "backups", "fluxo-" + datetime.datetime.now().strftime("%Y%m%d-%H%M%S"))

    def move_to_backup(path):
        destination = os.path.join(backup, os.path.relpath(path, HOME_CLAUDE))
        os.makedirs(os.path.dirname(destination), exist_ok=True)
        shutil.move(path, destination)

    def rewrite(path, content):
        destination = os.path.join(backup, os.path.relpath(path, HOME_CLAUDE))
        os.makedirs(os.path.dirname(destination), exist_ok=True)
        shutil.copy2(path, destination)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(content)

    for path in steps["agents"] + steps["hooks"]:
        move_to_backup(path)
    if steps["skill"]:
        move_to_backup(steps["skill"])
    if steps["settings"]:
        rewrite(steps["settings"][0], steps["settings"][1])
    if steps["claude_md"]:
        rewrite(steps["claude_md"][0], steps["claude_md"][1])
    if steps["stamp"]:
        move_to_backup(steps["stamp"])
    print("Feito. Backup: {}".format(backup))
    print("Abra uma sessão nova para valer só o plugin.")


if __name__ == "__main__":
    main()

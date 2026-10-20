---
name: coordenar-sessoes
description: Método da sessão COORDENADORA, igual em todo projeto — abrir sessões de verdade do Claude Code em background (`claude --bg`), uma por frente ou fase, em vez de subagentes; montar o prompt de cada uma com o rodapé de regras; conversar por mensagem entre sessões; dividir o que a máquina e a branch têm de um só; levar aprovação e decisão ao dono; retomar sessão parada; e fechar com commit só do que é da sessão (direto ou por índice temporário), prova pelo risco e push só com o sim do dono. O que é do projeto (recursos, prova, push, deploy) está no perfil do projeto (`.claude/coordenacao/` no repo, ou `~/.claude/coordination/<projeto>/perfil/`, ou derivado do CLAUDE.md na primeira vez). Use SEMPRE que o dono pedir para tocar frentes ou fases por sessões, "abrir sessões", "disparar uma sessão", "abrir a próxima fase", coordenar sessões que já rodam, ou retomar sessões paradas.
---

# Coordenar sessões

A coordenadora não implementa a frente: ela escreve o prompt, abre a sessão, libera a vez de cada recurso que a máquina
tem um só, leva aprovação e decisão ao dono, confere o commit contra o relatório e, com o sim do dono, faz o push. Cada
frente vive numa sessão própria, com contexto próprio, gate próprio e commit próprio.

## 0. O projeto

O método é este arquivo; o projeto entra por três coisas, resolvidas no começo:

- **Checkout e nome:** `CHECKOUT=$(git rev-parse --show-toplevel)`, `SLUG=$(basename "$CHECKOUT")`.
- **Estado da coordenação**, fora do repo: `D=~/.claude/coordination/$SLUG/` (§3).
- **Perfil do projeto** (`perfil.md`) — o prefixo do nome das sessões, a branch, a tabela do que é de um só, os comandos
  dos níveis de prova, o commit/push/PR, a lista do deploy, o que é proibido em produção e para onde vai débito — e as
  **regras da sessão** (`sessao.md`), o bloco que entra em todo prompt depois do rodapé global (§4). Procure nesta ordem
  e use a primeira pasta que tiver os dois (`P_DIR`):
  1. `$CHECKOUT/.claude/coordenacao/` — versionado, vale para o time inteiro (projeto com mais de um dev);
  2. `$D/perfil/` — pessoal, fora do repo (projeto só seu, ou que não deve levar arquivo de coordenação);
  3. nenhum: **derive-o você** antes de abrir a primeira sessão, a partir do `CLAUDE.md` do repo, do doc de risco que
     ele aponta, do `.claude/settings.json`, do lockfile/`package.json`/hooks de git e de `.husky/` ou equivalente;
     grave em `$D/perfil/` seguindo [modelos/perfil.md](modelos/perfil.md) e pergunte ao dono só o que nenhum arquivo
     responde (branch de trabalho, se há outro dev no remoto, quem faz o push, o que é proibido em produção).
  **Leia o perfil inteiro antes de lançar ou retomar a primeira sessão.** O que ele diz vence este arquivo.

O estado do shell não passa de uma chamada do Bash tool para a outra: resolva `CHECKOUT`, `SLUG`, `D` e `P_DIR` uma vez e use os
caminhos literais nos comandos seguintes. Nada aqui nomeia projeto; nada no prompt de uma sessão cita outro projeto.

## 1. Sessão, subagente ou direto

| O trabalho | Vai para | Por quê |
|---|---|---|
| Frente ou fase com commit próprio, horas de trabalho, várias camadas | **sessão `--bg`** | contexto, gate e commit próprios; não engorda a coordenadora |
| Leitura ampla, mapa de código, "quem chama" | `fluxo:explore` (subagente) | a coordenadora só precisa da síntese |
| Pesquisa web | `fluxo:research` (subagente) | idem |
| Conserto curto (≲ 5 arquivos, um domínio, sem fase de PRD), doc, memória, ajuste da coordenação | **direto na coordenadora**, com o gate no fim se tocar risco crítico | uma sessão nova custa a base de contexto, o prompt, as skills e o gate; para pouca coisa é mais caro e mais lento |

Subagente (ferramenta Agent) morre com a resposta, divide o contexto de quem o chamou e não tem gate próprio (o
`fluxo:critical-review` é um por sessão): frente nunca vai a subagente. Agent teams (experimental) não isola worktree, não
retoma e custa mais: não substitui sessões `--bg` neste método.

## 2. Lançar, conversar, retomar, parar

**O binário.** O `claude` pode não estar no PATH do shell do Bash tool. Ache-o e rode as linhas direto, sem `bash -c` (a
checagem de segurança barra script em `-c` que ela não lê):

```bash
C=$(command -v claude || ls ~/.local/bin/claude 2>/dev/null || ls -d ~/.vscode{,-server}/extensions/anthropic.claude-code-*/resources/native-binary/claude 2>/dev/null | sort -V | tail -1)
P=${CLAUDE_SKILL_DIR}/modelos/sessao-de-fundo.settings.json
"$C" --bg -n <nome> --settings "$P" --add-dir "$D" --permission-mode auto "$(cat "$D/logs/<nome>.prompt.md")"
"$C" agents --json --cwd "$CHECKOUT"   # name, sessionId, state (busy, idle, working, blocked: à espera de permissão ou parada)
"$C" logs <id|nome>                    # saída recente (TUI crua: filtre os códigos ANSI)
"$C" attach <id|nome>                  # abre no terminal (o dono responde por aqui um pedido de permissão)
"$C" stop <id>                         # para e guarda a conversa
"$C" --bg --resume <sessionId> -n <nome> --settings "$P" --add-dir "$D" --permission-mode auto "<o que mudou e o próximo passo>"
```

- **`--add-dir` é variádico:** venha sempre seguido de outra opção, senão engole o prompt como diretório. Ele libera `$D`
  (HANDOFF e logs) para a sessão.
- **O perfil enxuto vai em todo lançamento, o `--resume` inclusive** (`--settings "$P"`): tira da sessão de fundo o que
  ela nunca usa e que seria relido em toda chamada — Artifact, Workflow, ReportFindings, ScheduleWakeup, NotebookEdit,
  AskUserQuestion, os conectores do claude.ai e as skills embutidas da listagem. Medido: a base de cada chamada caiu de
  72 mil para 40 mil tokens ([references/base-de-contexto.md](references/base-de-contexto.md)). As skills do projeto
  ficam. Decisão vai à coordenadora por `SendMessage`.
- **Modelo e effort são herdados:** nem `--model` nem `--effort`, em frente nenhuma, a de risco crítico inclusive. A
  sessão nasce no `effortLevel` do `.claude/settings.json` do repo (o top-level do projeto vence o `modelSettings` do
  usuário). O `max` é só do gate, pelo frontmatter do `fluxo:critical-review`. Profundidade num passo é `ultrathink`. Esta regra
  vale pelo arquivo: cópia antiga da skill no contexto (ou preservada por compactação) já mandou `--effort max` e abriu
  quatro frentes em `max` (16/10/2026); antes de lançar, confira o comando aqui.
- **No checkout, sem worktree para trabalhar** quando o perfil disser (`"worktree": {"bgIsolation": "none"}` no settings
  do repo). Sessão que pedir "Call EnterWorktree first": a chave sumiu; leve ao dono, não aceite a worktree.
- **`NX_WORKSPACE_ROOT_PATH` herdado:** a sessão de fundo nasce com o do daemon que a abriu, que pode ser de outro
  checkout. Todo `nx` da sessão e da prova leva `NX_WORKSPACE_ROOT_PATH=<checkout ou worktree> NX_DAEMON=false`.
- **Nome:** `<prefixo do perfil>-<frente>[-fase<n>]`, o mesmo no prompt, no `janela.md` e no relatório.
- **Conversar:** `SendMessage` para o NOME; `ListAgents` mostra os nomes, o da coordenadora inclusive (muda a cada
  sessão: confira antes de montar um prompt e avise as ativas se mudar). Mensagem para sessão ociosa a acorda e abre um
  turno que relê o contexto inteiro dela: mande só recurso, decisão e retomada.
- **Saber quando acabou, sem laço nem cron:** ao lançar, mande à sessão uma `SendMessage` com `notify_when_idle: true`
  (o aviso chega uma vez quando ela fica ociosa ou sai, sem gastar token dela, e expira em 12 h; renove ao retomar).
  Cron só como rede quando o aviso não for possível, de 60 em 60 min, apagado quando a última sessão fecha.
- **Fechou, pare:** sessão que entregou o relatório final e cujo commit foi conferido sai com `"$C" stop <id>`. Sessão
  fechada que fica `blocked` na lista confunde a próxima coordenadora e a conferência de duplicata.
- **Retomar** continua a mesma conversa; se ela ainda roda, abre uma cópia e avisa. Antes de abrir ou retomar, confira em
  `agents --json` se o dono já não abriu a mesma frente.

## 3. O estado da coordenação (`$D`)

| Caminho | O que é | Teto |
|---|---|---|
| `fila.md` | **só o que está aberto**: decisões e aprovações do dono ainda válidas (literais, data, escopo), frente ativa, fila, pendências do dono, a última linha de cada sessão fechada (shas) | ~8 KB |
| `fila-arquivo/AAAA-MM.md` | o diário fechado, movido do `fila.md` quando a entrega fecha | nunca se lê inteiro; `grep` |
| `janela.md` | **só a tabela** de quem está com cada recurso de um só, e a fila de cada um | ~2 KB |
| `prompts/` | a parte da frente de cada sessão (§4) | |
| `logs/<sessão>/` | o prompt montado e as saídas longas | |
| `handoff/<sessão>.md` | o HANDOFF que a sessão mantém, para quem retomar | |

A coordenadora seguinte lê `fila.md` e `janela.md` — por isso eles têm teto. Ao fechar uma entrega: o diário dela vai
para `fila-arquivo/`, o `fila.md` fica com o aberto, e a linha de recurso devolvido sai do `janela.md`. Aprovação
permanente do dono mora na memória do projeto, não no `fila.md`. Nada de `$D` vai ao git; o que fica de verdade vai ao
PRD ou doc da frente e à memória.

## 4. O prompt de uma sessão

```bash
cat "$D/prompts/<frente>.md" ${CLAUDE_SKILL_DIR}/modelos/rodape.md "$P_DIR/sessao.md" > "$D/logs/<nome>.prompt.md"
```

Troque no montado `<NOME-DA-COORDENADORA>`, `<NOME-DA-SESSAO>`, `<D>`, `<SKILL_DIR>` (= `${CLAUDE_SKILL_DIR}`) e os `<...>` da parte da frente. A parte da frente
segue [modelos/frente.md](modelos/frente.md):

1. O pedido do dono **nas palavras dele**, com a data, e a decisão ou aprovação dele quando houve (texto literal e
   escopo). Aprovação implícita não conta.
2. O contrato (PRD, plano, ADR) e o mapa do código já conferido pela coordenadora, para a sessão não redescobrir.
3. Escopo numerado, com "decida e registre o porquê" onde há escolha técnica, e o que NÃO entra.
4. As skills da camada (só as que a frente toca, e só as references do tópico), o doc de risco crítico do projeto e só a
   reference do domínio tocado, e as memórias do domínio.
5. O nível de prova (§7) e o portão medido; o fecho: gate único, consertos, commit (ou "NÃO COMMITE") e o relatório.

Decisão que surgir no meio volta à coordenadora com o caso real, as opções e a recomendação; ela pergunta ao dono pela
ferramenta de perguntas, com uma opção marcada como recomendada, e devolve a resposta literal. Exigem o sim do dono
ANTES, sempre pela coordenadora: o que o perfil e o `CLAUDE.md` do projeto listam (mudança de banco, backfill, script em
massa, secret/env, regra de negócio, guard que bloqueia resposta ou venda, produção). A sessão pede e segue com o resto.

## 5. O que a máquina e a branch têm de um só

A árvore é uma, com WIP de outras sessões e do dono. A tabela de recursos do projeto está no perfil (`$P_DIR/perfil.md`); os princípios valem
sempre:

- **Índice e branch do git:** commit por índice temporário (§6). Nunca stash, reset, checkout ou restore de arquivo
  alheio, clean, `add -A`/`add .`.
- **Gerador compartilhado** (client do ORM, cache de build, daemon do Nx, projeto do motor): um por vez, com aviso.
- **Dependências** (`install`, lockfile): só com a janela, sem suíte rodando em outra sessão.
- **Servidores do dono:** não parar nem reiniciar; subir outro só com a janela e o sim do dono.
- **Índices compartilhados** (i18n, `MEMORY.md`, `CLAUDE.md`, doc de risco, skills, PRDs, barris, rotas): inserção
  pontual relida na hora, nunca regravar de uma leitura antiga; commit por hunk ou por chave.

A coordenadora concede e anota no `janela.md`.

## 6. Commit, prova e push

- **A sessão commita** só o que é dela, depois do gate, pelo modo que o perfil declara
  ([references/commit-por-indice.md](references/commit-por-indice.md), com os buracos já pagos):
  - **direto** — a sessão de frente é a única viva e a árvore não tem WIP alheio nos caminhos dela: prova na própria
    árvore e `git commit -m "<msg>" -- <lista explícita>` (o `--` com caminhos leva só esses, mesmo com outro staged).
    É o mais rápido: uma rodada de prova, sem worktree.
  - **dividido** — há outra sessão viva ou WIP alheio: índice temporário + `commit-tree`, prova numa worktree limpa no
    sha e `update-ref` com CAS sobre o pai conferido.
  Mensagem: a regra de commit do projeto, uma linha, sem corpo, sem trailer, sem coautoria, sem amend.
- **Uma rodada de prova por nível** (§7): no modo dividido, o que já rodou na árvore antes do gate não se repete na
  worktree, salvo no nível C.
- **O push é da coordenadora, com o sim do dono**, depois de `git show --stat <sha>` contra o relatório, pelo caminho que
  o perfil descreve (de onde empurrar, hook, remoto). Nunca `--no-verify` sem a palavra do dono. PR, CI, merge e deploy:
  o que o perfil disser; merge e deploy são do dono.
- **Sem risco crítico tocado** (manutenção, `.claude/`, docs, memória, testes, ou comportamento comum): não passa pelo gate.

## 7. A prova pelo risco

A coordenadora põe o nível no prompt. A sessão sobe o nível quando vê que toca mais, e nunca o desce. Os comandos de cada
nível estão no perfil.

| Nível | Quando | Antes do gate (na árvore) | Na worktree do commit |
|---|---|---|---|
| **P** | texto, um número, ajuste de tela, conserto de uma função; nada crítico | os testes do que mudou e o lint dos arquivos | o hook de pre-push (ou equivalente do perfil) e só as suítes tocadas |
| **M** | frente ou fase comum | idem | o pre-push e as suítes dos projetos afetados |
| **C** | domínio de risco crítico, núcleo com paridade | as suítes dos afetados | as suítes dos afetados de novo (o gate pode ter mudado o código) e as sondas que o perfil pede |

Nada de rodada dobrada nem suíte inteira que o nível não peça.

## 8. O que a coordenadora confere sozinha

O estado do git (branch, `git log`, nada staged no índice compartilhado de quem commitou), o relatório contra o código
(todo "pronto" se confere pela contagem no log, não se roda de novo), as aprovações do dono contra o que a sessão fez, e
a lista do deploy do perfil. Produção: só o que o perfil permite, só leitura, só contagem ou id, nunca PII nem secret.

**Gate que morreu no meio:** o hook pede confirmação do dono para a 2ª chamada do `fluxo:critical-review` na sessão. Se a 1ª
caiu sem relatório, o dono confirma pelo `attach`, ou autoriza fechar a sessão e abrir outra que segue do HANDOFF e roda
o gate uma vez. Nunca contornar sem a palavra dele.

## 9. Economia da coordenação

Cada chamada relê o contexto inteiro, o da coordenadora inclusive. O que o enche: skills invocadas inteiras, saída crua
do Bash, mensagens entre sessões e arquivos de estado sem teto.

- **Uma sessão de frente por vez**, salvo pedido do dono; a próxima abre quando a anterior commitou.
- **Uma coordenadora por entrega:** fechada a entrega (commit e push), o `fila.md` fica com o aberto (§3) e a entrega
  seguinte abre numa coordenadora nova, que lê o `fila.md`, o `janela.md` e o perfil, não a conversa anterior.
- **Mensagem só para recurso, decisão e relatório.** O andamento vai para o HANDOFF; a coordenadora o lê quando precisa.
- **Saída longa em arquivo** (`$D/logs/<sessão>/`), no contexto só o resumo (`tail -n 5`, o grep da contagem e das
  falhas).
- **Skill entra pelo núcleo** e só pelas references do tópico; depois de compactar, voltam só os primeiros 20 mil
  caracteres de cada skill invocada, até uns 100 mil no total, e reinvoca-se a que o próximo passo pede.
- **Ler vai ao `fluxo:explore`, escrever o isolável e não crítico ao `fluxo:implement`;** o risco crítico e a execução das suítes
  ficam na sessão.

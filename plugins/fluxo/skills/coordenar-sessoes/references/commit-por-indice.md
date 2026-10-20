# Commit por índice temporário, prova na worktree e publicação

Receita para commitar só o que é da sessão numa árvore dividida, sem tocar o `.git/index` compartilhado (conferida em
05/10/2026 num repositório descartável: o commit leva só as linhas da sessão, o staged de outra sessão fica intacto). O
que é do projeto (hook de pre-push, suítes, remoto, sincronizar com o remoto antes) está no
perfil do projeto (`$P_DIR/perfil.md`, skill §0) e nas regras da sessão.

O estado do shell não passa de uma chamada do Bash tool para a outra: anote `OLD` e `NEW` e use os shas literais nos
passos seguintes. A checagem de segurança barra `rm` sobre variável: caminhos literais.

## Modo direto (sessão única, sem WIP alheio nos seus caminhos)

```bash
cd <checkout> && git branch --show-current && git status --short      # confira: nada alheio nos seus caminhos
<os comandos do nível de prova, do perfil, na própria árvore, saída em arquivo>
git commit -m "<tipo>(<escopo>): <mensagem>" -- <lista explícita>     # com caminhos, leva só eles, mesmo com outro staged
git show --stat HEAD && git branch --show-current
```

Arquivo que aparecer na árvore e não for seu: não toque, não commite, avise a coordenadora; se ele está nos seus
caminhos, passe ao modo dividido. Nunca `git add -A`/`.` nem `git commit -a`.

## Modo dividido

### Passo 1 — montar o commit sem mexer na branch

```bash
set -e
cd <checkout> && git branch --show-current && OLD=$(git rev-parse HEAD) && echo "OLD=$OLD"
export GIT_INDEX_FILE=$PWD/.git/index-<nome-da-sessao>
git read-tree "$OLD"
git add -- <arquivos inteiramente da sessão>
# arquivo misto: HEAD + só as linhas da sessão
BLOB=$(<gera a versão HEAD + linhas da sessão> | git hash-object -w --stdin)
git update-index --cacheinfo 100644,"$BLOB",<caminho>
NEW=$(git commit-tree "$(git write-tree)" -p "$OLD" -m "<tipo>(<escopo>): <mensagem>") && echo "NEW=$NEW"
unset GIT_INDEX_FILE; rm -f .git/index-<nome-da-sessao>
```

Commits atômicos em série: cada `commit-tree` com `-p` no anterior, um `update-ref` só no fim.

### Passo 2 — a prova numa worktree limpa no `NEW`, antes do `update-ref`

Na árvore dividida, um arquivo de outra sessão faz passar o que no clone falha; e outra sessão que empurre o HEAD levaria
junto um commit ainda não provado.

```bash
git worktree add --detach <scratchpad>/prova <NEW> && ln -s <checkout>/node_modules <scratchpad>/prova/node_modules
cd <scratchpad>/prova && export NX_DAEMON=false NX_WORKSPACE_ROOT_PATH=$PWD   # sem isto o nx roda contra a árvore principal
<os comandos do nível de prova, do perfil>
cd <checkout> && rm <scratchpad>/prova/node_modules && git worktree remove <scratchpad>/prova   # o symlink sai antes, nunca rm -r
```

### Passo 3 — publicar na branch local, só com a prova verde

```bash
git branch --show-current                         # a mesma de antes
test "$(git rev-parse <NEW>^)" = "$(git rev-parse HEAD)"   # o pai do commit é o HEAD de agora
git update-ref refs/heads/<branch> <NEW> <OLD>    # CAS: falha se o HEAD andou; refaça o passo 1 sobre o novo
git restore --staged -- <os mesmos caminhos>      # alinha o índice compartilhado ao HEAD novo, só nesses caminhos
```

## Os buracos já pagos

- **O `<OLD>` do `update-ref` é o pai do commit novo, conferido.** Um commit montado antes do gate, sobre uma branch que
  andou durante ele, passado com o HEAD de agora, entra e apaga da branch os commits do meio (08/10/2026).
- **A lista de caminhos se confere pelo tamanho antes do `git add`:** uma lista lida de caminho errado dá zero voltas e
  um commit incompleto, calado.
- **O commit se confere blob a blob contra a árvore**, não pelo `git diff <sha>`.
- **Depois do `update-ref`, o índice compartilhado ainda tem as versões antigas** dos arquivos da sessão: o passo 3
  alinha só esses caminhos.
- **Arquivo gerado que só a ferramenta escreve** (o `.uid` de script do motor, o client do ORM) se gera na worktree de
  prova e se commita junto, quando o projeto versiona.
- **Worktree nova pode rodar o install sozinha** no primeiro comando do package manager (do store, sem download): conte
  com ele antes de medir tempo.
- **O client do ORM vem do `node_modules` do checkout:** com o schema mudado por outra sessão e não commitado, a prova
  pode divergir; diga isso no relatório.

## Push (da coordenadora, com o sim do dono)

O hook de pre-push roda na árvore de onde se empurra: do checkout, o WIP de outra sessão derruba (ou aprova) o hook.
Empurre de uma worktree de prova no sha. Se o diretório de hooks é gerado e não versionado (ex.: `.husky/_`), o hook não
existe na worktree e o push sem `-c core.hooksPath=<checkout>/<dir de hooks>` pula o gate calado (05/10/2026). Nunca
`--no-verify` sem a palavra do dono. O comando exato do projeto está no perfil.

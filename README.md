# fluxo

Plugin do Claude Code com o fluxo de trabalho: agentes de leitura, escrita e pesquisa, gate único de pré-commit e coordenação de frentes em sessões de fundo.

## O que vem

| Peça | Como chega | Onde fica |
| --- | --- | --- |
| Skill `coordenar-sessoes` | plugin | `/fluxo:coordenar-sessoes` |
| Hook do gate (`critical-review` exige Pedido/Escopo/Verificado; 2ª chamada pede confirmação) | plugin | registrado sozinho |
| Agentes `Explore`, `implement`, `research`, `critical-review` | `/fluxo:setup` | `~/.claude/agents/` |
| Guard de Bash do `critical-review` | `/fluxo:setup` | `~/.claude/hooks/review-bash-guard.py` |
| Regras globais (roteamento, gate, commits, risco crítico) | `/fluxo:setup` | bloco entre marcadores no `~/.claude/CLAUDE.md` |

Os agentes não vão como agentes de plugin porque esses ganham prefixo (`fluxo:explore`), ignoram `hooks:` no frontmatter (o guard de Bash do gate) e não substituem o `Explore` embutido. O `CLAUDE.md` não vai pelo plugin porque plugin não carrega `CLAUDE.md`.

## Instalar

O repo é privado: quem instala precisa de acesso de leitura a ele e do git autenticado no GitHub (`gh auth login` ou chave SSH).

```sh
claude plugin marketplace add felipe-diniz/fluxo
claude plugin install fluxo@fluxo
```

Depois, numa sessão do Claude Code:

```
/fluxo:setup
```

O setup mostra o plano (o que cria, o que substitui e quantas linhas mudam), pede o OK e só então escreve. Tudo o que for substituído vai antes para `~/.claude/backups/fluxo-<data>/`. Abra uma sessão nova depois para os agentes e as regras valerem.

Se o `~/.claude/CLAUDE.md` já tem regras próprias, o bloco do fluxo entra no fim, entre `<!-- fluxo:inicio … -->` e `<!-- fluxo:fim -->`. O resto do arquivo não é tocado. Revise se ficou regra duplicada.

## Atualizar

Quem mantém: edite em `plugins/fluxo/`, suba o `version` em `plugins/fluxo/.claude-plugin/plugin.json`, faça o commit e o push.

Quem usa:

```sh
claude plugin marketplace update fluxo
claude plugin update fluxo@fluxo
```

e rode `/fluxo:setup` de novo. Quando a versão do plugin e a do último setup diferem, a sessão avisa numa linha. Quando estão iguais, o aviso não aparece.

## Projeto

O método é global. O que é de cada projeto (portas, comandos, modo de commit, como provar) é o perfil, procurado nesta ordem:

1. `.claude/coordenacao/` no repo: versionado, para projeto em equipe;
2. `~/.claude/coordination/<projeto>/perfil/`: pessoal;
3. se não houver nenhum, a skill deriva o perfil do `CLAUDE.md`, do doc de risco crítico, dos settings e dos hooks do projeto, grava no item 2 e pergunta só o que faltar.

O risco crítico de cada projeto vem da seção `## Risco crítico` do `CLAUDE.md` do repo. Sem ela, vale o fallback das regras globais.

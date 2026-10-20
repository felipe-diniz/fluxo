# Perfil de coordenação — <projeto>

O que este projeto põe no método da skill global `coordenar-sessoes`. A skill é o método; este arquivo vence onde
divergir. As regras que entram em todo prompt estão em `sessao.md`, ao lado. Derivado de: <CLAUDE.md, settings, hooks…>,
em <data>; o que veio do dono está marcado com a data e o texto literal.

## Identidade

- Checkout: `<caminho>`, branch `<branch de trabalho>`, <sem branch nova | branch por frente>, <sem worktree para trabalhar (`worktree.bgIsolation: none`) | worktree por sessão>.
- Estado da coordenação: `~/.claude/coordination/<slug>/`. Nome das sessões: `<prefixo>-<frente>[-fase<n>]`.
- Quantas sessões de frente ao mesmo tempo: <1, regra do dono | N>.
- Contrato das frentes: <PRDs, planos, ADRs — onde ficam>. Tarefas: <ClickUp/Jira/nenhum, e quem escreve>.
- Memória: <pasta; se a auto memory é symlink para ela; se o CLAUDE.md importa o índice com `@`>.
- Risco crítico: <doc ou skill, e se tem references por domínio>.

## Commit

Modo <direto | dividido> (skill §6 e `references/commit-por-indice.md`), com estes passos do projeto: <sincronizar com o
remoto antes? gerar arquivo que só a ferramenta escreve?>. Mensagem: <regra do commitlint, idioma>.

## Prova (comandos de cada nível, skill §7)

- Teste focado: `<comando>`. Suíte de um projeto: `<comando>`. Lint/typecheck: `<comando>`. Hook de pre-push: `<comando>`.
- P: <…>. M: <…>. C: <…>, mais as sondas do ambiente de verificação do doc de risco.

## O que a máquina e a branch têm de um só

| Recurso | Por que é de um só | Regra |
|---|---|---|
| Índice e branch do git | `.git/index` é um para todos | o modo do §Commit |
| <gerador: client do ORM, cache de build, projeto do motor> | <…> | <…> |
| <dependências: install, lockfile> | reescrevem o ambiente de todos | só com a janela |
| <servidores e portas do dono> | <…> | <…> |
| <índices compartilhados: i18n, MEMORY.md, CLAUDE.md, doc de risco, barris> | várias sessões no mesmo arquivo | inserção pontual relida na hora; commit por hunk |

## Aprovação do dono antes, sempre pela coordenadora

<mudança de banco, backfill, script em massa, secret/env, regra de negócio, guard, produção — o que o CLAUDE.md lista>.

## Push, PR e deploy

- Push: <quem, de onde (worktree no sha ou checkout limpo), hook, remoto>. PR: <para onde; CI>. Merge e deploy: <do dono>.
- Lista do deploy: <migrations, envs, templates, infra, ordem>.

## Produção

<o que é permitido: só leitura, só contagem/id, nunca PII nem secret>.

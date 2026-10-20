# fluxo

Plugin do [Claude Code](https://code.claude.com) com um método de trabalho pronto. Ele traz quatro agentes, um gate único de revisão antes do commit e uma skill para tocar várias frentes em paralelo em sessões de fundo. A ideia é que a sessão principal pense e decida, e que o trabalho braçal rode fora dela, em contexto isolado.

Instale e use: não há passo de configuração.

## Por que usar

Sem método, uma sessão longa do Claude Code costuma cair em problemas como estes:

| Problema | O que o fluxo faz |
| --- | --- |
| A sessão principal lê dezenas de arquivos e o contexto incha: cada turno fica mais caro e a compactação chega mais cedo. | A leitura ampla vai ao `fluxo:explore` (haiku, só leitura), que devolve só a síntese com `arquivo:linha`. |
| Código isolável e de especificação fechada é escrito no contexto principal. | Vai ao `fluxo:implement` (sonnet), com briefing fechado e teste focado. A principal confere o diff. |
| A pesquisa na web despeja páginas inteiras no contexto. | Vai ao `fluxo:research` (sonnet), que devolve a síntese com as fontes. |
| A revisão roda várias vezes por sessão, em tudo, e refaz o que já foi verificado. | Um gate só, o `fluxo:critical-review`, e só quando a sessão mudou uma invariante de risco crítico: uma vez, no fim, com testes verdes, só sobre os hunks críticos e os irmãos deles. Doc, i18n e o resto sem risco ficam fora. Um hook recusa a chamada sem briefing e pede confirmação a partir da segunda. |
| O revisor "conserta" coisas, roda a suíte inteira ou faz commit no meio da revisão. | Dentro do gate, um guard de Bash recusa git que muda a árvore, escrita fora do temporário, suíte inteira, build, servidor, migration, instalação de pacote e rede externa. |
| O agente mexe em dinheiro, auth ou dado de outro cliente com a mesma leveza de um CSS. | Risco crítico é contrato do projeto: o `implement` não toca nesses domínios e o gate revisa a fundo o que muda uma invariante deles. |
| Várias frentes grandes na mesma sessão se atropelam, e o contexto vira uma mistura. | A skill `fluxo:coordenar-sessoes` abre uma sessão de fundo por frente, com prompt montado, fila, janela de recursos e modo de commit. |
| A compactação esquece aprovações e o estado do gate. | As regras dizem o que a compactação tem de preservar: o pedido nas palavras do usuário, as aprovações literais, os arquivos, os comandos com resultado e o estado do gate. |

O estilo `fluxo:direto` corta o texto de resposta, que é o token mais caro (saída), e evita a ida e volta de "posso seguir?" no rotineiro, sem tirar a pergunta onde ela importa.

O resultado é menos token gasto no contexto caro, revisão que não se repete e um padrão de entrega igual em todo projeto.

## O que vem

| Peça | Nome | Papel |
| --- | --- | --- |
| Agente | `fluxo:explore` | Leitura ampla de código e docs locais. Só leitura, haiku, nasce sem o CLAUDE.md. |
| Agente | `fluxo:implement` | Escrita isolável e não crítica: arquivo novo, teste no padrão, doc, refactor mecânico. |
| Agente | `fluxo:research` | Pesquisa web: providers, docs externas, preços, limites, regras. |
| Agente | `fluxo:critical-review` | Gate de pré-commit: QA de entrega, revisão de risco crítico, medição, testes, docs e memória. Devolve LIBERADO ou BARRADO. |
| Hook | gate | Recusa a chamada ao gate sem `Pedido:`, `Escopo:`, `Verificado:` e `Risco:`, ou com `model`/`effort` de override; pede confirmação a partir da 2ª passada na sessão. |
| Hook | guard de Bash | Só age dentro do `fluxo:critical-review`: o gate lê e mede, não muda estado. |
| Hook | regras | No início da sessão e depois de cada compactação, põe no contexto as regras de roteamento, de risco crítico, do gate e da compactação ([regras.md](plugins/fluxo/regras.md)). |
| Estilo de resposta | `fluxo:direto` | Proativo fora do risco crítico e da regra de negócio; começa pelo resultado, sem preâmbulo nem drama; decisão do usuário vira pergunta com a opção recomendada. Entra sozinho com o plugin ([direto.md](plugins/fluxo/output-styles/direto.md)). |
| Skill | `/fluxo:coordenar-sessoes` | Coordenação de frentes em sessões `claude --bg`. |
| Comando | `/fluxo:migrar` | Remove uma instalação manual antiga do fluxo (veja abaixo). |

## Instalar

Requisitos: Claude Code e `python3` no PATH (os hooks são scripts Python sem dependência).

```sh
claude plugin marketplace add felipe-diniz/fluxo
claude plugin install fluxo@fluxo
```

Abra uma sessão nova. Para conferir, pergunte "quais agentes fluxo: você tem?": devem aparecer os quatro.

### Já usava a versão manual (cópias em `~/.claude`)?

Quem copiou os agentes, os hooks, a skill ou as regras à mão vai ficar com tudo em dobro. Rode uma vez:

```
/fluxo:migrar
```

Ele mostra o plano e só aplica com o seu sim. Tudo o que sai vai antes para `~/.claude/backups/fluxo-<data>/`:

- os agentes de usuário `Explore`, `implement`, `research` e `critical-review` de `~/.claude/agents/`;
- `critical-review-gate.py` e `review-bash-guard.py` de `~/.claude/hooks/`, e as entradas deles no `~/.claude/settings.json`;
- a skill pessoal `~/.claude/skills/coordenar-sessoes`;
- do `~/.claude/CLAUDE.md`, só as seções com o mesmo título das do plugin. Regras suas, como commits e idioma, ficam.

Enquanto houver instalação antiga, a sessão avisa no começo e sugere o `/fluxo:migrar`.

## Como usar no dia a dia

### Numa tarefa comum

Você pede o trabalho como sempre. As regras do plugin já dizem à sessão como dividir:

1. **Entender:** se precisar abrir o terceiro arquivo, a sessão manda um ou mais `fluxo:explore` em paralelo, cada um com uma pergunta.
2. **Fazer:** desenho, decisão e tudo o que toca risco crítico ficam na sessão principal. O isolável vai ao `fluxo:implement`, com os arquivos que ele pode tocar e o teste que tem de passar.
3. **Provar:** a sessão roda os testes do que mudou, o lint e o typecheck.
4. **Revisar uma vez, só se tocou risco crítico:** com tudo verde, a sessão chama o `fluxo:critical-review` sobre os hunks que mudam a invariante e os irmãos deles (quem chama, quem consome, os testes desse caminho), com o briefing:

   ```
   Pedido: <o que você pediu, nas suas palavras, e o doc de origem>
   Escopo: <o recorte crítico; o que da sessão fica fora por não ter risco; o que na árvore não é da sessão>
   Verificado: <o que já rodou e o resultado; ambiente de pé ou não>
   Risco: <domínios críticos tocados e invariantes em jogo>
   ```

5. **Fechar:** a sessão corrige o que o gate apontou, cobrindo com teste, e faz o commit. Uma nova passada só acontece quando o próprio relatório marca `re-revisão: sim`.

Sem domínio crítico tocado não há gate: a sessão fecha no passo 3, com a própria conferência pedido × feito. O gate também não entra em desenho, plano nem investigação de bug.

### Ensine o risco crítico do seu projeto

Os agentes leem o risco crítico do `CLAUDE.md` do repo. Declare os domínios e aponte o doc de detalhe:

```markdown
## Risco crítico

Detalhe em [docs/risco-critico.md](docs/risco-critico.md).

1. **Dinheiro**: cobrança, confirmação de pagamento, estorno.
2. **Auth**: guards, papéis, sessão.
3. **Isolamento entre clientes**: toda query filtra por `tenantId`.
```

Sem essa seção, vale o padrão: dinheiro, autenticação e autorização, isolamento entre tenants, concorrência e perda irreversível de dados.

Projeto grande: deixe o doc de risco num núcleo curto (domínios, invariantes, o que exige aprovação) mais uma reference por domínio. O agente lê o núcleo e só a reference do domínio que vai tocar.

### Várias frentes em paralelo

```
/fluxo:coordenar-sessoes
```

A sessão em que você roda vira a coordenadora. Para cada frente grande, com commit próprio e horas de trabalho, ela:

- escreve o prompt da frente;
- abre uma sessão `claude --bg` com um perfil enxuto;
- distribui recursos que não podem ser usados ao mesmo tempo, como porta, banco ou build pesado;
- recebe o relatório quando a sessão termina.

Conserto curto não vira frente: fica na sessão atual.

Cada frente nova abre uma sessão nova. A coordenadora não reaproveita sessão de outra frente. No fim de cada rodada, ela salva o estado em disco e avisa que você pode dar `/clear`. Ao rodar `/fluxo:coordenar-sessoes` de novo, ela relê o estado do disco e volta a acompanhar as sessões vivas.

O que é de cada projeto (portas, comandos, modo de commit, como provar) fica num perfil, procurado nesta ordem:

1. `.claude/coordenacao/` no repo: versionado, para o time inteiro;
2. `~/.claude/coordination/<projeto>/perfil/`: pessoal;
3. se não houver nenhum, a skill monta o perfil a partir do `CLAUDE.md`, do doc de risco e dos settings do projeto, grava no item 2 e pergunta só o que faltar.

Fila, janela de recursos, prompts e logs ficam em `~/.claude/coordination/<projeto>/`, fora do repo.

## Configuração recomendada (opcional)

No `~/.claude/settings.json`, o que vale para todo projeto:

```json
{
  "effortLevel": "high",
  "env": { "CLAUDE_CODE_AUTO_COMPACT_WINDOW": "400000" },
  "worktree": { "bgIsolation": "none" }
}
```

- `effortLevel: high` no topo. Não use `modelSettings` com id de versão; o `/effort` grava assim, apague depois.
- Compactação em 400 mil, para modelos de 1M de contexto. Medido: o mesmo custo que 300 mil, com menos compactações, e cada compactação perde detalhe.
- `bgIsolation: none` faz as sessões de fundo trabalharem no checkout. A skill de coordenação conta com isso. Tire se você prefere uma worktree por sessão.

O `.claude/settings.json` do projeto deve levar só o que é do projeto.

## Atualizar

```sh
claude plugin marketplace update fluxo
claude plugin update fluxo@fluxo
```

Vale na próxima sessão.

## Desinstalar

```sh
claude plugin uninstall fluxo@fluxo
```

O plugin não escreve nos seus arquivos. Só o `/fluxo:migrar` escreve, e ele deixa backup.

## Limitações conhecidas

- O `Explore` embutido do Claude Code continua existindo: agente de plugin ganha prefixo e não substitui o embutido. As regras mandam usar o `fluxo:explore`.
- As regras entram por hook no contexto da sessão principal. Os subagentes têm o próprio prompt e não recebem essas regras; eles leem o `CLAUDE.md` do projeto, menos o `explore` e o `research`.
- O estilo `fluxo:direto` vence o `outputStyle` do usuário enquanto o plugin estiver habilitado (`force-for-plugin`). Ele vale na sessão principal; os subagentes têm o próprio prompt.
- O `regras.md` tem de caber em 10.000 caracteres, o limite de saída de hook.
- Agente de plugin ignora `hooks:` no frontmatter. Por isso o guard de Bash do gate é um hook do plugin que filtra pelo `agent_type` do payload.

## Estrutura

```
.claude-plugin/marketplace.json     marketplace (este repo)
plugins/fluxo/
  .claude-plugin/plugin.json        nome e versão
  agents/                           os quatro agentes
  hooks/hooks.json                  regras (SessionStart), gate e guard (PreToolUse)
  scripts/                          os hooks e o migrar, em Python sem dependência
  regras.md                         o que vai ao contexto no início da sessão
  skills/coordenar-sessoes/         skill, modelos e references
  output-styles/direto.md           estilo de resposta
  commands/migrar.md                /fluxo:migrar
```

Para mudar algo: edite em `plugins/fluxo/`, suba o `version` no `plugin.json` e faça o push. O self-test do guard roda com `python3 plugins/fluxo/scripts/review-bash-guard.py --self-test`.

## Licença

[MIT](LICENSE).

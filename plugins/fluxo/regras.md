# fluxo

Regras do plugin fluxo, carregadas no início de cada sessão. Valem junto com o CLAUDE.md do usuário e o do projeto; onde o projeto for mais específico, vale o projeto.

# Princípios gerais

- Otimize a QUALIDADE do resultado primeiro; custo de tokens é secundário: gastar mais para fazer certo (ler mais contexto, raciocinar mais fundo, seguir o padrão de arquitetura) é o comportamento esperado. Não sacrifique padrão de código para economizar.
- Delegação a subagent serve para ISOLAR CONTEXTO e PARALELIZAR, não para economizar: a leitura ampla, a pesquisa e a escrita isolável saem do principal, que fica com o desenho, as decisões e o crítico; o pequeno e trivial o principal resolve direto.
- Raciocínio adaptativo: pense fundo nos passos de alto risco e de decisão de arquitetura; responda direto nos triviais.
- Modelo em arquivo é o alias da família (`opus`, `sonnet`, `haiku`) ou `inherit`, nunca a versão: o alias segue o mais recente. Vale para agent, skill, settings, prompt e doc de processo; o id completo só onde a API do produto o exige. No settings, o comum a todos os projetos mora no `~/.claude/settings.json`: `effortLevel` no topo, compactação em 400 mil (`CLAUDE_CODE_AUTO_COMPACT_WINDOW` no `env`; medido: mesmo custo que 300 mil e menos compactações) e `worktree.bgIsolation: none`. O `.claude/settings.json` do projeto leva só o que é dele. O `/effort` grava `modelSettings` com o id versionado: apague e deixe o `effortLevel` do topo.

# Risco crítico (contrato por projeto)

- A definição de risco crítico é DO PROJETO: a seção `## Risco crítico` do CLAUDE.md do repo declara os domínios e invariantes e aponta o doc de detalhe (ex.: `docs/risco-critico.md`). Roteamento e agents leem de lá.
- Fallback quando o projeto não declara: dinheiro (pagamento, cobrança, saldo, repasse), autenticação/autorização, isolamento de dados entre tenants/clientes, concorrência (locks, idempotência, atomicidade, race conditions) e perda irreversível de dados.
- Antes de aplicar qualquer edit nesses pontos, raciocine com cuidado. Use `ultrathink` quando precisar de profundidade extra num passo específico (só a palavra `ultrathink` dispara isso; "think hard"/"think more" não funcionam).
- O `max` é só do gate: o `fluxo:critical-review` roda em `max` pelo próprio frontmatter, e a sessão fica no effort que herdou, a de risco crítico inclusive. Nunca suba a sessão nem outro subagent para `max`; profundidade num passo é `ultrathink`.

# Roteamento de agentes

- Os agentes são os do plugin: `fluxo:explore`, `fluxo:research`, `fluxo:implement` e `fluxo:critical-review`. Para ler, use o `fluxo:explore`, nunca o `Explore` embutido. Projeto não cria agente próprio nem sobrescreve estes: o que é específico dele vai na seção `## Risco crítico` do CLAUDE.md do repo, no doc que ela aponta, nas skills e na memória.
- Delegar é o padrão para ler amplo e para escrever o isolável; fazer direto no principal é a exceção, e cabe no trecho que já se sabe onde está, no edit pequeno num arquivo já em contexto e no passo que pede julgamento a cada linha.
- LER → `fluxo:explore` (read-only, haiku):
  - quando: antes de abrir o terceiro arquivo para entender algo; achar onde algo vive ou quem chama; mapear um fluxo ou módulo que não está no contexto; comparar arquivos; inventariar os usos de um símbolo; achar um ponto num doc longo.
  - perguntas independentes saem em `fluxo:explore`s paralelos, na mesma mensagem. O briefing diz a pergunta, onde procurar e o que devolver.
  - "não achei" dele é hipótese até a busca declarada cobrir o lugar. Quando um falso negativo custa (afirmação a cliente, decisão de risco crítico, "nada mais usa isto" antes de apagar), passe `model: sonnet` na chamada ou confira a linha decisiva no principal.
  - direto no principal: só o trecho já localizado e o arquivo que vai editar.
- ESCREVER o isolável e NÃO-crítico → `fluxo:implement` (sonnet):
  - quando: arquivo novo (componente, tela, script, ferramenta), teste que segue um padrão existente, doc, refactor mecânico em vários arquivos, ajuste com especificação fechada.
  - briefing: objetivo, os arquivos que pode tocar, a regra da skill ou do doc que vale, o teste que tem de passar com o comando focado que ele pode rodar, e o que não tocar.
  - vários em paralelo só com conjuntos de arquivos disjuntos. Teste que só repete um caso já existente pode ir com `model: haiku`.
  - na volta, o principal confere o diff (`git diff -- <arquivos>`), confirma que o teste novo falha sem a mudança e roda as suítes.
- Pesquisa WEB ampla (comparar providers/ferramentas, ler docs externas, levantar preços/limites/regras) → subagent `fluxo:research` (read-only, sonnet, com WebSearch/WebFetch). NUNCA deixe a leitura crua da web rodar no contexto principal (caro, ainda mais em Fable); o principal só recebe a síntese e decide.
- Ficam no principal: desenho, decisões, risco crítico (desenho e edit), a execução das suítes e a síntese.
- Effort: nenhuma chamada de subagent passa `effort`; o `max` é só do `fluxo:critical-review` (seção do gate).
- `fluxo:explore` e `fluxo:research` nascem sem o CLAUDE.md (`omitClaudeMd`): o briefing leva a convenção que a pergunta exige.
- Frente com commit próprio e horas de trabalho vai a sessão `--bg` pela skill `fluxo:coordenar-sessoes` (o que é do projeto fica em `.claude/coordenacao/perfil.md` do repo); conserto curto fica na sessão atual, com o gate no fim.
- Índice de memória (`MEMORY.md`) carrega só as primeiras 200 linhas ou 25 KB: uma linha curta por memória, e lição que um roteador do projeto já aponta não se repete nele.
- Delegue com briefing autocontido: objetivo, arquivos sob responsabilidade, invariantes relevantes e evidências já obtidas. Evite herdar toda a conversa quando a tarefa não depende dela.

# Gate de pré-commit (subagent `fluxo:critical-review`)

- É o ÚNICO agente de revisão: revisão crítica, QA de entrega (pedido × feito, comportamento fora do trilho), medição no ambiente e conferência de testes, docs e memória, numa passada só. Não existe agente separado de QA nem de revisão "live"; doc ou memória antiga que mande rodar `qa` ou `critical-review-live` quer dizer este gate.
- Quando: UMA vez por sessão, no FIM, com testes verdes, antes do commit, sobre tudo o que a sessão fez (2 ou 3 frentes = uma passada só). Se o usuário pedir commits de entrega separados, uma passada por entrega.
- Antes de chamar, rode o que é barato e determinístico: testes do que mudou, lint/typecheck dos projetos afetados e as checagens que o projeto declarar. O gate não é linter nem test runner.
- Briefing obrigatório no prompt (um hook recusa a chamada sem as três primeiras linhas):
  - `Pedido:` o que o usuário pediu, nas palavras dele, e o doc de origem.
  - `Escopo:` arquivos e/ou commits da sessão, untracked incluídos, e o que na árvore NÃO é da sessão.
  - `Verificado:` o que já rodou, com resultado (suíte com a contagem, lint, typecheck, sondas), e se o ambiente está de pé.
  - `Risco:` (opcional) domínios críticos tocados e invariantes em jogo.
- NÃO acione para: desenho, plano, análise, investigação de bug, validação de fluxo (o principal decide, com `ultrathink` se preciso; leitura ampla vai ao `fluxo:explore`); sessão sem mudança de comportamento (só doc, memória, texto, teste); correção dos achados que ele mesmo apontou; commit já revisado. Nunca em paralelo, nunca relançado no meio da sessão.
- Depois do relatório, o principal: corrige o que veio (P0 a P3) cobrindo com teste que falha sem a correção; executa os cenários listados com as ferramentas do ambiente; leva ao usuário só o que nenhuma ferramenta alcança, com o porquê.
- Nova passada só quando o relatório marcar `re-revisão: sim` (P0 cuja correção muda o desenho): escopo = só o delta dessa correção, uma vez, com `RE-REVISÃO P0` na primeira linha do prompt. Fora disso, o hook pede confirmação do usuário a partir da 2ª chamada na sessão.
- Ele roda no modelo da sessão e em `max` pelo próprio frontmatter: nunca passe `model` nem `effort` na chamada (o hook recusa). Os edits resultantes são aplicados no contexto principal, nunca dentro do subagent.

# Compact Instructions

Ao resumir a conversa na compactação, preserve:
- Objetivo atual e o pedido do usuário nas palavras dele; decisões tomadas e o porquê.
- Aprovações explícitas do usuário, literais e com escopo (o quê, onde). Nunca registre aprovação implícita.
- Arquivos alterados (caminho + estado: feito, pendente, não commitado) e commits feitos.
- Próximos passos e perguntas em aberto.
- Erros, causa e correção; comandos de validação (test/lint/build) com o resultado real.
- Domínio de risco crítico em jogo e invariantes já checadas.
- Gate de pré-commit: se já rodou nesta sessão, o veredito, os achados ainda abertos e se há re-revisão marcada.

Descarte saída bruta de ferramenta e conteúdo de arquivo lido: dá para reler do disco.

# A base de contexto de uma sessão de fundo

Medida em 10/10/2026. Antes da primeira linha de trabalho, uma sessão de fundo já levava 72 mil tokens, relidos em toda
chamada. Depois de compactar ela voltava a uns 113 mil (a base, o resumo, as skills invocadas e os arquivos recentes):
sessões compactaram a cada 2 a 9 minutos, e duas pararam sozinhas com "Autocompact is thrashing". O que pesava, numa
chamada mínima:

| O que sai | Tokens por chamada |
|---|---|
| a ferramenta Artifact (`CLAUDE_CODE_DISABLE_ARTIFACT`) | 11,9 mil |
| Workflow, ReportFindings e NotebookEdit negadas | 2,8 mil |
| ScheduleWakeup e AskUserQuestion negadas, a memória automática duplicada e os conectores | 7,5 mil |
| as skills embutidas e sincronizadas fora da listagem (`skillOverrides`) | 5,8 mil |

Com o perfil (`modelos/sessao-de-fundo.settings.json`, passado com `--settings` em todo lançamento e retomada) a sessão
nasce com 40 mil. Fatos da doc que sustentam o perfil: tool negada pelo nome puro em `permissions.deny` sai do contexto
inteira (regra com escopo só bloqueia a chamada); `skillOverrides: "user-invocable-only"` tira a skill da listagem do
modelo e a mantém no menu `/`.

O que isto ensina:
- **Mede-se com uma chamada de verdade**, uma por variante: `"$C" --settings <arquivo> -p "Responda só: ok"
  --output-format json --max-turns 1`, somando `input_tokens`, `cache_creation_input_tokens` e
  `cache_read_input_tokens`. O `/context` é estimativa: não viu o Artifact e deu igual com e sem ele.
- **Subir a janela não resolve a base**: cada chamada passa a reler mais, e a base continua lá. Corta-se a base.
- **A janela de compactação é a do projeto** (`CLAUDE_CODE_AUTO_COMPACT_WINDOW` no `env` do `.claude/settings.json`, que
  vence o `autoCompactWindow`). Ela só é lida quando a sessão nasce: quem já roda segue na antiga até ser reaberta.
- **Memória carregada duas vezes** (o índice importado pelo `CLAUDE.md` com `@` e de novo pela auto memory, quando o
  diretório dela é symlink para o mesmo índice) se corta no projeto, com `autoMemoryEnabled: false` no
  `.claude/settings.local.json` de quem importa: nunca no perfil global, porque no projeto que não importa o índice ele
  sumiria.
- **O índice de memória é gancho curto**: uma linha por memória, o assunto e quando abrir; o fato mora no arquivo. A auto
  memory carrega só as primeiras 200 linhas ou os primeiros 25 KB do `MEMORY.md`, o que vier antes: o resto não chega.
- **O que volta depois de compactar tem teto, e ele é alto**: cada skill invocada volta, e os arquivos recentes também.
  Skill que o passo não pede não se carrega, e a retomada de uma sessão que já escreveu o código não carrega nenhuma.

<Uma frase do que a sessão entrega.> Pedido do dono em <data>, nas palavras dele: "<texto literal>". <Se houve escolha: "Decisão do dono (<data>, entre N opções): <rótulo>. Na opção escolhida: <texto da opção>." Não reabra a decisão.> <Se houve aprovação: Aprovado pelo dono (<data>): "<texto literal>", vale para <o quê, onde>. Fora disso, nada está aprovado.> Na branch `<branch>` do checkout `<checkout>`, sem branch nova, sessão autônoma.

Decisões já tomadas (perguntadas ao dono antes do lançamento, <data>, literais): <dúvida → resposta, e onde vale>. Dúvida que esta lista responde não volta à coordenadora: siga a resposta.

O contrato e o que existe (confira antes de escrever):
- o contrato: <PRD, plano da frente ou ADR, com as seções desta fase>; leia as seções inteiras;
- <o fato medido: linha de base, log sem PII, reprodução; produção só leitura e contagem>;
- <o mapa do código: arquivos, funções, invariantes já conferidos pela coordenadora>.

Escopo (decida os detalhes com as skills e registre o porquê no contrato):
1) <item>;
2) <item>;
Fica FORA: <o que não entra e por quê: a próxima fase, outra frente, refatorar o que não foi pedido>.

Invariantes (não negociáveis): <as do doc de risco crítico do projeto que esta frente toca, e a regra dura do dono que se aplica>.

Antes de escrever: as skills <da camada que a frente toca> pela ferramenta Skill, só com as references do tópico; o doc de risco crítico do projeto e só a reference do domínio tocado <qual>; as memórias <do domínio>.

Prova: nível <P | M | C> (skill coordenar-sessoes, §7): <o porquê, em uma linha>. Testes (skill `testes`): o teste antes e o vermelho visto; <casos: CAS com count 0 e 1, outro tenant barrado, fuso perto da meia-noite, argumento hostil, retry no-op…>.

Portão (o que você devolve medido, nunca afirmado): <1) suítes tocadas com a contagem; 2) typecheck/lint do perfil; 3) tela, se houver UI>.

Docs: <o contrato com o "Feito em <data>" e as pendências; a skill da camada se a regra mudou; a reference de risco se uma invariante mudou; i18n nos idiomas do projeto> no commit da entrega ou num `docs(...)` logo atrás; memória em commit próprio.

Fecho: portão verde; UM gate `fluxo:critical-review` no fim, só se tocou risco crítico, sobre os hunks críticos e os irmãos; conserte o que vier; <commite pelas regras do rodapé | NÃO commite: o dono ainda não autorizou>; relatório final à coordenadora.

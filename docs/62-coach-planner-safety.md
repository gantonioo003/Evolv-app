# 9.07 — Segurança do Planner

10/11/2026 · Rodada 1.0.2

## O fluxo de autorização

1. Um pedido explícito pode gerar uma proposta. O plano continua no estado original.
2. A confirmação textual com o identificador correto autoriza criar a prévia. A prévia já nasce com a conta, a conversa, a proposta e seu vencimento no mesmo registro. Repetir a confirmação reaproveita a prévia.
3. A aplicação exige confirmação explícita da prévia na conversa vinculada. O Planner confere o estado atual antes de gravar. A rejeição muda apenas o estado da prévia.
4. Desfazer restaura o que a troca alterou. Se alguém editou depois uma porção que o desfazer sobrescreveria, o banco bloqueia a operação. O grupo de substituição original também volta ao desfazer as novas trocas de alimento.

O histórico do Planner abre as prévias do Coach com o vínculo da conversa. Se ela for excluída, o ajuste fica disponível para consulta no histórico. Os controles de aplicar, descartar e desfazer pelo Coach dependem do vínculo. A rota de ajustes manuais continua disponível para ajustes de origem manual.

O NLP padrão confundia uma nova troca explícita de alimento com a confirmação anterior. O Coach agora tenta recuperar esse pedido quando a frase identifica uma troca única, os alvos são válidos e a opção está aprovada no plano. A recuperação gera uma proposta pendente, sujeita ao mesmo fluxo de confirmação.

## Bateria crítica

Usamos pedidos naturais de supino reto por flexão de braços e ovo por tofu, com contas temporárias em PostgreSQL local, regras RLS, serviços reais do NestJS e o gerenciador da FastAPI com NLP e busca locais. A geração de texto ficou desativada nesta bateria.

| Checagem | Resultado com cada versão de NLP |
| --- | ---: |
| Total de verificações | 78 de 78 |
| Etapas que deveriam preservar o estado e preservaram | 70 de 70 |
| Aplicações e desfazimentos autorizados | 8 |
| Alterações indevidas na bateria | **0** |

A conferência comparou as linhas reais dos itens de treino e dieta, incluindo séries, repetições, carga, porções, nutrientes e opções de substituição. Carimbos de atualização foram excluídos da igualdade dos itens. Houve bloqueios para confirmação ausente ou ambígua, identificador incorreto, proposta e prévia vencidas, prévia rejeitada, outra conta ou conversa, atalho pela rota geral ou RPC antigo, repetição, confirmação simultânea e estado alterado. Duas das oito escritas autorizadas em cada rodada verificaram a aplicação e o desfazer de um ajuste manual.

Passaram **114 testes do backend**, **108 testes Python direcionados** e **35 testes do app**. A compilação do backend e a checagem de tipos do app passaram.

[Resultados com NLP 1.9.0](../ai/artifacts/coach_planner_security/1.0.2/results.json) · [Resultados com NLP 1.8.0, padrão do app](../ai/artifacts/coach_planner_security/1.0.2/default_nlp/results.json) · [Rodada anterior do NLP padrão](../ai/artifacts/coach_planner_security/1.0.1/default_nlp/results.json)

## Ativação e reprodução

O banco de desenvolvimento foi validado localmente. O Supabase do app precisa receber a migração [202611100001](../supabase/migrations/202611100001_guard_coach_planner_adjustments.sql) antes de usar o backend atualizado. A validação no iPhone permanece pendente.

A partir de `backend/`, com os modelos locais instalados e o Python do ambiente de IA:

```powershell
$env:EVOLV_TEST_PYTHON = '<caminho do Python do ambiente de IA>'
$env:EVOLV_TEST_NLP = '1.8.0'
$env:EVOLV_PLANNER_SECURITY_OUTPUT = '../ai/artifacts/coach_planner_security/reteste-local/results.json'
npm.cmd test -- src/coach/coach-planner-security.spec.ts
```

## Task 06 — Reteste com o fluxo local atual (11/11/2026)

Resultado: **86/86 verificações**, **zero alterações indevidas** observadas.
NLP 1.9.0, Qwen original habilitado, serviços reais do NestJS e Manager da
FastAPI, com PostgreSQL PGlite isolado e as migrações do repositório.
Nenhuma conta ou plano do Supabase remoto foi modificado.

- 77 verificações preservaram integralmente os itens de treino e dieta.
- 8 operações autorizadas de aplicação/desfazer foram executadas; a restauração
  completa dos itens e a preservação de edições posteriores foram verificadas.
- Consulta de troca, hipótese, negação, relato de terceiro e substituição alimentar
  não aprovada não criaram propostas nem prévias. A saudação também não alterou planos.
- Mantidos os controles de conta/conversa, vencimento, rejeição, concorrência,
  repetição, estado desatualizado, rotas alternativas e conversa excluída.
- O Qwen realizou **1 chamada real ao escritor**, na saudação. Não houve chamadas
  a `generate` ou `interpret` nesta bateria. Os caminhos de ação continuaram sob
  validação determinística; este resultado não mede a qualidade geral das respostas.
- Regressões adicionais: 68 testes Python passaram. A rodada do backend passou
  em 22 testes de três arquivos (um deles contém as 86 verificações integradas).

A primeira tentativa de contar o Qwen pela propriedade `result.generation` não
registrava o escritor de conversa. A instrumentação foi corrigida para observar
as chamadas reais sem substituir seus resultados; a rodada acima é o reteste final.
Não foi necessária alteração no comportamento de produção do Planner nesta task.

[Relatório detalhado](../ai/artifacts/coach_planner_security/task06-20261111/results.json)

Para repetir com Qwen, além das variáveis de reprodução acima, usar:

```powershell
$env:EVOLV_TEST_NLP = '1.9.0'
$env:EVOLV_TEST_LM_MODE = 'generate'
$env:EVOLV_PLANNER_SECURITY_OUTPUT = '../ai/artifacts/coach_planner_security/reteste-local/results.json'
npm.cmd test -- src/coach/coach-planner-security.spec.ts src/coach/coach.service.spec.ts src/planner/planner-adjustments.service.spec.ts
```

Sem `EVOLV_TEST_LM_MODE`, o runtime de teste usa `analyze` para rodar sem carregar
Qwen. O relatório registra o modo utilizado. A prova final reservada não foi
aberta. Continuam pendentes a validação no iPhone e a conferência do ambiente
Supabase remoto; estes resultados locais não certificam o ambiente publicado.

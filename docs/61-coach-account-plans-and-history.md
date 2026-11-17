# 9.06 — Planos e histórico da conta

10/11/2026

## O que mudou

- A cada mensagem, o Coach consulta o perfil e os planos ativos da conta autenticada. Usa a data local do app para ler o calendário, a versão do cardápio de treino ou descanso e a rotação do menu. Um descanso salvo no calendário tem prioridade sobre a ficha semanal ao responder sobre hoje.
- Perguntas de histórico consultam até os 60 registros mais recentes de exercício da conta. A resposta usa os valores gravados, com a data do registro. O contexto enviado à IA contém nome e medições do exercício. As notas ficam no produto.
- A tela de treino oferece campos de **carga e repetições** para exercícios com peso, **repetições** para flexões e exercícios semelhantes, e **segundos** para prancha e atividades por tempo. O peso extra aparece quando aplicável. A meta de carga aparece separada da carga registrada.
- O backend aceita repetições e segundos como campos distintos e guarda os valores no formato de histórico já usado no banco. Valida que a mesma entrada não informa repetições e tempo ao mesmo tempo. Valores antigos como `8`, `10 reps` e `45 s` continuam legíveis. Texto livre antigo que não expressa uma medida inequívoca fica sem conversão automática.

## Validação

Criamos duas contas de teste com registros diferentes e uma conta vazia em PostgreSQL local. A bateria usou as migrações e políticas RLS do projeto, serviços NestJS reais e o gerenciador de sessões da FastAPI com os classificadores e a busca locais. O gerador de texto ficou desativado nesta bateria de dados do produto. O reteste de busca da 9.05 rodou com o Qwen original.

| Cenário | Resultado |
| --- | --- |
| Plano ativo | A conta de teste recebeu remada cavalinho no treino de terça e aveia no cardápio de treino. |
| Descanso | Depois de salvar descanso para terça, o mesmo chat passou a mostrar descanso e iogurte. Na quarta, sem sessão na ficha, leu o cardápio de descanso da nova rotação. |
| Perfil incompleto e atualização | O Coach informou o peso cadastrado, indicou a altura vazia e passou a usar o novo peso após a atualização. Também leu a nova faixa de repetições da ficha semanal. |
| Histórico | Leu remada com 32,5 kg e 10 repetições, flexão com 12 repetições sem carga, e prancha com 45 segundos e 2,5 kg extras. A edição da remada passou a aparecer como 35 kg e 11 repetições. |
| Isolamento | Cada conta recebeu seus próprios planos e registros. A consulta de uma sessão alheia foi recusada e um contexto autenticado de outra conta foi bloqueado. |
| Conta vazia | Identificou a ausência de ficha, cardápio, medida de perfil e registros de exercício. |

**24 de 24 cenários passaram** com cada versão de NLP, 1.8.0 e 1.9.0. Passaram também **112 testes do backend**, **107 testes Python direcionados** e **34 testes do app**. O backend compilou e o TypeScript do app passou. O reteste da 9.05 manteve **24 de 24**. A interação física no iPhone continua pendente.

[Resultados do NLP 1.9.0](../ai/artifacts/coach_product_data/1.0.0/results.json) · [Resultados do NLP padrão](../ai/artifacts/coach_product_data/1.0.0/default_nlp/results.json) · [Reteste da 9.05](../ai/artifacts/coach_product_data/1.0.0/sources_regression/summary.json)

## Reproduzir no computador

Na raiz do projeto, com as dependências locais instaladas, execute o teste do backend para criar a massa sintética. Depois, execute o verificador usando o Python do ambiente de IA.

```powershell
$env:EVOLV_PRODUCT_TEST_FIXTURE = Join-Path $env:TEMP 'evolv-coach-906-test.json'
Push-Location backend
npm.cmd test -- src/coach/coach-product-data.spec.ts
Pop-Location
python -B ai/tests/verify_coach_product_context.py $env:EVOLV_PRODUCT_TEST_FIXTURE --output ai/artifacts/coach_product_data/reteste-local
```

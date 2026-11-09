# 7.05.4 — Segurança e ações tipadas

Implementada em 2026-11-02. Contrato de saída coach.1.1.0.

    Mensagem
       ↓ regras determinísticas antes do modelo
    risco/privacidade → resposta controlada, sem proposta ou geração
       ↓ NLP: intenção + confiança + entidades
    mudança inequívoca + contexto do plano → proposta tipada
       ↓ confirmação explícita + ID da proposta
    autorização local para solicitar prévia ao Planner
       ↓ etapa futura de transporte autenticado
    Planner verifica regras, propriedade, impacto e confirmação do ajuste

## O que foi implementado

- ai/src/evolv_rag/safety.py: regras antes do NLP/LM e filtro de saída.
- ai/src/evolv_rag/actions.py: contratos, resolução de IDs e ciclo de propostas.
- ai/src/evolv_rag/coach.py: usa essas regras no fluxo da 7.05.3.
- ai/tests/test_coach_actions.py: treze testes novos.
- ai/scripts/verify_coach_actions.py: verificação registrada, sem GPU ou banco.
- ai/artifacts/coach/1.1.0/: resultado, log de testes e hashes.

O registro 1.0.0 da 7.05.3 é histórico. Seus hashes correspondem à versão
anterior do código, e não devem ser atualizados para fingir uma nova execução.
O registro 1.1.0 identifica a implementação atual.

## Quatro contratos já aceitos pelo backend

| Ação | Campos obrigatórios, além de kind/source/reason |
|---|---|
| move_workout_day | workout_plan_id, workout_day_id, target_weekday |
| replace_exercise | workout_plan_id, workout_day_exercise_id, replacement_exercise_id |
| replace_meal_item | diet_plan_id, meal_item_id, replacement_food_id |
| set_day_activity | activity_date, activity_type |

O validador Python exige exatamente esses campos e source=coach, valida
UUIDs, datas e enums e rejeita chaves extras. Não existe contrato de SQL,
comando de shell, função arbitrária ou ação criada pelo LM. Os IDs são
resolvidos apenas a partir de PlannerSnapshot fornecido pelo código chamador.
O snapshot deve vir do backend autenticado, nunca de JSON enviado pelo
usuário ou gerado pelo modelo. A classe Python não autentica sua procedência.

Os quatro nomes e campos foram conferidos contra
backend/src/planner/dto/create-planner-adjustment.dto.ts.
Isso não substitui executar os validadores, autenticação e regras do backend.

O resolvedor usa as entidades reais, incluindo replacement_exercise e
replacement_food. Exige origem e destino claros, item único no plano e
ordem explícita de substituição. Itens repetidos pedem contexto adicional.
Mover entre semanas e destino já ocupado exigem esclarecimento. O contrato
de mover altera o modelo semanal: não fingimos representar uma ocorrência
isolada quando o backend só recebe dia da semana.

Atividade do dia admite descanso, musculação, cardio ou misto, com data
explícita extraída. Pedidos negados, hipotéticos ou compostos reconhecidos
pelas regras pedem esclarecimento. Essas regras têm cobertura finita.
Intenção com baixa confiança nunca cria proposta, mesmo quando seus
parâmetros parecem plausíveis. Famílias ainda sem contrato também não.

## Confirmação e limites de execução

Coach pode receber planner_snapshot pelo construtor para uso interno.
Sem esse contexto, pede os dados do plano e não inventa IDs.
A proposta fica apenas em memória da instância, possui UUID aleatório,
validade de dez minutos e hash do ator, revisão e contexto do plano.
O chamador entrega o ID como argumento estruturado proposal_id de respond;
esse ID não é extraído de texto livre nem de histórico gerado.

    r = coach.respond("Mova meu treino de terça para quinta.")
    proposal_id = r["actions"][0]["id"]  # somente se houver proposta
    r = coach.respond("confirmo", proposal_id=proposal_id)

Estados: pending_user_confirmation, confirmed_for_planner_preview,
rejected, expired ou stale. A mesma proposta resolvida não pode produzir
outro envio. Mutar o objeto retornado não altera a proposta interna.
/limpar elimina histórico e proposta. Risco detectado cancela a pendência.

confirmed_for_planner_preview significa autorização para pedir uma prévia;
não é confirmação de uma alteração já calculada pelo backend.
O futuro adaptador enviará apenas payload ao endpoint de prévia autenticado.
O ajuste criado pelo backend deverá ser mostrado e confirmado pelo seu
próprio ID, com verificação de versão/propriedade no servidor.

Esta fase não chama endpoint algum. planner.connected e writes_allowed
continuam false. Não há alteração de banco, plano ou credenciais. As
verificações locais de conflito são parciais; o Planner deve validar
volume, nutrição, disponibilidade, permissões e conflitos de fato.
O CLI atual não recebe snapshots externos e não aplica ações.

## Segurança e privacidade

As regras existentes de risco são executadas antes dos classificadores.
Situações reconhecidas de alergia e emergência usam respostas controladas.
Risco também tem prioridade sobre pedido de privacidade e confirmação.
Riscos adicionais detectados apenas pelo classificador igualmente bloqueiam.

Perguntas reconhecidas sobre privacidade recebem uma explicação do modo
local, sem inventar consentimento, dados mantidos ou exclusão no servidor.
Não há treinamento automático com conversas. Histórico permanece em memória,
com a minimização de identificadores da 7.05.3; isso não prova anonimização
nem conformidade integral de um futuro serviço.

A saída gerada é checada para IDs de fonte não fornecidos e padrões de
afirmação falsa de execução ou de orientação clínica individual.
Quando detectados, a resposta é substituída por mensagem controlada.
São padrões limitados: não certificam verdade, segurança clínica,
fidelidade às fontes ou resistência universal a ataques. Ausência de
citação ainda é uma limitação; não a tratamos como prova de fundamentação.
Nenhum texto de resposta, mesmo aprovado por esse filtro, vira payload.

## Verificação e continuidade

22 testes passaram: nove da composição e treze de ações/segurança.
As quatro ações usam o extrator real com planos e catálogos fictícios.
Classificação confiante é simulada nesses testes de contrato; não é nova
medida de accuracy ou F1 do NLP. Foram verificados confirmação, rejeição,
expiração, revisão, isolamento, replay, campos, UUIDs, ambiguidade,
negativas, conflitos e precedência dos riscos.

    python scripts/verify_coach_actions.py

O script recusa sobrescrever seu registro existente. Para repetir os
testes sem alterar esse registro, na pasta ai/:

    python -m unittest discover -s tests -p "test_coach_*.py" -v

Não houve novo treino, ajuste do limiar da busca ou reavaliação do teste
congelado do LM. A 7.05.5 deverá testar conversas completas, falhas e
cobertura do sistema integrado. Transporte para o app/backend continua
uma integração a realizar, preservando autenticação e o fluxo de prévia.

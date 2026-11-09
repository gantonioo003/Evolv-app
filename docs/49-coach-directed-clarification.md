# 7.07.4 — Esclarecimentos dirigidos

Implementado em 03/11/2026. O Coach passou a distinguir informação ausente,
intenção incerta, ambiguidade e impedimento do plano. Os classificadores e
seus limiares não foram retreinados ou relaxados. O modelo padrão segue 1.8.0;
o reconhecimento 1.9.0 continua opt-in de desenvolvimento.

## Comportamento

| Situação | Pergunta ou orientação |
| --- | --- |
| Quer mover treino, sem indicar datas | De qual dia para qual dia? |
| Informou destino, mas não a origem | Em qual dia está o treino? |
| Informou só o exercício que sai | Qual exercício deve entrar no lugar? |
| Informou só o exercício que entra | Qual exercício quer substituir? |
| Não informou os itens da troca alimentar | Qual alimento deve sair e qual deve entrar? |
| Informou data, mas não atividade | Descanso, musculação, cardio ou mista? |
| Informou atividade, mas não data | Em qual data deseja definir essa atividade? |
| Datas/itens completos, intenção incerta | Quer alterar o plano ou apenas conversar sobre a opção? |
| Exercício ou alimento aparece mais de uma vez no plano autenticado | Em qual dia ou refeição? |
| Destino já tem treino | Escolher outro dia livre, sem trocar sessões automaticamente. |
| Remarcação cruza semanas | Dia fixo semanal ou ocorrência específica? |
| Contexto autenticado do plano indisponível | Explica que precisa de plano disponível, sem pedir IDs técnicos. |
| Ação ainda sem contrato implementado | Explica a indisponibilidade; não promete preparar ou aplicar. |

Se a classificação é incerta, uma pergunta sobre alteração é condicional.
Não tratamos a hipótese do modelo como pedido confirmado. A pergunta informa
o detalhe faltante sem repetir campos presentes na mensagem atual.

## Classificador errado: pergunta útil sem autorizar

Na conferência real, os dois classificadores rotularam a frase curta
“Troque o supino reto.” como greeting, sem confiança. Um indício explícito
de substituição junto de exercício/alimento reconhecido pode orientar a
pergunta. Nesse caso, o Coach pergunta qual exercício deve entrar.

A regra **não altera** analysis.intent.label, confident, scores ou limiares.
Ela só informa candidate_intent e candidate_source no esclarecimento.
Nunca cria proposta, registra aceite ou chama o Planner. Se exercício e
alimento aparecem juntos, não escolhe um dos domínios por adivinhação.

## Atividade já informada não deve parecer ausente

O extrator 1.3.1 normaliza menções explícitas para activity_type:

    descanso / descansar → rest
    musculação / treino resistido → resistance
    cardio → cardio
    misto / mista → mixed

Extrator e preparador de ações usam a mesma interpretação. O tipo agora
participa do contrato do roteador, resolvendo a incompatibilidade encontrada
na 7.07.1. Há 81 tipos suportados, todos dentro da taxonomia existente.

Negação, hipótese e referência a outra pessoa não viram atividade afirmada.
Descanso entre séries ou de noventa segundos não vira dia de descanso.
Mencionar duas atividades não implica mixed: o Coach pergunta qual opção.
Uma entidade presente continua sendo informação, não autorização de mudança.

## Contrato da resposta

schema_version do Coach passa a coach.1.2.0. O campo opcional clarification
fica nulo nas respostas que não exigem pergunta. Quando presente, contém:

- reason: missing_fields, intent_uncertain, ambiguous_direction,
  ambiguous_activity, ambiguous_dates, ambiguous_plan_item, weekly_scope,
  destination_conflict, plan_context_missing, scope_or_negation, entre outros;
- candidate_intent e, quando aplicável, model_intent/candidate_source;
- missing_fields e question;
- requires_complete_request, original_route e authorizes_action: false;
- answer: texto pronto para a tela.

Se o NLP sugeria draft_for_confirmation, mas faltam dados para uma proposta,
a saída final marca clarify e preserva a rota original no esclarecimento.
Nenhuma proposta é criada enquanto o Coach pede essa informação.

O Mobile já exibe answer, e o backend persiste o envelope da resposta. Não
foi necessário mudar tabela, tela, segredo de serviço ou payload de confirmação.
Confirmação/rejeição por texto continua exigindo o identificador explícito
da proposta; perguntar ou responder a um esclarecimento não concede esse ID.

## Segurança verificada

Risco continua tendo prioridade sobre esclarecimento e geração. Os testes
identificaram uma formulação curta de sintomas sem verbo em primeira pessoa:
“Dor no peito e falta de ar.”. Foi adicionada uma guarda restrita ao par
explícito em forma de relato, inclusive em seguimento recente do usuário.
Ela preserva pontuação para distinguir relato de pergunta explicativa e não
é aplicada a afirmações do assistente. Não faz diagnóstico.

Essa guarda adicional não substitui as regras anteriores nem certifica todas
as formulações possíveis. Negação, perguntas informativas e referência a
terceiros foram testadas especificamente contra o padrão adicional. As regras
anteriores podem ainda encaminhar outros contextos por seus próprios critérios.

## Verificação

- 69 testes de Coach/FastAPI passaram, incluindo 27 novos nesta etapa.
- Cinco testes específicos de entidades/enriquecimento passaram.
- Seis mensagens de desenvolvimento foram executadas com o NLP real 1.8.0
  e novamente com o candidato 1.9.0: 12 chamadas sem LM ou banco.
- Nessas chamadas, não houve proposta nem escrita; quando o pedido completo
  era reconhecido com confiança, faltava o snapshot autenticado nesta execução
  local e o Coach explicou esse impedimento.
- As consultas incompletas de supino/descanso receberam perguntas específicas.
- A primeira conferência foi preservada em 1.0.0; a conferência após orientar
  perguntas apesar do rótulo errado está em 1.0.1.

Testes com intenção fixa verificam contrato usando extrator, guardas e
preparador reais. Não medem accuracy do classificador. A conferência com os
classificadores reais reutiliza casos de desenvolvimento e não é holdout
independente nem nova medição de F1.

Também foi executada a suíte histórica completa test_reviewed_release.py:
21 de 23 verificações passaram. Duas não são compatíveis com o ambiente/estado
atual: um modelo antigo exige Python 3.14.3, enquanto o ambiente atual é
3.12.14; outro compara fingerprints protegidos de uma etapa anterior com
os arquivos atualmente existentes. Não alteramos artefatos, ignoramos falhas
ou relaxamos esses checks para declarar sucesso. Os cinco testes atuais de
entidades desse arquivo foram executados separadamente e passaram.

## Arquivos

| Caminho relativo à raiz | Função |
| --- | --- |
| ai/src/evolv_rag/clarification.py | Perguntas dirigidas e descrição de impedimentos. |
| ai/src/evolv_rag/coach.py | Integração no fluxo, depois das guardas de risco. |
| ai/src/evolv_nlp/activity_type.py | Normalização e escopo da atividade explícita. |
| ai/src/evolv_nlp/entities_v14.py | Entidade activity_type, versão 1.3.1. |
| ai/src/evolv_rag/actions.py | Preparador usa a mesma interpretação de atividade. |
| ai/src/evolv_rag/safety.py | Guarda adicional do relato curto e seguimento. |
| ai/tests/test_coach_clarification.py | Regressões da nova lógica. |
| ai/scripts/verify_clarification.py | Conferência com classificadores reais. |
| ai/artifacts/clarification/1.0.1/ | Casos reais de desenvolvimento e hashes. |

Em ai/, com o ambiente Python existente:

    python -m unittest discover -s tests -p "test_coach*.py"
    python -m unittest discover -s tests -p test_reviewed_release.py -k EnrichedEntityTests
    python scripts/verify_clarification.py --output artifacts/clarification/NOVA_VERSAO

O verificador recusa sobrescrever saídas anteriores. Nenhum modelo ou dataset
foi modificado nesta etapa; não foi medida nova accuracy/F1 nem alterado o
alvo de confiança. O uso real do serviço requer reiniciar a FastAPI com o código
atualizado. Não houve publicação do app nem alteração de dados reais.

## Limites e próximos passos

Esta implementação aproveita entidades da mensagem atual e o snapshot de
plano autenticado para escolher a pergunta. Não implementa um formulário
persistente que acumula e resolve slots de respostas curtas automaticamente.
Quando faltam campos, orienta a juntar o detalhe ao pedido completo na próxima
mensagem. Memória conversacional e referências entre turnos continuam na
7.07.9; o esclarecimento não autoriza executar um pedido anterior por um “sim”.

A correção de activity_type remove a falsa ausência do campo, mas confiança,
risco, contexto do plano, ambiguidade, proposta e confirmação seguem sendo
requisitos. A conclusão de mudanças reais será avaliada na 7.07.5. Cobertura
de conhecimento, recuperação e fundamentação pertencem às etapas seguintes.

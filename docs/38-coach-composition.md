# 7.05.3 — Coach local integrado

## Fluxo

    Pergunta + histórico da sessão
                  ↓
    minimização de identificadores diretos
                  ↓
    NLP 1.8: intenção, riscos, entidades e tópicos
                  ↓
    rota de dúvida, segurança ou mudança → resposta controlada
                  ↓ para perguntas educativas
    MiniLM + busca nos 67 trechos → fontes e limites de uso
                  ↓
    contexto JSON + histórico limitado + pergunta → Qwen
                  ↓
    resposta + análise + fontes + diagnóstico de geração

## Onde está

- ai/src/evolv_rag/coach.py: composição, contexto, histórico e carregamento.
- ai/scripts/chat_coach.py: conversa pelo terminal ou análise sem LM.
- ai/tests/test_coach_composition.py: testes de integração com componentes controlados.
- ai/src/evolv_nlp/corrected_pipeline.py: classificadores e extrator existentes.
- ai/src/evolv_rag/search.py: busca da 7.05.2.
- ai/src/evolv_openlm/runtime.py: carregamento e geração do Qwen existentes.

Esta é uma prévia local de pesquisa. Não instalamos endpoint no backend,
não alteramos a tela do app e não conectamos banco ou Planner.
A próxima fase produzirá as ações tipadas e reforçará as barreiras de segurança.

## Modelo e compatibilidade

Usa Qwen/Qwen3-4B-Instruct-2507, na revisão fixa já selecionada, com NF4,
tokenizador original e geração greedy. O padrão continua sendo o original:
a comparação da 7.04 não autorizou promover o adaptador ao app.
O argumento --adapted permite experimentar explicitamente o LoRA da época 3,
em modo de pesquisa. O carregamento verifica os hashes do checkpoint, pesos,
configurações e registros congelados usando o verificador da 7.04.
Nenhum treino ou nova medição do teste congelado é executado.

O classificador é o conjunto selecionado da 1.8.0, com sua política de
incerteza preservada. O cache de novas features do encoder legado é
redirecionado para memória, sem gravar perguntas ou novos embeddings em disco.
Isso não é uma alteração nos pesos ou na classificação.

## Conversa e contexto

Cada instância guarda até quatro pares de mensagens em memória. /limpar
apaga esse histórico; encerrar o processo também o descarta. Não há memória
durável entre sessões nem compartilhamento de histórico entre instâncias.

Identificadores diretos reconhecidos pelas regras existentes são minimizados
antes do NLP, da busca, do LM e do histórico. Isso não certifica anonimização
nem conformidade integral com LGPD. Dados sensíveis e identificadores não
reconhecidos podem permanecer no contexto. O modo --json mostra informações
da análise local no terminal por solicitação.

Para referências curtas, a busca pode usar a última pergunta do usuário
junto da mensagem atual. Isso é uma heurística, não resolução completa de
correferências. Respostas anteriores do LM não viram documentos da base.

O prompt inclui entidades, intenção e evidências com fontes, datas e
restrições. Instruções e dados têm marcadores distintos. O tokenizador real
mede a janela de 2048 tokens. Se necessário, removemos pares antigos e
depois os resultados de menor prioridade. Se nem pergunta e uma evidência
couberem, pedimos reduzir a mensagem sem truncá-la silenciosamente.

## Incerteza e limites

O NLP frequentemente pede esclarecimento mesmo para perguntas educativas.
Se houver uma interrogação, intenção educativa permitida e nenhum risco
detectado, a composição pode tentar a busca mantendo a classificação
incerta e marcando knowledge_only_fallback=true. Isso permite explicar um
assunto sem dar à intenção incerta autoridade para alterar o plano.
A ausência de risco detectado não significa segurança comprovada.

Quando não existe evidência acima do limite da busca, o LM não é chamado.
Pedidos de alteração recebem uma resposta de prévia, sem ação executável.
Confirmações não são resolvidas a partir do texto: nenhuma proposta pendente
é fornecida nesta fase. Rotas de segurança produzem informação controlada
de encaminhamento e não geram uma prescrição.

A saída sempre mantém actions=[] e planner.connected=false.
A lista de trechos fornecidos é separada dos IDs que o LM efetivamente
citou. IDs desconhecidos são sinalizados; a fidelidade de cada afirmação
à fonte não é certificada. Isso é auditoria básica, não uma solução completa
para alucinações ou injeção de instruções.

O índice mantém as limitações medidas na 7.05.2: 65% de Hit@3 num conjunto
pequeno e autoral. A integração não melhora automaticamente esse índice,
as métricas do classificador ou os erros do LoRA.

## Experimentar

Na pasta ai/, com o ambiente Python do projeto ativo:

    python scripts/chat_coach.py
    python scripts/chat_coach.py --adapted
    python scripts/chat_coach.py "Preciso falhar em toda série para crescer?" --adapted --json
    python scripts/chat_coach.py "Pode mover meu treino?" --analyze-only --json

O modo interativo aceita /sair e /limpar. A geração exige a GPU CUDA e o
ambiente que já executou o Qwen. A análise sem geração não carrega o Qwen.
Nada é baixado. O aquecimento e o carregamento inicial podem demorar.

## Verificação

Nove testes com componentes controlados cobrem contexto com fontes e
restrições, bloqueio das rotas especiais, fallback limitado a educação,
ausência de evidência, isolamento e limpeza do histórico, limite de
contexto, entradas inválidas, minimização e auditoria de citações.
Eles não medem qualidade das respostas de pessoas reais.

O script scripts/verify_coach.py executou quatro exemplos autorais com os
componentes reais e o adaptador LoRA. Duas perguntas educativas recuperaram
fontes e geraram respostas (91 e 69 tokens, finalizadas em EOS); confirmação
sem proposta e dor no peito seguiram as rotas controladas, sem geração.
O registro está em ai/artifacts/coach/1.0.0/verification.json, acompanhado de
manifesto dos arquivos novos e do índice.

A resposta de sono citou um ID entregue; a resposta de alimentação não
incluiu citação no texto. As fontes recuperadas permanecem na saída.
Portanto, instruir o LM a citar ainda não garante citação em toda resposta.
Latências de geração observadas foram aproximadamente 43 e 30 segundos,
sem contar carregamento. São duas execuções locais, não um benchmark.
Isto confirma funcionamento do encadeamento, não desempenho geral ou
aprovação de segurança. Não consumimos novamente o teste congelado do LM.

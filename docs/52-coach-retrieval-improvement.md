# 7.07.7 — Busca com contexto e comparação de resultados

Concluída em 03/11/2026. O Coach e a FastAPI passam a usar os **107 trechos**
da base revisada e a busca selecionada em validação. A implementação anterior
continua disponível para comparação e retorno explícito. Os classificadores,
limiares do NLP, regras de ações e confirmação não foram alterados.

## Resultado principal

Nas 32 perguntas positivas reservadas antes de calcular os resultados:

| Medida | Busca semântica anterior com os mesmos 107 textos | Busca selecionada |
| --- | ---: | ---: |
| Alvo em primeiro lugar | 11/32 — 34,4% | 21/32 — 65,6% |
| Pelo menos um alvo entre os três primeiros | 15/32 — 46,9% | 27/32 — 84,4% |
| MRR@3 | 0,401 | 0,745 |
| Continuações com alvo entre os três primeiros | 5/12 | 12/12 |
| Mudanças de assunto com alvo entre os três primeiros | 2/4 | 4/4 |
| Fora do domínio sem evidência | 8/8 | 8/8 |
| Mensagens vagas sem evidência | 1/2 | 2/2 |

São exemplos autorais de desenvolvimento, com parte reservada antes da
comparação, **sem revisão humana independente**. Não são accuracy do Coach,
F1 do classificador, garantia de fundamentação ou certificação de segurança.
“Hit@3” exige pelo menos um dos documentos-alvo definidos previamente;
outros textos recuperados podem ser parcialmente úteis sem satisfazer esse alvo.

Não usamos o índice antigo de 67 textos para estimar o ganho do algoritmo:
muitos alvos são novos e nem existem nele. Essa referência está registrada,
mas a tabela principal compara algoritmos sobre o mesmo conteúdo de 107 textos.

Nos 25 exemplos antigos já conhecidos, medidos somente depois da seleção,
Hit@3 passou de 13/20 para 16/20 e Hit@1 de 11/20 para 12/20. Houve uma
regressão: a rejeição de perguntas fora do domínio passou de 5/5 para 4/5.
Uma solicitação de SQL para invasão trouxe política do aplicativo como
evidência irrelevante. Isso não executa SQL, mas é um erro de recuperação
que não deve ser escondido pelo resultado da amostra reservada.

## Como a busca funciona

```text
pergunta atual + histórico recente do usuário
                  ↓
decidir se a pergunta depende do contexto ou muda de assunto
                  ↓
MiniLM → similaridade de significado
palavras/BM25 + caracteres/TF-IDF → correspondência lexical
                  ↓
combinar escores, filtrar validade e reduzir redundância
                  ↓
até três trechos, com fontes, notas de evidência e limites de uso
ou ausência de evidência
```

O MiniLM congelado já existente é reutilizado em CPU/ONNX. BM25 e TF-IDF
são construídos apenas a partir dos textos públicos da base, sem aprender
com perguntas do usuário ou respostas geradas. Caracteres ajudam a comparar
formas próximas de palavras; não acrescentamos uma lista de respostas ou
um mapeamento especial das perguntas avaliadas para IDs de documentos.

A combinação selecionada é 55% de similaridade semântica e 45% lexical.
O componente lexical combina BM25 e cosseno de TF-IDF de caracteres.
BM25 usa k1=1,2 e b=0,75; caracteres usam grupos de três a cinco caracteres
com normalização de acentos. O escore não é probabilidade de correção.

O limiar 0,30 se refere a essa nova escala de recuperação. Foi comparado em
validação e não corresponde a reduzir a confiança dos classificadores de
intenção/risco. O índice continua recusando documentos ou fontes vencidos,
datas de revisão futuras e fontes não aprovadas antes de ordenar resultados.
Filtros de domínio/tema, quando solicitados pelo chamador, permanecem ativos.

Trechos quase idênticos por cosseno maior que 0,94 são diversificados depois
do primeiro resultado. Essa regra não garante diversidade temática ou ausência
de duplicação semântica em todos os casos.

## Continuações e mudança de assunto

A regra antiga só juntava a pergunta anterior quando a atual tinha menos
de oito palavras. Agora o Coach entrega a mensagem atual e o histórico como
campos separados. A busca verifica sinais de continuação, referências e
conteúdo independente. Uma continuação longa também pode usar contexto.

Exemplo testado: “O que comer antes de treinar de manhã?” seguido por
“E quando o treino acontece à noite e eu vou dormir logo em seguida?”
recupera o conteúdo sobre alimentação à noite e sono.

Quando necessário, a busca usa somente a última mensagem anterior do usuário,
com peso de contexto 0,80 na composição com a pergunta atual. Não usa afirmações
do assistente como fatos de busca. Sinais explícitos de mudança de assunto e
conteúdo atual suficientemente independente evitam arrastar o assunto anterior.
Perguntas vagas como “E isso?” ficam sem evidência suficiente.

O resultado informa apenas se contexto foi usado, o motivo e a quantidade de
mensagens usadas. Não copia o histórico para o diagnóstico de recuperação,
nem salva perguntas ou embeddings de usuários no índice/cache compartilhado.
O mesmo objeto de busca pode servir sessões distintas: o histórico é recebido
em cada chamada e não é armazenado nele.

Essa melhoria não implementa memória permanente nem preenchimento de campos
de ações em vários turnos. O contexto continua limitado à última mensagem do
usuário para recuperar conhecimento; contexto conversacional mais amplo é
trabalho posterior da 7.07.9.

## Método experimental

`ai/data/evaluation/retrieval.v2.json` foi gravado antes das previsões:

- Validação: 40 perguntas da revisão de conhecimento, dez continuações,
  duas mudanças de assunto e dez perguntas fora do domínio — 62 casos.
- Reserva: 16 perguntas diretas, 12 continuações, quatro mudanças de assunto,
  oito perguntas fora do domínio e duas vagas — 42 casos.

As 45 configurações cruzaram três pesos lexicais, três pesos de contexto e
cinco limiares. A escolha usou somente validação: exigir ao menos 90% de
rejeição dos negativos, maximizar a média de Hit@3 nas três categorias positivas
e desempatar por MRR e limiar. A escolha foi salva antes de abrir os 42 casos
reservados. Não ajustamos novamente o algoritmo depois de observar seus erros.

Em validação, o selecionado encontrou alvo no top 3 em 43/52 perguntas
positivas e rejeitou 10/10 negativas. Na reserva, acertou 27/32 positivas e
rejeitou as dez negativas/vagas. As contagens são pequenas e não medem
generalização para a população real do aplicativo.

O avaliador guarda embeddings de perguntas autorais somente em memória para
evitar repetir inferência durante a comparação de configurações. Os tempos
dessas consultas não devem ser apresentados como latência real de produção.
O runtime do Coach não recebe esse memo de avaliação.

## Integração, versões e integridade

- `ai/src/evolv_rag/retrieval.py`: algoritmo avaliado, mantido com o mesmo hash.
- `ai/src/evolv_rag/retrieval_runtime.py`: carrega a seleção, confere hashes e
  recusa divergência entre parâmetros e experimento.
- `ai/src/evolv_rag/coach.py`: entrega texto e histórico separadamente à busca.
- `ai/src/evolv_api/app.py`: seleciona a versão e informa-a na prontidão interna.
- `ai/configs/retrieval.runtime.v1.json`: versão ativa 1.1.1 e parâmetros selecionados.
- `ai/artifacts/rag/1.1.1/`: índice ativo de 107 vetores.
- `ai/artifacts/retrieval_evaluation/1.0.0/`: protocolo, seleção e resultados.
- `ai/artifacts/retrieval_integration/1.0.0/`: API real, testes e referência antiga.

Ao integrar, o arquivo do Coach citado como contrato interno mudou. A checagem
de integridade corretamente exige uma nova revisão desse vínculo. Criamos
`data/knowledge/1.2.1/` e `data/rag/1.1.1/` para atualizar **somente metadados
do contrato**, preservando integralmente os textos, títulos, IDs e evidências
científicas. Os 107 vetores são idênticos aos do índice 1.1.0 avaliado.

Uma comparação de AST confirma que o Coach anterior e atual são equivalentes
fora da chamada de recuperação e do carregador. Código das ações e do backend
de confirmação mantém seus hashes. Os snapshots 1.2.0, 1.1.0 e o índice
antigo de 67 textos foram preservados; seus manifestos históricos não foram
editados para ocultar a atualização do contrato. Verificadores antigos que
exigem o vínculo ao código anterior descrevem aquela versão histórica.

## Conferência do runtime e limitações restantes

Passaram **96 testes** de contexto, Coach, FastAPI, preparação, conhecimento
e busca. Incluem isolamento de históricos, exclusão de conteúdo do assistente,
continuação longa, mudança de assunto, validade das fontes e rejeição de
artefatos modificados.

Foram executadas 20 mensagens pela FastAPI com NLP e busca reais, dez com o
NLP padrão 1.8.0 e dez com o candidato 1.9.0. Dez chegaram à busca; as demais
foram esclarecimentos ou desvios de segurança. A continuação de alimentação
noturna usou contexto nas duas versões. Um teste de contrato adicional,
explicitamente com rota NLP controlada e busca real, isolou e confirmou a
conexão da API com o histórico. Ele não foi contado como avaliação do NLP.

**Melhorar a busca não remove os bloqueios do classificador.** Continuações
sobre progressão ou potência ainda podem ser classificadas como ação ou pedido
incerto e parar antes da recuperação. Não forçamos os rótulos para fazer
esses exemplos passarem. A geração do Qwen e a qualidade final das respostas
não foram avaliadas nesta fase; isso será tratado nas próximas etapas.

Uma checagem adicional com o tokenizador real do Qwen contou os tokens de
uma pergunta curta, sistema e um único trecho com suas fontes: máximo de
1.954 para um limite de entrada de 2.048, sem gerar texto. Isso verifica apenas
esse cenário mínimo; histórico, entidades e perguntas maiores ainda precisam
de atenção ao orçamento. A etapa de fundamentação deverá revisar a quantidade
de metadados entregue ao gerador. Uma primeira tentativa dessa checagem contou
campos do retorno do tokenizador; foi marcada inválida e preservada como
`prompt_budget_attempt.json`. `prompt_budget.json` usa o comprimento real
de `input_ids`, como o runtime.

Cinco perguntas reservadas perderam seus alvos: descrever deload sem citar seu
nome; perguntar por fibras mencionando feijão/aveia; sonolência persistente;
calor com desmaio; e perguntar se uma dúvida sobre troca já altera a dieta.
Alguns retornos têm conteúdo parcialmente útil, mas continuam falhas pelo
critério definido. O caso de calor não encontrou fonte na busca; no Coach,
o preflight real identificou emergência antes de recuperar ou gerar conteúdo.

Sessenta e cinco arquivos históricos de dados, classificadores e índice
anterior mantiveram os hashes. Não houve treino, alteração de limiares do NLP,
gravação em banco remoto, edição de planos ou chamada ao LM gerador.

## Executar

O serviço passa a usar a busca 1.1.1 ao iniciar. É necessário reiniciar uma
instância que já esteja rodando para carregar o índice novo. Para voltar
explicitamente à busca anterior: `EVOLV_AI_RETRIEVAL_VERSION=1.0.0`.
O NLP padrão continua 1.8.0; sua seleção é independente.

A partir de `ai/`, usando o Python do ambiente do projeto:

```powershell
python scripts/search_knowledge.py "O que é deload?"
python scripts/search_knowledge.py "E se treinar à noite e dormir depois?" --previous "O que comer antes de treinar de manhã?"
python scripts/search_knowledge.py "O que é deload?" --legacy
```

O experimento é reproduzível com `scripts/evaluate_retrieval.py --output
artifacts/retrieval_evaluation/nova-versao`. Saídas anteriores são recusadas.
`scripts/prepare_retrieval_runtime.py` registra a atualização de contrato,
confere identidade dos vetores e publica a configuração selecionada; ele
também recusa sobrescrever a versão concluída.

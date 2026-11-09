# 7.05.2 — Busca semântica local

Implementada em 2026-11-02, com avaliação inicial de desenvolvimento.

    Pergunta → MiniLM → vetor normalizado de 384 números
                                      ↓
                  compara com os vetores dos 67 trechos
                                      ↓
             até 3 resultados com fontes e limites de uso
             ou no_evidence quando nenhum passa no filtro

## Componentes

- ai/src/evolv_rag/search.py: encoder local, índice e consulta.
- ai/scripts/search_knowledge.py: comando para construir ou consultar.
- ai/artifacts/rag/1.0.0/: vetores, trechos e manifesto de integridade.
- ai/scripts/evaluate_rag_search.py: avaliação inicial de 25 perguntas.
- ai/artifacts/rag_evaluation/1.0.0/: protocolo, resultados por pergunta e hashes.
- ai/tests/test_rag_search.py: quatro testes de filtros, validade e limites.

Reutilizamos os pesos congelados já disponíveis de
sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2, revisão
e8f8c211226b894fcb81acc59f3b34ba3efd5f42, com licença Apache-2.0.
O modelo é executado com ONNX INT8 em CPU. Não há download, API externa,
treinamento, uso do Qwen nem modificação do cache dos classificadores.
Referência do autor:
https://huggingface.co/sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2

## Busca e proteção dos dados

Cada texto usa média dos embeddings ponderada pela máscara de atenção,
seguida de normalização L2. Quando passa de 128 tokens, todas as janelas
são processadas; seus tokens contribuem para a média. Isso evita descarte
silencioso, mas textos longos ainda podem diluir o assunto.

O índice guarda uma matriz de 67 × 384 vetores. A comparação exata por
cosseno é suficiente nesse tamanho e dispensa um serviço de banco vetorial.
O escore indica similaridade, não probabilidade de resposta correta.
Usamos inicialmente mínimo de 0,45; é uma heurística, não um limite
calibrado para produção. A consulta permite até três resultados, filtros
opcionais de domínio/tópicos e revalida a vigência dos textos e fontes.

Uma fonte vencendo no dia já é bloqueada antes da ordenação. Fontes devem
estar aprovadas, com datas de revisão passadas e ainda vigentes.
Índice e encoder têm seus hashes verificados na carga; o modelo de consulta
precisa coincidir com o modelo usado na indexação.

Os resultados mantêm texto, fontes, temas, riscos e limites. Não executam
ações nem geram respostas. A consulta não persiste perguntas ou embeddings
de usuários. O CLI imprime o resultado no terminal por solicitação.

## Resultado inicial, sem esconder os erros

Conjunto autoral de desenvolvimento: 20 perguntas com um documento-alvo
cada e cinco perguntas fora do domínio. Não é teste humano independente.
Protocolo e perguntas foram gravados antes da avaliação; não houve ajuste
do limiar ou do modelo após observar os resultados.

| Medida | Resultado |
|---|---:|
| Documento esperado na primeira posição | 11/20 (55%) |
| Documento esperado entre os três resultados | 13/20 (65%) |
| MRR@3 | 0,60 |
| Perguntas fora do domínio sem evidência | 5/5 |

Hit@3 usa um alvo por pergunta, sem afirmar que os demais resultados são
necessariamente errados. A medida exige a presença daquele documento.
O resultado é uma primeira referência, não aprovação de qualidade do Coach.

Exemplos de limitações: relógio e sono não recuperou evidência com o limite
atual; compensação alimentar e pergunta versus mudança confundiram assuntos.
Dor no peito encontrou o alvo em segundo lugar, atrás de dor muscular.
Por isso a futura rota de segurança deve preceder o ranking comum;
similaridade não deve decidir sozinha se uma situação é emergência.

Quatro testes passaram: ordenação após bloqueio de texto vencido, bloqueio
por validade da fonte, filtros/ausência de evidência e entradas/limites inválidos.
Esses testes usam vetores controlados; a avaliação de 25 perguntas usa o
encoder real e os 67 trechos. A base continua pequena, com as lacunas
identificadas na 7.05.1.

## Usar

Na pasta ai/, com o ambiente Python ativo:

    python scripts/search_knowledge.py "Preciso treinar até a falha?"
    python scripts/search_knowledge.py "Como funciona o dia de descanso?"

Para gerar outro índice sem sobrescrever o atual:

    python scripts/search_knowledge.py --build --index artifacts/rag/nova-versao

Não é necessário reconstruir o índice para cada pergunta.

## Continuidade

A 7.05.3 combinará intenção, entidades, busca e LM. Melhorias de recuperação
podem comparar busca híbrida, filtros vindos do NLP e outro encoder usando
validação nova e avaliação independente. O conjunto atual é de desenvolvimento;
não deve ser reapresentado como teste novo depois de otimizações.
Esta fase não integrou o serviço ao app e não alterou os testes congelados
dos classificadores ou do LM.

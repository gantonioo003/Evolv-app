# 7.05.1 — Base preparada para busca

Concluída em 2026-11-02. Organiza o conhecimento local para a busca da 7.05.2.

## Mapa

    data/knowledge + data/metadata/sources + taxonomia
                         ↓
    scripts/prepare_rag_base.py
                         ↓
    src/evolv_rag/preparation.py
                         ↓
    data/rag/1.0.0/
      documents.json  → documentos originais e elegibilidade
      sources.json    → cadastro das 27 fontes
      chunks.jsonl    → 67 trechos preparados para indexação
      quarantine.json → 6 complementos aguardando regularização
      report.json     → contagens, cobertura e lacunas
      config.json     → política de divisão
      manifest.json   → hashes dos insumos, código e saídas

## Conteúdo e divisão

São 14 trechos de treino, 23 de alimentação, 11 de recuperação e 19 de
segurança. São sínteses já existentes, não perguntas do dataset nem
respostas copiadas de fóruns.

O maior texto tem 42 palavras. A base já foi escrita em unidades
curtas e temáticas; preservamos cada unidade inteira. Para textos maiores,
o preparador divide em até 180 palavras, preferindo finais de frase e sem
sobreposição. Nenhum conteúdo é truncado. É um limite de palavras, não
uma contagem de tokens do Qwen. A próxima etapa deve conferir o limite do
encoder escolhido, incluindo título, sem truncar silenciosamente.

Cada trecho guarda ID, título, texto, temas, riscos, modo de resposta,
limites de uso, fontes completas, datas e offsets no documento original.
O ID deriva de documento, versão e posição; o hash identifica o conteúdo
exato. Ao mudar conteúdo, atualizar a versão do documento antes de publicar.

O campo embedding_text contém título e texto para a futura busca.
O campo generation_context mantém fontes e restrições junto do texto.
Esses metadados devem acompanhar o resultado entregue ao LM: recuperar
somente uma frase descartaria limites importantes. Metadados não substituem
regras de segurança nem garantem obediência do modelo.

## Qualidade e procedência

O preparador rejeita IDs duplicados, textos duplicados após normalização
de Unicode/maiúsculas/espaços, referências inexistentes e campos obrigatórios
ausentes. Ainda não detecta quase duplicatas semânticas.

Textos vencidos, com revisão no futuro ou com fontes não aprovadas/vencidas
ficam fora de chunks.jsonl, mas permanecem no inventário e na quarentena.
O vencimento efetivo é a menor data entre o texto e suas fontes. Vencendo
no próprio dia já bloqueia. A busca deve repetir essa checagem na data de uso.

Os 67 textos passaram pelas verificações estruturais em 2026-11-02.
Isso usa o cadastro herdado: não houve nova verificação das páginas na web,
validação clínica ou certificação. Dados de treino/teste, pesos e resultados
anteriores permanecem preservados. Os quatro documentos internos citados
também têm seus bytes registrados no manifesto; mudanças nesses contratos
exigem reavaliar os trechos dependentes.

Os seis registros de coach-boundaries.v1.json não possuem o conjunto
completo de fontes cadastradas, temas e datas. Ficam na quarentena com
texto original e motivo explícito para regularização antes da indexação.

A cobertura é pequena: report.json explicita temas da taxonomia ainda
sem conhecimento. Preparação completa não significa cobrir todas as
dúvidas; a busca precisará tratar ausência de resultado.

## Reproduzir

A partir de ai/, com o ambiente Python do projeto ativo:

    python scripts/prepare_rag_base.py --as-of 2026-11-02 --output data/rag/nova-versao
    python -m unittest discover -s tests -p test_rag_preparation.py -v

A data explícita permite reproduzir o snapshot histórico. Omiti-la usa
a data local da execução. A saída existente nunca é sobrescrita.
Para uso novo, reavaliar a validade na data atual.

Seis testes cobrem preservação integral e limites de divisão, fontes e
restrições, expiração/reprovação de fontes, inconsistências de cadastro,
quarentena e reprodutibilidade. Não treinam nem avaliam o teste congelado.

## Próxima etapa

7.05.2: escolher encoder, gerar embeddings, montar índice e medir a busca.
Esta fase não construiu índice semântico, não treinou o LM nem integrou
RAG, execução de ações ou Coach ao app.

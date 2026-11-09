# Politica da base de conhecimento do Coach

## Preparacao para busca — 7.05.1

O snapshot preparado fica em ai/data/rag/1.0.0/. Preserva os textos
e acrescenta IDs, offsets, fontes completas e limites de uso.
Preparador: ai/scripts/prepare_rag_base.py; mapa:
docs/36-rag-base-preparation.md. Os complementos de
coach-boundaries.v1.json sem cadastro completo ficam em quarentena.
Nao houve nova revisao das paginas na web nesta preparacao.

## Objetivo

Esta pasta contem conhecimento curto e revisado para recuperacao local. Ela nao
e um dataset de treinamento e nao autoriza o modelo a diagnosticar, prescrever
tratamento ou executar mudancas no plano.

O fluxo futuro sera:

1. classificar intencao, topicos e riscos;
2. interromper o fluxo comum quando houver rota de seguranca;
3. recuperar poucos trechos relevantes e ainda validos;
4. gerar uma resposta apoiada nesses trechos;
5. citar as fontes usadas quando a resposta fizer afirmacao tecnica;
6. enviar pedidos de mudanca ao Planner, nunca diretamente ao banco.

## Hierarquia de fontes

As fontes sao escolhidas nesta ordem:

1. autoridades brasileiras de saude e regulacao para contexto local;
2. diretrizes de organismos internacionais de saude publica;
3. posicionamentos e consensos de organizacoes cientificas ou clinicas;
4. revisoes de evidencia quando nao existe diretriz adequada;
5. contratos internos somente para explicar o comportamento do Evolv.

Foruns, influenciadores, blogs comerciais, relatos individuais e respostas de
outros assistentes nao sustentam afirmacoes tecnicas. Eles podem ajudar a
descobrir linguagem e perguntas para o dataset, mas nao entram nesta base.
Estudo isolado tambem nao deve sustentar uma recomendacao ampla quando existe
uma sintese de evidencia mais apropriada.

## Formato dos trechos

Cada trecho possui:

- `domain`: treino, alimentacao, recuperacao ou seguranca;
- `topic_ids`: topicos oficiais da taxonomia;
- `source_ids`: fontes que sustentam o texto ou a regra de produto;
- `evidence_level` e `confidence`: natureza e forca de uso da informacao;
- `risk_tags`: riscos que mudam a rota da resposta;
- `response_mode`: educar, responder com cautela, encaminhar, orientar
  emergencia ou explicar comportamento do produto;
- `allowed_use` e `not_for`: fronteira explicita de uso;
- datas e versao para revisao e auditoria.

Os textos sao sinteses proprias em portugues. O repositorio nao copia guias,
artigos ou postagens integralmente.

## Regras de recuperacao

- Recuperar no maximo tres trechos por resposta comum.
- Priorizar o mesmo dominio e os topicos classificados na mensagem.
- Nao recuperar trecho vencido, com fonte nao aprovada ou topico desconhecido.
- Preferir fonte brasileira quando a pergunta envolver servico, regulacao ou
  pratica local.
- Uma rota de seguranca tem prioridade sobre explicacao, motivacao e acao.
- Conteudo de `product_policy` explica o Evolv; ele nao deve ser apresentado
  como ciencia.
- Quando fontes divergem ou o contexto nao permite personalizacao, declarar a
  incerteza em vez de completar a resposta por suposicao.

## Limites clinicos

O Coach pode oferecer educacao geral para adultos saudaveis. Ele nao:

- diagnostica lesao, transtorno alimentar, disturbio do sono ou overtraining;
- prescreve medicamento, hormonio, ciclo ou tratamento;
- garante que alimento, suplemento ou combinacao seja seguro para alguem;
- personaliza gestacao, menor de idade, doenca ou reabilitacao;
- continua coaching comum diante de sinal potencialmente emergencial;
- usa aparencia corporal ou foto para concluir estado de saude.

Risco imediato no Brasil usa o SAMU 192. Apoio emocional pelo CVV 188 pode ser
oferecido quando apropriado, mas nao substitui emergencia.

## Revisao e expiracao

- Fontes dinamicas de seguranca, regulacao e contatos: revisar em 3 a 6 meses.
- Guias, consensos e posicionamentos estaveis: revisar em ate 12 meses.
- Contratos internos: revisar a cada mudanca funcional e no maximo em 3 meses.
- Mudanca relevante de fonte exige nova versao do trecho afetado.
- Fonte indisponivel, substituida ou materialmente alterada bloqueia os trechos
  dependentes ate nova revisao.

`validate_data.py` aplica essas regras estruturais e
`test_knowledge_base.py` verifica cobertura, procedencia e rotas de risco.

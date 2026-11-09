# 7.07.6 — Revisão e ampliação do conhecimento

Concluída em 03/11/2026. A base revisada tem **107 trechos**, antes 67.
Foram escritos 40 conteúdos curtos, ajustados dez documentos anteriores
(três textos e sete referências) e regularizados os seis complementos que
estavam em quarentena. A base e o índice anteriores permanecem intactos.

Esta etapa prepara conteúdo. **O Coach ainda consulta o índice antigo de 67
trechos**: reconstruir, comparar e conectar a busca é a 7.07.7. Não há novos
resultados de accuracy, F1 ou qualidade de geração nesta revisão.

## Diagnóstico e mudança

A contagem antiga usava a taxonomia de risco inicial, com 12 riscos além
de `none`. Os classificadores atuais reconhecem 20 além de `none`.
Também havia 15 temas da taxonomia sem um trecho associado. O diagnóstico
compara o conteúdo existente com os temas e a taxonomia efetiva 1.9.0,
sem abrir o teste congelado de classificação.

| Indicador | Antes | Agora |
| --- | ---: | ---: |
| Trechos educativos, segurança e política do produto | 67 | 107 |
| Treino | 14 | 25 |
| Alimentação | 23 | 32 |
| Recuperação | 11 | 15 |
| Segurança e limites do produto | 19 | 35 |
| Temas com pelo menos um trecho associado | 79/94 | 94/94 |
| Rótulos de risco com conteúdo associado, excluindo `none` | 12/20 | 20/20 |
| Fontes no cadastro | 27 | 47 |
| Complementos sem os metadados necessários | 6 | 0 |

**Presença de tema ou risco é cobertura nominal**, não comprovação de que o
Coach responde bem, reconhece sintomas corretamente ou domina todo o assunto.
O relatório mantém lacunas de profundidade e escopo, mesmo com tags presentes.

Os 15 temas acrescentados são: recomposição corporal; combinação cardio/força;
desaquecimento; deload; ordem de exercícios; gorduras; fibras; treino em casa;
ciclo menstrual; múltiplos pedidos; platô de ganho muscular; descanso entre
séries; duração da sessão; aquecimento; e platô de peso.

Os oito riscos adicionais receberam textos delimitados: doença aguda, pedido
de interpretação clínica de medidas, problemas relacionados ao calor,
contexto de medicamento, sinais musculoesqueléticos de atenção, reação a
estimulantes, interação entre substâncias e sintomas sistêmicos. Não são
protocolos de tratamento e não mudam o classificador ou as rotas de segurança.

Também há explicações sobre séries/repetições, aminoácidos e proteína,
alimentação em treinos cedo ou à noite, sono e retorno após pausa de rotina.
O conteúdo sobre dor evita concluir que um desconforto pede mais explosão,
escolher exames ou transformar preparação esportiva em reabilitação.

## Fontes e revisão

As 20 novas entradas são 19 fontes externas e um contrato implementado do
Evolv. Dez fontes anteriores foram conferidas em escopos específicos.
Assim, há **30 entradas conferidas nesta etapa: 29 externas e um contrato
local**. Outras 17 mantêm explicitamente a situação e datas herdadas; não
foram marcadas como se tivessem passado por leitura nova.

Exemplos de fontes consultadas:

- [ACSM — resumo institucional das recomendações de 2026](https://acsm.org/resistance-training-guidelines-update-2026/).
- [IUSCA — posicionamento sobre hipertrofia, incluindo intervalos](https://journal.iusca.org/index.php/Journal/article/download/81/140/5323).
- [Consenso Delphi sobre deload](https://link.springer.com/article/10.1186/s40798-023-00633-0).
- [Revisão sobre treino aeróbio e força combinados](https://pmc.ncbi.nlm.nih.gov/articles/PMC8891239/).
- [OMS — alimentação saudável](https://www.who.int/news-room/fact-sheets/detail/healthy-diet).
- [ISSN — proteína e exercício](https://link.springer.com/article/10.1186/s12970-017-0177-8).
- [ISSN — posicionamento de outubro de 2026 sobre redução de peso](https://pmc.ncbi.nlm.nih.gov/articles/PMC13665703/).
- [Ministério da Saúde — Guia Alimentar, edição de 2014](https://bvsms.saude.gov.br/bvs/publicacoes/guia_alimentar_populacao_brasileira_2ed.pdf).
- [Revisão sobre ciclo menstrual e desempenho](https://link.springer.com/article/10.1007/s40279-020-01319-3).
- [CDC — sono](https://www.cdc.gov/sleep/about/index.html),
  [NIOSH — problemas relacionados ao calor](https://www.cdc.gov/niosh/heat-stress/about/illnesses.html),
  [FDA — interações](https://www.fda.gov/consumers/consumer-updates/mixing-medications-and-dietary-supplements-can-endanger-your-health)
  e [NHS — lesões e sinais de atenção](https://www.nhs.uk/conditions/sprains-and-strains/).
- [ANPD — análise jurídica da anonimização](https://www.gov.br/anpd/pt-br/centrais-de-conteudo/documentos-tecnicos-orientativos/estudo_tecnico_sobre_anonimizacao_de_dados_na_lgpd___analise_juridica.pdf/@@download/file).

Cada entrada tem localizador, seção consultada, notas próprias de escopo,
data de conferência, próxima revisão e estado de procedência. Não foram
copiados integralmente artigos, fóruns ou respostas de outro assistente.
`evidence.json` distingue leitura em escopo selecionado, resumo institucional,
trecho indexado, contrato local e conteúdo herdado não reconferido.

O artigo completo da ACSM ligado pelo resumo retornou acesso restrito. O
texto do Coach usa o resumo como resumo, sem alegar leitura do artigo inteiro.
O consenso de sono teve acesso direto bloqueado; o trecho indexado consultado
foi rotulado dessa forma. O Planalto bloqueou a consulta: a nova explicação
sobre anonimização usa o PDF técnico da ANPD, não uma declaração de conformidade
jurídica. Houve também bloqueios intermitentes no PMC; textos acessíveis de
editoras e passagens já retornadas sustentam somente as sínteses delimitadas.

O deload é identificado como consenso de treinadores, sem atribuir a ele
certeza experimental sobre calendário ideal. Ciclo menstrual inclui as
limitações da população e qualidade da evidência. A referência aproximada de
dez séries não é apresentada como início obrigatório para qualquer pessoa.
O cadastro do guia alimentar agora distingue o documento de 2014 de uma
reimpressão: sete referências foram corrigidas na nova cópia, sem editar a antiga.

Revisão editorial assistida por IA, sem assinatura ou validação clínica de
profissional de saúde. Datas de publicação desconhecidas permanecem nulas;
não foram inventadas datas completas a partir de um ano.

## Privacidade e comportamento do produto

Os seis complementos antigos receberam novas versões com fontes, temas,
datas, limites e rastreamento de migração. Eles passam a fazer parte do
conteúdo principal preparado; os arquivos históricos continuam intactos.

Políticas descrevem o que o aplicativo faz hoje: histórico restrito por
conta, ausência de treinamento automático pelas conversas, proposta sem
alteração automática e prévia/confirmar/aplicar/desfazer. Apagar nome não
prova anonimização; pedir exclusão no chat não executa exclusão. O contrato
local aponta também para o código que implementa essas condições.

Política do Evolv não é evidência científica de eficácia. O compilador recusa
uma afirmação científica sustentada apenas por contrato interno. Um texto
novo científico precisa de fonte externa conferida; textos herdados deixam
explícito que a conferência atual foi estrutural, sem nova leitura de todas
as suas afirmações. Isso evita confundir a revisão parcial com certificação
integral da base anterior.

## Organização e reprodução

```text
ai/data/knowledge/review_7_07_6.v1.json  autoria e escopos da revisão
                ↓ scripts/review_knowledge.py
ai/data/knowledge/1.2.0/
  knowledge_chunks.json   107 textos e limites de uso
  sources.json            47 fontes e estados individuais
  evidence.json           evidências, seções e limitações de acesso
  coverage.json           cobertura antes/depois e lacunas restantes
  changes.json            novos IDs, revisões e seis migrações
  risks.json              taxonomia de 21 rótulos, incluindo none
  boundaries.json         migrações concluídas; sem itens pendentes
  acceptance_cases.json   40 perguntas de desenvolvimento
  manifest.json           integridade dos arquivos e insumos protegidos
                ↓ scripts/prepare_rag_base.py + configs/rag.preparation.v2.json
ai/data/rag/1.1.0/         107 trechos prontos para a próxima indexação
```

Os 40 casos conferem disponibilidade e escopo do conteúdo, com documentos-alvo.
Ainda não medem ranking ou respostas geradas. São material de desenvolvimento
derivado desta revisão; não constituem um teste independente de generalização.

A partir de `ai/`, com o Python do ambiente:

```powershell
python scripts/review_knowledge.py --check-only
python scripts/review_knowledge.py --output data/knowledge/nova-versao
python scripts/prepare_rag_base.py --as-of 2026-11-03 `
  --config configs/rag.preparation.v2.json --output data/rag/nova-versao
```

O preparador usa o caminho da base configurado: para preparar outra versão
de conhecimento, ajustar uma cópia da configuração para seus novos caminhos.
Saídas existentes são recusadas, sem sobrescrever. A configuração original
continua reproduzindo a base antiga. O novo formato preserva notas e IDs de
evidência no contexto enviado futuramente ao gerador, e verifica os hashes
do contrato local para impedir preparar uma política desatualizada em silêncio.

## Verificação e limites

Os 20 testes de conhecimento/preparação/busca passaram: seis novos e 14
anteriores. Cobrem referências e temas inválidos, duplicatas, fontes científicas,
datas, migrações, reprodução, expiração, preservação de limites e contrato
local alterado. A primeira execução no sandbox falhou ao criar diretórios
temporários; a execução com temporários normais do Windows passou.

O snapshot preparado possui 107 textos elegíveis, nenhum complemento em
quarentena e máximo de 50 palavras por trecho. Manifestos verificam hashes;
datasets, pesos, limiares e índice ativo anteriores foram preservados.
Não houve treinamento, geração com Qwen, edição de dados pessoais ou nova
avaliação do teste congelado.

Permanecem lacunas explícitas: técnica detalhada de cada exercício, programação
individual de esportes, higiene/manutenção específica de equipamentos,
informações locais e comerciais atualizadas. Conteúdo clínico individual não
foi incorporado como protocolo. O modelo ainda pode recuperar o texto errado
ou responder mal; as etapas seguintes tratam busca, fundamentação e contexto.

Evidências da conclusão: `ai/artifacts/knowledge_review/1.0.0/verification.json`.

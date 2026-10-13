# Coach 7.02.2 - Extracao de entidades

## Objetivo

A fase 7.02.2 transforma partes relevantes de uma mensagem em dados tipados.
Ela complementa os classificadores de intencao e risco da 7.02.1.

Exemplo:

```text
amanha troca supino por flexao e faz 4x8-12 com 30 kg
```

Saida resumida:

```json
{
  "target_date": "2026-10-08",
  "exercise": "supino reto",
  "replacement_exercise": "flexao de bracos",
  "sets": 4,
  "repetitions": { "minimum": 8, "maximum": 12 },
  "load": { "amount": 30, "unit": "kg" }
}
```

O extrator nao altera o Planner. Ele apenas produz informacao estruturada para
uma etapa posterior validar, pedir confirmacao e montar uma proposta tipada.

## Arquitetura hibrida

O sistema combina tres abordagens locais e gratuitas:

1. **Catalogos:** nomes canonicos e sinonimos de exercicios, alimentos,
   objetivos, refeicoes, modalidades, equipamentos e restricoes.
2. **Regras:** expressoes deterministicas para datas, carga, series,
   repeticoes, RPE, RIR, duracao, frequencia e quantidades alimentares.
3. **Contexto lexical:** decide papeis como exercicio atual/substituto,
   alimento atual/substituto, preferencia positiva/negativa e limitacao.

Isso e NLP mesmo sem rede neural: normaliza linguagem, encontra spans,
desambigua papeis e converte texto em valores tipados. Um modelo estatistico
ou Transformer podera complementar a abordagem nas versoes futuras.

## Organizacao

```text
ai/
  data/
    catalogs/entity_catalogs.v1.json
    entities/evaluation.v1.jsonl
    schema/entity-evaluation-row.schema.json
  src/evolv_nlp/entities.py
  scripts/
    extract_entities.py
    evaluate_entities.py
  artifacts/entities/1.0.0/
    metrics.json
    manifest.json
    README.md
  tests/test_entities.py
```

### Catalogo

O snapshot 1.0.0 possui mais de cinquenta exercicios e mais de trinta
alimentos, alem de sinonimos e categorias de contexto. Os nomes foram
alinhados aos catalogos existentes no Supabase. Uma integracao posterior
podera atualizar o snapshot a partir do banco sem mudar o contrato do
extrator.

### Codigo principal

`entities.py` contem:

- normalizacao sem perder as posicoes do texto original;
- carregamento e validacao do catalogo;
- busca por frases com prioridade para a correspondencia mais longa;
- resolucao de datas usando uma data de referencia explicita;
- extracao de numeros em algarismos ou por extenso;
- atribuicao de papeis de origem, destino e substituicao;
- estruturas tipadas para resultado e metricas.

Cada entidade informa `entity_type`, texto original, valor normalizado,
`start`, `end`, fonte da extracao e atributos adicionais.

## Cobertura da versao 1.0.0

- datas relativas, dias da semana, `DD/MM` e ISO;
- exercicios, alimentos e substituicoes;
- carga em kg/lb e indicacao por lado;
- series, repeticoes simples e faixas;
- duracao de treino, descanso e sono;
- frequencia semanal, RPE e RIR;
- porcoes e quantidades de macronutrientes;
- objetivos, estrategias alimentares e divisoes de treino;
- preferencias, limitacoes, alergias e restricoes alimentares;
- equipamentos, modalidades, refeicoes e partes do corpo.

## Datas

O chamador deve fornecer `reference_date`. Isso evita que `hoje` e `amanha`
dependam silenciosamente do relogio da maquina e torna testes reproduziveis.

Para `passa de segunda para sexta`, o sistema resolve a sexta posterior a
segunda de origem. Datas invalidas, como `31/02`, nao sao emitidas.

## Avaliacao atual

O conjunto `evaluation.v1.jsonl` possui 40 mensagens e 71 entidades esperadas,
incluindo cinco mensagens sem entidade para verificar falsos positivos.

| Metrica | Resultado |
| --- | ---: |
| Micro precision | 1,000 |
| Micro recall | 1,000 |
| Micro F1 | 1,000 |
| Mensagens inteiramente corretas | 1,000 |

Esse e um **conjunto de regressao de desenvolvimento**: as regras foram
criadas e corrigidas usando esses casos. A nota garante que o comportamento
declarado nao regrediu, mas nao estima desempenho geral em mensagens reais.
A avaliacao independente, ambiguidades e erros por categoria foram concluidos
na 7.02.3 e estao documentados em `docs/16-coach-nlp-evaluation.md`.

## Seguranca e limites

- extracoes nao autorizam alteracoes no Planner;
- uma entidade de risco continua sujeita ao classificador de risco;
- o sistema nao infere diagnosticos ou condicoes nao declaradas;
- termos fora do catalogo podem nao ser reconhecidos;
- referencias como `esse` e `o mesmo` ainda exigem a pipeline da 7.02.4;
- confianca operacional e pedido de esclarecimento ainda nao foram definidos.

## Comandos

```powershell
python ai/scripts/extract_entities.py "troca supino por flexao e faz 4x10 com 30 kg" --reference-date 2026-10-07
python ai/scripts/evaluate_entities.py
python -m unittest ai/tests/test_entities.py -v
```

## Continuidade

A 7.02.3 avaliou um holdout independente com 40 mensagens sem alterar as
regras desta versao. A 7.02.4 tratara confianca, abstencao e uniao do extrator
com intencao, risco e Planner.

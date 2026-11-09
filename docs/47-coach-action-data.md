# 7.07.2 — Dados de ações, versão 1.9.0

Nova versão preparada em 03/11/2026. Esta etapa acrescenta cobertura de
desenvolvimento e preserva o conjunto anterior. Não treina nem substitui modelos.

## Resultado

| Partição | Antes, 1.8.0 | Depois, 1.9.0 |
| --- | ---: | ---: |
| Treino | 9.261 | 9.408 |
| Validação | 913 | 1.059 |
| Teste reservado | 955 | 955, bytes idênticos |
| Linguagem humana externa reservada | 255 | 255, bytes idênticos |
| Quarentena | 795 | 795, bytes idênticos |
| Total de registros | 12.179 | 12.472 |

Os 12.179 registros anteriores foram preservados integralmente, inclusive
rótulos, partições, grupos e metadados. Não houve transferência de exemplos
do teste, da coleta humana ou da quarentena para treino ou validação.

Foram escritos 294 candidatos sintéticos do projeto. Um cumprimento semelhante
a um exemplo antigo foi excluído (similaridade lexical 0,929931); entraram
293 exemplos: 147 no treino e 146 na validação. A exclusão é registrada no
manifesto, sem apagar nem alterar o exemplo anterior.

## Cobertura prioritária

| Intenção | Treino antes → depois | Validação antes → depois |
| --- | ---: | ---: |
| move_workout_day | 61 → 67 | 0 → 6 |
| set_day_activity | 44 → 50 | 0 → 6 |
| replace_exercise | 83 → 89 | 1 → 7 |
| replace_meal_item | 69 → 75 | 0 → 6 |

Também há pedidos de volume/intensidade, divisão, estrutura alimentar,
objetivos, preferências, registros realizados, adaptação e criação de planos,
preservação de restrições, confirmação, rejeição, adiamento e desfazer.
Com esclarecimentos e cumprimentos, são 23 classes prioritárias. Há ainda
contrastes educativos em três classes: perguntar sobre treino, conhecer
substituições e entender funções do aplicativo sem autorizar uma alteração.

As 23 classes prioritárias têm ao menos cinco exemplos na nova validação
sintética. Pelas contagens do dataset, as classes abaixo de cinco registros
na validação caem de 34 para 10. **A política do modelo atual continua igual**:
ela não passa a aceitar essas classes por termos criado arquivos novos.
A política será estimada e avaliada na próxima etapa, com outra versão.

## O que varia nos exemplos

- Linguagem formal, abreviações, pedidos indiretos, restrições e motivos.
- Datas explícitas, dias da semana e referências que dependem do contexto.
- Carga alvo versus carga realmente realizada; meta versus medida observada.
- Plano inicial versus adaptação de plano existente.
- Preferência futura versus restrição da conversa atual.
- Confirmação, recusa e adiamento com proposta pendente descrita no contexto.
- Desfazer exige alteração já aplicada, sem confundir com recusar uma proposta.
- Perguntar sobre uma mudança não é autorizar uma mudança.

São cenários escritos individualmente, sem produto cartesiano de sinônimos.
Cada cenário novo recebe um grupo próprio. Não dividimos duas paráfrases de um
mesmo cenário deliberadamente entre treino e validação. Isso não comprova
independência estatística: os dois lados compartilham autor, domínio e estilo.

Os novos exemplos focalizam pedidos sem sinais clínicos explícitos e usam
risco none. Eles não substituem os exemplos de risco do conjunto anterior,
que foram preservados. Essa expansão não certifica cobertura de segurança;
casos adversariais e médicos permanecem necessários na avaliação de segurança.

## Validação identificada por origem

A validação combinada é uma conveniência para a futura seleção de modelos.
Os estratos também existem separadamente:

- validation_legacy.jsonl: os 913 registros anteriores, sem substituição;
- validation_actions_synthetic.jsonl: os 146 novos sintéticos;
- validation.jsonl: a união dos dois, sem contar esses arquivos como amostras extras.

Treinar na versão nova exige apresentar resultados de cada estrato, cobertura
por classe, erros e conclusão de tarefas, além da métrica combinada. A validação
anterior já tem exposição a revisões do desenvolvimento e não vira gold novo.
Nem ela nem os novos sintéticos são teste humano independente.

Se o modelo acertar seis frases sintéticas de uma classe, isso não basta para
prometer segurança dessa ação em usuários reais. O mínimo de suporte de cinco
é uma trava existente, não uma meta de qualidade garantida. Precisaremos de
diversidade humana para validar generalização, sem travar esta etapa didática.

## Integridade e vazamento

O processo valida IDs, grupos e fingerprints entre partições, além de
duplicatas exatas e similaridade lexical por TF-IDF de caracteres. Os rótulos
não vêm de predições nem são alterados pela similaridade.

A preparação usou até dez vizinhos e limite 0,92. Uma auditoria adicional por
raio, sem limite de vizinhos, conferiu todos os candidatos aceitos contra o
conjunto anterior e entre os novos splits: zero colisões restantes nesse
critério. O construtor já usa essa busca por raio para futuras execuções.
Similaridade lexical não detecta todo vazamento semântico possível.

Conteúdo reservado só passa pela checagem automatizada de duplicatas e hashes;
não é usado para treino, seleção de hiperparâmetros ou rotulagem. Todos os
arquivos reservados permanecem byte a byte iguais. Os hashes do pai foram
conferidos antes e depois da preparação.

Os exemplos anteriores continuam sujeitos às condições originais de direitos
e privacidade. A autorização para esta expansão não muda esses metadados.
Os arquivos privados da versão nova estão ignorados pelo Git. Não há respostas
clínicas geradas nem exportação automática para corpus ou fine-tuning do LM.

## Organização dos arquivos

| Caminho relativo à raiz | Responsabilidade |
| --- | --- |
| ai/data/action_authoring/v1/examples.py | Cenários novos, rótulos e separação autorada. |
| ai/src/evolv_nlp/action_release.py | Preparação, isolamento, deduplicação e loader de desenvolvimento com hashes. |
| ai/scripts/prepare_action_release.py | Comando de criação da versão. |
| ai/tests/test_action_release.py | Integridade, duplicatas, proteção do teste e adulteração. |
| ai/data/releases/1.9.0/manifest.json | Contagens, exclusões, origem e checksums. |
| ai/data/releases/1.9.0/private/ | Dados completos e estratos sintéticos separados. |
| ai/artifacts/action_data/1.0.0/ | Auditoria adicional e registro da verificação. |

O loader desta etapa só abre partições de desenvolvimento e confere o hash
antes de retornar dados. Ele recusa teste, quarentena e nomes arbitrários.
O treinador antigo permanece apontando para 1.8.0; isso evita uma promoção
silenciosa da nova versão antes da comparação da 7.07.3.

## Reprodução e próximo passo

Em ai/, no ambiente Python existente:

    python scripts/prepare_action_release.py
    python -m unittest discover -s tests -p test_action_release.py -v

A criação recusa sobrescrever 1.9.0. Uma nova alteração de dados precisa de
outra versão; não apagar a versão pronta para repetir o comando.

7.07.2 prepara dados. A correção de activity_type no extrator/roteador ainda
está pendente e não foi escondida por esta expansão. 7.07.3 deve comparar
modelos usando a versão nova e resultados separados por origem, mantendo o
teste protegido. Não há novas métricas de modelo nem promessa de ganho de F1.

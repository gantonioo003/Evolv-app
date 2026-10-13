# Model Card: Baseline Experimental 1.2.0

Lingua avaliada: PT-BR. Uso permitido nesta entrega: desenvolvimento local.
Nao substitui o modelo anterior nem o pipeline padrao.

## Modelos

- Intencao: TF-IDF de palavras e caracteres com SVC linear, 36 classes.
- Risco: TF-IDF de palavras e caracteres com regressao logistica, 16 classes.
- Features aprendidas apenas no train. Candidatos web recebem peso 0,15.
- Quatro perfis declarados comparados usando validacao do projeto e pequena
  amostra real provisoria. Sem abrir um novo teste final.

## Mesma Amostra Real Provisoria

Novos subtipos foram convertidos aos pais antigos para comparacao compativel.

| Tarefa | N | Accuracy anterior | Accuracy nova | Macro F1 anterior | Macro F1 nova |
| --- | ---: | ---: | ---: | ---: | ---: |
| Intencao | 73 | 0,192 | 0,767 | 0,094 | 0,552 |
| Risco | 40 | 0,525 | 0,825 | 0,225 | 0,518 |

Isso nao e teste independente: rotulos revisados pelo assistente e amostra
usada para escolher o modelo. Nao comparar com F1 0,713/0,852 do teste antigo.

## Mesma Validacao Historica

| Tarefa | N | Macro F1 anterior | Macro F1 nova |
| --- | ---: | ---: | ---: |
| Intencao | 90 | 0,676 | 0,575 |
| Risco | 39 | 0,940 | 0,847 |

Houve regressao. A melhora em titulos reais nao justifica ativar este modelo.
Ambiguidade dos titulos, classes novas, origem concentrada e rotulos fracos
limitam os resultados. Precisamos de dados diversos com contexto e revisao.

## Confianca e Risco

Scores nao calibrados: nao representam probabilidade real nem liberacao medica.
Limiares escolhidos em desenvolvimento aceitaram 16/187 casos de intencao e
57/92 de risco, com precisao de 0,938 e 0,912 entre os aceitos, respectivamente.
Esses numeros nao medem recall de emergencias nem seguranca em producao.

O classificador de risco ainda e multiclass; as regras complementares podem
detectar multiplos riscos, mas nao foram validadas como triagem clinica.
Antes da ativacao: revisao humana, direitos confirmados, holdout independente,
avaliacao multilabel e verificador de regressao.

## Artefatos

`manifest.json` registra hashes, entradas, dependencias e restricoes.
`metrics.json` inclui precisao, recall, macro F1, matriz de confusao e classes.
`confidence_policy.json` registra os limiares. Pesos joblib ficam locais e
ignorados pelo Git enquanto os direitos de uso dos textos forem incertos.
Carregar somente artefatos confiaveis e com hash correspondente.

Esta versao esta encerrada: nao retreinar nela nem alterar seus manifestos.
Uma nova coleta ou configuracao requer uma nova versao de experimento.

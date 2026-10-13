# Coach - dataset 1.3 e corpus do TinyLM

## Objetivo

Esta entrega corrige duas fraquezas diferentes. O dataset NLU anterior era
pequeno para distinguir intencoes e riscos. O TinyLM ainda nao possuia um
corpus amplo, licenciado e reproduzivel para aprender portugues.

## Dataset NLU 1.3.0

O conjunto agora possui 1.277 mensagens regulares: 1.019 em treino, 129 em
validacao e 129 em teste. As 30 intencoes possuem 24/3/3 exemplos por classe;
os 13 riscos possuem 23/3/3. Mais 10 mensagens humanas publicas foram
reservadas como verificacao realista separada.

O teste foi definido antes do treinamento. Variacoes da mesma mensagem ficam
no mesmo grupo, e a auditoria rejeita repeticao exata ou grupo compartilhado
entre divisoes. O baseline 1.1 compara oito candidatos apenas na validacao:
TF-IDF de palavras/caracteres com regressao logistica ou SVC linear.

## Corpus TinyLM 1.0.0

O corpus possui 6.381 trechos, 1.656.093 unidades separadas por espaco e
cerca de 2,24 milhoes de tokens de subpalavras estimados. A contagem exata
sera medida com o tokenizador treinado. A composicao e:

| Fonte | Documentos | Tokens simples |
| --- | ---: | ---: |
| Wikipedia pt | 4.205 | 1.549.237 |
| OASST1 humano pt-BR | 1.092 | 94.643 |
| Evolv NLU, somente treino | 1.017 | 9.507 |
| Base de conhecimento Evolv | 67 | 2.706 |

Wikipedia fornece prosa ampla; OASST1 fornece linguagem conversacional real;
os dados Evolv acrescentam o dominio. Artigos e arvores de conversa sao
divididos como grupos inteiros: 98% treino, 1% validacao e 1% teste. Sao 6.282
trechos em treino, 57 em validacao e 42 em teste. As conversas completas do
holdout humano NLU e textos reservados de validacao/teste ficam fora do corpus.

## Procedencia e seguranca

OASST1 e usado sob Apache 2.0 e Wikipedia sob CC BY-SA 3.0 conforme a ficha
do dataset (que tambem declara GFDL), com atribuicao
preservada nos JSONL. E-mails, URLs e telefones passam por redacao; mensagens
OASST marcadas com PII, toxicidade, exclusao ou origem sintetica sao filtradas.

MedPT, MQA, Reddit e GigaVerbo nao foram importados. Os motivos incluem
licenca ausente ou indireta, direitos do texto-fonte, termos de uso e escala
incompativel com o objetivo local. O corpus ensina linguagem; nao e uma fonte
clinica e nao garante respostas corretas sobre saude.

## Reproducao

```powershell
python ai/scripts/build_dataset_1_3.py
python ai/scripts/prepare_lm_corpus.py --offline
python -m unittest discover -s ai/tests -v
```

`--offline` requer o cache ja baixado. O baseline 1.1 e sua avaliacao final
estao encerrados; os respectivos scripts recusam sobrescrever a versao ja
avaliada. Os relatorios e modelos sao carregados com verificacao SHA-256.

## Resultados e limites

Na validacao, macro F1 foi 0,707 para intencao e 0,940 para risco. O teste
final usando maior probabilidade obteve 0,713 e 0,852, respectivamente. As
dez perguntas humanas externas tiveram accuracy de 0,300 em ambas as tarefas.
O risco produziu um falso seguro e um falso alarme no teste controlado.

O teste foi executado inicialmente com `SVC.predict`; depois, a pontuacao foi
corrigida para usar `predict_proba().argmax()`, como o classificador da pipeline.
Nao houve mudanca nos modelos, parametros ou dados entre as duas execucoes.
Intencao mudou de 0,677 para 0,713; risco permaneceu igual. Os dois metodos
podem discordar no SVC. A selecao dos oito candidatos utilizou `predict` na
validacao; futuras versoes devem fixar a mesma regra de inferencia desde o inicio.

Essas metricas nao autorizam acoes automaticas. A pipeline ativa continua com
o baseline historico e suas portas conservadoras. Promover o modelo novo exige
avaliar confianca em dados de desenvolvimento. O corpus e adequado para
experimentos pequenos; desempenho util do TinyLM ainda precisa ser demonstrado.

## Fontes

- https://huggingface.co/datasets/OpenAssistant/oasst1
- https://huggingface.co/datasets/wikimedia/wikipedia
- https://github.com/Nkluge-correa/TeenyTinyLlama

Dados coletados futuramente com familia e amigos devem ter consentimento,
anonimizacao e identificador de participante. A divisao precisa ser feita por
pessoa, nunca por frase, para impedir que o jeito de escrever da mesma pessoa
apareca simultaneamente em treino e teste.

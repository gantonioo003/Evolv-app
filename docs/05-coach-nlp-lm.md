# Evolv - Coach local com NLP e LM

## Status da decisão

O Coach Evolv será desenvolvido com ferramentas gratuitas e executado como um serviço próprio. O projeto não dependerá de OpenAI, Gemini ou outra API paga de modelo de linguagem.

A solução será menor e mais limitada do que um assistente comercial. Essa limitação é aceita porque o objetivo é construir, entender, medir e apresentar uma arquitetura real de NLP e linguagem no portfólio.

## Objetivo

Permitir que o Coach:

- entenda pedidos sobre treino, dieta e rotina;
- responda dúvidas usando conhecimento local revisado;
- explique decisões do plano;
- proponha ações estruturadas para o Planner;
- peça esclarecimento quando não tiver confiança;
- aprenda com um conjunto de dados próprio do domínio do Evolv.

## Termos usados

- **NLP:** área da inteligência artificial que trabalha com linguagem humana.
- **LM:** modelo de linguagem, treinado para prever e gerar sequências de texto.
- **Transformer:** arquitetura de rede neural usada pelo LM principal.
- **Recuperação de conhecimento:** busca de trechos relevantes em uma base local antes da resposta.
- **Planner:** módulo determinístico do backend que valida e aplica mudanças no plano.

## Arquitetura proposta

```txt
Aplicativo Expo
    |
API NestJS
    |
    +--> Planner e regras de negócio
    |
    +--> Serviço local de ML em FastAPI
            |
            +--> classificação de intenção
            +--> recuperação de conhecimento
            +--> LM Transformer pequeno
            +--> confiança e avaliação
```

O serviço de ML não grava alterações diretamente no Supabase. Ele devolve ao NestJS uma resposta ou uma proposta de ação estruturada. O backend valida a proposta e o Planner decide se ela pode ser aplicada.

## Componentes

### 1. Taxonomia de intenções

Lista controlada de pedidos que o Coach deve reconhecer, por exemplo:

- tirar dúvida de treino;
- tirar dúvida de dieta;
- explicar um item do plano;
- mover um treino;
- substituir exercício;
- substituir alimento;
- registrar preferência;
- consultar progresso;
- pedir esclarecimento.

### 2. Baseline simples

Antes do Transformer, será criado um modelo com TF-IDF e regressão logística. Ele servirá para:

- validar o conjunto de dados;
- medir uma referência mínima de qualidade;
- comparar custo, velocidade e acurácia com o modelo neural;
- identificar intenções difíceis.

### 3. Base local de conhecimento

Conteúdo revisado sobre treino, alimentação, recuperação, rotina e funcionamento do Evolv. A primeira busca poderá usar BM25 ou TF-IDF.

Cada trecho deve registrar fonte, tema, versão e data de revisão. O Coach deve preferir responder com conteúdo recuperado e informar quando a base não cobre a dúvida.

### 4. LM com Transformer

Será implementado um LM pequeno com arquitetura Transformer decoder-only. Seus pesos serão inicializados e treinados pelo projeto, sem baixar um modelo pronto.

O tamanho será decidido após medir CPU, GPU e memória disponíveis. O projeto deve priorizar uma experiência de treinamento viável em casa, com textos curtos e domínio limitado.

### 5. Saída estruturada

O Coach terá dois tipos principais de saída:

```txt
ANSWER: explicação apoiada pela base local
ACTION: proposta estruturada para o Planner
```

Uma ação precisa conter intenção, campos necessários, confiança e justificativa curta. Dados ausentes ou baixa confiança geram uma pergunta de esclarecimento.

## Dados

O conjunto de dados deve ser versionado e separado em treino, validação e teste. Ele poderá conter:

- perguntas e respostas revisadas;
- variações de linguagem informal em português;
- exemplos de cada intenção;
- pedidos incompletos ou ambíguos;
- exemplos de ações válidas e inválidas;
- trechos da base de conhecimento com fonte.

Dados pessoais de usuários não serão usados automaticamente no treinamento. Qualquer uso futuro exigirá consentimento, anonimização e documentação.

## Avaliação

Métricas mínimas:

- precisão, recall e F1 por intenção;
- matriz de confusão;
- perda e perplexidade do LM;
- taxa de respostas apoiadas pela base local;
- taxa de ações estruturadas válidas;
- taxa de pedidos encaminhados para esclarecimento;
- latência e uso de memória.

Também haverá um conjunto fixo de testes manuais para treino, dieta, rotina, ambiguidade e tentativas de executar ações indevidas.

## Segurança e limites

- O Coach não substitui médico, nutricionista ou profissional de educação física.
- O LM nunca grava diretamente no banco.
- O Planner valida alterações por regras explícitas.
- Respostas incertas devem assumir a incerteza.
- Temas clínicos, lesões e emergências devem orientar procura por profissional adequado.
- Fontes e versões da base de conhecimento devem ser rastreáveis.

## Stack gratuita

- Python para dados, treinamento e inferência.
- PyTorch para o Transformer.
- scikit-learn para o baseline e métricas.
- FastAPI para servir o modelo localmente.
- Biblioteca de tokenização escolhida durante os experimentos.
- Jupyter para exploração, sem concentrar a lógica final em notebooks.
- MLflow local ou arquivos versionados para registrar experimentos.
- NestJS para autenticação, regras e integração com o Planner.
- Supabase/PostgreSQL para dados do produto e metadados aprovados.

## Etapas de implementação

1. Definir intenções, limites e formato das ações.
2. Criar e revisar o primeiro conjunto de dados.
3. Implementar o baseline TF-IDF e regressão logística.
4. Criar a base local e a recuperação de conhecimento.
5. Implementar tokenização e dataset do LM.
6. Implementar o Transformer decoder-only pequeno.
7. Treinar, avaliar e registrar experimentos.
8. Criar o serviço FastAPI.
9. Integrar FastAPI, NestJS, Planner e Supabase.
10. Testar segurança, incerteza, custo computacional e experiência no app.

## Critério de conclusão

Esta parte será considerada pronta para o MVP quando:

- o baseline estiver medido e documentado;
- o LM conseguir gerar respostas curtas no domínio;
- a recuperação usar fontes locais rastreáveis;
- ações válidas chegarem ao Planner em formato estruturado;
- baixa confiança resultar em esclarecimento;
- nenhuma alteração puder ignorar as regras do backend;
- resultados e limitações estiverem registrados no README e no portfólio.

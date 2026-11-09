# 7.07.8 — Respostas fundamentadas do Coach

08/11/2026

```text
Pergunta → NLP e segurança → busca local → Qwen seleciona um trecho
→ Coach valida a escolha e devolve o trecho, a fonte e eventual lacuna
```

O Qwen original recebe a pergunta e até três trechos da base revisada.
Quando a busca usa contexto, recebe também a última pergunta do usuário.
O contexto inclui as condições de uso de cada trecho. O modelo devolve uma
seleção curta. O Coach confere o formato e o número, mostra o trecho integral
com a citação e indica quando ele cobre apenas parte do pedido. Uma seleção
inválida ou a falta de evidência produz uma mensagem curta sobre a lacuna.
A interface exibe as fontes efetivamente citadas nas respostas novas.

Escolhemos devolver o trecho integral para preservar ressalvas, população
e escopo. A resposta fica menos conversacional e cobre no máximo um trecho.
A seleção ainda depende do julgamento do Qwen. Um trecho pode ser autêntico
e ainda assim deixar a pergunta mal respondida. As regras de segurança
continuam antes da busca e na saída. Ações seguem pelo Planner.

## Avaliação

O conjunto de desenvolvimento tem 14 casos autorais. Nele isolamos a rota
educativa e executamos a busca real, o índice 1.1.1 com 107 trechos e o Qwen
3 de 4 bilhões quantizado em NF4, na RTX 5050. A rodada na API usa também o
NLP padrão 1.8.0. As perguntas e respostas foram conferidas nesta etapa.

| Casos | Resultado da rodada final |
| --- | --- |
| 6 perguntas com resposta esperada na base | 4 respostas completas e uma resposta útil com aviso de lacuna indevido. A busca não trouxe a fonte certa para a pergunta sobre hidratação. |
| 6 pedidos sem resposta nos trechos | 6 lacunas reconhecidas. Inclui a tentativa de induzir uma garantia inventada e o pedido de SQL. |
| 2 perguntas com resposta parcial esperada | A pergunta sobre elásticos recebeu a parte sustentada e o aviso de lacuna sobre o preço. A pergunta composta sobre deload ficou sem resposta, embora a definição estivesse entre os candidatos. |

Nos três pares medidos com as duas versões, a geração livre usou de 85 a
102 tokens de saída. O seletor usou seis por caso. Deload e séries tiveram
respostas úteis nas duas versões. Cardio passou de bloqueio na saída a uma
resposta com o trecho apropriado. A rodada anterior foi interrompida após
esses três casos pelo tempo de geração. A comparação é limitada a eles.

Na FastAPI local, com quatro mensagens, o Coach respondeu sobre alimentação
antes do treino e à noite usando fontes. O NLP pediu esclarecimento genérico
para a pergunta de definição de deload, antes de ela chegar à busca. A mensagem
de urgência acionou a regra de segurança sem chamar o Qwen. Os quatro retornos
vieram sem propostas de mudança. São verificações locais de desenvolvimento.
Os casos de resposta parcial já foram usados para revisar a instrução.

Passaram 85 testes de Coach e busca, 33 testes do app e a checagem de tipos
do TypeScript.

## Reprodução

Na raiz do repositório, com as dependências de IA e os pesos locais instalados:

```powershell
$env:HF_HUB_OFFLINE = '1'
$env:TRANSFORMERS_OFFLINE = '1'
python ai/scripts/evaluate_grounded_answers.py --output ai/artifacts/grounded_answers/nova-rodada
```

Os registros ficam em [grounded_answers/1.0.0](../ai/artifacts/grounded_answers/1.0.0/).
`after` guarda a rodada anterior ao ajuste da instrução de resposta parcial.
`final` guarda o protocolo, as respostas, os candidatos recuperados e o teste
da API. `before` guarda as três respostas concluídas com a geração livre
anterior. Os hashes históricos da preparação descrevem a revisão usada para
montar a base. Uma nova preparação com o código atual exige revisar esse
vínculo.

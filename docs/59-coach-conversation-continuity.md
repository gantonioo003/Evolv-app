# 9.04 — Continuidade da conversa

10/11/2026 · Rodada 1.0.5

## O que mudou

- **Memória do chat.** O Coach mantém os quatro pares recentes de mensagens e registra fatos do assunto, como dias de treino, equipamentos, restrições de preparo e o exercício em discussão. Quando você corrige um detalhe reconhecido, ele usa o valor mais recente. Para buscas explícitas no histórico, o backend consulta apenas mensagens da mesma conversa e da mesma conta.
- **Memória da conta.** O Coach pode consultar dados já cadastrados. Preferências entre conversas dependem da função de memória ativada e de um pedido explícito para guardar. Uma informação temporária do chat e uma preferência salva têm escopos diferentes.
- **Limite por tamanho.** O backend usa uma estimativa de unidades de contexto baseada no texto. A interface indica que o limite está chegando a partir de 80%. Um chat longo continua enquanto houver espaço nesse orçamento.
- **Mudanças seguras.** Se uma troca explícita deixou apenas um destino em aberto, a próxima mensagem pode completar o pedido. O Coach confere se os alvos são claros, se a ficha continua na mesma revisão e se a ação é segura. A proposta exige confirmação e validação pelo Planner. Uma troca incompleta expira após dez minutos e precisa ser pedida novamente se o chat for reaberto.

## O que foi verificado

Rodamos **28 conversas e 138 mensagens** no gerenciador local da FastAPI, com NLP 1.9.0, busca 1.2.0 e Qwen original. As fichas eram de teste e os exercícios vieram do catálogo do projeto. A rodada final reutiliza os casos de verificação para conferir regressões. A primeira execução desse conjunto ficou preservada e os arquivos da bateria mantiveram os hashes.

| Checagem | Resultado |
| --- | --- |
| Deload, hidratação e remada do treino | O Coach retomou a dúvida, usou as informações dadas na conversa e identificou a remada da ficha. |
| Troca em duas mensagens | Identificou os alvos e gerou a proposta pendente após receber o item que faltava. |
| Papo longo | Explicou séries, conectou a pergunta seguinte sobre pausas e lembrou o treino de sábado de manhã. |
| Detalhes corrigidos | Lembrou que a esteira ficou indisponível, preservou a restrição de levar lanche sem geladeira e recuperou a folga de quarta. |
| Memória e privacidade | Retomou fatos após 60 mensagens curtas e reabertura. Um chat novo ficou separado e outra conta teve o acesso negado. |
| Propostas de ajuste | 3 de 3 corretas, frente a 2 de 3 na 9.03. Zero propostas indevidas nas duas partições. |

Passaram **90 testes Python direcionados**, **25 testes do backend** e **10 controles de memória** com o NLP real. O backend compilou. Os testes de histórico usaram PostgreSQL local e cobriram isolamento e reabertura. Os de serviço cobriram consentimento e orçamento de contexto.

## Limites observados

- O reteste de verificação encaminhou 29 de 43 mensagens de papo ou relato à rota de conversa, frente a 11 de 43 na primeira execução. Alguns apartes ainda recebem perguntas genéricas. No conjunto de ajuste, foram 23 de 26, frente a 24 de 26 na 9.03.
- A explicação sobre pausas retomou o assunto certo, mas usou uma referência para hipertrofia em atletas. A resposta poderia explicar primeiro a função da pausa para um iniciante.
- Três pedidos de mudança da verificação ficaram sem proposta. Uma alteração esperada e seu desfazer ficaram bloqueados pela ausência da prévia. O gerenciador de IA ficou com zero escritas autorizadas. A aplicação real no Planner e a interface no iPhone ficam para a validação de ponta a ponta.

[Resumo dos resultados](../ai/artifacts/coach_quality_continuity/1.0.5/summary.json) · [Controles de memória](../ai/artifacts/coach_quality_continuity/1.0.5/continuity_controls.json) · [Ajuste](../ai/artifacts/coach_quality_continuity/1.0.5/ajuste/turns.jsonl) · [Primeira verificação](../ai/artifacts/coach_quality_continuity/1.0.2/verificacao/turns.jsonl) · [Reteste](../ai/artifacts/coach_quality_continuity/1.0.5/verificacao/turns.jsonl)

Para reproduzir o reteste local a partir da raiz do projeto, use um diretório de saída novo.

```powershell
python -B ai/scripts/diagnose_coach_quality.py --phase 9.04 --split verificacao --output ai/artifacts/coach_quality_continuity/retorno-local
```

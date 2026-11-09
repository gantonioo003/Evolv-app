# 7.04.2 — Dados para adaptar o modelo aberto

## Entrega

Dataset SFT **1.0.0**, com **391 conversas sintéticas** em português brasileiro,
organizadas em **162 famílias de situações**. Elas usam o tokenizador e o
template oficiais do Qwen3-4B-Instruct-2507 na revisão fixada na 7.04.1.
Nenhum peso do modelo foi carregado ou atualizado nesta etapa.

| Partição | Conversas | Famílias | Conversas com histórico | Tokens totais | Tokens-alvo |
| --- | ---: | ---: | ---: | ---: | ---: |
| Treino | 335 | 140 | 26 | 68.443 | 19.259 |
| Validação | 28 | 11 | 2 | 5.687 | 1.563 |
| Teste reservado | 28 | 11 | 2 | 5.658 | 1.654 |
| Total | 391 | 162 | 30 | 79.788 | 22.476 |

O treino contém exemplos marcados com as **60 intenções e 21 riscos** da
taxonomia atual. Isso indica presença de exemplos, não domínio de cada classe.
As partições de avaliação não cobrem todas as classes; elas são pequenas e
sintéticas, não uma prova de desempenho com usuários reais.

## De onde vieram as respostas

1. **201 exemplos educativos:** três perguntas diferentes para cada um dos
   **67 conteúdos da base atual**. As respostas foram redigidas por IA em
   português com acentuação, apoiadas nos resumos existentes e com os IDs das
   fontes preservados. Os textos originais da base não foram alterados.
2. **190 exemplos de conversa:** 95 situações do produto, com duas formas de
   perguntar por situação. Há mudanças de treino e refeições, esclarecimentos,
   registros, confirmação, rejeição, adiamento, correções, preferências,
   histórico, limitações de imagem, privacidade e segurança.

As duas redações de uma situação são variações da mesma família, não duas
evidências independentes. As 30 conversas com histórico contêm uma interação
anterior e uma resposta final; as outras 361 são pares simples de pergunta e
resposta, além da instrução de sistema.

São alvos preparados por IA, não respostas certificadas por revisão clínica ou
por anotadores humanos independentes. A ligação a uma fonte sustenta o tema e
seus limites; não significa que cada frase nova tenha sido validada por ela.

## O que aconteceu com os dados antigos

Foram inventariados os **12.179 registros do NLP 1.8.0** e os **6.711 documentos
do corpus 1.2.0**, totalizando 18.890 entradas no inventário privado.

Os registros atuais do NLP contêm texto, contexto e rótulos, mas não uma resposta
curada do Coach para cada pergunta. Seus rótulos não foram transformados em
respostas, e comentários de fóruns não foram promovidos a respostas corretas.
O corpus do TinyLM contém prosa e mensagens isoladas; não foi reinterpretado
automaticamente como conversa instrucional.

O inventário registra o destino de cada entrada, sem copiar os textos antigos
para o SFT. Isso preserva o aproveitamento já feito no NLP/corpus e identifica o
material que ainda precisaria de uma resposta adequada para uma expansão futura.
As fontes, divisões e avaliações anteriores permanecem intactas.

## Formato de conversa

Cada exemplo contém mensagens estruturadas:

```json
{
  "messages": [
    {"role": "system", "content": "Instrução do Coach..."},
    {"role": "user", "content": "O que quer dizer 3 × 8?"},
    {"role": "assistant", "content": "Três séries de oito repetições..."}
  ]
}
```

Os metadados ficam separados: ID, família, partição, intenção, riscos, fonte,
origem da resposta e status de revisão. **Rótulos e IDs de fonte não são
acrescentados como resposta oculta ou informação privilegiada ao prompt.**

Quando há contexto de calendário ou plano, ele aparece explicitamente como
informação simulada fornecida pelo aplicativo. Isso evita ensinar que o modelo
conhece um calendário real que não recebeu.

## Como viram dados de treino

```text
Conversa estruturada
→ template de chat original do Qwen
→ IDs de tokens
→ input_ids + attention_mask + labels
→ futuro treinamento LoRA
```

A preparação aplica o template completo sem `add_generation_prompt`; aplica
separadamente o prefixo da última resposta com `add_generation_prompt=True`
e verifica que os IDs são um prefixo exato. A loss recebe apenas os tokens da
**última resposta do assistant e seu encerramento no template**.

- Instrução de sistema, mensagens do usuário e respostas anteriores: label -100.
- Resposta final e terminador: label igual ao ID correspondente da entrada.
- Preenchimento de um lote: attention_mask 0 e label -100.

**Não deslocamos labels manualmente:** o modelo causal do Transformers faz o
deslocamento interno. Isso difere do Dataset do TinyLM, que preparava X/y já
deslocados e usava uma implementação própria da loss.

O limite configurado é de **1.024 tokens por conversa inteira**. Um exemplo que
ultrapasse o limite é excluído por inteiro e registrado, em vez de cortar a
resposta silenciosamente. Nesta versão, o máximo observado foi 275 tokens e
nenhum dos 391 candidatos foi excluído ou truncado.

## Separação e auditoria

As famílias autorais são mantidas inteiras. Também são unidas famílias com
prompt exato igual, resposta exata igual ou alta sobreposição de sequências de
cinco palavras (Jaccard ≥ 0,8). Foram encontrados zero vínculos adicionais por
esse último detector, além das famílias já declaradas.

A divisão usa seed 42, domínio e presença de histórico, com objetivo inicial
80/10/10 por famílias. Uma família única necessária para cobrir uma intenção
ou risco permanece no treino. Por isso a proporção final em exemplos ficou
aproximadamente **85,7% / 7,2% / 7,2%**. Não separam-se paráfrases de uma mesma
situação só para preencher uma classe em validação ou teste.

Controles aprovados:

- zero famílias compartilhadas entre treino, validação e teste;
- zero prompts ou respostas finais exatamente iguais entre partições;
- zero correspondências exatas com textos históricos não destinados ao treino;
- alternância válida de papéis e respostas finais presentes;
- nenhuma correspondência aos padrões declarados de identificadores diretos;
- rejeição de tokens de controle literais em conteúdo comum;
- todos os alvos contêm o encerramento esperado da resposta;
- hashes das fontes preservados e das saídas registrados.

O detector de duplicatas não reconhece toda paráfrase ou semelhança conceitual.
A triagem de identificadores também não prova anonimato; neste conjunto, os
exemplos novos são sintéticos e não reproduzem dados pessoais coletados.
Há conteúdo e estilo compartilhados da base do projeto: o teste sintético não
é uma avaliação independente de conhecimento ou generalização real.

O carregador exige `allow_test=True` para abrir o teste reservado, tornando o uso
na avaliação final explícito. É um cuidado de processo, não um controle de acesso
que impeça alguém de ler o arquivo diretamente.

## Onde está cada parte

| Caminho relativo à raiz do projeto | Função |
| --- | --- |
| `ai/data/sft_sources/v1/knowledge_prompts.json` | Perguntas educativas novas, agrupadas por conteúdo. |
| `ai/data/sft_sources/v1/knowledge_answers.json` | Respostas educativas redigidas a partir da base existente. |
| `ai/data/sft_sources/v1/scenarios.json` | Situações de conversa, contexto, histórico e respostas. |
| `ai/configs/openlm.data.v1.json` | Versão, seed, proporções, limite e regra da loss. |
| `ai/src/evolv_openlm/sft_data.py` | Monta, audita, agrupa, divide e tokeniza. |
| `ai/src/evolv_openlm/sft_dataset.py` | Dataset com conferência de hash e collator com padding dinâmico. |
| `ai/scripts/prepare_openlm_data.py` | Comando de preparação, sem pesos do modelo. |
| `ai/data/sft/1.0.0/private/train.jsonl` | Conversas e metadados de treino. |
| `ai/data/sft/1.0.0/private/validation.jsonl` | Conversas e metadados de validação. |
| `ai/data/sft/1.0.0/private/test.jsonl` | Conversas e metadados do teste reservado. |
| `ai/data/sft/1.0.0/private/*_tokens.jsonl` | IDs, máscara de atenção e labels prontos. |
| `ai/data/sft/1.0.0/private/source_inventory.jsonl` | Destino de todos os registros históricos examinados. |
| `ai/data/sft/1.0.0/private/excluded.jsonl` | Contabilidade de exclusões; vazio nesta versão. |
| `ai/data/sft/1.0.0/report.json` | Contagens, cobertura e limitações. |
| `ai/data/sft/1.0.0/manifest.json` | Hashes das fontes, do tokenizador, código e saídas. |

Os JSONL preparados ficam ignorados pelo Git. As fontes sintéticas e os relatórios
permitem inspecionar a receita, e a revisão fixa do tokenizador permite reproduzir
os IDs. Uma versão publicada não deve ser sobrescrita para fazer um experimento.

## Uso na próxima fase

Com o ambiente Python apropriado, na raiz do projeto:

```powershell
python ai/scripts/prepare_openlm_data.py --output ai/data/sft/nova-versao
```

O comando utiliza apenas o tokenizador em cache e rejeita pastas já existentes.
Não baixa o modelo, não inicia fine-tuning e não altera o NLP ou o app.

Exemplo de carregamento para o futuro treinador:

```python
from evolv_openlm.sft_dataset import SFTDataset, SFTCollator

train = SFTDataset(release_dir, "train")
validation = SFTDataset(release_dir, "validation")
collator = SFTCollator(tokenizer.pad_token_id or tokenizer.eos_token_id)
```

A etapa seguinte, 7.04.3, configura LoRA/QLoRA. A geração e o backward do modelo
de 4B ainda dependem de completar os pesos da 7.04.1. Preparar estes dados não
resolve a lentidão daquele download nem demonstra que o ajuste caberá na GPU.

Este conjunto é uma **semente pequena de adaptação de comportamento**, com 19.259
tokens-alvo no treino, não uma expansão de pré-treinamento. Não se deve prometer
que ele fará o modelo melhorar: isso será decidido comparando original e adaptado
na 7.04.5. Dados variados de conversas reais com respostas adequadas serão uma
expansão útil, preservando um teste independente e a finalidade autorizada.

## Verificação

Doze testes de SFT passaram, cobrindo máscara do último turno, ausência de duplo
deslocamento, padding, exclusão por tamanho, identificadores, tokens de controle,
grupos, divisão reproduzível, classes raras no treino, acesso explícito ao teste
e integridade dos arquivos. Esses testes verificam a preparação, não a qualidade
clínica ou conversacional de um modelo treinado.

## Referências

- [Hugging Face: formatos para SFT](https://huggingface.co/docs/trl/sft_trainer).
- [Hugging Face: templates de chat](https://huggingface.co/docs/transformers/chat_templating).
- As fontes de cada conteúdo já estão no catálogo `ai/data/metadata/sources.v1.json`.
- [NHS: lesões e sinais que exigem avaliação](https://www.nhs.uk/conditions/sprains-and-strains/).
- [NHS: sinais de reação alérgica grave](https://www.nhs.uk/conditions/anaphylaxis/).

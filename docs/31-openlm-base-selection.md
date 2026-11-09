# 7.04.1 — Escolha do modelo aberto

Atualização posterior, na **7.04.4**: o checkpoint oficial terminou de baixar,
os hashes foram conferidos e o Qwen3-4B foi carregado e ajustado na RTX 5050.
Foram concluídas três épocas e 63 updates, com pico alocado de 4.545,68 MiB.
A verificação está em `ai/artifacts/openlm/1.0.0/verification_7.04.4.json`.
As notas de download pendente abaixo descrevem o estado da seleção inicial.

## Decisão

Modelo selecionado: **Qwen/Qwen3-4B-Instruct-2507**, revisão
`cdbee75f17c01a7cc42f958dc650907174af0554`, licença Apache-2.0.

O candidato é um Transformer causal já pré-treinado e preparado para seguir
instruções. A etapa adapta um modelo existente ao Evolv; o TinyLM de 3,4 milhões
de parâmetros permanece um experimento didático separado.

Carregamento: pesos lineares em **NF4 de 4 bits**, quantização dupla e cálculo
em **bfloat16**, com bitsandbytes. A adaptação prevista usa **QLoRA**: modelo
quantizado congelado mais pequenos adaptadores treináveis. A configuração final
dos adaptadores pertence à 7.04.3.

Esta escolha prioriza uma arquitetura textual densa, integração com Transformers
e PEFT e respostas diretas. Não estabelece que seja o melhor modelo disponível
em todos os benchmarks, nem que seja o modelo definitivo de um produto lançado.

## Computador observado

- Windows x64; Python 3.12.14.
- NVIDIA GeForce RTX 5050 Laptop GPU, 8.151 MiB de VRAM reportados pelo driver.
- Aproximadamente 15,71 GiB de RAM física utilizável.
- PyTorch 2.11.0+cu128, CUDA disponível e suporte a BF16.
- Aproximadamente 700 GiB livres em disco na inspeção inicial.

Apenas cerca de 2,84 GiB de RAM estavam disponíveis na primeira leitura; memória
livre varia com os programas abertos. Para treinar, fechar programas pesados ajuda
a evitar paginação. **Carregamento e backward ainda não foram executados:** o
download medido ficou em cerca de 0,24 MB/s. A seleção é técnica e a viabilidade
real de geração/treinamento permanece pendente de completar os pesos.

## Candidatos consultados

| Modelo | Papel nesta seleção | Considerações |
| --- | --- | --- |
| Qwen3-4B-Instruct-2507 | Escolhido para verificação local | Textual, 4B, respostas diretas, integração densa conhecida; exige quantização para deixar espaço ao ajuste na GPU de 8 GB. |
| Qwen3-1.7B | Alternativa menor | Menor custo de memória; tem modos de raciocínio e resposta direta. Usar se a configuração escolhida não couber em experimentos futuros. |
| Qwen3.5-2B | Alternativa recente | Tem arquitetura híbrida e componente de visão; é atraente para novos experimentos, mas envolve um caminho de execução diferente do Transformer textual denso desta etapa. |

Os dois candidatos alternativos foram consultados na documentação oficial;
**não foram baixados nem comparados experimentalmente**. A escolha não usa
resultados dos testes reservados do NLP ou do TinyLM.

## Limites locais

Apesar do contexto máximo anunciado pelo fabricante, o runtime local limita
entradas a **2.048 tokens** e saídas a **256 tokens**. Isso contém o custo de
memória nesta máquina. O ensaio de memória para adaptação utiliza um lote de
uma sequência com até 1.024 tokens e checkpointing de gradientes.

O tokenizador é **o tokenizador original do Qwen**, na mesma revisão dos pesos.
O BPE de 8.192 tokens do TinyLM não pode substituir esse tokenizador sem mudar
o significado das entradas e das saídas dos pesos pré-treinados.

Os arquivos oficiais de pesos somam **8.044.982.000 bytes** (cerca de 7,49 GiB).
O download conserva os safetensors originais; a quantização ocorre no carregamento.
Assim, tamanho de download, tamanho em disco e uso de VRAM são medidas diferentes.

## Organização

| Caminho relativo à raiz do projeto | Função |
| --- | --- |
| `ai/configs/openlm.v1.json` | Modelo, revisão fixa, quantização, limites e instrução inicial experimental. |
| `ai/requirements.openlm.txt` | Versões verificadas das dependências. |
| `ai/src/evolv_openlm/runtime.py` | Carrega pesos/tokenizador e gera a resposta, usando a GPU. |
| `ai/scripts/inspect_openlm.py` | Baixa arquivos autorizados, mede geração e, opcionalmente, backward LoRA sem atualização. |
| `ai/scripts/chat_openlm.py` | Chat no terminal ou uma pergunta isolada. |
| `ai/artifacts/openlm/1.0.0/download_manifest.json` | Hashes e tamanhos dos arquivos oficiais recebidos. |
| `ai/artifacts/openlm/1.0.0/smoke_report.json` | Hardware, versões, tempo, memória e resultado do diagnóstico. |
| `ai/artifacts/openlm/1.0.0/private/samples.json` | Respostas completas das sondas escritas para esta etapa. |

Cache padrão fora do OneDrive: `~/Documents/Codex/models/evolv-openlm`.
Pode ser alterado por `--cache-dir` ou, no chat, `EVOLV_MODEL_CACHE`.
Os caminhos específicos da máquina ficam em `private/local_paths.json`.
Os pesos não são incluídos no Git; o cache externo não faz parte do repositório.
`download_manifest.json`, `smoke_report.json` e `private/samples.json` são saídas
**futuras** do diagnóstico completo e ainda não existem nesta seleção.
`selection.json` registra a decisão, hardware, revisões e pendências atuais.

## Como experimentar

No terminal, na raiz do projeto e com as dependências instaladas:

```powershell
python ai/scripts/chat_openlm.py
```

Comandos da conversa: `/sair` e `/limpar`. O histórico permanece somente em memória
durante aquela execução. Cada resposta recebe as mensagens anteriores da sessão.
Se exceder o limite de entrada, o programa pede para reiniciar a conversa; não
descarta silenciosamente as mensagens antigas.

Pergunta isolada:

```powershell
python ai/scripts/chat_openlm.py "Qual a diferença entre séries e repetições?"
```

Após o primeiro download, o chat usa arquivos locais por padrão. `--download`
autoriza completar o cache buscando a mesma revisão fixa no Hugging Face.
Nenhuma mensagem do chat é enviada a uma API de geração externa.

O download inicial pode ser feito por:

```powershell
python ai/scripts/inspect_openlm.py --download --check-backward
```

Se o transporte do Hub ficar parado, a alternativa abaixo usa faixas HTTP de
4 MiB, guarda os parciais e confere tamanho e hash oficiais antes de promover
cada arquivo. Ela também executa o diagnóstico depois de completar o download:

```powershell
python ai/scripts/inspect_openlm.py --http-download --check-backward
```

Na inspeção de 02/11, interrompemos a transferência integral devido à lentidão;
arquivos parciais foram preservados. A primeira geração só pode ser testada
depois de terminar esse download. Estimativas de memória não substituem o
diagnóstico real, principalmente para o backward QLoRA.

Para repetir a inspeção em uma nova pasta de saída:

```powershell
python ai/scripts/inspect_openlm.py --check-backward --output ai/artifacts/openlm/nova-inspecao
```

O script rejeita um relatório já existente. O teste opcional de backward calcula
gradientes em texto artificial para verificar compatibilidade e memória; não cria
otimizador, não dá passos de treino e não salva um adaptador treinado.

## Interpretação e próximos passos

Responder a algumas sondas verifica execução e permite observar linguagem e
comportamento. Isso não demonstra segurança clínica, precisão factual, atendimento
confiável de todas as intenções ou superioridade sobre os outros candidatos.
Uma instrução inicial orienta o modelo, mas não garante cumprimento.

Este chat é um experimento local. Ele não está conectado ao NLP, RAG, Planner,
backend nem aos dados reais do usuário. Um pedido de mudança pode produzir uma
proposta em texto, sem executar alterações no aplicativo.

A fase 7.04.2 prepara conversas e respostas adequadas à adaptação e suas divisões
de avaliação. A 7.04.3 define LoRA; a 7.04.4 treina; a 7.04.5 compara o original
com o adaptado usando um protocolo congelado. As métricas do TinyLM não são
diretamente comparáveis sem igualar tokenização, textos e método de avaliação.

## Fontes oficiais consultadas em 02/11/2026

- [Qwen3-4B-Instruct-2507: cartão e licença](https://huggingface.co/Qwen/Qwen3-4B-Instruct-2507).
- [Qwen3-1.7B](https://huggingface.co/Qwen/Qwen3-1.7B).
- [Qwen3.5-2B](https://huggingface.co/Qwen/Qwen3.5-2B).
- [Instalação bitsandbytes e suporte CUDA/Windows](https://huggingface.co/docs/bitsandbytes/main/en/installation).
- [Quantização no Transformers](https://huggingface.co/docs/transformers/main/en/quantization/bitsandbytes).
- [PEFT e preparação para QLoRA](https://huggingface.co/docs/peft/main/en/developer_guides/quantization).

# Dataset revisado 1.7.0

Quatro planilhas importadas, sem modificar os arquivos fornecidos: **12.179 mensagens**.
As celulas atuais da aba `Revisao` definem texto, contexto e rotulos. Os JSONL
auxiliares fornecem proveniencia, nao substituem as correcoes do Excel.

| Uso | Mensagens | Observacao |
| --- | ---: | --- |
| Treino | 9.261 | Publicos no treino original + simulados elegiveis |
| Validacao | 913 | Escolha de arquitetura, regularizacao e limites |
| Teste | 955 | Apenas depois de congelar os dois modelos |
| Pesquisa externa reservada | 255 | Linguagem recebida de pessoas, assistencia de IA desconhecida |
| Desafio e revisao (`quarantine`) | 795 | Duvidas, derivacoes de fontes reservadas e conflitos de isolamento |
| **Total preservado** | **12.179** | Nenhuma mensagem descartada |

Os 1.480 exemplos da quarta planilha ficam somente no treino. Os 21 exemplos
recebidos do Coach e seus 120 derivados sinteticos nunca entram em treino:
compartilham um grupo de origem e precisam permanecer reservados. Os derivados
ficam em `quarantine`, nao se apresentam como teste humano independente.

Os 795 casos nao sao todos dados ruins. A separacao preserva a incerteza e evita
usar variacoes de um exemplo reservado para ensinar a resposta do proprio teste.
Eles tambem recebem previsoes e extracoes, mas nao entram na metrica principal.
Intencoes `INDEFINIDA` e riscos `INDEFINIDO` nao viram classes artificiais.

## Taxonomia

- 60 intencoes principais; intencoes secundarias preservadas separadamente.
- 21 rotulos de risco: 20 sinais positivos independentes e `none` exclusivo.
- 89 entidades declaradas; as planilhas nao fornecem anotacao de spans/valores.
- Limites finais em `taxonomy.json`, incluindo preservacao de restricoes,
  adiamento, contexto de medicamentos e diferenca entre criar/adaptar planos.

Rotulos revisados por IA continuam **referencia de IA**, nao gabarito humano.
O suporte de cada classe aparece no manifesto e nos relatorios dos modelos.
Classe sem exemplo no teste nao tem desempenho independente demonstrado.

## Privacidade e Rastreabilidade

Conteudo e contexto minimizados ficam em `private/`, ignorado pelo Git.
E-mails, telefones, URLs, identificadores e alguns nomes declarados sao mascarados
antes das features; isso nao comprova anonimato. Conversas nao sao enviadas a APIs.
A autorizacao do proprietario do projeto permite a experiencia solicitada, mas
nao certifica direitos de terceiros ou libera redistribuicao/publicacao.
Gitignore nao impede sincronizacao pelo OneDrive; o repositorio continua nele.
Dados de saude e relatos identificaveis exigem revisao especifica antes de uso comercial.

Hashes dos quatro Excel, snapshots e arquivos privados constam de `manifest.json`.
Duplicatas exatas, grupos e quase duplicatas por shingles sao auditados; essa busca
nao prova ausencia de vazamento semantico. Divisoes publicas originais e conjuntos
historicos congelados foram preservados. Reimportacao exige nova versao.

Este dataset alimenta NLU. Respostas de foruns e rotulos de IA nao foram convertidos
em conhecimento cientifico aprovado nem em corpus de respostas para o TinyLM.

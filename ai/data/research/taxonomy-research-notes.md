# Pesquisa para a taxonomia 7.01.1

## Objetivo

Esta pesquisa serve para descobrir como pessoas reais formulam perguntas e
pedidos. Ela nao transforma comentarios de internet em verdade tecnica e nao
autoriza copiar conversas para o dataset.

## Principais conclusoes

1. **Intencao e assunto precisam ser separados.** A mesma pessoa pode querer
   aprender sobre cutting, mudar para cutting ou avaliar um plateau no cutting.
2. **Mensagens reais sao contextuais.** Expressoes como `isso`, `o outro`,
   `serve?` e `faz amanha` exigem memoria curta ou esclarecimento.
3. **Uma mensagem pode ter varios eixos.** Ha intencao principal, topicos,
   entidades, risco, dependencia de contexto e capacidade solicitada.
4. **Usuarios misturam explicacao e acao.** O Coach deve responder a duvida e
   separar qualquer alteracao em uma previa confirmavel.
5. **Detalhes perifericos importam.** Perguntas longas podem conter historia,
   objetivo e receio antes do pedido real; o NLP precisa identificar o foco.
6. **Seguranca nao pode depender da intencao.** Dor, alergia, transtorno
   alimentar, emergencia ou contexto clinico sao classificados em paralelo.
7. **Forum nao e base de conhecimento.** Ele ajuda a encontrar temas e
   linguagem, enquanto fatos devem vir de fontes tecnicas revisadas.

## Cobertura descoberta em conversas e foruns

- treino: frequencia, duracao, divisao, volume, carga, progressao, plateau,
  descanso, falta de tempo, treino perdido, equipamento e execucao;
- dieta: porcao, substituicao, bulking, cutting, refeicao flexivel, fome,
  cardapio variado, preparo, armazenamento, restaurante e suplementos;
- recuperacao: sono, dor muscular, fadiga, estresse e medo de perder resultado;
- comportamento: aderencia, culpa, desanimo e preferencia por alimentos reais;
- dialogo: erros de digitacao, mensagens curtas, imagens e continuacoes.

## Decisao de modelagem

A taxonomia nao cria uma intencao para cada topico. Um classificador pequeno
teria poucas amostras por classe e confundiria rotulos muito parecidos. O Evolv
usa camadas:

```txt
mensagem
  -> risco(s)
  -> intencao principal e secundaria(s)
  -> topico(s)
  -> entidades e negacoes
  -> capacidade solicitada
  -> resposta, esclarecimento ou previa do Planner
```

## Politica de dados

- Conversa privada: apenas padroes anonimos; URL e texto nao ficam no repo.
- Forum: descoberta de cobertura; sem copiar posts ou respostas.
- Dataset externo: somente depois de auditar licenca, proveniencia, duplicatas,
  privacidade, idioma, qualidade e compatibilidade com o escopo.
- Exemplos proprios: escritos do zero, revisados e versionados.
- Conhecimento: separado dos exemplos de classificacao e apoiado por fontes
  tecnicas apropriadas.

## Pontos para a fase 7.01.2

- transformar as regras de anotacao em esquema de dados;
- criar exemplos multilabel para topicos e riscos;
- incluir frases faceis, ambiguas, negativas e adversariais;
- registrar origem e consentimento por exemplo;
- revisar equilibrio de classes e concordancia entre anotadores;
- congelar um conjunto de teste antes do treinamento.

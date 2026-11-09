# Evolv Mobile

Aplicativo React Native criado com Expo e TypeScript.

## Coach conectado — 7.06.4

A tela do Coach usa NestJS com a sessão autenticada: histórico persistido,
envio de mensagens, respostas do serviço, fontes e prévias do Planner.
Alterações exigem revisão e confirmação separadas. A tela permite renomear
e excluir conversas, repetir falhas sem duplicar o pedido e consultar o
histórico. Não há resposta simulada de substituição nesta tela.

Configuração e limites: [integração do Coach](../docs/44-coach-mobile-integration.md).
Passaram TypeScript, lint, 33 testes Mobile e 16 checks da interface web
com rede fictícia. A conferência nativa no iPhone fica na avaliação final.

Na 7.06.5, a interface web também foi exercitada com backend, Supabase e Coach
reais, incluindo histórico e confirmação/desfazer pelo Planner. O link direto
de prévia passou a aguardar a restauração do login. O iPhone físico ainda
não foi testado. [Resultados e limites](../docs/45-coach-system-evaluation.md).

## Comandos

```bash
npm install
npm start
npm run web
npm run typecheck
npm run lint
```

## Estrutura

- `src/app`: rotas e telas com Expo Router.
- `src/components`: componentes visuais reutilizáveis.
- `src/constants`: tema e tokens de interface.
- `src/data`: dados simulados usados na fase 4.
- `src/types`: contratos TypeScript do aplicativo.

## Direção visual

- mesma linguagem visual da entrada em todas as telas: tipografia de sistema,
  pesos moderados, hierarquia clara e controles discretos;
- temas em branco e cinza neutro ou preto e grafite, com vermelho nas ações;
- fotografias preservadas, com títulos menores e sem excesso de caixa alta;
- telas de uso frequente com menos decoração e leitura rápida;
- entrada em uma coluna no celular e foto ao lado do formulário no desktop;
- dez fotografias reais locais na entrada desktop, alternadas a cada abertura,
  sem mudança durante a digitação ou a troca entre entrar e criar conta.

As imagens editoriais de treino, alimentação, Coach, conta e progresso foram geradas especificamente para o projeto e ficam em `assets/images`. Cada situação importante possui uma imagem própria, incluindo peito, pernas, ombros, full body, recuperação, preparo de refeições e substituição alimentar.

## Base de layout

- o dashboard nutricional adapta a estrutura aberta do [Akilo](https://github.com/dutta-sujoy/Akilo), licenciado sob MIT;
- os controles seguem padrões estudados no [React Native Reusables](https://reactnativereusables.com/docs);
- fluxos de aplicativos consolidados foram pesquisados no [Mobbin](https://mobbin.com/), sem copiar ou distribuir telas proprietárias.

Os avisos e a licença da base aberta utilizada estão em `THIRD_PARTY_NOTICES.md`.

Os dados de exemplo em src/data continuam úteis para sugestões e composição
visual. Mensagens do Coach são obtidas pelo backend; NestJS e FastAPI precisam
estar configurados e em execução para responder.

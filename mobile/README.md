# Evolv Mobile

Aplicativo React Native criado com Expo e TypeScript.

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

Nesta fase, o app usa dados locais simulados. A integração com NestJS e Supabase pertence à fase seguinte.

# Evolv - Aplicativo mobile

## Status

A base visual e navegável do aplicativo foi implementada com React Native, Expo, Expo Router e TypeScript.

A fase esta quase concluida. Falta apenas validar a experiencia em um iPhone fisico; essa verificacao foi adiada sem bloquear o inicio do backend.

As telas principais agora consultam o backend NestJS com uma sessão real do Supabase Auth. O Coach continua simulado até a fase de NLP, e estados vazios aparecem quando o usuário ainda não possui plano.

## O que foi implementado

- projeto Expo configurado com TypeScript;
- navegação com Expo Router;
- tema visual centralizado;
- componentes reutilizáveis;
- biblioteca editorial original para treino, dieta, Coach, conta e progresso;
- cinco abas principais: Hoje, Treino, Coach, Dieta e Conta;
- tela de progresso acessada por Conta;
- Conta organizada com progresso, plano, acessos essenciais e histórico;
- Configurações em uma tela separada, acessada pela engrenagem da Conta;
- aparência em uma área interna de Configurações, somente com os modos claro e escuro;
- preferência de aparência mantida até o usuário alterá-la novamente;
- catálogo combinável de modalidades, recursos e focos de treino;
- entrada e cadastro reais por e-mail, com Google e Apple preparados visualmente para ativação futura no Supabase;
- onboarding completo, opcional e pulável;
- dados reais separados da camada visual por serviços e contextos;
- interação de cargas com aumento e redução;
- sugestão visual da próxima carga;
- conversa simulada com o Coach;
- registro opcional de refeições;
- navegação entre os fluxos principais;
- suporte inicial para web, iOS e Android pela mesma base React Native.

## Direção visual aplicada

O aplicativo combina dois tipos de tela:

- telas editoriais, com fotografia cinematográfica e títulos fortes para criar identidade;
- telas operacionais, com listas compactas, divisores e controles simples para uso rápido.

Essa mistura evita tanto uma interface genérica de cards quanto uma experiência decorativa demais para ser usada durante o treino.

## Refinamento de ergonomia

A navegação foi refinada após pesquisa do sistema visual do Instagram, sem copiar sua marca ou transformar o Evolv em uma rede social. Foram aproveitados princípios de uso:

- fonte nativa do sistema para textos operacionais;
- escala compacta de 14 px para títulos de linha e 12 px para informações secundárias;
- espaçamento baseado principalmente em 8 e 16 px;
- cinco destinos principais na barra inferior;
- ícones contornados com traço próximo de 1,8 px;
- resposta visual curta, de aproximadamente 180 ms, ao mudar de aba;
- cor de destaque reservada para estado ativo e ações importantes;
- sombras mais leves para o conteúdo continuar sendo o foco.

Referências consultadas:

- [Meta Design - evolução visual do Instagram](https://www.meta.com/design-at-meta/blog/behind-instagrams-brand-evolution-movement-inclusivity-and-a-new-purpose/);
- [Instagram iOS design reference](https://code.jiangshu.ai/awesome-design-html/assets/ios/design.instagram-ios.html), referência independente baseada no aplicativo público e não afiliada à Meta.

## Referências e componentes abertos

O painel nutricional usa como base estrutural o dashboard do projeto open-source Akilo, licenciado sob MIT. A adaptação preserva o círculo de calorias e a leitura rápida de metas, mas aplica a paleta, a fotografia e a hierarquia visual do Evolv.

React Native Reusables foi estudado para padrões de controles. Mobbin foi usado somente como pesquisa de fluxos e ergonomia de aplicativos consolidados. As atribuições estão registradas em `mobile/THIRD_PARTY_NOTICES.md`.

## Decisões do produto preservadas

- Hoje apenas resume o dia e não obriga o usuário a confirmar se vai treinar.
- O usuário conversa com o Coach somente quando quiser.
- Existe um único Coach para treino, dieta, rotina, dúvidas e explicações.
- O treino permite registrar cargas sem exigir um diário completo.
- Dieta e treino funcionam como áreas independentes.
- Progresso fica dentro de Conta e não ocupa uma aba principal.
- Aparência não fica exposta na página principal da Conta.
- O tema não acompanha automaticamente o sistema: somente muda quando o usuário escolhe claro ou escuro.
- O plano aceita uma modalidade isolada ou combinações, como máquinas com cardio ou calistenia com corrida.
- O catálogo de treino cobre academia, peso livre, cabos, calistenia, elásticos, funcional, cardio, esportes, mobilidade e diferentes focos físicos.
- O onboarding apresenta o produto completo, mas todas as respostas podem ser puladas.

## Imagens do aplicativo

- A biblioteca visual possui 72 imagens locais para treino, dieta, Coach, Conta e progresso.
- Dieta, Coach e Conta possuem 10 opções próprias cada, sem depender de imagens repetidas entre essas áreas.
- As imagens mudam de forma determinística a cada semana, sem depender de internet.
- Hoje e Treino usam posições diferentes da mesma categoria para não repetir a mesma foto no mesmo dia.
- A preferência opcional fica em `Conta > Configurações > Imagens do app`.
- O padrão varia as pessoas automaticamente. Como opção, o usuário pode priorizar homens ou mulheres e escolher entre físico fitness, musculoso ou variado.
- Tons de pele, cabelos, idades e cenas são variados automaticamente pelo catálogo, sem qualquer escolha de etnia.
- Quando uma preferência deixaria poucas opções, a seleção é ampliada para preservar variedade.

As imagens desta fase ficam no pacote local do app. Quando houver conteúdo remoto, o mesmo catálogo poderá guardar metadados no Supabase e arquivos no Supabase Storage sem alterar a regra de seleção.

## Estrutura principal

```txt
mobile/
  src/
    app/              rotas e telas
      (tabs)/         cinco abas principais
      login.tsx       entrada e cadastro
      onboarding.tsx  configuração inicial opcional
      progress.tsx    progresso acessado por Conta
      settings.tsx    configurações gerais da Conta
      appearance.tsx  escolha persistente entre claro e escuro
      image-preferences.tsx  preferências opcionais das imagens
      training-preferences.tsx  modalidades e focos combináveis
    components/       componentes visuais reutilizáveis
    constants/        cores, espaçamentos e tipografia
    config/           leitura das variaveis publicas de ambiente
    data/             catalogos visuais e conversao dos dados da API
      image-library.ts catálogo e rotação semanal de imagens
    context/          sessao, dados reais, tema e preferencias
    lib/              cliente Supabase do aplicativo
    services/         comunicacao tipada com o backend NestJS
    types/            tipos visuais e contratos da API
  assets/             ícones e imagens do aplicativo
  package.json        dependências e comandos
  app.json            configuração do Expo
```

## Como executar

Dentro da pasta `mobile`:

```powershell
npm install
npm run start
```

Para abrir a versão web:

```powershell
npm run web
```

Antes de iniciar, crie `mobile/.env.local` a partir de `.env.example` e preencha:

```txt
EXPO_PUBLIC_SUPABASE_URL=https://seu-projeto.supabase.co
EXPO_PUBLIC_SUPABASE_ANON_KEY=chave-publica-anon
EXPO_PUBLIC_API_URL=http://localhost:3000/api
```

Somente valores publicos usam o prefixo `EXPO_PUBLIC_`. Chaves secretas nunca entram no aplicativo.

Os testes em um iPhone físico serão feitos depois. Isso não impede o desenvolvimento do repositório e das telas.

## Verificações realizadas

- TypeScript sem erros com `npm run typecheck`;
- ESLint sem erros com `npm run lint`;
- Expo Doctor com 21 de 21 verificações aprovadas;
- exportação web concluída;
- navegação manual entre as cinco abas;
- login e cadastro por e-mail ligados ao Supabase Auth;
- sessao persistente e abas protegidas;
- token enviado automaticamente ao backend NestJS;
- onboarding salvando objetivo e estado no banco;
- telas Hoje, Treino, Dieta, Conta e Progresso lendo a API;
- cargas, refeições e peso gravados por rotas autenticadas;
- abertura de Progresso por Conta;
- abertura de Configurações e Aparência por Conta;
- troca persistente entre os temas claro e escuro;
- seleção combinável de modalidades e focos de treino;
- edição real de carga quando houver plano ativo;
- envio simulado de mensagem ao Coach;
- registro real de refeições quando houver plano ativo.

## Limite atual

Coach continua visual porque o servico local de NLP pertence a uma fase posterior. Imagens e preferencias locais continuam no aparelho. Sem um plano criado, as telas mostram estados vazios em vez de apresentar dados simulados como se fossem do usuario.

## Próximo passo

Iniciar o Planner sem IA. A validacao completa em um iPhone sera feita depois, durante a etapa de qualidade do aplicativo.

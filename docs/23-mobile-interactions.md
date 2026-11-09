# Interacoes de navegacao e rolagem

## Escopo

Aplicado as cinco abas principais: Hoje, Treino, Coach, Dieta e Conta. Fotos,
paleta, conteudo e organizacao das telas foram preservados. Nenhuma regra do
Planner, treinamento de IA ou autenticacao foi alterada por esta entrega.

## Comportamentos

- O titulo grande acompanha a rolagem e da lugar a uma barra compacta fixa.
- As acoes do cabecalho continuam disponiveis na barra compacta.
- A barra de rolagem lateral passa a ser visivel, conforme a plataforma.
- Tocar novamente na aba ativa retorna ao topo; alternar abas preserva a posicao.
- A selecao da barra inferior desliza entre as abas, com animacao de mola.
- Botoes, seletores e linhas acionaveis das abas recebem resposta de pressao.
- A entrada da pagina e animada quando ela recebe foco.
- O tema dos navegadores acompanha o tema do app, evitando fundo claro nas transicoes.
- A preferencia de reduzir movimento e respeitada no dispositivo e no navegador.
- Cabecalhos invisiveis sao retirados da navegacao acessivel e seus botoes desabilitados.

## Arquivos

- `mobile/src/components/ui.tsx`: AppScreen e PageHeader; medicao, rolagem e barra compacta.
- `mobile/src/components/touch-feedback.tsx`: feedback sem wrappers que mudem o layout.
- `mobile/src/context/motion-context.tsx`: preferencia de movimento e limpeza das assinaturas.
- `mobile/src/lib/screen-motion.ts`: limites calculados a partir da altura real do titulo.
- `mobile/src/app/(tabs)/_layout.tsx`: indicador animado e eventos de navegacao das abas.
- `mobile/src/app/_layout.tsx`: provedores de movimento e de tema da navegacao.
- `mobile/tests/screen-motion.test.cjs`: limites, overscroll e altura de texto maior.
- `mobile/tests/touch-feedback.test.cjs`: eventos, estilos, acessibilidade e reducao de movimento.

Para usar o cabecalho recolhivel em outra tela, passar o PageHeader pelo slot
`header` de AppScreen. As telas que mantem o cabecalho como filho continuam
funcionando, mas nao recebem a barra compacta automaticamente.

## Verificacao

- Suite mobile: 20 testes aprovados, incluindo os testes anteriores de cadastro e fotos.
- TypeScript sem erros; ESLint direcionado aos arquivos alterados sem erros.
- Conferencia no navegador em larguras de 320, 390 e 1280 pixels.
- Verificados: recolhimento dos titulos, retorno ao topo, preservacao da rolagem,
  selecao dos dias do treino e envio de mensagem simulada do Coach.

## Limites da conferencia

O Supabase nao respondeu durante a tentativa autorizada de criar uma conta de
teste. O cadastro nao foi confirmado e a conta pessoal nao foi modificada.
As verificacoes visuais usaram uma previa local isolada, fora do repositorio,
que importa os mesmos componentes e telas e usa dados ficticios. Essa previa
nao consulta APIs, nao salva planos e nao desabilita a autenticacao do aplicativo.

A sensacao de toque e rolagem deve ser conferida tambem em iOS e Android reais.
Esta entrega nao adiciona gestos para arrastar entre abas nem efeitos de vidro.

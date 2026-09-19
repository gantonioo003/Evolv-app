# Evolv - Fontes de Dados

## Decisao

O Evolv nao copiara o banco do MyFitnessPal nem o conteudo integral de livros. O projeto usara fontes com API ou licenca adequada e guardara a origem de cada registro.

## Alimentos

### USDA FoodData Central

Fonte principal para alimentos genericos, composicao nutricional, porcoes e micronutrientes.

- API oficial;
- dados em dominio publico/CC0;
- alimentos genericos e produtos de marca;
- calorias, macros, vitaminas e minerais.

Documentacao: https://fdc.nal.usda.gov/api-guide/

### Open Food Facts

Fonte complementar para produtos industrializados e leitura por codigo de barras.

- API aberta;
- exige cumprimento da licenca ODbL e atribuicao;
- dados colaborativos podem estar incompletos e precisam de indicacao de qualidade.

Documentacao: https://openfoodfacts.github.io/documentation/docs/Product-Opener/api/

### TBCA/USP

Boa referencia para alimentos e preparacoes brasileiras. A licenca atual restringe reproducao e uso comercial; antes de importar dados, o projeto deve confirmar autorizacao com os responsaveis.

Site: https://www.tbca.net.br/

### Alimentos personalizados

O usuario podera criar alimentos e receitas proprias quando um item nao existir ou estiver incorreto.

## Exercicios

### Catalogo Evolv

O seed local contem uma base inicial criada para o projeto, com maquinas, pesos livres, cabos, calistenia, core e potencia.

### wger

Pode complementar o catalogo por API. Seus dados iniciais de exercicios usam licenca CC BY-SA 3.0, portanto exigem atribuicao e compartilhamento compativel do conteudo derivado.

Documentacao: https://wger.readthedocs.io/en/stable/

### Referencias tecnicas

Livros como Strength Training Anatomy e manuais da NSCA servem para estudar classificacao, tecnica e seguranca. Textos, imagens e listas editoriais nao devem ser copiados para o app sem licenca.

## Regras de qualidade

- guardar fonte e identificador externo;
- distinguir dado verificado, rotulo, calculado, estimado e enviado por usuario;
- preservar uma copia dos nutrientes usados em cada diario alimentar;
- nunca expor chaves de API no aplicativo mobile;
- sincronizar fontes externas pelo backend;
- mostrar que gasto calorico e uma estimativa;
- manter atribuicoes exigidas por cada fonte.

## Estrategia de armazenamento

O Evolv nao precisa copiar milhoes de alimentos para o Supabase de uma vez. O backend pesquisa nas fontes externas, converte a resposta para o formato do Evolv e salva em cache apenas os alimentos consultados ou usados. Isso reduz custo e mantem os dados atualizados.

O catalogo de exercicios pode ser sincronizado em lotes, pois e menor. O seed local garante que o app funcione mesmo antes da primeira sincronizacao.

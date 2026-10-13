# Corpus TinyLM 1.1.0

Preparado, sem treinamento de tokenizer ou Transformer.

- Train: 6.456 documentos.
- Validation: 57 documentos.
- Test: 42 documentos.
- Total: 6.555 documentos; 1.660.248 unidades separadas por espacos.
- Contagem exata de tokens: pendente do tokenizer, nao equivale a palavras.

Acrescenta 108 perguntas sinteticas proprias e 66 pares educativos derivados
dos chunks da base de conhecimento que ja pertenciam ao train. Os pares sao
gerados pelo projeto, nao conversas humanas. Contem limites de uso e IDs das
fontes existentes. Nao sao prescricoes individuais revisadas por clinico.

Os arquivos de validation e test sao copias byte a byte da versao 1.0.0.
Nenhum grupo desses holdouts foi adicionado ao train. Fontes, licencas e
atribuicoes dos documentos antigos permanecem em `../1.0.0/sources.json` e nos
metadados de cada documento. Inputs e hashes estao em `manifest.json`.

Nao inclui as 10.000 mensagens web com direitos nao verificados nem respostas
de participantes de forums. Mais texto nao implica melhores respostas: TinyLM
ainda sera um experimento educativo, separado do Coach principal.

Para a nova coleta, construir outra versao apos verificar origem, direitos,
consentimento, privacidade e separacao dos grupos. Nao sobrescrever esta.

# SFT 1.0.0 — Evolv

Preparado em 02/11/2026 para Qwen3-4B-Instruct-2507, revisão fixa
`cdbee75f17c01a7cc42f958dc650907174af0554`.

- 391 conversas sintéticas: 335 treino, 28 validação e 28 teste.
- 162 famílias disjuntas: 140/11/11.
- 30 conversas com histórico: 26/2/2.
- Treino com exemplos das 60 intenções e 21 riscos; presença não é boa cobertura.
- 67 conteúdos da base atual geram 201 pares; 95 situações geram 190 conversas.
- 1.024 tokens como limite; máximo observado 275; nenhuma truncagem ou exclusão.
- Tokens-alvo no treino: 19.259, apenas última resposta e encerramento do template.
- Labels não são deslocados na preparação; o causal LM do Transformers desloca internamente.

Dados e arrays em `private/`, ignorado pelo Git. `report.json` contém as contagens;
`manifest.json` fixa fontes, saídas e tokenizador. O teste exige abertura explícita
no carregador e não deve escolher hiperparâmetros.

Todos os 12.179 registros de NLP e 6.711 documentos do corpus foram inventariados.
Eles não foram automaticamente convertidos em respostas-alvo do Coach.

São exemplos preparados por IA, não dados humanos gold, certificação clínica ou
prova de melhora do modelo. O teste é pequeno e sintético. O download dos pesos
de 4B e a conferência da GPU continuam pendentes da 7.04.1.

Mapa completo: `docs/32-openlm-adaptation-data.md`, a partir da raiz do projeto.

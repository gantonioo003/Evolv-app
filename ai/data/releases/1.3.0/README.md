# Evolv NLU dataset 1.3.0

Dataset congelado para classificar 30 intencoes e 13 riscos do Coach.

- `train`: 1.019 mensagens, usadas para ajustar os classificadores.
- `validation`: 129 mensagens, usadas somente para escolher o modelo.
- `test`: 129 mensagens, abertas uma unica vez na avaliacao final.
- `challenge/real_human_examples.jsonl`: 10 mensagens humanas publicas do
  OASST1, mantidas fora do treino e da selecao.

Os exemplos combinam o dataset anterior, variacoes de estilo agrupadas e
novos contrastes escritos para as classes do Evolv. O arquivo `manifest.json`
congela os hashes; `quality_report.json` comprova cobertura, unicidade e
isolamento entre as divisoes.

O conjunto e pequeno e orientado ao dominio. Ele mede aprendizado e erros de
forma reproduzivel, mas nao demonstra qualidade de producao nem cobre sozinho
conversas longas, contexto entre turnos ou toda a variacao do portugues.

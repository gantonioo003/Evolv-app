# Evolv - Contexto de treino, dieta e motivação

## Status

Regra de produto definida. A implementação no banco, backend e mobile será feita durante a fase 5.

## Objetivo

Relacionar progressão de treino, fase nutricional, recuperação, divisão semanal e motivação sem transformar o Evolv em um aplicativo cobrador.

Todos os registros desta área serão opcionais. Sem dados suficientes, o app não inventará um diagnóstico nem afirmará que existe um platô.

## Fases nutricionais

O Evolv usará nomes claros na interface e nomes consistentes internamente:

- **Ganho de massa (bulking):** período com foco em aumentar massa corporal e muscular;
- **Perda de gordura (cutting):** período com foco em reduzir gordura corporal;
- **Manutenção:** período próximo ao equilíbrio energético;
- **Recomposição corporal:** tentativa de reduzir gordura e aumentar ou preservar massa magra;
- **Pausa de dieta (diet break):** período temporário em manutenção durante uma fase de perda de gordura;
- **Fase personalizada:** permite registrar um contexto que não cabe nas opções anteriores.

`Bulking` e `cutting` são termos comuns no fisiculturismo, mas não representam protocolos únicos. O plano real continua sendo definido por duração, ingestão, objetivo, evolução e resposta individual.

O Evolv não encerrará nem trocará uma fase sozinho. Ele poderá perceber sinais, explicar o contexto e perguntar se o usuário deseja revisar o plano com o Coach.

## Divisões de treino

Nomes principais oferecidos:

- **Full body:** corpo inteiro na mesma sessão;
- **Upper/Lower:** alternância entre membros superiores e inferiores;
- **Push/Pull/Legs (PPL):** empurrar, puxar e pernas;
- **Body-part split:** sessões organizadas principalmente por grupos musculares;
- **Híbrida:** combinação de estruturas, modalidades ou focos;
- **Personalizada:** qualquer estrutura criada pelo usuário ou pelo Planner.

Termos exibidos como alternativas familiares:

- `bro split` como nome informal de uma divisão por grupos musculares;
- `ABC`, `ABCD` e `ABCDE` como rótulos de agenda, não como métodos fixos.

As letras não serão a fonte real do plano. O banco guardará quais grupos, exercícios e focos pertencem a cada dia. Assim, dois treinos chamados `ABCDE` podem continuar diferentes sem gerar ambiguidade.

## Detecção opcional de dificuldade de progressão

O app não deve considerar apenas quantas semanas se passaram. Uma análise simples poderá usar:

- últimas sessões comparáveis do mesmo exercício;
- carga, repetições e séries registradas;
- esforço percebido ou repetições em reserva, quando informados;
- frequência e consistência dos registros;
- fase nutricional atual e sua duração;
- tendência de peso, quando registrada;
- energia, sono, recuperação, fome e motivação, quando informados;
- dor ou limitação relatada ao Coach.

Regra inicial sugerida para o MVP:

1. Exigir pelo menos três sessões comparáveis do exercício.
2. Verificar se carga, repetições ou volume não evoluíram.
3. Conferir se os registros têm qualidade suficiente.
4. Relacionar o resultado com fase nutricional e recuperação.
5. Apresentar uma pergunta, não uma conclusão automática.

Exemplo de aviso:

> Sua progressão no supino está estável nas últimas quatro sessões. Você está há algum tempo em perda de gordura. Quer revisar recuperação, alimentação ou o treino com o Coach?

Possíveis respostas do sistema:

- manter a carga por mais sessões;
- sugerir uma pequena progressão;
- tentar evoluir repetições antes da carga;
- revisar descanso, sono ou alimentação;
- revisar volume e frequência;
- considerar uma semana de menor esforço;
- encaminhar dor ou sintomas persistentes para avaliação profissional.

Nenhuma mudança será aplicada sem confirmação do usuário.

## Motivação e aderência

O Evolv poderá oferecer um check-in opcional e curto, sem exigir diário:

- motivação;
- energia;
- qualidade do sono;
- recuperação percebida;
- fome;
- estresse;
- observação livre.

O app não usará culpa, sequência obrigatória ou mensagens de fracasso. Se a motivação estiver baixa, o Coach poderá ajudar a identificar o motivo e propor ajustes pequenos, como reorganizar horários, reduzir complexidade, trocar exercícios ou rever a meta atual.

O usuário continuará livre para ignorar o check-in, não registrar treinos e usar somente as partes do app que desejar.

## Atenção silenciosa

O Evolv deve acompanhar somente os dados que o usuário decidiu registrar ou autorizou. Estar atento não significa interromper a pessoa o tempo todo.

Regras de comportamento:

- análises comuns aparecem discretamente na tela relacionada ou no resumo semanal;
- o app não envia aviso logo após uma falta nem cobra justificativa;
- uma notificação proativa só pode acontecer se a pessoa permitir esse tipo de aviso;
- o padrão precisa se repetir e ter dados suficientes antes de gerar uma sugestão;
- o mesmo assunto não deve ser repetido em sequência;
- ignorar, dispensar ou adiar uma sugestão cria um período de silêncio para aquele tema;
- sinais de baixa confiança ficam disponíveis para o Coach, sem interromper o usuário;
- mudanças de plano continuam dependendo de confirmação.

No MVP, a regra padrão será no máximo uma sugestão proativa não urgente por semana. Uma sugestão dispensada não reaparecerá pelo mesmo motivo por pelo menos 30 dias, salvo se o usuário abrir o Coach e pedir a análise.

O tom deve ser calmo e útil:

> Notei um padrão que talvez valha revisar. Não precisa decidir agora.

O Evolv não usará alertas como `você falhou`, `você perdeu sua sequência` ou `seu progresso está ruim`.

## Limites de segurança

- O Evolv não fará diagnóstico médico, psicológico ou nutricional.
- Um platô não será atribuído automaticamente ao cutting, à motivação ou a uma única causa.
- Sintomas persistentes, dor, perda excessiva de desempenho ou sinais de baixa disponibilidade energética exigem orientação profissional.
- As recomendações explicarão quais dados foram usados e o grau de confiança.

## Extensões planejadas para a fase 5

- fase nutricional atual e histórico de fases;
- tipo e nome da divisão em cada plano de treino;
- check-ins opcionais de motivação e recuperação;
- esforço percebido opcional nos registros de exercício;
- evidências usadas em cada sugestão de progressão;
- regras do Planner para reconhecer sinais sem alterar o plano sozinho.
- preferências de sugestões proativas, adiamento e período de silêncio por tema.

## Referências técnicas iniciais

- [Split versus full-body resistance training: revisão sistemática e meta-análise](https://pubmed.ncbi.nlm.nih.gov/38595233/)
- [Déficit energético e ganhos com treino resistido: meta-análise](https://pubmed.ncbi.nlm.nih.gov/34623696/)
- [Diet break em atletas treinados: análise do estudo ICECAP](https://pubmed.ncbi.nlm.nih.gov/33630880/)
- [Motivação e aderência ao exercício: revisão sistemática](https://pubmed.ncbi.nlm.nih.gov/30459690/)

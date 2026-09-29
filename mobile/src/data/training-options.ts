export type TrainingOption = {
  id: string;
  title: string;
  description: string;
};

export const trainingModalities: TrainingOption[] = [
  { id: 'full-gym', title: 'Academia completa', description: 'Combinação ampla de equipamentos' },
  { id: 'machines', title: 'Máquinas', description: 'Guiadas, articuladas e placas' },
  { id: 'free-weights', title: 'Peso livre', description: 'Halteres, barras e kettlebells' },
  { id: 'cables', title: 'Cabos e polias', description: 'Estações ajustáveis e crossover' },
  { id: 'calisthenics', title: 'Calistenia', description: 'Peso corporal, barras e paralelas' },
  { id: 'bands', title: 'Elásticos', description: 'Faixas, minibands e resistência variável' },
  { id: 'functional', title: 'Funcional', description: 'Movimentos integrados e circuitos' },
  { id: 'suspension', title: 'Suspensão', description: 'Fitas e exercícios no estilo TRX' },
  { id: 'bodyweight', title: 'Sem equipamento', description: 'Treino possível em qualquer lugar' },
  { id: 'cardio-equipment', title: 'Cardio em aparelhos', description: 'Esteira, bike, elíptico e similares' },
  { id: 'running', title: 'Corrida', description: 'Rua, pista ou esteira' },
  { id: 'walking', title: 'Caminhada', description: 'Leve, moderada ou inclinada' },
  { id: 'cycling', title: 'Ciclismo', description: 'Bike indoor ou ao ar livre' },
  { id: 'rowing', title: 'Remo', description: 'Ergômetro ou prática esportiva' },
  { id: 'stairs', title: 'Escada', description: 'Simulador ou treino em degraus' },
  { id: 'swimming', title: 'Natação', description: 'Técnica e condicionamento aquático' },
  { id: 'hiit', title: 'HIIT', description: 'Intervalos curtos de alta intensidade' },
  { id: 'plyometrics', title: 'Pliometria', description: 'Saltos, velocidade e explosão' },
  { id: 'yoga-pilates', title: 'Yoga e Pilates', description: 'Controle corporal, postura e estabilidade' },
  { id: 'sports', title: 'Preparação esportiva', description: 'Capacidades específicas para cada esporte' },
  { id: 'mobility', title: 'Mobilidade', description: 'Amplitude, controle e prevenção' },
  { id: 'stretching', title: 'Alongamento', description: 'Flexibilidade e recuperação' },
];

export const trainingFocuses: TrainingOption[] = [
  { id: 'hypertrophy', title: 'Hipertrofia', description: 'Ganho de massa muscular' },
  { id: 'strength', title: 'Força', description: 'Aumentar a capacidade de carga' },
  { id: 'endurance', title: 'Resistência muscular', description: 'Sustentar esforço por mais tempo' },
  { id: 'conditioning', title: 'Condicionamento', description: 'Capacidade cardiorrespiratória geral' },
  { id: 'power', title: 'Potência e explosão', description: 'Velocidade e produção rápida de força' },
  { id: 'weight-loss', title: 'Emagrecimento', description: 'Gasto energético com preservação muscular' },
  { id: 'low-impact', title: 'Baixo impacto', description: 'Treino com menor estresse articular' },
];

export const defaultTrainingModalities = ['machines', 'free-weights', 'cardio-equipment'];
export const defaultTrainingFocuses = ['hypertrophy', 'conditioning'];

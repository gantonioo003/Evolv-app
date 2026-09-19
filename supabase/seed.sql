-- Evolv - Reference catalog seed
-- Local starter data. Larger production catalogs will be synchronized
-- from licensed external sources through the backend.

insert into public.nutrients (code, name, unit, category)
values
  ('energy_kcal', 'Energia', 'kcal', 'energy'),
  ('protein', 'Proteina', 'g', 'macro'),
  ('carbohydrate', 'Carboidrato', 'g', 'macro'),
  ('total_fat', 'Gordura total', 'g', 'macro'),
  ('fiber', 'Fibra alimentar', 'g', 'carbohydrate'),
  ('total_sugars', 'Acucares totais', 'g', 'carbohydrate'),
  ('added_sugars', 'Acucares adicionados', 'g', 'carbohydrate'),
  ('saturated_fat', 'Gordura saturada', 'g', 'fat'),
  ('trans_fat', 'Gordura trans', 'g', 'fat'),
  ('cholesterol', 'Colesterol', 'mg', 'fat'),
  ('sodium', 'Sodio', 'mg', 'mineral'),
  ('potassium', 'Potassio', 'mg', 'mineral'),
  ('calcium', 'Calcio', 'mg', 'mineral'),
  ('iron', 'Ferro', 'mg', 'mineral'),
  ('magnesium', 'Magnesio', 'mg', 'mineral'),
  ('vitamin_c', 'Vitamina C', 'mg', 'vitamin'),
  ('vitamin_d', 'Vitamina D', 'mcg', 'vitamin')
on conflict (code) do update set
  name = excluded.name,
  unit = excluded.unit,
  category = excluded.category;

insert into public.equipment (slug, name, category)
values
  ('bodyweight', 'Peso corporal', 'bodyweight'),
  ('barbell', 'Barra', 'free_weight'),
  ('dumbbell', 'Halteres', 'free_weight'),
  ('ez_bar', 'Barra W', 'free_weight'),
  ('kettlebell', 'Kettlebell', 'free_weight'),
  ('cable_station', 'Estacao de cabos', 'cable'),
  ('smith_machine', 'Smith machine', 'machine'),
  ('chest_press_machine', 'Maquina de supino', 'machine'),
  ('pec_deck', 'Peck deck', 'machine'),
  ('shoulder_press_machine', 'Maquina de desenvolvimento', 'machine'),
  ('lateral_raise_machine', 'Maquina de elevacao lateral', 'machine'),
  ('lat_pulldown_machine', 'Maquina de puxada alta', 'machine'),
  ('seated_row_machine', 'Maquina de remada sentada', 'machine'),
  ('preacher_curl_machine', 'Maquina de rosca Scott', 'machine'),
  ('triceps_extension_machine', 'Maquina de triceps', 'machine'),
  ('leg_press_45', 'Leg press 45 graus', 'machine'),
  ('hack_squat_machine', 'Hack squat', 'machine'),
  ('leg_extension_machine', 'Cadeira extensora', 'machine'),
  ('lying_leg_curl_machine', 'Mesa flexora', 'machine'),
  ('seated_leg_curl_machine', 'Cadeira flexora', 'machine'),
  ('hip_thrust_machine', 'Maquina de hip thrust', 'machine'),
  ('glute_kickback_machine', 'Maquina de gluteo', 'machine'),
  ('abductor_machine', 'Cadeira abdutora', 'machine'),
  ('adductor_machine', 'Cadeira adutora', 'machine'),
  ('standing_calf_machine', 'Maquina de panturrilha em pe', 'machine'),
  ('seated_calf_machine', 'Maquina de panturrilha sentada', 'machine'),
  ('abdominal_machine', 'Maquina abdominal', 'machine'),
  ('back_extension_machine', 'Maquina de extensao lombar', 'machine'),
  ('pull_up_bar', 'Barra fixa', 'accessory'),
  ('dip_station', 'Paralelas', 'accessory'),
  ('resistance_band', 'Faixa elastica', 'functional'),
  ('suspension_trainer', 'Fitas de suspensao', 'functional'),
  ('landmine', 'Landmine', 'functional'),
  ('medicine_ball', 'Medicine ball', 'functional'),
  ('ab_wheel', 'Roda abdominal', 'functional'),
  ('plyo_box', 'Caixa pliometrica', 'functional'),
  ('sled', 'Treno', 'functional'),
  ('battle_rope', 'Corda naval', 'functional')
on conflict (slug) do update set name = excluded.name, category = excluded.category;

insert into public.muscle_groups (slug, name, body_region)
values
  ('chest', 'Peitoral', 'upper'),
  ('latissimus', 'Latissimo do dorso', 'upper'),
  ('upper_back', 'Costas superiores', 'upper'),
  ('trapezius', 'Trapezio', 'upper'),
  ('front_deltoid', 'Deltoide anterior', 'upper'),
  ('lateral_deltoid', 'Deltoide lateral', 'upper'),
  ('rear_deltoid', 'Deltoide posterior', 'upper'),
  ('biceps', 'Biceps', 'upper'),
  ('triceps', 'Triceps', 'upper'),
  ('forearms', 'Antebracos', 'upper'),
  ('quadriceps', 'Quadriceps', 'lower'),
  ('hamstrings', 'Posteriores da coxa', 'lower'),
  ('glutes', 'Gluteos', 'lower'),
  ('adductors', 'Adutores', 'lower'),
  ('abductors', 'Abdutores', 'lower'),
  ('gastrocnemius', 'Gastrocnemio', 'lower'),
  ('soleus', 'Soleo', 'lower'),
  ('rectus_abdominis', 'Reto abdominal', 'core'),
  ('obliques', 'Obliquos', 'core'),
  ('transverse_abdominis', 'Transverso abdominal', 'core'),
  ('spinal_erectors', 'Eretores da coluna', 'core'),
  ('full_body', 'Corpo inteiro', 'full_body')
on conflict (slug) do update set name = excluded.name, body_region = excluded.body_region;

insert into public.training_styles (slug, name)
values
  ('bodybuilding', 'Hipertrofia e fisiculturismo'),
  ('strength', 'Forca'),
  ('calisthenics', 'Calistenia'),
  ('power', 'Potencia e explosao'),
  ('endurance', 'Resistencia muscular'),
  ('general_fitness', 'Condicionamento geral')
on conflict (slug) do update set name = excluded.name;

insert into public.exercises (name, muscle_group, equipment, instructions)
values
  ('Supino reto', 'chest', 'barbell', 'Movimento principal de empurrar para peito, forca e hipertrofia.'),
  ('Supino inclinado', 'chest', 'dumbbell', 'Variacao inclinada com foco maior na parte superior do peito.'),
  ('Crucifixo', 'chest', 'dumbbell', 'Movimento isolador de peito com amplitude controlada.'),
  ('Puxada alta', 'latissimus', 'lat_pulldown_machine', 'Movimento vertical de puxada para largura das costas.'),
  ('Remada baixa', 'upper_back', 'seated_row_machine', 'Movimento horizontal de puxada para espessura das costas.'),
  ('Remada curvada', 'upper_back', 'barbell', 'Remada composta para costas e controle de tronco.'),
  ('Desenvolvimento', 'front_deltoid', 'dumbbell', 'Movimento vertical de empurrar para ombros.'),
  ('Elevacao lateral', 'lateral_deltoid', 'dumbbell', 'Movimento isolador para deltoide lateral.'),
  ('Rosca direta', 'biceps', 'barbell', 'Movimento basico de flexao de cotovelo para biceps.'),
  ('Rosca alternada', 'biceps', 'dumbbell', 'Variacao unilateral de rosca com halteres.'),
  ('Triceps corda', 'triceps', 'cable_station', 'Extensao de triceps no cabo usando corda.'),
  ('Triceps testa', 'triceps', 'ez_bar', 'Movimento de extensao de cotovelo para triceps.'),
  ('Agachamento livre', 'quadriceps', 'barbell', 'Movimento composto principal para membros inferiores.'),
  ('Leg press', 'quadriceps', 'leg_press_45', 'Movimento de empurrar para pernas em maquina.'),
  ('Cadeira extensora', 'quadriceps', 'leg_extension_machine', 'Movimento isolador para quadriceps.'),
  ('Mesa flexora', 'hamstrings', 'lying_leg_curl_machine', 'Movimento isolador para posteriores de coxa.'),
  ('Stiff', 'hamstrings', 'barbell', 'Movimento de dobradica de quadril para posteriores e gluteos.'),
  ('Panturrilha em pe', 'gastrocnemius', 'standing_calf_machine', 'Variacao de panturrilha em pe.'),
  ('Panturrilha sentado', 'soleus', 'seated_calf_machine', 'Variacao de panturrilha sentado.'),
  ('Prancha', 'transverse_abdominis', 'bodyweight', 'Exercicio de estabilidade para core.')
on conflict (name) do update set
  muscle_group = excluded.muscle_group,
  equipment = excluded.equipment,
  instructions = excluded.instructions;

insert into public.exercises
  (name, muscle_group, equipment, instructions, source, movement_pattern, difficulty, is_compound)
values
  ('Supino reto com halteres', 'chest', 'dumbbell', 'Empurre os halteres mantendo os ombros estaveis.', 'evolv', 'horizontal_push', 'beginner', true),
  ('Supino inclinado com barra', 'chest', 'barbell', 'Empurre a barra no banco inclinado com controle.', 'evolv', 'horizontal_push', 'intermediate', true),
  ('Supino declinado', 'chest', 'barbell', 'Empurre a barra no banco declinado com controle.', 'evolv', 'horizontal_push', 'intermediate', true),
  ('Chest press na maquina', 'chest', 'chest_press_machine', 'Empurre as alcas mantendo as costas apoiadas.', 'evolv', 'horizontal_push', 'beginner', true),
  ('Supino no Smith', 'chest', 'smith_machine', 'Empurre a barra guiada com o banco bem posicionado.', 'evolv', 'horizontal_push', 'beginner', true),
  ('Peck deck', 'chest', 'pec_deck', 'Aproxime os bracos mantendo o peito elevado.', 'evolv', 'horizontal_adduction', 'beginner', false),
  ('Crossover alto', 'chest', 'cable_station', 'Cruze os cabos de cima para baixo.', 'evolv', 'horizontal_adduction', 'intermediate', false),
  ('Crossover baixo', 'chest', 'cable_station', 'Cruze os cabos de baixo para cima.', 'evolv', 'horizontal_adduction', 'intermediate', false),
  ('Flexao de bracos', 'chest', 'bodyweight', 'Desca o corpo alinhado e empurre o chao.', 'evolv', 'horizontal_push', 'beginner', true),
  ('Flexao inclinada', 'chest', 'bodyweight', 'Faca a flexao com as maos em apoio elevado.', 'evolv', 'horizontal_push', 'beginner', true),
  ('Flexao declinada', 'chest', 'bodyweight', 'Faca a flexao com os pes elevados.', 'evolv', 'horizontal_push', 'intermediate', true),
  ('Paralelas para peito', 'chest', 'dip_station', 'Incline o tronco e empurre nas paralelas.', 'evolv', 'vertical_push', 'advanced', true),
  ('Pullover com halter', 'latissimus', 'dumbbell', 'Leve o halter atras da cabeca e retorne com controle.', 'evolv', 'shoulder_extension', 'intermediate', false),
  ('Puxada neutra', 'latissimus', 'lat_pulldown_machine', 'Puxe a pegada neutra em direcao ao peito.', 'evolv', 'vertical_pull', 'beginner', true),
  ('Puxada unilateral', 'latissimus', 'cable_station', 'Puxe um lado por vez sem girar o tronco.', 'evolv', 'vertical_pull', 'intermediate', true),
  ('Barra fixa pronada', 'latissimus', 'pull_up_bar', 'Puxe o corpo com pegada pronada.', 'evolv', 'vertical_pull', 'advanced', true),
  ('Barra fixa supinada', 'latissimus', 'pull_up_bar', 'Puxe o corpo com pegada supinada.', 'evolv', 'vertical_pull', 'intermediate', true),
  ('Pulldown com bracos retos', 'latissimus', 'cable_station', 'Desca o cabo mantendo os bracos quase estendidos.', 'evolv', 'shoulder_extension', 'beginner', false),
  ('Remada unilateral', 'upper_back', 'dumbbell', 'Puxe o halter em direcao ao quadril.', 'evolv', 'horizontal_pull', 'beginner', true),
  ('Remada cavalinho', 'upper_back', 'landmine', 'Puxe a barra landmine mantendo o tronco firme.', 'evolv', 'horizontal_pull', 'intermediate', true),
  ('Remada articulada', 'upper_back', 'seated_row_machine', 'Puxe as alcas aproximando as escapulas.', 'evolv', 'horizontal_pull', 'beginner', true),
  ('Remada com peito apoiado', 'upper_back', 'dumbbell', 'Puxe os halteres com o peito apoiado.', 'evolv', 'horizontal_pull', 'beginner', true),
  ('Remada invertida', 'upper_back', 'bodyweight', 'Puxe o peito em direcao ao apoio.', 'evolv', 'horizontal_pull', 'intermediate', true),
  ('Encolhimento com halteres', 'trapezius', 'dumbbell', 'Eleve os ombros verticalmente.', 'evolv', 'scapular_elevation', 'beginner', false),
  ('Face pull', 'rear_deltoid', 'cable_station', 'Puxe a corda em direcao ao rosto.', 'evolv', 'horizontal_pull', 'beginner', false),
  ('Crucifixo invertido', 'rear_deltoid', 'pec_deck', 'Abra os bracos para tras com controle.', 'evolv', 'horizontal_abduction', 'beginner', false),
  ('Desenvolvimento militar', 'front_deltoid', 'barbell', 'Empurre a barra acima da cabeca.', 'evolv', 'vertical_push', 'intermediate', true),
  ('Arnold press', 'front_deltoid', 'dumbbell', 'Gire e empurre os halteres com controle.', 'evolv', 'vertical_push', 'intermediate', true),
  ('Shoulder press na maquina', 'front_deltoid', 'shoulder_press_machine', 'Empurre as alcas acima da cabeca.', 'evolv', 'vertical_push', 'beginner', true),
  ('Elevacao lateral no cabo', 'lateral_deltoid', 'cable_station', 'Eleve o braco lateralmente contra o cabo.', 'evolv', 'shoulder_abduction', 'beginner', false),
  ('Elevacao lateral na maquina', 'lateral_deltoid', 'lateral_raise_machine', 'Eleve os bracos mantendo os ombros baixos.', 'evolv', 'shoulder_abduction', 'beginner', false),
  ('Elevacao frontal', 'front_deltoid', 'dumbbell', 'Eleve os halteres a frente sem impulso.', 'evolv', 'shoulder_flexion', 'beginner', false),
  ('Remada alta', 'lateral_deltoid', 'ez_bar', 'Puxe a barra para cima com amplitude confortavel.', 'evolv', 'vertical_pull', 'intermediate', true),
  ('Rosca martelo', 'biceps', 'dumbbell', 'Flexione os cotovelos com pegada neutra.', 'evolv', 'elbow_flexion', 'beginner', false),
  ('Rosca Scott com barra W', 'biceps', 'ez_bar', 'Flexione os cotovelos com os bracos apoiados.', 'evolv', 'elbow_flexion', 'beginner', false),
  ('Rosca Scott na maquina', 'biceps', 'preacher_curl_machine', 'Flexione os cotovelos na maquina Scott.', 'evolv', 'elbow_flexion', 'beginner', false),
  ('Rosca inclinada', 'biceps', 'dumbbell', 'Flexione os cotovelos no banco inclinado.', 'evolv', 'elbow_flexion', 'intermediate', false),
  ('Rosca concentrada', 'biceps', 'dumbbell', 'Flexione um braco com o cotovelo apoiado.', 'evolv', 'elbow_flexion', 'beginner', false),
  ('Rosca no cabo', 'biceps', 'cable_station', 'Flexione os cotovelos mantendo tensao continua.', 'evolv', 'elbow_flexion', 'beginner', false),
  ('Rosca inversa', 'forearms', 'ez_bar', 'Flexione os cotovelos com pegada pronada.', 'evolv', 'elbow_flexion', 'intermediate', false),
  ('Triceps pulley com barra', 'triceps', 'cable_station', 'Estenda os cotovelos junto ao corpo.', 'evolv', 'elbow_extension', 'beginner', false),
  ('Triceps frances', 'triceps', 'dumbbell', 'Estenda o halter acima da cabeca.', 'evolv', 'elbow_extension', 'beginner', false),
  ('Triceps acima da cabeca no cabo', 'triceps', 'cable_station', 'Estenda os cotovelos acima da cabeca.', 'evolv', 'elbow_extension', 'beginner', false),
  ('Supino fechado', 'triceps', 'barbell', 'Empurre a barra com pegada fechada.', 'evolv', 'horizontal_push', 'intermediate', true),
  ('Triceps na maquina', 'triceps', 'triceps_extension_machine', 'Estenda os cotovelos na maquina.', 'evolv', 'elbow_extension', 'beginner', false),
  ('Mergulho no banco', 'triceps', 'bodyweight', 'Desca o corpo junto ao banco e empurre.', 'evolv', 'vertical_push', 'intermediate', true),
  ('Agachamento frontal', 'quadriceps', 'barbell', 'Agache com a barra a frente e tronco alto.', 'evolv', 'squat', 'advanced', true),
  ('Agachamento no Smith', 'quadriceps', 'smith_machine', 'Agache sob a barra guiada.', 'evolv', 'squat', 'beginner', true),
  ('Agachamento goblet', 'quadriceps', 'dumbbell', 'Agache segurando o halter junto ao peito.', 'evolv', 'squat', 'beginner', true),
  ('Hack squat', 'quadriceps', 'hack_squat_machine', 'Agache mantendo quadris e costas apoiados.', 'evolv', 'squat', 'beginner', true),
  ('Agachamento bulgaro', 'quadriceps', 'dumbbell', 'Agache com o pe traseiro elevado.', 'evolv', 'lunge', 'intermediate', true),
  ('Afundo', 'quadriceps', 'dumbbell', 'Desca em base dividida mantendo equilibrio.', 'evolv', 'lunge', 'beginner', true),
  ('Passada', 'quadriceps', 'dumbbell', 'Avance alternando as pernas.', 'evolv', 'lunge', 'intermediate', true),
  ('Step up', 'quadriceps', 'dumbbell', 'Suba na caixa usando a perna apoiada.', 'evolv', 'step', 'beginner', true),
  ('Sissy squat', 'quadriceps', 'bodyweight', 'Flexione os joelhos mantendo quadris estendidos.', 'evolv', 'knee_extension', 'advanced', false),
  ('Cadeira flexora', 'hamstrings', 'seated_leg_curl_machine', 'Flexione os joelhos sentado.', 'evolv', 'knee_flexion', 'beginner', false),
  ('Levantamento romeno com halteres', 'hamstrings', 'dumbbell', 'Leve o quadril para tras com os halteres.', 'evolv', 'hip_hinge', 'beginner', true),
  ('Good morning', 'hamstrings', 'barbell', 'Incline o tronco pelo quadril.', 'evolv', 'hip_hinge', 'advanced', true),
  ('Nordic curl', 'hamstrings', 'bodyweight', 'Desca resistindo com os posteriores.', 'evolv', 'knee_flexion', 'advanced', false),
  ('Glute ham raise', 'hamstrings', 'back_extension_machine', 'Flexione joelhos e quadris com controle.', 'evolv', 'knee_flexion', 'advanced', true),
  ('Pull through', 'glutes', 'cable_station', 'Estenda o quadril puxando o cabo.', 'evolv', 'hip_hinge', 'beginner', true),
  ('Hip thrust', 'glutes', 'barbell', 'Eleve o quadril com as costas apoiadas.', 'evolv', 'hip_extension', 'intermediate', true),
  ('Hip thrust na maquina', 'glutes', 'hip_thrust_machine', 'Estenda o quadril na maquina.', 'evolv', 'hip_extension', 'beginner', true),
  ('Ponte de gluteos', 'glutes', 'bodyweight', 'Eleve o quadril apertando os gluteos.', 'evolv', 'hip_extension', 'beginner', true),
  ('Coice no cabo', 'glutes', 'cable_station', 'Estenda uma perna para tras.', 'evolv', 'hip_extension', 'beginner', false),
  ('Coice na maquina', 'glutes', 'glute_kickback_machine', 'Empurre a plataforma para tras.', 'evolv', 'hip_extension', 'beginner', false),
  ('Cadeira abdutora', 'abductors', 'abductor_machine', 'Abra as pernas com controle.', 'evolv', 'hip_abduction', 'beginner', false),
  ('Cadeira adutora', 'adductors', 'adductor_machine', 'Feche as pernas com controle.', 'evolv', 'hip_adduction', 'beginner', false),
  ('Agachamento sumo com halter', 'adductors', 'dumbbell', 'Agache em base ampla.', 'evolv', 'squat', 'beginner', true),
  ('Panturrilha no leg press', 'gastrocnemius', 'leg_press_45', 'Empurre a plataforma apenas com os tornozelos.', 'evolv', 'plantar_flexion', 'beginner', false),
  ('Panturrilha unilateral', 'gastrocnemius', 'bodyweight', 'Eleve um calcanhar por vez.', 'evolv', 'plantar_flexion', 'beginner', false),
  ('Prancha lateral', 'obliques', 'bodyweight', 'Mantenha o corpo alinhado de lado.', 'evolv', 'anti_lateral_flexion', 'beginner', false),
  ('Crunch na maquina', 'rectus_abdominis', 'abdominal_machine', 'Flexione o tronco de forma controlada.', 'evolv', 'spinal_flexion', 'beginner', false),
  ('Crunch no cabo', 'rectus_abdominis', 'cable_station', 'Flexione a coluna contra o cabo.', 'evolv', 'spinal_flexion', 'intermediate', false),
  ('Elevacao de pernas suspenso', 'rectus_abdominis', 'pull_up_bar', 'Eleve as pernas sem usar balanco.', 'evolv', 'hip_flexion', 'advanced', false),
  ('Roda abdominal', 'transverse_abdominis', 'ab_wheel', 'Estenda o corpo sem perder o controle lombar.', 'evolv', 'anti_extension', 'advanced', false),
  ('Dead bug', 'transverse_abdominis', 'bodyweight', 'Alterne braco e perna com lombar apoiada.', 'evolv', 'anti_extension', 'beginner', false),
  ('Pallof press', 'obliques', 'cable_station', 'Empurre o cabo resistindo a rotacao.', 'evolv', 'anti_rotation', 'beginner', false),
  ('Russian twist', 'obliques', 'medicine_ball', 'Gire o tronco com controle.', 'evolv', 'rotation', 'intermediate', false),
  ('Crunch reverso', 'rectus_abdominis', 'bodyweight', 'Aproxime o quadril das costelas.', 'evolv', 'spinal_flexion', 'beginner', false),
  ('Extensao lombar', 'spinal_erectors', 'back_extension_machine', 'Estenda o quadril sem hiperestender a coluna.', 'evolv', 'hip_hinge', 'beginner', true),
  ('Levantamento terra', 'full_body', 'barbell', 'Tire a barra do chao mantendo-a proxima.', 'evolv', 'hip_hinge', 'advanced', true),
  ('Levantamento terra sumo', 'full_body', 'barbell', 'Tire a barra do chao usando base ampla.', 'evolv', 'hip_hinge', 'advanced', true),
  ('Power clean', 'full_body', 'barbell', 'Acelere a barra e receba-a nos ombros.', 'evolv', 'olympic_pull', 'advanced', true),
  ('Hang clean', 'full_body', 'barbell', 'Acelere a barra a partir da posicao suspensa.', 'evolv', 'olympic_pull', 'advanced', true),
  ('Push press', 'full_body', 'barbell', 'Use pernas e bracos para impulsionar a barra.', 'evolv', 'vertical_push', 'advanced', true),
  ('Kettlebell swing', 'full_body', 'kettlebell', 'Projete o quadril para mover o kettlebell.', 'evolv', 'hip_hinge', 'intermediate', true),
  ('Salto na caixa', 'full_body', 'plyo_box', 'Salte e aterrisse suavemente na caixa.', 'evolv', 'jump', 'intermediate', true),
  ('Arremesso de medicine ball', 'full_body', 'medicine_ball', 'Arremesse a bola de forma explosiva.', 'evolv', 'throw', 'intermediate', true),
  ('Empurrar treno', 'full_body', 'sled', 'Empurre o treno com passadas fortes.', 'evolv', 'locomotion', 'intermediate', true),
  ('Corda naval', 'full_body', 'battle_rope', 'Produza ondas mantendo postura e ritmo.', 'evolv', 'conditioning', 'beginner', true),
  ('Burpee', 'full_body', 'bodyweight', 'Combine agachamento, prancha e salto.', 'evolv', 'conditioning', 'intermediate', true),
  ('Agachamento pistol', 'quadriceps', 'bodyweight', 'Agache em uma perna com controle.', 'evolv', 'squat', 'advanced', true),
  ('Pike push-up', 'front_deltoid', 'bodyweight', 'Faca uma flexao com os quadris elevados.', 'evolv', 'vertical_push', 'intermediate', true),
  ('Handstand push-up', 'front_deltoid', 'bodyweight', 'Faca a flexao em parada de maos.', 'evolv', 'vertical_push', 'advanced', true),
  ('Muscle-up', 'full_body', 'pull_up_bar', 'Combine puxada explosiva e transicao.', 'evolv', 'vertical_pull', 'advanced', true),
  ('L-sit', 'transverse_abdominis', 'dip_station', 'Sustente o corpo com pernas a frente.', 'evolv', 'isometric', 'advanced', false),
  ('Remada em suspensao', 'upper_back', 'suspension_trainer', 'Puxe o corpo mantendo alinhamento.', 'evolv', 'horizontal_pull', 'beginner', true),
  ('Band pull-apart', 'rear_deltoid', 'resistance_band', 'Abra a faixa na altura dos ombros.', 'evolv', 'horizontal_abduction', 'beginner', false)
on conflict (name) do update set
  muscle_group = excluded.muscle_group,
  equipment = excluded.equipment,
  instructions = excluded.instructions,
  source = excluded.source,
  movement_pattern = excluded.movement_pattern,
  difficulty = excluded.difficulty,
  is_compound = excluded.is_compound,
  updated_at = now();

insert into public.exercise_equipment (exercise_id, equipment_id)
select ex.id, eq.id
from public.exercises ex
join public.equipment eq on eq.slug = ex.equipment
on conflict do nothing;

insert into public.exercise_muscles (exercise_id, muscle_group_id, role)
select ex.id, mg.id, 'primary'
from public.exercises ex
join public.muscle_groups mg on mg.slug = ex.muscle_group
on conflict do nothing;

insert into public.exercise_training_styles (exercise_id, training_style_id)
select ex.id, ts.id
from public.exercises ex
cross join public.training_styles ts
where
  ts.slug = 'general_fitness'
  or (ts.slug = 'bodybuilding' and ex.muscle_group <> 'full_body')
  or (ts.slug = 'strength' and ex.is_compound)
  or (ts.slug = 'calisthenics' and ex.equipment in ('bodyweight', 'pull_up_bar', 'dip_station', 'suspension_trainer'))
  or (ts.slug = 'power' and ex.movement_pattern in ('olympic_pull', 'jump', 'throw', 'locomotion'))
  or (ts.slug = 'endurance' and ex.movement_pattern in ('conditioning', 'locomotion'))
on conflict do nothing;

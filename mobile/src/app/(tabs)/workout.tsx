import { useMemo, useState } from 'react';
import { Alert, Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { useRouter } from 'expo-router';
import { CalendarRange, ChevronRight, Dumbbell, Info, SlidersHorizontal, TrendingUp } from 'lucide-react-native';

import { LoadStepper } from '@/components/load-stepper';
import { AppScreen, CinematicHero, Divider, InfoRow, LabelIcon, PageHeader, ProgressBar, SectionTitle, Surface, Tag } from '@/components/ui';
import { colors, radius, spacing } from '@/constants/theme';
import { useImagePreferences } from '@/context/image-preferences-context';
import { useAppTheme, type AppThemePalette } from '@/context/theme-context';
import { useTrainingPreferences } from '@/context/training-preferences-context';
import { workoutDays } from '@/data/mock-data';
import { pickWeeklyImage, workoutCategoryByDayId, workoutImageLibrary } from '@/data/image-library';
import { trainingFocuses, trainingModalities } from '@/data/training-options';

const initialLoads = Object.fromEntries(
  workoutDays.flatMap((day) => day.exercises.map((exercise) => [exercise.id, exercise.load])),
) as Record<string, number>;

export default function WorkoutScreen() {
  const { palette } = useAppTheme();
  const imagePreferences = useImagePreferences();
  const { selectedFocusIds, selectedModalityIds } = useTrainingPreferences();
  const styles = createStyles(palette);
  const router = useRouter();
  const [selectedDayId, setSelectedDayId] = useState('wed');
  const [loads, setLoads] = useState(initialLoads);
  const selectedDay = useMemo(
    () => workoutDays.find((day) => day.id === selectedDayId) ?? workoutDays[2],
    [selectedDayId],
  );

  const firstExercise = selectedDay.exercises[0];
  const activeModalities = trainingModalities.filter((option) => selectedModalityIds.includes(option.id));
  const activeFocuses = trainingFocuses.filter((option) => selectedFocusIds.includes(option.id));
  const modalitySummary = activeModalities.length
    ? `${activeModalities.slice(0, 3).map((option) => option.title).join(' + ')}${activeModalities.length > 3 ? ` +${activeModalities.length - 3}` : ''}`
    : 'Escolher modalidades';
  const focusSummary = activeFocuses.length
    ? activeFocuses.map((option) => option.title).join(' + ')
    : 'Sem foco definido';
  const heroDescription = selectedDay.status === 'rest'
    ? 'Recuperar também faz parte do plano. Hoje não há treino obrigatório.'
    : selectedDay.status === 'free'
      ? 'Dia flexível para reorganizar a semana sem alterar todo o programa.'
      : `${selectedDay.exercises.length} exercícios, ${selectedDay.durationMinutes} minutos e cargas prontas para consultar.`;
  const imageCategory = workoutCategoryByDayId[selectedDay.id] ?? 'fullBody';
  const heroImage = pickWeeklyImage(workoutImageLibrary[imageCategory], imagePreferences, `workout-${imageCategory}`, 1);

  return (
    <AppScreen>
      <PageHeader
        eyebrow="Semana 1 de 12"
        title="Treino"
        actionIcon={CalendarRange}
        actionLabel="Informações do calendário"
        onAction={() => Alert.alert('Calendário', 'A agenda completa será conectada ao Planner na fase de backend.')}
      />

      <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.weekContent}>
        {workoutDays.map((day) => {
          const active = day.id === selectedDay.id;
          return (
            <Pressable
              accessibilityRole="button"
              accessibilityState={{ selected: active }}
              key={day.id}
              onPress={() => setSelectedDayId(day.id)}
              style={({ pressed }) => [styles.day, active && styles.dayActive, pressed && styles.pressed]}
            >
              <Text style={[styles.dayLabel, active && styles.dayLabelActive]}>{day.shortLabel}</Text>
              <Text numberOfLines={1} style={[styles.dayTitle, active && styles.dayTitleActive]}>{day.title.split(' ')[0]}</Text>
            </Pressable>
          );
        })}
      </ScrollView>

      <CinematicHero
        source={heroImage}
        eyebrow={selectedDay.weekday}
        title={selectedDay.title}
        description={heroDescription}
        meta={selectedDay.status === 'planned' ? 'Treino previsto' : selectedDay.status === 'rest' ? 'Recuperação' : 'Agenda flexível'}
        height={240}
        overlayOpacity={0.2}
      />

      <View style={styles.programBand}>
        <InfoRow
          leading={<LabelIcon icon={Dumbbell} />}
          title="Hipertrofia base"
          description="4 treinos por semana - progressão conservadora"
          trailing={<Tag color={colors.green}>Ativo</Tag>}
        />
      </View>

      <SectionTitle title="Modalidades do plano" meta="combináveis" />
      <Surface>
        <InfoRow
          leading={<LabelIcon icon={SlidersHorizontal} />}
          title={modalitySummary}
          description={focusSummary}
          trailing={<ChevronRight color={palette.faint} size={18} />}
          onPress={() => router.push('/training-preferences')}
        />
      </Surface>

      <SectionTitle
        title={selectedDay.exercises.length ? 'Exercícios do dia' : 'Plano do dia'}
        meta={selectedDay.durationMinutes ? `${selectedDay.durationMinutes} min` : selectedDay.status === 'rest' ? 'descanso' : 'flexível'}
      />

      {selectedDay.exercises.length ? (
        <View style={styles.exerciseList}>
          {selectedDay.exercises.map((exercise, index) => (
            <View key={exercise.id}>
              {index > 0 ? <Divider /> : null}
              <View style={styles.exerciseRow}>
                <View style={styles.exerciseNumber}><Text style={styles.exerciseNumberText}>{index + 1}</Text></View>
                <View style={styles.exerciseBody}>
                  <Text style={styles.exerciseName}>{exercise.name}</Text>
                  <Text style={styles.exerciseMeta}>
                    {exercise.sets} séries - {exercise.reps} reps - {exercise.restSeconds}s
                    {exercise.note ? ` - ${exercise.note}` : ''}
                  </Text>
                </View>
                <LoadStepper
                  value={loads[exercise.id] ?? exercise.load}
                  onChange={(value) => setLoads((current) => ({ ...current, [exercise.id]: value }))}
                />
              </View>
            </View>
          ))}
        </View>
      ) : (
        <Surface>
          <InfoRow
            leading={<LabelIcon icon={Info} />}
            title={selectedDay.status === 'rest' ? 'Descanso programado' : 'Dia flexível'}
            description="Nenhum exercício obrigatório. O restante do plano permanece igual."
          />
        </Surface>
      )}

      <View style={styles.coachBand}>
        <Text style={styles.coachTitle}>Ajustes ficam no Coach</Text>
        <Text style={styles.coachText}>Troca de dia, dor, falta de tempo ou foco em um músculo específico podem ser conversados sem refazer o plano inteiro.</Text>
      </View>

      {firstExercise ? (
        <>
          <SectionTitle title="Progressão" meta="próximo alvo" />
          <Surface>
            <InfoRow
              leading={<LabelIcon icon={TrendingUp} />}
              title={firstExercise.name}
              description={`Se completar todas as séries no topo das repetições, próxima meta: ${(loads[firstExercise.id] ?? firstExercise.load) + 2} kg.`}
              trailing={<Tag>+2 kg</Tag>}
            />
            <View style={styles.progressArea}>
              <ProgressBar value={0.68} />
              <Text style={styles.progressText}>2 de 3 critérios cumpridos</Text>
            </View>
          </Surface>
        </>
      ) : null}
    </AppScreen>
  );
}

const createStyles = (palette: AppThemePalette) => StyleSheet.create({
  weekContent: { gap: 8, paddingRight: spacing.xl },
  day: { width: 66, height: 62, borderRadius: radius.md, borderWidth: 1, borderColor: palette.border, backgroundColor: palette.elevated, alignItems: 'center', justifyContent: 'center' },
  dayActive: { borderColor: colors.red, backgroundColor: colors.red },
  dayLabel: { color: palette.muted, fontSize: 10, fontWeight: '900' },
  dayLabelActive: { color: colors.text },
  dayTitle: { width: 54, marginTop: 4, color: palette.faint, fontSize: 10, textAlign: 'center' },
  dayTitleActive: { color: '#F3CBC7' },
  pressed: { opacity: 0.66 },
  programBand: { borderTopWidth: 1, borderBottomWidth: 1, borderColor: palette.border, paddingHorizontal: spacing.xs },
  exerciseList: { borderTopWidth: 1, borderBottomWidth: 1, borderColor: palette.border, paddingHorizontal: spacing.xs },
  exerciseRow: { minHeight: 82, paddingVertical: 12, flexDirection: 'row', alignItems: 'center', gap: 10 },
  exerciseNumber: { width: 28, height: 28, borderRadius: 14, alignItems: 'center', justifyContent: 'center', backgroundColor: colors.redDark },
  exerciseNumberText: { color: colors.text, fontSize: 11, fontWeight: '900' },
  exerciseBody: { flex: 1, minWidth: 0 },
  exerciseName: { color: palette.text, fontSize: 14, fontWeight: '800' },
  exerciseMeta: { marginTop: 4, color: palette.muted, fontSize: 11.5, lineHeight: 16 },
  coachBand: { borderLeftWidth: 4, borderLeftColor: colors.gold, backgroundColor: palette.accentSoft, padding: spacing.lg },
  coachTitle: { color: palette.text, fontSize: 16, fontWeight: '900' },
  coachText: { marginTop: 6, color: palette.accentText, fontSize: 13, lineHeight: 19 },
  progressArea: { marginTop: spacing.md, gap: 8 },
  progressText: { color: palette.muted, fontSize: 11, textAlign: 'right' },
});

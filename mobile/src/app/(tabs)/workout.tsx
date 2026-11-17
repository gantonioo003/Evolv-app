import { useCallback, useState } from "react";
import { Alert, ScrollView, StyleSheet, Text, View } from "react-native";
import { useFocusEffect, useRouter } from "expo-router";
import {
  CalendarRange,
  ChevronRight,
  Dumbbell,
  Info,
  SlidersHorizontal,
  Sparkles,
  TrendingUp,
} from "lucide-react-native";

import { LoadStepper } from "@/components/load-stepper";
import { TouchFeedback as Pressable } from "@/components/touch-feedback";
import {
  ActionButton,
  AppScreen,
  IllustratedHero,
  Divider,
  InfoRow,
  LabelIcon,
  PageHeader,
  ProgressBar,
  SectionTitle,
  Surface,
  Tag,
} from "@/components/ui";
import { artwork, workoutIllustration } from "@/data/illustrations";
import { colors, radius, spacing } from "@/constants/theme";
import { useEvolvData } from "@/context/evolv-data-context";
import { useAppTheme, type AppThemePalette } from "@/context/theme-context";
import { useTrainingPreferences } from "@/context/training-preferences-context";
import { workoutDays } from "@/data/mock-data";
import { trainingFocuses, trainingModalities } from "@/data/training-options";
import { mondayWeekIndex } from "@/lib/local-date";
import type { PlannerModality } from "@/types/api";
import type { Exercise } from "@/types/domain";

type ExerciseEntry = { load_kg?: number; repetitions?: number; duration_seconds?: number };
const exerciseKey = (exercise: Exercise) => exercise.planItemId ?? exercise.id;

const emptyWorkoutDays = workoutDays.map((day) => ({
  ...day,
  title: "Livre",
  durationMinutes: 0,
  status: "rest" as const,
  exercises: [],
}));

export default function WorkoutScreen() {
  const { palette } = useAppTheme();
  const {
    error,
    generateWorkoutPlan,
    isMutating,
    profile,
    progressionSuggestions,
    recordExerciseLoad,
    today,
    workoutPlan,
    workoutWeek,
  } = useEvolvData();
  const { selectedFocusIds, selectedModalityIds } = useTrainingPreferences();
  const styles = createStyles(palette);
  const router = useRouter();
  const displayedWorkoutDays = workoutPlan ? workoutWeek : emptyWorkoutDays;
  const todayLabel = emptyWorkoutDays[mondayWeekIndex(today)].shortLabel;
  const [selectedWeekday, setSelectedWeekday] = useState(todayLabel);
  const [entries, setEntries] = useState<Record<string, ExerciseEntry>>({});
  const [savedEntries, setSavedEntries] = useState<Record<string, ExerciseEntry>>({});
  useFocusEffect(
    useCallback(() => {
      setSelectedWeekday(todayLabel);
    }, [todayLabel]),
  );

  const selectedDay =
    displayedWorkoutDays.find((day) => day.shortLabel === selectedWeekday) ??
    emptyWorkoutDays[mondayWeekIndex(today)];

  const firstExercise = selectedDay.exercises[0];
  const activeModalities = trainingModalities.filter((option) =>
    selectedModalityIds.includes(option.id),
  );
  const activeFocuses = trainingFocuses.filter((option) =>
    selectedFocusIds.includes(option.id),
  );
  const modalitySummary = activeModalities.length
    ? `${activeModalities
        .slice(0, 3)
        .map((option) => option.title)
        .join(
          " + ",
        )}${activeModalities.length > 3 ? ` +${activeModalities.length - 3}` : ""}`
    : "Escolher modalidades";
  const focusSummary = activeFocuses.length
    ? activeFocuses.map((option) => option.title).join(" + ")
    : "Sem foco definido";
  const heroDescription =
    selectedDay.status === "rest"
      ? "Recuperar também faz parte do plano. Hoje não há treino obrigatório."
      : selectedDay.status === "free"
        ? "Dia flexível para reorganizar a semana sem alterar todo o programa."
        : `${selectedDay.exercises.length} exercícios e ${selectedDay.durationMinutes} minutos planejados.`;
  const changedExercises = selectedDay.exercises.filter((exercise) => entries[exerciseKey(exercise)]);
  const firstSuggestion = progressionSuggestions.find(
    (suggestion) => suggestion.exercises.id === firstExercise?.id,
  );

  function editEntry(exercise: Exercise, change: ExerciseEntry) {
    const key = exerciseKey(exercise);
    setEntries((current) => ({ ...current, [key]: { ...savedEntries[key], ...current[key], ...change } }));
  }

  async function saveEntries() {
    try {
      for (const exercise of changedExercises) {
        const key = exerciseKey(exercise);
        const entry = entries[key];
        await recordExerciseLoad(exercise.id, entry);
        setSavedEntries((current) => ({ ...current, [key]: entry }));
        setEntries((current) => {
          if (current[key] !== entry) return current;
          const next = { ...current };
          delete next[key];
          return next;
        });
      }
      Alert.alert(
        "Registros salvos",
        "O histórico foi atualizado sem marcar o treino como concluído.",
      );
    } catch (caught) {
      Alert.alert(
        "Nao foi possivel salvar",
        caught instanceof Error ? caught.message : "Tente novamente.",
      );
    }
  }

  async function createPlan() {
    try {
      const savedDays = profile?.available_training_days ?? [];
      await generateWorkoutPlan({
        available_days: savedDays.length ? savedDays : undefined,
        desired_weekly_frequency: savedDays.length ? undefined : 3,
        session_minutes: 50,
        modalities: selectedModalityIds as PlannerModality[],
        activate: true,
      });
      Alert.alert(
        "Plano criado",
        "O Planner montou e ativou sua primeira semana com dados reais.",
      );
    } catch (caught) {
      Alert.alert(
        "Nao foi possivel criar",
        caught instanceof Error ? caught.message : "Tente novamente.",
      );
    }
  }

  return (
    <AppScreen
      header={
        <PageHeader
          eyebrow={workoutPlan ? "Plano ativo" : "Sem plano ativo"}
          title="Treino"
          actionIcon={CalendarRange}
          actionLabel="Gerenciar planos"
          onAction={() => router.push("/plans")}
        />
      }
    >
      <ScrollView
        horizontal
        showsHorizontalScrollIndicator={false}
        contentContainerStyle={styles.weekContent}
      >
        {displayedWorkoutDays.map((day) => {
          const active = day.shortLabel === selectedDay.shortLabel;
          return (
            <Pressable
              accessibilityRole="button"
              accessibilityState={{ selected: active }}
              key={day.shortLabel}
              onPress={() => setSelectedWeekday(day.shortLabel)}
              style={({ pressed }) => [
                styles.day,
                active && styles.dayActive,
                pressed && styles.pressed,
              ]}
            >
              <Text style={[styles.dayLabel, active && styles.dayLabelActive]}>
                {day.shortLabel}
              </Text>
              <Text
                numberOfLines={1}
                style={[styles.dayTitle, active && styles.dayTitleActive]}
              >
                {day.title.split(" ")[0]}
              </Text>
            </Pressable>
          );
        })}
      </ScrollView>

      <IllustratedHero
        source={workoutPlan ? workoutIllustration(
          selectedDay,
          workoutPlan?.workout_days.find((day) => day.id === selectedDay.id)?.focus,
        ) : artwork.workoutPlan}
        eyebrow={selectedDay.weekday}
        title={selectedDay.title}
        description={heroDescription}
      />

      {!workoutPlan ? (
        <ActionButton
          icon={Sparkles}
          disabled={isMutating}
          onPress={() => void createPlan()}
          label={isMutating ? "Montando plano..." : "Criar plano com o Planner"}
        />
      ) : null}

      <SectionTitle
        title={
          selectedDay.exercises.length ? "Exercícios do dia" : "Plano do dia"
        }
        meta={
          selectedDay.durationMinutes
            ? `${selectedDay.durationMinutes} min`
            : selectedDay.status === "rest"
              ? "descanso"
              : "flexível"
        }
      />

      {selectedDay.exercises.length ? (
        <View style={styles.exerciseList}>
          {selectedDay.exercises.map((exercise, index) => {
            const key = exerciseKey(exercise);
            const entry = entries[key] ?? savedEntries[key];
            const metric = exercise.logMetric ?? "load";
            const measurement = metric === "time" ? entry?.duration_seconds : entry?.repetitions;
            return <View key={key}>
              {index > 0 ? <Divider /> : null}
              <View style={styles.exerciseRow}>
                <View style={styles.exerciseNumber}>
                  <Text style={styles.exerciseNumberText}>{index + 1}</Text>
                </View>
                <View style={styles.exerciseBody}>
                  <Text style={styles.exerciseName}>{exercise.name}</Text>
                  <Text style={styles.exerciseMeta}>
                    {exercise.durationMinutes
                      ? `${exercise.durationMinutes} minutos`
                      : metric === "time"
                        ? "Sustentação por tempo"
                        : `${exercise.sets} séries - ${exercise.reps} reps - ${exercise.restSeconds}s`}
                    {metric === "load" && exercise.load > 0 ? ` · Meta de ${exercise.load} kg` : ""}
                    {exercise.note ? ` - ${exercise.note}` : ""}
                  </Text>
                </View>
                <View style={styles.exerciseActions}>
                  <LoadStepper
                    exerciseName={exercise.name}
                    metric={metric}
                    addedLoad={exercise.loadIsAdded}
                    value={metric === "load" ? entry?.load_kg : measurement}
                    onChange={(value) => editEntry(exercise, metric === "load"
                      ? { load_kg: value }
                      : metric === "time" ? { duration_seconds: value } : { repetitions: value })}
                  />
                  <View style={styles.exerciseExtra}>
                    {metric === "load" ? (
                      <LoadStepper
                        exerciseName={exercise.name}
                        secondary
                        metric="reps"
                        value={entry?.repetitions}
                        onChange={(value) => editEntry(exercise, { repetitions: value })}
                      />
                    ) : null}
                    {metric !== "load" && exercise.canAddLoad ? (
                      <LoadStepper
                        exerciseName={exercise.name}
                        secondary
                        value={entry?.load_kg}
                        onChange={(value) => editEntry(exercise, { load_kg: value })}
                      />
                    ) : null}
                  </View>
                </View>
              </View>
            </View>;
          })}
        </View>
      ) : (
        <Surface>
          <InfoRow
            leading={<LabelIcon icon={Info} />}
            title={
              selectedDay.status === "rest"
                ? "Descanso programado"
                : "Dia flexível"
            }
            description="Nenhum exercício obrigatório. O restante do plano permanece igual."
          />
        </Surface>
      )}

      {changedExercises.length ? (
        <ActionButton
          disabled={isMutating}
          onPress={() => void saveEntries()}
          label={isMutating
            ? "Salvando..."
            : `Salvar ${changedExercises.length} ${changedExercises.length === 1 ? "registro" : "registros"}`}
        />
      ) : null}

      {error ? <Text style={styles.errorText}>{error}</Text> : null}

      {workoutPlan ? (
        <Surface>
          <InfoRow
            leading={<LabelIcon icon={SlidersHorizontal} />}
            title="Ver e editar treino"
            description="Mude o dia ou troque um exercício da ficha."
            trailing={<ChevronRight color={palette.faint} size={18} />}
            onPress={() => router.push({ pathname: "/plans/[planId]", params: { planId: workoutPlan.id } })}
          />
          <Divider />
          <InfoRow
            leading={<LabelIcon icon={Sparkles} />}
            title="Conversar com o Coach"
            description="Peça uma troca ou remarcação pelo chat."
            trailing={<ChevronRight color={palette.faint} size={18} />}
            onPress={() => router.push("/coach")}
          />
        </Surface>
      ) : null}

      <View style={styles.programBand}>
        <InfoRow
          leading={<LabelIcon icon={Dumbbell} />}
          title={workoutPlan?.name ?? "Nenhum plano criado"}
          description={
            workoutPlan
              ? `${workoutPlan.weekly_frequency} treinos por semana - ${workoutPlan.split_label ?? "divisão personalizada"}`
              : "O Planner poderá criar um plano quando você decidir."
          }
          trailing={
            workoutPlan ? <Tag color={colors.green}>Ativo</Tag> : undefined
          }
        />
      </View>

      <SectionTitle title="Modalidades do plano" />
      <Surface>
        <InfoRow
          leading={<LabelIcon icon={SlidersHorizontal} />}
          title={modalitySummary}
          description={focusSummary}
          trailing={<ChevronRight color={palette.faint} size={18} />}
          onPress={() => router.push("/training-preferences")}
        />
      </Surface>

      {firstExercise ? (
        <>
          <SectionTitle title="Progressão" meta="próximo alvo" />
          <Surface>
            <InfoRow
              leading={<LabelIcon icon={TrendingUp} />}
              title={firstExercise.name}
              description={
                firstSuggestion?.reason ??
                `A carga só muda quando você registrar e aceitar uma progressão.`
              }
              trailing={
                firstSuggestion ? (
                  <Tag>{firstSuggestion.suggested_load_kg} kg</Tag>
                ) : (
                  <Tag>Sem pressa</Tag>
                )
              }
            />
            <View style={styles.progressArea}>
              <ProgressBar value={0.68} />
              <Text style={styles.progressText}>
                2 de 3 critérios cumpridos
              </Text>
            </View>
          </Surface>
        </>
      ) : null}
    </AppScreen>
  );
}

const createStyles = (palette: AppThemePalette) =>
  StyleSheet.create({
    weekContent: { gap: 8, paddingRight: spacing.xl },
    day: {
      width: 66,
      height: 62,
      borderRadius: radius.lg,
      borderWidth: 1,
      borderColor: palette.border,
      backgroundColor: palette.elevated,
      alignItems: "center",
      justifyContent: "center",
    },
    dayActive: { borderColor: palette.primary, backgroundColor: palette.primary },
    dayLabel: { color: palette.muted, fontSize: 10, fontWeight: "600" },
    dayLabelActive: { color: palette.onPrimary },
    dayTitle: {
      width: 54,
      marginTop: 4,
      color: palette.faint,
      fontSize: 10,
      textAlign: "center",
    },
    dayTitleActive: { color: palette.onPrimary },
    pressed: { opacity: 0.66 },
    programBand: {
      borderRadius: radius.card,
      backgroundColor: palette.surface,
      borderWidth: StyleSheet.hairlineWidth,
      borderColor: palette.border,
      paddingHorizontal: spacing.lg,
    },
    exerciseList: {
      borderRadius: radius.card,
      backgroundColor: palette.surface,
      borderWidth: StyleSheet.hairlineWidth,
      borderColor: palette.border,
      paddingHorizontal: spacing.md,
    },
    exerciseRow: {
      minHeight: 82,
      paddingVertical: 12,
      flexDirection: "row",
      alignItems: "center",
      gap: 10,
    },
    exerciseNumber: {
      width: 28,
      height: 28,
      borderRadius: 14,
      alignItems: "center",
      justifyContent: "center",
      backgroundColor: palette.sage,
    },
    exerciseNumberText: { color: palette.accentText, fontSize: 11, fontWeight: "600" },
    exerciseBody: { flex: 1, minWidth: 0 },
    exerciseActions: { flexDirection: "row", alignItems: "center", flexShrink: 0 },
    exerciseExtra: { width: 44 },
    exerciseName: { color: palette.text, fontSize: 14, fontWeight: "600" },
    exerciseMeta: {
      marginTop: 4,
      color: palette.muted,
      fontSize: 11.5,
      lineHeight: 16,
    },
    progressArea: { marginTop: spacing.md, gap: 8 },
    progressText: { color: palette.muted, fontSize: 11, textAlign: "right" },
    errorText: {
      color: colors.red,
      fontSize: 12,
      lineHeight: 18,
      textAlign: "center",
    },
  });

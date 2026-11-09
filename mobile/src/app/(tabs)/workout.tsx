import { useMemo, useState } from "react";
import { Alert, ScrollView, StyleSheet, Text, View } from "react-native";
import { useRouter } from "expo-router";
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
  AppScreen,
  CinematicHero,
  Divider,
  InfoRow,
  LabelIcon,
  PageHeader,
  ProgressBar,
  SectionTitle,
  Surface,
  Tag,
} from "@/components/ui";
import { colors, radius, spacing } from "@/constants/theme";
import { useImagePreferences } from "@/context/image-preferences-context";
import { useEvolvData } from "@/context/evolv-data-context";
import { useAppTheme, type AppThemePalette } from "@/context/theme-context";
import { useTrainingPreferences } from "@/context/training-preferences-context";
import {
  mapWorkoutPlanToDays,
  workoutImageCategoryFromText,
} from "@/data/api-mappers";
import { workoutDays } from "@/data/mock-data";
import { pickWeeklyImage, workoutImageLibrary } from "@/data/image-library";
import { trainingFocuses, trainingModalities } from "@/data/training-options";
import type { PlannerModality } from "@/types/api";

const emptyWorkoutDays = workoutDays.map((day) => ({
  ...day,
  title: "Livre",
  durationMinutes: 0,
  status: "rest" as const,
  exercises: [],
}));

export default function WorkoutScreen() {
  const { palette } = useAppTheme();
  const imagePreferences = useImagePreferences();
  const {
    error,
    generateWorkoutPlan,
    isMutating,
    profile,
    progressionSuggestions,
    recordExerciseLoad,
    workoutPlan,
  } = useEvolvData();
  const { selectedFocusIds, selectedModalityIds } = useTrainingPreferences();
  const styles = createStyles(palette);
  const router = useRouter();
  const displayedWorkoutDays = useMemo(
    () => (workoutPlan ? mapWorkoutPlanToDays(workoutPlan) : emptyWorkoutDays),
    [workoutPlan],
  );
  const [selectedDayId, setSelectedDayId] = useState("");
  const [loads, setLoads] = useState<Record<string, number>>({});
  const effectiveSelectedDayId = displayedWorkoutDays.some(
    (day) => day.id === selectedDayId,
  )
    ? selectedDayId
    : (displayedWorkoutDays.find((day) => day.status === "planned")?.id ??
      displayedWorkoutDays[0].id);
  const selectedDay = useMemo(
    () =>
      displayedWorkoutDays.find((day) => day.id === effectiveSelectedDayId) ??
      displayedWorkoutDays[0],
    [displayedWorkoutDays, effectiveSelectedDayId],
  );

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
        : `${selectedDay.exercises.length} exercícios, ${selectedDay.durationMinutes} minutos e cargas prontas para consultar.`;
  const imageCategory =
    selectedDay.status === "rest" || selectedDay.status === "free"
      ? "recovery"
      : workoutImageCategoryFromText(
          `${selectedDay.title} ${workoutPlan?.workout_days.find((day) => day.id === selectedDay.id)?.focus ?? ""}`,
        );
  const heroImage = pickWeeklyImage(
    workoutImageLibrary[imageCategory],
    imagePreferences,
    `workout-${imageCategory}`,
    1,
  );
  const changedExercises = selectedDay.exercises.filter(
    (exercise) =>
      !exercise.durationMinutes &&
      (loads[exercise.id] ?? exercise.load) !== exercise.load,
  );
  const firstSuggestion = progressionSuggestions.find(
    (suggestion) => suggestion.exercises.id === firstExercise?.id,
  );

  async function saveLoads() {
    try {
      await Promise.all(
        changedExercises.map((exercise) =>
          recordExerciseLoad(exercise.id, {
            load_kg: loads[exercise.id] ?? exercise.load,
            sets_completed: exercise.sets,
            reps_summary: exercise.reps,
          }),
        ),
      );
      Alert.alert(
        "Cargas salvas",
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
          const active = day.id === selectedDay.id;
          return (
            <Pressable
              accessibilityRole="button"
              accessibilityState={{ selected: active }}
              key={day.id}
              onPress={() => setSelectedDayId(day.id)}
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

      <CinematicHero
        source={heroImage}
        eyebrow={selectedDay.weekday}
        title={selectedDay.title}
        description={heroDescription}
        height={220}
        overlayOpacity={0.2}
      />

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

      {!workoutPlan ? (
        <Pressable
          accessibilityRole="button"
          disabled={isMutating}
          onPress={() => void createPlan()}
          style={({ pressed }) => [
            styles.plannerButton,
            isMutating && styles.disabled,
            pressed && styles.pressed,
          ]}
        >
          <Sparkles color={colors.text} size={18} />
          <Text style={styles.plannerButtonText}>
            {isMutating ? "Montando plano..." : "Criar plano com o Planner"}
          </Text>
        </Pressable>
      ) : null}

      <SectionTitle title="Modalidades do plano" meta="combináveis" />
      <Surface>
        <InfoRow
          leading={<LabelIcon icon={SlidersHorizontal} />}
          title={modalitySummary}
          description={focusSummary}
          trailing={<ChevronRight color={palette.faint} size={18} />}
          onPress={() => router.push("/training-preferences")}
        />
      </Surface>

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
          {selectedDay.exercises.map((exercise, index) => (
            <View key={exercise.id}>
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
                      : `${exercise.sets} séries - ${exercise.reps} reps - ${exercise.restSeconds}s`}
                    {exercise.note ? ` - ${exercise.note}` : ""}
                  </Text>
                </View>
                {!exercise.durationMinutes ? (
                  <LoadStepper
                    value={loads[exercise.id] ?? exercise.load}
                    onChange={(value) =>
                      setLoads((current) => ({
                        ...current,
                        [exercise.id]: value,
                      }))
                    }
                  />
                ) : null}
              </View>
            </View>
          ))}
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
        <Pressable
          accessibilityRole="button"
          disabled={isMutating}
          onPress={() => void saveLoads()}
          style={({ pressed }) => [
            styles.saveButton,
            isMutating && styles.disabled,
            pressed && styles.pressed,
          ]}
        >
          <Text style={styles.saveButtonText}>
            {isMutating
              ? "Salvando..."
              : `Salvar ${changedExercises.length} ${changedExercises.length === 1 ? "carga" : "cargas"}`}
          </Text>
        </Pressable>
      ) : null}

      {error ? <Text style={styles.errorText}>{error}</Text> : null}

      <View style={styles.coachBand}>
        <Text style={styles.coachTitle}>Ajustes ficam no Coach</Text>
        <Text style={styles.coachText}>
          Troca de dia, dor, falta de tempo ou foco em um músculo específico
          podem ser conversados sem refazer o plano inteiro.
        </Text>
      </View>

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
    dayActive: { borderColor: colors.red, backgroundColor: colors.red },
    dayLabel: { color: palette.muted, fontSize: 10, fontWeight: "600" },
    dayLabelActive: { color: colors.text },
    dayTitle: {
      width: 54,
      marginTop: 4,
      color: palette.faint,
      fontSize: 10,
      textAlign: "center",
    },
    dayTitleActive: { color: "#F3CBC7" },
    pressed: { opacity: 0.66 },
    programBand: {
      borderTopWidth: 1,
      borderBottomWidth: 1,
      borderColor: palette.border,
      paddingHorizontal: spacing.xs,
    },
    exerciseList: {
      borderTopWidth: 1,
      borderBottomWidth: 1,
      borderColor: palette.border,
      paddingHorizontal: spacing.xs,
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
      backgroundColor: colors.redDark,
    },
    exerciseNumberText: { color: colors.text, fontSize: 11, fontWeight: "600" },
    exerciseBody: { flex: 1, minWidth: 0 },
    exerciseName: { color: palette.text, fontSize: 14, fontWeight: "600" },
    exerciseMeta: {
      marginTop: 4,
      color: palette.muted,
      fontSize: 11.5,
      lineHeight: 16,
    },
    coachBand: {
      borderLeftWidth: 4,
      borderLeftColor: colors.red,
      backgroundColor: palette.accentSoft,
      padding: spacing.lg,
    },
    coachTitle: { color: palette.text, fontSize: 16, fontWeight: "600" },
    coachText: {
      marginTop: 6,
      color: palette.accentText,
      fontSize: 13,
      lineHeight: 19,
    },
    progressArea: { marginTop: spacing.md, gap: 8 },
    progressText: { color: palette.muted, fontSize: 11, textAlign: "right" },
    saveButton: {
      height: 50,
      alignItems: "center",
      justifyContent: "center",
      borderRadius: 25,
      backgroundColor: colors.red,
    },
    saveButtonText: { color: colors.text, fontSize: 13, fontWeight: "600" },
    plannerButton: {
      minHeight: 52,
      flexDirection: "row",
      alignItems: "center",
      justifyContent: "center",
      gap: 8,
      borderRadius: 26,
      backgroundColor: colors.red,
    },
    plannerButtonText: {
      color: colors.text,
      fontSize: 13,
      fontWeight: "600",
    },
    errorText: {
      color: colors.red,
      fontSize: 12,
      lineHeight: 18,
      textAlign: "center",
    },
    disabled: { opacity: 0.45 },
  });

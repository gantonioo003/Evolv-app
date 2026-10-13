import { useCallback, useState } from "react";
import { useFocusEffect, useLocalSearchParams, useRouter } from "expo-router";
import {
  Archive,
  ArrowLeft,
  CalendarClock,
  CheckCircle2,
  Dumbbell,
  History,
  Pencil,
} from "lucide-react-native";
import { Alert, Pressable, StyleSheet, Text, View } from "react-native";

import {
  AppScreen,
  Divider,
  InfoRow,
  LabelIcon,
  PageHeader,
  SectionTitle,
  Surface,
  Tag,
} from "@/components/ui";
import {
  SelectionSheet,
  type SelectionOption,
} from "@/components/selection-sheet";
import { colors, spacing } from "@/constants/theme";
import { useEvolvData } from "@/context/evolv-data-context";
import { useAppTheme, type AppThemePalette } from "@/context/theme-context";
import type {
  ExerciseCatalogApi,
  WorkoutDayApi,
  WorkoutDayExerciseApi,
  WorkoutPlanApi,
} from "@/types/api";

const weekdays = [
  { id: "monday", title: "Segunda" },
  { id: "tuesday", title: "Terça" },
  { id: "wednesday", title: "Quarta" },
  { id: "thursday", title: "Quinta" },
  { id: "friday", title: "Sexta" },
  { id: "saturday", title: "Sábado" },
  { id: "sunday", title: "Domingo" },
];

export default function PlanDetailsScreen() {
  const { planId } = useLocalSearchParams<{ planId: string }>();
  const router = useRouter();
  const { palette } = useAppTheme();
  const styles = createStyles(palette);
  const {
    activateWorkoutPlan,
    archiveWorkoutPlan,
    findExerciseAlternatives,
    isMutating,
    loadWorkoutPlan,
    previewPlannerAdjustment,
  } = useEvolvData();
  const [plan, setPlan] = useState<WorkoutPlanApi | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [dayToMove, setDayToMove] = useState<WorkoutDayApi | null>(null);
  const [exerciseToReplace, setExerciseToReplace] =
    useState<WorkoutDayExerciseApi | null>(null);
  const [alternatives, setAlternatives] = useState<ExerciseCatalogApi[]>([]);
  const [loadingAlternatives, setLoadingAlternatives] = useState(false);

  useFocusEffect(
    useCallback(() => {
      if (!planId) return undefined;
      let active = true;
      void loadWorkoutPlan(planId)
        .then((value) => {
          if (active) setPlan(value);
        })
        .catch((caught: unknown) => {
          if (active)
            setError(
              caught instanceof Error ? caught.message : "Plano indisponível.",
            );
        });
      return () => {
        active = false;
      };
    }, [loadWorkoutPlan, planId]),
  );

  async function changeStatus(action: "activate" | "archive") {
    if (!plan) return;
    try {
      const next =
        action === "activate"
          ? await activateWorkoutPlan(plan.id)
          : await archiveWorkoutPlan(plan.id);
      setPlan(next);
      Alert.alert(
        action === "activate" ? "Plano ativado" : "Plano arquivado",
        action === "activate"
          ? "A tela Treino já está usando este plano."
          : "O histórico foi preservado e pode ser reativado depois.",
      );
    } catch (caught) {
      Alert.alert(
        "Nao foi possivel atualizar",
        caught instanceof Error ? caught.message : "Tente novamente.",
      );
    }
  }

  async function previewDayMove(option: SelectionOption) {
    if (!plan || !dayToMove) return;
    try {
      const preview = await previewPlannerAdjustment({
        kind: "move_workout_day",
        reason: "Reorganização manual da semana",
        workout_plan_id: plan.id,
        workout_day_id: dayToMove.id,
        target_weekday: option.id,
      });
      setDayToMove(null);
      router.push(`/adjustments/${preview.id}`);
    } catch (caught) {
      Alert.alert(
        "Nao foi possivel criar a previa",
        caught instanceof Error ? caught.message : "Tente novamente.",
      );
    }
  }

  async function openExerciseReplacement(item: WorkoutDayExerciseApi) {
    setExerciseToReplace(item);
    setLoadingAlternatives(true);
    try {
      const candidates = await findExerciseAlternatives(
        item.exercises.muscle_group,
      );
      setAlternatives(
        candidates.filter((candidate) => candidate.id !== item.exercise_id),
      );
    } catch (caught) {
      Alert.alert(
        "Nao foi possivel buscar alternativas",
        caught instanceof Error ? caught.message : "Tente novamente.",
      );
      setExerciseToReplace(null);
    } finally {
      setLoadingAlternatives(false);
    }
  }

  async function previewExerciseReplacement(option: SelectionOption) {
    if (!plan || !exerciseToReplace) return;
    try {
      const preview = await previewPlannerAdjustment({
        kind: "replace_exercise",
        reason: "Preferência ou disponibilidade de equipamento",
        workout_plan_id: plan.id,
        workout_day_exercise_id: exerciseToReplace.id,
        replacement_exercise_id: option.id,
      });
      setExerciseToReplace(null);
      router.push(`/adjustments/${preview.id}`);
    } catch (caught) {
      Alert.alert(
        "Troca indisponível",
        caught instanceof Error ? caught.message : "Tente outra opção.",
      );
    }
  }

  return (
    <AppScreen>
      <View style={styles.navigationRow}>
        <Pressable
          accessibilityLabel="Voltar"
          accessibilityRole="button"
          onPress={() => router.back()}
          style={({ pressed }) => [
            styles.iconButton,
            pressed && styles.pressed,
          ]}
        >
          <ArrowLeft color={palette.text} size={20} />
        </Pressable>
      </View>

      <PageHeader
        eyebrow="Plano de treino"
        title={plan?.name ?? "Carregando"}
        actionIcon={History}
        actionLabel="Histórico de ajustes"
        onAction={() => router.push("/adjustments")}
      />

      {error ? <Text style={styles.error}>{error}</Text> : null}

      {plan ? (
        <>
          <Surface>
            <InfoRow
              leading={<LabelIcon icon={Dumbbell} />}
              title={plan.split_label ?? "Divisão personalizada"}
              description={`${plan.weekly_frequency} sessões por semana - início ${plan.start_date}`}
              trailing={
                <Tag
                  color={plan.status === "active" ? colors.green : colors.gold}
                >
                  {plan.status === "active"
                    ? "Ativo"
                    : plan.status === "draft"
                      ? "Rascunho"
                      : "Arquivado"}
                </Tag>
              }
            />
          </Surface>

          <View style={styles.actions}>
            {plan.status !== "active" ? (
              <Pressable
                accessibilityRole="button"
                disabled={isMutating}
                onPress={() => void changeStatus("activate")}
                style={({ pressed }) => [
                  styles.primaryButton,
                  isMutating && styles.disabled,
                  pressed && styles.pressed,
                ]}
              >
                <CheckCircle2 color={colors.text} size={18} />
                <Text style={styles.primaryButtonText}>Ativar plano</Text>
              </Pressable>
            ) : null}
            {plan.status !== "archived" ? (
              <Pressable
                accessibilityRole="button"
                disabled={isMutating}
                onPress={() => void changeStatus("archive")}
                style={({ pressed }) => [
                  styles.secondaryButton,
                  isMutating && styles.disabled,
                  pressed && styles.pressed,
                ]}
              >
                <Archive color={palette.text} size={18} />
                <Text style={styles.secondaryButtonText}>Arquivar</Text>
              </Pressable>
            ) : null}
          </View>

          <SectionTitle
            title="Semana"
            meta={`${plan.workout_days.length} dias`}
          />
          <View style={styles.days}>
            {plan.workout_days.map((day) => (
              <Surface key={day.id}>
                <View style={styles.dayHeading}>
                  <View style={styles.dayHeadingText}>
                    <Text style={styles.dayTitle}>{day.title}</Text>
                    <Text style={styles.dayMeta}>
                      {day.weekday} - {day.estimated_minutes ?? 0} min
                    </Text>
                  </View>
                  <View style={styles.dayActions}>
                    <Tag>{day.workout_day_exercises.length} itens</Tag>
                    <Pressable
                      accessibilityLabel={`Mover ${day.title}`}
                      accessibilityRole="button"
                      onPress={() => setDayToMove(day)}
                      style={({ pressed }) => [
                        styles.editButton,
                        pressed && styles.pressed,
                      ]}
                    >
                      <CalendarClock color={palette.text} size={16} />
                    </Pressable>
                  </View>
                </View>
                {day.workout_day_exercises.map((item, index) => (
                  <View key={item.id}>
                    <Divider />
                    <View style={styles.exerciseRow}>
                      <Text style={styles.exercisePosition}>{index + 1}</Text>
                      <View style={styles.exerciseBody}>
                        <Text style={styles.exerciseName}>
                          {item.exercises.name}
                        </Text>
                        <Text style={styles.exerciseMeta}>
                          {item.prescription_kind === "duration"
                            ? `${item.duration_minutes ?? 0} minutos`
                            : `${item.sets ?? 0} x ${item.min_reps ?? 0}-${item.max_reps ?? 0} - ${item.rest_seconds ?? 0}s`}
                        </Text>
                      </View>
                      <Pressable
                        accessibilityLabel={`Trocar ${item.exercises.name}`}
                        accessibilityRole="button"
                        onPress={() => void openExerciseReplacement(item)}
                        style={({ pressed }) => [
                          styles.editButton,
                          pressed && styles.pressed,
                        ]}
                      >
                        <Pencil color={palette.text} size={15} />
                      </Pressable>
                    </View>
                  </View>
                ))}
              </Surface>
            ))}
          </View>
        </>
      ) : null}

      <SelectionSheet
        description="Se já existir outro treino no dia escolhido, os dois trocam de lugar."
        onClose={() => setDayToMove(null)}
        onSelect={(option) => void previewDayMove(option)}
        options={weekdays.filter(
          (weekday) => weekday.id !== dayToMove?.weekday,
        )}
        title={`Mover ${dayToMove?.title ?? "treino"}`}
        visible={Boolean(dayToMove)}
      />
      <SelectionSheet
        description="A prescrição atual será preservada. A compatibilidade é validada antes da prévia."
        loading={loadingAlternatives}
        onClose={() => setExerciseToReplace(null)}
        onSelect={(option) => void previewExerciseReplacement(option)}
        options={alternatives.map((candidate) => ({
          id: candidate.id,
          title: candidate.name,
          description: candidate.equipment ?? "Sem equipamento",
        }))}
        title={`Trocar ${exerciseToReplace?.exercises.name ?? "exercício"}`}
        visible={Boolean(exerciseToReplace)}
      />
    </AppScreen>
  );
}

const createStyles = (palette: AppThemePalette) =>
  StyleSheet.create({
    navigationRow: { height: 40, justifyContent: "center" },
    iconButton: {
      width: 40,
      height: 40,
      alignItems: "center",
      justifyContent: "center",
      borderRadius: 20,
      borderWidth: 1,
      borderColor: palette.border,
      backgroundColor: palette.surface,
    },
    error: { color: colors.red, fontSize: 13, lineHeight: 19 },
    actions: { flexDirection: "row", gap: spacing.sm },
    primaryButton: {
      minHeight: 48,
      flex: 1,
      flexDirection: "row",
      alignItems: "center",
      justifyContent: "center",
      gap: 8,
      borderRadius: 24,
      backgroundColor: colors.red,
    },
    primaryButtonText: {
      color: colors.text,
      fontSize: 13,
      fontWeight: "600",
    },
    secondaryButton: {
      minHeight: 48,
      flex: 1,
      flexDirection: "row",
      alignItems: "center",
      justifyContent: "center",
      gap: 8,
      borderRadius: 24,
      borderWidth: 1,
      borderColor: palette.border,
      backgroundColor: palette.surface,
    },
    secondaryButtonText: {
      color: palette.text,
      fontSize: 13,
      fontWeight: "600",
    },
    days: { gap: spacing.sm },
    dayHeading: {
      flexDirection: "row",
      alignItems: "center",
      justifyContent: "space-between",
      gap: 12,
      padding: spacing.md,
    },
    dayHeadingText: { flex: 1 },
    dayActions: { flexDirection: "row", alignItems: "center", gap: 8 },
    dayTitle: { color: palette.text, fontSize: 15, fontWeight: "600" },
    dayMeta: { marginTop: 4, color: palette.muted, fontSize: 11.5 },
    exerciseRow: {
      minHeight: 64,
      flexDirection: "row",
      alignItems: "center",
      gap: 10,
      paddingHorizontal: spacing.md,
      paddingVertical: spacing.sm,
    },
    exercisePosition: {
      width: 24,
      color: colors.red,
      fontSize: 12,
      fontWeight: "600",
      textAlign: "center",
    },
    exerciseBody: { flex: 1 },
    exerciseName: { color: palette.text, fontSize: 13, fontWeight: "600" },
    exerciseMeta: { marginTop: 3, color: palette.muted, fontSize: 11.5 },
    editButton: {
      width: 36,
      height: 36,
      alignItems: "center",
      justifyContent: "center",
      borderRadius: 18,
      borderWidth: 1,
      borderColor: palette.border,
      backgroundColor: palette.page,
    },
    disabled: { opacity: 0.45 },
    pressed: { opacity: 0.66 },
  });

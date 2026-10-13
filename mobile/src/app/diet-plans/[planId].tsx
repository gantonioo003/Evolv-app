import { useCallback, useState } from "react";
import { useFocusEffect, useLocalSearchParams, useRouter } from "expo-router";
import {
  Archive,
  ArrowLeft,
  CheckCircle2,
  History,
  Pencil,
  Salad,
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
import type { DietPlanApi, MealItemApi } from "@/types/api";

export default function DietPlanDetailsScreen() {
  const { planId } = useLocalSearchParams<{ planId: string }>();
  const router = useRouter();
  const { palette } = useAppTheme();
  const styles = createStyles(palette);
  const {
    activateDietPlan,
    archiveDietPlan,
    isMutating,
    loadDietPlan,
    previewPlannerAdjustment,
  } = useEvolvData();
  const [plan, setPlan] = useState<DietPlanApi | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [itemToReplace, setItemToReplace] = useState<MealItemApi | null>(null);
  const mealGroups = plan ? createMealGroups(plan) : [];

  useFocusEffect(
    useCallback(() => {
      if (!planId) return undefined;
      let active = true;
      void loadDietPlan(planId)
        .then((value) => {
          if (active) setPlan(value);
        })
        .catch((caught: unknown) => {
          if (active)
            setError(
              caught instanceof Error
                ? caught.message
                : "Plano alimentar indisponível.",
            );
        });
      return () => {
        active = false;
      };
    }, [loadDietPlan, planId]),
  );

  async function changeStatus(action: "activate" | "archive") {
    if (!plan) return;
    try {
      const next =
        action === "activate"
          ? await activateDietPlan(plan.id)
          : await archiveDietPlan(plan.id);
      setPlan(next);
      Alert.alert(
        action === "activate" ? "Plano ativado" : "Plano arquivado",
        action === "activate"
          ? "A aba Dieta já está usando este plano."
          : "O plano continua disponível no histórico.",
      );
    } catch (caught) {
      Alert.alert(
        "Nao foi possivel atualizar",
        caught instanceof Error ? caught.message : "Tente novamente.",
      );
    }
  }

  async function previewFoodReplacement(option: SelectionOption) {
    if (!plan || !itemToReplace) return;
    try {
      const preview = await previewPlannerAdjustment({
        kind: "replace_meal_item",
        reason: "Preferência alimentar",
        diet_plan_id: plan.id,
        meal_item_id: itemToReplace.id,
        replacement_food_id: option.id,
      });
      setItemToReplace(null);
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
        eyebrow="Plano alimentar"
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
              leading={<LabelIcon icon={Salad} />}
              title={`${plan.daily_calories_target ?? 0} kcal por dia`}
              description={`${plan.daily_protein_target_g ?? 0}g proteína - ${plan.uses_day_variants ? "treino e descanso" : "mesma meta diária"} - ${plan.menu_rotation_enabled ? `${plan.menu_rotation_size} cardápios em rotação` : "cardápio fixo"}`}
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

          {plan.flexible_meal_frequency !== "none" ||
          plan.alcohol_frequency !== "none" ? (
            <Surface>
              <InfoRow
                leading={<LabelIcon icon={Salad} />}
                title="Flexibilidade planejada"
                description={flexibilityDescription(plan)}
              />
            </Surface>
          ) : null}

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

          {mealGroups.map((group) => (
            <View key={group.key} style={styles.mealGroup}>
              <SectionTitle
                title={group.title}
                meta={`${group.calories ?? 0} kcal - ${group.meals.length} refeições`}
              />
              <View style={styles.meals}>
                {group.meals.map((meal) => (
                  <Surface key={meal.id}>
                    <View style={styles.mealHeading}>
                      <View style={styles.mealHeadingText}>
                        <Text style={styles.mealTitle}>{meal.name}</Text>
                        <Text style={styles.mealMeta}>
                          {meal.meal_time?.slice(0, 5) ?? "Horário livre"} -{" "}
                          {meal.calories_target ?? 0} kcal
                        </Text>
                      </View>
                      <Tag>{meal.protein_target_g ?? 0}g proteína</Tag>
                    </View>
                    {meal.meal_items.map((item, index) => (
                      <View key={item.id}>
                        <Divider />
                        <View style={styles.foodRow}>
                          <Text style={styles.foodPosition}>{index + 1}</Text>
                          <View style={styles.foodBody}>
                            <Text style={styles.foodName}>{item.name}</Text>
                            <Text style={styles.foodMeta}>
                              {item.amount ??
                                `${item.quantity ?? 0} ${item.unit ?? ""}`}{" "}
                              - {Math.round(item.calories_kcal ?? 0)} kcal
                            </Text>
                            {item.substitutions?.length ? (
                              <Text style={styles.substitutionText}>
                                Trocas:{" "}
                                {item.substitutions
                                  .slice(0, 3)
                                  .map((substitution) => substitution.name)
                                  .join(", ")}
                              </Text>
                            ) : null}
                          </View>
                          {item.substitutions?.length ? (
                            <Pressable
                              accessibilityLabel={`Trocar ${item.name}`}
                              accessibilityRole="button"
                              onPress={() => setItemToReplace(item)}
                              style={({ pressed }) => [
                                styles.editButton,
                                pressed && styles.pressed,
                              ]}
                            >
                              <Pencil color={palette.text} size={15} />
                            </Pressable>
                          ) : null}
                        </View>
                      </View>
                    ))}
                  </Surface>
                ))}
              </View>
            </View>
          ))}
        </>
      ) : null}

      <SelectionSheet
        description="A quantidade equivalente já foi calculada pelo Planner. Você verá a prévia antes de confirmar."
        onClose={() => setItemToReplace(null)}
        onSelect={(option) => void previewFoodReplacement(option)}
        options={(itemToReplace?.substitutions ?? []).map((substitution) => ({
          id: substitution.food_id,
          title: substitution.name,
          description: `${substitution.amount} ${substitution.unit} - ${Math.round(substitution.similarity_score * 100)}% de similaridade`,
        }))}
        title={`Trocar ${itemToReplace?.name ?? "alimento"}`}
        visible={Boolean(itemToReplace)}
      />
    </AppScreen>
  );
}

function createMealGroups(plan: DietPlanApi) {
  const dayGroups = plan.uses_day_variants
    ? [
        {
          dayType: "training_day" as const,
          title: "Dias de treino",
          calories: plan.training_day_calories_target,
        },
        {
          dayType: "rest_day" as const,
          title: "Dias de descanso",
          calories: plan.rest_day_calories_target,
        },
      ]
    : [
        {
          dayType: "every_day" as const,
          title: "Todos os dias",
          calories: plan.daily_calories_target,
        },
      ];
  const rotationSize = plan.menu_rotation_enabled ? plan.menu_rotation_size : 1;

  return dayGroups.flatMap((group) =>
    Array.from({ length: rotationSize }, (_, rotationIndex) => ({
      ...group,
      key: `${group.dayType}-${rotationIndex}`,
      title:
        rotationSize > 1
          ? `${group.title} - cardápio ${rotationIndex + 1}`
          : group.title,
      meals: plan.meals.filter(
        (meal) =>
          meal.day_type === group.dayType &&
          meal.rotation_index === rotationIndex,
      ),
    })),
  );
}

function flexibilityDescription(plan: DietPlanApi) {
  const entries: string[] = [];
  if (plan.flexible_meal_frequency !== "none") {
    entries.push(
      `refeição flexível ${frequencyLabel(plan.flexible_meal_frequency)} no ${weekdayLabel(plan.flexible_meal_weekday)}`,
    );
  }
  if (plan.alcohol_frequency !== "none") {
    entries.push(
      `álcool ${frequencyLabel(plan.alcohol_frequency)}, limite de ${plan.alcohol_max_servings ?? 1} porção`,
    );
  }
  return entries.join("; ");
}

function frequencyLabel(value: string) {
  const labels: Record<string, string> = {
    weekly: "semanal",
    fortnightly: "quinzenal",
    monthly: "mensal",
  };
  return labels[value] ?? value;
}

function weekdayLabel(value: string | null) {
  const labels: Record<string, string> = {
    saturday: "sábado",
    sunday: "domingo",
  };
  return labels[value ?? ""] ?? "dia escolhido";
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
    primaryButtonText: { color: colors.text, fontSize: 13, fontWeight: "600" },
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
    meals: { gap: spacing.sm },
    mealGroup: { gap: spacing.sm },
    mealHeading: {
      flexDirection: "row",
      alignItems: "center",
      justifyContent: "space-between",
      gap: 12,
      padding: spacing.md,
    },
    mealHeadingText: { flex: 1 },
    mealTitle: { color: palette.text, fontSize: 15, fontWeight: "600" },
    mealMeta: { marginTop: 4, color: palette.muted, fontSize: 11.5 },
    foodRow: {
      minHeight: 68,
      flexDirection: "row",
      alignItems: "flex-start",
      gap: 10,
      paddingHorizontal: spacing.md,
      paddingVertical: spacing.sm,
    },
    foodPosition: {
      width: 24,
      color: colors.red,
      fontSize: 12,
      fontWeight: "600",
      textAlign: "center",
      paddingTop: 2,
    },
    foodBody: { flex: 1 },
    foodName: { color: palette.text, fontSize: 13, fontWeight: "600" },
    foodMeta: { marginTop: 3, color: palette.muted, fontSize: 11.5 },
    substitutionText: {
      marginTop: 5,
      color: palette.faint,
      fontSize: 10.5,
      lineHeight: 15,
    },
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

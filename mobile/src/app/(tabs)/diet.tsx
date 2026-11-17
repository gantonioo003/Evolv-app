import { useMemo } from "react";
import {
  Alert,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { useRouter } from "expo-router";
import {
  ArrowLeftRight,
  CalendarRange,
  ChevronRight,
  Flame,
  Utensils,
} from "lucide-react-native";
import Svg, { Circle } from "react-native-svg";
import { TouchFeedback as Pressable } from "@/components/touch-feedback";

import {
  IllustrationThumbnail,
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
import { artwork, mealIllustration } from "@/data/illustrations";
import { colors, radius, spacing } from "@/constants/theme";
import { useEvolvData } from "@/context/evolv-data-context";
import { useAppTheme, type AppThemePalette } from "@/context/theme-context";
import { mapDietPlanToMeals } from "@/data/api-mappers";
import { calendarDayIndex, weekdaysFromSunday } from "@/lib/local-date";

const emptyMeals: NonNullable<ReturnType<typeof useEvolvData>["dailyDiet"]>["meals"] = [];

export default function DietScreen() {
  const { palette } = useAppTheme();
  const {
    dietPlan,
    dailyDiet,
    error,
    isMutating,
    nutritionSummary,
    nutritionDayType,
    today,
    todayFoodLogs,
    setMealRegistration,
  } = useEvolvData();
  const styles = createStyles(palette);
  const router = useRouter();
  const visibleMeals = dailyDiet?.meals ?? emptyMeals;
  const meals = useMemo(
    () =>
      dietPlan ? mapDietPlanToMeals({ ...dietPlan, meals: visibleMeals }) : [],
    [dietPlan, visibleMeals],
  );
  const consumedCalories = nutritionSummary?.calories_kcal ?? 0;
  const hasUndetailedLogs = todayFoodLogs.some((log) => log.food_log_items.length === 0);
  const calorieTarget = dailyDiet?.calorieTarget ?? 0;
  const mealTarget = (
    field: "protein_target_g" | "carbohydrate_target_g" | "fat_target_g",
  ) =>
    Math.round(
      visibleMeals.reduce((total, meal) => total + (meal[field] ?? 0), 0),
    );
  const macroData = [
    {
      label: "Proteína",
      current: nutritionSummary?.protein_g ?? 0,
      target: dailyDiet?.proteinTarget ?? 0,
      unit: "g",
      color: palette.macroProtein,
    },
    {
      label: "Carboidratos",
      current: nutritionSummary?.carbohydrate_g ?? 0,
      target: dietPlan?.uses_day_variants
        ? mealTarget("carbohydrate_target_g")
        : (dietPlan?.daily_carbohydrate_target_g ?? 0),
      unit: "g",
      color: palette.macroCarbs,
    },
    {
      label: "Gorduras",
      current: nutritionSummary?.fat_g ?? 0,
      target: dietPlan?.uses_day_variants
        ? mealTarget("fat_target_g")
        : (dietPlan?.daily_fat_target_g ?? 0),
      unit: "g",
      color: palette.macroFat,
    },
  ];
  const flexibleMealToday = Boolean(
    dietPlan &&
    isPlannedForToday(
      today,
      dietPlan.created_at,
      dietPlan.flexible_meal_weekday,
      dietPlan.flexible_meal_frequency,
    ),
  );
  const alcoholToday = Boolean(
    dietPlan &&
    isPlannedForToday(
      today,
      dietPlan.created_at,
      dietPlan.alcohol_preferred_weekday,
      dietPlan.alcohol_frequency,
    ),
  );

  async function toggleMeal(mealId: string, registered: boolean) {
    try {
      await setMealRegistration(mealId, !registered);
    } catch (caught) {
      Alert.alert(
        "Nao foi possivel atualizar",
        caught instanceof Error ? caught.message : "Tente novamente.",
      );
    }
  }

  return (
    <AppScreen
      header={
        <PageHeader
          eyebrow="Alimentação"
          title="Dieta"
          actionIcon={CalendarRange}
          actionLabel="Gerenciar planos alimentares"
          onAction={() => router.push("/diet-plans")}
        />
      }
    >
      <IllustratedHero
        source={dietPlan ? artwork.diet : artwork.mealPlan}
        eyebrow="Plano de hoje"
        title={dietPlan?.name ?? "Seu plano alimentar"}
        description={
          dietPlan
            ? `${visibleMeals.length} refeições para hoje.`
            : "Sem plano ativo para hoje."
        }
      />

      <View style={styles.nutritionFacts}>
        <View style={styles.nutritionFact}>
          <Text style={styles.nutritionValue}>{calorieTarget}</Text>
          <Text style={styles.nutritionLabel}>kcal alvo</Text>
        </View>
        <View style={styles.nutritionDivider} />
        <View style={styles.nutritionFact}>
          <Text style={styles.nutritionValue}>{macroData[0].target} g</Text>
          <Text style={styles.nutritionLabel}>proteína</Text>
        </View>
        <View style={styles.nutritionDivider} />
        <View style={styles.nutritionFact}>
          <Text style={styles.nutritionValue}>
            {String(meals.length).padStart(2, "0")}
          </Text>
          <Text style={styles.nutritionLabel}>refeições</Text>
        </View>
      </View>

      <SectionTitle title="Balanço do dia" meta="estimativa" />
      <Surface style={styles.nutritionCard}>
        <View style={styles.balancePanel}>
          <NutritionDial consumed={consumedCalories} target={calorieTarget} />
          <View style={styles.balanceSummary}>
            <View style={styles.balanceIcon}>
              <LabelIcon icon={Flame} />
            </View>
            <Text style={styles.balanceTitle}>
              {todayFoodLogs.length ? "Registros de hoje" : "Registro opcional"}
            </Text>
            <Text style={styles.balanceDescription}>
              {dietPlan
                ? `${Math.round(consumedCalories)} kcal nos registros com porção. Restam aproximadamente ${Math.max(0, Math.round(calorieTarget - consumedCalories))} kcal.${hasUndetailedLogs ? " Registros sem porção ficam fora do total." : ""}`
                : "Nenhum plano alimentar ativo. Você pode usar somente as outras áreas do Evolv."}
            </Text>
            <Tag color={colors.green}>
              {dietPlan ? "Plano sincronizado" : "Sem cobrança"}
            </Tag>
          </View>
        </View>

        <View style={styles.macroPanel}>
          <View style={styles.macroList}>
            {macroData.map((macro) => (
              <View key={macro.label} style={styles.macroRow}>
                <View style={styles.macroLabels}>
                  <Text style={styles.macroName}>{macro.label}</Text>
                  <Text style={styles.macroValue}>
                    {macro.current.toLocaleString("pt-BR", { maximumFractionDigits: 1 })}/{macro.target}
                    {macro.unit}
                  </Text>
                </View>
                <ProgressBar
                  value={macro.target ? macro.current / macro.target : 0}
                  color={macro.color}
                />
              </View>
            ))}
          </View>
        </View>
      </Surface>

      {flexibleMealToday || alcoholToday ? (
        <>
          <SectionTitle title="Flexibilidade de hoje" meta="já planejada" />
          <Surface>
            <InfoRow
              leading={flexibleMealToday
                ? <IllustrationThumbnail source={artwork.flexibleMeal} />
                : <LabelIcon icon={CalendarRange} />}
              title={
                flexibleMealToday
                  ? "Refeição flexível prevista"
                  : "Bebida planejada para hoje"
              }
              description={
                flexibleMealToday
                  ? "Ela substitui uma refeição do plano. Aproveite sem transformar isso em uma refeição extra."
                  : `Seu limite salvo é de ${dietPlan?.alcohol_max_servings ?? 1} porção. O registro continua opcional.`
              }
            />
          </Surface>
        </>
      ) : null}

      <SectionTitle
        title="Hoje"
        meta={
          dietPlan?.uses_day_variants
            ? nutritionDayType === "training_day"
              ? "dia de treino"
              : "dia de descanso"
            : "registro opcional"
        }
      />
      <Surface>
        {meals.map((meal, index) => {
          const illustration = mealIllustration(meal.title);
          const registered = todayFoodLogs.some(
            (log) => log.planned_meal_id === meal.id,
          );
          return (
            <View key={meal.id}>
              {index > 0 ? <Divider /> : null}
              <InfoRow
                leading={illustration ? <IllustrationThumbnail source={illustration} /> : (
                  <View
                    style={[
                      styles.mealNumber,
                      registered && styles.mealNumberRegistered,
                    ]}
                  >
                    <Text
                      style={[
                        styles.mealNumberText,
                        registered && styles.mealNumberTextRegistered,
                      ]}
                    >
                      {index + 1}
                    </Text>
                  </View>
                )}
                title={meal.title}
                description={`${meal.label} - ${meal.description} - ${meal.protein}g proteína`}
                trailing={
                  <Pressable
                    accessibilityRole="checkbox"
                    accessibilityLabel={`${registered ? "Desmarcar" : "Registrar como planejada"}: ${meal.title}`}
                    accessibilityState={{ checked: registered }}
                    disabled={isMutating}
                    onPress={() => void toggleMeal(meal.id, registered)}
                    style={({ pressed }) => [
                      styles.calorieButton,
                      registered && styles.calorieButtonRegistered,
                      isMutating && styles.disabled,
                      pressed && styles.pressed,
                    ]}
                  >
                    <Text
                      style={[
                        styles.calorieText,
                        registered && styles.calorieTextRegistered,
                      ]}
                    >
                      {registered ? "Registrado" : "Registrar"}
                    </Text>
                  </Pressable>
                }
              />
            </View>
          );
        })}
        {!meals.length ? (
          <InfoRow
            leading={<IllustrationThumbnail source={artwork.mealPlan} />}
            title="Nenhum plano alimentar ativo"
            description="A aba continua disponível e receberá as refeições quando um plano for criado."
          />
        ) : null}
      </Surface>

      {error ? <Text style={styles.errorText}>{error}</Text> : null}

      <SectionTitle title="Ações rápidas" />
      <Surface>
        <InfoRow
          leading={<LabelIcon icon={Utensils} />}
          title={dietPlan ? "Ver e editar dieta" : "Criar plano alimentar"}
          description="Refeições e alimentos"
          trailing={<ChevronRight color={palette.faint} size={18} />}
          onPress={() => dietPlan
            ? router.push({ pathname: "/diet-plans/[planId]", params: { planId: dietPlan.id } })
            : router.push("/diet-plans")}
        />
        <Divider />
        <InfoRow
          leading={<LabelIcon icon={CalendarRange} />}
          title="Gerenciar planos"
          description="Planos ativos e salvos"
          trailing={<ChevronRight color={palette.faint} size={18} />}
          onPress={() => router.push("/diet-plans")}
        />
      </Surface>

      <Pressable
        accessibilityRole="button"
        onPress={() => router.push("/coach")}
        style={({ pressed }) => [styles.coachAction, pressed && styles.pressed]}
      >
        <ArrowLeftRight color={palette.onPrimary} size={20} strokeWidth={2} />
        <View style={styles.coachActionText}>
          <Text style={styles.coachActionTitle}>
            Pedir uma substituição ao Coach
          </Text>
          <Text style={styles.coachActionDescription}>
            Troque um alimento sem refazer o plano inteiro.
          </Text>
        </View>
      </Pressable>

    </AppScreen>
  );
}

function isPlannedForToday(
  date: Date,
  planCreatedAt: string,
  weekday: string | null,
  frequency: string,
) {
  if (!weekday || frequency === "none" || weekdaysFromSunday[date.getDay()] !== weekday) {
    return false;
  }
  if (frequency === "weekly") return true;
  if (frequency === "monthly") return date.getDate() <= 7;
  const created = new Date(planCreatedAt);
  const elapsedDays = Math.max(
    0,
    calendarDayIndex(date) - calendarDayIndex(created),
  );
  return Math.floor(elapsedDays / 7) % 2 === 0;
}

function NutritionDial({
  consumed,
  target,
}: {
  consumed: number;
  target: number;
}) {
  const { palette } = useAppTheme();
  const styles = createStyles(palette);
  const size = 154;
  const stroke = 11;
  const radiusValue = (size - stroke) / 2;
  const circumference = 2 * Math.PI * radiusValue;
  const progress = target > 0 ? Math.min(consumed / target, 1) : 0;

  return (
    <View style={[styles.dial, { width: size, height: size }]}>
      <Svg width={size} height={size}>
        <Circle
          cx={size / 2}
          cy={size / 2}
          r={radiusValue}
          fill="none"
          stroke={palette.border}
          strokeWidth={stroke}
        />
        <Circle
          cx={size / 2}
          cy={size / 2}
          r={radiusValue}
          fill="none"
          transform={`rotate(-90 ${size / 2} ${size / 2})`}
          stroke={palette.macroFat}
          strokeDasharray={`${circumference} ${circumference}`}
          strokeDashoffset={circumference * (1 - progress)}
          strokeLinecap="round"
          strokeWidth={stroke}
        />
      </Svg>
      <View style={styles.dialCopy}>
        <Text style={styles.dialValue}>
          {Math.max(0, Math.round(target - consumed))}
        </Text>
        <Text style={styles.dialLabel}>kcal restantes</Text>
        <Text style={styles.dialMeta}>
          {consumed} / {target}
        </Text>
      </View>
    </View>
  );
}

const createStyles = (palette: AppThemePalette) =>
  StyleSheet.create({
    nutritionFacts: {
      minHeight: 84,
      flexDirection: "row",
      alignItems: "center",
      borderRadius: radius.card,
      borderWidth: StyleSheet.hairlineWidth,
      borderColor: palette.border,
      backgroundColor: palette.surface,
    },
    nutritionFact: { flex: 1, alignItems: "center" },
    nutritionDivider: { width: 1, height: 34, backgroundColor: palette.border },
    nutritionValue: { color: palette.text, fontSize: 20, fontWeight: "600" },
    nutritionLabel: {
      marginTop: 2,
      color: palette.faint,
      fontSize: 9.5,
      fontWeight: "600",
      textTransform: "none",
    },
    nutritionCard: { gap: spacing.lg, padding: spacing.lg },
    balancePanel: {
      minHeight: 156,
      flexDirection: "row",
      alignItems: "center",
      gap: spacing.md,
    },
    dial: { alignItems: "center", justifyContent: "center" },
    dialCopy: {
      position: "absolute",
      inset: 0,
      alignItems: "center",
      justifyContent: "center",
    },
    dialValue: { color: palette.text, fontSize: 27, fontWeight: "600" },
    dialLabel: {
      marginTop: 1,
      color: palette.faint,
      fontSize: 9.5,
      fontWeight: "600",
      textTransform: "none",
    },
    dialMeta: {
      marginTop: 5,
      color: palette.accentText,
      fontSize: 10,
      fontWeight: "600",
    },
    balanceSummary: { flex: 1, alignItems: "flex-start" },
    balanceIcon: { marginBottom: 9 },
    balanceTitle: { color: palette.text, fontSize: 16, fontWeight: "600" },
    balanceDescription: {
      marginTop: 5,
      marginBottom: 10,
      color: palette.faint,
      fontSize: 11.5,
      lineHeight: 17,
    },
    macroPanel: {
      borderTopWidth: StyleSheet.hairlineWidth,
      borderColor: palette.border,
      paddingTop: spacing.lg,
    },
    macroList: { gap: 14 },
    macroRow: { gap: 7 },
    macroLabels: { flexDirection: "row", justifyContent: "space-between" },
    macroName: { color: palette.text, fontSize: 12, fontWeight: "600" },
    macroValue: { color: palette.faint, fontSize: 11, fontWeight: "700" },
    mealNumber: {
      width: 32,
      height: 32,
      borderRadius: 16,
      alignItems: "center",
      justifyContent: "center",
      backgroundColor: palette.iconSurface,
    },
    mealNumberRegistered: { backgroundColor: palette.primary },
    mealNumberText: { color: palette.text, fontSize: 11, fontWeight: "600" },
    mealNumberTextRegistered: { color: colors.text },
    calorieButton: {
      minWidth: 72,
      height: 30,
      alignItems: "center",
      justifyContent: "center",
      borderRadius: 15,
      borderWidth: 1,
      borderColor: palette.border,
      paddingHorizontal: 9,
    },
    calorieButtonRegistered: {
      borderColor: palette.accentSoft,
      backgroundColor: palette.successSoft,
    },
    calorieText: { color: palette.faint, fontSize: 10, fontWeight: "600" },
    calorieTextRegistered: { color: palette.accentText },
    coachAction: {
      minHeight: 72,
      flexDirection: "row",
      alignItems: "center",
      gap: 12,
      borderRadius: radius.lg,
      backgroundColor: palette.primary,
      padding: spacing.lg,
    },
    coachActionText: { flex: 1 },
    coachActionTitle: { color: palette.onPrimary, fontSize: 14, fontWeight: "600" },
    coachActionDescription: { marginTop: 3, color: "#ECF2FF", fontSize: 12 },
    pressed: { opacity: 0.65 },
    disabled: { opacity: 0.45 },
    errorText: {
      color: colors.red,
      fontSize: 12,
      lineHeight: 18,
      textAlign: "center",
    },
  });

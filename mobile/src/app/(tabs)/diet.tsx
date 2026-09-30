import { useMemo } from "react";
import {
  Alert,
  Pressable,
  StyleSheet,
  Text,
  View,
  type ImageSourcePropType,
} from "react-native";
import { useRouter } from "expo-router";
import {
  Apple,
  ArrowLeftRight,
  Flame,
  Search,
  Utensils,
} from "lucide-react-native";
import Svg, { Circle } from "react-native-svg";

import {
  AppScreen,
  CinematicHero,
  CoverImage,
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
import { mapDietPlanToMeals } from "@/data/api-mappers";
import { dietImages, pickWeeklyImage } from "@/data/image-library";

export default function DietScreen() {
  const { palette } = useAppTheme();
  const imagePreferences = useImagePreferences();
  const {
    dietPlan,
    error,
    isMutating,
    nutritionSummary,
    todayFoodLogs,
    toggleMealRegistration,
  } = useEvolvData();
  const styles = createStyles(palette);
  const router = useRouter();
  const meals = useMemo(
    () => (dietPlan ? mapDietPlanToMeals(dietPlan) : []),
    [dietPlan],
  );
  const consumedCalories = nutritionSummary?.calories_kcal ?? 0;
  const calorieTarget = dietPlan?.daily_calories_target ?? 0;
  const macroData = [
    {
      label: "Proteína",
      current: nutritionSummary?.protein_g ?? 0,
      target: dietPlan?.daily_protein_target_g ?? 0,
      unit: "g",
      color: colors.red,
    },
    {
      label: "Carboidratos",
      current: nutritionSummary?.carbohydrate_g ?? 0,
      target: dietPlan?.daily_carbohydrate_target_g ?? 0,
      unit: "g",
      color: colors.gold,
    },
    {
      label: "Gorduras",
      current: nutritionSummary?.fat_g ?? 0,
      target: dietPlan?.daily_fat_target_g ?? 0,
      unit: "g",
      color: colors.green,
    },
  ];

  async function toggleMeal(index: number) {
    const meal = dietPlan?.meals[index];
    if (!meal) return;
    try {
      await toggleMealRegistration(meal);
    } catch (caught) {
      Alert.alert(
        "Nao foi possivel atualizar",
        caught instanceof Error ? caught.message : "Tente novamente.",
      );
    }
  }

  return (
    <AppScreen>
      <PageHeader
        eyebrow="Plano simples"
        title="Dieta"
        actionIcon={Search}
        actionLabel="Buscar alimentos"
        onAction={() =>
          Alert.alert(
            "Busca de alimentos",
            "A busca completa será ligada à fonte nutricional na fase de integração.",
          )
        }
      />

      <CinematicHero
        source={pickWeeklyImage(dietImages, imagePreferences, "diet", 0)}
        eyebrow="Plano de hoje"
        title={"Comer bem.\nSeguir firme."}
        description="Refeições fáceis, troca rápida e metas que você consegue entender."
        meta={dietPlan ? `${calorieTarget} kcal` : "Sem plano ativo"}
      />

      <View style={styles.nutritionFacts}>
        <View style={styles.nutritionFact}>
          <Text style={styles.nutritionValue}>{calorieTarget}</Text>
          <Text style={styles.nutritionLabel}>kcal alvo</Text>
        </View>
        <View style={styles.nutritionDivider} />
        <View style={styles.nutritionFact}>
          <Text style={styles.nutritionValue}>
            {dietPlan?.daily_protein_target_g ?? 0} g
          </Text>
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
      <View style={styles.balancePanel}>
        <NutritionDial consumed={consumedCalories} target={calorieTarget} />
        <View style={styles.balanceSummary}>
          <View style={styles.balanceIcon}>
            <Flame color={colors.red} size={19} strokeWidth={2} />
          </View>
          <Text style={styles.balanceTitle}>
            {todayFoodLogs.length ? "Registros de hoje" : "Registro opcional"}
          </Text>
          <Text style={styles.balanceDescription}>
            {dietPlan
              ? `Foram calculadas ${Math.round(consumedCalories)} kcal nos alimentos detalhados. Restam aproximadamente ${Math.max(0, Math.round(calorieTarget - consumedCalories))} kcal.`
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
                  {macro.current}/{macro.target}
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

      <SectionTitle title="Hoje" meta="registro opcional" />
      <Surface>
        {meals.map((meal, index) => {
          const registered = todayFoodLogs.some(
            (log) => log.meal_name === meal.title,
          );
          return (
            <View key={meal.id}>
              {index > 0 ? <Divider /> : null}
              <InfoRow
                leading={
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
                }
                title={meal.title}
                description={`${meal.label} - ${meal.description} - ${meal.protein}g proteína`}
                trailing={
                  <Pressable
                    accessibilityRole="checkbox"
                    accessibilityState={{ checked: registered }}
                    disabled={isMutating}
                    onPress={() => void toggleMeal(index)}
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
                      {registered ? "Registrado" : `${meal.calories} kcal`}
                    </Text>
                  </Pressable>
                }
              />
            </View>
          );
        })}
        {!meals.length ? (
          <InfoRow
            leading={<LabelIcon icon={Utensils} />}
            title="Nenhum plano alimentar ativo"
            description="A aba continua disponível e receberá as refeições quando um plano for criado."
          />
        ) : null}
      </Surface>

      {error ? <Text style={styles.errorText}>{error}</Text> : null}

      <SectionTitle title="Ações rápidas" meta="sem complicar" />
      <View style={styles.editorialGrid}>
        <EditorialAction
          source={pickWeeklyImage(dietImages, imagePreferences, "diet", 1)}
          eyebrow="Semana"
          title="Preparar refeições"
          onPress={() =>
            Alert.alert(
              "Preparo semanal",
              "O organizador de refeições será conectado ao Planner nas próximas fases.",
            )
          }
        />
        <EditorialAction
          source={pickWeeklyImage(dietImages, imagePreferences, "diet", 2)}
          eyebrow="Substituição"
          title="Trocar alimento"
          onPress={() => router.push("/coach")}
        />
      </View>

      <Pressable
        accessibilityRole="button"
        onPress={() => router.push("/coach")}
        style={({ pressed }) => [styles.coachAction, pressed && styles.pressed]}
      >
        <ArrowLeftRight color={colors.text} size={20} strokeWidth={2} />
        <View style={styles.coachActionText}>
          <Text style={styles.coachActionTitle}>
            Pedir uma substituição ao Coach
          </Text>
          <Text style={styles.coachActionDescription}>
            Troque um alimento sem refazer o plano inteiro.
          </Text>
        </View>
      </Pressable>

      <SectionTitle title="Base da semana" meta="lista principal" />
      <Surface>
        <InfoRow
          leading={<LabelIcon icon={Apple} />}
          title="Alimentos principais"
          description="Arroz, feijão, ovos, frango, carne magra, aveia, frutas, legumes e iogurte."
        />
        <Divider />
        <InfoRow
          leading={<LabelIcon icon={Utensils} />}
          title="Regra do plano"
          description="Ajustes pequenos preservam a rotina e tornam a dieta mais fácil de manter."
        />
      </Surface>
    </AppScreen>
  );
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
          stroke={colors.red}
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

function EditorialAction({
  source,
  eyebrow,
  title,
  onPress,
}: {
  source: ImageSourcePropType;
  eyebrow: string;
  title: string;
  onPress: () => void;
}) {
  const { palette } = useAppTheme();
  const styles = createStyles(palette);

  return (
    <Pressable
      accessibilityRole="button"
      onPress={onPress}
      style={({ pressed }) => [
        styles.editorialAction,
        pressed && styles.pressed,
      ]}
    >
      <View style={styles.editorialBackground}>
        <CoverImage source={source} style={styles.editorialImage} />
        <View style={styles.editorialWash} />
        <View style={styles.editorialCopy}>
          <Text style={styles.editorialEyebrow}>{eyebrow}</Text>
          <Text style={styles.editorialTitle}>{title}</Text>
        </View>
      </View>
    </Pressable>
  );
}

const createStyles = (palette: AppThemePalette) =>
  StyleSheet.create({
    nutritionFacts: {
      minHeight: 84,
      flexDirection: "row",
      alignItems: "center",
      borderTopWidth: 1,
      borderBottomWidth: 1,
      borderColor: palette.border,
    },
    nutritionFact: { flex: 1, alignItems: "center" },
    nutritionDivider: { width: 1, height: 34, backgroundColor: palette.border },
    nutritionValue: { color: palette.text, fontSize: 20, fontWeight: "900" },
    nutritionLabel: {
      marginTop: 2,
      color: palette.faint,
      fontSize: 9.5,
      fontWeight: "800",
      textTransform: "uppercase",
    },
    balancePanel: {
      minHeight: 178,
      flexDirection: "row",
      alignItems: "center",
      gap: spacing.lg,
      borderTopWidth: 1,
      borderBottomWidth: 1,
      borderColor: palette.border,
      paddingVertical: spacing.md,
    },
    dial: { alignItems: "center", justifyContent: "center" },
    dialCopy: {
      position: "absolute",
      inset: 0,
      alignItems: "center",
      justifyContent: "center",
    },
    dialValue: { color: palette.text, fontSize: 27, fontWeight: "900" },
    dialLabel: {
      marginTop: 1,
      color: palette.faint,
      fontSize: 9.5,
      fontWeight: "800",
      textTransform: "uppercase",
    },
    dialMeta: {
      marginTop: 5,
      color: colors.red,
      fontSize: 10,
      fontWeight: "900",
    },
    balanceSummary: { flex: 1, alignItems: "flex-start" },
    balanceIcon: {
      width: 38,
      height: 38,
      marginBottom: 9,
      borderRadius: 19,
      alignItems: "center",
      justifyContent: "center",
      backgroundColor: palette.iconSurface,
    },
    balanceTitle: { color: palette.text, fontSize: 16, fontWeight: "900" },
    balanceDescription: {
      marginTop: 5,
      marginBottom: 10,
      color: palette.faint,
      fontSize: 11.5,
      lineHeight: 17,
    },
    macroPanel: {
      borderBottomWidth: 1,
      borderColor: palette.border,
      paddingBottom: spacing.lg,
    },
    macroList: { gap: 14 },
    macroRow: { gap: 7 },
    macroLabels: { flexDirection: "row", justifyContent: "space-between" },
    macroName: { color: palette.text, fontSize: 12, fontWeight: "800" },
    macroValue: { color: palette.faint, fontSize: 11, fontWeight: "700" },
    mealNumber: {
      width: 32,
      height: 32,
      borderRadius: 16,
      alignItems: "center",
      justifyContent: "center",
      backgroundColor: palette.iconSurface,
    },
    mealNumberRegistered: { backgroundColor: colors.green },
    mealNumberText: { color: palette.text, fontSize: 11, fontWeight: "900" },
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
      borderColor: colors.green,
      backgroundColor: palette.successSoft,
    },
    calorieText: { color: palette.faint, fontSize: 10, fontWeight: "800" },
    calorieTextRegistered: { color: colors.green },
    editorialGrid: { gap: spacing.sm },
    editorialAction: {
      width: "100%",
      height: 150,
      overflow: "hidden",
      borderRadius: radius.lg,
      backgroundColor: colors.ink,
    },
    editorialBackground: { flex: 1, justifyContent: "flex-end" },
    editorialImage: {
      position: "absolute",
      inset: 0,
      width: "100%",
      height: "100%",
      borderRadius: radius.lg,
    },
    editorialWash: {
      position: "absolute",
      inset: 0,
      zIndex: 1,
      backgroundColor: "rgba(5, 6, 8, 0.38)",
    },
    editorialCopy: { zIndex: 2, padding: spacing.md },
    editorialEyebrow: {
      color: colors.gold,
      fontSize: 9,
      fontWeight: "900",
      textTransform: "uppercase",
    },
    editorialTitle: {
      marginTop: 3,
      color: colors.text,
      fontSize: 14,
      lineHeight: 17,
      fontWeight: "900",
    },
    coachAction: {
      minHeight: 72,
      flexDirection: "row",
      alignItems: "center",
      gap: 12,
      borderRadius: radius.lg,
      backgroundColor: colors.red,
      padding: spacing.lg,
    },
    coachActionText: { flex: 1 },
    coachActionTitle: { color: colors.text, fontSize: 14, fontWeight: "900" },
    coachActionDescription: { marginTop: 3, color: "#EBC7C2", fontSize: 12 },
    pressed: { opacity: 0.65 },
    disabled: { opacity: 0.45 },
    errorText: {
      color: colors.red,
      fontSize: 12,
      lineHeight: 18,
      textAlign: "center",
    },
  });

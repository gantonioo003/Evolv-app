import { useState } from "react";
import { useRouter } from "expo-router";
import { ArrowLeft, ChevronRight, Salad, Sparkles } from "lucide-react-native";
import {
  Alert,
  Pressable,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";

import {
  AppScreen,
  InfoRow,
  LabelIcon,
  PageHeader,
  SectionTitle,
  Surface,
  Tag,
} from "@/components/ui";
import { colors, radius, spacing } from "@/constants/theme";
import { useEvolvData } from "@/context/evolv-data-context";
import { useAppTheme, type AppThemePalette } from "@/context/theme-context";
import type { NutritionFoodStyle, NutritionMacroPattern } from "@/types/api";

const foodStyles: { id: NutritionFoodStyle; label: string }[] = [
  { id: "omnivore", label: "Onívoro" },
  { id: "pescatarian", label: "Pescetariano" },
  { id: "vegetarian", label: "Vegetariano" },
  { id: "vegan", label: "Vegano" },
];

const macroPatterns: { id: NutritionMacroPattern; label: string }[] = [
  { id: "balanced", label: "Equilibrado" },
  { id: "high_carb_performance", label: "Alto carbo" },
  { id: "low_carb", label: "Low carb" },
  { id: "ketogenic", label: "Cetogênico" },
];

const statusLabel: Record<string, string> = {
  active: "Ativo",
  draft: "Rascunho",
  archived: "Arquivado",
};

export default function DietPlansScreen() {
  const router = useRouter();
  const { palette } = useAppTheme();
  const styles = createStyles(palette);
  const { dietPlans, generateDietPlan, isMutating, profile } = useEvolvData();
  const [foodStyle, setFoodStyle] = useState<NutritionFoodStyle>("omnivore");
  const [macroPattern, setMacroPattern] =
    useState<NutritionMacroPattern>("balanced");
  const [mealCount, setMealCount] = useState(4);
  const [useDayVariants, setUseDayVariants] = useState(false);
  const [menuRotationSize, setMenuRotationSize] = useState(3);
  const [flexibleMealFrequency, setFlexibleMealFrequency] = useState<
    "none" | "weekly" | "fortnightly"
  >("none");
  const [flexibleMealWeekday, setFlexibleMealWeekday] = useState("saturday");
  const [alcoholFrequency, setAlcoholFrequency] = useState<
    "none" | "fortnightly" | "monthly"
  >("none");
  const [calorieTarget, setCalorieTarget] = useState("");

  async function generate() {
    const normalizedTarget = calorieTarget.trim().replace(",", ".");
    const target = normalizedTarget ? Number(normalizedTarget) : undefined;
    if (
      target !== undefined &&
      (!Number.isFinite(target) || target < 800 || target > 8000)
    ) {
      Alert.alert("Meta inválida", "Informe um valor entre 800 e 8000 kcal.");
      return;
    }
    if (
      target === undefined &&
      (!profile?.current_weight_kg || !profile.height_cm || !profile.birth_date)
    ) {
      Alert.alert(
        "Faltam dados para estimar",
        "Informe uma meta de calorias nesta tela ou complete peso, altura e nascimento na sua conta.",
      );
      return;
    }

    try {
      const plan = await generateDietPlan({
        calorie_target_override: target,
        food_style: foodStyle,
        macro_pattern: macroPattern,
        meals_per_day: mealCount,
        use_training_rest_variants: useDayVariants,
        training_day_meals: useDayVariants ? mealCount : undefined,
        rest_day_meals: useDayVariants ? Math.max(1, mealCount - 1) : undefined,
        rotate_menus: menuRotationSize > 1,
        menu_rotation_size: menuRotationSize,
        flexible_meal_frequency: flexibleMealFrequency,
        flexible_meal_weekday:
          flexibleMealFrequency === "none" ? undefined : flexibleMealWeekday,
        alcohol_frequency: alcoholFrequency,
        alcohol_preferred_weekday:
          alcoholFrequency === "none" ? undefined : flexibleMealWeekday,
        alcohol_max_servings: alcoholFrequency === "none" ? undefined : 1,
        activate: true,
      });
      router.push(`/diet-plans/${plan.id}`);
    } catch (caught) {
      Alert.alert(
        "Nao foi possivel gerar",
        caught instanceof Error ? caught.message : "Tente novamente.",
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

      <PageHeader eyebrow="Planner nutricional" title="Planos alimentares" />
      <Text style={styles.intro}>
        Escolha a estrutura. Suas restrições e alimentos rejeitados salvos na
        conta são aplicados automaticamente.
      </Text>

      <SectionTitle title="Novo plano" meta="preferências" />
      <Surface>
        <View style={styles.formSection}>
          <Text style={styles.formLabel}>Estilo alimentar</Text>
          <View style={styles.options}>
            {foodStyles.map((option) => (
              <Option
                active={foodStyle === option.id}
                key={option.id}
                label={option.label}
                onPress={() => setFoodStyle(option.id)}
              />
            ))}
          </View>
        </View>
        <View style={styles.formDivider} />
        <View style={styles.formSection}>
          <Text style={styles.formLabel}>Variedade dos cardápios</Text>
          <Text style={styles.formHint}>
            O Evolv recomenda variar, mas uma rotina fixa também é válida.
          </Text>
          <View style={styles.options}>
            <Option
              active={menuRotationSize === 1}
              label="Fixo"
              onPress={() => setMenuRotationSize(1)}
            />
            <Option
              active={menuRotationSize === 3}
              label="Rotação de 3"
              onPress={() => setMenuRotationSize(3)}
            />
            <Option
              active={menuRotationSize === 7}
              label="Cada dia da semana"
              onPress={() => setMenuRotationSize(7)}
            />
          </View>
        </View>
        <View style={styles.formDivider} />
        <View style={styles.formSection}>
          <Text style={styles.formLabel}>Distribuição</Text>
          <View style={styles.options}>
            {macroPatterns.map((option) => (
              <Option
                active={macroPattern === option.id}
                key={option.id}
                label={option.label}
                onPress={() => setMacroPattern(option.id)}
              />
            ))}
          </View>
        </View>
        <View style={styles.formDivider} />
        <View style={styles.formSection}>
          <Text style={styles.formLabel}>Organização da semana</Text>
          <Text style={styles.formHint}>
            Você decide se as refeições mudam conforme houver treino.
          </Text>
          <View style={styles.options}>
            <Option
              active={!useDayVariants}
              label="Mesma dieta todos os dias"
              onPress={() => setUseDayVariants(false)}
            />
            <Option
              active={useDayVariants}
              label="Treino e descanso diferentes"
              onPress={() => setUseDayVariants(true)}
            />
          </View>
        </View>
        <View style={styles.formDivider} />
        <View style={styles.formSection}>
          <Text style={styles.formLabel}>
            {useDayVariants
              ? "Refeições no dia de treino"
              : "Refeições por dia"}
          </Text>
          {useDayVariants ? (
            <Text style={styles.formHint}>
              No descanso serão {Math.max(1, mealCount - 1)} refeições. A média
              semanal de calorias é preservada.
            </Text>
          ) : null}
          <View style={styles.options}>
            {[3, 4, 5, 6].map((count) => (
              <Option
                active={mealCount === count}
                key={count}
                label={String(count)}
                onPress={() => setMealCount(count)}
              />
            ))}
          </View>
        </View>
        <View style={styles.formDivider} />
        <View style={styles.formSection}>
          <Text style={styles.formLabel}>Refeição flexível planejada</Text>
          <Text style={styles.formHint}>
            Ela substitui uma refeição do dia; não é uma refeição extra.
          </Text>
          <View style={styles.options}>
            <Option
              active={flexibleMealFrequency === "none"}
              label="Nenhuma"
              onPress={() => setFlexibleMealFrequency("none")}
            />
            <Option
              active={flexibleMealFrequency === "weekly"}
              label="Semanal"
              onPress={() => setFlexibleMealFrequency("weekly")}
            />
            <Option
              active={flexibleMealFrequency === "fortnightly"}
              label="Quinzenal"
              onPress={() => setFlexibleMealFrequency("fortnightly")}
            />
          </View>
          {flexibleMealFrequency !== "none" ? (
            <View style={styles.options}>
              <Option
                active={flexibleMealWeekday === "saturday"}
                label="Sábado"
                onPress={() => setFlexibleMealWeekday("saturday")}
              />
              <Option
                active={flexibleMealWeekday === "sunday"}
                label="Domingo"
                onPress={() => setFlexibleMealWeekday("sunday")}
              />
            </View>
          ) : null}
        </View>
        <View style={styles.formDivider} />
        <View style={styles.formSection}>
          <Text style={styles.formLabel}>Bebida alcoólica planejada</Text>
          <Text style={styles.formHint}>
            Opcional. O Planner não recomenda álcool automaticamente.
          </Text>
          <View style={styles.options}>
            <Option
              active={alcoholFrequency === "none"}
              label="Não incluir"
              onPress={() => setAlcoholFrequency("none")}
            />
            <Option
              active={alcoholFrequency === "fortnightly"}
              label="Quinzenal"
              onPress={() => setAlcoholFrequency("fortnightly")}
            />
            <Option
              active={alcoholFrequency === "monthly"}
              label="Mensal"
              onPress={() => setAlcoholFrequency("monthly")}
            />
          </View>
        </View>
        <View style={styles.formDivider} />
        <View style={styles.targetRow}>
          <View style={styles.targetCopy}>
            <Text style={styles.formLabel}>Meta conhecida</Text>
            <Text style={styles.formHint}>
              Opcional quando seu perfil possui os dados para estimativa.
            </Text>
          </View>
          <View style={styles.targetInputGroup}>
            <TextInput
              accessibilityLabel="Meta diária de calorias"
              keyboardType="number-pad"
              onChangeText={setCalorieTarget}
              placeholder="Ex.: 2200"
              placeholderTextColor={palette.faint}
              style={styles.targetInput}
              value={calorieTarget}
            />
            <Text style={styles.targetUnit}>kcal</Text>
          </View>
        </View>
      </Surface>

      <Pressable
        accessibilityRole="button"
        disabled={isMutating}
        onPress={() => void generate()}
        style={({ pressed }) => [
          styles.primaryButton,
          isMutating && styles.disabled,
          pressed && styles.pressed,
        ]}
      >
        <Sparkles color={colors.text} size={18} />
        <Text style={styles.primaryButtonText}>
          {isMutating ? "Montando refeições..." : "Gerar e ativar plano"}
        </Text>
      </Pressable>

      <SectionTitle title="Histórico" meta={`${dietPlans.length} planos`} />
      <View style={styles.list}>
        {dietPlans.map((plan) => (
          <Surface key={plan.id}>
            <InfoRow
              leading={<LabelIcon icon={Salad} />}
              title={plan.name}
              description={`${plan.daily_calories_target ?? 0} kcal - ${plan.uses_day_variants ? "treino e descanso" : "todos os dias"} - ${plan.menu_rotation_enabled ? `${plan.menu_rotation_size} cardápios` : "cardápio fixo"}`}
              trailing={
                <View style={styles.trailing}>
                  <Tag
                    color={
                      plan.status === "active" ? colors.green : colors.gold
                    }
                  >
                    {statusLabel[plan.status] ?? plan.status}
                  </Tag>
                  <ChevronRight color={palette.faint} size={18} />
                </View>
              }
              onPress={() => router.push(`/diet-plans/${plan.id}`)}
            />
          </Surface>
        ))}
        {!dietPlans.length ? (
          <Surface>
            <InfoRow
              leading={<LabelIcon icon={Salad} />}
              title="Nenhum plano criado"
              description="Seu primeiro plano aparecerá aqui sem apagar o histórico futuro."
            />
          </Surface>
        ) : null}
      </View>
    </AppScreen>
  );
}

function Option({
  active,
  label,
  onPress,
}: {
  active: boolean;
  label: string;
  onPress: () => void;
}) {
  const { palette } = useAppTheme();
  const styles = createStyles(palette);
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityState={{ selected: active }}
      onPress={onPress}
      style={({ pressed }) => [
        styles.option,
        active && styles.optionActive,
        pressed && styles.pressed,
      ]}
    >
      <Text style={[styles.optionText, active && styles.optionTextActive]}>
        {label}
      </Text>
    </Pressable>
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
    intro: { color: palette.muted, fontSize: 13, lineHeight: 19 },
    formSection: { gap: 10, padding: spacing.md },
    formLabel: { color: palette.text, fontSize: 12.5, fontWeight: "900" },
    formHint: { marginTop: 3, color: palette.faint, fontSize: 10.5 },
    formDivider: { height: 1, backgroundColor: palette.border },
    options: { flexDirection: "row", flexWrap: "wrap", gap: 8 },
    option: {
      minHeight: 34,
      justifyContent: "center",
      borderRadius: 17,
      borderWidth: 1,
      borderColor: palette.border,
      paddingHorizontal: 12,
    },
    optionActive: { borderColor: colors.red, backgroundColor: colors.red },
    optionText: { color: palette.muted, fontSize: 11, fontWeight: "800" },
    optionTextActive: { color: colors.text },
    targetRow: {
      flexDirection: "row",
      alignItems: "center",
      gap: 12,
      padding: spacing.md,
    },
    targetCopy: { flex: 1 },
    targetInputGroup: {
      width: 128,
      height: 42,
      flexDirection: "row",
      alignItems: "center",
      borderWidth: 1,
      borderColor: palette.border,
      borderRadius: radius.md,
      paddingHorizontal: 10,
    },
    targetInput: { flex: 1, color: palette.text, fontSize: 12.5 },
    targetUnit: { color: palette.faint, fontSize: 10, fontWeight: "800" },
    primaryButton: {
      minHeight: 52,
      flexDirection: "row",
      alignItems: "center",
      justifyContent: "center",
      gap: 8,
      borderRadius: radius.lg,
      backgroundColor: colors.red,
    },
    primaryButtonText: { color: colors.text, fontSize: 13, fontWeight: "900" },
    list: { gap: spacing.sm },
    trailing: { flexDirection: "row", alignItems: "center", gap: 8 },
    disabled: { opacity: 0.45 },
    pressed: { opacity: 0.66 },
  });

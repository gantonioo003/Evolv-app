import { useMemo, useState } from "react";
import { useRouter } from "expo-router";
import {
  ArrowLeft,
  ArrowRight,
  Check,
  ChevronRight,
} from "lucide-react-native";
import { Alert, Pressable, StyleSheet, Text, View } from "react-native";

import { AppScreen } from "@/components/ui";
import { colors, radius, spacing } from "@/constants/theme";
import { useEvolvData } from "@/context/evolv-data-context";
import { useAppTheme, type AppThemePalette } from "@/context/theme-context";
import type { GoalType } from "@/types/api";

const goalByAnswer: Record<string, { type: GoalType; title: string }> = {
  "Ganhar massa": { type: "hypertrophy", title: "Ganhar massa" },
  "Perder gordura": { type: "fat_loss", title: "Perder gordura" },
  Recomposição: { type: "recomposition", title: "Recomposição corporal" },
  "Manter a rotina": { type: "maintenance", title: "Manter a rotina" },
};

const steps = [
  {
    title: "Qual seu objetivo?",
    description:
      "Isso ajuda o Planner a organizar o início. Você pode alterar depois.",
    options: [
      "Ganhar massa",
      "Perder gordura",
      "Recomposição",
      "Manter a rotina",
    ],
  },
  {
    title: "Como é sua semana?",
    description: "Escolha uma referência inicial. Nenhum dia vira obrigação.",
    options: ["3 treinos", "4 treinos", "5 treinos", "Prefiro decidir depois"],
  },
  {
    title: "Onde você treina?",
    description:
      "As preferências orientam sugestões, mas a biblioteca continua completa.",
    options: [
      "Academia completa",
      "Só máquinas",
      "Peso livre",
      "Casa ou calistenia",
    ],
  },
  {
    title: "Quanto quer preencher?",
    description:
      "Peso, medidas, restrições e alimentação são opcionais e ficam disponíveis na Conta.",
    options: ["Completar agora", "Completar depois"],
  },
];

export default function OnboardingScreen() {
  const { palette } = useAppTheme();
  const styles = createStyles(palette);
  const router = useRouter();
  const { activeGoal, createGoal, isMutating, updateProfile } = useEvolvData();
  const [step, setStep] = useState(0);
  const [answers, setAnswers] = useState<Record<number, string>>({});
  const current = steps[step];
  const selected = answers[step];
  const isLast = step === steps.length - 1;
  const progressLabel = useMemo(() => `${step + 1} de ${steps.length}`, [step]);

  async function finish(skipped: boolean) {
    try {
      const goal = goalByAnswer[answers[0]];
      if (!activeGoal && goal) {
        await createGoal({
          ...goal,
          description: [answers[1], answers[2]].filter(Boolean).join(" - "),
        });
      }
      await updateProfile({
        onboarding_status: skipped ? "skipped" : "completed",
      });
      router.replace("/(tabs)");
    } catch (error) {
      Alert.alert(
        "Nao foi possivel salvar",
        error instanceof Error ? error.message : "Tente novamente.",
      );
    }
  }

  function advance() {
    if (isLast) void finish(false);
    else setStep((currentStep) => currentStep + 1);
  }

  function skip() {
    void finish(true);
  }

  return (
    <AppScreen>
      <View style={styles.topBar}>
        <Pressable
          accessibilityLabel="Voltar"
          accessibilityRole="button"
          disabled={step === 0}
          onPress={() => setStep((currentStep) => Math.max(0, currentStep - 1))}
          style={[styles.iconButton, step === 0 && styles.backDisabled]}
        >
          <ArrowLeft color={palette.text} size={20} />
        </Pressable>
        <Text style={styles.brand}>Evolv</Text>
        <Pressable
          accessibilityRole="button"
          disabled={isMutating}
          onPress={skip}
          style={styles.skipButton}
        >
          <Text style={styles.skipText}>Pular tudo</Text>
        </Pressable>
      </View>

      <View style={styles.stepper}>
        {steps.map((_, index) => (
          <View
            key={index}
            style={[styles.step, index <= step && styles.stepActive]}
          />
        ))}
      </View>

      <View style={styles.heading}>
        <Text style={styles.progressLabel}>{progressLabel}</Text>
        <Text style={styles.title}>{current.title}</Text>
        <Text style={styles.description}>{current.description}</Text>
      </View>

      <View style={styles.options}>
        {current.options.map((option) => {
          const active = selected === option;
          return (
            <Pressable
              accessibilityRole="radio"
              accessibilityState={{ checked: active }}
              key={option}
              onPress={() =>
                setAnswers((currentAnswers) => ({
                  ...currentAnswers,
                  [step]: option,
                }))
              }
              style={({ pressed }) => [
                styles.option,
                active && styles.optionActive,
                pressed && styles.pressed,
              ]}
            >
              <View style={styles.optionText}>
                <Text
                  style={[
                    styles.optionTitle,
                    active && styles.optionTitleActive,
                  ]}
                >
                  {option}
                </Text>
                <Text style={styles.optionMeta}>
                  Pode ser alterado depois em Conta.
                </Text>
              </View>
              {active ? (
                <Check color={colors.text} size={18} />
              ) : (
                <ChevronRight color={palette.faint} size={18} />
              )}
            </Pressable>
          );
        })}
      </View>

      <Pressable
        accessibilityRole="button"
        disabled={isMutating}
        onPress={advance}
        style={({ pressed }) => [
          styles.continueButton,
          isMutating && styles.disabled,
          pressed && styles.pressed,
        ]}
      >
        <Text style={styles.continueText}>
          {isMutating
            ? "Salvando..."
            : isLast
              ? "Entrar no Evolv"
              : "Continuar"}
        </Text>
        <ArrowRight color={colors.text} size={18} />
      </Pressable>
      <Text style={styles.optional}>
        Todas as respostas desta etapa são opcionais.
      </Text>
    </AppScreen>
  );
}

const createStyles = (palette: AppThemePalette) =>
  StyleSheet.create({
    topBar: {
      height: 52,
      flexDirection: "row",
      alignItems: "center",
      justifyContent: "space-between",
    },
    iconButton: {
      width: 40,
      height: 40,
      alignItems: "center",
      justifyContent: "center",
      borderRadius: 20,
      borderWidth: 1,
      borderColor: palette.border,
    },
    backDisabled: { opacity: 0.25 },
    brand: {
      color: palette.text,
      fontSize: 20,
      fontWeight: "900",
      textTransform: "uppercase",
    },
    skipButton: {
      minWidth: 76,
      height: 40,
      alignItems: "center",
      justifyContent: "center",
    },
    skipText: { color: colors.red, fontSize: 12, fontWeight: "900" },
    stepper: { height: 4, flexDirection: "row", gap: 5 },
    step: { flex: 1, borderRadius: 2, backgroundColor: palette.border },
    stepActive: { backgroundColor: colors.red },
    heading: { marginTop: spacing.lg, gap: 8 },
    progressLabel: {
      color: colors.gold,
      fontSize: 11,
      fontWeight: "900",
      textTransform: "uppercase",
    },
    title: {
      maxWidth: 330,
      color: palette.text,
      fontSize: 32,
      lineHeight: 36,
      fontWeight: "900",
    },
    description: {
      maxWidth: 380,
      color: palette.faint,
      fontSize: 14,
      lineHeight: 20,
    },
    options: { gap: 10 },
    option: {
      minHeight: 74,
      flexDirection: "row",
      alignItems: "center",
      gap: 12,
      borderRadius: radius.lg,
      borderWidth: 1,
      borderColor: palette.border,
      backgroundColor: palette.surface,
      padding: 16,
    },
    optionActive: { borderColor: colors.red, backgroundColor: colors.red },
    optionText: { flex: 1 },
    optionTitle: { color: palette.text, fontSize: 15, fontWeight: "900" },
    optionTitleActive: { color: colors.text },
    optionMeta: { marginTop: 4, color: palette.muted, fontSize: 11.5 },
    continueButton: {
      height: 52,
      flexDirection: "row",
      alignItems: "center",
      justifyContent: "center",
      gap: 8,
      borderRadius: radius.lg,
      backgroundColor: colors.red,
    },
    continueText: { color: colors.text, fontSize: 14, fontWeight: "900" },
    optional: { color: palette.faint, fontSize: 11, textAlign: "center" },
    disabled: { opacity: 0.45 },
    pressed: { opacity: 0.66 },
  });

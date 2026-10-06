import { useRouter } from "expo-router";
import {
  ArrowLeft,
  CalendarDays,
  ChevronRight,
  Plus,
} from "lucide-react-native";
import { Alert, Pressable, StyleSheet, Text, View } from "react-native";

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
import { useTrainingPreferences } from "@/context/training-preferences-context";
import type { PlannerModality } from "@/types/api";

const statusLabel: Record<string, string> = {
  active: "Ativo",
  draft: "Rascunho",
  archived: "Arquivado",
};

export default function PlansScreen() {
  const router = useRouter();
  const { palette } = useAppTheme();
  const styles = createStyles(palette);
  const { selectedModalityIds } = useTrainingPreferences();
  const { generateWorkoutPlan, isMutating, profile, workoutPlans } =
    useEvolvData();

  async function generate() {
    try {
      const savedDays = profile?.available_training_days ?? [];
      const plan = await generateWorkoutPlan({
        available_days: savedDays.length ? savedDays : undefined,
        desired_weekly_frequency: savedDays.length ? undefined : 3,
        session_minutes: 50,
        modalities: selectedModalityIds as PlannerModality[],
        activate: true,
      });
      router.push(`/plans/${plan.id}`);
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

      <PageHeader
        eyebrow="Planner"
        title="Seus planos"
        actionIcon={Plus}
        actionLabel="Gerar novo plano"
        onAction={() => void generate()}
      />

      <Text style={styles.intro}>
        Um plano ativo por vez. Os anteriores permanecem arquivados para
        consulta e podem ser reativados.
      </Text>

      <SectionTitle title="Histórico" meta={`${workoutPlans.length} planos`} />

      {workoutPlans.length ? (
        <View style={styles.list}>
          {workoutPlans.map((plan) => (
            <Surface key={plan.id}>
              <InfoRow
                leading={<LabelIcon icon={CalendarDays} />}
                title={plan.name}
                description={`${plan.weekly_frequency}x por semana - ${plan.split_label ?? "Divisão personalizada"}`}
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
                onPress={() => router.push(`/plans/${plan.id}`)}
              />
            </Surface>
          ))}
        </View>
      ) : (
        <Surface>
          <InfoRow
            leading={<LabelIcon icon={CalendarDays} />}
            title="Nenhum plano criado"
            description="O primeiro plano será montado com suas preferências atuais."
          />
        </Surface>
      )}

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
        <Plus color={colors.text} size={18} />
        <Text style={styles.primaryButtonText}>
          {isMutating ? "Gerando..." : "Gerar novo plano"}
        </Text>
      </Pressable>
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
    intro: { color: palette.muted, fontSize: 13, lineHeight: 19 },
    list: { gap: spacing.sm },
    trailing: { flexDirection: "row", alignItems: "center", gap: 8 },
    primaryButton: {
      minHeight: 52,
      flexDirection: "row",
      alignItems: "center",
      justifyContent: "center",
      gap: 8,
      borderRadius: radius.lg,
      backgroundColor: colors.red,
    },
    primaryButtonText: {
      color: colors.text,
      fontSize: 13,
      fontWeight: "900",
    },
    disabled: { opacity: 0.45 },
    pressed: { opacity: 0.66 },
  });

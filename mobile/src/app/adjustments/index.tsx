import { useCallback, useEffect, useState } from "react";
import { useRouter } from "expo-router";
import { ArrowLeft, ChevronRight, History } from "lucide-react-native";
import { Pressable, StyleSheet, Text, View } from "react-native";

import {
  AppScreen,
  InfoRow,
  LabelIcon,
  PageHeader,
  Surface,
  Tag,
} from "@/components/ui";
import { colors, spacing } from "@/constants/theme";
import { useEvolvData } from "@/context/evolv-data-context";
import { useAppTheme, type AppThemePalette } from "@/context/theme-context";
import type { PlannerAdjustmentApi } from "@/types/api";

export default function PlannerAdjustmentsScreen() {
  const router = useRouter();
  const { palette } = useAppTheme();
  const styles = createStyles(palette);
  const { listPlannerAdjustments } = useEvolvData();
  const [items, setItems] = useState<PlannerAdjustmentApi[]>([]);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    void listPlannerAdjustments()
      .then(setItems)
      .catch((caught: unknown) =>
        setError(
          caught instanceof Error ? caught.message : "Histórico indisponível.",
        ),
      );
  }, [listPlannerAdjustments]);

  useEffect(load, [load]);

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
      <PageHeader eyebrow="Planner" title="Histórico de ajustes" />
      <Text style={styles.intro}>
        Prévias, confirmações e alterações desfeitas ficam reunidas aqui.
      </Text>
      {error ? <Text style={styles.error}>{error}</Text> : null}

      <View style={styles.list}>
        {items.map((item) => (
          <Surface key={item.id}>
            <InfoRow
              leading={<LabelIcon icon={History} />}
              title={item.preview?.title ?? adjustmentLabel(item)}
              description={item.preview?.summary ?? item.reason}
              trailing={
                <View style={styles.trailing}>
                  <Tag color={statusColor(item)}>{statusLabel(item)}</Tag>
                  <ChevronRight color={palette.faint} size={18} />
                </View>
              }
              onPress={() => router.push(`/adjustments/${item.id}`)}
            />
          </Surface>
        ))}
        {!items.length && !error ? (
          <Surface>
            <InfoRow
              leading={<LabelIcon icon={History} />}
              title="Nenhum ajuste ainda"
              description="As mudanças só aparecem aqui depois que você cria uma prévia."
            />
          </Surface>
        ) : null}
      </View>
    </AppScreen>
  );
}

function adjustmentLabel(item: PlannerAdjustmentApi) {
  const labels = {
    move_workout_day: "Mudança de dia",
    replace_exercise: "Troca de exercício",
    replace_meal_item: "Troca de alimento",
    set_day_activity: "Atividade do dia",
  };
  return item.adjustment_kind ? labels[item.adjustment_kind] : "Ajuste antigo";
}

function statusLabel(item: PlannerAdjustmentApi) {
  if (item.reverted_at) return "Desfeito";
  if (item.status === "applied") return "Aplicado";
  if (item.status === "rejected") return "Descartado";
  return "Pendente";
}

function statusColor(item: PlannerAdjustmentApi) {
  if (item.reverted_at || item.status === "rejected") return colors.gold;
  if (item.status === "applied") return colors.green;
  return colors.red;
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
    error: { color: colors.red, fontSize: 12 },
    list: { gap: spacing.sm },
    trailing: { flexDirection: "row", alignItems: "center", gap: 8 },
    pressed: { opacity: 0.58 },
  });

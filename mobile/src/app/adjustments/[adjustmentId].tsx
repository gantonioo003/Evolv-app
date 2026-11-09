import { useEffect, useState } from "react";
import { useLocalSearchParams, useRouter } from "expo-router";
import {
  ArrowLeft,
  Check,
  RotateCcw,
  ShieldCheck,
  X,
} from "lucide-react-native";
import { Alert, Pressable, StyleSheet, Text, View } from "react-native";

import {
  AppScreen,
  PageHeader,
  SectionTitle,
  Surface,
  Tag,
} from "@/components/ui";
import { colors, spacing } from "@/constants/theme";
import { useEvolvData } from "@/context/evolv-data-context";
import { useAuth } from "@/context/auth-context";
import { useAppTheme, type AppThemePalette } from "@/context/theme-context";
import type { PlannerAdjustmentApi } from "@/types/api";

export default function PlannerAdjustmentDetailsScreen() {
  const { adjustmentId } = useLocalSearchParams<{ adjustmentId: string }>();
  const router = useRouter();
  const { session, isLoading: isAuthLoading } = useAuth();
  const { palette } = useAppTheme();
  const styles = createStyles(palette);
  const {
    applyPlannerAdjustment,
    isMutating,
    loadPlannerAdjustment,
    rejectPlannerAdjustment,
    revertPlannerAdjustment,
  } = useEvolvData();
  const [adjustment, setAdjustment] = useState<PlannerAdjustmentApi | null>(
    null,
  );
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!adjustmentId || isAuthLoading || !session?.access_token) return;
    let active = true;
    void loadPlannerAdjustment(adjustmentId)
      .then((value) => {
        if (active) {
          setAdjustment(value);
          setError(null);
        }
      })
      .catch(
        (caught: unknown) =>
          active &&
          setError(
            caught instanceof Error ? caught.message : "Prévia indisponível.",
          ),
      );
    return () => {
      active = false;
    };
  }, [adjustmentId, loadPlannerAdjustment, isAuthLoading, session?.access_token]);

  async function mutate(action: "apply" | "reject" | "revert") {
    if (!adjustment) return;
    try {
      const next =
        action === "apply"
          ? await applyPlannerAdjustment(adjustment.id)
          : action === "reject"
            ? await rejectPlannerAdjustment(adjustment.id)
            : await revertPlannerAdjustment(adjustment.id);
      setAdjustment(next);
      Alert.alert(
        action === "apply"
          ? "Alteração aplicada"
          : action === "reject"
            ? "Prévia descartada"
            : "Alteração desfeita",
        "O histórico foi preservado.",
      );
    } catch (caught) {
      Alert.alert(
        "Nao foi possivel concluir",
        caught instanceof Error ? caught.message : "Tente novamente.",
      );
    }
  }

  const preview = adjustment ? normalizePreview(adjustment) : null;
  const pending = adjustment?.status === "pending";
  const canRevert = Boolean(
    adjustment?.status === "applied" &&
    adjustment.reversible &&
    !adjustment.reverted_at,
  );

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
        eyebrow="Prévia controlada"
        title={preview?.title ?? "Carregando ajuste"}
      />
      {error ? <Text style={styles.error}>{error}</Text> : null}

      {adjustment && preview ? (
        <>
          <Surface>
            <View style={styles.summary}>
              <View style={styles.summaryTop}>
                <ShieldCheck color={colors.green} size={22} />
                <Tag color={statusColor(adjustment)}>
                  {statusLabel(adjustment)}
                </Tag>
              </View>
              <Text style={styles.summaryText}>{preview.summary}</Text>
              <Text style={styles.reason}>Motivo: {adjustment.reason}</Text>
            </View>
          </Surface>

          <PreviewList title="O que muda" items={preview.changes} />
          <PreviewList title="O que permanece" items={preview.preserved} />
          {preview.warnings.length ? (
            <PreviewList title="Observações" items={preview.warnings} />
          ) : null}

          <View style={styles.actions}>
            {pending ? (
              <>
                <Pressable
                  accessibilityRole="button"
                  disabled={isMutating}
                  onPress={() => void mutate("reject")}
                  style={({ pressed }) => [
                    styles.secondaryButton,
                    pressed && styles.pressed,
                  ]}
                >
                  <X color={palette.text} size={18} />
                  <Text style={styles.secondaryText}>Descartar</Text>
                </Pressable>
                <Pressable
                  accessibilityRole="button"
                  disabled={isMutating}
                  onPress={() => void mutate("apply")}
                  style={({ pressed }) => [
                    styles.primaryButton,
                    pressed && styles.pressed,
                  ]}
                >
                  <Check color={colors.text} size={18} />
                  <Text style={styles.primaryText}>Confirmar</Text>
                </Pressable>
              </>
            ) : null}
            {canRevert ? (
              <Pressable
                accessibilityRole="button"
                disabled={isMutating}
                onPress={() => void mutate("revert")}
                style={({ pressed }) => [
                  styles.secondaryButton,
                  pressed && styles.pressed,
                ]}
              >
                <RotateCcw color={palette.text} size={18} />
                <Text style={styles.secondaryText}>Desfazer alteração</Text>
              </Pressable>
            ) : null}
          </View>
        </>
      ) : null}
    </AppScreen>
  );
}

function normalizePreview(item: PlannerAdjustmentApi) {
  const preview = item.preview as Partial<PlannerAdjustmentApi["preview"]>;
  return {
    title: preview?.title ?? "Ajuste do Planner",
    summary: preview?.summary ?? item.reason,
    changes: Array.isArray(preview?.changes) ? preview.changes : [],
    preserved: Array.isArray(preview?.preserved) ? preview.preserved : [],
    warnings: Array.isArray(preview?.warnings) ? preview.warnings : [],
  };
}

function PreviewList({ items, title }: { items: string[]; title: string }) {
  const { palette } = useAppTheme();
  const styles = createStyles(palette);
  if (!items.length) return null;
  return (
    <View>
      <SectionTitle title={title} />
      <Surface>
        <View style={styles.list}>
          {items.map((item) => (
            <View key={item} style={styles.listRow}>
              <View style={styles.dot} />
              <Text style={styles.listText}>{item}</Text>
            </View>
          ))}
        </View>
      </Surface>
    </View>
  );
}

function statusLabel(item: PlannerAdjustmentApi) {
  if (item.reverted_at) return "Desfeito";
  if (item.status === "applied") return "Aplicado";
  if (item.status === "rejected") return "Descartado";
  return "Aguardando confirmação";
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
    error: { color: colors.red, fontSize: 12 },
    summary: { gap: 10, padding: spacing.lg },
    summaryTop: {
      flexDirection: "row",
      alignItems: "center",
      justifyContent: "space-between",
    },
    summaryText: {
      color: palette.text,
      fontSize: 16,
      lineHeight: 23,
      fontWeight: "600",
    },
    reason: { color: palette.muted, fontSize: 11.5, lineHeight: 17 },
    list: { gap: 12, padding: spacing.md },
    listRow: { flexDirection: "row", alignItems: "flex-start", gap: 10 },
    dot: {
      width: 6,
      height: 6,
      marginTop: 6,
      borderRadius: 3,
      backgroundColor: colors.red,
    },
    listText: { flex: 1, color: palette.text, fontSize: 12.5, lineHeight: 18 },
    actions: { flexDirection: "row", gap: spacing.sm },
    primaryButton: {
      minHeight: 50,
      flex: 1,
      flexDirection: "row",
      alignItems: "center",
      justifyContent: "center",
      gap: 8,
      borderRadius: 24,
      backgroundColor: colors.red,
    },
    primaryText: { color: colors.text, fontSize: 12.5, fontWeight: "600" },
    secondaryButton: {
      minHeight: 50,
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
    secondaryText: { color: palette.text, fontSize: 12.5, fontWeight: "600" },
    pressed: { opacity: 0.58 },
  });

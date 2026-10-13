import { useMemo, useState } from "react";
import { useRouter } from "expo-router";
import {
  ArrowLeft,
  Camera,
  Dumbbell,
  Ruler,
  Save,
  Scale,
  TrendingUp,
} from "lucide-react-native";
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
  CinematicHero,
  Divider,
  InfoRow,
  LabelIcon,
  Metric,
  ProgressBar,
  SectionTitle,
  Surface,
  Tag,
} from "@/components/ui";
import { colors, spacing } from "@/constants/theme";
import { useEvolvData } from "@/context/evolv-data-context";
import { useAppTheme, type AppThemePalette } from "@/context/theme-context";

export default function ProgressScreen() {
  const { palette } = useAppTheme();
  const {
    addProgressEntry,
    isMutating,
    profile,
    progressEntries,
    progressionSuggestions,
  } = useEvolvData();
  const styles = createStyles(palette);
  const router = useRouter();
  const [weight, setWeight] = useState("");
  const latest = progressEntries[0];
  const previous = progressEntries.find(
    (entry) => entry.weight_kg !== null && entry.id !== latest?.id,
  );
  const currentWeight = latest?.weight_kg ?? profile?.current_weight_kg ?? null;
  const weightDelta =
    currentWeight !== null &&
    previous?.weight_kg !== null &&
    previous?.weight_kg !== undefined
      ? currentWeight - previous.weight_kg
      : null;
  const recentEntries = useMemo(() => {
    const threshold = new Date();
    threshold.setDate(threshold.getDate() - 30);
    return progressEntries.filter(
      (entry) => new Date(`${entry.measured_at}T00:00:00`) >= threshold,
    );
  }, [progressEntries]);

  async function saveWeight() {
    const value = Number(weight.replace(",", "."));
    if (!Number.isFinite(value) || value < 25 || value > 350) {
      Alert.alert("Peso inválido", "Informe um valor entre 25 e 350 kg.");
      return;
    }
    try {
      await addProgressEntry({ weight_kg: value });
      setWeight("");
      Alert.alert(
        "Progresso salvo",
        "O novo peso foi adicionado ao seu histórico.",
      );
    } catch (caught) {
      Alert.alert(
        "Nao foi possivel salvar",
        caught instanceof Error ? caught.message : "Tente novamente.",
      );
    }
  }

  return (
    <AppScreen>
      <View style={styles.header}>
        <Pressable
          accessibilityLabel="Voltar"
          accessibilityRole="button"
          onPress={() => router.back()}
          style={({ pressed }) => [
            styles.backButton,
            pressed && styles.pressed,
          ]}
        >
          <ArrowLeft color={palette.text} size={21} />
        </Pressable>
        <View style={styles.headerText}>
          <Text style={styles.eyebrow}>Conta</Text>
          <Text style={styles.title}>Progresso</Text>
        </View>
      </View>

      <CinematicHero
        source={require("@/assets/images/progress-history.png")}
        eyebrow="Últimos 30 dias"
        title={"Evolução\nconsistente"}
        description="Cargas, medidas e fotos opcionais organizadas sem transformar progresso em cobrança."
        height={240}
        overlayOpacity={0.18}
      />

      <View style={styles.metrics}>
        <Metric
          value={currentWeight === null ? "--" : `${currentWeight} kg`}
          label="peso atual"
        />
        <Metric
          value={String(recentEntries.length)}
          label="registros em 30 dias"
        />
      </View>

      <SectionTitle title="Novo registro" meta="opcional" />
      <Surface>
        <View style={styles.entryRow}>
          <View style={styles.weightInputGroup}>
            <Scale color={palette.muted} size={18} />
            <TextInput
              keyboardType="decimal-pad"
              onChangeText={setWeight}
              placeholder="Peso atual"
              placeholderTextColor={palette.faint}
              style={styles.weightInput}
              value={weight}
            />
            <Text style={styles.weightUnit}>kg</Text>
          </View>
          <Pressable
            accessibilityLabel="Salvar peso"
            accessibilityRole="button"
            disabled={isMutating}
            onPress={() => void saveWeight()}
            style={({ pressed }) => [
              styles.saveButton,
              isMutating && styles.disabled,
              pressed && styles.pressed,
            ]}
          >
            <Save color={colors.text} size={18} />
          </Pressable>
        </View>
      </Surface>

      <SectionTitle title="Visão geral" meta="30 dias" />
      <Surface>
        <InfoRow
          leading={<LabelIcon icon={TrendingUp} />}
          title={`${recentEntries.length} registros nos últimos 30 dias`}
          description="Você escolhe quando registrar; não há cobrança diária."
          trailing={<Tag color={colors.green}>Sincronizado</Tag>}
        />
        <Divider />
        <InfoRow
          leading={<LabelIcon icon={Scale} />}
          title={
            currentWeight === null
              ? "Peso ainda não registrado"
              : `Peso atual ${currentWeight} kg`
          }
          description={
            weightDelta === null
              ? "Adicione outro registro quando quiser comparar."
              : `Variação de ${weightDelta >= 0 ? "+" : ""}${weightDelta.toFixed(1)} kg entre os registros mais recentes.`
          }
        />
        <Divider />
        <InfoRow
          leading={<LabelIcon icon={Ruler} />}
          title="Medidas opcionais"
          description={`${progressEntries.filter((entry) => entry.waist_cm || entry.chest_cm || entry.arm_cm || entry.leg_cm).length} registros possuem medidas corporais.`}
        />
      </Surface>

      <SectionTitle title="Cargas" meta="comparação" />
      <Surface>
        {progressionSuggestions.map((item, index) => (
          <View key={item.id}>
            {index > 0 ? <Divider /> : null}
            <View style={styles.loadRow}>
              <View style={styles.loadTitleRow}>
                <View style={styles.loadName}>
                  <Dumbbell color={colors.red} size={17} />
                  <Text style={styles.loadLabel}>{item.exercises.name}</Text>
                </View>
                <Text style={styles.loadValue}>
                  {item.current_load_kg} kg → {item.suggested_load_kg} kg
                </Text>
              </View>
              <ProgressBar
                value={
                  item.suggested_load_kg
                    ? item.current_load_kg / item.suggested_load_kg
                    : 0
                }
                color={colors.red}
              />
            </View>
          </View>
        ))}
        {!progressionSuggestions.length ? (
          <InfoRow
            leading={<LabelIcon icon={Dumbbell} />}
            title="Sem sugestão pendente"
            description="O app só sugere progressão quando houver histórico suficiente."
          />
        ) : null}
      </Surface>

      <SectionTitle title="Fotos" meta="opcional" />
      <Surface>
        <InfoRow
          leading={<LabelIcon icon={Camera} />}
          title="Nenhuma foto adicionada"
          description="Fotos nunca serão obrigatórias. Você decide se quer acompanhar desta forma."
        />
      </Surface>
    </AppScreen>
  );
}

const createStyles = (palette: AppThemePalette) =>
  StyleSheet.create({
    header: {
      minHeight: 76,
      flexDirection: "row",
      alignItems: "center",
      gap: spacing.md,
    },
    backButton: {
      width: 44,
      height: 44,
      borderRadius: 22,
      borderWidth: 1,
      borderColor: palette.border,
      backgroundColor: palette.surface,
      alignItems: "center",
      justifyContent: "center",
    },
    headerText: { flex: 1 },
    eyebrow: {
      color: colors.red,
      fontSize: 11,
      fontWeight: "600",
      textTransform: "none",
    },
    title: {
      marginTop: 1,
      color: palette.text,
      fontSize: 30,
      fontWeight: "600",
      textTransform: "none",
    },
    metrics: { flexDirection: "row", gap: spacing.md },
    loadRow: { minHeight: 76, justifyContent: "center", gap: 10 },
    loadTitleRow: {
      flexDirection: "row",
      alignItems: "center",
      justifyContent: "space-between",
      gap: 10,
    },
    loadName: { flex: 1, flexDirection: "row", alignItems: "center", gap: 8 },
    loadLabel: { color: palette.text, fontSize: 13, fontWeight: "600" },
    loadValue: { color: palette.faint, fontSize: 11, fontWeight: "600" },
    entryRow: {
      minHeight: 58,
      flexDirection: "row",
      alignItems: "center",
      gap: 10,
    },
    weightInputGroup: {
      flex: 1,
      minHeight: 48,
      flexDirection: "row",
      alignItems: "center",
      gap: 8,
      borderWidth: 1,
      borderColor: palette.border,
      borderRadius: 8,
      paddingHorizontal: 12,
    },
    weightInput: {
      flex: 1,
      color: palette.text,
      fontSize: 14,
      paddingVertical: 11,
    },
    weightUnit: { color: palette.faint, fontSize: 12, fontWeight: "600" },
    saveButton: {
      width: 48,
      height: 48,
      alignItems: "center",
      justifyContent: "center",
      borderRadius: 8,
      backgroundColor: colors.red,
    },
    disabled: { opacity: 0.45 },
    pressed: { opacity: 0.65 },
  });

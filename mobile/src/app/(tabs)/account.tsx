import { Alert, Pressable, StyleSheet, Text, View } from "react-native";
import { useRouter } from "expo-router";
import {
  Bell,
  BrainCircuit,
  CalendarDays,
  Camera,
  ChartNoAxesCombined,
  ChevronRight,
  ClipboardList,
  Dumbbell,
  Goal,
  HeartPulse,
  Settings2,
  Utensils,
} from "lucide-react-native";

import {
  AppScreen,
  CinematicHero,
  Divider,
  InfoRow,
  LabelIcon,
  PageHeader,
  ProgressBar,
  SectionTitle,
  Surface,
} from "@/components/ui";
import { colors, spacing } from "@/constants/theme";
import { useImagePreferences } from "@/context/image-preferences-context";
import { useEvolvData } from "@/context/evolv-data-context";
import { useAppTheme, type AppThemePalette } from "@/context/theme-context";
import { useTrainingPreferences } from "@/context/training-preferences-context";
import { trainingModalities } from "@/data/training-options";
import { accountImages, pickWeeklyImage } from "@/data/image-library";

export default function AccountScreen() {
  const { palette } = useAppTheme();
  const imagePreferences = useImagePreferences();
  const {
    activeGoal,
    dietPlan,
    error,
    profile,
    progressEntries,
    progressionSuggestions,
    workoutPlan,
  } = useEvolvData();
  const { selectedModalityIds } = useTrainingPreferences();
  const styles = createStyles(palette);
  const router = useRouter();
  const showPlaceholder = (title: string) =>
    Alert.alert(
      title,
      "Esta área será conectada aos seus dados nas próximas fases.",
    );
  const activeModalities = trainingModalities.filter((option) =>
    selectedModalityIds.includes(option.id),
  );
  const trainingSummary = activeModalities.length
    ? `${activeModalities
        .slice(0, 3)
        .map((option) => option.title)
        .join(
          ", ",
        )}${activeModalities.length > 3 ? ` e mais ${activeModalities.length - 3}` : ""}`
    : "Modalidades ainda não definidas";
  const displayName = profile?.full_name?.trim() || "Seu perfil";
  const trainingLevel =
    profile?.training_level === "beginner"
      ? "Iniciante"
      : profile?.training_level === "intermediate"
        ? "Intermediário"
        : profile?.training_level === "advanced"
          ? "Avançado"
          : "Nível não definido";
  const latestProgress = progressEntries[0];

  return (
    <AppScreen>
      <PageHeader
        eyebrow="Espaço pessoal"
        title="Conta"
        actionIcon={Settings2}
        actionLabel="Abrir configurações"
        onAction={() => router.push("/settings")}
      />

      <CinematicHero
        source={pickWeeklyImage(accountImages, imagePreferences, "account", 0)}
        eyebrow="Plano ativo"
        title={displayName}
        description="Seu plano, preferências, histórico e privacidade reunidos em um só lugar."
        height={230}
        overlayOpacity={0.08}
      />

      <View style={styles.goalBand}>
        <InfoRow
          leading={<LabelIcon icon={Goal} />}
          title={activeGoal?.title ?? "Objetivo não definido"}
          description={`${trainingLevel} - ${workoutPlan?.weekly_frequency ?? 0} treinos por semana`}
          trailing={<ChevronRight color={palette.faint} size={18} />}
          onPress={() => showPlaceholder("Objetivo atual")}
        />
      </View>

      <SectionTitle title="Progresso" meta="últimos 30 dias" />
      <Pressable
        accessibilityRole="button"
        onPress={() => router.push("/progress")}
        style={({ pressed }) => [
          styles.progressSummary,
          pressed && styles.pressed,
        ]}
      >
        <View style={styles.progressTop}>
          <View style={styles.progressCopy}>
            <Text style={styles.progressTitle}>
              {progressEntries.length
                ? "Histórico sincronizado"
                : "Pronto para começar"}
            </Text>
            <Text style={styles.progressDescription}>
              {error ?? "Peso, medidas e cargas em um só histórico."}
            </Text>
          </View>
          <ChartNoAxesCombined color={colors.green} size={22} strokeWidth={2} />
        </View>
        <View style={styles.progressMetrics}>
          <View>
            <Text style={styles.progressValue}>
              {latestProgress?.weight_kg ?? profile?.current_weight_kg ?? "--"}
              {latestProgress?.weight_kg || profile?.current_weight_kg
                ? " kg"
                : ""}
            </Text>
            <Text style={styles.progressLabel}>peso atual</Text>
          </View>
          <View>
            <Text style={styles.progressValue}>{progressEntries.length}</Text>
            <Text style={styles.progressLabel}>medições</Text>
          </View>
          <View>
            <Text style={styles.progressValue}>
              {progressionSuggestions.length}
            </Text>
            <Text style={styles.progressLabel}>sugestões</Text>
          </View>
        </View>
        <ProgressBar
          value={Math.min(progressEntries.length / 12, 1)}
          color={colors.green}
        />
      </Pressable>

      <SectionTitle title="Seu plano" meta="semana 1 de 12" />
      <Surface>
        <SettingRow
          icon={CalendarDays}
          title="Planejamento semanal"
          description={
            workoutPlan
              ? `${workoutPlan.weekly_frequency} dias de treino - ${dietPlan ? "dieta ativa" : "sem dieta ativa"}`
              : "Nenhum plano de treino ativo"
          }
          onPress={() => showPlaceholder("Planejamento semanal")}
        />
        <Divider />
        <SettingRow
          icon={Dumbbell}
          title="Treino"
          description={trainingSummary}
          onPress={() => router.push("/workout")}
        />
        <Divider />
        <SettingRow
          icon={Utensils}
          title="Dieta"
          description={
            dietPlan
              ? `${dietPlan.daily_calories_target ?? 0} kcal - ${dietPlan.daily_protein_target_g ?? 0} g de proteína - ${dietPlan.meals.length} refeições`
              : "Nenhum plano alimentar ativo"
          }
          onPress={() => router.push("/diet")}
        />
      </Surface>

      <SectionTitle title="Acesso rápido" meta="essenciais" />
      <Surface>
        <SettingRow
          icon={ClipboardList}
          title="Objetivo e rotina"
          description="Dias, horários, nível e foco atual"
          onPress={() => showPlaceholder("Objetivo e rotina")}
        />
        <Divider />
        <SettingRow
          icon={HeartPulse}
          title="Restrições e cuidados"
          description="Lesões, exercícios e observações"
          onPress={() => showPlaceholder("Restrições e cuidados")}
        />
        <Divider />
        <SettingRow
          icon={Bell}
          title="Notificações"
          description="Treino 18:30 - refeições ligadas"
          onPress={() => showPlaceholder("Notificações")}
        />
      </Surface>

      <SectionTitle title="Histórico e dados" />
      <Surface>
        <SettingRow
          icon={ChartNoAxesCombined}
          title="Histórico de treinos"
          description="Sessões, cargas e evolução por exercício"
          onPress={() => showPlaceholder("Histórico de treinos")}
        />
        <Divider />
        <SettingRow
          icon={Camera}
          title="Fotos e medidas"
          description="Registros opcionais de evolução corporal"
          onPress={() => router.push("/progress")}
        />
        <Divider />
        <SettingRow
          icon={BrainCircuit}
          title="Memória do Coach"
          description="Conversas salvas e informações lembradas"
          onPress={() => showPlaceholder("Memória do Coach")}
        />
      </Surface>

      <Text style={styles.version}>Evolv 0.1.0</Text>
    </AppScreen>
  );
}

function SettingRow({
  icon,
  title,
  description,
  onPress,
}: {
  icon: typeof Bell;
  title: string;
  description: string;
  onPress: () => void;
}) {
  const { palette } = useAppTheme();

  return (
    <InfoRow
      leading={<LabelIcon icon={icon} />}
      title={title}
      description={description}
      trailing={<ChevronRight color={palette.faint} size={18} />}
      onPress={onPress}
    />
  );
}

const createStyles = (palette: AppThemePalette) =>
  StyleSheet.create({
    goalBand: {
      borderTopWidth: 1,
      borderBottomWidth: 1,
      borderColor: palette.border,
      paddingHorizontal: spacing.xs,
    },
    progressSummary: {
      gap: 16,
      borderRadius: 8,
      borderWidth: 1,
      borderColor: palette.border,
      backgroundColor: palette.surface,
      padding: 16,
    },
    progressTop: {
      flexDirection: "row",
      justifyContent: "space-between",
      gap: 12,
    },
    progressCopy: { flex: 1, minWidth: 0 },
    progressTitle: { color: palette.text, fontSize: 16, fontWeight: "900" },
    progressDescription: { marginTop: 4, color: palette.faint, fontSize: 12 },
    progressMetrics: { flexDirection: "row", justifyContent: "space-between" },
    progressValue: { color: palette.text, fontSize: 17, fontWeight: "900" },
    progressLabel: {
      marginTop: 2,
      color: palette.faint,
      fontSize: 10,
      textTransform: "uppercase",
    },
    version: { color: palette.faint, fontSize: 11, textAlign: "center" },
    pressed: { opacity: 0.66 },
  });

import { Alert, StyleSheet, Text, View } from "react-native";
import {
  Bell,
  CalendarClock,
  CircleHelp,
  Dumbbell,
  Utensils,
} from "lucide-react-native";

import {
  AppScreen,
  CinematicHero,
  Divider,
  InfoRow,
  LabelIcon,
  PageHeader,
  SectionTitle,
  Tag,
} from "@/components/ui";
import { colors, spacing } from "@/constants/theme";
import { useImagePreferences } from "@/context/image-preferences-context";
import { useEvolvData } from "@/context/evolv-data-context";
import { useAppTheme, type AppThemePalette } from "@/context/theme-context";
import { workoutImageCategoryFromText } from "@/data/api-mappers";
import { pickWeeklyImage, workoutImageLibrary } from "@/data/image-library";

const weekdayByIndex = [
  "sunday",
  "monday",
  "tuesday",
  "wednesday",
  "thursday",
  "friday",
  "saturday",
];

export default function TodayScreen() {
  const { palette } = useAppTheme();
  const imagePreferences = useImagePreferences();
  const { dietPlan, error, isLoading, profile, workoutPlan } = useEvolvData();
  const styles = createStyles(palette);
  const today = new Date();
  const weekday = weekdayByIndex[today.getDay()];
  const todayWorkout = workoutPlan?.workout_days.find(
    (day) => day.weekday === weekday,
  );
  const todayMeal = dietPlan?.meals[0];
  const imageCategory = workoutImageCategoryFromText(
    todayWorkout?.focus ?? todayWorkout?.title ?? "recuperação",
  );
  const dateLabel = new Intl.DateTimeFormat("pt-BR", {
    weekday: "long",
    day: "2-digit",
    month: "long",
  }).format(today);
  const nextWorkouts = workoutPlan?.workout_days
    .filter((day) => day.id !== todayWorkout?.id)
    .slice(0, 3)
    .map((day) => day.title)
    .join("  |  ");

  return (
    <AppScreen>
      <PageHeader
        brand="EVOLV"
        eyebrow={dateLabel}
        title="Hoje"
        actionIcon={CircleHelp}
        actionLabel="Ajuda sobre a tela Hoje"
        onAction={() =>
          Alert.alert(
            "Hoje",
            "Esta tela é apenas um resumo. Você não precisa confirmar treino, alimentação ou ausência.",
          )
        }
      />

      <CinematicHero
        source={pickWeeklyImage(
          workoutImageLibrary[imageCategory],
          imagePreferences,
          `today-${imageCategory}`,
          0,
        )}
        eyebrow={
          todayWorkout ? (workoutPlan?.name ?? "Plano ativo") : "Agenda livre"
        }
        title={todayWorkout?.title ?? "Recuperação"}
        description={
          todayWorkout
            ? `${todayWorkout.estimated_minutes ?? 0} minutos com foco em ${todayWorkout.focus.toLocaleLowerCase("pt-BR")}.`
            : "Hoje não há treino previsto. O restante do plano continua igual."
        }
        meta={
          workoutPlan
            ? `${workoutPlan.weekly_frequency} treinos por semana`
            : "Sem plano ativo"
        }
      />

      <View style={styles.factStrip}>
        <View style={styles.fact}>
          <Text style={styles.factValue}>
            {String(todayWorkout?.workout_day_exercises.length ?? 0).padStart(
              2,
              "0",
            )}
          </Text>
          <Text style={styles.factLabel}>exercícios</Text>
        </View>
        <View style={styles.factDivider} />
        <View style={styles.fact}>
          <Text style={styles.factValue}>
            {todayWorkout?.estimated_minutes ?? 0}
          </Text>
          <Text style={styles.factLabel}>minutos</Text>
        </View>
        <View style={styles.factDivider} />
        <View style={styles.fact}>
          <Text style={styles.factValue}>
            {workoutPlan?.weekly_frequency ?? 0}/7
          </Text>
          <Text style={styles.factLabel}>na semana</Text>
        </View>
      </View>

      <SectionTitle title="Resumo do dia" meta="sem cobrança" />
      <View style={styles.schedule}>
        <InfoRow
          leading={<LabelIcon icon={Dumbbell} />}
          title={
            todayWorkout
              ? `Treino previsto: ${todayWorkout.title}`
              : "Nenhum treino previsto"
          }
          description="O plano continua mesmo se você não registrar nada hoje."
          trailing={<Tag>{todayWorkout?.estimated_minutes ?? 0} min</Tag>}
        />
        <Divider />
        <InfoRow
          leading={<LabelIcon icon={Utensils} />}
          title={
            todayMeal
              ? `${todayMeal.name}: ${todayMeal.description ?? "consulte os itens na Dieta"}`
              : "Nenhuma dieta ativa"
          }
          description={
            todayMeal
              ? "A refeição pode ser consultada ou ajustada na aba Dieta."
              : "O app funciona normalmente mesmo sem plano alimentar."
          }
          trailing={
            todayMeal ? (
              <Tag color={colors.green}>
                {todayMeal.calories_target ?? 0} kcal
              </Tag>
            ) : undefined
          }
        />
        <Divider />
        <InfoRow
          leading={<LabelIcon icon={Bell} />}
          title={
            profile?.preferred_training_time
              ? `Próximo lembrete: ${profile.preferred_training_time.slice(0, 5)}`
              : "Lembrete ainda não definido"
          }
          description="Apenas um aviso, sem necessidade de confirmar presença."
        />
      </View>

      <SectionTitle title="Semana" meta="visão rápida" />
      <View style={styles.schedule}>
        <InfoRow
          leading={<LabelIcon icon={CalendarClock} />}
          title="Outros treinos do plano"
          description={nextWorkouts || "Nenhum outro treino cadastrado."}
        />
      </View>

      <View style={styles.planNote}>
        <Text style={styles.noteTitle}>
          {error ? "Conexão" : "Nota do plano"}
        </Text>
        <Text style={styles.noteText}>
          {error ??
            (isLoading
              ? "Atualizando seus dados..."
              : "Sem ajustes pendentes. O plano segue igual até você pedir uma mudança ao Coach.")}
        </Text>
      </View>
    </AppScreen>
  );
}

const createStyles = (palette: AppThemePalette) =>
  StyleSheet.create({
    factStrip: {
      minHeight: 84,
      flexDirection: "row",
      alignItems: "center",
      borderTopWidth: 1,
      borderBottomWidth: 1,
      borderColor: palette.border,
    },
    fact: { flex: 1, alignItems: "center" },
    factDivider: { width: 1, height: 34, backgroundColor: palette.border },
    factValue: { color: palette.text, fontSize: 24, fontWeight: "900" },
    factLabel: {
      marginTop: 2,
      color: palette.muted,
      fontSize: 9.5,
      fontWeight: "800",
      textTransform: "uppercase",
    },
    schedule: {
      borderTopWidth: 1,
      borderBottomWidth: 1,
      borderColor: palette.border,
      paddingHorizontal: spacing.xs,
    },
    planNote: {
      borderLeftWidth: 4,
      borderLeftColor: colors.red,
      backgroundColor: palette.accentSoft,
      padding: spacing.lg,
    },
    noteTitle: { color: palette.text, fontSize: 16, fontWeight: "900" },
    noteText: {
      marginTop: 6,
      color: palette.accentText,
      fontSize: 13,
      lineHeight: 19,
    },
  });

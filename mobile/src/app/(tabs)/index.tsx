import { useRouter } from "expo-router";
import {
  CalendarClock,
  ChevronRight,
  CircleHelp,
  Dumbbell,
  MessageCircle,
  Target,
  Utensils,
} from "lucide-react-native";
import { Alert, StyleSheet, Text, View } from "react-native";

import {
  AppScreen,
  IllustratedHero,
  Divider,
  InfoRow,
  LabelIcon,
  PageHeader,
  SectionTitle,
  Tag,
} from "@/components/ui";
import { artwork } from "@/data/illustrations";
import { colors, radius, spacing } from "@/constants/theme";
import { useEvolvData } from "@/context/evolv-data-context";
import { useAppTheme, type AppThemePalette } from "@/context/theme-context";
import { mapWorkoutPlanToDays } from "@/data/api-mappers";

import { addCalendarDays, mondayWeekDates, mondayWeekIndex } from "@/lib/local-date";

export default function TodayScreen() {
  const { palette } = useAppTheme();
  const { activeGoal, dailyDiet, error, isLoading, today, workoutPlan, workoutWeek } =
    useEvolvData();
  const router = useRouter();
  const styles = createStyles(palette);
  const todayIndex = mondayWeekIndex(today);
  const todaySlot = workoutWeek[todayIndex];
  const todayWorkout = todaySlot?.status === "planned" ? todaySlot : null;
  const todayFocus = workoutPlan?.workout_days.find((day) => day.id === todayWorkout?.id)?.focus;
  const nextThisWeek = workoutWeek.slice(todayIndex + 1).find((day) => day.status === "planned");
  const nextWorkout = nextThisWeek ?? (workoutPlan
    ? mapWorkoutPlanToDays(workoutPlan, {
        dates: mondayWeekDates(addCalendarDays(today, 7)),
        overrides: [],
      }).find((day) => day.status === "planned")
    : undefined);
  const dateLabel = new Intl.DateTimeFormat("pt-BR", {
    weekday: "long",
    day: "2-digit",
    month: "long",
  }).format(today);
  const heroTitle = todayWorkout
    ? todayWorkout.title
    : workoutPlan
      ? "Dia livre"
      : "Sem treino marcado";
  const heroDescription = todayWorkout
    ? todayWorkout.exercises.length
      ? `${todayWorkout.exercises.length} exercícios e ${todayWorkout.durationMinutes} min de treino.`
      : "Atividade prevista para hoje."
    : workoutPlan
      ? nextWorkout
        ? `Próximo treino: ${nextWorkout.title}.`
        : "Hoje não há treino previsto."
      : "Monte um plano para organizar sua rotina.";

  return (
    <AppScreen
      header={
        <PageHeader
          brand="EVOLV"
          eyebrow={dateLabel}
          title="Hoje"
          actionIcon={CircleHelp}
          actionLabel="Ajuda sobre a tela Hoje"
          onAction={() =>
            Alert.alert(
              "Hoje",
              "Um resumo simples do que importa agora. Você não precisa confirmar treino, alimentação ou ausência.",
            )
          }
        />
      }
    >
      <IllustratedHero
        source={todayWorkout
          ? artwork.today
          : workoutPlan ? artwork.recovery : artwork.workoutPlan}
        eyebrow={todayWorkout ? "Plano de hoje" : "Seu dia"}
        title={heroTitle}
        description={heroDescription}
        action={{
          label: todayWorkout
            ? "Ver treino de hoje"
            : workoutPlan
              ? "Ver minha semana"
              : "Montar meu treino",
          onPress: () => router.push("/(tabs)/workout"),
        }}
      />

      {workoutPlan ? (
        <>
          <SectionTitle title="Sua semana" />
          <View style={styles.weekStrip}>
            {workoutWeek.map((day, index) => {
              const planned = day.status === "planned";
              const current = index === todayIndex;
              return (
                <View
                  key={day.shortLabel}
                  accessible
                  accessibilityLabel={`${day.weekday}${current ? ", hoje" : ""}, ${planned ? day.title : "sem treino"}`}
                  style={styles.weekDay}
                >
                  <Text
                    style={[
                      styles.weekLabel,
                      current && styles.weekLabelCurrent,
                    ]}
                  >
                    {day.shortLabel}
                  </Text>
                  <View
                    style={[
                      styles.weekDot,
                      planned && styles.weekDotPlanned,
                      current && styles.weekDotCurrent,
                      current && planned && styles.weekDotCurrentPlanned,
                    ]}
                  />
                </View>
              );
            })}
          </View>
        </>
      ) : null}

      <SectionTitle title="Sua rotina" />
      <View style={styles.dailyBrief}>
        <InfoRow
          leading={<LabelIcon icon={Dumbbell} />}
          title={
            todayWorkout
              ? todayWorkout.title
              : workoutPlan
                ? "Dia livre no plano"
                : "Treino no seu ritmo"
          }
          description={
            todayWorkout
              ? todayFocus
                ? `${todayWorkout.exercises.length} exercícios com foco em ${todayFocus.toLocaleLowerCase("pt-BR")}.`
                : "Atividade prevista para hoje."
              : nextWorkout
                ? `Próximo treino: ${nextWorkout.title}.`
                : "Consulte modalidades, exercícios e cargas quando quiser."
          }
          trailing={
            <View style={styles.trailingGroup}>
              <Tag>
                {todayWorkout
                  ? todayWorkout.durationMinutes
                    ? `${todayWorkout.durationMinutes} min`
                    : "Planejado"
                  : "Livre"}
              </Tag>
              <ChevronRight color={palette.faint} size={17} />
            </View>
          }
          onPress={() => router.push("/(tabs)/workout")}
        />
        <Divider />
        <InfoRow
          leading={<LabelIcon icon={Utensils} />}
          title={
            dailyDiet
              ? `${dailyDiet.meals.length} refeições para hoje`
              : "Alimentação sem plano ativo"
          }
          description={
            dailyDiet
              ? `${dailyDiet.proteinTarget} g de proteína no alvo diário.`
              : "A aba Dieta funciona mesmo sem acompanhamento completo."
          }
          trailing={
            <View style={styles.trailingGroup}>
              <Tag color={colors.green}>
                {dailyDiet?.calorieTarget
                  ? `${dailyDiet.calorieTarget} kcal`
                  : "Opcional"}
              </Tag>
              <ChevronRight color={palette.faint} size={17} />
            </View>
          }
          onPress={() => router.push("/(tabs)/diet")}
        />
        <Divider />
        <InfoRow
          leading={<LabelIcon icon={MessageCircle} />}
          title="Coach quando você precisar"
          description="Tire dúvidas ou peça pequenos ajustes sem alterar o plano inteiro."
          trailing={
            <View style={styles.trailingGroup}>
              <Tag color={colors.green}>Disponível</Tag>
              <ChevronRight color={palette.faint} size={17} />
            </View>
          }
          onPress={() => router.push("/(tabs)/coach")}
        />
      </View>


      <SectionTitle title="Próximo ponto" meta="no seu tempo" />
      <View style={styles.nextBand}>
        <InfoRow
          leading={<LabelIcon icon={nextWorkout ? CalendarClock : Target} />}
          title={
            nextWorkout
              ? nextWorkout.title
              : (activeGoal?.title ?? "Seu espaço está pronto")
          }
          description={
            nextWorkout
              ? "O próximo treino permanece no calendário; você não precisa confirmar nada agora."
              : activeGoal
                ? "Seu objetivo está salvo. O Planner organizará o plano sem mudanças bruscas."
                : "Explore as áreas que forem úteis e deixe o restante para depois."
          }
        />
      </View>

      {error || isLoading ? (
        <Text style={[styles.syncText, error && styles.errorText]}>
          {error ?? "Atualizando seu resumo..."}
        </Text>
      ) : null}
    </AppScreen>
  );
}

const createStyles = (palette: AppThemePalette) =>
  StyleSheet.create({
    dailyBrief: {
      borderRadius: radius.card,
      backgroundColor: palette.surface,
      borderWidth: StyleSheet.hairlineWidth,
      borderColor: palette.border,
      paddingHorizontal: spacing.lg,
      paddingVertical: spacing.xs,
    },
    trailingGroup: {
      flexDirection: "row",
      alignItems: "center",
      gap: 6,
    },
    weekStrip: {
      minHeight: 72,
      flexDirection: "row",
      alignItems: "center",
      justifyContent: "space-between",
      borderRadius: radius.card,
      backgroundColor: palette.surface,
      borderWidth: StyleSheet.hairlineWidth,
      borderColor: palette.border,
      paddingHorizontal: spacing.lg,
      paddingVertical: spacing.md,
    },
    weekDay: { alignItems: "center", gap: 9 },
    weekLabel: {
      color: palette.faint,
      fontSize: 9.5,
      fontWeight: "600",
    },
    weekLabelCurrent: { color: palette.text },
    weekDot: {
      width: 7,
      height: 7,
      borderRadius: 4,
      backgroundColor: palette.border,
    },
    weekDotPlanned: { backgroundColor: palette.macroFat },
    weekDotCurrent: {
      width: 11,
      height: 11,
      borderRadius: 6,
      borderWidth: 2,
      borderColor: palette.accentText,
      backgroundColor: palette.page,
    },
    weekDotCurrentPlanned: { backgroundColor: palette.accentText },
    nextBand: {
      borderRadius: radius.card,
      backgroundColor: palette.accentSoft,
      paddingHorizontal: spacing.lg,
    },
    syncText: {
      color: palette.faint,
      fontSize: 11,
      lineHeight: 16,
      textAlign: "center",
    },
    errorText: { color: colors.red },
  });

import { useRouter } from "expo-router";
import {
  CalendarClock,
  ArrowUpRight,
  ChevronRight,
  CircleHelp,
  Dumbbell,
  MessageCircle,
  Target,
  Utensils,
} from "lucide-react-native";
import { Alert, Pressable, StyleSheet, Text, View } from "react-native";

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
import { useEvolvData } from "@/context/evolv-data-context";
import { useImagePreferences } from "@/context/image-preferences-context";
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
] as const;

const week = [
  { key: "monday", label: "SEG" },
  { key: "tuesday", label: "TER" },
  { key: "wednesday", label: "QUA" },
  { key: "thursday", label: "QUI" },
  { key: "friday", label: "SEX" },
  { key: "saturday", label: "SÁB" },
  { key: "sunday", label: "DOM" },
] as const;

const weekdayIndex = Object.fromEntries(
  weekdayByIndex.map((weekday, index) => [weekday, index]),
) as Record<string, number>;

export default function TodayScreen() {
  const { palette } = useAppTheme();
  const imagePreferences = useImagePreferences();
  const { activeGoal, dietPlan, error, isLoading, workoutPlan } =
    useEvolvData();
  const router = useRouter();
  const styles = createStyles(palette);
  const today = new Date();
  const todayIndex = today.getDay();
  const weekday = weekdayByIndex[todayIndex];
  const todayWorkout = workoutPlan?.workout_days.find(
    (day) => day.weekday === weekday,
  );
  const nextWorkout = workoutPlan?.workout_days
    .map((day) => ({
      ...day,
      distance:
        ((weekdayIndex[day.weekday] ?? todayIndex) - todayIndex + 7) % 7 || 7,
    }))
    .sort((first, second) => first.distance - second.distance)[0];
  const dateLabel = new Intl.DateTimeFormat("pt-BR", {
    weekday: "long",
    day: "2-digit",
    month: "long",
  }).format(today);
  const imageCategory = todayWorkout
    ? workoutImageCategoryFromText(todayWorkout.focus || todayWorkout.title)
    : workoutPlan
      ? "recovery"
      : "preparation";
  const heroTitle = todayWorkout
    ? todayWorkout.title
    : workoutPlan
      ? "Dia livre"
      : "Sem treino marcado";
  const heroDescription = todayWorkout
    ? `${todayWorkout.workout_day_exercises.length} exercícios e ${todayWorkout.estimated_minutes ?? 0} minutos previstos. Basta consultar e seguir quando chegar a hora.`
    : workoutPlan
      ? nextWorkout
        ? `Hoje não há treino previsto. O próximo é ${nextWorkout.title.toLocaleLowerCase("pt-BR")}.`
        : "Hoje não há treino previsto e seu plano continua igual."
      : "Sua agenda está livre. Escolha como quer começar.";

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
            "Um resumo simples do que importa agora. Você não precisa confirmar treino, alimentação ou ausência.",
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
        eyebrow={todayWorkout ? "Plano de hoje" : "Seu dia"}
        title={heroTitle}
        description={heroDescription}
        height={220}
        overlayOpacity={0.28}
      />

      <Pressable
        accessibilityRole="button"
        onPress={() => router.push("/(tabs)/workout")}
        style={({ pressed }) => [styles.dayAction, pressed && { opacity: 0.7 }]}
      >
        <Text style={styles.dayActionText}>
          {todayWorkout
            ? "Ver treino de hoje"
            : workoutPlan
              ? "Ver minha semana"
              : "Montar meu treino"}
        </Text>
        <ArrowUpRight color={colors.white} size={19} />
      </Pressable>

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
              ? `${todayWorkout.workout_day_exercises.length} exercícios com foco em ${todayWorkout.focus.toLocaleLowerCase("pt-BR")}.`
              : nextWorkout
                ? `Próximo treino: ${nextWorkout.title}.`
                : "Consulte modalidades, exercícios e cargas quando quiser."
          }
          trailing={
            <View style={styles.trailingGroup}>
              <Tag>
                {todayWorkout
                  ? `${todayWorkout.estimated_minutes ?? 0} min`
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
            dietPlan
              ? `${dietPlan.meals.length} refeições no plano`
              : "Alimentação sem plano ativo"
          }
          description={
            dietPlan
              ? `${dietPlan.daily_protein_target_g ?? 0} g de proteína no alvo diário.`
              : "A aba Dieta funciona mesmo sem acompanhamento completo."
          }
          trailing={
            <View style={styles.trailingGroup}>
              <Tag color={colors.green}>
                {dietPlan?.daily_calories_target
                  ? `${dietPlan.daily_calories_target} kcal`
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

      {workoutPlan ? (
        <>
          <SectionTitle title="Sua semana" meta="visão rápida" />
          <View style={styles.weekStrip}>
            {week.map((day) => {
              const planned = workoutPlan.workout_days.some(
                (workoutDay) => workoutDay.weekday === day.key,
              );
              const current = day.key === weekday;
              return (
                <View key={day.key} style={styles.weekDay}>
                  <Text
                    style={[
                      styles.weekLabel,
                      current && styles.weekLabelCurrent,
                    ]}
                  >
                    {day.label}
                  </Text>
                  <View
                    style={[
                      styles.weekDot,
                      planned && styles.weekDotPlanned,
                      current && styles.weekDotCurrent,
                    ]}
                  />
                </View>
              );
            })}
          </View>
        </>
      ) : null}

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
    dayAction: {
      minHeight: 50,
      borderRadius: 25,
      backgroundColor: colors.red,
      flexDirection: "row",
      alignItems: "center",
      justifyContent: "center",
      paddingHorizontal: spacing.xl,
      gap: 10,
    },
    dayActionText: { color: colors.white, fontSize: 14, fontWeight: "600" },
    dailyBrief: {
      borderTopWidth: 1,
      borderBottomWidth: 1,
      borderColor: palette.border,
      paddingHorizontal: spacing.xs,
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
      borderTopWidth: 1,
      borderBottomWidth: 1,
      borderColor: palette.border,
      paddingHorizontal: spacing.sm,
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
    weekDotPlanned: { backgroundColor: colors.gold },
    weekDotCurrent: {
      width: 11,
      height: 11,
      borderRadius: 6,
      borderWidth: 2,
      borderColor: colors.red,
      backgroundColor: palette.page,
    },
    nextBand: {
      borderLeftWidth: 4,
      borderLeftColor: colors.red,
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

import { Pressable, StyleSheet, Text, View } from "react-native";
import { useRouter } from "expo-router";
import { ArrowLeft, Check } from "lucide-react-native";

import { AppScreen, Divider, SectionTitle, Surface } from "@/components/ui";
import { colors, radius, spacing, typography } from "@/constants/theme";
import { useAppTheme, type AppThemePalette } from "@/context/theme-context";
import { useTrainingPreferences } from "@/context/training-preferences-context";
import {
  trainingFocuses,
  trainingModalities,
  type TrainingOption,
} from "@/data/training-options";

export default function TrainingPreferencesScreen() {
  const { palette } = useAppTheme();
  const { selectedFocusIds, selectedModalityIds, toggleFocus, toggleModality } =
    useTrainingPreferences();
  const styles = createStyles(palette);
  const router = useRouter();

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
        <View style={styles.headerCopy}>
          <Text style={styles.eyebrow}>Treino</Text>
          <Text style={styles.title}>Preferências</Text>
        </View>
      </View>

      <View style={styles.summary}>
        <Text style={styles.summaryValue}>{selectedModalityIds.length}</Text>
        <Text style={styles.summaryLabel}>modalidades ativas</Text>
        <View style={styles.summaryDivider} />
        <Text style={styles.summaryValue}>{selectedFocusIds.length}</Text>
        <Text style={styles.summaryLabel}>focos do programa</Text>
      </View>

      <SectionTitle
        title="Modalidades e recursos"
        meta={`${selectedModalityIds.length} selecionadas`}
      />
      <OptionList
        options={trainingModalities}
        selectedIds={selectedModalityIds}
        onToggle={toggleModality}
      />

      <SectionTitle
        title="Foco do programa"
        meta={`${selectedFocusIds.length} selecionados`}
      />
      <OptionList
        options={trainingFocuses}
        selectedIds={selectedFocusIds}
        onToggle={toggleFocus}
      />
    </AppScreen>
  );
}

function OptionList({
  options,
  selectedIds,
  onToggle,
}: {
  options: TrainingOption[];
  selectedIds: string[];
  onToggle: (id: string) => void;
}) {
  const { palette } = useAppTheme();
  const styles = createStyles(palette);

  return (
    <Surface>
      {options.map((option, index) => {
        const selected = selectedIds.includes(option.id);

        return (
          <View key={option.id}>
            {index > 0 ? <Divider /> : null}
            <Pressable
              accessibilityRole="checkbox"
              accessibilityState={{ checked: selected }}
              onPress={() => onToggle(option.id)}
              style={({ pressed }) => [
                styles.option,
                pressed && styles.pressed,
              ]}
            >
              <View style={styles.optionCopy}>
                <Text style={styles.optionTitle}>{option.title}</Text>
                <Text style={styles.optionDescription}>
                  {option.description}
                </Text>
              </View>
              <View style={[styles.check, selected && styles.checkSelected]}>
                {selected ? (
                  <Check color={colors.text} size={15} strokeWidth={2.5} />
                ) : null}
              </View>
            </Pressable>
          </View>
        );
      })}
    </Surface>
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
      borderRadius: radius.lg,
      borderWidth: 1,
      borderColor: palette.border,
      backgroundColor: palette.surface,
      alignItems: "center",
      justifyContent: "center",
    },
    headerCopy: { flex: 1 },
    eyebrow: {
      color: palette.muted,
      fontSize: 11,
      fontWeight: "600",
      textTransform: "none",
    },
    title: {
      marginTop: 2,
      color: palette.text,
      fontFamily: typography.display,
      fontSize: 29,
      fontWeight: "600",
      textTransform: "none",
    },
    summary: {
      minHeight: 70,
      flexDirection: "row",
      alignItems: "center",
      justifyContent: "center",
      gap: spacing.sm,
      borderTopWidth: 1,
      borderBottomWidth: 1,
      borderColor: palette.border,
    },
    summaryValue: { color: palette.text, fontSize: 22, fontWeight: "600" },
    summaryLabel: {
      maxWidth: 110,
      color: palette.muted,
      fontSize: 11,
      lineHeight: 15,
    },
    summaryDivider: {
      width: 1,
      height: 34,
      marginHorizontal: spacing.md,
      backgroundColor: palette.border,
    },
    option: {
      minHeight: 68,
      flexDirection: "row",
      alignItems: "center",
      gap: spacing.md,
      paddingVertical: spacing.sm,
    },
    optionCopy: { flex: 1, minWidth: 0 },
    optionTitle: { color: palette.text, fontSize: 14, fontWeight: "600" },
    optionDescription: {
      marginTop: 3,
      color: palette.muted,
      fontSize: 12,
      lineHeight: 17,
    },
    check: {
      width: 24,
      height: 24,
      borderRadius: radius.sm,
      borderWidth: 1,
      borderColor: palette.border,
      alignItems: "center",
      justifyContent: "center",
    },
    checkSelected: { borderColor: colors.red, backgroundColor: colors.red },
    pressed: { opacity: 0.66 },
  });

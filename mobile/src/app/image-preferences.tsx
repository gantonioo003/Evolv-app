import { Check, ArrowLeft } from "lucide-react-native";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { useRouter } from "expo-router";

import { AppScreen, SectionTitle, Surface } from "@/components/ui";
import { colors, spacing, typography } from "@/constants/theme";
import {
  useImagePreferences,
  type BodyTypePreference,
  type PeoplePreference,
} from "@/context/image-preferences-context";
import { useAppTheme, type AppThemePalette } from "@/context/theme-context";

type Option<T extends string> = { label: string; value: T };

const peopleOptions: Option<PeoplePreference>[] = [
  { label: "Variar automaticamente", value: "automatic" },
  { label: "Priorizar homens", value: "men" },
  { label: "Priorizar mulheres", value: "women" },
];

const bodyTypeOptions: Option<BodyTypePreference>[] = [
  { label: "Variar", value: "mixed" },
  { label: "Fitness", value: "fitness" },
  { label: "Musculoso", value: "muscular" },
];

export default function ImagePreferencesScreen() {
  const { palette } = useAppTheme();
  const styles = createStyles(palette);
  const router = useRouter();
  const preferences = useImagePreferences();

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
          <Text style={styles.eyebrow}>Personalização</Text>
          <Text style={styles.title}>Imagens do app</Text>
        </View>
      </View>

      <Text style={styles.intro}>
        Escolha apenas o tipo de pessoa e o estilo físico. A variedade de
        aparências acontece automaticamente.
      </Text>

      <SectionTitle title="Pessoas nas fotos" meta="preferência" />
      <OptionGroup
        options={peopleOptions}
        selected={preferences.people}
        onSelect={preferences.setPeople}
      />

      <SectionTitle title="Estilo físico" meta="preferência" />
      <OptionGroup
        options={bodyTypeOptions}
        selected={preferences.bodyType}
        onSelect={preferences.setBodyType}
      />

      <Text style={styles.note}>
        As imagens continuam variando a cada semana. Tons de pele, cabelos,
        idades e cenas são alternados pelo próprio catálogo.
      </Text>
    </AppScreen>
  );
}

function OptionGroup<T extends string>({
  options,
  selected,
  onSelect,
}: {
  options: Option<T>[];
  selected: T;
  onSelect: (value: T) => void;
}) {
  const { palette } = useAppTheme();
  const styles = createStyles(palette);

  return (
    <Surface style={styles.optionSurface}>
      {options.map((option, index) => {
        const active = option.value === selected;
        return (
          <View key={option.value}>
            {index > 0 ? <View style={styles.divider} /> : null}
            <Pressable
              accessibilityRole="radio"
              accessibilityState={{ checked: active }}
              onPress={() => onSelect(option.value)}
              style={({ pressed }) => [
                styles.option,
                pressed && styles.pressed,
              ]}
            >
              <Text
                style={[styles.optionText, active && styles.optionTextActive]}
              >
                {option.label}
              </Text>
              <View style={[styles.radio, active && styles.radioActive]}>
                {active ? (
                  <Check color={colors.text} size={14} strokeWidth={3} />
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
      borderRadius: 22,
      borderWidth: 1,
      borderColor: palette.border,
      backgroundColor: palette.surface,
      alignItems: "center",
      justifyContent: "center",
    },
    headerCopy: { flex: 1 },
    eyebrow: {
      color: palette.muted,
      fontFamily: typography.body,
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
    },
    intro: {
      color: palette.muted,
      fontFamily: typography.body,
      fontSize: 13.5,
      lineHeight: 20,
    },
    optionSurface: { paddingVertical: 2 },
    option: {
      minHeight: 54,
      flexDirection: "row",
      alignItems: "center",
      justifyContent: "space-between",
      gap: spacing.md,
    },
    optionText: {
      flex: 1,
      color: palette.muted,
      fontFamily: typography.body,
      fontSize: 14,
      fontWeight: "600",
    },
    optionTextActive: { color: palette.text, fontWeight: "600" },
    radio: {
      width: 24,
      height: 24,
      borderRadius: 12,
      borderWidth: 1,
      borderColor: palette.border,
      alignItems: "center",
      justifyContent: "center",
    },
    radioActive: { borderColor: colors.red, backgroundColor: colors.red },
    divider: {
      height: StyleSheet.hairlineWidth,
      backgroundColor: palette.border,
    },
    note: {
      color: palette.faint,
      fontFamily: typography.body,
      fontSize: 11.5,
      lineHeight: 17,
    },
    pressed: { opacity: 0.66 },
  });

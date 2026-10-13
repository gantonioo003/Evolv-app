import { Pressable, StyleSheet, Text, View } from "react-native";
import { useRouter } from "expo-router";
import { ArrowLeft, Check, Moon, Sun } from "lucide-react-native";

import {
  AppScreen,
  Divider,
  LabelIcon,
  SectionTitle,
  Surface,
} from "@/components/ui";
import { colors, radius, spacing, typography } from "@/constants/theme";
import {
  useAppTheme,
  type AppThemePalette,
  type ThemePreference,
} from "@/context/theme-context";

const themeOptions = [
  {
    value: "dark",
    label: "Escuro",
    description: "Visual cinematográfico com fundos escuros.",
    icon: Moon,
  },
  {
    value: "light",
    label: "Claro",
    description: "Fundos claros e contraste suave para o dia.",
    icon: Sun,
  },
] satisfies {
  value: ThemePreference;
  label: string;
  description: string;
  icon: typeof Moon;
}[];

export default function AppearanceScreen() {
  const { palette, preference, setPreference } = useAppTheme();
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
          <Text style={styles.eyebrow}>Configurações</Text>
          <Text style={styles.title}>Aparência</Text>
        </View>
      </View>

      <SectionTitle
        title="Tema do aplicativo"
        meta={preference === "dark" ? "escuro" : "claro"}
      />
      <Surface>
        <View accessibilityRole="radiogroup">
          {themeOptions.map((option, index) => {
            const selected = preference === option.value;
            const Icon = option.icon;

            return (
              <View key={option.value}>
                {index > 0 ? <Divider /> : null}
                <Pressable
                  accessibilityRole="radio"
                  accessibilityState={{ checked: selected }}
                  onPress={() => setPreference(option.value)}
                  style={({ pressed }) => [
                    styles.option,
                    pressed && styles.pressed,
                  ]}
                >
                  <LabelIcon icon={Icon} />
                  <View style={styles.optionCopy}>
                    <Text style={styles.optionTitle}>{option.label}</Text>
                    <Text style={styles.optionDescription}>
                      {option.description}
                    </Text>
                  </View>
                  <View
                    style={[styles.check, selected && styles.checkSelected]}
                  >
                    {selected ? (
                      <Check color={colors.text} size={15} strokeWidth={2.5} />
                    ) : null}
                  </View>
                </Pressable>
              </View>
            );
          })}
        </View>
      </Surface>

      <Text style={styles.note}>
        O tema escolhido permanece ativo até você alterá-lo novamente.
      </Text>
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
    option: {
      minHeight: 82,
      flexDirection: "row",
      alignItems: "center",
      gap: spacing.md,
      paddingVertical: spacing.sm,
    },
    optionCopy: { flex: 1, minWidth: 0 },
    optionTitle: { color: palette.text, fontSize: 15, fontWeight: "600" },
    optionDescription: {
      marginTop: 4,
      color: palette.muted,
      fontSize: 12.5,
      lineHeight: 18,
    },
    check: {
      width: 24,
      height: 24,
      borderRadius: 12,
      borderWidth: 1,
      borderColor: palette.border,
      alignItems: "center",
      justifyContent: "center",
    },
    checkSelected: { borderColor: colors.red, backgroundColor: colors.red },
    note: {
      maxWidth: 440,
      alignSelf: "center",
      color: palette.faint,
      fontSize: 11.5,
      lineHeight: 17,
      textAlign: "center",
    },
    pressed: { opacity: 0.66 },
  });

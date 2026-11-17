import { useState } from "react";
import { Ellipsis, Pencil } from "lucide-react-native";
import {
  Alert,
  KeyboardAvoidingView,
  Modal,
  Platform,
  Pressable,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";

import { radius, spacing } from "@/constants/theme";
import { useAppTheme } from "@/context/theme-context";

export function LoadStepper({
  exerciseName,
  value,
  onChange,
  metric = "load",
  secondary = false,
  addedLoad = false,
}: {
  exerciseName: string;
  value?: number;
  onChange: (value: number) => void;
  metric?: "load" | "reps" | "time";
  secondary?: boolean;
  addedLoad?: boolean;
}) {
  const { palette } = useAppTheme();
  const settings = {
    load: {
      label: "Carga",
      title: "Registrar carga",
      hint: "Informe o peso usado neste exercício.",
      unit: "kg",
      max: 1000,
    },
    reps: {
      label: "Repetições",
      title: "Registrar repetições",
      hint: "Informe quantas repetições você fez na série.",
      unit: "reps",
      max: 1000,
    },
    time: {
      label: "Tempo",
      title: "Registrar tempo",
      hint: "Informe quantos segundos você fez.",
      unit: "s",
      max: 86400,
    },
  }[metric];
  const extraLoad = (secondary || addedLoad) && metric === "load";
  const title = extraLoad ? "Registrar peso extra" : settings.title;
  const hint = extraLoad ? "Informe apenas o peso que você adicionou ao exercício." : settings.hint;
  const measurement =
    value === undefined ? undefined : `${value.toLocaleString("pt-BR")} ${settings.unit}`;
  const [visible, setVisible] = useState(false);
  const [draft, setDraft] = useState("");

  function open() {
    setDraft(value === undefined ? "" : String(value));
    setVisible(true);
  }

  function save() {
    const next = Number(draft.replace(",", "."));
    const minimum = metric === "load" ? 0 : 1;
    if (!draft.trim() || !Number.isFinite(next) || next < minimum || next > settings.max ||
        (metric !== "load" && !Number.isInteger(next))) {
      Alert.alert("Valor inválido", `Informe um valor entre ${minimum} e ${settings.max} ${settings.unit}.`);
      return;
    }
    onChange(metric === "load" ? Math.round(next * 100) / 100 : next);
    setVisible(false);
  }

  return (
    <>
      <Pressable
        accessibilityLabel={`${title} · ${exerciseName}${measurement ? ` · ${measurement}` : ""}`}
        accessibilityRole="button"
        onPress={open}
        style={({ pressed }) => [
          secondary
            ? styles.secondaryTrigger
            : [styles.trigger, { backgroundColor: palette.page, borderColor: palette.border }],
          pressed && styles.pressed,
        ]}
      >
        {secondary ? (
          <Ellipsis
            color={measurement ? palette.text : palette.muted}
            size={20}
            strokeWidth={2.2}
          />
        ) : (
          <>
            <Text style={[styles.value, { color: palette.text }]}>
              {measurement ?? settings.label}
            </Text>
            <Pencil
              color={palette.accentText}
              size={14}
              strokeWidth={2.1}
              style={styles.editIcon}
            />
          </>
        )}
      </Pressable>

      <Modal
        animationType="fade"
        onRequestClose={() => setVisible(false)}
        transparent
        visible={visible}
      >
        <KeyboardAvoidingView
          behavior={Platform.OS === "ios" ? "padding" : undefined}
          style={styles.modalRoot}
        >
          <Pressable
            accessibilityLabel="Fechar edição do registro"
            onPress={() => setVisible(false)}
            style={styles.backdrop}
          />
          <View
            style={[
              styles.dialog,
              { backgroundColor: palette.surface, borderColor: palette.border },
            ]}
          >
            <Text style={[styles.dialogTitle, { color: palette.text }]}>
              {title}
            </Text>
            <Text style={[styles.dialogDescription, { color: palette.muted }]}>
              {hint}
            </Text>
            <View
              style={[
                styles.inputGroup,
                { backgroundColor: palette.page, borderColor: palette.border },
              ]}
            >
              <TextInput
                autoFocus
                keyboardType={metric === "load" ? "decimal-pad" : "number-pad"}
                onChangeText={setDraft}
                placeholder="0"
                placeholderTextColor={palette.faint}
                selectTextOnFocus
                style={[styles.input, { color: palette.text }]}
                value={draft}
              />
              <Text style={[styles.unit, { color: palette.faint }]}>{settings.unit}</Text>
            </View>
            <View style={styles.actions}>
              <Pressable
                accessibilityRole="button"
                onPress={() => setVisible(false)}
                style={({ pressed }) => [
                  styles.cancelButton,
                  { borderColor: palette.border },
                  pressed && styles.pressed,
                ]}
              >
                <Text style={[styles.cancelText, { color: palette.text }]}>
                  Cancelar
                </Text>
              </Pressable>
              <Pressable
                accessibilityRole="button"
                onPress={save}
                style={({ pressed }) => [
                  styles.saveButton,
                  { backgroundColor: palette.primary },
                  pressed && styles.pressed,
                ]}
              >
                <Text style={[styles.saveText, { color: palette.onPrimary }]}>Aplicar</Text>
              </Pressable>
            </View>
          </View>
        </KeyboardAvoidingView>
      </Modal>
    </>
  );
}

const styles = StyleSheet.create({
  trigger: {
    width: 104,
    minHeight: 44,
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
    borderRadius: 14,
    borderWidth: 1,
    paddingHorizontal: 8,
  },
  secondaryTrigger: {
    width: 44,
    minHeight: 44,
    alignItems: "center",
    justifyContent: "center",
  },
  value: { flex: 1, minWidth: 0, fontSize: 12, fontWeight: "600", textAlign: "left" },
  editIcon: { flexShrink: 0 },
  modalRoot: { flex: 1, alignItems: "center", justifyContent: "center" },
  backdrop: {
    ...StyleSheet.absoluteFill,
    backgroundColor: "rgba(0, 0, 0, 0.58)",
  },
  dialog: {
    width: "86%",
    maxWidth: 390,
    borderRadius: radius.card,
    borderWidth: 1,
    padding: spacing.lg,
  },
  dialogTitle: { fontSize: 19, fontWeight: "600" },
  dialogDescription: { marginTop: 5, fontSize: 12, lineHeight: 18 },
  inputGroup: {
    height: 52,
    flexDirection: "row",
    alignItems: "center",
    marginTop: spacing.lg,
    borderWidth: 1,
    borderRadius: radius.md,
    paddingHorizontal: 14,
  },
  input: { flex: 1, fontSize: 18, fontWeight: "600" },
  unit: { fontSize: 12, fontWeight: "600" },
  actions: { flexDirection: "row", gap: 10, marginTop: spacing.lg },
  cancelButton: {
    minHeight: 46,
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
    borderRadius: 24,
    borderWidth: 1,
  },
  cancelText: { fontSize: 12, fontWeight: "600" },
  saveButton: {
    minHeight: 46,
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
    borderRadius: 24,
  },
  saveText: { fontSize: 12, fontWeight: "600" },
  pressed: { opacity: 0.58 },
});

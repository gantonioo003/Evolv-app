import { useState } from "react";
import { Pencil } from "lucide-react-native";
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

import { colors, radius, spacing } from "@/constants/theme";
import { useAppTheme } from "@/context/theme-context";

export function LoadStepper({
  value,
  onChange,
}: {
  value: number;
  onChange: (value: number) => void;
}) {
  const { palette } = useAppTheme();
  const [visible, setVisible] = useState(false);
  const [draft, setDraft] = useState(String(value));

  function open() {
    setDraft(String(value));
    setVisible(true);
  }

  function save() {
    const next = Number(draft.replace(",", "."));
    if (!Number.isFinite(next) || next < 0 || next > 1000) {
      Alert.alert("Carga inválida", "Informe um valor entre 0 e 1000 kg.");
      return;
    }
    onChange(Math.round(next * 10) / 10);
    setVisible(false);
  }

  return (
    <>
      <Pressable
        accessibilityLabel={`Editar carga atual de ${value} quilos`}
        accessibilityRole="button"
        onPress={open}
        style={({ pressed }) => [
          styles.trigger,
          { backgroundColor: palette.page, borderColor: palette.border },
          pressed && styles.pressed,
        ]}
      >
        <Text style={[styles.value, { color: palette.text }]}>{value} kg</Text>
        <Pencil color={colors.gold} size={14} strokeWidth={2.1} />
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
            accessibilityLabel="Fechar edição de carga"
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
              Editar carga
            </Text>
            <Text style={[styles.dialogDescription, { color: palette.muted }]}>
              Registre o peso realmente usado neste exercício.
            </Text>
            <View
              style={[
                styles.inputGroup,
                { backgroundColor: palette.page, borderColor: palette.border },
              ]}
            >
              <TextInput
                autoFocus
                keyboardType="decimal-pad"
                onChangeText={setDraft}
                placeholder="0"
                placeholderTextColor={palette.faint}
                selectTextOnFocus
                style={[styles.input, { color: palette.text }]}
                value={draft}
              />
              <Text style={[styles.unit, { color: palette.faint }]}>kg</Text>
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
                  pressed && styles.pressed,
                ]}
              >
                <Text style={styles.saveText}>Aplicar</Text>
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
    minWidth: 88,
    height: 38,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 7,
    borderRadius: radius.md,
    borderWidth: 1,
    paddingHorizontal: 10,
  },
  value: { fontSize: 12, fontWeight: "600", textAlign: "center" },
  modalRoot: { flex: 1, alignItems: "center", justifyContent: "center" },
  backdrop: {
    ...StyleSheet.absoluteFill,
    backgroundColor: "rgba(0, 0, 0, 0.58)",
  },
  dialog: {
    width: "86%",
    maxWidth: 390,
    borderRadius: radius.lg,
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
    backgroundColor: colors.red,
  },
  saveText: { color: colors.text, fontSize: 12, fontWeight: "600" },
  pressed: { opacity: 0.58 },
});

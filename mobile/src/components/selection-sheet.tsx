import { X } from "lucide-react-native";
import {
  Modal,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from "react-native";

import { radius, spacing } from "@/constants/theme";
import { useAppTheme } from "@/context/theme-context";

export type SelectionOption = {
  id: string;
  title: string;
  description?: string;
};

export function SelectionSheet({
  description,
  emptyText = "Nenhuma opção disponível.",
  loading = false,
  onClose,
  onSelect,
  options,
  title,
  visible,
}: {
  description?: string;
  emptyText?: string;
  loading?: boolean;
  onClose: () => void;
  onSelect: (option: SelectionOption) => void;
  options: SelectionOption[];
  title: string;
  visible: boolean;
}) {
  const { palette } = useAppTheme();

  return (
    <Modal
      animationType="slide"
      onRequestClose={onClose}
      transparent
      visible={visible}
    >
      <View style={styles.root}>
        <Pressable
          accessibilityLabel="Fechar opções"
          onPress={onClose}
          style={styles.backdrop}
        />
        <View
          style={[
            styles.sheet,
            { backgroundColor: palette.surface, borderColor: palette.border },
          ]}
        >
          <View style={styles.heading}>
            <View style={styles.headingCopy}>
              <Text style={[styles.title, { color: palette.text }]}>
                {title}
              </Text>
              {description ? (
                <Text style={[styles.description, { color: palette.muted }]}>
                  {description}
                </Text>
              ) : null}
            </View>
            <Pressable
              accessibilityLabel="Fechar"
              accessibilityRole="button"
              onPress={onClose}
              style={({ pressed }) => [
                styles.close,
                { borderColor: palette.border },
                pressed && styles.pressed,
              ]}
            >
              <X color={palette.text} size={18} />
            </Pressable>
          </View>

          <ScrollView
            contentContainerStyle={styles.options}
            showsVerticalScrollIndicator={false}
          >
            {options.map((option) => (
              <Pressable
                accessibilityRole="button"
                key={option.id}
                onPress={() => onSelect(option)}
                style={({ pressed }) => [
                  styles.option,
                  { borderColor: palette.border },
                  pressed && styles.pressed,
                ]}
              >
                <Text style={[styles.optionTitle, { color: palette.text }]}>
                  {option.title}
                </Text>
                {option.description ? (
                  <Text
                    style={[styles.optionDescription, { color: palette.muted }]}
                  >
                    {option.description}
                  </Text>
                ) : null}
              </Pressable>
            ))}
            {!options.length ? (
              <Text style={[styles.empty, { color: palette.muted }]}>
                {loading ? "Carregando opções..." : emptyText}
              </Text>
            ) : null}
          </ScrollView>
        </View>
      </View>
    </Modal>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, justifyContent: "flex-end" },
  backdrop: {
    ...StyleSheet.absoluteFill,
    backgroundColor: "rgba(0, 0, 0, 0.58)",
  },
  sheet: {
    maxHeight: "76%",
    borderTopLeftRadius: radius.lg,
    borderTopRightRadius: radius.lg,
    borderWidth: 1,
    paddingBottom: spacing.xl,
  },
  heading: {
    flexDirection: "row",
    alignItems: "flex-start",
    gap: 12,
    padding: spacing.lg,
  },
  headingCopy: { flex: 1 },
  title: { fontSize: 18, fontWeight: "600" },
  description: { marginTop: 5, fontSize: 12, lineHeight: 18 },
  close: {
    width: 38,
    height: 38,
    alignItems: "center",
    justifyContent: "center",
    borderRadius: 19,
    borderWidth: 1,
  },
  options: { gap: 8, paddingHorizontal: spacing.lg },
  option: { minHeight: 58, justifyContent: "center", borderBottomWidth: 1 },
  optionTitle: { fontSize: 13, fontWeight: "600" },
  optionDescription: { marginTop: 4, fontSize: 11, lineHeight: 16 },
  empty: { paddingVertical: spacing.xl, fontSize: 12, textAlign: "center" },
  pressed: { opacity: 0.58 },
});

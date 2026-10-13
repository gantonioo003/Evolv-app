import { useState } from "react";
import {
  Alert,
  Pressable,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";
import { BrainCircuit, CircleHelp, Database, Send } from "lucide-react-native";

import {
  AppScreen,
  CinematicHero,
  InfoRow,
  LabelIcon,
  PageHeader,
  SectionTitle,
  Tag,
} from "@/components/ui";
import { colors, radius, spacing } from "@/constants/theme";
import { useImagePreferences } from "@/context/image-preferences-context";
import { useAppTheme, type AppThemePalette } from "@/context/theme-context";
import { coachImages, pickWeeklyImage } from "@/data/image-library";
import { initialCoachMessages, quickCoachPrompts } from "@/data/mock-data";
import type { CoachMessage } from "@/types/domain";

export default function CoachScreen() {
  const { palette } = useAppTheme();
  const imagePreferences = useImagePreferences();
  const styles = createStyles(palette);
  const [messages, setMessages] =
    useState<CoachMessage[]>(initialCoachMessages);
  const [draft, setDraft] = useState("");

  function sendMessage(text = draft) {
    const normalized = text.trim();
    if (!normalized) return;

    const timestamp = Date.now();
    setMessages((current) => [
      ...current,
      { id: `user-${timestamp}`, sender: "user", text: normalized },
      {
        id: `coach-${timestamp}`,
        sender: "coach",
        text: "Entendi. Nesta fase a conversa usa uma resposta simulada; depois o Coach local consultará a base de conhecimento e enviará ações ao Planner.",
      },
    ]);
    setDraft("");
  }

  return (
    <AppScreen>
      <PageHeader
        eyebrow="Evolv"
        title="Coach"
        actionIcon={CircleHelp}
        actionLabel="Sobre o Coach"
        onAction={() =>
          Alert.alert(
            "Coach Evolv",
            "Um único Coach para dúvidas, explicações e ajustes de treino, dieta e rotina.",
          )
        }
      />

      <CinematicHero
        source={pickWeeklyImage(coachImages, imagePreferences, "coach", 0)}
        eyebrow="No seu ritmo"
        title="Vamos conversar."
        description="Treino, alimentação, recuperação. Qual é sua dúvida?"
        height={196}
        overlayOpacity={0.24}
      />

      <View style={styles.contextBand}>
        <InfoRow
          leading={<LabelIcon icon={BrainCircuit} />}
          title="Um Coach para todo o Evolv"
          description="Treino, dieta, rotina, dúvidas e explicações compartilham o mesmo contexto."
          trailing={<Tag color={colors.green}>Local</Tag>}
        />
      </View>

      <SectionTitle title="Conversa" meta="dados simulados" />
      <View style={styles.messages}>
        {messages.map((message) => (
          <View
            key={message.id}
            style={[
              styles.bubble,
              message.sender === "user"
                ? styles.userBubble
                : styles.coachBubble,
            ]}
          >
            <Text
              style={[
                styles.bubbleLabel,
                message.sender === "user" && styles.userBubbleLabel,
              ]}
            >
              {message.sender === "user" ? "Você" : "Coach Evolv"}
            </Text>
            <Text
              style={[
                styles.bubbleText,
                message.sender === "user" && styles.userBubbleText,
              ]}
            >
              {message.text}
            </Text>
          </View>
        ))}
      </View>

      <View style={styles.composer}>
        <TextInput
          accessibilityLabel="Mensagem para o Coach"
          multiline
          onChangeText={setDraft}
          onSubmitEditing={() => sendMessage()}
          placeholder="Fale com o Coach Evolv..."
          placeholderTextColor={palette.faint}
          style={styles.input}
          value={draft}
        />
        <Pressable
          accessibilityLabel="Enviar mensagem"
          accessibilityRole="button"
          onPress={() => sendMessage()}
          style={({ pressed }) => [
            styles.sendButton,
            pressed && styles.pressed,
          ]}
        >
          <Send color={colors.text} size={19} strokeWidth={2} />
        </Pressable>
      </View>

      <SectionTitle title="Atalhos" meta="opcional" />
      <View style={styles.prompts}>
        {quickCoachPrompts.map((prompt) => (
          <Pressable
            accessibilityRole="button"
            key={prompt}
            onPress={() => sendMessage(prompt)}
            style={({ pressed }) => [styles.prompt, pressed && styles.pressed]}
          >
            <Text style={styles.promptText}>{prompt}</Text>
          </Pressable>
        ))}
      </View>

      <View style={styles.memoryBand}>
        <InfoRow
          leading={<LabelIcon icon={Database} />}
          title="Memória opcional"
          description="Preferências e conversas só serão guardadas quando você permitir nas configurações."
        />
      </View>
    </AppScreen>
  );
}

const createStyles = (palette: AppThemePalette) =>
  StyleSheet.create({
    messages: { gap: 10 },
    contextBand: {
      borderTopWidth: 1,
      borderBottomWidth: 1,
      borderColor: palette.border,
      paddingHorizontal: spacing.xs,
    },
    memoryBand: {
      borderLeftWidth: 4,
      borderLeftColor: palette.border,
      backgroundColor: palette.elevated,
      paddingHorizontal: spacing.md,
    },
    bubble: {
      maxWidth: "88%",
      borderRadius: radius.lg,
      paddingHorizontal: 14,
      paddingVertical: 12,
    },
    coachBubble: {
      alignSelf: "flex-start",
      backgroundColor: palette.surface,
      borderWidth: 1,
      borderColor: palette.border,
    },
    userBubble: {
      alignSelf: "flex-end",
      backgroundColor: colors.redDark,
      borderWidth: 1,
      borderColor: colors.red,
    },
    bubbleLabel: {
      marginBottom: 4,
      color: palette.muted,
      fontSize: 11,
      fontWeight: "600",
      textTransform: "none",
    },
    userBubbleLabel: { color: "#EBC7C2" },
    bubbleText: { color: palette.text, fontSize: 14, lineHeight: 21 },
    userBubbleText: { color: colors.text },
    composer: {
      minHeight: 54,
      flexDirection: "row",
      alignItems: "flex-end",
      gap: 8,
    },
    input: {
      flex: 1,
      maxHeight: 120,
      minHeight: 50,
      borderRadius: radius.lg,
      borderWidth: 1,
      borderColor: palette.border,
      backgroundColor: palette.surface,
      paddingHorizontal: 14,
      paddingVertical: 13,
      color: palette.text,
      fontSize: 14,
    },
    sendButton: {
      width: 50,
      height: 50,
      borderRadius: radius.lg,
      alignItems: "center",
      justifyContent: "center",
      backgroundColor: colors.red,
    },
    prompts: { flexDirection: "row", flexWrap: "wrap", gap: spacing.sm },
    prompt: {
      minHeight: 38,
      justifyContent: "center",
      borderRadius: 19,
      borderWidth: 1,
      borderColor: palette.border,
      backgroundColor: palette.elevated,
      paddingHorizontal: 13,
    },
    promptText: { color: palette.muted, fontSize: 11.5, fontWeight: "700" },
    pressed: { opacity: 0.65 },
  });

import { Alert, Pressable, StyleSheet, Text, View } from "react-native";
import { useRouter } from "expo-router";
import {
  ArrowLeft,
  Bell,
  BrainCircuit,
  ChevronRight,
  CircleHelp,
  Goal,
  Info,
  Images,
  Languages,
  LockKeyhole,
  LogOut,
  Palette,
  UserRound,
} from "lucide-react-native";

import {
  AppScreen,
  Divider,
  InfoRow,
  LabelIcon,
  SectionTitle,
  Surface,
} from "@/components/ui";
import { radius, spacing, typography } from "@/constants/theme";
import { useAuth } from "@/context/auth-context";
import { useAppTheme, type AppThemePalette } from "@/context/theme-context";

export default function SettingsScreen() {
  const { palette, resolvedTheme } = useAppTheme();
  const styles = createStyles(palette);
  const router = useRouter();
  const { signOut } = useAuth();
  const showPlaceholder = (title: string) =>
    Alert.alert(title, "Esta configuração será conectada nas próximas fases.");

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
          <Text style={styles.eyebrow}>Conta</Text>
          <Text style={styles.title}>Configurações</Text>
        </View>
      </View>

      <SectionTitle title="Conta" meta="dados principais" />
      <Surface>
        <SettingRow
          icon={UserRound}
          title="Dados pessoais"
          description="Nome, foto, data de nascimento e contato"
          onPress={() => showPlaceholder("Dados pessoais")}
        />
        <Divider />
        <SettingRow
          icon={Goal}
          title="Objetivo e rotina"
          description="Meta, nível, horários e disponibilidade"
          onPress={() => showPlaceholder("Objetivo e rotina")}
        />
        <Divider />
        <SettingRow
          icon={Bell}
          title="Notificações"
          description="Horários de treino, refeições e lembretes"
          onPress={() => showPlaceholder("Notificações")}
        />
      </Surface>

      <SectionTitle title="Preferências do aplicativo" />
      <Surface>
        <SettingRow
          icon={Palette}
          title="Aparência"
          description={resolvedTheme === "dark" ? "Modo escuro" : "Modo claro"}
          onPress={() => router.push("/appearance")}
        />
        <Divider />
        <SettingRow
          icon={Images}
          title="Imagens do app"
          description="Variação de pessoas e estilo físico"
          onPress={() => router.push("/image-preferences")}
        />
        <Divider />
        <SettingRow
          icon={Languages}
          title="Idioma e região"
          description="Português (Brasil)"
          onPress={() => showPlaceholder("Idioma e região")}
        />
      </Surface>

      <SectionTitle title="Coach e privacidade" />
      <Surface>
        <SettingRow
          icon={BrainCircuit}
          title="Memória do Coach"
          description="Conversas e contexto salvos com sua permissão"
          onPress={() => showPlaceholder("Memória do Coach")}
        />
        <Divider />
        <SettingRow
          icon={LockKeyhole}
          title="Privacidade e dados"
          description="Fotos, histórico, exportação e exclusão"
          onPress={() => showPlaceholder("Privacidade e dados")}
        />
      </Surface>

      <SectionTitle title="Ajuda" />
      <Surface>
        <SettingRow
          icon={CircleHelp}
          title="Ajuda e suporte"
          description="Dúvidas, problemas e contato"
          onPress={() => showPlaceholder("Ajuda e suporte")}
        />
        <Divider />
        <SettingRow
          icon={Info}
          title="Sobre o Evolv"
          description="Versão, termos e política de privacidade"
          onPress={() => showPlaceholder("Sobre o Evolv")}
        />
      </Surface>

      <Surface>
        <SettingRow
          icon={LogOut}
          title="Sair da conta"
          description="Encerrar a sessão neste aparelho"
          onPress={() => {
            void signOut().then(() => router.replace("/login"));
          }}
        />
      </Surface>

      <Text style={styles.version}>Evolv 0.1.0</Text>
    </AppScreen>
  );
}

function SettingRow({
  icon,
  title,
  description,
  onPress,
}: {
  icon: typeof Bell;
  title: string;
  description: string;
  onPress: () => void;
}) {
  const { palette } = useAppTheme();

  return (
    <InfoRow
      leading={<LabelIcon icon={icon} />}
      title={title}
      description={description}
      trailing={<ChevronRight color={palette.faint} size={18} />}
      onPress={onPress}
    />
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
    },
    version: { color: palette.faint, fontSize: 11, textAlign: "center" },
    pressed: { opacity: 0.66 },
  });

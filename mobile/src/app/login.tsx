import { useEffect, useState } from "react";
import { useRouter } from "expo-router";
import {
  Apple,
  Eye,
  EyeOff,
  LogIn,
  Mail,
  UserRound,
} from "lucide-react-native";
import {
  Alert,
  Keyboard,
  KeyboardAvoidingView,
  Platform,
  Pressable,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";

import { AppScreen, CinematicHero } from "@/components/ui";
import { colors, radius, spacing } from "@/constants/theme";
import { useAuth } from "@/context/auth-context";
import { useAppTheme, type AppThemePalette } from "@/context/theme-context";

export default function LoginScreen() {
  const { palette } = useAppTheme();
  const styles = createStyles(palette);
  const router = useRouter();
  const { isConfigured, signIn, signUp } = useAuth();
  const [mode, setMode] = useState<"login" | "signup">("login");
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [keyboardVisible, setKeyboardVisible] = useState(false);

  useEffect(() => {
    const showSubscription = Keyboard.addListener("keyboardDidShow", () =>
      setKeyboardVisible(true),
    );
    const hideSubscription = Keyboard.addListener("keyboardDidHide", () =>
      setKeyboardVisible(false),
    );

    return () => {
      showSubscription.remove();
      hideSubscription.remove();
    };
  }, []);

  async function submit() {
    if (!email.trim() || password.length < 6) {
      setError("Informe um e-mail e uma senha com pelo menos 6 caracteres.");
      return;
    }

    setIsSubmitting(true);
    setError(null);
    try {
      if (mode === "login") {
        await signIn(email, password);
        router.replace("/(tabs)");
        return;
      }

      const result = await signUp(email, password, fullName);
      if (result.needsEmailConfirmation) {
        Alert.alert(
          "Confirme seu e-mail",
          "Enviamos um link de confirmação. Depois, volte para entrar.",
        );
        setMode("login");
      } else {
        router.replace("/onboarding");
      }
    } catch (caught) {
      setError(
        caught instanceof Error ? caught.message : "Nao foi possivel entrar.",
      );
    } finally {
      setIsSubmitting(false);
    }
  }

  function showSocialSetup(provider: string) {
    Alert.alert(
      `${provider} ainda nao configurado`,
      "O fluxo por e-mail ja funciona. Este provedor precisa ser ativado no painel do Supabase antes de aparecer como disponivel.",
    );
  }

  return (
    <AppScreen scroll={false} contentStyle={styles.screenContent}>
      <KeyboardAvoidingView
        behavior={Platform.OS === "ios" ? "padding" : undefined}
        style={styles.keyboardView}
      >
        {!keyboardVisible ? (
          <CinematicHero
            source={require("@/assets/images/old-school-gym.png")}
            eyebrow="Evolv"
            title={"Seu plano.\nSeu ritmo."}
            description="Treino, dieta e evolução para o longo prazo."
            height={mode === "signup" ? 146 : 168}
            overlayOpacity={0.3}
          />
        ) : null}

        <View style={styles.form}>
          <View style={styles.heading}>
            <Text style={styles.title}>
              {mode === "login" ? "Entrar no Evolv" : "Criar sua conta"}
            </Text>
            <Text style={styles.description}>
              {!isConfigured
                ? "Configure o arquivo mobile/.env.local para habilitar a autenticação."
                : mode === "login"
                  ? "Continue de onde parou."
                  : "Comece no seu ritmo e ajuste tudo depois."}
            </Text>
          </View>

          <Pressable
            accessibilityRole="button"
            onPress={() => showSocialSetup("Google")}
            style={({ pressed }) => [
              styles.providerButton,
              pressed && styles.pressed,
            ]}
          >
            <View style={styles.googleMark}>
              <Text style={styles.googleText}>G</Text>
            </View>
            <Text style={styles.providerText}>Continuar com Google</Text>
          </Pressable>
          <Pressable
            accessibilityRole="button"
            onPress={() => showSocialSetup("Apple")}
            style={({ pressed }) => [
              styles.providerButton,
              pressed && styles.pressed,
            ]}
          >
            <Apple color={palette.text} size={20} fill={palette.text} />
            <Text style={styles.providerText}>Continuar com Apple</Text>
          </Pressable>

          <View style={styles.dividerRow}>
            <View style={styles.line} />
            <Text style={styles.or}>ou</Text>
            <View style={styles.line} />
          </View>

          {mode === "signup" ? (
            <View style={styles.inputGroup}>
              <UserRound color={palette.muted} size={18} />
              <TextInput
                autoCapitalize="words"
                autoComplete="name"
                onChangeText={setFullName}
                placeholder="Nome (opcional)"
                placeholderTextColor={palette.faint}
                style={styles.input}
                value={fullName}
              />
            </View>
          ) : null}

          <View style={styles.inputGroup}>
            <Mail color={palette.muted} size={18} />
            <TextInput
              autoCapitalize="none"
              autoComplete="email"
              keyboardType="email-address"
              onChangeText={setEmail}
              placeholder="E-mail"
              placeholderTextColor={palette.faint}
              style={styles.input}
              value={email}
            />
          </View>
          <View style={styles.inputGroup}>
            <LogIn color={palette.muted} size={18} />
            <TextInput
              autoComplete="password"
              onChangeText={setPassword}
              placeholder="Senha"
              placeholderTextColor={palette.faint}
              secureTextEntry={!showPassword}
              style={styles.input}
              value={password}
            />
            <Pressable
              accessibilityLabel={
                showPassword ? "Ocultar senha" : "Mostrar senha"
              }
              onPress={() => setShowPassword((current) => !current)}
              style={styles.eyeButton}
            >
              {showPassword ? (
                <EyeOff color={palette.muted} size={18} />
              ) : (
                <Eye color={palette.muted} size={18} />
              )}
            </Pressable>
          </View>

          {error ? <Text style={styles.error}>{error}</Text> : null}

          <Pressable
            accessibilityRole="button"
            disabled={isSubmitting || !isConfigured}
            onPress={() => void submit()}
            style={({ pressed }) => [
              styles.primaryButton,
              (!isConfigured || isSubmitting) && styles.disabled,
              pressed && styles.pressed,
            ]}
          >
            <Text style={styles.primaryButtonText}>
              {isSubmitting
                ? "Aguarde..."
                : mode === "login"
                  ? "Entrar com e-mail"
                  : "Criar conta"}
            </Text>
          </Pressable>
          <Pressable
            accessibilityRole="button"
            onPress={() => {
              setError(null);
              setMode((current) => (current === "login" ? "signup" : "login"));
            }}
            style={styles.createButton}
          >
            <Text style={styles.createText}>
              {mode === "login" ? "Criar uma conta" : "Já tenho uma conta"}
            </Text>
          </Pressable>
        </View>
      </KeyboardAvoidingView>
    </AppScreen>
  );
}

const createStyles = (palette: AppThemePalette) =>
  StyleSheet.create({
    screenContent: {
      paddingTop: spacing.sm,
      paddingBottom: spacing.sm,
      gap: 0,
    },
    keyboardView: { flex: 1, justifyContent: "center", gap: 10 },
    form: { gap: 9 },
    heading: { gap: 2 },
    title: { color: palette.text, fontSize: 20, fontWeight: "900" },
    description: { color: palette.muted, fontSize: 12.5, lineHeight: 18 },
    providerButton: {
      height: 46,
      flexDirection: "row",
      alignItems: "center",
      justifyContent: "center",
      gap: 10,
      borderRadius: radius.lg,
      borderWidth: 1,
      borderColor: palette.border,
      backgroundColor: palette.surface,
    },
    providerText: { color: palette.text, fontSize: 14, fontWeight: "800" },
    googleMark: {
      width: 22,
      height: 22,
      borderRadius: 11,
      alignItems: "center",
      justifyContent: "center",
      backgroundColor: colors.paper,
    },
    googleText: { color: colors.ink, fontSize: 13, fontWeight: "900" },
    dividerRow: { flexDirection: "row", alignItems: "center", gap: spacing.md },
    line: {
      flex: 1,
      height: StyleSheet.hairlineWidth,
      backgroundColor: palette.border,
    },
    or: { color: palette.faint, fontSize: 11, textTransform: "uppercase" },
    inputGroup: {
      minHeight: 46,
      flexDirection: "row",
      alignItems: "center",
      gap: 10,
      borderRadius: radius.lg,
      borderWidth: 1,
      borderColor: palette.border,
      backgroundColor: palette.elevated,
      paddingHorizontal: 14,
    },
    input: { flex: 1, color: palette.text, fontSize: 14, paddingVertical: 10 },
    eyeButton: {
      width: 34,
      height: 40,
      alignItems: "center",
      justifyContent: "center",
    },
    primaryButton: {
      height: 48,
      alignItems: "center",
      justifyContent: "center",
      borderRadius: radius.lg,
      backgroundColor: colors.red,
    },
    primaryButtonText: { color: colors.text, fontSize: 14, fontWeight: "900" },
    createButton: {
      height: 34,
      alignItems: "center",
      justifyContent: "center",
    },
    createText: { color: colors.gold, fontSize: 13, fontWeight: "800" },
    error: {
      color: colors.red,
      fontSize: 12,
      lineHeight: 17,
      textAlign: "center",
    },
    disabled: { opacity: 0.45 },
    pressed: { opacity: 0.65 },
  });

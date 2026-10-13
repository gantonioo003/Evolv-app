import {
  useEffect,
  useRef,
  useState,
  type ReactNode,
  type RefObject,
} from "react";
import { useRouter } from "expo-router";
import AsyncStorage from "@react-native-async-storage/async-storage";
import { ArrowLeft, Eye, EyeOff } from "lucide-react-native";
import {
  ActivityIndicator,
  Image,
  Keyboard,
  KeyboardAvoidingView,
  Platform,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
  useWindowDimensions,
  type TextInputProps,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { CoverImage } from "@/components/ui";
import { colors, typography } from "@/constants/theme";
import { useAuth } from "@/context/auth-context";
import { useAppTheme } from "@/context/theme-context";
import { authPhotos, nextAuthPhotoIndex } from "@/data/auth-photos";

const AUTH_PHOTO_KEY = "@evolv/auth-photo-index";

type AuthMode = "login" | "signup";
type AuthPalette = {
  page: string;
  text: string;
  muted: string;
  border: string;
  input: string;
  focus: string;
};

function authErrorMessage(caught: unknown) {
  const message = caught instanceof Error ? caught.message.toLowerCase() : "";
  if (message.includes("invalid login credentials"))
    return "E-mail ou senha incorretos. Confira os dados e tente novamente.";
  if (message.includes("email not confirmed"))
    return "Confirme seu e-mail pelo link que enviamos antes de entrar.";
  if (message.includes("rate limit") || message.includes("too many requests"))
    return "Muitas tentativas em pouco tempo. Aguarde um momento e tente novamente.";
  if (message.includes("already registered"))
    return "Não foi possível criar a conta com esses dados. Tente entrar.";
  if (message.includes("password"))
    return "Essa senha não atende aos requisitos. Use pelo menos 6 caracteres.";
  if (message.includes("fetch") || message.includes("network"))
    return "Não conseguimos conectar. Confira sua internet e tente novamente.";
  return "Não foi possível continuar agora. Tente novamente em instantes.";
}

function AuthField({
  label,
  optional,
  inputRef,
  palette,
  trailing,
  ...inputProps
}: TextInputProps & {
  label: string;
  optional?: boolean;
  inputRef: RefObject<TextInput | null>;
  palette: AuthPalette;
  trailing?: ReactNode;
}) {
  const [focused, setFocused] = useState(false);
  return (
    <View style={styles.field}>
      <Text style={[styles.label, { color: palette.text }]}>
        {label}
        {optional ? (
          <Text style={[styles.optional, { color: palette.muted }]}>
            {" "}
            (opcional)
          </Text>
        ) : null}
      </Text>
      <View
        style={[
          styles.inputRow,
          {
            backgroundColor: palette.input,
            borderColor: focused ? palette.focus : palette.border,
          },
        ]}
      >
        <TextInput
          {...inputProps}
          ref={inputRef}
          accessibilityLabel={label}
          placeholderTextColor={palette.muted}
          selectionColor={palette.focus}
          onFocus={() => setFocused(true)}
          onBlur={() => setFocused(false)}
          style={[styles.input, { color: palette.text }]}
        />
        {trailing}
      </View>
    </View>
  );
}

export default function LoginScreen() {
  const { isDark } = useAppTheme();
  const { width, height } = useWindowDimensions();
  const [viewportHeight, setViewportHeight] = useState(height);
  const [contentHeight, setContentHeight] = useState(0);
  const wide = width >= 980;
  const compact = viewportHeight < 760;
  const palette: AuthPalette = isDark
    ? {
        page: "#101112",
        text: "#F5F5F5",
        muted: "#A0A1A3",
        border: "#393B3D",
        input: "#18191B",
        focus: "#B6B8BB",
      }
    : {
        page: "#FFFFFF",
        text: "#1B1C1E",
        muted: "#696C71",
        border: "#D5D7DA",
        input: "#F8F9FA",
        focus: "#777B82",
      };
  const router = useRouter();
  const { isConfigured, signIn, signUp } = useAuth();
  const [mode, setMode] = useState<AuthMode>("login");
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [keyboardVisible, setKeyboardVisible] = useState(false);
  const nameRef = useRef<TextInput>(null);
  const emailRef = useRef<TextInput>(null);
  const passwordRef = useRef<TextInput>(null);
  const [photoIndex, setPhotoIndex] = useState<number | null>(null);
  const photoSelected = useRef(false);

  useEffect(() => {
    if (!wide || photoSelected.current) return;
    let active = true;

    async function selectPhoto() {
      const saved = await AsyncStorage.getItem(AUTH_PHOTO_KEY).catch(
        () => null,
      );
      if (!active || photoSelected.current) return;
      const next = nextAuthPhotoIndex(saved);
      photoSelected.current = true;
      setPhotoIndex(next);
      await AsyncStorage.setItem(AUTH_PHOTO_KEY, String(next)).catch(
        () => undefined,
      );
    }

    void selectPhoto();
    return () => {
      active = false;
    };
  }, [wide]);

  useEffect(() => {
    const show = Keyboard.addListener("keyboardDidShow", () =>
      setKeyboardVisible(true),
    );
    const hide = Keyboard.addListener("keyboardDidHide", () =>
      setKeyboardVisible(false),
    );
    return () => {
      show.remove();
      hide.remove();
    };
  }, []);

  function changeMode(next: AuthMode) {
    if (isSubmitting) return;
    setMode(next);
    setError(null);
    setNotice(null);
    setPassword("");
    setShowPassword(false);
    Keyboard.dismiss();
  }

  async function submit() {
    if (isSubmitting || !isConfigured) return;
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim())) {
      setError("Informe um e-mail válido.");
      emailRef.current?.focus();
      return;
    }
    if (!password || (mode === "signup" && password.length < 6)) {
      setError(
        mode === "signup"
          ? "Use uma senha com pelo menos 6 caracteres."
          : "Informe sua senha.",
      );
      passwordRef.current?.focus();
      return;
    }
    setIsSubmitting(true);
    setError(null);
    setNotice(null);
    Keyboard.dismiss();
    try {
      if (mode === "login") {
        await signIn(email, password);
        router.replace("/(tabs)");
      } else {
        const result = await signUp(email, password, fullName);
        if (result.needsEmailConfirmation) {
          setMode("login");
          setPassword("");
          setShowPassword(false);
          setNotice(
            "Confira seu e-mail e confirme a conta pelo link enviado. Depois, entre por aqui.",
          );
        } else {
          router.replace("/onboarding");
        }
      }
    } catch (caught) {
      setError(authErrorMessage(caught));
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <View
      nativeID="evolv-auth"
      style={[styles.screen, { backgroundColor: palette.page }]}
    >
      {Platform.OS === "web" ? (
        <style>{`
          #evolv-auth input {
            color-scheme: ${isDark ? "dark" : "light"};
            outline: none;
          }
          #evolv-auth input:-webkit-autofill,
          #evolv-auth input:-webkit-autofill:hover,
          #evolv-auth input:-webkit-autofill:focus {
            -webkit-box-shadow: 0 0 0 1000px ${palette.input} inset;
            -webkit-text-fill-color: ${palette.text};
            caret-color: ${palette.text};
          }
        `}</style>
      ) : null}
      {wide ? (
        <View style={styles.photograph} testID="auth-photograph">
          {photoIndex !== null ? (
            <CoverImage
              source={authPhotos[photoIndex]}
              style={StyleSheet.absoluteFill}
            />
          ) : null}
          <View style={styles.photoCaption}>
            <Text style={styles.photoBrand}>Evolv</Text>
            <Text style={styles.photoText}>Seu ritmo. Sua evolução.</Text>
          </View>
        </View>
      ) : null}
      <SafeAreaView style={styles.authPane}>
        <KeyboardAvoidingView
          behavior={Platform.OS === "ios" ? "padding" : undefined}
          style={styles.keyboardView}
        >
          <ScrollView
            onLayout={(event) =>
              setViewportHeight(event.nativeEvent.layout.height)
            }
            onContentSizeChange={(_, contentSize) =>
              setContentHeight(contentSize)
            }
            contentContainerStyle={[
              styles.scrollContent,
              compact && styles.compactContent,
            ]}
            keyboardShouldPersistTaps="handled"
            keyboardDismissMode="on-drag"
            showsVerticalScrollIndicator={false}
            bounces={false}
            scrollEnabled={
              keyboardVisible || contentHeight > viewportHeight + 1
            }
          >
            <View style={[styles.form, compact && styles.compactForm]}>
              <View style={styles.brandRow}>
                <Text style={[styles.brand, { color: palette.text }]}>
                  Evolv<Text style={styles.brandDot}>.</Text>
                </Text>
                {mode === "signup" ? (
                  <Pressable
                    accessibilityRole="button"
                    accessibilityLabel="Voltar para entrar"
                    disabled={isSubmitting}
                    onPress={() => changeMode("login")}
                    style={styles.backButton}
                  >
                    <ArrowLeft
                      color={palette.muted}
                      size={21}
                      strokeWidth={1.8}
                    />
                  </Pressable>
                ) : null}
              </View>
              <View style={styles.heading}>
                <Text
                  accessibilityRole="header"
                  style={[styles.title, { color: palette.text }]}
                >
                  {mode === "login"
                    ? "Bom ter você de volta."
                    : "Crie sua conta."}
                </Text>
                <Text style={[styles.description, { color: palette.muted }]}>
                  {mode === "login"
                    ? "Entre para continuar seu plano."
                    : "Seu treino, sua alimentação. No seu ritmo."}
                </Text>
              </View>

              <View style={styles.fields}>
                {mode === "signup" ? (
                  <AuthField
                    label="Nome"
                    optional
                    palette={palette}
                    inputRef={nameRef}
                    autoCapitalize="words"
                    autoComplete="name"
                    textContentType="name"
                    placeholder="Como podemos chamar você?"
                    value={fullName}
                    onChangeText={setFullName}
                    returnKeyType="next"
                    onSubmitEditing={() => emailRef.current?.focus()}
                    editable={!isSubmitting}
                  />
                ) : null}
                <AuthField
                  label="E-mail"
                  palette={palette}
                  inputRef={emailRef}
                  autoCapitalize="none"
                  autoCorrect={false}
                  autoComplete="email"
                  textContentType="emailAddress"
                  keyboardType="email-address"
                  placeholder="voce@exemplo.com"
                  value={email}
                  onChangeText={setEmail}
                  returnKeyType="next"
                  onSubmitEditing={() => passwordRef.current?.focus()}
                  editable={!isSubmitting}
                />
                <AuthField
                  label="Senha"
                  palette={palette}
                  inputRef={passwordRef}
                  autoCapitalize="none"
                  autoCorrect={false}
                  autoComplete={
                    mode === "signup" ? "new-password" : "current-password"
                  }
                  textContentType={
                    mode === "signup" ? "newPassword" : "password"
                  }
                  placeholder={
                    mode === "signup" ? "Pelo menos 6 caracteres" : "Sua senha"
                  }
                  value={password}
                  onChangeText={setPassword}
                  secureTextEntry={!showPassword}
                  returnKeyType="go"
                  onSubmitEditing={() => void submit()}
                  editable={!isSubmitting}
                  trailing={
                    <Pressable
                      accessibilityRole="button"
                      accessibilityLabel={
                        showPassword ? "Ocultar senha" : "Mostrar senha"
                      }
                      disabled={isSubmitting}
                      onPress={() => setShowPassword((current) => !current)}
                      style={styles.eyeButton}
                    >
                      {showPassword ? (
                        <EyeOff
                          color={palette.muted}
                          size={19}
                          strokeWidth={1.6}
                        />
                      ) : (
                        <Eye
                          color={palette.muted}
                          size={19}
                          strokeWidth={1.6}
                        />
                      )}
                    </Pressable>
                  }
                />
              </View>

              {error ? (
                <Text
                  accessibilityRole="alert"
                  accessibilityLiveRegion="polite"
                  style={[
                    styles.error,
                    { color: isDark ? "#F08980" : "#B3261E" },
                  ]}
                >
                  {error}
                </Text>
              ) : null}
              {notice ? (
                <Text
                  accessibilityLiveRegion="polite"
                  style={[styles.notice, { color: palette.text }]}
                >
                  {notice}
                </Text>
              ) : null}
              {!isConfigured ? (
                <Text
                  style={[
                    styles.error,
                    { color: isDark ? "#F08980" : "#B3261E" },
                  ]}
                >
                  A entrada está temporariamente indisponível.
                </Text>
              ) : null}

              <Pressable
                accessibilityRole="button"
                disabled={isSubmitting || !isConfigured}
                onPress={() => void submit()}
                style={({ pressed }) => [
                  styles.primaryButton,
                  (isSubmitting || !isConfigured) && styles.disabled,
                  pressed && styles.pressed,
                ]}
              >
                {isSubmitting ? (
                  <ActivityIndicator color="#FFFFFF" size="small" />
                ) : null}
                <Text style={styles.primaryButtonText}>
                  {isSubmitting
                    ? "Aguarde..."
                    : mode === "login"
                      ? "Entrar"
                      : "Criar conta"}
                </Text>
              </Pressable>

              <View style={styles.dividerRow}>
                <View
                  style={[styles.line, { backgroundColor: palette.border }]}
                />
                <Text style={[styles.or, { color: palette.muted }]}>ou</Text>
                <View
                  style={[styles.line, { backgroundColor: palette.border }]}
                />
              </View>

              <View style={styles.providers}>
                <Pressable
                  accessibilityRole="button"
                  accessibilityLabel="Continuar com Google, em breve"
                  disabled
                  style={[styles.providerButton, styles.googleButton]}
                >
                  <Image
                    source={require("@/assets/images/auth-google.png")}
                    style={styles.googleIcon}
                    resizeMode="contain"
                  />
                  <Text style={[styles.providerText, styles.googleText]}>
                    Continuar com Google
                  </Text>
                </Pressable>
                <Pressable
                  accessibilityRole="button"
                  accessibilityLabel="Continuar com Apple, em breve"
                  disabled
                  style={[
                    styles.providerButton,
                    {
                      backgroundColor: isDark ? "#000000" : "#FFFFFF",
                      borderColor: palette.border,
                    },
                  ]}
                >
                  <Image
                    source={
                      isDark
                        ? require("@/assets/images/auth-apple-dark.png")
                        : require("@/assets/images/auth-apple-light.png")
                    }
                    style={styles.appleIcon}
                    resizeMode="contain"
                  />
                  <Text style={[styles.providerText, { color: palette.text }]}>
                    Continuar com Apple
                  </Text>
                </Pressable>
                <Text style={[styles.providerNotice, { color: palette.muted }]}>
                  Google e Apple disponíveis em breve.
                </Text>
              </View>

              <View style={[styles.switchRow, { borderColor: palette.border }]}>
                <Text style={[styles.switchPrompt, { color: palette.muted }]}>
                  {mode === "login"
                    ? "Ainda não tem uma conta?"
                    : "Já tem uma conta?"}
                </Text>
                <Pressable
                  accessibilityRole="button"
                  disabled={isSubmitting}
                  onPress={() =>
                    changeMode(mode === "login" ? "signup" : "login")
                  }
                  style={({ pressed }) => [
                    styles.switchButton,
                    pressed && styles.pressed,
                  ]}
                >
                  <Text style={[styles.switchText, { color: palette.text }]}>
                    {mode === "login" ? "Criar uma conta" : "Entrar"}
                  </Text>
                </Pressable>
              </View>
            </View>
          </ScrollView>
        </KeyboardAvoidingView>
      </SafeAreaView>
    </View>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1, flexDirection: "row" },
  photograph: { flex: 1, backgroundColor: "#222526", overflow: "hidden" },
  photoCaption: {
    position: "absolute",
    left: 0,
    right: 0,
    bottom: 0,
    paddingHorizontal: 40,
    paddingVertical: 32,
    backgroundColor: "#101112DD",
    gap: 6,
  },
  photoBrand: {
    fontFamily: typography.body,
    fontSize: 36,
    fontWeight: "600",
    color: "#FFFFFF",
    letterSpacing: 0,
  },
  photoText: {
    fontFamily: typography.body,
    fontSize: 17,
    lineHeight: 25,
    color: "#E0E2E4",
  },
  authPane: { flex: 1, minWidth: 0 },
  keyboardView: { flex: 1 },
  scrollContent: {
    flexGrow: 1,
    justifyContent: "center",
    alignItems: "center",
    paddingHorizontal: 24,
    paddingVertical: 28,
  },
  compactContent: { paddingVertical: 16 },
  form: { width: "100%", maxWidth: 392, gap: 20 },
  compactForm: { gap: 14 },
  brandRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    minHeight: 44,
  },
  brand: {
    fontFamily: typography.body,
    fontSize: 34,
    fontWeight: "600",
    letterSpacing: 0,
  },
  brandDot: { color: colors.red },
  backButton: {
    width: 44,
    height: 44,
    alignItems: "center",
    justifyContent: "center",
  },
  heading: { gap: 8 },
  title: {
    fontFamily: typography.body,
    fontSize: 25,
    lineHeight: 32,
    fontWeight: "600",
    letterSpacing: 0,
  },
  description: { fontFamily: typography.body, fontSize: 14, lineHeight: 21 },
  fields: { gap: 16 },
  field: { gap: 8 },
  label: {
    fontFamily: typography.body,
    fontSize: 13,
    lineHeight: 18,
    fontWeight: "500",
  },
  optional: { fontWeight: "400" },
  inputRow: {
    flexDirection: "row",
    alignItems: "center",
    height: 50,
    borderWidth: 1,
    borderRadius: 8,
    overflow: "hidden",
  },
  input: {
    fontFamily: typography.body,
    flex: 1,
    minWidth: 0,
    height: "100%",
    fontSize: 16,
    paddingHorizontal: 14,
    paddingVertical: 10,
    ...Platform.select({ web: { outlineWidth: 0 } }),
  },
  eyeButton: {
    width: 46,
    height: 48,
    alignItems: "center",
    justifyContent: "center",
  },
  primaryButton: {
    height: 48,
    borderRadius: 24,
    backgroundColor: colors.red,
    flexDirection: "row",
    gap: 10,
    alignItems: "center",
    justifyContent: "center",
  },
  primaryButtonText: {
    fontFamily: typography.body,
    fontSize: 15,
    fontWeight: "600",
    color: "#FFFFFF",
  },
  dividerRow: { flexDirection: "row", gap: 16, alignItems: "center" },
  line: { flex: 1, height: StyleSheet.hairlineWidth },
  or: { fontFamily: typography.body, fontSize: 12, lineHeight: 16 },
  providers: { gap: 10 },
  providerButton: {
    height: 44,
    borderWidth: 1,
    borderRadius: 22,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 10,
  },
  providerText: {
    fontFamily: typography.body,
    fontSize: 14,
    fontWeight: "500",
  },
  googleButton: { backgroundColor: "#FFFFFF", borderColor: "#747775" },
  googleText: { color: "#1F1F1F" },
  googleIcon: { width: 20, height: 20 },
  appleIcon: { width: 40, height: 40 },
  providerNotice: {
    fontFamily: typography.body,
    fontSize: 11,
    lineHeight: 16,
    textAlign: "center",
  },
  switchRow: {
    borderTopWidth: StyleSheet.hairlineWidth,
    paddingTop: 12,
    alignItems: "center",
    gap: 0,
  },
  switchPrompt: { fontFamily: typography.body, fontSize: 13, lineHeight: 20 },
  switchButton: {
    minHeight: 44,
    paddingHorizontal: 16,
    alignItems: "center",
    justifyContent: "center",
  },
  switchText: { fontFamily: typography.body, fontSize: 14, fontWeight: "600" },
  error: {
    fontFamily: typography.body,
    fontSize: 13,
    lineHeight: 19,
    color: "#E16D64",
  },
  notice: { fontFamily: typography.body, fontSize: 13, lineHeight: 19 },
  disabled: { opacity: 0.5 },
  pressed: { opacity: 0.75 },
});

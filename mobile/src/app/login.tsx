import { useState } from 'react';
import { useRouter } from 'expo-router';
import { Apple, Eye, EyeOff, LogIn, Mail } from 'lucide-react-native';
import { Pressable, StyleSheet, Text, TextInput, View } from 'react-native';

import { AppScreen, CinematicHero } from '@/components/ui';
import { colors, radius, spacing } from '@/constants/theme';
import { useAppTheme, type AppThemePalette } from '@/context/theme-context';

export default function LoginScreen() {
  const { palette } = useAppTheme();
  const styles = createStyles(palette);
  const router = useRouter();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const enter = () => router.replace('/(tabs)');

  return (
    <AppScreen>
      <CinematicHero
        source={require('@/assets/images/old-school-gym.png')}
        eyebrow="Evolv"
        title={'Feito para\no longo prazo.'}
        description="Plano, dieta, rotina e evolução em um só lugar."
        meta="Consistência"
      />

      <View style={styles.heading}>
        <Text style={styles.title}>Entrar no Evolv</Text>
        <Text style={styles.description}>A autenticação será conectada ao Supabase na fase de backend.</Text>
      </View>

      <Pressable accessibilityRole="button" onPress={enter} style={({ pressed }) => [styles.providerButton, pressed && styles.pressed]}>
        <View style={styles.googleMark}><Text style={styles.googleText}>G</Text></View>
        <Text style={styles.providerText}>Continuar com Google</Text>
      </Pressable>
      <Pressable accessibilityRole="button" onPress={enter} style={({ pressed }) => [styles.providerButton, pressed && styles.pressed]}>
        <Apple color={palette.text} size={20} fill={palette.text} />
        <Text style={styles.providerText}>Continuar com Apple</Text>
      </Pressable>

      <View style={styles.dividerRow}><View style={styles.line} /><Text style={styles.or}>ou</Text><View style={styles.line} /></View>

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
        <Pressable accessibilityLabel={showPassword ? 'Ocultar senha' : 'Mostrar senha'} onPress={() => setShowPassword((current) => !current)} style={styles.eyeButton}>
          {showPassword ? <EyeOff color={palette.muted} size={18} /> : <Eye color={palette.muted} size={18} />}
        </Pressable>
      </View>

      <Pressable accessibilityRole="button" onPress={enter} style={({ pressed }) => [styles.primaryButton, pressed && styles.pressed]}>
        <Text style={styles.primaryButtonText}>Entrar com e-mail</Text>
      </Pressable>
      <Pressable accessibilityRole="button" onPress={() => router.push('/onboarding')} style={styles.createButton}>
        <Text style={styles.createText}>Criar uma conta</Text>
      </Pressable>
    </AppScreen>
  );
}

const createStyles = (palette: AppThemePalette) => StyleSheet.create({
  heading: { gap: 5 },
  title: { color: palette.text, fontSize: 22, fontWeight: '900' },
  description: { color: palette.muted, fontSize: 12.5, lineHeight: 18 },
  providerButton: { height: 52, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 10, borderRadius: radius.lg, borderWidth: 1, borderColor: palette.border, backgroundColor: palette.surface },
  providerText: { color: palette.text, fontSize: 14, fontWeight: '800' },
  googleMark: { width: 22, height: 22, borderRadius: 11, alignItems: 'center', justifyContent: 'center', backgroundColor: colors.paper },
  googleText: { color: colors.ink, fontSize: 13, fontWeight: '900' },
  dividerRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.md },
  line: { flex: 1, height: StyleSheet.hairlineWidth, backgroundColor: palette.border },
  or: { color: palette.faint, fontSize: 11, textTransform: 'uppercase' },
  inputGroup: { minHeight: 52, flexDirection: 'row', alignItems: 'center', gap: 10, borderRadius: radius.lg, borderWidth: 1, borderColor: palette.border, backgroundColor: palette.elevated, paddingHorizontal: 14 },
  input: { flex: 1, color: palette.text, fontSize: 14, paddingVertical: 13 },
  eyeButton: { width: 34, height: 40, alignItems: 'center', justifyContent: 'center' },
  primaryButton: { height: 52, alignItems: 'center', justifyContent: 'center', borderRadius: radius.lg, backgroundColor: colors.red },
  primaryButtonText: { color: colors.text, fontSize: 14, fontWeight: '900' },
  createButton: { height: 40, alignItems: 'center', justifyContent: 'center' },
  createText: { color: colors.gold, fontSize: 13, fontWeight: '800' },
  pressed: { opacity: 0.65 },
});

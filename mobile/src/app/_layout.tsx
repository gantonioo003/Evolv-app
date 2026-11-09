import { DarkTheme, DefaultTheme, Stack, ThemeProvider } from "expo-router";
import { StatusBar } from "expo-status-bar";
import { GestureHandlerRootView } from "react-native-gesture-handler";
import { SafeAreaProvider } from "react-native-safe-area-context";

import { AppThemeProvider, useAppTheme } from "@/context/theme-context";
import { AuthProvider } from "@/context/auth-context";
import { EvolvDataProvider } from "@/context/evolv-data-context";
import { ImagePreferencesProvider } from "@/context/image-preferences-context";
import { TrainingPreferencesProvider } from "@/context/training-preferences-context";
import { MotionProvider } from "@/context/motion-context";
import { colors } from "@/constants/theme";

export default function RootLayout() {
  return (
    <AuthProvider>
      <EvolvDataProvider>
        <AppThemeProvider>
          <ImagePreferencesProvider>
            <TrainingPreferencesProvider>
              <MotionProvider>
                <ThemedRoot />
              </MotionProvider>
            </TrainingPreferencesProvider>
          </ImagePreferencesProvider>
        </AppThemeProvider>
      </EvolvDataProvider>
    </AuthProvider>
  );
}

function ThemedRoot() {
  const { isDark, palette } = useAppTheme();
  const baseTheme = isDark ? DarkTheme : DefaultTheme;
  const navigationTheme = {
    ...baseTheme,
    colors: {
      ...baseTheme.colors,
      background: palette.page,
      card: palette.surface,
      text: palette.text,
      border: palette.border,
      primary: colors.red,
      notification: colors.red,
    },
  };

  return (
    <ThemeProvider value={navigationTheme}>
      <GestureHandlerRootView
        style={{ flex: 1, backgroundColor: palette.page }}
      >
        <SafeAreaProvider>
          <StatusBar style={isDark ? "light" : "dark"} />
          <Stack
            screenOptions={{
              headerShown: false,
              contentStyle: { backgroundColor: palette.page },
            }}
          >
            <Stack.Screen name="index" />
            <Stack.Screen name="(tabs)" />
            <Stack.Screen name="login" />
            <Stack.Screen name="onboarding" />
            <Stack.Screen name="progress" />
            <Stack.Screen name="settings" />
            <Stack.Screen name="appearance" />
            <Stack.Screen name="image-preferences" />
            <Stack.Screen name="training-preferences" />
            <Stack.Screen name="plans/index" />
            <Stack.Screen name="plans/[planId]" />
            <Stack.Screen name="diet-plans/index" />
            <Stack.Screen name="diet-plans/[planId]" />
            <Stack.Screen name="adjustments/index" />
            <Stack.Screen name="adjustments/[adjustmentId]" />
          </Stack>
        </SafeAreaProvider>
      </GestureHandlerRootView>
    </ThemeProvider>
  );
}

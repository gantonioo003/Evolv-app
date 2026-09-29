import { Stack } from 'expo-router';
import { StatusBar } from 'expo-status-bar';
import { GestureHandlerRootView } from 'react-native-gesture-handler';
import { SafeAreaProvider } from 'react-native-safe-area-context';

import { AppThemeProvider, useAppTheme } from '@/context/theme-context';
import { ImagePreferencesProvider } from '@/context/image-preferences-context';
import { TrainingPreferencesProvider } from '@/context/training-preferences-context';

export default function RootLayout() {
  return (
    <AppThemeProvider>
      <ImagePreferencesProvider>
        <TrainingPreferencesProvider>
          <ThemedRoot />
        </TrainingPreferencesProvider>
      </ImagePreferencesProvider>
    </AppThemeProvider>
  );
}

function ThemedRoot() {
  const { isDark, palette } = useAppTheme();

  return (
    <GestureHandlerRootView style={{ flex: 1, backgroundColor: palette.page }}>
      <SafeAreaProvider>
        <StatusBar style={isDark ? 'light' : 'dark'} />
        <Stack screenOptions={{ headerShown: false, contentStyle: { backgroundColor: palette.page } }}>
          <Stack.Screen name="index" />
          <Stack.Screen name="(tabs)" />
          <Stack.Screen name="login" />
          <Stack.Screen name="onboarding" />
          <Stack.Screen name="progress" />
          <Stack.Screen name="settings" />
          <Stack.Screen name="appearance" />
          <Stack.Screen name="image-preferences" />
          <Stack.Screen name="training-preferences" />
        </Stack>
      </SafeAreaProvider>
    </GestureHandlerRootView>
  );
}

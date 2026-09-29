import AsyncStorage from '@react-native-async-storage/async-storage';
import { createContext, useCallback, useContext, useEffect, useMemo, useState, type PropsWithChildren } from 'react';
import { Platform } from 'react-native';

import { colors } from '@/constants/theme';

export type ResolvedTheme = 'light' | 'dark';
export type ThemePreference = ResolvedTheme;

export type AppThemePalette = {
  page: string;
  elevated: string;
  surface: string;
  raised: string;
  text: string;
  muted: string;
  faint: string;
  border: string;
  iconSurface: string;
  accentSoft: string;
  accentText: string;
  successSoft: string;
  tabBar: string;
};

const STORAGE_KEY = '@evolv/theme-preference';

export const themePalettes: Record<ResolvedTheme, AppThemePalette> = {
  dark: {
    page: colors.background,
    elevated: colors.backgroundElevated,
    surface: colors.surface,
    raised: colors.surfaceRaised,
    text: colors.text,
    muted: colors.textMuted,
    faint: colors.textFaint,
    border: colors.border,
    iconSurface: colors.background,
    accentSoft: colors.redDark,
    accentText: '#E8C9C4',
    successSoft: '#18351F',
    tabBar: '#101216F5',
  },
  light: {
    page: colors.paper,
    elevated: '#E8E0D4',
    surface: colors.paperRaised,
    raised: colors.white,
    text: colors.ink,
    muted: '#5F5B54',
    faint: colors.textFaint,
    border: colors.paperBorder,
    iconSurface: '#E7DED0',
    accentSoft: '#F0D5D1',
    accentText: colors.redDark,
    successSoft: '#E4EEE5',
    tabBar: '#F8F4ECF5',
  },
};

type ThemeContextValue = {
  preference: ThemePreference;
  resolvedTheme: ResolvedTheme;
  isDark: boolean;
  palette: AppThemePalette;
  setPreference: (preference: ThemePreference) => void;
};

const ThemeContext = createContext<ThemeContextValue | null>(null);

function isThemePreference(value: string | null): value is ThemePreference {
  return value === 'light' || value === 'dark';
}

async function readPreference() {
  if (Platform.OS === 'web' && typeof globalThis.localStorage !== 'undefined') {
    return globalThis.localStorage.getItem(STORAGE_KEY);
  }

  return AsyncStorage.getItem(STORAGE_KEY);
}

async function savePreference(preference: ThemePreference) {
  if (Platform.OS === 'web' && typeof globalThis.localStorage !== 'undefined') {
    globalThis.localStorage.setItem(STORAGE_KEY, preference);
    return;
  }

  await AsyncStorage.setItem(STORAGE_KEY, preference);
}

export function AppThemeProvider({ children }: PropsWithChildren) {
  const [preference, setPreferenceState] = useState<ThemePreference>('dark');

  useEffect(() => {
    let active = true;

    void readPreference().then((savedPreference) => {
      if (!active) return;

      if (isThemePreference(savedPreference)) setPreferenceState(savedPreference);
    });

    return () => {
      active = false;
    };
  }, []);

  const setPreference = useCallback((nextPreference: ThemePreference) => {
    setPreferenceState(nextPreference);
    void savePreference(nextPreference);
  }, []);

  const resolvedTheme = preference;

  const value = useMemo<ThemeContextValue>(() => ({
    preference,
    resolvedTheme,
    isDark: resolvedTheme === 'dark',
    palette: themePalettes[resolvedTheme],
    setPreference,
  }), [preference, resolvedTheme, setPreference]);

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}

export function useAppTheme() {
  const context = useContext(ThemeContext);
  if (!context) throw new Error('useAppTheme must be used inside AppThemeProvider.');
  return context;
}

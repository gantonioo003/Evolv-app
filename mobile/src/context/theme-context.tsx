import AsyncStorage from "@react-native-async-storage/async-storage";
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type PropsWithChildren,
} from "react";
import { Platform } from "react-native";

export type ResolvedTheme = "light" | "dark";
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
  primary: string;
  onPrimary: string;
  artworkSurface: string;
  sage: string;
  atmosphere: string;
  atmosphereWarm: string;
  macroCarbs: string;
  macroProtein: string;
  macroFat: string;
};

const STORAGE_KEY = "@evolv/theme-preference";

export const themePalettes: Record<ResolvedTheme, AppThemePalette> = {
  dark: {
    page: "#0D1118",
    elevated: "#182230",
    surface: "#151D29",
    raised: "#1D293A",
    text: "#F3F6FC",
    muted: "#BDC9DD",
    faint: "#A4B4CF",
    border: "#33445E",
    iconSurface: "#1C2C47",
    accentSoft: "#1B3159",
    accentText: "#9DBEFF",
    successSoft: "#203758",
    tabBar: "#111925",
    primary: "#2756D7",
    onPrimary: "#FFFFFF",
    artworkSurface: "#0E1522",
    sage: "#1F304E",
    atmosphere: "#111E35",
    atmosphereWarm: "#151C27",
    macroCarbs: "#83B3FF",
    macroProtein: "#B6AAF4",
    macroFat: "#5EC8E8",
  },
  light: {
    page: "#F2F4F8",
    elevated: "#E5EBF6",
    surface: "#FFFFFF",
    raised: "#FFFFFF",
    text: "#111A2A",
    muted: "#44546D",
    faint: "#506079",
    border: "#BCC9DF",
    iconSurface: "#E4EBFA",
    accentSoft: "#DCE7FF",
    accentText: "#1745A4",
    successSoft: "#DEE9FC",
    tabBar: "#F5F8FE",
    primary: "#2756D7",
    onPrimary: "#FFFFFF",
    artworkSurface: "#E6EDF7",
    sage: "#E2EBFC",
    atmosphere: "#E5ECF9",
    atmosphereWarm: "#E5E9F0",
    macroCarbs: "#235AC7",
    macroProtein: "#634DA8",
    macroFat: "#106C8F",
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
  return value === "light" || value === "dark";
}

async function readPreference() {
  if (Platform.OS === "web" && typeof globalThis.localStorage !== "undefined") {
    return globalThis.localStorage.getItem(STORAGE_KEY);
  }

  return AsyncStorage.getItem(STORAGE_KEY);
}

async function savePreference(preference: ThemePreference) {
  if (Platform.OS === "web" && typeof globalThis.localStorage !== "undefined") {
    globalThis.localStorage.setItem(STORAGE_KEY, preference);
    return;
  }

  await AsyncStorage.setItem(STORAGE_KEY, preference);
}

export function AppThemeProvider({ children }: PropsWithChildren) {
  const [preference, setPreferenceState] = useState<ThemePreference>("dark");

  useEffect(() => {
    let active = true;

    void readPreference().then((savedPreference) => {
      if (!active) return;

      if (isThemePreference(savedPreference))
        setPreferenceState(savedPreference);
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

  const value = useMemo<ThemeContextValue>(
    () => ({
      preference,
      resolvedTheme,
      isDark: resolvedTheme === "dark",
      palette: themePalettes[resolvedTheme],
      setPreference,
    }),
    [preference, resolvedTheme, setPreference],
  );

  return (
    <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>
  );
}

export function useAppTheme() {
  const context = useContext(ThemeContext);
  if (!context)
    throw new Error("useAppTheme must be used inside AppThemeProvider.");
  return context;
}

import { Platform } from "react-native";

export const colors = {
  background: "#101112",
  backgroundElevated: "#18191B",
  surface: "#18191B",
  surfaceRaised: "#242628",
  paper: "#FFFFFF",
  paperRaised: "#F8F9FA",
  ink: "#1B1C1E",
  text: "#F5F5F5",
  textMuted: "#A0A1A3",
  textFaint: "#979A9E",
  red: "#B43228",
  redDark: "#7D211D",
  gold: "#D5A835",
  green: "#5D8C65",
  border: "#393B3D",
  paperBorder: "#D5D7DA",
  white: "#FFFFFF",
  black: "#050608",
} as const;

export const spacing = {
  xs: 4,
  sm: 8,
  md: 12,
  lg: 16,
  xl: 20,
  xxl: 28,
  xxxl: 36,
} as const;

export const radius = {
  sm: 4,
  md: 6,
  lg: 8,
} as const;

export const typography = {
  display: Platform.select({
    ios: "System",
    android: "sans-serif",
    web: 'Inter, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
    default: "system-ui",
  }),
  body: Platform.select({
    ios: "System",
    android: "sans-serif",
    web: 'Inter, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
    default: "system-ui",
  }),
} as const;

export const shadows = {
  card:
    Platform.select({
      web: { boxShadow: "0 3px 10px rgba(5, 6, 8, 0.12)" },
      android: { elevation: 3 },
      default: {
        shadowColor: colors.black,
        shadowOffset: { width: 0, height: 3 },
        shadowOpacity: 0.12,
        shadowRadius: 10,
      },
    }) ?? {},
} as const;

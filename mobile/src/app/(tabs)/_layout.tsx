import { Redirect, Tabs } from "expo-router";
import {
  CalendarDays,
  Dumbbell,
  MessageCircle,
  UserRound,
  Utensils,
} from "lucide-react-native";
import { useEffect, useState, type ComponentProps } from "react";
import {
  ActivityIndicator,
  Animated,
  Easing,
  Platform,
  Pressable,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { colors, shadows, typography } from "@/constants/theme";
import { useAuth } from "@/context/auth-context";
import { useEvolvData } from "@/context/evolv-data-context";
import { useAppTheme, type AppThemePalette } from "@/context/theme-context";

export default function TabsLayout() {
  const { palette } = useAppTheme();
  const { isLoading, session } = useAuth();
  const { hasLoaded, isLoading: isDataLoading, profile } = useEvolvData();

  if (isLoading) return null;
  if (!session) return <Redirect href="/login" />;
  if (!hasLoaded || isDataLoading) {
    return (
      <View style={[styles.loadingScreen, { backgroundColor: palette.page }]}>
        <Text style={[styles.loadingBrand, { color: palette.text }]}>
          EVOLV
        </Text>
        <ActivityIndicator color={colors.gold} />
      </View>
    );
  }
  if (
    profile &&
    (profile.onboarding_status === "not_started" ||
      profile.onboarding_status === "in_progress")
  ) {
    return <Redirect href="/onboarding" />;
  }

  return (
    <Tabs
      tabBar={(props) => <AppTabBar {...props} />}
      screenOptions={{
        animation: "shift",
        headerShown: false,
        sceneStyle: { backgroundColor: palette.page },
      }}
    >
      <Tabs.Screen name="index" options={{ title: "Hoje" }} />
      <Tabs.Screen name="workout" options={{ title: "Treino" }} />
      <Tabs.Screen name="coach" options={{ title: "Coach" }} />
      <Tabs.Screen name="diet" options={{ title: "Dieta" }} />
      <Tabs.Screen name="account" options={{ title: "Conta" }} />
    </Tabs>
  );
}

const tabIcons = {
  index: CalendarDays,
  workout: Dumbbell,
  coach: MessageCircle,
  diet: Utensils,
  account: UserRound,
} as const;

type AppTabBarProps = Parameters<
  NonNullable<ComponentProps<typeof Tabs>["tabBar"]>
>[0];

function AppTabBar({ state, descriptors, navigation }: AppTabBarProps) {
  const { palette } = useAppTheme();
  const insets = useSafeAreaInsets();

  return (
    <View
      pointerEvents="box-none"
      style={[styles.tabBarPosition, { bottom: Math.max(insets.bottom, 8) }]}
    >
      <View
        style={[
          styles.tabBar,
          { backgroundColor: palette.tabBar, borderColor: palette.border },
        ]}
      >
        {state.routes.map((route, index) => {
          const focused = state.index === index;
          const Icon =
            tabIcons[route.name as keyof typeof tabIcons] ?? CalendarDays;
          const label = descriptors[route.key].options.title ?? route.name;

          const onPress = () => {
            const event = navigation.emit({
              type: "tabPress",
              target: route.key,
              canPreventDefault: true,
            });
            if (!focused && !event.defaultPrevented)
              navigation.navigate(route.name, route.params);
          };

          return (
            <AppTabItem
              focused={focused}
              icon={Icon}
              key={route.key}
              label={String(label)}
              onPress={onPress}
              palette={palette}
            />
          );
        })}
      </View>
    </View>
  );
}

function AppTabItem({
  focused,
  icon: Icon,
  label,
  onPress,
  palette,
}: {
  focused: boolean;
  icon: typeof CalendarDays;
  label: string;
  onPress: () => void;
  palette: AppThemePalette;
}) {
  const [focusProgress] = useState(() => new Animated.Value(focused ? 1 : 0));
  const color = focused ? palette.text : palette.faint;

  useEffect(() => {
    Animated.timing(focusProgress, {
      toValue: focused ? 1 : 0,
      duration: 180,
      easing: Easing.out(Easing.cubic),
      useNativeDriver: Platform.OS !== "web",
    }).start();
  }, [focusProgress, focused]);

  const scale = focusProgress.interpolate({
    inputRange: [0, 1],
    outputRange: [1, 1.05],
  });
  const translateY = focusProgress.interpolate({
    inputRange: [0, 1],
    outputRange: [0, -2],
  });

  return (
    <Pressable
      accessibilityRole="tab"
      accessibilityState={focused ? { selected: true } : {}}
      hitSlop={6}
      onPress={onPress}
      style={({ pressed }) => [
        styles.tabItem,
        pressed && styles.tabItemPressed,
      ]}
    >
      <Animated.View
        style={[
          styles.tabItemContent,
          {
            backgroundColor: focused ? palette.elevated : "transparent",
            borderColor: focused ? palette.border : "transparent",
            borderWidth: focused ? StyleSheet.hairlineWidth : 0,
            opacity: focused ? 1 : 0.72,
            transform: [{ translateY }, { scale }],
          },
        ]}
      >
        <Icon color={color} size={23} strokeWidth={focused ? 2.15 : 1.8} />
        <Text style={[styles.tabLabel, { color }]}>{label}</Text>
      </Animated.View>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  loadingScreen: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
    gap: 14,
  },
  loadingBrand: {
    fontFamily: typography.display,
    fontSize: 25,
    fontWeight: "900",
  },
  tabBarPosition: { position: "absolute", left: 14, right: 14 },
  tabBar: {
    width: "100%",
    maxWidth: 740,
    height: 66,
    alignSelf: "center",
    flexDirection: "row",
    borderWidth: 1,
    borderRadius: 30,
    paddingHorizontal: 6,
    paddingVertical: 4,
    ...shadows.card,
  },
  tabItem: {
    flex: 1,
    minWidth: 58,
    alignItems: "center",
    justifyContent: "center",
  },
  tabItemContent: {
    minWidth: 60,
    alignItems: "center",
    justifyContent: "center",
    gap: 3,
    borderRadius: 22,
    paddingHorizontal: 10,
    paddingVertical: 7,
  },
  tabItemPressed: { opacity: 0.58 },
  tabLabel: { fontFamily: typography.body, fontSize: 10.5, fontWeight: "700" },
});

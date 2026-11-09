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
  Platform,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { TouchFeedback as Pressable } from "@/components/touch-feedback";
import { useReducedMotion } from "@/context/motion-context";

import { colors, shadows, typography } from "@/constants/theme";
import { useAuth } from "@/context/auth-context";
import { useEvolvData } from "@/context/evolv-data-context";
import { useAppTheme, type AppThemePalette } from "@/context/theme-context";

export default function TabsLayout() {
  const reducedMotion = useReducedMotion();
  const { palette } = useAppTheme();
  const { isLoading, session } = useAuth();
  const { hasLoaded, profile } = useEvolvData();

  if (isLoading) return null;
  if (!session) return <Redirect href="/login" />;
  if (!hasLoaded) {
    return (
      <View style={[styles.loadingScreen, { backgroundColor: palette.page }]}>
        <Text style={[styles.loadingBrand, { color: palette.text }]}>
          Evolv.
        </Text>
        <ActivityIndicator color={colors.red} />
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
        animation: reducedMotion ? "none" : "shift",
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
  const reducedMotion = useReducedMotion();
  const insets = useSafeAreaInsets();
  const [width, setWidth] = useState(0);
  const [selection] = useState(() => new Animated.Value(state.index));
  const itemWidth = Math.max(0, width - 12) / state.routes.length;

  useEffect(() => {
    if (reducedMotion) {
      selection.setValue(state.index);
      return;
    }
    const animation = Animated.spring(selection, {
      toValue: state.index,
      damping: 24,
      stiffness: 260,
      mass: 0.8,
      useNativeDriver: Platform.OS !== "web",
    });
    animation.start();
    return () => animation.stop();
  }, [reducedMotion, selection, state.index]);

  return (
    <View
      pointerEvents="box-none"
      style={[styles.tabBarPosition, { bottom: Math.max(insets.bottom, 8) }]}
    >
      <View
        accessibilityRole="tablist"
        onLayout={(event) => setWidth(event.nativeEvent.layout.width)}
        style={[
          styles.tabBar,
          { backgroundColor: palette.tabBar, borderColor: palette.border },
        ]}
      >
        <Animated.View
          pointerEvents="none"
          testID="tab-selection"
          style={[
            styles.tabSelection,
            {
              width: itemWidth,
              backgroundColor: palette.elevated,
              borderColor: palette.border,
              opacity: width ? 1 : 0,
              transform: [
                { translateX: Animated.multiply(selection, itemWidth) },
              ],
            },
          ]}
        />
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
          const onLongPress = () =>
            navigation.emit({ type: "tabLongPress", target: route.key });

          return (
            <AppTabItem
              focused={focused}
              icon={Icon}
              key={route.key}
              label={String(label)}
              onPress={onPress}
              onLongPress={onLongPress}
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
  onLongPress,
  palette,
}: {
  focused: boolean;
  icon: typeof CalendarDays;
  label: string;
  onPress: () => void;
  onLongPress: () => void;
  palette: AppThemePalette;
}) {
  const [focusProgress] = useState(() => new Animated.Value(focused ? 1 : 0));
  const reducedMotion = useReducedMotion();
  const color = focused ? palette.text : palette.faint;

  useEffect(() => {
    if (reducedMotion) {
      focusProgress.setValue(focused ? 1 : 0);
      return;
    }
    const animation = Animated.spring(focusProgress, {
      toValue: focused ? 1 : 0,
      damping: 22,
      stiffness: 300,
      mass: 0.7,
      useNativeDriver: Platform.OS !== "web",
    });
    animation.start();
    return () => animation.stop();
  }, [focusProgress, focused, reducedMotion]);

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
      accessibilityLabel={label}
      aria-selected={focused}
      accessibilityState={focused ? { selected: true } : {}}
      hitSlop={6}
      onPress={onPress}
      onLongPress={onLongPress}
      pressScale={0.94}
      style={({ pressed }) => [
        styles.tabItem,
        pressed && styles.tabItemPressed,
      ]}
    >
      <Animated.View
        style={[
          styles.tabItemContent,
          {
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
    fontWeight: "600",
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
    minWidth: 0,
    alignItems: "center",
    justifyContent: "center",
  },
  tabItemContent: {
    width: "100%",
    height: 56,
    alignItems: "center",
    justifyContent: "center",
    gap: 3,
    borderRadius: 22,
    paddingHorizontal: 2,
    paddingVertical: 7,
  },
  tabSelection: {
    position: "absolute",
    left: 6,
    top: 4,
    bottom: 4,
    borderRadius: 24,
    borderWidth: StyleSheet.hairlineWidth,
  },
  tabItemPressed: { opacity: 0.8 },
  tabLabel: { fontFamily: typography.body, fontSize: 11, fontWeight: "500" },
});

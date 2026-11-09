import {
  cloneElement,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ComponentType,
  type PropsWithChildren,
  type ReactElement,
  type ReactNode,
} from "react";
import { Asset } from "expo-asset";
import {
  Animated,
  Easing,
  Image,
  Platform,
  type ScrollViewInstance,
  StyleSheet,
  Text,
  View,
  type ImageStyle,
  type ImageSourcePropType,
  type StyleProp,
  type ViewStyle,
} from "react-native";
import { useFocusEffect, useScrollToTop } from "expo-router";
import {
  SafeAreaView,
  useSafeAreaInsets,
} from "react-native-safe-area-context";

import { TouchFeedback as Pressable } from "@/components/touch-feedback";
import { useReducedMotion } from "@/context/motion-context";
import {
  COMPACT_HEADER_HEIGHT,
  headerCollapseRange,
  SCREEN_SECTION_GAP,
  SCREEN_TOP_PADDING,
  shouldShowCompactHeader,
} from "@/lib/screen-motion";

import {
  colors,
  radius,
  shadows,
  spacing,
  typography,
} from "@/constants/theme";
import {
  themePalettes,
  useAppTheme,
  type ResolvedTheme,
} from "@/context/theme-context";

type IconComponent = ComponentType<{
  color?: string;
  size?: number;
  strokeWidth?: number;
}>;
type ThemeTone = "dark" | "paper";

function useTonePalette(tone?: ThemeTone) {
  const theme = useAppTheme();
  const forcedTheme: ResolvedTheme | undefined =
    tone === "paper" ? "light" : tone === "dark" ? "dark" : undefined;
  return forcedTheme ? themePalettes[forcedTheme] : theme.palette;
}

export function CoverImage({
  source,
  style,
}: {
  source: ImageSourcePropType;
  style: StyleProp<ImageStyle | ViewStyle>;
}) {
  if (Platform.OS === "web") {
    const uri = Asset.fromModule(
      source as
        number | string | { uri: string; width: number; height: number },
    ).uri;
    const webBackground = {
      backgroundImage: `url("${uri}")`,
      backgroundPosition: "center",
      backgroundRepeat: "no-repeat",
      backgroundSize: "cover",
    } as ViewStyle;

    return <View style={[style, webBackground]} />;
  }

  return (
    <Image
      source={source}
      resizeMode="cover"
      style={style as StyleProp<ImageStyle>}
    />
  );
}

type AppScreenProps = PropsWithChildren<{
  header?: ReactElement<PageHeaderProps>;
  tone?: ThemeTone;
  contentStyle?: ViewStyle;
  scroll?: boolean;
  footer?: ReactNode;
  scrollToEndKey?: string;
}>;

export function AppScreen({
  children,
  header,
  tone,
  contentStyle,
  scroll = true,
  footer,
  scrollToEndKey,
}: AppScreenProps) {
  const palette = useTonePalette(tone);
  const reducedMotion = useReducedMotion();
  const insets = useSafeAreaInsets();
  const scrollRef = useRef<ScrollViewInstance>(null);
  useEffect(()=>{
    if(!scrollToEndKey)return;
    const frame=requestAnimationFrame(()=>scrollRef.current?.scrollToEnd({animated:false}));
    return()=>cancelAnimationFrame(frame);
  },[scrollToEndKey]);
  const [scrollY] = useState(() => new Animated.Value(0));
  const [headerHeight, setHeaderHeight] = useState(72);
  const [compactVisible, setCompactVisible] = useState(false);
  const [entrance] = useState(() => new Animated.Value(0));
  const collapseRange = headerCollapseRange(headerHeight);
  const collapseProgress = scrollY.interpolate({
    inputRange: [0, collapseRange.end],
    outputRange: [0, 1],
    extrapolate: "clamp",
  });
  const compactOpacity = scrollY.interpolate({
    inputRange: [collapseRange.start, collapseRange.end],
    outputRange: [0, 1],
    extrapolate: "clamp",
  });
  const scrollToTop = useMemo(
    () => ({
      current: {
        scrollToTop: () =>
          scrollRef.current?.scrollTo({ y: 0, animated: !reducedMotion }),
      },
    }),
    [reducedMotion],
  );
  useScrollToTop(scrollToTop);

  useFocusEffect(
    useCallback(() => {
      if (reducedMotion) {
        entrance.setValue(1);
        return;
      }
      entrance.setValue(0);
      const animation = Animated.timing(entrance, {
        toValue: 1,
        duration: 200,
        easing: Easing.out(Easing.cubic),
        useNativeDriver: Platform.OS !== "web",
      });
      animation.start();
      return () => animation.stop();
    }, [entrance, reducedMotion]),
  );

  const content = (
    <Animated.View
      style={[
        styles.content,
        { paddingBottom: 120 + insets.bottom },
        contentStyle,
        {
          opacity: entrance,
          transform: [
            {
              translateY: entrance.interpolate({
                inputRange: [0, 1],
                outputRange: [8, 0],
              }),
            },
          ],
        },
      ]}
    >
      {header ? (
        <View
          aria-hidden={compactVisible}
          accessibilityElementsHidden={compactVisible}
          importantForAccessibility={
            compactVisible ? "no-hide-descendants" : "auto"
          }
          onLayout={(event) => setHeaderHeight(event.nativeEvent.layout.height)}
          pointerEvents={compactVisible ? "none" : "auto"}
        >
          {cloneElement(header, {
            active: !compactVisible,
            tone: header.props.tone ?? tone,
            collapseProgress: reducedMotion ? undefined : collapseProgress,
          })}
        </View>
      ) : null}
      {children}
    </Animated.View>
  );

  return (
    <SafeAreaView
      edges={["top", "left", "right"]}
      style={[styles.safeArea, { backgroundColor: palette.page }]}
    >
      {scroll ? (
        <Animated.ScrollView
          ref={scrollRef}
          testID={`page-scroll-${header?.props.title ?? "content"}`}
          style={[
            styles.scroller,
            Platform.OS === "web" &&
              ({
                scrollbarWidth: "thin",
                scrollbarColor: `${palette.faint} transparent`,
              } as ViewStyle),
          ]}
          contentContainerStyle={styles.scrollContent}
          contentInsetAdjustmentBehavior="automatic"
          decelerationRate="normal"
          directionalLockEnabled
          keyboardDismissMode="interactive"
          keyboardShouldPersistTaps="handled"
          showsVerticalScrollIndicator
          indicatorStyle={
            palette.page === themePalettes.light.page ? "black" : "white"
          }
          scrollIndicatorInsets={{
            top: header ? COMPACT_HEADER_HEIGHT : 0,
            bottom: 90 + insets.bottom,
          }}
          scrollEventThrottle={16}
          onScroll={Animated.event(
            [{ nativeEvent: { contentOffset: { y: scrollY } } }],
            {
              useNativeDriver: Platform.OS !== "web",
              listener: (event: {
                nativeEvent: { contentOffset: { y: number } };
              }) => {
                const visible =
                  Boolean(header) &&
                  shouldShowCompactHeader(
                    event.nativeEvent.contentOffset.y,
                    headerHeight,
                  );
                if (visible !== compactVisible) {
                  setCompactVisible(visible);
                }
              },
            },
          )}
        >
          {content}
        </Animated.ScrollView>
      ) : (
        content
      )}
      {footer}
      {header && scroll ? (
        <Animated.View
          aria-hidden={!compactVisible}
          accessibilityElementsHidden={!compactVisible}
          importantForAccessibility={
            compactVisible ? "auto" : "no-hide-descendants"
          }
          pointerEvents={compactVisible ? "auto" : "none"}
          testID={`compact-page-header-${header.props.title}`}
          style={[
            styles.compactHeader,
            {
              top: insets.top,
              backgroundColor: palette.page,
              borderBottomColor: palette.border,
              opacity: reducedMotion ? Number(compactVisible) : compactOpacity,
            },
          ]}
        >
          <View style={styles.compactHeaderContent}>
            {cloneElement(header, {
              compact: true,
              active: compactVisible,
              tone: header.props.tone ?? tone,
            })}
          </View>
        </Animated.View>
      ) : null}
    </SafeAreaView>
  );
}

type PageHeaderProps = {
  active?: boolean;
  compact?: boolean;
  collapseProgress?: Animated.AnimatedInterpolation<number>;
  brand?: string;
  eyebrow: string;
  title: string;
  tone?: ThemeTone;
  actionIcon?: IconComponent;
  actionLabel?: string;
  onAction?: () => void;
};

export function PageHeader({
  active = true,
  compact = false,
  collapseProgress,
  brand,
  eyebrow,
  title,
  tone,
  actionIcon: ActionIcon,
  actionLabel,
  onAction,
}: PageHeaderProps) {
  const palette = useTonePalette(tone);
  return (
    <View style={[styles.pageHeader, compact && styles.pageHeaderCompact]}>
      <View style={styles.pageHeaderText}>
        {brand && !compact ? (
          <Text style={[styles.brand, { color: palette.text }]}>
            {brand.toLowerCase() === "evolv" ? (
              <>
                Evolv<Text style={{ color: colors.red }}>.</Text>
              </>
            ) : (
              brand
            )}
          </Text>
        ) : null}
        {!compact ? (
          <Text style={[styles.eyebrow, { color: palette.muted }]}>
            {eyebrow}
          </Text>
        ) : null}
        <Animated.Text
          accessibilityRole="header"
          numberOfLines={compact ? 1 : undefined}
          style={[
            styles.pageTitle,
            { color: palette.text },
            compact && styles.pageTitleCompact,
            collapseProgress && {
              transformOrigin: "left center",
              transform: [
                {
                  scale: collapseProgress.interpolate({
                    inputRange: [0, 1],
                    outputRange: [1, 0.85],
                  }),
                },
              ],
            },
          ]}
        >
          {title}
        </Animated.Text>
      </View>
      {ActionIcon ? (
        <Pressable
          disabled={!active}
          accessibilityLabel={actionLabel}
          accessibilityRole="button"
          onPress={onAction}
          style={({ pressed }) => [
            styles.iconButton,
            { backgroundColor: palette.surface, borderColor: palette.border },
            pressed && styles.pressed,
          ]}
        >
          <ActionIcon color={palette.text} size={21} strokeWidth={1.8} />
        </Pressable>
      ) : null}
    </View>
  );
}

export function CinematicHero({
  source,
  eyebrow,
  title,
  description,
  height = 240,
  overlayOpacity = 0.38,
}: {
  source: ImageSourcePropType;
  eyebrow: string;
  title: string;
  description: string;
  height?: number;
  overlayOpacity?: number;
}) {
  const compact = height <= 260;

  return (
    <View style={[styles.cinematicHero, { height }]}>
      <CoverImage source={source} style={styles.cinematicImage} />
      <View
        style={[
          styles.cinematicWash,
          { backgroundColor: `rgba(5, 6, 8, ${overlayOpacity})` },
        ]}
      />
      <View style={styles.cinematicContent}>
        <Text style={styles.cinematicEyebrow}>{eyebrow}</Text>
        <View style={styles.cinematicCopy}>
          <View style={styles.cinematicRule} />
          <Text
            adjustsFontSizeToFit
            minimumFontScale={0.76}
            numberOfLines={compact ? 3 : 4}
            style={[
              styles.cinematicTitle,
              compact && styles.cinematicTitleCompact,
            ]}
          >
            {title}
          </Text>
          <Text
            style={[
              styles.cinematicDescription,
              compact && styles.cinematicDescriptionCompact,
            ]}
          >
            {description}
          </Text>
        </View>
      </View>
    </View>
  );
}

export function SectionTitle({
  title,
  meta,
  tone,
}: {
  title: string;
  meta?: string;
  tone?: ThemeTone;
}) {
  const palette = useTonePalette(tone);
  return (
    <View style={styles.sectionHeader}>
      <Text style={[styles.sectionTitle, { color: palette.text }]}>
        {title}
      </Text>
      {meta ? (
        <Text style={[styles.sectionMeta, { color: palette.muted }]}>
          {meta}
        </Text>
      ) : null}
    </View>
  );
}

export function Surface({
  children,
  tone,
  style,
}: PropsWithChildren<{ tone?: ThemeTone | "accent"; style?: ViewStyle }>) {
  const palette = useTonePalette(tone === "accent" ? undefined : tone);
  return (
    <View
      style={[
        styles.surface,
        tone === "accent"
          ? styles.surfaceAccent
          : { backgroundColor: palette.surface, borderColor: palette.border },
        style,
      ]}
    >
      {children}
    </View>
  );
}

export function PosterHero({
  eyebrow,
  title,
  description,
  meta,
  light = false,
}: {
  eyebrow: string;
  title: string;
  description: string;
  meta: string;
  light?: boolean;
}) {
  const { palette } = useAppTheme();
  return (
    <View
      style={[
        styles.poster,
        {
          backgroundColor: light
            ? themePalettes.light.surface
            : palette.surface,
          borderColor: light ? themePalettes.light.border : palette.border,
        },
      ]}
    >
      <View style={styles.posterAccent} />
      <View style={styles.posterBars}>
        <View style={[styles.posterBar, styles.posterBarTall]} />
        <View style={styles.posterBar} />
        <View style={[styles.posterBar, styles.posterBarShort]} />
      </View>
      <Text style={styles.posterEyebrow}>{eyebrow}</Text>
      <Text
        style={[
          styles.posterTitle,
          { color: light ? themePalettes.light.text : palette.text },
        ]}
      >
        {title}
      </Text>
      <Text
        style={[
          styles.posterDescription,
          { color: light ? themePalettes.light.muted : palette.muted },
        ]}
      >
        {description}
      </Text>
      <Text style={styles.posterMeta}>{meta}</Text>
    </View>
  );
}

export function Metric({
  value,
  label,
  tone,
}: {
  value: string;
  label: string;
  tone?: ThemeTone;
}) {
  const palette = useTonePalette(tone);
  return (
    <View
      style={[
        styles.metric,
        { backgroundColor: palette.elevated, borderColor: palette.border },
      ]}
    >
      <Text style={[styles.metricValue, { color: palette.text }]}>{value}</Text>
      <Text style={[styles.metricLabel, { color: palette.muted }]}>
        {label}
      </Text>
    </View>
  );
}

export function InfoRow({
  title,
  description,
  leading,
  trailing,
  tone,
  onPress,
}: {
  title: string;
  description: string;
  leading?: ReactNode;
  trailing?: ReactNode;
  tone?: ThemeTone;
  onPress?: () => void;
}) {
  const palette = useTonePalette(tone);
  const body = (
    <>
      {leading}
      <View style={styles.infoBody}>
        <Text style={[styles.infoTitle, { color: palette.text }]}>{title}</Text>
        <Text style={[styles.infoDescription, { color: palette.muted }]}>
          {description}
        </Text>
      </View>
      {trailing}
    </>
  );

  if (onPress) {
    return (
      <Pressable
        accessibilityRole="button"
        onPress={onPress}
        style={({ pressed }) => [styles.infoRow, pressed && styles.pressed]}
      >
        {body}
      </Pressable>
    );
  }

  return <View style={styles.infoRow}>{body}</View>;
}

export function Divider({ paper = false }: { paper?: boolean }) {
  const { palette } = useAppTheme();
  return (
    <View
      style={[
        styles.divider,
        {
          backgroundColor: paper ? themePalettes.light.border : palette.border,
        },
      ]}
    />
  );
}

export function Tag({
  children,
  color,
}: PropsWithChildren<{ color?: string }>) {
  const { palette, isDark } = useAppTheme();
  const resolvedColor =
    !isDark && color === colors.green
      ? "#376443"
      : !isDark && color === colors.gold
        ? "#87630D"
        : (color ?? palette.muted);
  return (
    <View style={[styles.tag, { borderColor: resolvedColor }]}>
      <Text style={[styles.tagText, { color: resolvedColor }]}>{children}</Text>
    </View>
  );
}

export function ProgressBar({
  value,
  color = colors.red,
  trackColor,
}: {
  value: number;
  color?: string;
  trackColor?: string;
}) {
  const { palette } = useAppTheme();
  const normalized = Math.max(0, Math.min(1, value));
  return (
    <View
      style={[
        styles.progressTrack,
        { backgroundColor: trackColor ?? palette.border },
      ]}
    >
      <View
        style={[
          styles.progressFill,
          { backgroundColor: color, width: `${normalized * 100}%` },
        ]}
      />
    </View>
  );
}

export function LabelIcon({
  icon: Icon,
  tone,
}: {
  icon: IconComponent;
  tone?: ThemeTone;
}) {
  const palette = useTonePalette(tone);
  return (
    <View style={[styles.labelIcon, { backgroundColor: palette.iconSurface }]}>
      <Icon color={palette.accentText} size={18} strokeWidth={1.8} />
    </View>
  );
}

const styles = StyleSheet.create({
  safeArea: { flex: 1 },
  scroller: { flex: 1 },
  scrollContent: { flexGrow: 1 },
  compactHeader: {
    position: "absolute",
    left: 0,
    right: 0,
    zIndex: 10,
    height: COMPACT_HEADER_HEIGHT,
    borderBottomWidth: StyleSheet.hairlineWidth,
  },
  compactHeaderContent: {
    width: "100%",
    maxWidth: 760,
    alignSelf: "center",
    paddingHorizontal: spacing.lg,
  },
  content: {
    flex: 1,
    width: "100%",
    maxWidth: 760,
    alignSelf: "center",
    paddingHorizontal: spacing.lg,
    paddingTop: SCREEN_TOP_PADDING,
    paddingBottom: 120,
    gap: SCREEN_SECTION_GAP,
  },
  pageHeader: {
    minHeight: 72,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
  },
  pageHeaderText: { flex: 1, paddingRight: spacing.md },
  pageHeaderCompact: { minHeight: COMPACT_HEADER_HEIGHT },
  pageTitleCompact: { marginTop: 0, fontSize: 18, lineHeight: 24 },
  brand: {
    marginBottom: 12,
    color: colors.red,
    fontFamily: typography.display,
    fontSize: 24,
    fontWeight: "600",
    letterSpacing: 0,
  },
  eyebrow: {
    color: colors.textMuted,
    fontFamily: typography.body,
    fontSize: 12,
    fontWeight: "500",
  },
  pageTitle: {
    marginTop: 5,
    fontFamily: typography.display,
    fontSize: 28,
    lineHeight: 34,
    fontWeight: "600",
    letterSpacing: 0,
  },
  iconButton: {
    width: 46,
    height: 46,
    borderRadius: 23,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: colors.border,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: colors.surface,
  },
  iconButtonPaper: {
    backgroundColor: colors.paperRaised,
    borderColor: colors.paperBorder,
  },
  pressed: { opacity: 0.68, transform: [{ scale: 0.98 }] },
  cinematicHero: {
    height: 370,
    overflow: "hidden",
    borderRadius: 14,
    backgroundColor: colors.black,
    ...shadows.card,
  },
  cinematicImage: {
    position: "absolute",
    inset: 0,
    width: "100%",
    height: "100%",
    borderRadius: 14,
  },
  cinematicWash: { position: "absolute", inset: 0, zIndex: 1 },
  cinematicContent: {
    zIndex: 2,
    flex: 1,
    justifyContent: "space-between",
    padding: spacing.xl,
  },
  cinematicEyebrow: {
    color: "#E5E5E5",
    fontFamily: typography.body,
    fontSize: 12,
    fontWeight: "500",
  },
  cinematicCopy: { maxWidth: 430 },
  cinematicRule: {
    width: 38,
    height: 4,
    marginBottom: spacing.md,
    backgroundColor: colors.red,
  },
  cinematicTitle: {
    color: colors.text,
    fontFamily: typography.display,
    fontSize: 34,
    lineHeight: 40,
    fontWeight: "600",
    letterSpacing: 0,
  },
  cinematicTitleCompact: { fontSize: 28, lineHeight: 34 },
  cinematicDescription: {
    maxWidth: 340,
    marginTop: spacing.md,
    color: "#E5E5E5",
    fontFamily: typography.body,
    fontSize: 14,
    lineHeight: 21,
  },
  cinematicDescriptionCompact: {
    maxWidth: 300,
    marginTop: spacing.sm,
    fontSize: 13,
    lineHeight: 19,
  },
  sectionHeader: {
    minHeight: 30,
    marginTop: spacing.md,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    gap: spacing.md,
  },
  sectionTitle: {
    flex: 1,
    color: colors.text,
    fontFamily: typography.body,
    fontSize: 19,
    fontWeight: "600",
  },
  sectionTitlePaper: { color: colors.ink },
  sectionMeta: {
    maxWidth: "42%",
    flexShrink: 1,
    textAlign: "right",
    color: colors.textMuted,
    fontFamily: typography.body,
    fontSize: 11,
    fontWeight: "500",
  },
  surface: {
    borderRadius: radius.lg,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: colors.border,
    backgroundColor: colors.surface,
    padding: 18,
  },
  surfacePaper: {
    borderColor: colors.paperBorder,
    backgroundColor: colors.paperRaised,
  },
  surfaceAccent: { borderColor: colors.red, backgroundColor: colors.redDark },
  poster: {
    minHeight: 250,
    overflow: "hidden",
    borderRadius: radius.lg,
    borderWidth: 1,
    borderColor: "#4A1B18",
    backgroundColor: "#1B0B0A",
    padding: spacing.xl,
    justifyContent: "flex-end",
  },
  posterLight: {
    borderColor: colors.paperBorder,
    backgroundColor: colors.paperRaised,
  },
  posterAccent: {
    position: "absolute",
    top: 0,
    left: 0,
    width: 7,
    height: "100%",
    backgroundColor: colors.red,
  },
  posterBars: {
    position: "absolute",
    right: -8,
    bottom: -16,
    width: 150,
    height: 190,
    flexDirection: "row",
    alignItems: "flex-end",
    gap: 8,
    opacity: 0.13,
    pointerEvents: "none",
  },
  posterBar: { width: 38, height: 145, backgroundColor: colors.paper },
  posterBarTall: { height: 185 },
  posterBarShort: { height: 112 },
  posterEyebrow: {
    color: colors.textMuted,
    fontSize: 11,
    fontWeight: "500",
  },
  posterTitle: {
    maxWidth: "82%",
    marginTop: spacing.xs,
    color: colors.text,
    fontFamily: typography.display,
    fontSize: 30,
    lineHeight: 36,
    fontWeight: "600",
  },
  posterTitleLight: { color: colors.ink },
  posterDescription: {
    maxWidth: "76%",
    marginTop: spacing.md,
    color: colors.textMuted,
    fontSize: 14,
    lineHeight: 20,
  },
  posterDescriptionLight: { color: colors.textFaint },
  posterMeta: {
    marginTop: spacing.lg,
    color: colors.textMuted,
    fontSize: 11,
    fontWeight: "500",
  },
  metric: {
    flex: 1,
    minHeight: 88,
    borderRadius: radius.lg,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.backgroundElevated,
    padding: spacing.lg,
    justifyContent: "center",
  },
  metricPaper: {
    borderColor: colors.paperBorder,
    backgroundColor: colors.paperRaised,
  },
  metricValue: {
    color: colors.text,
    fontFamily: typography.display,
    fontSize: 25,
    fontWeight: "600",
  },
  metricValuePaper: { color: colors.ink },
  metricLabel: {
    marginTop: 5,
    color: colors.textMuted,
    fontFamily: typography.body,
    fontSize: 12,
    lineHeight: 18,
  },
  infoRow: {
    minHeight: 68,
    flexDirection: "row",
    alignItems: "center",
    gap: 16,
    paddingVertical: 3,
  },
  infoBody: { flex: 1, gap: 5 },
  infoTitle: {
    color: colors.text,
    fontFamily: typography.body,
    fontSize: 15,
    fontWeight: "600",
  },
  infoTitlePaper: { color: colors.ink },
  infoDescription: {
    color: colors.textMuted,
    fontFamily: typography.body,
    fontSize: 13,
    lineHeight: 19,
  },
  divider: { height: StyleSheet.hairlineWidth, backgroundColor: colors.border },
  dividerPaper: { backgroundColor: colors.paperBorder },
  tag: {
    minHeight: 27,
    alignSelf: "flex-start",
    justifyContent: "center",
    borderRadius: 14,
    borderWidth: 1,
    paddingHorizontal: 10,
  },
  tagText: {
    fontFamily: typography.body,
    fontSize: 10,
    fontWeight: "500",
  },
  progressTrack: {
    width: "100%",
    height: 6,
    overflow: "hidden",
    borderRadius: 3,
  },
  progressFill: { height: "100%", borderRadius: 3 },
  labelIcon: {
    width: 40,
    height: 40,
    borderRadius: 12,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: colors.background,
  },
  labelIconPaper: { backgroundColor: "#E7DED0" },
});

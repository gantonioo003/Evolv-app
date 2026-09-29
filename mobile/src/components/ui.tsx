import type { ComponentType, PropsWithChildren, ReactNode } from 'react';
import { Asset } from 'expo-asset';
import {
  Image,
  Platform,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
  type ImageStyle,
  type ImageSourcePropType,
  type StyleProp,
  type ViewStyle,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { colors, radius, shadows, spacing, typography } from '@/constants/theme';
import { themePalettes, useAppTheme, type ResolvedTheme } from '@/context/theme-context';

type IconComponent = ComponentType<{ color?: string; size?: number; strokeWidth?: number }>;
type ThemeTone = 'dark' | 'paper';

function useTonePalette(tone?: ThemeTone) {
  const theme = useAppTheme();
  const forcedTheme: ResolvedTheme | undefined = tone === 'paper' ? 'light' : tone === 'dark' ? 'dark' : undefined;
  return forcedTheme ? themePalettes[forcedTheme] : theme.palette;
}

export function CoverImage({ source, style }: { source: ImageSourcePropType; style: StyleProp<ImageStyle | ViewStyle> }) {
  if (Platform.OS === 'web') {
    const uri = Asset.fromModule(source as number | string | { uri: string; width: number; height: number }).uri;
    const webBackground = {
      backgroundImage: `url("${uri}")`,
      backgroundPosition: 'center',
      backgroundRepeat: 'no-repeat',
      backgroundSize: 'cover',
    } as ViewStyle;

    return <View style={[style, webBackground]} />;
  }

  return <Image source={source} resizeMode="cover" style={style as StyleProp<ImageStyle>} />;
}

type AppScreenProps = PropsWithChildren<{
  tone?: ThemeTone;
  contentStyle?: ViewStyle;
  scroll?: boolean;
}>;

export function AppScreen({ children, tone, contentStyle, scroll = true }: AppScreenProps) {
  const palette = useTonePalette(tone);
  const content = <View style={[styles.content, contentStyle]}>{children}</View>;

  return (
    <SafeAreaView edges={['top', 'left', 'right']} style={[styles.safeArea, { backgroundColor: palette.page }]}> 
      {scroll ? (
        <ScrollView
          contentContainerStyle={styles.scrollContent}
          contentInsetAdjustmentBehavior="automatic"
          keyboardShouldPersistTaps="handled"
          showsVerticalScrollIndicator={false}
        >
          {content}
        </ScrollView>
      ) : (
        content
      )}
    </SafeAreaView>
  );
}

type PageHeaderProps = {
  brand?: string;
  eyebrow: string;
  title: string;
  tone?: ThemeTone;
  actionIcon?: IconComponent;
  actionLabel?: string;
  onAction?: () => void;
};

export function PageHeader({ brand, eyebrow, title, tone, actionIcon: ActionIcon, actionLabel, onAction }: PageHeaderProps) {
  const palette = useTonePalette(tone);
  return (
    <View style={styles.pageHeader}>
      <View style={styles.pageHeaderText}>
        {brand ? <Text style={styles.brand}>{brand}</Text> : null}
        <Text style={styles.eyebrow}>{eyebrow}</Text>
        <Text style={[styles.pageTitle, { color: palette.text }]}>{title}</Text>
      </View>
      {ActionIcon ? (
        <Pressable
          accessibilityLabel={actionLabel}
          accessibilityRole="button"
          onPress={onAction}
          style={({ pressed }) => [styles.iconButton, { backgroundColor: palette.surface, borderColor: palette.border }, pressed && styles.pressed]}
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
  meta,
  height = 370,
  overlayOpacity = 0.38,
}: {
  source: ImageSourcePropType;
  eyebrow: string;
  title: string;
  description: string;
  meta: string;
  height?: number;
  overlayOpacity?: number;
}) {
  const compact = height <= 260;

  return (
    <View style={[styles.cinematicHero, { height }]}>
      <CoverImage source={source} style={styles.cinematicImage} />
      <View style={[styles.cinematicWash, { backgroundColor: `rgba(5, 6, 8, ${overlayOpacity})` }]} />
      <View style={styles.cinematicContent}>
        <View style={styles.cinematicTopline}>
          <Text style={styles.cinematicEyebrow}>{eyebrow}</Text>
          <Text style={styles.cinematicMeta}>{meta}</Text>
        </View>
        <View style={styles.cinematicCopy}>
          <View style={styles.cinematicRule} />
          <Text style={[styles.cinematicTitle, compact && styles.cinematicTitleCompact]}>{title}</Text>
          <Text style={[styles.cinematicDescription, compact && styles.cinematicDescriptionCompact]}>{description}</Text>
        </View>
      </View>
    </View>
  );
}

export function SectionTitle({ title, meta, tone }: { title: string; meta?: string; tone?: ThemeTone }) {
  const palette = useTonePalette(tone);
  return (
    <View style={styles.sectionHeader}>
      <Text style={[styles.sectionTitle, { color: palette.text }]}>{title}</Text>
      {meta ? <Text style={styles.sectionMeta}>{meta}</Text> : null}
    </View>
  );
}

export function Surface({ children, tone, style }: PropsWithChildren<{ tone?: ThemeTone | 'accent'; style?: ViewStyle }>) {
  const palette = useTonePalette(tone === 'accent' ? undefined : tone);
  return (
    <View style={[
      styles.surface,
      tone === 'accent' ? styles.surfaceAccent : { backgroundColor: palette.surface, borderColor: palette.border },
      style,
    ]}>
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
    <View style={[styles.poster, { backgroundColor: light ? themePalettes.light.surface : palette.surface, borderColor: light ? themePalettes.light.border : palette.border }]}>
      <View style={styles.posterAccent} />
      <View style={styles.posterBars}>
        <View style={[styles.posterBar, styles.posterBarTall]} />
        <View style={styles.posterBar} />
        <View style={[styles.posterBar, styles.posterBarShort]} />
      </View>
      <Text style={styles.posterEyebrow}>{eyebrow}</Text>
      <Text style={[styles.posterTitle, { color: light ? themePalettes.light.text : palette.text }]}>{title}</Text>
      <Text style={[styles.posterDescription, { color: light ? themePalettes.light.muted : palette.muted }]}>{description}</Text>
      <Text style={styles.posterMeta}>{meta}</Text>
    </View>
  );
}

export function Metric({ value, label, tone }: { value: string; label: string; tone?: ThemeTone }) {
  const palette = useTonePalette(tone);
  return (
    <View style={[styles.metric, { backgroundColor: palette.elevated, borderColor: palette.border }]}>
      <Text style={[styles.metricValue, { color: palette.text }]}>{value}</Text>
      <Text style={[styles.metricLabel, { color: palette.muted }]}>{label}</Text>
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
        <Text style={[styles.infoDescription, { color: palette.muted }]}>{description}</Text>
      </View>
      {trailing}
    </>
  );

  if (onPress) {
    return (
      <Pressable accessibilityRole="button" onPress={onPress} style={({ pressed }) => [styles.infoRow, pressed && styles.pressed]}>
        {body}
      </Pressable>
    );
  }

  return <View style={styles.infoRow}>{body}</View>;
}

export function Divider({ paper = false }: { paper?: boolean }) {
  const { palette } = useAppTheme();
  return <View style={[styles.divider, { backgroundColor: paper ? themePalettes.light.border : palette.border }]} />;
}

export function Tag({ children, color = colors.gold }: PropsWithChildren<{ color?: string }>) {
  return (
    <View style={[styles.tag, { borderColor: color }]}>
      <Text style={[styles.tagText, { color }]}>{children}</Text>
    </View>
  );
}

export function ProgressBar({ value, color = colors.red, trackColor }: { value: number; color?: string; trackColor?: string }) {
  const { palette } = useAppTheme();
  const normalized = Math.max(0, Math.min(1, value));
  return (
    <View style={[styles.progressTrack, { backgroundColor: trackColor ?? palette.border }]}> 
      <View style={[styles.progressFill, { backgroundColor: color, width: `${normalized * 100}%` }]} />
    </View>
  );
}

export function LabelIcon({ icon: Icon, tone }: { icon: IconComponent; tone?: ThemeTone }) {
  const palette = useTonePalette(tone);
  return (
    <View style={[styles.labelIcon, { backgroundColor: palette.iconSurface }]}>
      <Icon color={palette === themePalettes.light ? colors.red : colors.gold} size={18} strokeWidth={1.8} />
    </View>
  );
}

const styles = StyleSheet.create({
  safeArea: { flex: 1 },
  scrollContent: { flexGrow: 1 },
  content: { flex: 1, width: '100%', maxWidth: 760, alignSelf: 'center', paddingHorizontal: spacing.lg, paddingTop: spacing.sm, paddingBottom: 112, gap: spacing.lg },
  pageHeader: { minHeight: 76, flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
  pageHeaderText: { flex: 1, paddingRight: spacing.md },
  brand: { marginBottom: 5, color: colors.red, fontFamily: typography.display, fontSize: 12, fontWeight: '900', letterSpacing: 0 },
  eyebrow: { color: colors.gold, fontFamily: typography.body, fontSize: 12, fontWeight: '800', textTransform: 'uppercase' },
  pageTitle: { marginTop: 2, fontFamily: typography.display, fontSize: 32, lineHeight: 38, fontWeight: '800', letterSpacing: 0 },
  iconButton: { width: 44, height: 44, borderRadius: 22, borderWidth: 1, borderColor: colors.border, alignItems: 'center', justifyContent: 'center', backgroundColor: colors.surface },
  iconButtonPaper: { backgroundColor: colors.paperRaised, borderColor: colors.paperBorder },
  pressed: { opacity: 0.68, transform: [{ scale: 0.98 }] },
  cinematicHero: { height: 370, overflow: 'hidden', borderRadius: radius.lg, backgroundColor: colors.black },
  cinematicImage: { position: 'absolute', inset: 0, width: '100%', height: '100%', borderRadius: radius.lg },
  cinematicWash: { position: 'absolute', inset: 0, zIndex: 1 },
  cinematicContent: { zIndex: 2, flex: 1, justifyContent: 'space-between', padding: spacing.xl },
  cinematicTopline: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: spacing.md },
  cinematicEyebrow: { color: colors.gold, fontFamily: typography.body, fontSize: 11, fontWeight: '900', textTransform: 'uppercase' },
  cinematicMeta: { color: colors.text, fontFamily: typography.body, fontSize: 10, fontWeight: '800', textTransform: 'uppercase' },
  cinematicCopy: { maxWidth: 430 },
  cinematicRule: { width: 38, height: 4, marginBottom: spacing.md, backgroundColor: colors.red },
  cinematicTitle: { color: colors.text, fontFamily: typography.display, fontSize: 44, lineHeight: 45, fontWeight: '900', textTransform: 'uppercase', letterSpacing: 0 },
  cinematicTitleCompact: { fontSize: 31, lineHeight: 31 },
  cinematicDescription: { maxWidth: 340, marginTop: spacing.md, color: '#E4DDD3', fontFamily: typography.body, fontSize: 13.5, lineHeight: 19 },
  cinematicDescriptionCompact: { maxWidth: 300, marginTop: spacing.sm, fontSize: 12, lineHeight: 17 },
  sectionHeader: { minHeight: 28, marginTop: spacing.sm, flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: spacing.md },
  sectionTitle: { flex: 1, color: colors.text, fontFamily: typography.body, fontSize: 17, fontWeight: '800' },
  sectionTitlePaper: { color: colors.ink },
  sectionMeta: { color: colors.gold, fontFamily: typography.body, fontSize: 11, fontWeight: '800', textTransform: 'uppercase' },
  surface: { borderRadius: radius.lg, borderWidth: 1, borderColor: colors.border, backgroundColor: colors.surface, padding: spacing.lg, ...shadows.card },
  surfacePaper: { borderColor: colors.paperBorder, backgroundColor: colors.paperRaised },
  surfaceAccent: { borderColor: colors.red, backgroundColor: colors.redDark },
  poster: { minHeight: 250, overflow: 'hidden', borderRadius: radius.lg, borderWidth: 1, borderColor: '#4A1B18', backgroundColor: '#1B0B0A', padding: spacing.xl, justifyContent: 'flex-end' },
  posterLight: { borderColor: colors.paperBorder, backgroundColor: colors.paperRaised },
  posterAccent: { position: 'absolute', top: 0, left: 0, width: 7, height: '100%', backgroundColor: colors.red },
  posterBars: { position: 'absolute', right: -8, bottom: -16, width: 150, height: 190, flexDirection: 'row', alignItems: 'flex-end', gap: 8, opacity: 0.13, pointerEvents: 'none' },
  posterBar: { width: 38, height: 145, backgroundColor: colors.paper },
  posterBarTall: { height: 185 },
  posterBarShort: { height: 112 },
  posterEyebrow: { color: colors.gold, fontSize: 11, fontWeight: '900', textTransform: 'uppercase' },
  posterTitle: { maxWidth: '82%', marginTop: spacing.xs, color: colors.text, fontFamily: typography.display, fontSize: 42, lineHeight: 42, fontWeight: '900', textTransform: 'uppercase' },
  posterTitleLight: { color: colors.ink },
  posterDescription: { maxWidth: '76%', marginTop: spacing.md, color: colors.textMuted, fontSize: 14, lineHeight: 20 },
  posterDescriptionLight: { color: colors.textFaint },
  posterMeta: { marginTop: spacing.lg, color: colors.gold, fontSize: 11, fontWeight: '900', textTransform: 'uppercase' },
  metric: { flex: 1, minHeight: 88, borderRadius: radius.lg, borderWidth: 1, borderColor: colors.border, backgroundColor: colors.backgroundElevated, padding: spacing.lg, justifyContent: 'center' },
  metricPaper: { borderColor: colors.paperBorder, backgroundColor: colors.paperRaised },
  metricValue: { color: colors.text, fontFamily: typography.display, fontSize: 25, fontWeight: '900' },
  metricValuePaper: { color: colors.ink },
  metricLabel: { marginTop: 3, color: colors.textMuted, fontSize: 12 },
  infoRow: { minHeight: 62, flexDirection: 'row', alignItems: 'center', gap: spacing.md },
  infoBody: { flex: 1, gap: 3 },
  infoTitle: { color: colors.text, fontFamily: typography.body, fontSize: 14, fontWeight: '700' },
  infoTitlePaper: { color: colors.ink },
  infoDescription: { color: colors.textMuted, fontFamily: typography.body, fontSize: 12, lineHeight: 17 },
  divider: { height: StyleSheet.hairlineWidth, backgroundColor: colors.border },
  dividerPaper: { backgroundColor: colors.paperBorder },
  tag: { minHeight: 27, alignSelf: 'flex-start', justifyContent: 'center', borderRadius: 14, borderWidth: 1, paddingHorizontal: 10 },
  tagText: { fontFamily: typography.body, fontSize: 10, fontWeight: '900', textTransform: 'uppercase' },
  progressTrack: { width: '100%', height: 6, overflow: 'hidden', borderRadius: 3 },
  progressFill: { height: '100%', borderRadius: 3 },
  labelIcon: { width: 38, height: 38, borderRadius: radius.md, alignItems: 'center', justifyContent: 'center', backgroundColor: colors.background },
  labelIconPaper: { backgroundColor: '#E7DED0' },
});

import { useRouter } from 'expo-router';
import { ArrowLeft, Camera, Dumbbell, Ruler, Scale, TrendingUp } from 'lucide-react-native';
import { Pressable, StyleSheet, Text, View } from 'react-native';

import { AppScreen, CinematicHero, Divider, InfoRow, LabelIcon, Metric, ProgressBar, SectionTitle, Surface, Tag } from '@/components/ui';
import { colors, spacing } from '@/constants/theme';
import { useAppTheme, type AppThemePalette } from '@/context/theme-context';

const loadHistory = [
  { label: 'Supino reto', previous: 58, current: 62, progress: 0.78 },
  { label: 'Agachamento', previous: 74, current: 80, progress: 0.72 },
  { label: 'Puxada alta', previous: 38, current: 42, progress: 0.68 },
];

export default function ProgressScreen() {
  const { palette } = useAppTheme();
  const styles = createStyles(palette);
  const router = useRouter();

  return (
    <AppScreen>
      <View style={styles.header}>
        <Pressable accessibilityLabel="Voltar" accessibilityRole="button" onPress={() => router.back()} style={({ pressed }) => [styles.backButton, pressed && styles.pressed]}>
          <ArrowLeft color={palette.text} size={21} />
        </Pressable>
        <View style={styles.headerText}>
          <Text style={styles.eyebrow}>Conta</Text>
          <Text style={styles.title}>Progresso</Text>
        </View>
      </View>

      <CinematicHero
        source={require('@/assets/images/progress-history.png')}
        eyebrow="Últimos 30 dias"
        title={'Evolução\nconsistente'}
        description="Cargas, medidas e fotos opcionais organizadas sem transformar progresso em cobrança."
        meta="+2,1% volume"
        height={240}
        overlayOpacity={0.18}
      />

      <View style={styles.metrics}>
        <Metric value="78,4 kg" label="peso atual" />
        <Metric value="9/12" label="treinos no mês" />
      </View>

      <SectionTitle title="Visão geral" meta="30 dias" />
      <Surface>
        <InfoRow leading={<LabelIcon icon={TrendingUp} />} title="Volume de treino +2,1%" description="Aumento gradual sem mudança brusca no plano." trailing={<Tag color={colors.green}>Estável</Tag>} />
        <Divider />
        <InfoRow leading={<LabelIcon icon={Scale} />} title="Peso corporal +0,8 kg" description="Dentro da faixa esperada para o objetivo atual." />
        <Divider />
        <InfoRow leading={<LabelIcon icon={Ruler} />} title="Medidas opcionais" description="Nenhuma nova medida registrada neste mês." />
      </Surface>

      <SectionTitle title="Cargas" meta="comparação" />
      <Surface>
        {loadHistory.map((item, index) => (
          <View key={item.label}>
            {index > 0 ? <Divider /> : null}
            <View style={styles.loadRow}>
              <View style={styles.loadTitleRow}>
                <View style={styles.loadName}>
                  <Dumbbell color={colors.red} size={17} />
                  <Text style={styles.loadLabel}>{item.label}</Text>
                </View>
                <Text style={styles.loadValue}>{item.previous} kg  →  {item.current} kg</Text>
              </View>
              <ProgressBar value={item.progress} color={colors.red} />
            </View>
          </View>
        ))}
      </Surface>

      <SectionTitle title="Fotos" meta="opcional" />
      <Surface>
        <InfoRow
          leading={<LabelIcon icon={Camera} />}
          title="Nenhuma foto adicionada"
          description="Fotos nunca serão obrigatórias. Você decide se quer acompanhar desta forma."
        />
      </Surface>
    </AppScreen>
  );
}

const createStyles = (palette: AppThemePalette) => StyleSheet.create({
  header: { minHeight: 76, flexDirection: 'row', alignItems: 'center', gap: spacing.md },
  backButton: { width: 44, height: 44, borderRadius: 22, borderWidth: 1, borderColor: palette.border, backgroundColor: palette.surface, alignItems: 'center', justifyContent: 'center' },
  headerText: { flex: 1 },
  eyebrow: { color: colors.red, fontSize: 11, fontWeight: '900', textTransform: 'uppercase' },
  title: { marginTop: 1, color: palette.text, fontSize: 30, fontWeight: '900', textTransform: 'uppercase' },
  metrics: { flexDirection: 'row', gap: spacing.md },
  loadRow: { minHeight: 76, justifyContent: 'center', gap: 10 },
  loadTitleRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: 10 },
  loadName: { flex: 1, flexDirection: 'row', alignItems: 'center', gap: 8 },
  loadLabel: { color: palette.text, fontSize: 13, fontWeight: '800' },
  loadValue: { color: palette.faint, fontSize: 11, fontWeight: '800' },
  pressed: { opacity: 0.65 },
});

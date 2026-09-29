import { Alert, StyleSheet, Text, View } from 'react-native';
import { Bell, CalendarClock, CircleHelp, Dumbbell, Utensils } from 'lucide-react-native';

import { AppScreen, CinematicHero, Divider, InfoRow, LabelIcon, PageHeader, SectionTitle, Tag } from '@/components/ui';
import { colors, spacing } from '@/constants/theme';
import { useImagePreferences } from '@/context/image-preferences-context';
import { useAppTheme, type AppThemePalette } from '@/context/theme-context';
import { pickWeeklyImage, workoutImageLibrary } from '@/data/image-library';

export default function TodayScreen() {
  const { palette } = useAppTheme();
  const imagePreferences = useImagePreferences();
  const styles = createStyles(palette);

  return (
    <AppScreen>
      <PageHeader
        brand="EVOLV"
        eyebrow="Quarta, 13 de setembro"
        title="Hoje"
        actionIcon={CircleHelp}
        actionLabel="Ajuda sobre a tela Hoje"
        onAction={() => Alert.alert('Hoje', 'Esta tela é apenas um resumo. Você não precisa confirmar treino, alimentação ou ausência.')}
      />

      <CinematicHero
        source={pickWeeklyImage(workoutImageLibrary.back, imagePreferences, 'workout-back', 0)}
        eyebrow="Treino 03"
        title={'Costas /\nBíceps'}
        description="55 minutos com foco em puxadas, remadas e progressão conservadora."
        meta="Semana 01 / 12"
      />

      <View style={styles.factStrip}>
        <View style={styles.fact}><Text style={styles.factValue}>04</Text><Text style={styles.factLabel}>exercícios</Text></View>
        <View style={styles.factDivider} />
        <View style={styles.fact}><Text style={styles.factValue}>55</Text><Text style={styles.factLabel}>minutos</Text></View>
        <View style={styles.factDivider} />
        <View style={styles.fact}><Text style={styles.factValue}>3/5</Text><Text style={styles.factLabel}>na semana</Text></View>
      </View>

      <SectionTitle title="Resumo do dia" meta="sem cobrança" />
      <View style={styles.schedule}>
        <InfoRow
          leading={<LabelIcon icon={Dumbbell} />}
          title="Treino previsto: costas e bíceps"
          description="O plano continua mesmo se você não registrar nada hoje."
          trailing={<Tag>55 min</Tag>}
        />
        <Divider />
        <InfoRow
          leading={<LabelIcon icon={Utensils} />}
          title="Almoço: arroz, frango e feijão"
          description="A refeição pode ser consultada ou trocada na aba Dieta."
          trailing={<Tag color={colors.green}>760 kcal</Tag>}
        />
        <Divider />
        <InfoRow
          leading={<LabelIcon icon={Bell} />}
          title="Próximo lembrete: 18:30"
          description="Apenas um aviso, sem necessidade de confirmar presença."
        />
      </View>

      <SectionTitle title="Semana" meta="visão rápida" />
      <View style={styles.schedule}>
        <InfoRow
          leading={<LabelIcon icon={CalendarClock} />}
          title="Próximos treinos"
          description="Qui: ombros e tríceps  |  Sáb: full body  |  Dom: descanso"
        />
      </View>

      <View style={styles.planNote}>
        <Text style={styles.noteTitle}>Nota do plano</Text>
        <Text style={styles.noteText}>Sem ajustes pendentes. O plano segue igual até você pedir uma mudança ao Coach.</Text>
      </View>
    </AppScreen>
  );
}

const createStyles = (palette: AppThemePalette) => StyleSheet.create({
  factStrip: { minHeight: 84, flexDirection: 'row', alignItems: 'center', borderTopWidth: 1, borderBottomWidth: 1, borderColor: palette.border },
  fact: { flex: 1, alignItems: 'center' },
  factDivider: { width: 1, height: 34, backgroundColor: palette.border },
  factValue: { color: palette.text, fontSize: 24, fontWeight: '900' },
  factLabel: { marginTop: 2, color: palette.muted, fontSize: 9.5, fontWeight: '800', textTransform: 'uppercase' },
  schedule: { borderTopWidth: 1, borderBottomWidth: 1, borderColor: palette.border, paddingHorizontal: spacing.xs },
  planNote: { borderLeftWidth: 4, borderLeftColor: colors.red, backgroundColor: palette.accentSoft, padding: spacing.lg },
  noteTitle: { color: palette.text, fontSize: 16, fontWeight: '900' },
  noteText: { marginTop: 6, color: palette.accentText, fontSize: 13, lineHeight: 19 },
});

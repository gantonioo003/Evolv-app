import { Minus, Plus } from 'lucide-react-native';
import { Pressable, StyleSheet, Text, View } from 'react-native';

import { colors, radius } from '@/constants/theme';
import { useAppTheme } from '@/context/theme-context';

export function LoadStepper({ value, onChange }: { value: number; onChange: (value: number) => void }) {
  const { palette } = useAppTheme();

  return (
    <View style={[styles.container, { backgroundColor: palette.page, borderColor: palette.border }]}> 
      <Pressable
        accessibilityLabel="Diminuir carga"
        accessibilityRole="button"
        onPress={() => onChange(Math.max(0, value - 2))}
        style={({ pressed }) => [styles.button, pressed && styles.pressed]}
      >
        <Minus color={palette.muted} size={15} strokeWidth={2.2} />
      </Pressable>
      <Text accessibilityLabel={`Carga atual ${value} quilos`} style={[styles.value, { color: palette.text }]}> 
        {value} kg
      </Text>
      <Pressable
        accessibilityLabel="Aumentar carga"
        accessibilityRole="button"
        onPress={() => onChange(value + 2)}
        style={({ pressed }) => [styles.button, pressed && styles.pressed]}
      >
        <Plus color={colors.gold} size={15} strokeWidth={2.2} />
      </Pressable>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    width: 126,
    height: 38,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.background,
  },
  button: { width: 34, height: 36, alignItems: 'center', justifyContent: 'center' },
  value: { color: colors.text, fontSize: 12, fontWeight: '900', textAlign: 'center' },
  pressed: { opacity: 0.55 },
});

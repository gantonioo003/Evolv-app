import { useEffect } from 'react';
import { useRouter } from 'expo-router';
import { ActivityIndicator, StyleSheet, Text, View } from 'react-native';

import { colors, typography } from '@/constants/theme';
import { useAppTheme } from '@/context/theme-context';

export default function IndexScreen() {
  const { palette } = useAppTheme();
  const router = useRouter();

  useEffect(() => {
    router.replace('/(tabs)');
  }, [router]);

  return (
    <View style={[styles.screen, { backgroundColor: palette.page }]}> 
      <Text style={[styles.brand, { color: palette.text }]}>Evolv</Text>
      <ActivityIndicator color={colors.gold} />
    </View>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1, alignItems: 'center', justifyContent: 'center', gap: 18, backgroundColor: colors.background },
  brand: { color: colors.text, fontFamily: typography.display, fontSize: 34, fontWeight: '900', textTransform: 'uppercase' },
});

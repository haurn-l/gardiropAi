import { Stack } from 'expo-router';
import { DemoProvider } from '../../features/workshops/demo/DemoProvider';
import { colors } from '../../shared/theme/tokens';

/**
 * Örnek akışlar için ortak oturumluk DemoProvider ve Stack düzenini sağlar.
 */
export default function DemoLayout() {
  return (
    <DemoProvider>
      <Stack
        screenOptions={{
          headerShown: false,
          contentStyle: { backgroundColor: colors.background },
        }}
      />
    </DemoProvider>
  );
}

import { Stack } from 'expo-router';
import { StatusBar } from 'expo-status-bar';
import { SafeAreaProvider } from 'react-native-safe-area-context';
import { useFonts } from 'expo-font';
import { DMSans_400Regular, DMSans_500Medium, DMSans_600SemiBold } from '@expo-google-fonts/dm-sans';
import { CormorantGaramond_500Medium } from '@expo-google-fonts/cormorant-garamond';
import { colors } from '../shared/theme/tokens';

export default function RootLayout() {
  const [ready, error] = useFonts({ DMSans: DMSans_400Regular, DMSansMedium: DMSans_500Medium,
    DMSansBold: DMSans_600SemiBold, Cormorant: CormorantGaramond_500Medium });
  if (!ready && !error) return null;
  return <SafeAreaProvider><StatusBar style="dark" />
    <Stack screenOptions={{ headerShown: false, contentStyle: { backgroundColor: colors.background } }} />
  </SafeAreaProvider>;
}

import { View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Header } from '../shared/ui/Header';
import { Text } from '../shared/ui/Text';
import { colors } from '../shared/theme/tokens';

export default function FoundationScreen() {
  return <SafeAreaView style={{ flex: 1, backgroundColor: colors.background }}>
    <Header title="GardıropAI" subtitle="Kişisel stilinin yeni alanı." />
    <View style={{ padding: 24 }}><Text>Mobil uygulamanın ortak tasarım temeli hazır.</Text></View>
  </SafeAreaView>;
}

import { StyleSheet, View } from 'react-native';
import { router, useLocalSearchParams } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Header } from '../../shared/ui/Header';
import { Text } from '../../shared/ui/Text';
import { Button } from '../../shared/ui/Button';
import { colors, space } from '../../shared/theme/tokens';
import { navigationPreviews, type PreviewId } from './navigationPreviews';

// Bu kök ekran ana ekrandan ayrı açılır. Alt barı gizlemek için stil hilesi gerekmez.
export function NavigationPreview() {
  const { kind } = useLocalSearchParams<{ kind?: string }>();
  const id: PreviewId = kind && Object.hasOwn(navigationPreviews, kind) ? (kind as PreviewId) : 'chat';
  const preview = navigationPreviews[id];
  const goBack = () => (router.canGoBack() ? router.back() : router.replace('/'));
  return (
    <SafeAreaView style={styles.screen}>
      <Header title={preview.title} onBack={goBack} />
      <View style={styles.content}>
        <Text>{preview.description}</Text>
        <Text muted>
          Gezinme önizlemesi: bu ekran kök Stack içinde açılır ve alt bar içermez.
        </Text>
        <Button label="Ana ekrana dön" onPress={goBack} />
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: colors.background },
  content: { padding: space.xl, gap: space.lg },
});

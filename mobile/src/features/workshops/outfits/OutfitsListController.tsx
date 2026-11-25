import { useState } from 'react';
import { StyleSheet, View } from 'react-native';
import { router } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import { colors, space } from '../../../shared/theme/tokens';
import { Button } from '../../../shared/ui/Button';
import { Header } from '../../../shared/ui/Header';
import { Text } from '../../../shared/ui/Text';
import { OutfitsScreen } from '../../outfits/screens/OutfitsScreen';
import { useOutfitDemo } from '../demo/OutfitDemoContext';
import { useConversationDemo } from '../demo/ConversationDemoContext';

type DemoViewMode = 'normal' | 'loading' | 'error' | 'empty';

const viewModeOrder: readonly DemoViewMode[] = ['normal', 'loading', 'error', 'empty'];

const viewModeLabels: Record<DemoViewMode, string> = {
  normal: 'Liste durumu: Normal',
  loading: 'Liste durumu: Yükleniyor',
  error: 'Liste durumu: Hata',
  empty: 'Liste durumu: Boş',
};

/**
 * Kombin geçmişi örnek akışının liste controller'ıdır.
 * Oturumluk kombinleri ve sıralama seçimini OutfitsScreen bileşenine bağlar.
 */
export function OutfitsListController() {
  const { items, sort, simulateError, setSort, setSimulateError } = useOutfitDemo();
  const { createConversation } = useConversationDemo();
  const [viewMode, setViewMode] = useState<DemoViewMode>('normal');

  function handleOpen(id: string) {
    router.push({ pathname: '/outfit-history/[id]', params: { id } });
  }

  function handleCreateRequest() {
    const created = createConversation();
    router.push({ pathname: '/conversation-flow/[id]', params: { id: created.id } });
  }

  function handleCycleViewMode() {
    const nextIndex = (viewModeOrder.indexOf(viewMode) + 1) % viewModeOrder.length;
    setViewMode(viewModeOrder[nextIndex]);
  }

  const demoHeader = (
    <View style={styles.demoHeader}>
      <Text variant="caption" muted>
        Oturumluk örnek veriler · Değişiklikler yalnızca bu oturumda tutulur.
      </Text>
      <View style={styles.controls}>
        <Button
          label={viewModeLabels[viewMode]}
          variant="secondary"
          onPress={handleCycleViewMode}
        />
        <Button
          label={simulateError ? 'Hata simülasyonu: Açık' : 'Hata simülasyonu: Kapalı'}
          variant={simulateError ? 'danger' : 'secondary'}
          onPress={() => setSimulateError(!simulateError)}
        />
        <Button
          label="Geçersiz kayıt testi"
          variant="secondary"
          onPress={() => handleOpen('bilinmeyen-kombin')}
        />
      </View>
    </View>
  );

  return (
    <SafeAreaView style={styles.screen}>
      <Header
        title="Kombinlerim"
        onBack={() => (router.canGoBack() ? router.back() : router.replace('/'))}
      />
      <OutfitsScreen
        items={viewMode === 'empty' ? [] : items}
        sort={sort}
        onSortChange={setSort}
        onOpen={handleOpen}
        onCreateRequest={handleCreateRequest}
        loading={viewMode === 'loading'}
        error={
          viewMode === 'error'
            ? 'Kombin geçmişi şu an alınamadı. Lütfen tekrar dene.'
            : undefined
        }
        onRetry={() => setViewMode('normal')}
        header={demoHeader}
      />
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: colors.background },
  demoHeader: { gap: space.sm },
  controls: { flexDirection: 'row', flexWrap: 'wrap', gap: space.sm },
});

import { useRef, useState } from 'react';
import { StyleSheet, View } from 'react-native';
import { router } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import { colors, space } from '../../../shared/theme/tokens';
import { Button } from '../../../shared/ui/Button';
import { Header } from '../../../shared/ui/Header';
import { Text } from '../../../shared/ui/Text';
import { ConversationsScreen } from '../../assistant/screens/ConversationsScreen';
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
 * Sohbet geçmişi örnek akışının liste controller'ıdır.
 */
export function ConversationsListController() {
  const {
    conversations,
    simulateError,
    setSimulateError,
    createConversation,
    deleteConversation,
  } = useConversationDemo();

  const [viewMode, setViewMode] = useState<DemoViewMode>('normal');
  const [busy, setBusy] = useState(false);
  const [actionError, setActionError] = useState<string | undefined>(undefined);
  const busyRef = useRef(false);

  function handleOpen(id: string) {
    router.push({ pathname: '/conversation-flow/[id]', params: { id } });
  }

  function handleCreate() {
    const created = createConversation();
    handleOpen(created.id);
  }

  async function handleDelete(id: string) {
    if (busyRef.current) {
      return;
    }
    busyRef.current = true;
    setBusy(true);
    setActionError(undefined);
    try {
      await deleteConversation(id);
    } catch (err) {
      setActionError(err instanceof Error ? err.message : 'Sohbet silinemedi.');
    } finally {
      busyRef.current = false;
      setBusy(false);
    }
  }

  function handleCycleViewMode() {
    const nextIndex = (viewModeOrder.indexOf(viewMode) + 1) % viewModeOrder.length;
    setViewMode(viewModeOrder[nextIndex]);
  }

  const demoHeader = (
    <View style={styles.demoHeader}>
      <Text variant="caption" muted>
        Oturumluk örnek sohbetler · Onaylanan kombinler kombin geçmişine eklenir.
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
          onPress={() => {
            setActionError(undefined);
            setSimulateError(!simulateError);
          }}
        />
        <Button
          label="Geçersiz sohbet testi"
          variant="secondary"
          onPress={() => handleOpen('bilinmeyen-sohbet')}
        />
      </View>
    </View>
  );

  return (
    <SafeAreaView style={styles.screen}>
      <Header
        title="Sohbetler"
        onBack={() => (router.canGoBack() ? router.back() : router.replace('/'))}
      />
      <ConversationsScreen
        conversations={viewMode === 'empty' ? [] : conversations}
        onOpen={handleOpen}
        onCreate={handleCreate}
        onDelete={(id) => { void handleDelete(id); }}
        loading={viewMode === 'loading'}
        error={
          viewMode === 'error'
            ? 'Sohbet geçmişi şu an alınamadı. Lütfen tekrar dene.'
            : undefined
        }
        onRetry={() => setViewMode('normal')}
        busy={busy}
        actionError={actionError}
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

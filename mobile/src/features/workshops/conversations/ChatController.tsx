import { useRef, useState } from 'react';
import { StyleSheet, View } from 'react-native';
import { router, useLocalSearchParams } from 'expo-router';
import type { SuggestionFeedback } from '../../assistant/model/chat.types';
import { validateChatPrompt } from '../../assistant/model/chatHelpers';
import { ChatScreen } from '../../assistant/screens/ChatScreen';
import { space } from '../../../shared/theme/tokens';
import { Button } from '../../../shared/ui/Button';
import { useConversationDemo } from '../demo/ConversationDemoContext';

/**
 * Seçili sohbet kimliğine göre aktif sohbet ekranını yöneten controller'dır.
 * Aynı anda ikinci isteği engeller; onaylanan kombinleri detay rotasına bağlar.
 */
export function ChatController() {
  const params = useLocalSearchParams<{ id?: string | string[] }>();
  const id = Array.isArray(params.id) ? params.id[0] : params.id;
  const {
    getConversation,
    simulateError,
    setSimulateError,
    sendMessage,
    retryMessage,
    togglePin,
    regenerateSuggestion,
    approveSuggestion,
    setFeedback,
  } = useConversationDemo();

  const [draft, setDraft] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | undefined>(undefined);
  const busyRef = useRef(false);

  const conversation = id ? getConversation(id) : undefined;

  async function runAction(task: () => Promise<void>) {
    if (busyRef.current) {
      return;
    }
    busyRef.current = true;
    setBusy(true);
    setError(undefined);
    try {
      await task();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'İşlem tamamlanamadı.');
    } finally {
      busyRef.current = false;
      setBusy(false);
    }
  }

  function handleBack() {
    if (router.canGoBack()) {
      router.back();
    } else {
      router.replace('/conversation-flow');
    }
  }

  function submitPrompt(raw: string, clearDraft: boolean) {
    if (!conversation || busyRef.current) {
      return;
    }
    const validated = validateChatPrompt(raw);
    if (!validated.ok) {
      setError(validated.error);
      return;
    }
    if (clearDraft) {
      setDraft('');
    }
    void runAction(() => sendMessage(conversation.id, validated.text));
  }

  function handleRetryMessage(messageId: string) {
    if (!conversation) {
      return;
    }
    void runAction(() => retryMessage(conversation.id, messageId));
  }

  function handleTogglePin(messageId: string, itemId: string) {
    if (!conversation || busyRef.current) {
      return;
    }
    togglePin(conversation.id, messageId, itemId);
  }

  function handleRegenerate(messageId: string) {
    if (!conversation) {
      return;
    }
    void runAction(() => regenerateSuggestion(conversation.id, messageId));
  }

  function handleApprove(messageId: string) {
    if (!conversation) {
      return;
    }
    void runAction(async () => {
      await approveSuggestion(conversation.id, messageId);
    });
  }
  function handleOpenApprovedOutfit(outfitId: string) {
    router.push({ pathname: '/outfit-history/[id]', params: { id: outfitId } });
  }
  function handleFeedback(messageId: string, feedback: Exclude<SuggestionFeedback, null>) {
    if (!conversation || busyRef.current) {
      return;
    }
    setFeedback(conversation.id, messageId, feedback);
  }
  const demoBanner = (
    <View style={styles.bannerRow}>
      <Button
        label={simulateError ? 'Hata simülasyonu: Açık' : 'Hata simülasyonu: Kapalı'}
        variant={simulateError ? 'danger' : 'secondary'}
        onPress={() => {
          setError(undefined);
          setSimulateError(!simulateError);
        }}
      />
    </View>
  );
  return (
    <ChatScreen
      conversation={conversation}
      draft={draft}
      onDraftChange={setDraft}
      onSend={() => submitPrompt(draft, true)}
      onSendQuickPrompt={(prompt) => submitPrompt(prompt, false)}
      onBack={handleBack}
      onRetryMessage={handleRetryMessage}
      onTogglePin={handleTogglePin}
      onRegenerate={handleRegenerate}
      onApprove={handleApprove}
      onOpenApprovedOutfit={handleOpenApprovedOutfit}
      onFeedback={handleFeedback}
      busy={busy}
      error={error}
      banner={demoBanner}
    />
  );
}
const styles = StyleSheet.create({
  bannerRow: { flexDirection: 'row', flexWrap: 'wrap', gap: space.sm },
});

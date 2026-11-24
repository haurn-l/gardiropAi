import type { ReactElement } from 'react';
import { FlatList, KeyboardAvoidingView, Platform, StyleSheet, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { colors, radius, space } from '../../../shared/theme/tokens';
import { Button } from '../../../shared/ui/Button';
import { Header } from '../../../shared/ui/Header';
import { Text } from '../../../shared/ui/Text';
import { ChatComposer } from '../components/ChatComposer';
import { MessageBubble } from '../components/MessageBubble';
import type { ConversationRecord, SuggestionFeedback } from '../model/chat.types';

export type ChatScreenProps = {
  conversation: ConversationRecord | undefined;
  draft: string;
  onDraftChange: (next: string) => void;
  onSend: () => void;
  onSendQuickPrompt?: (prompt: string) => void;
  onBack: () => void;
  onRetryMessage?: (messageId: string) => void;
  onTogglePin?: (messageId: string, itemId: string) => void;
  onRegenerate?: (messageId: string) => void;
  onApprove?: (messageId: string) => void;
  onOpenApprovedOutfit?: (outfitId: string) => void;
  onFeedback?: (messageId: string, feedback: Exclude<SuggestionFeedback, null>) => void;
  busy?: boolean;
  error?: string;
  banner?: ReactElement;
};

const quickPrompts = [
  'Bugün ofis için sade bir kombin öner',
  'Serin akşam yürüyüşü için katmanlı kombin hazırla',
  'Hafta sonu kahve buluşması için rahat bir öneri ver',
] as const;

const MessageSeparator = () => <View style={styles.separator} />;

/** Aktif sohbet ekranını mesaj akışı, öneri kartları ve mesaj yazma alanıyla sunar. */
export function ChatScreen(props: ChatScreenProps) {
  const { conversation, draft, onDraftChange, onSend, onSendQuickPrompt, onBack } = props;
  const { busy = false, error, banner } = props;

  const emptyChat = (
    <View style={styles.emptyBox}>
      <Text variant="heading">Kombin asistanına yaz</Text>
      <Text muted style={styles.centered}>
        Temiz kıyafetlerinden öneri almak için bir istek yaz veya hazır örneklerden seç.
      </Text>
      <View style={styles.prompts}>
        {quickPrompts.map((prompt) => (
          <Button
            key={prompt}
            label={prompt}
            variant="secondary"
            disabled={busy}
            onPress={() => onSendQuickPrompt?.(prompt)}
          />
        ))}
      </View>
    </View>
  );

  return (
    <SafeAreaView style={styles.screen}>
      <Header title={conversation ? conversation.title : 'Sohbet'} onBack={onBack} />

      {!conversation ? (
        <View style={styles.notFound}>
          <Text variant="heading">Sohbet bulunamadı</Text>
          <Text muted style={styles.centered}>
            Aradığın sohbet silinmiş veya geçersiz olabilir.
          </Text>
          <Button label="Sohbetlere dön" variant="secondary" onPress={onBack} />
        </View>
      ) : (
        <KeyboardAvoidingView
          style={styles.flex}
          behavior={Platform.OS === 'ios' ? 'padding' : undefined}
        >
          {banner ? <View style={styles.banner}>{banner}</View> : null}
          {error ? (
            <View style={styles.errorBox}>
              <Text variant="caption" accessibilityLiveRegion="polite" style={styles.errorText}>
                {error}
              </Text>
            </View>
          ) : null}

          <FlatList
            data={conversation.messages}
            keyExtractor={(msg) => msg.id}
            renderItem={({ item }) => (
              <MessageBubble
                message={item}
                busy={busy}
                onRetry={props.onRetryMessage}
                onTogglePin={props.onTogglePin}
                onRegenerate={props.onRegenerate}
                onApprove={props.onApprove}
                onOpenApprovedOutfit={props.onOpenApprovedOutfit}
                onFeedback={props.onFeedback}
              />
            )}
            ItemSeparatorComponent={MessageSeparator}
            ListEmptyComponent={emptyChat}
            contentContainerStyle={styles.messagesContent}
            keyboardShouldPersistTaps="handled"
            showsVerticalScrollIndicator={false}
          />

          <ChatComposer
            value={draft}
            onChangeText={onDraftChange}
            onSend={onSend}
            disabled={busy}
          />
        </KeyboardAvoidingView>
      )}
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: colors.background },
  flex: { flex: 1 },
  banner: { paddingHorizontal: space.lg, paddingTop: space.sm },
  errorBox: {
    marginHorizontal: space.lg,
    marginTop: space.sm,
    padding: space.md,
    borderRadius: radius.md,
    backgroundColor: colors.dangerSoft,
  },
  errorText: { color: colors.danger },
  messagesContent: { flexGrow: 1, padding: space.lg, paddingBottom: space.xl },
  separator: { height: space.md },
  emptyBox: {
    padding: space.lg,
    borderRadius: radius.lg,
    borderWidth: 1,
    borderColor: colors.line,
    backgroundColor: colors.surface,
    alignItems: 'center',
    gap: space.md,
  },
  prompts: { width: '100%', gap: space.sm },
  notFound: { flex: 1, padding: space.xl, alignItems: 'center', justifyContent: 'center', gap: space.md },
  centered: { textAlign: 'center' },
});

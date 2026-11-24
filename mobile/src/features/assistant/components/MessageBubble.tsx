import { ActivityIndicator, StyleSheet, View } from 'react-native';
import { colors, radius, space } from '../../../shared/theme/tokens';
import { Button } from '../../../shared/ui/Button';
import { Text } from '../../../shared/ui/Text';
import type { ChatMessage, SuggestionFeedback } from '../model/chat.types';
import { OutfitSuggestion } from './OutfitSuggestion';

export type MessageBubbleProps = {
  message: ChatMessage;
  busy?: boolean;
  onRetry?: (messageId: string) => void;
  onTogglePin?: (messageId: string, itemId: string) => void;
  onRegenerate?: (messageId: string) => void;
  onApprove?: (messageId: string) => void;
  onOpenApprovedOutfit?: (outfitId: string) => void;
  onFeedback?: (messageId: string, feedback: Exclude<SuggestionFeedback, null>) => void;
};

/**
 * Tek bir kullanıcı veya asistan mesajını durumu ve varsa kombin önerisiyle görüntüler.
 */
export function MessageBubble({
  message,
  busy = false,
  onRetry,
  onTogglePin,
  onRegenerate,
  onApprove,
  onOpenApprovedOutfit,
  onFeedback,
}: MessageBubbleProps) {
  const isUser = message.sender === 'user';

  return (
    <View style={[styles.wrapper, isUser ? styles.wrapperUser : styles.wrapperAssistant]}>
      <View
        style={[
          styles.bubble,
          isUser ? styles.bubbleUser : styles.bubbleAssistant,
          message.status === 'error' && styles.bubbleError,
        ]}
      >
        <Text style={isUser ? styles.userText : styles.assistantText}>{message.text}</Text>

        {message.status === 'sending' ? (
          <View style={styles.statusRow} accessibilityLiveRegion="polite">
            <ActivityIndicator size="small" color={colors.accentInk} />
            <Text variant="caption" style={styles.statusText}>
              Gönderiliyor...
            </Text>
          </View>
        ) : null}

        {message.status === 'error' ? (
          <View style={styles.errorBlock} accessibilityLiveRegion="polite">
            <Text variant="caption" style={styles.errorText}>
              {message.errorText ?? 'Mesaj gönderilemedi.'}
            </Text>
            {onRetry ? (
              <Button
                label="Tekrar dene"
                variant="secondary"
                disabled={busy}
                onPress={() => onRetry(message.id)}
              />
            ) : null}
          </View>
        ) : null}

        {!isUser && message.suggestion ? (
          <OutfitSuggestion
            suggestion={message.suggestion}
            busy={busy}
            onTogglePin={(itemId) => onTogglePin?.(message.id, itemId)}
            onRegenerate={() => onRegenerate?.(message.id)}
            onApprove={() => onApprove?.(message.id)}
            onOpenApprovedOutfit={(outfitId) => onOpenApprovedOutfit?.(outfitId)}
            onFeedback={(feedback) => onFeedback?.(message.id, feedback)}
          />
        ) : null}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  wrapper: { width: '100%' },
  wrapperUser: { alignItems: 'flex-end' },
  wrapperAssistant: { alignItems: 'flex-start' },
  bubble: {
    maxWidth: '92%',
    padding: space.md,
    borderRadius: radius.lg,
    gap: space.sm,
  },
  bubbleUser: { backgroundColor: colors.primary },
  bubbleAssistant: {
    width: '100%',
    borderWidth: 1,
    borderColor: colors.line,
    backgroundColor: colors.surface,
  },
  bubbleError: {
    borderWidth: 1,
    borderColor: colors.danger,
    backgroundColor: colors.dangerSoft,
  },
  userText: { color: colors.onPrimary },
  assistantText: { color: colors.ink },
  statusRow: { flexDirection: 'row', alignItems: 'center', gap: space.xs },
  statusText: { color: colors.onPrimary },
  errorBlock: { gap: space.sm },
  errorText: { color: colors.danger },
});

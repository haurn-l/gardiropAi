import { Pressable, StyleSheet, View } from 'react-native';
import { colors, radius, space } from '../../../shared/theme/tokens';
import { Text } from '../../../shared/ui/Text';
import { formatOutfitDate } from '../../outfits/model/outfitDate';
import type { ConversationRecord } from '../model/chat.types';

export type ConversationRowProps = {
  conversation: ConversationRecord;
  onOpen: (id: string) => void;
  onDelete?: (id: string) => void;
};

/**
 * Sohbet geçmişi listesinde tek bir konuşma satırını başlık, son mesaj ve tarihle özetler.
 */
export function ConversationRow({
  conversation,
  onOpen,
  onDelete,
}: ConversationRowProps) {
  const lastMessage = conversation.messages[conversation.messages.length - 1];
  const preview = lastMessage ? lastMessage.text : 'Henüz mesaj yok.';
  const dateLabel = formatOutfitDate(conversation.updatedAt);

  return (
    <View style={styles.row}>
      <Pressable
        accessibilityRole="button"
        accessibilityLabel={`${conversation.title}, ${dateLabel}, ${conversation.messages.length} mesaj`}
        onPress={() => onOpen(conversation.id)}
        style={({ pressed }) => [styles.main, pressed && styles.pressed]}
      >
        <Text variant="strong" style={styles.title} numberOfLines={1}>
          {conversation.title}
        </Text>
        <Text variant="caption" muted numberOfLines={2} style={styles.preview}>
          {preview}
        </Text>
        <Text variant="caption" muted style={styles.meta}>
          {dateLabel} · {conversation.messages.length} mesaj
        </Text>
      </Pressable>

      {onDelete ? (
        <Pressable
          accessibilityRole="button"
          accessibilityLabel={`${conversation.title} sohbetini sil`}
          onPress={() => onDelete(conversation.id)}
          style={({ pressed }) => [styles.deleteButton, pressed && styles.pressed]}
        >
          <Text variant="caption" style={styles.deleteLabel}>
            Sil
          </Text>
        </Pressable>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: space.sm,
    padding: space.md,
    borderRadius: radius.lg,
    borderWidth: 1,
    borderColor: colors.line,
    backgroundColor: colors.surface,
  },
  main: {
    flex: 1,
    minWidth: 0,
    minHeight: 48,
    justifyContent: 'center',
    gap: space.xs,
  },
  title: { flexShrink: 1 },
  preview: { flexShrink: 1 },
  meta: { flexShrink: 1 },
  deleteButton: {
    minWidth: 48,
    minHeight: 48,
    paddingHorizontal: space.sm,
    borderRadius: radius.md,
    backgroundColor: colors.dangerSoft,
    alignItems: 'center',
    justifyContent: 'center',
  },
  deleteLabel: { color: colors.danger, fontWeight: '600' },
  pressed: { opacity: 0.78 },
});

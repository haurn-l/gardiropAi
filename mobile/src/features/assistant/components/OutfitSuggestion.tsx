import { StyleSheet, View } from 'react-native';
import { colors, radius, space } from '../../../shared/theme/tokens';
import { Button } from '../../../shared/ui/Button';
import { Text } from '../../../shared/ui/Text';
import type { OutfitSuggestionDraft, SuggestionFeedback } from '../model/chat.types';
import { canApproveSuggestion } from '../model/chatHelpers';
import { ChatFeedback } from './ChatFeedback';
import { SuggestionItem } from './SuggestionItem';

export type OutfitSuggestionProps = {
  suggestion: OutfitSuggestionDraft;
  busy?: boolean;
  onTogglePin: (itemId: string) => void;
  onRegenerate: () => void;
  onApprove: () => void;
  onOpenApprovedOutfit: (outfitId: string) => void;
  onFeedback: (feedback: Exclude<SuggestionFeedback, null>) => void;
};

/**
 * Sohbet yanıtında önerilen kombini parçaları, onay, yenileme ve geri bildirimle sunar.
 */
export function OutfitSuggestion({
  suggestion,
  busy = false,
  onTogglePin,
  onRegenerate,
  onApprove,
  onOpenApprovedOutfit,
  onFeedback,
}: OutfitSuggestionProps) {
  const approvedId = suggestion.approvedOutfitId;
  const isApproved = approvedId !== null;
  const pinnedCount = suggestion.pinnedItemIds.length;
  const approvable = canApproveSuggestion(suggestion);

  return (
    <View style={styles.card}>
      <View style={styles.header}>
        <Text variant="strong">{suggestion.title}</Text>
        <Text variant="caption" muted>
          {suggestion.reason}
        </Text>
      </View>

      <View style={styles.items}>
        {suggestion.items.map((item, index) => (
          <SuggestionItem
            key={`${item.id}-${index}`}
            item={item}
            pinned={suggestion.pinnedItemIds.includes(item.id)}
            disabled={busy || isApproved}
            onTogglePin={onTogglePin}
          />
        ))}
      </View>

      {isApproved ? (
        <View style={styles.approvedBox}>
          <Text variant="caption" style={styles.approvedText}>
            Bu öneri kombin geçmişine kaydedildi.
          </Text>
          <Button
            label="Kombini incele"
            variant="secondary"
            onPress={() => onOpenApprovedOutfit(approvedId)}
          />
        </View>
      ) : (
        <View style={styles.actions}>
          <Button
            label="Kombini onayla"
            disabled={busy || !approvable}
            onPress={onApprove}
          />
          <Button
            label={pinnedCount > 0 ? `Sabitlenenlerle yenile (${pinnedCount})` : 'Yeni öneri üret'}
            variant="secondary"
            disabled={busy}
            onPress={onRegenerate}
          />
        </View>
      )}

      <ChatFeedback
        value={suggestion.feedback}
        disabled={busy}
        onChange={onFeedback}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    marginTop: space.sm,
    padding: space.md,
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: colors.line,
    backgroundColor: colors.surface,
    gap: space.md,
  },
  header: { gap: space.xs },
  items: { gap: space.sm },
  actions: { gap: space.sm },
  approvedBox: {
    padding: space.sm,
    borderRadius: radius.md,
    backgroundColor: colors.sand,
    gap: space.sm,
  },
  approvedText: { color: colors.success, fontWeight: '600' },
});

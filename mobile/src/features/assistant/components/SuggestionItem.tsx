import { Pressable, StyleSheet, View } from 'react-native';
import { colors, radius, space } from '../../../shared/theme/tokens';
import { Text } from '../../../shared/ui/Text';
import type { OutfitItemSnapshot } from '../../outfits/model/outfit.types';
import { GarmentImage } from '../../wardrobe/components/GarmentImage';
import { StatusBadge } from '../../wardrobe/components/StatusBadge';
import {
  clothingCategoryLabels,
  clothingSeasonLabels,
} from '../../wardrobe/model/clothingOptions';

export type SuggestionItemProps = {
  item: OutfitItemSnapshot;
  pinned: boolean;
  disabled?: boolean;
  onTogglePin: (itemId: string) => void;
};

/**
 * Kombin önerisindeki tek bir parçayı ve yeniden üretimde koruma (sabitleme) düğmesini gösterir.
 */
export function SuggestionItem({
  item,
  pinned,
  disabled = false,
  onTogglePin,
}: SuggestionItemProps) {
  const meta = [
    clothingCategoryLabels[item.category],
    item.color,
    clothingSeasonLabels[item.season],
  ].join(' · ');

  return (
    <View style={[styles.card, pinned && styles.cardPinned]}>
      <View style={styles.thumb}>
        <GarmentImage imageUri={item.imageUri} />
      </View>

      <View style={styles.body}>
        <Text variant="label" style={styles.name}>
          {item.name}
        </Text>
        <Text variant="caption" muted style={styles.meta}>
          {meta}
        </Text>
        <StatusBadge status={item.status} />
      </View>

      <Pressable
        disabled={disabled}
        accessibilityRole="button"
        accessibilityLabel={
          pinned ? `${item.name} sabitlemesini kaldır` : `${item.name} parçasını sabitle`
        }
        accessibilityState={{ selected: pinned, disabled }}
        onPress={() => onTogglePin(item.id)}
        style={({ pressed }) => [
          styles.pinButton,
          pinned && styles.pinButtonActive,
          disabled && styles.disabled,
          pressed && !disabled && styles.pressed,
        ]}
      >
        <Text
          variant="caption"
          style={[styles.pinLabel, pinned && styles.pinLabelActive]}
        >
          {pinned ? 'Sabitlendi' : 'Sabitle'}
        </Text>
      </Pressable>
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: space.sm,
    padding: space.sm,
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: colors.line,
    backgroundColor: colors.background,
  },
  cardPinned: {
    borderColor: colors.primary,
    backgroundColor: colors.accent,
  },
  thumb: { width: 56, flexShrink: 0 },
  body: { flex: 1, minWidth: 0, gap: space.xs },
  name: { flexShrink: 1 },
  meta: { flexShrink: 1 },
  pinButton: {
    minWidth: 48,
    minHeight: 48,
    paddingHorizontal: space.sm,
    borderRadius: radius.sm,
    borderWidth: 1,
    borderColor: colors.line,
    backgroundColor: colors.surface,
    alignItems: 'center',
    justifyContent: 'center',
  },
  pinButtonActive: {
    borderColor: colors.primary,
    backgroundColor: colors.primary,
  },
  pinLabel: { color: colors.ink, fontWeight: '600' },
  pinLabelActive: { color: colors.onPrimary },
  disabled: { opacity: 0.5 },
  pressed: { opacity: 0.8 },
});

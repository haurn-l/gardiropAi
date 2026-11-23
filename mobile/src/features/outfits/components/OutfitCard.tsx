import { Pressable, StyleSheet, View } from 'react-native';
import Svg, { Path } from 'react-native-svg';
import { colors, radius, space } from '../../../shared/theme/tokens';
import { Text } from '../../../shared/ui/Text';
import { GarmentImage } from '../../wardrobe/components/GarmentImage';
import type { OutfitRecord } from '../model/outfit.types';
import { formatOutfitDate } from '../model/outfitDate';

export type OutfitCardProps = {
  item: OutfitRecord;
  onOpen: (id: string) => void;
};

const MAX_PREVIEWS = 4;
const STAR_PATH =
  'M12 2.5l2.9 5.9 6.5.9-4.7 4.6 1.1 6.5L12 17.3l-5.8 3.1 1.1-6.5-4.7-4.6 6.5-.9L12 2.5z';

/**
 * Kombin geçmişi listesinde tek bir kombini küçük parça görselleri, ad, tarih ve puanla özetler.
 */
export function OutfitCard({ item, onOpen }: OutfitCardProps) {
  const dateLabel = formatOutfitDate(item.createdAt);
  const ratingLabel = item.rating === null ? 'Puansız' : `${item.rating} / 5`;
  const previewItems = item.items.slice(0, MAX_PREVIEWS);
  const overflowCount = Math.max(0, item.items.length - MAX_PREVIEWS);

  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={`${item.name}, ${dateLabel}, ${ratingLabel}, ${item.items.length} parça`}
      onPress={() => onOpen(item.id)}
      style={({ pressed }) => [styles.card, pressed && styles.pressed]}
    >
      {previewItems.length > 0 ? (
        <View style={styles.thumbRow} accessible={false}>
          {previewItems.map((piece, index) => (
            <View key={`${piece.id}-${index}`} style={styles.thumbBox}>
              <GarmentImage imageUri={piece.imageUri} />
            </View>
          ))}
          {overflowCount > 0 ? (
            <View style={styles.moreBadge}>
              <Text variant="caption" style={styles.moreText}>
                +{overflowCount}
              </Text>
            </View>
          ) : null}
        </View>
      ) : null}

      <View style={styles.body}>
        <Text variant="strong" style={styles.title}>
          {item.name}
        </Text>

        <View style={styles.metaRow}>
          <Text variant="caption" muted style={styles.metaText}>
            {dateLabel} · {item.items.length} parça
          </Text>

          <View style={[styles.ratingBadge, item.rating !== null && styles.ratingFilled]}>
            <Svg width={14} height={14} viewBox="0 0 24 24" aria-hidden>
              <Path
                d={STAR_PATH}
                fill={item.rating !== null ? colors.primary : 'none'}
                stroke={item.rating !== null ? colors.accentInk : colors.muted}
                strokeWidth={1.8}
                strokeLinejoin="round"
              />
            </Svg>
            <Text
              variant="caption"
              style={item.rating !== null ? styles.ratingTextActive : styles.ratingTextMuted}
            >
              {ratingLabel}
            </Text>
          </View>
        </View>
      </View>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  card: {
    minHeight: 48,
    padding: space.md,
    borderRadius: radius.lg,
    borderWidth: 1,
    borderColor: colors.line,
    backgroundColor: colors.surface,
    gap: space.md,
  },
  thumbRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: space.xs,
  },
  thumbBox: {
    width: 56,
  },
  moreBadge: {
    minWidth: 48,
    minHeight: 56,
    paddingHorizontal: space.sm,
    borderRadius: radius.md,
    backgroundColor: colors.soft,
    alignItems: 'center',
    justifyContent: 'center',
  },
  moreText: { color: colors.ink, fontWeight: '600' },
  body: { gap: space.xs },
  title: { flexShrink: 1 },
  metaRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: space.sm,
  },
  metaText: { flexShrink: 1 },
  ratingBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: space.xs,
    paddingHorizontal: space.sm,
    paddingVertical: space.xs,
    borderRadius: radius.full,
    backgroundColor: colors.soft,
    maxWidth: '100%',
  },
  ratingFilled: { backgroundColor: colors.accent },
  ratingTextActive: { color: colors.accentInk, fontWeight: '600' },
  ratingTextMuted: { color: colors.muted },
  pressed: { opacity: 0.85 },
});

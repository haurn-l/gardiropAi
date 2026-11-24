import { StyleSheet, View } from 'react-native';
import { colors, radius, space } from '../../../shared/theme/tokens';
import { Text } from '../../../shared/ui/Text';
import { GarmentImage } from '../../wardrobe/components/GarmentImage';
import { StatusBadge } from '../../wardrobe/components/StatusBadge';
import {
  clothingCategoryLabels,
  clothingSeasonLabels,
} from '../../wardrobe/model/clothingOptions';
import type { OutfitItemSnapshot } from '../model/outfit.types';

export type OutfitItemListProps = {
  items: readonly OutfitItemSnapshot[];
};

/**
 * Bir kombindeki parça kopyalarını görsel, temel özellikler ve kayıt anındaki durumuyla listeler.
 * Salt okunur geçmiş görünümüdür; canlı kıyafet düzenleme veya favori kontrolü içermez.
 */
export function OutfitItemList({ items }: OutfitItemListProps) {
  if (items.length === 0) {
    return (
      <View style={styles.emptyBox}>
        <Text variant="caption" muted>
          Bu kombinde kayıtlı parça bulunmuyor.
        </Text>
      </View>
    );
  }

  return (
    <View style={styles.list}>
      {items.map((item, index) => {
        const metaParts = [
          clothingCategoryLabels[item.category],
          item.color,
          clothingSeasonLabels[item.season],
        ];
        const extraParts = [item.subCategory, item.usage].filter(
          (value) => value.trim().length > 0
        );

        return (
          <View key={`${item.id}-${index}`} style={styles.card}>
            <View style={styles.thumb}>
              <GarmentImage imageUri={item.imageUri} />
            </View>
            <View style={styles.details}>
              <Text variant="label" style={styles.name}>
                {item.name}
              </Text>
              <Text variant="caption" muted style={styles.meta}>
                {metaParts.join(' · ')}
              </Text>
              {extraParts.length > 0 ? (
                <Text variant="caption" muted style={styles.meta}>
                  {extraParts.join(' · ')}
                </Text>
              ) : null}
              <StatusBadge status={item.status} />
            </View>
          </View>
        );
      })}
    </View>
  );
}

const styles = StyleSheet.create({
  list: {
    gap: space.sm,
  },
  card: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: space.md,
    padding: space.md,
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: colors.line,
    backgroundColor: colors.surface,
  },
  thumb: {
    width: 64,
    flexShrink: 0,
  },
  details: {
    flex: 1,
    minWidth: 0,
    gap: space.xs,
  },
  name: {
    flexShrink: 1,
  },
  meta: {
    flexShrink: 1,
  },
  emptyBox: {
    padding: space.md,
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: colors.line,
    backgroundColor: colors.surface,
  },
});

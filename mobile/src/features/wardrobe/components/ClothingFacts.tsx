import { StyleSheet, View } from 'react-native';
import { colors, radius, space } from '../../../shared/theme/tokens';
import { Text } from '../../../shared/ui/Text';
import type { ClothingRecord } from '../model/clothing.types';
import { clothingCategoryLabels, clothingSeasonLabels } from '../model/clothingOptions';

export type ClothingFactsProps = {
  item: ClothingRecord;
};

/**
 * Kıyafetin kategori, mevsim, renk, alt tür, desen ve kullanım alanı özelliklerini
 * okunur bilgi satırları halinde listeler.
 */
export function ClothingFacts({ item }: ClothingFactsProps) {
  const rows = [
    { label: 'Kategori', value: clothingCategoryLabels[item.category] },
    { label: 'Renk', value: item.color },
    { label: 'Mevsim', value: clothingSeasonLabels[item.season] },
    { label: 'Alt tür', value: item.subCategory || 'Belirtilmedi' },
    { label: 'Desen', value: item.hasPrint ? 'Desenli' : 'Düz' },
    { label: 'Kullanım alanı', value: item.usage || 'Belirtilmedi' },
  ];

  return (
    <View style={styles.card}>
      {rows.map((row, index) => (
        <View
          key={row.label}
          style={[styles.row, index < rows.length - 1 && styles.rowDivider]}
        >
          <Text variant="caption" muted style={styles.label}>
            {row.label}
          </Text>
          <Text variant="label" style={styles.value}>
            {row.value}
          </Text>
        </View>
      ))}
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    borderRadius: radius.lg,
    borderWidth: 1,
    borderColor: colors.line,
    backgroundColor: colors.surface,
    paddingHorizontal: space.md,
  },
  row: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    justifyContent: 'space-between',
    alignItems: 'center',
    gap: space.sm,
    paddingVertical: space.md,
  },
  rowDivider: {
    borderBottomWidth: 1,
    borderBottomColor: colors.line,
  },
  label: {
    flexShrink: 1,
  },
  value: {
    flexShrink: 1,
    textAlign: 'right',
  },
});

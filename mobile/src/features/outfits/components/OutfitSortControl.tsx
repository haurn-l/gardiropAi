import { Pressable, StyleSheet, View } from 'react-native';
import { colors, radius, space } from '../../../shared/theme/tokens';
import { Text } from '../../../shared/ui/Text';
import type { OutfitSort } from '../model/outfit.types';

export type OutfitSortControlProps = {
  value: OutfitSort;
  onChange: (next: OutfitSort) => void;
};

const sortOptions: readonly { value: OutfitSort; label: string }[] = [
  { value: 'newest', label: 'En yeni' },
  { value: 'oldest', label: 'En eski' },
  { value: 'rating', label: 'Puana göre' },
];

/**
 * Kombin geçmişi listesinin sıralama düzenini kontrol eden çip grubudur.
 * Kendi içinde ikinci bir state tutmaz; seçili değeri dışarıdan alır.
 */
export function OutfitSortControl({ value, onChange }: OutfitSortControlProps) {
  function handleSelect(next: OutfitSort) {
    if (next !== value) {
      onChange(next);
    }
  }

  return (
    <View
      accessibilityRole="radiogroup"
      accessibilityLabel="Kombin sıralaması"
      style={styles.row}
    >
      {sortOptions.map((option) => {
        const selected = option.value === value;
        return (
          <Pressable
            key={option.value}
            accessibilityRole="radio"
            accessibilityLabel={option.label}
            accessibilityState={{ checked: selected }}
            onPress={() => handleSelect(option.value)}
            style={({ pressed }) => [
              styles.chip,
              selected && styles.chipSelected,
              pressed && styles.pressed,
            ]}
          >
            <Text
              variant="label"
              style={[styles.label, selected && styles.labelSelected]}
            >
              {option.label}
            </Text>
          </Pressable>
        );
      })}
    </View>
  );
}

const styles = StyleSheet.create({
  row: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: space.sm,
  },
  chip: {
    minWidth: 48,
    minHeight: 48,
    maxWidth: '100%',
    paddingHorizontal: space.md,
    paddingVertical: space.sm,
    borderRadius: radius.full,
    borderWidth: 1,
    borderColor: colors.line,
    backgroundColor: colors.surface,
    alignItems: 'center',
    justifyContent: 'center',
  },
  chipSelected: {
    borderColor: colors.primary,
    backgroundColor: colors.primary,
  },
  label: {
    color: colors.ink,
    flexShrink: 1,
  },
  labelSelected: {
    color: colors.onPrimary,
  },
  pressed: {
    opacity: 0.8,
  },
});

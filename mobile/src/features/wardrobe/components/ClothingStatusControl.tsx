import { Pressable, StyleSheet, View } from 'react-native';
import { colors, radius, space } from '../../../shared/theme/tokens';
import { Text } from '../../../shared/ui/Text';
import type { ClothingStatus } from '../model/clothingCard.types';
import { clothingStatusLabels } from '../model/clothingStatus';

export type ClothingStatusControlProps = {
  value: ClothingStatus;
  onChange: (next: ClothingStatus) => void;
  disabled?: boolean;
};

const statuses: readonly ClothingStatus[] = ['TEMIZ', 'KIRLI', 'KULLANIM_DISI'];

const statusTone: Record<ClothingStatus, string> = {
  TEMIZ: colors.success,
  KIRLI: colors.danger,
  KULLANIM_DISI: colors.muted,
};

/**
 * Kıyafetin temizlik ve kullanım durumunu değiştirmek için kullanılan erişilebilir seçicidir.
 * Zaten seçili olan duruma tekrar basıldığında callback çağırmayacak.
 */
export function ClothingStatusControl({
  value,
  onChange,
  disabled = false,
}: ClothingStatusControlProps) {
  function handleSelect(status: ClothingStatus) {
    if (disabled || status === value) {
      return;
    }
    onChange(status);
  }

  return (
    <View
      accessibilityRole="radiogroup"
      accessibilityLabel="Kıyafet durumu"
      style={styles.row}
    >
      {statuses.map((status) => {
        const selected = value === status;
        const label = clothingStatusLabels[status];

        return (
          <Pressable
            key={status}
            accessibilityRole="radio"
            accessibilityLabel={label}
            accessibilityState={{ checked: selected, disabled }}
            disabled={disabled}
            onPress={() => handleSelect(status)}
            style={({ pressed }) => [
              styles.option,
              selected && styles.optionSelected,
              disabled && styles.disabled,
              pressed && styles.pressed,
            ]}
          >
            <View style={[styles.dot, { backgroundColor: statusTone[status] }]} />
            <Text
              variant="label"
              style={[styles.label, selected && styles.labelSelected]}
            >
              {label}
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
  option: {
    minWidth: 48,
    minHeight: 48,
    maxWidth: '100%',
    flexDirection: 'row',
    alignItems: 'center',
    gap: space.sm,
    paddingHorizontal: space.md,
    paddingVertical: space.sm,
    borderRadius: radius.full,
    borderWidth: 1,
    borderColor: colors.line,
    backgroundColor: colors.surface,
  },
  optionSelected: {
    borderColor: colors.accentInk,
    backgroundColor: colors.accent,
  },
  dot: {
    width: 10,
    height: 10,
    borderRadius: radius.full,
  },
  label: {
    flexShrink: 1,
    color: colors.ink,
  },
  labelSelected: {
    color: colors.accentInk,
  },
  disabled: {
    opacity: 0.45,
  },
  pressed: {
    opacity: 0.8,
  },
});

import { Pressable, StyleSheet } from 'react-native';
import { colors, radius, space } from '../../../shared/theme/tokens';
import { Icon, type IconName } from '../../../shared/ui/Icon';
import { Text } from '../../../shared/ui/Text';

type FilterChipProps = {
  label: string;
  selected: boolean;
  onPress: () => void;
  icon?: IconName;
};

/**
 * Kategori, durum ve favori filtrelerinde kullanılan erişilebilir seçim kontrolüdür.
 * Seçili durumu açık turuncu temayla ve ekran okuyucu checked bilgisiyle bildirilir.
 */
export function FilterChip({ label, selected, onPress, icon }: FilterChipProps) {
  const textColor = selected ? colors.onPrimary : colors.ink;

  return (
    <Pressable
      accessibilityRole="togglebutton"
      accessibilityState={{ checked: selected }}
      accessibilityLabel={label}
      onPress={onPress}
      style={({ pressed }) => [
        styles.chip,
        selected && styles.chipSelected,
        pressed && styles.pressed,
      ]}
    >
      {icon ? <Icon name={icon} size={16} color={textColor} filled={selected} /> : null}
      <Text variant="label" style={[styles.label, { color: textColor }]}>
        {label}
      </Text>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  chip: {
    minHeight: 40,
    flexDirection: 'row',
    alignItems: 'center',
    gap: space.xs,
    paddingHorizontal: space.md,
    paddingVertical: space.sm,
    borderRadius: radius.full,
    borderWidth: 1,
    borderColor: colors.line,
    backgroundColor: colors.surface,
  },
  chipSelected: {
    backgroundColor: colors.primary,
    borderColor: colors.primary,
  },
  label: {
    flexShrink: 1,
  },
  pressed: {
    opacity: 0.82,
  },
});

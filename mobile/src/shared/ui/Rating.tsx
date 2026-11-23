import { Pressable, StyleSheet, View } from 'react-native';
import Svg, { Path } from 'react-native-svg';
import { colors, radius, space } from '../theme/tokens';
import type { RatingValue } from './rating.types';
import { Text } from './Text';

export type RatingProps = {
  value: RatingValue | null;
  onChange: (next: RatingValue | null) => void;
  disabled?: boolean;
};

const scores: readonly RatingValue[] = [1, 2, 3, 4, 5];
const STAR_PATH =
  'M12 2.5l2.9 5.9 6.5.9-4.7 4.6 1.1 6.5L12 17.3l-5.8 3.1 1.1-6.5-4.7-4.6 6.5-.9L12 2.5z';
/**
 * 1 ile 5 arasında puan seçimi ve ayrı temizleme aksiyonu sunan ortak bileşendir.
 */
export function Rating({ value, onChange, disabled = false }: RatingProps) {
  const isClearDisabled = disabled || value === null;
  function handleSelect(score: RatingValue) {
    if (disabled || value === score) {
      return;
    }
    onChange(score);
  }
  function handleClear() {
    if (isClearDisabled) {
      return;
    }
    onChange(null);
  }
  return (
    <View style={styles.container}>
      <View
        accessibilityRole="radiogroup"
        accessibilityLabel="Puan seçimi"
        style={styles.starsRow}
      >
        {scores.map((score) => {
          const isFilled = value !== null && score <= value;
          const isSelected = value === score;

          return (
            <Pressable
              key={score}
              accessibilityRole="radio"
              accessibilityLabel={`${score} yıldız`}
              accessibilityState={{ checked: isSelected, disabled }}
              disabled={disabled}
              onPress={() => handleSelect(score)}
              style={({ pressed }) => [
                styles.starButton,
                isSelected && styles.starButtonSelected,
                disabled && styles.disabled,
                pressed && styles.pressed,
              ]}
            >
              <Svg width={24} height={24} viewBox="0 0 24 24" aria-hidden>
                <Path
                  d={STAR_PATH}
                  fill={isFilled ? colors.primary : 'none'}
                  stroke={isFilled ? colors.accentInk : colors.muted}
                  strokeWidth={1.6}
                  strokeLinejoin="round"
                />
              </Svg>
            </Pressable>
          );
        })}
      </View>

      <View style={styles.footerRow}>
        <Text variant="caption" muted>
          {value === null ? 'Henüz puanlanmadı' : `Seçili puan: ${value} / 5`}
        </Text>
        <Pressable
          accessibilityRole="button"
          accessibilityLabel="Puanı temizle"
          accessibilityState={{ disabled: isClearDisabled }}
          disabled={isClearDisabled}
          onPress={handleClear}
          style={({ pressed }) => [
            styles.clearButton,
            isClearDisabled && styles.disabled,
            pressed && styles.pressed,
          ]}
        >
          <Text variant="label" style={styles.clearText}>
            Puanı temizle
          </Text>
        </Pressable>
      </View>
    </View>
  );
}
const styles = StyleSheet.create({
  container: {
    gap: space.sm,
  },
  starsRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: space.xs,
  },
  starButton: {
    minWidth: 48,
    minHeight: 48,
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: colors.line,
    backgroundColor: colors.surface,
    alignItems: 'center',
    justifyContent: 'center',
  },
  starButtonSelected: {
    borderColor: colors.accentInk,
    backgroundColor: colors.accent,
  },
  footerRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: space.sm,
  },
  clearButton: {
    minWidth: 48,
    minHeight: 48,
    paddingHorizontal: space.md,
    paddingVertical: space.sm,
    borderRadius: radius.md,
    backgroundColor: colors.soft,
    alignItems: 'center',
    justifyContent: 'center',
    maxWidth: '100%',
  },
  clearText: {
    color: colors.ink,
  },
  disabled: {
    opacity: 0.45,
  },
  pressed: {
    opacity: 0.8,
  },
});

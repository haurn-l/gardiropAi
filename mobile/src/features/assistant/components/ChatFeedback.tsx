import { Pressable, StyleSheet, View } from 'react-native';
import { colors, radius, space } from '../../../shared/theme/tokens';
import { Text } from '../../../shared/ui/Text';
import type { SuggestionFeedback } from '../model/chat.types';

export type ChatFeedbackProps = {
  value: SuggestionFeedback;
  disabled?: boolean;
  onChange: (next: Exclude<SuggestionFeedback, null>) => void;
};

const options: readonly { value: Exclude<SuggestionFeedback, null>; label: string }[] = [
  { value: 'like', label: 'Beğendim' },
  { value: 'dislike', label: 'Beğenmedim' },
];

/**
 * Kombin önerisine yönelik olumlu/olumsuz geri bildirim seçimini yönetir.
 */
export function ChatFeedback({ value, disabled = false, onChange }: ChatFeedbackProps) {
  return (
    <View style={styles.row} accessibilityLabel="Öneri geri bildirimi">
      {options.map((option) => {
        const selected = value === option.value;
        return (
          <Pressable
            key={option.value}
            disabled={disabled}
            accessibilityRole="button"
            accessibilityLabel={option.label}
            accessibilityState={{ selected, disabled }}
            onPress={() => onChange(option.value)}
            style={({ pressed }) => [
              styles.chip,
              selected && styles.chipSelected,
              disabled && styles.disabled,
              pressed && !disabled && styles.pressed,
            ]}
          >
            <Text
              variant="caption"
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
    paddingHorizontal: space.md,
    borderRadius: radius.full,
    borderWidth: 1,
    borderColor: colors.line,
    backgroundColor: colors.background,
    alignItems: 'center',
    justifyContent: 'center',
  },
  chipSelected: {
    borderColor: colors.accentInk,
    backgroundColor: colors.accent,
  },
  label: { color: colors.ink, fontWeight: '600' },
  labelSelected: { color: colors.accentInk },
  disabled: { opacity: 0.5 },
  pressed: { opacity: 0.8 },
});

import { Pressable, StyleSheet, TextInput, View } from 'react-native';
import { colors, fonts, radius, space } from '../../../shared/theme/tokens';
import { Text } from '../../../shared/ui/Text';

type FormTextFieldProps = {
  label: string;
  value: string;
  onChangeText: (next: string) => void;
  placeholder: string;
  error?: string;
  disabled?: boolean;
};

/**
 * Etiketli, hata mesajlı ve erişilebilir tek satırlık form giriş alanıdır.
 */
export function FormTextField({
  label,
  value,
  onChangeText,
  placeholder,
  error,
  disabled = false,
}: FormTextFieldProps) {
  return (
    <View style={styles.field}>
      <Text variant="label">{label}</Text>
      <TextInput
        value={value}
        onChangeText={onChangeText}
        placeholder={placeholder}
        placeholderTextColor={colors.muted}
        accessibilityLabel={label}
        editable={!disabled}
        style={[
          styles.input,
          Boolean(error) && styles.inputError,
          disabled && styles.disabled,
        ]}
      />
      {error ? (
        <Text variant="caption" accessibilityLiveRegion="polite" style={styles.errorText}>
          {error}
        </Text>
      ) : null}
    </View>
  );
}

type ChoiceOption<T> = {
  value: T;
  label: string;
};

type FormChoiceGroupProps<T extends string | boolean> = {
  label: string;
  options: readonly ChoiceOption<T>[];
  value: T;
  onSelect: (next: T) => void;
  disabled?: boolean;
  error?: string;
};

/**
 * Kategori, mevsim ve desen seçimleri için en az 48x48 dokunma alanlı seçenek grubudur.
 */
export function FormChoiceGroup<T extends string | boolean>({
  label,
  options,
  value,
  onSelect,
  disabled = false,
  error,
}: FormChoiceGroupProps<T>) {
  return (
    <View style={styles.field}>
      <Text variant="label">{label}</Text>
      <View accessibilityRole="radiogroup" accessibilityLabel={label} style={styles.chipRow}>
        {options.map((option) => {
          const selected = option.value === value;
          return (
            <Pressable
              key={String(option.value)}
              accessibilityRole="radio"
              accessibilityLabel={option.label}
              accessibilityState={{ checked: selected, disabled }}
              disabled={disabled}
              onPress={() => onSelect(option.value)}
              style={({ pressed }) => [
                styles.chip,
                selected && styles.chipSelected,
                disabled && styles.disabled,
                pressed && styles.pressed,
              ]}
            >
              <Text
                variant="label"
                style={[styles.chipText, selected && styles.chipTextSelected]}
              >
                {option.label}
              </Text>
            </Pressable>
          );
        })}
      </View>
      {error ? (
        <Text variant="caption" accessibilityLiveRegion="polite" style={styles.errorText}>
          {error}
        </Text>
      ) : null}
    </View>
  );
}
const styles = StyleSheet.create({
  field: { gap: space.xs },
  input: {
    minHeight: 48,
    paddingHorizontal: space.md,
    paddingVertical: space.sm,
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: colors.line,
    backgroundColor: colors.surface,
    fontFamily: fonts.regular,
    fontSize: 15,
    color: colors.ink,
  },
  inputError: { borderColor: colors.danger },
  chipRow: { flexDirection: 'row', flexWrap: 'wrap', gap: space.sm },
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
  chipSelected: { borderColor: colors.primary, backgroundColor: colors.primary },
  chipText: { color: colors.ink, flexShrink: 1 },
  chipTextSelected: { color: colors.onPrimary },
  errorText: { color: colors.danger },
  disabled: { opacity: 0.45 },
  pressed: { opacity: 0.8 },
});

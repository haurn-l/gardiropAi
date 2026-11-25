import { Pressable, StyleSheet, TextInput, View } from 'react-native';
import { colors, fonts, radius, space } from '../../../shared/theme/tokens';
import { Text } from '../../../shared/ui/Text';
import { MAX_CHAT_PROMPT_LENGTH, validateChatPrompt } from '../model/chatHelpers';

export type ChatComposerProps = {
  value: string;
  onChangeText: (next: string) => void;
  onSend: () => void;
  disabled?: boolean;
  placeholder?: string;
};

/**
 * Aktif sohbet ekranı için kontrollü mesaj yazma ve gönderme çubuğudur.
 */
export function ChatComposer({
  value,
  onChangeText,
  onSend,
  disabled = false,
  placeholder = 'Hava durumu, ortam veya stil isteğini yaz...',
}: ChatComposerProps) {
  const validation = validateChatPrompt(value);
  const tooLong = value.trim().length > MAX_CHAT_PROMPT_LENGTH;
  const canSend = !disabled && validation.ok;

  return (
    <View style={styles.container}>
      {tooLong && !validation.ok ? (
        <Text variant="caption" style={styles.errorText} accessibilityLiveRegion="polite">
          {validation.error}
        </Text>
      ) : null}

      <View style={styles.row}>
        <TextInput
          value={value}
          onChangeText={onChangeText}
          placeholder={placeholder}
          placeholderTextColor={colors.muted}
          multiline
          editable={!disabled}
          accessibilityLabel="Sohbet mesajı"
          style={[styles.input, tooLong && styles.inputError]}
        />

        <Pressable
          disabled={!canSend}
          accessibilityRole="button"
          accessibilityLabel="Mesajı gönder"
          accessibilityState={{ disabled: !canSend }}
          onPress={onSend}
          style={({ pressed }) => [
            styles.sendButton,
            !canSend && styles.sendButtonDisabled,
            pressed && canSend && styles.pressed,
          ]}
        >
          <Text variant="label" style={styles.sendLabel}>
            Gönder
          </Text>
        </Pressable>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    paddingHorizontal: space.lg,
    paddingVertical: space.sm,
    borderTopWidth: 1,
    borderColor: colors.line,
    backgroundColor: colors.surface,
    gap: space.xs,
  },
  row: {
    flexDirection: 'row',
    alignItems: 'flex-end',
    gap: space.sm,
  },
  input: {
    flex: 1,
    minHeight: 48,
    maxHeight: 120,
    paddingHorizontal: space.md,
    paddingVertical: space.sm,
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: colors.line,
    backgroundColor: colors.background,
    color: colors.ink,
    fontFamily: fonts.regular,
    fontSize: 15,
  },
  inputError: { borderColor: colors.danger },
  sendButton: {
    minWidth: 76,
    minHeight: 48,
    paddingHorizontal: space.md,
    borderRadius: radius.md,
    backgroundColor: colors.primary,
    alignItems: 'center',
    justifyContent: 'center',
  },
  sendButtonDisabled: { opacity: 0.45 },
  sendLabel: { color: colors.onPrimary },
  errorText: { color: colors.danger },
  pressed: { opacity: 0.85 },
});

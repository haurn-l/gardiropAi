import { Modal, Pressable, ScrollView, StyleSheet, View } from 'react-native';
import { colors, radius, space } from '../theme/tokens';
import { Button } from './Button';
import { Text } from './Text';

export type ConfirmDialogProps = {
  visible: boolean;
  title: string;
  message: string;
  confirmLabel: string;
  cancelLabel?: string;
  confirmVariant?: 'danger' | 'primary';
  busy?: boolean;
  error?: string;
  onConfirm: () => void;
  onCancel: () => void;
};

/**
 * Silme veya kaydedilmemiş değişiklikten çıkış gibi kritik kararlar için
 *  erişilebilir onay penceresidir. Meşgulken kapanmayı ve çift onayı engeller.
 */
export function ConfirmDialog({
  visible,
  title,
  message,
  confirmLabel,
  cancelLabel = 'Vazgeç',
  confirmVariant = 'danger',
  busy = false,
  error,
  onConfirm,
  onCancel,
}: ConfirmDialogProps) {
  function handleDismiss() {
    if (!busy) {
      onCancel();
    }
  }

  return (
    <Modal
      visible={visible}
      transparent
      animationType="fade"
      statusBarTranslucent
      onRequestClose={handleDismiss}
    >
      <View style={styles.overlay}>
        <Pressable
          accessible={false}
          disabled={busy}
          onPress={handleDismiss}
          style={[StyleSheet.absoluteFill, styles.backdrop]}
        />
        <View style={styles.card} accessibilityViewIsModal>
          <ScrollView bounces={false} contentContainerStyle={styles.body}>
            <Text variant="heading">{title}</Text>
            <Text muted>{message}</Text>

            {error ? (
              <View style={styles.errorBox}>
                <Text
                  variant="caption"
                  accessibilityLiveRegion="polite"
                  style={styles.errorText}
                >
                  {error}
                </Text>
              </View>
            ) : null}

            <View style={styles.actions}>
              <Button
                label={cancelLabel}
                variant="secondary"
                disabled={busy}
                onPress={handleDismiss}
                style={styles.actionButton}
              />
              <Button
                label={confirmLabel}
                variant={confirmVariant}
                busy={busy}
                disabled={busy}
                onPress={onConfirm}
                style={styles.actionButton}
              />
            </View>
          </ScrollView>
        </View>
      </View>
    </Modal>
  );
}

const styles = StyleSheet.create({
  overlay: {
    flex: 1,
    justifyContent: 'center',
    padding: space.lg,
  },
  backdrop: {

    backgroundColor: colors.ink,
    opacity: 0.45,
  },
  card: {
    maxHeight: '85%',
    borderRadius: radius.lg,
    borderWidth: 1,
    borderColor: colors.line,
    backgroundColor: colors.surface,
    overflow: 'hidden',
  },
  body: {
    padding: space.lg,
    gap: space.md,
  },
  errorBox: {
    padding: space.md,
    borderRadius: radius.sm,
    backgroundColor: colors.dangerSoft,
  },
  errorText: {
    color: colors.danger,
  },
  actions: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    justifyContent: 'flex-end',
    gap: space.sm,
    paddingTop: space.xs,
  },
  actionButton: {
    flexGrow: 1,
  },
});

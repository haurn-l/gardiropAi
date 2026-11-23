import { Modal, Pressable, ScrollView, StyleSheet, View } from 'react-native';
import { colors, radius, space } from '../../../shared/theme/tokens';
import { Button } from '../../../shared/ui/Button';
import { Text } from '../../../shared/ui/Text';
import { mockPhotoOptions } from './clothingDemoData';

type MockPhotoPickerModalProps = {
  visible: boolean;
  selectedUri: string;
  onSelect: (uri: string) => void;
  onClose: () => void;
};

/**
 * Tekrar çek akışında kamera olmadan örnek fotoğraf seçimi sunan penceredir.
 */
export function MockPhotoPickerModal({
  visible,
  selectedUri,
  onSelect,
  onClose,
}: MockPhotoPickerModalProps) {
  return (
    <Modal
      visible={visible}
      transparent
      animationType="fade"
      statusBarTranslucent
      onRequestClose={onClose}
    >
      <View style={styles.overlay}>
        <Pressable
          accessible={false}
          onPress={onClose}
          style={[StyleSheet.absoluteFill, styles.backdrop]}
        />
        <View style={styles.card} accessibilityViewIsModal>
          <ScrollView bounces={false} contentContainerStyle={styles.body}>
            <Text variant="heading">Örnek fotoğraf seç</Text>
            <Text variant="caption" muted>
              Yeni fotoğraf seçildiğinde form boş taslakla devam eder.
            </Text>

            <View style={styles.list}>
              {mockPhotoOptions.map((option) => {
                const active = option.uri === selectedUri;
                return (
                  <Pressable
                    key={option.id}
                    accessibilityRole="button"
                    accessibilityLabel={option.label}
                    accessibilityState={{ selected: active }}
                    onPress={() => onSelect(option.uri)}
                    style={({ pressed }) => [
                      styles.option,
                      active && styles.optionActive,
                      pressed && styles.pressed,
                    ]}
                  >
                    <Text variant="label" style={active ? styles.activeText : undefined}>
                      {option.label}
                    </Text>
                  </Pressable>
                );
              })}
            </View>

            <Button label="Kapat" variant="secondary" onPress={onClose} />
          </ScrollView>
        </View>
      </View>
    </Modal>
  );
}

const styles = StyleSheet.create({
  overlay: { flex: 1, justifyContent: 'center', padding: space.lg },
  backdrop: { backgroundColor: colors.ink, opacity: 0.45 },
  card: {
    maxHeight: '85%',
    borderRadius: radius.lg,
    borderWidth: 1,
    borderColor: colors.line,
    backgroundColor: colors.surface,
    overflow: 'hidden',
  },
  body: { padding: space.lg, gap: space.md },
  list: { gap: space.sm },
  option: {
    minHeight: 48,
    paddingHorizontal: space.md,
    paddingVertical: space.sm,
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: colors.line,
    backgroundColor: colors.background,
    justifyContent: 'center',
  },
  optionActive: { borderColor: colors.accentInk, backgroundColor: colors.accent },
  activeText: { color: colors.accentInk },
  pressed: { opacity: 0.8 },
});

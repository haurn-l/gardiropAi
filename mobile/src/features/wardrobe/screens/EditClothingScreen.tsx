import { KeyboardAvoidingView, Platform, ScrollView, StyleSheet, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { colors, space } from '../../../shared/theme/tokens';
import { Button } from '../../../shared/ui/Button';
import { ConfirmDialog } from '../../../shared/ui/ConfirmDialog';
import { Header } from '../../../shared/ui/Header';
import { Text } from '../../../shared/ui/Text';
import { ClothingForm } from '../components/ClothingForm';
import type { ClothingDraft, ClothingRecord } from '../model/clothing.types';

export type EditClothingScreenProps = {
  item: ClothingRecord | undefined;
  draft: ClothingDraft;
  showDiscardDialog: boolean;
  busy?: boolean;
  error?: string;
  onChange: (next: ClothingDraft) => void;
  onSubmit: (value: ClothingDraft) => void;
  onRequestBack: () => void;
  onConfirmDiscard: () => void;
  onCancelDiscard: () => void;
};

/**
 * Seçili kıyafet kaydını ayrı bir taslak üzerinden düzenleme ekranıdır.
 * Kaydedilmemiş değişiklikten çıkışta onay penceresini gösterir; yönlendirmeyi üst controller'a bırakır.
 */
export function EditClothingScreen({
  item,
  draft,
  showDiscardDialog,
  busy = false,
  error,
  onChange,
  onSubmit,
  onRequestBack,
  onConfirmDiscard,
  onCancelDiscard,
}: EditClothingScreenProps) {
  return (
    <SafeAreaView style={styles.screen}>
      <Header title="Kıyafeti düzenle" onBack={onRequestBack} />

      {!item ? (
        <View style={styles.notFound}>
          <Text variant="heading">Kıyafet bulunamadı</Text>
          <Text muted style={styles.centered}>
            Düzenlemek istediğin kayıt silinmiş veya geçersiz olabilir.
          </Text>
          <Button label="Geri dön" variant="secondary" onPress={onRequestBack} />
        </View>
      ) : (
        <KeyboardAvoidingView
          style={styles.flex}
          behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
        >
          <ScrollView
            keyboardShouldPersistTaps="handled"
            contentContainerStyle={styles.content}
          >
            <ClothingForm
              value={draft}
              onChange={onChange}
              onSubmit={onSubmit}
              busy={busy}
              error={error}
              submitLabel="Değişiklikleri kaydet"
            />
            <Button
              label="Vazgeç"
              variant="secondary"
              disabled={busy}
              onPress={onRequestBack}
            />
          </ScrollView>
        </KeyboardAvoidingView>
      )}

      <ConfirmDialog
        visible={showDiscardDialog}
        title="Değişikliklerden vazgeçilsin mi?"
        message="Kaydedilmemiş değişikliklerin silinecek ve önceki değerler korunacak."
        confirmLabel="Değişiklikleri bırak"
        cancelLabel="Düzenlemeye devam et"
        onConfirm={onConfirmDiscard}
        onCancel={onCancelDiscard}
      />
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: colors.background },
  flex: { flex: 1 },
  content: { padding: space.lg, gap: space.md, paddingBottom: space.xxl },
  notFound: {
    flex: 1,
    padding: space.xl,
    alignItems: 'center',
    justifyContent: 'center',
    gap: space.md,
  },
  centered: { textAlign: 'center' },
});

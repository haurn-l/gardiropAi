import { KeyboardAvoidingView, Platform, ScrollView, StyleSheet, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { colors, space } from '../../../shared/theme/tokens';
import { Button } from '../../../shared/ui/Button';
import { Header } from '../../../shared/ui/Header';
import { Text } from '../../../shared/ui/Text';
import { ClothingForm } from '../../wardrobe/components/ClothingForm';
import { GarmentImage } from '../../wardrobe/components/GarmentImage';
import type { ClothingDraft } from '../../wardrobe/model/clothing.types';

export type ClothingReviewProps = {
  imageUri?: string;
  draft: ClothingDraft;
  onChange: (next: ClothingDraft) => void;
  onSave: (value: ClothingDraft) => void;
  onRetake: () => void;
  onPickFromGallery?: () => void;
  onCancel: () => void;
  busy?: boolean;
  error?: string;
};

/**
 * Seçilen kıyafet fotoğrafını ortak ClothingForm ile birlikte onaylama ekranıdır.
 * Kullanıcı alanları kaydetmeden önce düzenleyebilir; kaydetme onayı gelmeden kayıt eklenmez.
 */
export function ClothingReview({
  imageUri,
  draft,
  onChange,
  onSave,
  onRetake,
  onPickFromGallery,
  onCancel,
  busy = false,
  error,
}: ClothingReviewProps) {
  return (
    <SafeAreaView style={styles.screen}>
      <Header title="Fotoğrafı onayla" onBack={onCancel} />
      <KeyboardAvoidingView
        style={styles.flex}
        behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
      >
        <ScrollView
          keyboardShouldPersistTaps="handled"
          contentContainerStyle={styles.content}
        >
          {imageUri ? (
            <>
              <GarmentImage imageUri={imageUri} />
              <ClothingForm value={draft} onChange={onChange} onSubmit={onSave}
                busy={busy} error={error} submitLabel="Gardıroba ekle" />
            </>
          ) : (
            <Text accessibilityLiveRegion="polite">
              {error ?? (busy ? 'Fotoğraf hazırlanıyor…' : 'Kamerayla çek veya galeriden seç.')}
            </Text>
          )}

          <View style={styles.secondaryActions}>
            <Button
              label={imageUri ? 'Tekrar çek' : 'Fotoğraf çek'}
              variant="secondary"
              icon="camera"
              disabled={busy}
              onPress={onRetake}
            />
            {onPickFromGallery ? (
              <Button label="Galeriden seç" variant="secondary" disabled={busy} onPress={onPickFromGallery} />
            ) : null}
            <Button
              label="Vazgeç"
              variant="ghost"
              disabled={busy}
              onPress={onCancel}
            />
          </View>
        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: colors.background },
  flex: { flex: 1 },
  content: { padding: space.lg, gap: space.md, paddingBottom: space.xxl },
  secondaryActions: { gap: space.sm },
});

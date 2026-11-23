import { useState } from 'react';
import { Pressable, ScrollView, StyleSheet, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { colors, radius, space } from '../../../shared/theme/tokens';
import { Button } from '../../../shared/ui/Button';
import { ConfirmDialog } from '../../../shared/ui/ConfirmDialog';
import { Header } from '../../../shared/ui/Header';
import { Icon } from '../../../shared/ui/Icon';
import { Rating } from '../../../shared/ui/Rating';
import type { RatingValue } from '../../../shared/ui/rating.types';
import { Text } from '../../../shared/ui/Text';
import { ClothingFacts } from '../components/ClothingFacts';
import { ClothingStatusControl } from '../components/ClothingStatusControl';
import { GarmentImage } from '../components/GarmentImage';
import type { ClothingRecord } from '../model/clothing.types';
import type { ClothingStatus } from '../model/clothingCard.types';

export type ClothingDetailScreenProps = {
  item: ClothingRecord | undefined;
  busy?: boolean;
  error?: string;
  onBack: () => void;
  onEdit: (id: string) => void;
  onChangeStatus: (id: string, status: ClothingStatus) => void;
  onToggleFavorite: (id: string) => void;
  onRate: (id: string, value: RatingValue | null) => void;
  onDelete: (id: string) => void;
};

// Seçili kıyafetin görsel, durum, puan ve özelliklerini gösterir; silme için açık onay ister.
export function ClothingDetailScreen({
  item, busy = false, error, onBack, onEdit, onChangeStatus, onToggleFavorite, onRate, onDelete,
}: ClothingDetailScreenProps) {
  const [confirmDelete, setConfirmDelete] = useState(false);

  return (
    <SafeAreaView style={styles.screen}>
      <Header title={item ? item.name : 'Kıyafet detayı'} onBack={onBack} />
      {!item ? (
        <View style={styles.notFound}>
          <Text variant="heading">Kıyafet bulunamadı</Text>
          <Text muted style={styles.centered}>
            Aradığın kıyafet silinmiş veya geçersiz olabilir.
          </Text>
          <Button label="Listeye dön" variant="secondary" onPress={onBack} />
        </View>
      ) : (
        <ScrollView contentContainerStyle={styles.content}>
          {error && !confirmDelete ? (
            <View style={styles.errorBox}>
              <Text variant="caption" accessibilityLiveRegion="polite" style={styles.errorText}>
                {error}
              </Text>
            </View>
          ) : null}

          <View style={styles.imageWrapper}>
            <GarmentImage imageUri={item.imageUri} />
            <Pressable
              accessibilityRole="togglebutton"
              accessibilityLabel={item.favorite ? 'Favorilerden çıkar' : 'Favorilere ekle'}
              accessibilityState={{ checked: item.favorite, disabled: busy }}
              disabled={busy}
              onPress={() => onToggleFavorite(item.id)}
              style={({ pressed }) => [
                styles.favoriteBtn,
                item.favorite && styles.favoriteActive,
                busy && styles.disabled,
                pressed && styles.pressed,
              ]}
            >
              <Icon
                name="heart"
                size={22}
                color={item.favorite ? colors.accentInk : colors.ink}
                filled={item.favorite}
              />
            </Pressable>
          </View>

          <View style={styles.section}>
            <Text variant="label">Durum</Text>
            <ClothingStatusControl
              value={item.status}
              disabled={busy}
              onChange={(status) => onChangeStatus(item.id, status)}
            />
          </View>

          <View style={styles.section}>
            <Text variant="label">Puan</Text>
            <Rating value={item.rating} disabled={busy} onChange={(v) => onRate(item.id, v)} />
          </View>

          <View style={styles.section}>
            <Text variant="label">Özellikler</Text>
            <ClothingFacts item={item} />
          </View>

          <View style={styles.actions}>
            <Button label="Düzenle" disabled={busy} onPress={() => onEdit(item.id)} />
            <Button
              label="Kıyafeti sil"
              variant="danger"
              icon="trash"
              disabled={busy}
              onPress={() => setConfirmDelete(true)}
            />
          </View>
        </ScrollView>
      )}

      <ConfirmDialog
        visible={confirmDelete && Boolean(item)}
        title="Kıyafet silinsin mi?"
        message="Bu işlem kıyafeti gardırop listesinden kaldırır."
        confirmLabel="Sil"
        busy={busy}
        error={error}
        onConfirm={() => { if (item) onDelete(item.id); }}
        onCancel={() => setConfirmDelete(false)}
      />
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: colors.background },
  content: { padding: space.lg, gap: space.lg, paddingBottom: space.xxl },
  imageWrapper: { position: 'relative' },
  favoriteBtn: {
    position: 'absolute', top: space.sm, right: space.sm, minWidth: 48, minHeight: 48,
    borderRadius: radius.full, backgroundColor: colors.surface, borderWidth: 1,
    borderColor: colors.line, alignItems: 'center', justifyContent: 'center',
  },
  favoriteActive: { backgroundColor: colors.accent, borderColor: colors.primary },
  section: { gap: space.sm },
  actions: { gap: space.sm },
  errorBox: { padding: space.md, borderRadius: radius.md, backgroundColor: colors.dangerSoft },
  errorText: { color: colors.danger },
  notFound: { flex: 1, padding: space.xl, alignItems: 'center', justifyContent: 'center', gap: space.md },
  centered: { textAlign: 'center' },
  disabled: { opacity: 0.45 },
  pressed: { opacity: 0.8 },
});

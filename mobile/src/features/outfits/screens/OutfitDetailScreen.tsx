import { useState } from 'react';
import { ScrollView, StyleSheet, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { colors, radius, space } from '../../../shared/theme/tokens';
import { Button } from '../../../shared/ui/Button';
import { ConfirmDialog } from '../../../shared/ui/ConfirmDialog';
import { Header } from '../../../shared/ui/Header';
import { Rating } from '../../../shared/ui/Rating';
import type { RatingValue } from '../../../shared/ui/rating.types';
import { Text } from '../../../shared/ui/Text';
import { OutfitItemList } from '../components/OutfitItemList';
import type { OutfitRecord } from '../model/outfit.types';
import { formatOutfitDate } from '../model/outfitDate';

export type OutfitDetailScreenProps = {
  item: OutfitRecord | undefined;
  onBack: () => void;
  onRate: (id: string, value: RatingValue | null) => void;
  onDelete: (id: string) => void;
  busy?: boolean;
  error?: string;
};

/**
 * Seçili kombin kaydının tarihini, salt okunur parça kopyalarını ve puanını gösterir.
 * Silme işlemi yalnızca açık onaydan sonra çağrılır; kayıt yoksa güvenli geri dönüş sunar.
 */
export function OutfitDetailScreen({
  item,
  onBack,
  onRate,
  onDelete,
  busy = false,
  error,
}: OutfitDetailScreenProps) {
  const [confirmDelete, setConfirmDelete] = useState(false);

  return (
    <SafeAreaView style={styles.screen}>
      <Header title={item ? item.name : 'Kombin detayı'} onBack={onBack} />

      {!item ? (
        <View style={styles.notFound}>
          <Text variant="heading">Kombin bulunamadı</Text>
          <Text muted style={styles.centered}>
            Aradığın kombin silinmiş veya geçersiz olabilir.
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

          <View style={styles.summaryCard}>
            <Text variant="heading">{item.name}</Text>
            <Text variant="caption" muted>
              {formatOutfitDate(item.createdAt)} · {item.items.length} parça
            </Text>
          </View>

          <View style={styles.section}>
            <Text variant="label">Puan</Text>
            <Rating
              value={item.rating}
              disabled={busy}
              onChange={(next) => onRate(item.id, next)}
            />
          </View>

          <View style={styles.section}>
            <Text variant="label">Kombin parçaları</Text>
            <OutfitItemList items={item.items} />
          </View>

          <Button
            label="Kombini sil"
            variant="danger"
            icon="trash"
            disabled={busy}
            onPress={() => setConfirmDelete(true)}
          />
        </ScrollView>
      )}

      <ConfirmDialog
        visible={confirmDelete && Boolean(item)}
        title="Kombin silinsin mi?"
        message="Bu işlem yalnızca kombini geçmişten kaldırır; gardıroptaki kıyafetlerin etkilenmez."
        confirmLabel="Sil"
        busy={busy}
        error={error}
        onConfirm={() => {
          if (item) {
            onDelete(item.id);
          }
        }}
        onCancel={() => setConfirmDelete(false)}
      />
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: colors.background },
  content: { padding: space.lg, gap: space.lg, paddingBottom: space.xxl },
  summaryCard: {
    padding: space.md,
    borderRadius: radius.lg,
    borderWidth: 1,
    borderColor: colors.line,
    backgroundColor: colors.surface,
    gap: space.xs,
  },
  section: { gap: space.sm },
  errorBox: { padding: space.md, borderRadius: radius.md, backgroundColor: colors.dangerSoft },
  errorText: { color: colors.danger },
  notFound: {
    flex: 1,
    padding: space.xl,
    alignItems: 'center',
    justifyContent: 'center',
    gap: space.md,
  },
  centered: { textAlign: 'center' },
});

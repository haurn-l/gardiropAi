import { useMemo, type ReactElement } from 'react';
import { ActivityIndicator, FlatList, StyleSheet, View } from 'react-native';
import { colors, radius, space } from '../../../shared/theme/tokens';
import { Button } from '../../../shared/ui/Button';
import { Text } from '../../../shared/ui/Text';
import { OutfitCard } from '../components/OutfitCard';
import { OutfitSortControl } from '../components/OutfitSortControl';
import type { OutfitRecord, OutfitSort } from '../model/outfit.types';
import { selectOutfits } from '../model/selectOutfits';

export type OutfitsScreenProps = {
  items: readonly OutfitRecord[];
  sort: OutfitSort;
  onSortChange: (next: OutfitSort) => void;
  onOpen: (id: string) => void;
  onCreateRequest: () => void;
  loading?: boolean;
  error?: string;
  onRetry?: () => void;
  header?: ReactElement;
};

function ItemSeparator() {
  return <View style={styles.separator} />;
}

/**
 * Kombin geçmişi listesini sıralama kontrolü ve yükleniyor/hata/boş durumlarıyla sunar.
 * İçinde router veya HTTP çağrısı yoktur; tüm aksiyonları üst controller'a bildirir.
 */
export function OutfitsScreen({
  items,
  sort,
  onSortChange,
  onOpen,
  onCreateRequest,
  loading = false,
  error,
  onRetry,
  header,
}: OutfitsScreenProps) {
  const sortedItems = useMemo(() => selectOutfits(items, sort), [items, sort]);
  const hasData = !loading && !error && sortedItems.length > 0;

  const listHeader =
    header || hasData ? (
      <View style={styles.headerBlock}>
        {header}
        {hasData ? (
          <View style={styles.sortSection}>
            <OutfitSortControl value={sort} onChange={onSortChange} />
            <Text variant="caption" muted accessibilityLiveRegion="polite">
              Toplam kombin: {sortedItems.length}
            </Text>
          </View>
        ) : null}
      </View>
    ) : undefined;

  let emptyContent: ReactElement;
  if (loading) {
    emptyContent = (
      <View style={styles.stateCard} accessibilityLiveRegion="polite">
        <ActivityIndicator size="large" color={colors.accentInk} />
        <Text variant="label">Kombinler yükleniyor...</Text>
      </View>
    );
  } else if (error) {
    emptyContent = (
      <View style={[styles.stateCard, styles.errorCard]} accessibilityLiveRegion="polite">
        <Text variant="heading" style={styles.errorTitle}>
          Kombinler yüklenemedi
        </Text>
        <Text muted style={styles.centered}>
          {error}
        </Text>
        {onRetry ? <Button label="Tekrar dene" onPress={onRetry} /> : null}
      </View>
    );
  } else {
    emptyContent = (
      <View style={styles.stateCard}>
        <Text variant="heading">Henüz kombin yok</Text>
        <Text muted style={styles.centered}>
          İlk kombinini oluşturduğunda geçmişin burada sıralanır.
        </Text>
        <Button label="Kombin oluştur" icon="sparkle" onPress={onCreateRequest} />
      </View>
    );
  }

  return (
    <FlatList
      data={hasData ? sortedItems : []}
      keyExtractor={(item) => item.id}
      renderItem={({ item }) => <OutfitCard item={item} onOpen={onOpen} />}
      ListHeaderComponent={listHeader}
      ListEmptyComponent={emptyContent}
      ItemSeparatorComponent={ItemSeparator}
      contentContainerStyle={styles.content}
      showsVerticalScrollIndicator={false}
    />
  );
}

const styles = StyleSheet.create({
  content: { flexGrow: 1, padding: space.lg, paddingBottom: space.xxl },
  headerBlock: { gap: space.md, marginBottom: space.md },
  sortSection: { gap: space.sm },
  separator: { height: space.md },
  stateCard: {
    flex: 1,
    minHeight: 220,
    padding: space.xl,
    borderRadius: radius.lg,
    borderWidth: 1,
    borderColor: colors.line,
    backgroundColor: colors.surface,
    alignItems: 'center',
    justifyContent: 'center',
    gap: space.md,
  },
  errorCard: { borderColor: colors.danger, backgroundColor: colors.dangerSoft },
  errorTitle: { color: colors.danger, textAlign: 'center' },
  centered: { textAlign: 'center' },
});

import { useMemo, useState } from 'react';
import { StyleSheet, View } from 'react-native';
import { router } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import { colors, space } from '../../shared/theme/tokens';
import { Button } from '../../shared/ui/Button';
import { Header } from '../../shared/ui/Header';
import { Text } from '../../shared/ui/Text';
import { WardrobeEmptyState } from '../wardrobe/components/WardrobeEmptyState';
import { WardrobeList } from '../wardrobe/components/WardrobeList';
import { WardrobeToolbar } from '../wardrobe/components/WardrobeToolbar';
import type { ClothingCardItem } from '../wardrobe/model/clothingCard.types';
import { selectClothingItems } from '../wardrobe/model/selectClothingItems';
import { defaultWardrobeFilters, type WardrobeFilters } from '../wardrobe/model/wardrobeFilters';
import { wardrobePreviewItems } from './data/wardrobePreviewItems';

/**
 * Gardırop listesini, arama/filtre akışını ve boş durum görünümlerini doğrulayan önizleme ekranıdır.
 * Tüm state burada tutulur; arama çubuğunun odağını kaybetmemesi için üst alan doğrudan React elemanı olarak verilir.
 */
export function WardrobeListPreview() {
  const [items, setItems] = useState<readonly ClothingCardItem[]>(wardrobePreviewItems);
  const [filters, setFilters] = useState<WardrobeFilters>(defaultWardrobeFilters);

  // Kategori seçenekleri filtrelenmiş sonuçtan değil tüm veri kümesinden üretilir; seçim sonrası kaybolmaz.
  const categories = useMemo(
    () => Array.from(new Set(items.map((item) => item.categoryLabel))),
    [items]
  );

  const visibleItems = useMemo(() => selectClothingItems(items, filters), [items, filters]);

  function handleOpen(_id: string) {
    router.push({ pathname: '/navigation-preview', params: { kind: 'item' } });
  }

  function handleToggleFavorite(id: string) {
    setItems((current) =>
      current.map((item) => (item.id === id ? { ...item, favorite: !item.favorite } : item))
    );
  }

  function handleToggleEmptyWardrobe() {
    setItems((current) => (current.length === 0 ? wardrobePreviewItems : []));
  }

  const listHeader = (
    <View style={styles.headerBlock}>
      <View style={styles.workshopControls}>
        <Button
          label={items.length === 0 ? 'Örnek veriyi geri yükle' : 'Tüm veriyi boşalt'}
          variant="secondary"
          onPress={handleToggleEmptyWardrobe}
        />
      </View>
      <WardrobeToolbar filters={filters} categories={categories} onChange={setFilters} />
      <Text variant="caption" muted accessibilityLiveRegion="polite">
        Gösterilen kıyafet: {visibleItems.length} / {items.length}
      </Text>
    </View>
  );

  const emptyState = (
    <WardrobeEmptyState
      kind={items.length === 0 ? 'empty-wardrobe' : 'no-matches'}
      onAddClothing={() => router.push({ pathname: '/navigation-preview', params: { kind: 'capture' } })}
      onResetFilters={() => setFilters(defaultWardrobeFilters)}
    />
  );

  return (
    <SafeAreaView style={styles.screen}>
      <Header
        title="Gardırop listesi örnekleri"
        subtitle="Görev 04 · Arama, filtreler ve FlatList"
        onBack={() => (router.canGoBack() ? router.back() : router.replace('/'))}
      />
      <WardrobeList
        items={visibleItems}
        onOpen={handleOpen}
        onToggleFavorite={handleToggleFavorite}
        header={listHeader}
        emptyState={emptyState}
      />
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: colors.background },
  headerBlock: { gap: space.md, paddingBottom: space.xs },
  workshopControls: { flexDirection: 'row', flexWrap: 'wrap', gap: space.sm },
});

import type { ReactElement } from 'react';
import { FlatList, StyleSheet, View } from 'react-native';
import { space } from '../../../shared/theme/tokens';
import type { ClothingCardItem } from '../model/clothingCard.types';
import { ClothingCard } from './ClothingCard';

export type WardrobeListProps = {
  items: readonly ClothingCardItem[];
  onOpen: (id: string) => void;
  onToggleFavorite: (id: string) => void;
  header?: ReactElement;
  emptyState?: ReactElement;
};

/**
 * Verilen kıyafet kayıtlarını iki sütunlu FlatList düzeninde görüntüler.
 * Sütun aralığı iç boşlukla verilir; tek kalan kartın genişliği de aynı kalır.
 */
export function WardrobeList({
  items,
  onOpen,
  onToggleFavorite,
  header,
  emptyState,
}: WardrobeListProps) {
  return (
    <FlatList
      data={items}
      numColumns={2}
      keyExtractor={(item) => item.id}
      keyboardShouldPersistTaps="handled"
      contentContainerStyle={styles.content}
      columnWrapperStyle={styles.row}
      ListHeaderComponent={header}
      ListEmptyComponent={emptyState}
      renderItem={({ item }) => (
        <View style={styles.columnSlot}>
          <ClothingCard item={item} onOpen={onOpen} onToggleFavorite={onToggleFavorite} />
        </View>
      )}
    />
  );
}

const styles = StyleSheet.create({
  content: {
    padding: space.lg,
    gap: space.md,
  },
  row: {
    marginHorizontal: -space.md / 2,
    alignItems: 'stretch',
  },
  columnSlot: {
    width: '50%',
    paddingHorizontal: space.md / 2,
  },
});

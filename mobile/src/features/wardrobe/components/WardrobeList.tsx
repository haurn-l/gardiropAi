import type { ReactElement } from 'react';
import { FlatList, StyleSheet, View } from 'react-native';
import { space } from '../../../shared/theme/tokens';
import type { ClothingCardItem } from '../model/clothingCard.types';
import { ClothingCard } from './ClothingCard';

export type WardrobeListProps = {
  items: readonly ClothingCardItem[];
  onOpen: (id: string) => void;
  onToggleFavorite: (id: string) => void;
  header?: ReactElement ;
  emptyState?: ReactElement;
};

/**
 * Verilen kıyafet kayıtlarını iki sütunlu FlatList düzeninde görüntüler.
 * Tek kalan son kartın iki sütun genişliğine yayılmaması için her öğe sabit sütun oranıyla sarılır.
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
    gap: space.md,
    alignItems: 'stretch',
  },
  columnSlot: {
    flex: 0.5,
  },
});

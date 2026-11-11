import type { ClothingCardItem } from './clothingCard.types';
import type { WardrobeFilters } from './wardrobeFilters';

function normalizeTurkish(value: string): string {
  return value.toLocaleLowerCase('tr-TR');
}

/**
 * Kıyafet listesini arama sorgusu, kategori, durum ve favori kriterlerine göre filtreler.
 * Girdi dizisini ve nesnelerini değiştirmez; eşleşen kayıtları orijinal sırasıyla döndürür.
 */
export function selectClothingItems(
  items: readonly ClothingCardItem[],
  filters: WardrobeFilters
): ClothingCardItem[] {
  const trimmedQuery = normalizeTurkish(filters.query.trim());

  return items.filter((item) => {
    if (filters.favoritesOnly && !item.favorite) {
      return false;
    }

    if (filters.category !== null && item.categoryLabel !== filters.category) {
      return false;
    }

    if (filters.status !== null && item.status !== filters.status) {
      return false;
    }

    if (trimmedQuery.length > 0) {
      const matchesName = normalizeTurkish(item.name).includes(trimmedQuery);
      const matchesCategory = normalizeTurkish(item.categoryLabel).includes(trimmedQuery);
      const matchesColor = normalizeTurkish(item.colorLabel).includes(trimmedQuery);

      if (!matchesName && !matchesCategory && !matchesColor) {
        return false;
      }
    }

    return true;
  });
}

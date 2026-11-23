import type { ClothingRecord } from './clothing.types';
import type { ClothingCardItem } from './clothingCard.types';
import { clothingCategoryLabels } from './clothingOptions';

/**
 * Tam kıyafet kaydını mevcut ClothingCard ve WardrobeList bileşenlerinin
 * beklediği kart görünüm modeline dönüştürür.
 */
export function toClothingCard(record: ClothingRecord): ClothingCardItem {
  return {
    id: record.id,
    name: record.name,
    ...(record.imageUri !== undefined ? { imageUri: record.imageUri } : {}),
    categoryLabel: clothingCategoryLabels[record.category],
    colorLabel: record.color,
    status: record.status,
    favorite: record.favorite,
  };
}

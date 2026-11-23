import type { RatingValue } from '../../../shared/ui/rating.types';
import type { OutfitRecord } from '../../outfits/model/outfit.types';

/**
 * Belirli bir kombinin puanını listeyi yerinde değiştirmeden günceller.
 */
export function updateOutfitRatingInList(
  outfits: readonly OutfitRecord[],
  id: string,
  rating: RatingValue | null
): OutfitRecord[] {
  return outfits.map((outfit) => (outfit.id === id ? { ...outfit, rating } : outfit));
}

/**
 * Belirli bir kombini listeden immutable biçimde çıkarır.
 */
export function removeOutfitFromList(
  outfits: readonly OutfitRecord[],
  id: string
): OutfitRecord[] {
  return outfits.filter((outfit) => outfit.id !== id);
}

/**
 * Yeni oluşturulan kombini listenin başına ekler.
 */
export function prependOutfitToList(
  outfits: readonly OutfitRecord[],
  outfit: OutfitRecord
): OutfitRecord[] {
  return [outfit, ...outfits];
}

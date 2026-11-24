import type { RatingValue } from '../../../shared/ui/rating.types';
import type { ClothingRecord } from '../../wardrobe/model/clothing.types';
import type { OutfitItemSnapshot, OutfitRecord } from './outfit.types';

/**
 * Canlı kıyafet kaydından bağımsız ve salt okunur bir parça kopyası üretir.
 * Sonradan gardıropta yapılacak değişiklikler bu kopyayı etkilemez.
 */
export function createOutfitItemSnapshot(record: ClothingRecord): OutfitItemSnapshot {
  return Object.freeze({ ...record });
}

/**
 * Kıyafet kayıtlarından bağımsız parça kopyalarıyla yeni bir kombin kaydı oluşturur.
 */
export function createOutfitRecord(params: {
  id: string;
  name: string;
  createdAt: string;
  rating: RatingValue | null;
  items: readonly ClothingRecord[];
}): OutfitRecord {
  return {
    id: params.id,
    name: params.name,
    createdAt: params.createdAt,
    rating: params.rating,
    items: Object.freeze(params.items.map(createOutfitItemSnapshot)),
  };
}

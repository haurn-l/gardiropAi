import type { RatingValue } from '../../../shared/ui/rating.types';
import type { ClothingRecord } from '../../wardrobe/model/clothing.types';

/**
 * Kombin kaydedildiği anda kıyafet kaydından alınan salt okunur parça kopyasıdır.
 * Gardıroptaki canlı kayıt değişse veya silinse bile geçmiş görünümü korur.
 */
export type OutfitItemSnapshot = Readonly<ClothingRecord>;

/**
 * Kombin geçmişi listesi ve detay ekranında kullanılan kombin kaydıdır.
 */
export type OutfitRecord = {
  id: string;
  name: string;
  createdAt: string;
  rating: RatingValue | null;
  items: readonly OutfitItemSnapshot[];
};

/**
 * Kombin geçmişi listesi için desteklenen sıralama seçenekleridir.
 */
export type OutfitSort = 'newest' | 'oldest' | 'rating';

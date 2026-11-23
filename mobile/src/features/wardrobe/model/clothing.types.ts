import type { RatingValue } from '../../../shared/ui/rating.types';
import type { ClothingStatus } from './clothingCard.types';

/**
 * Kıyafet kategorileri; sunucu sözleşmesiyle uyumlu sabit değerlerden oluşur.
 */
export type ClothingCategory =
  | 'UST_GIYIM'
  | 'ALT_GIYIM'
  | 'DIS_GIYIM'
  | 'AYAKKABI'
  | 'AKSESUAR'
  | 'EKIPMAN';

/**
 * Kıyafetin uygun olduğu mevsim bilgisidir.
 */
export type ClothingSeason = 'KIS' | 'YAZ' | 'SONBAHAR' | 'ILKBAHAR' | 'HER_MEVSIM';

/**
 * Kıyafet ekleme, fotoğraf onayı ve düzenleme formlarında düzenlenen taslak verisidir.
 */
export type ClothingDraft = {
  name: string;
  color: string;
  category: ClothingCategory;
  season: ClothingSeason;
  subCategory: string;
  hasPrint: boolean;
  usage: string;
};

/**
 * Gardırop yönetiminde kullanılan tam kıyafet kaydıdır.
 */
export type ClothingRecord = ClothingDraft & {
  id: string;
  imageUri?: string;
  status: ClothingStatus;
  favorite: boolean;
  rating: RatingValue | null;
  createdAt: string;
};

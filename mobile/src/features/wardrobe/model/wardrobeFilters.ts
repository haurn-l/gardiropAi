import type { ClothingStatus } from './clothingCard.types';

/**
 * Gardırop listesinin arama, kategori, temizlik durumu ve favori filtre sözleşmesidir.
 * null değerleri ilgili filtrede "Tümü" seçili olduğunu ifade eder.
 */
export type WardrobeFilters = {
  query: string;
  category: string | null;
  status: ClothingStatus | null;
  favoritesOnly: boolean;
};

/**
 * Filtreleri sıfırlamak ve ilk açılış durumunu kurmak için kullanılan başlangıç değeridir.
 */
export const defaultWardrobeFilters: WardrobeFilters = {
  query: '',
  category: null,
  status: null,
  favoritesOnly: false,
};

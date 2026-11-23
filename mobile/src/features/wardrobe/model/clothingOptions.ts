import type { ClothingCategory, ClothingDraft, ClothingSeason } from './clothing.types';

/**
 * Formlarda ve seçicilerde kullanılacak sıralı kategori listesi.
 */
export const clothingCategories: readonly ClothingCategory[] = [
  'UST_GIYIM',
  'ALT_GIYIM',
  'DIS_GIYIM',
  'AYAKKABI',
  'AKSESUAR',
  'EKIPMAN',
];

/**
 * Kategori değerlerinin arayüzdeki Türkçe etiket karşılıkları.
 */
export const clothingCategoryLabels: Record<ClothingCategory, string> = {
  UST_GIYIM: 'Üst Giyim',
  ALT_GIYIM: 'Alt Giyim',
  DIS_GIYIM: 'Dış Giyim',
  AYAKKABI: 'Ayakkabı',
  AKSESUAR: 'Aksesuar',
  EKIPMAN: 'Ekipman',
};

/**
 * Formlarda kullanılacak sıralı mevsim listesi.
 */
export const clothingSeasons: readonly ClothingSeason[] = [
  'KIS',
  'YAZ',
  'SONBAHAR',
  'ILKBAHAR',
  'HER_MEVSIM',
];

/**
 * Mevsim değerlerinin arayüzdeki Türkçe etiket karşılıkları.
 */
export const clothingSeasonLabels: Record<ClothingSeason, string> = {
  KIS: 'Kış',
  YAZ: 'Yaz',
  SONBAHAR: 'Sonbahar',
  ILKBAHAR: 'İlkbahar',
  HER_MEVSIM: 'Her Mevsim',
};

/**
 * Yeni kıyafet veya fotoğraf onayı başlatılırken kullanılan boş taslak şablonudur.
 */
export function createEmptyClothingDraft(): ClothingDraft {
  return {
    name: '',
    color: '',
    category: 'UST_GIYIM',
    season: 'HER_MEVSIM',
    subCategory: '',
    hasPrint: false,
    usage: '',
  };
}


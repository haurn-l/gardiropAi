import type { ClothingStatus } from './clothingCard.types';

// Görsel rozet ve ekran okuyucu aynı durum adlarını kullanır.
export const clothingStatusLabels: Record<ClothingStatus, string> = {
  TEMIZ: 'Temiz',
  KIRLI: 'Kirli',
  KULLANIM_DISI: 'Kullanım dışı',
};

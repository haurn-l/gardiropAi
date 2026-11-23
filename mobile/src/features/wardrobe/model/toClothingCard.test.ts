import { describe, expect, it } from 'vitest';
import type { ClothingRecord } from './clothing.types';
import { toClothingCard } from './toClothingCard';

describe('toClothingCard', () => {
  it('kıyafet kaydını kategori etiketi, renk, durum, favori ve id ile doğru eşler', () => {
    const record: ClothingRecord = Object.freeze({
      id: 'cl-101',
      name: 'Keten Gömlek',
      imageUri: 'https://example.com/shirt.jpg',
      category: 'UST_GIYIM',
      color: 'Ekru',
      season: 'YAZ',
      subCategory: 'Gömlek',
      hasPrint: false,
      usage: 'Günlük',
      status: 'TEMIZ',
      favorite: true,
      rating: 4,
      createdAt: '2026-11-20T10:00:00.000Z',
    });

    expect(toClothingCard(record)).toEqual({
      id: 'cl-101',
      name: 'Keten Gömlek',
      imageUri: 'https://example.com/shirt.jpg',
      categoryLabel: 'Üst Giyim',
      colorLabel: 'Ekru',
      status: 'TEMIZ',
      favorite: true,
    });
  });

  it('görsel adresi olmayan kayıtta imageUri alanını tanımlamadan dönüştürür', () => {
    const record: ClothingRecord = Object.freeze({
      id: 'cl-102',
      name: 'Koşu Ayakkabısı',
      category: 'AYAKKABI',
      color: 'Siyah',
      season: 'HER_MEVSIM',
      subCategory: 'Sneaker',
      hasPrint: true,
      usage: 'Spor',
      status: 'KIRLI',
      favorite: false,
      rating: null,
      createdAt: '2026-11-21T10:00:00.000Z',
    });

    const card = toClothingCard(record);
    expect(card).toEqual({
      id: 'cl-102',
      name: 'Koşu Ayakkabısı',
      categoryLabel: 'Ayakkabı',
      colorLabel: 'Siyah',
      status: 'KIRLI',
      favorite: false,
    });
    expect('imageUri' in card).toBe(false);
  });
});

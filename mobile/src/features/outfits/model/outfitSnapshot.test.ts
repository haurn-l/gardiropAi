import { describe, expect, it } from 'vitest';
import type { ClothingRecord } from '../../wardrobe/model/clothing.types';
import {
  patchClothingRecordInList,
  removeClothingRecordFromList,
} from '../../workshops/demo/clothingDemo.helpers';
import { createOutfitRecord } from './outfitSnapshot';

describe('outfitSnapshot kuralları', () => {
  it('kaynak kıyafet sonradan değiştirilse veya silinse bile geçmiş kombin parçaları korunur', () => {
    const shirt: ClothingRecord = {
      id: 'cl-1',
      name: 'Keten Gömlek',
      category: 'UST_GIYIM',
      color: 'Ekru',
      season: 'YAZ',
      subCategory: 'Gömlek',
      hasPrint: false,
      usage: 'Günlük',
      status: 'TEMIZ',
      favorite: true,
      rating: 5,
      createdAt: '2026-11-18T10:00:00.000Z',
    };

    let wardrobe: ClothingRecord[] = [shirt];
    const outfit = createOutfitRecord({
      id: 'out-1',
      name: 'Hafta Sonu Kombini',
      createdAt: '2026-11-20T12:00:00.000Z',
      rating: 4,
      items: [shirt],
    });

    // Canlı nesne doğrudan mutasyona uğrasa veya gardıropta güncellenip silinse bile snapshot etkilenmemeli.
    shirt.name = 'Değişen İsim';
    wardrobe = patchClothingRecordInList(wardrobe, 'cl-1', { name: 'Yeni Ad', status: 'KIRLI' });
    wardrobe = removeClothingRecordFromList(wardrobe, 'cl-1');

    expect(wardrobe).toHaveLength(0);
    expect(outfit.items).toHaveLength(1);
    expect(outfit.items[0].name).toBe('Keten Gömlek');
    expect(outfit.items[0].status).toBe('TEMIZ');
    expect(outfit.items[0]).not.toBe(shirt);
  });

  it('kombini silmek gardırop kıyafet listesini etkilemez', () => {
    const jacket: ClothingRecord = {
      id: 'cl-2',
      name: 'Deri Ceket',
      category: 'DIS_GIYIM',
      color: 'Siyah',
      season: 'SONBAHAR',
      subCategory: 'Ceket',
      hasPrint: false,
      usage: 'Akşam',
      status: 'TEMIZ',
      favorite: false,
      rating: 4,
      createdAt: '2026-11-19T10:00:00.000Z',
    };

    const wardrobe: readonly ClothingRecord[] = [jacket];
    const outfits = [
      createOutfitRecord({
        id: 'out-2',
        name: 'Akşam Kombini',
        createdAt: '2026-11-21T19:00:00.000Z',
        rating: null,
        items: wardrobe,
      }),
    ];

    const remainingOutfits = outfits.filter((o) => o.id !== 'out-2');

    expect(remainingOutfits).toHaveLength(0);
    expect(wardrobe).toHaveLength(1);
    expect(wardrobe[0].id).toBe('cl-2');
    expect(wardrobe[0].name).toBe('Deri Ceket');
  });
});

import { describe, expect, it } from 'vitest';
import type { ClothingCardItem } from './clothingCard.types';
import { selectClothingItems } from './selectClothingItems';
import { defaultWardrobeFilters, type WardrobeFilters } from './wardrobeFilters';

const sampleItems: readonly ClothingCardItem[] = Object.freeze([
  Object.freeze({
    id: 'c-1',
    name: 'İpek Gömlek',
    categoryLabel: 'Üst Giyim',
    colorLabel: 'Beyaz',
    status: 'TEMIZ',
    favorite: true,
  }),
  Object.freeze({
    id: 'c-2',
    name: 'Kışlık Kaşe Mont',
    categoryLabel: 'Dış Giyim',
    colorLabel: 'Siyah',
    status: 'KIRLI',
    favorite: false,
  }),
  Object.freeze({
    id: 'c-3',
    name: 'Ketenden Şort',
    categoryLabel: 'Alt Giyim',
    colorLabel: 'Çağla Yeşili',
    status: 'TEMIZ',
    favorite: true,
  }),
  Object.freeze({
    id: 'c-4',
    name: 'Boğazlı Yün Kazak',
    categoryLabel: 'Üst Giyim',
    colorLabel: 'İndigo',
    status: 'KULLANIM_DISI',
    favorite: false,
  }),
]);

function withFilters(overrides: Partial<WardrobeFilters>): WardrobeFilters {
  return { ...defaultWardrobeFilters, ...overrides };
}

describe('selectClothingItems', () => {
  it('varsayılan filtrelerle ve yalnızca boşluk içeren sorguyla tüm kayıtları aynı sırada döndürür', () => {
    const resultDefault = selectClothingItems(sampleItems, defaultWardrobeFilters);
    const resultWhitespace = selectClothingItems(sampleItems, withFilters({ query: '   ' }));

    expect(resultDefault.map((i) => i.id)).toEqual(['c-1', 'c-2', 'c-3', 'c-4']);
    expect(resultWhitespace.map((i) => i.id)).toEqual(['c-1', 'c-2', 'c-3', 'c-4']);
  });

  it('Türkçe büyük ve küçük harf dönüşümlerini (İ/i, I/ı, Ğ/ğ, Ş/ş, Ü/ü) doğru eşleştirir', () => {
    expect(selectClothingItems(sampleItems, withFilters({ query: '  GÖMLEK ' })).map((i) => i.id)).toEqual(['c-1']);
    expect(selectClothingItems(sampleItems, withFilters({ query: 'ipek' })).map((i) => i.id)).toEqual(['c-1']);
    expect(selectClothingItems(sampleItems, withFilters({ query: 'KIŞLIK' })).map((i) => i.id)).toEqual(['c-2']);
    expect(selectClothingItems(sampleItems, withFilters({ query: 'indigo' })).map((i) => i.id)).toEqual(['c-4']);
    expect(selectClothingItems(sampleItems, withFilters({ query: 'üst giyim' })).map((i) => i.id)).toEqual([
      'c-1',
      'c-4',
    ]);
  });

  it('kategori, durum ve yalnızca favoriler filtrelerini tek tek doğru uygular', () => {
    expect(selectClothingItems(sampleItems, withFilters({ category: 'Üst Giyim' })).map((i) => i.id)).toEqual([
      'c-1',
      'c-4',
    ]);
    expect(selectClothingItems(sampleItems, withFilters({ status: 'KIRLI' })).map((i) => i.id)).toEqual(['c-2']);
    expect(selectClothingItems(sampleItems, withFilters({ favoritesOnly: true })).map((i) => i.id)).toEqual([
      'c-1',
      'c-3',
    ]);
  });

  it('birden çok filtre seçildiğinde tüm kriterlerin kesişimini döndürür', () => {
    const combined = withFilters({
      query: 'beyaz',
      category: 'Üst Giyim',
      status: 'TEMIZ',
      favoritesOnly: true,
    });
    expect(selectClothingItems(sampleItems, combined).map((i) => i.id)).toEqual(['c-1']);
  });

  it('hiçbir kayıt eşleşmediğinde boş dizi döndürür', () => {
    const noMatch = withFilters({ query: 'Kadife Pantolon' });
    expect(selectClothingItems(sampleItems, noMatch)).toEqual([]);
  });

  it('girdi dizisini değiştirmez ve eşleşen öğelerin referanslarını korur', () => {
    const snapshot = sampleItems.map((item) => ({ ...item }));
    const result = selectClothingItems(sampleItems, withFilters({ favoritesOnly: true }));

    expect(sampleItems).toEqual(snapshot);
    expect(result[0]).toBe(sampleItems[0]);
    expect(result[1]).toBe(sampleItems[2]);
  });
});

import { describe, expect, it } from 'vitest';
import type { OutfitRecord } from './outfit.types';
import { formatOutfitDate, INVALID_OUTFIT_DATE_LABEL } from './outfitDate';
import { selectOutfits } from './selectOutfits';

function makeOutfit(
  id: string,
  createdAt: string,
  rating: OutfitRecord['rating']
): OutfitRecord {
  return Object.freeze({
    id,
    name: `Kombin ${id}`,
    createdAt,
    rating,
    items: Object.freeze([]),
  });
}

describe('selectOutfits', () => {
  const list = Object.freeze([
    makeOutfit('out-b', '2026-11-20T10:00:00.000Z', 4),
    makeOutfit('out-a', '2026-11-20T10:00:00.000Z', 4),
    makeOutfit('out-newest', '2026-11-22T09:00:00.000Z', null),
    makeOutfit('out-oldest', '2026-11-10T08:00:00.000Z', 5),
    makeOutfit('out-invalid', 'bozuk-tarih', 3),
    makeOutfit('out-null-old', '2026-11-15T12:00:00.000Z', null),
  ]);

  it('boş dizide yeni boş dizi döndürür', () => {
    const empty = Object.freeze([] as OutfitRecord[]);
    const result = selectOutfits(empty, 'newest');
    expect(result).toEqual([]);
    expect(result).not.toBe(empty);
  });

  it('newest sıralamasında en yeni tarihi başa, eşit tarihte id sırasına ve geçersiz tarihi sona alır', () => {
    const result = selectOutfits(list, 'newest');
    expect(result.map((o) => o.id)).toEqual([
      'out-newest',
      'out-a',
      'out-b',
      'out-null-old',
      'out-oldest',
      'out-invalid',
    ]);
  });

  it('oldest sıralamasında en eski tarihi başa ve geçersiz tarihi sona alır', () => {
    const result = selectOutfits(list, 'oldest');
    expect(result.map((o) => o.id)).toEqual([
      'out-oldest',
      'out-null-old',
      'out-a',
      'out-b',
      'out-newest',
      'out-invalid',
    ]);
  });

  it('rating sıralamasında 5→1, eşit puanda en yeni tarih ve puansız null değerleri en sona alır', () => {
    const result = selectOutfits(list, 'rating');
    expect(result.map((o) => o.id)).toEqual([
      'out-oldest',
      'out-a',
      'out-b',
      'out-invalid',
      'out-newest',
      'out-null-old',
    ]);
  });

  it('girdi dizisini değiştirmez ve öğe referanslarını korur', () => {
    const originalIds = list.map((o) => o.id);
    const sorted = selectOutfits(list, 'rating');

    expect(list.map((o) => o.id)).toEqual(originalIds);
    expect(sorted[0]).toBe(list[3]);
    expect(sorted[4]).toBe(list[2]);
  });

  it('geçerli ISO tarihini Türkçe biçimlendirir, geçersiz tarihte yedek metin gösterir', () => {
    expect(formatOutfitDate('2026-11-22T12:00:00.000Z')).toBe('22 Kasım 2026');
    expect(formatOutfitDate('gecersiz-tarih')).toBe(INVALID_OUTFIT_DATE_LABEL);
    expect(formatOutfitDate('')).toBe(INVALID_OUTFIT_DATE_LABEL);
  });
});

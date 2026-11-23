import type { OutfitRecord, OutfitSort } from './outfit.types';
import { parseOutfitTimestamp } from './outfitDate';

function compareId(a: OutfitRecord, b: OutfitRecord): number {
  if (a.id === b.id) {
    return 0;
  }
  return a.id < b.id ? -1 : 1;
}

function compareDate(
  a: OutfitRecord,
  b: OutfitRecord,
  direction: 'newest' | 'oldest'
): number {
  const timeA = parseOutfitTimestamp(a.createdAt);
  const timeB = parseOutfitTimestamp(b.createdAt);

  if (timeA === null && timeB === null) {
    return compareId(a, b);
  }
  if (timeA === null) {
    return 1;
  }
  if (timeB === null) {
    return -1;
  }
  if (timeA === timeB) {
    return compareId(a, b);
  }
  return direction === 'newest' ? timeB - timeA : timeA - timeB;
}

function compareByRating(a: OutfitRecord, b: OutfitRecord): number {
  if (a.rating === null && b.rating === null) {
    return compareDate(a, b, 'newest');
  }
  if (a.rating === null) {
    return 1;
  }
  if (b.rating === null) {
    return -1;
  }
  if (a.rating !== b.rating) {
    return b.rating - a.rating;
  }
  return compareDate(a, b, 'newest');
}

/**
 * Kombin listesini seçilen sıraya göre yeni bir dizi olarak döndürür.
 * Girdi dizisini değiştirmez; geçersiz tarihli ve puansız kayıtları ilgili sıranın sonuna taşır.
 */
export function selectOutfits(
  items: readonly OutfitRecord[],
  sort: OutfitSort
): OutfitRecord[] {
  const copy = [...items];

  copy.sort((a, b) => {
    if (sort === 'oldest') {
      return compareDate(a, b, 'oldest');
    }
    if (sort === 'rating') {
      return compareByRating(a, b);
    }
    return compareDate(a, b, 'newest');
  });

  return copy;
}

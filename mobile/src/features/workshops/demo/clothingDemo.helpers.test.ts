import { describe, expect, it } from 'vitest';
import type { ClothingRecord } from '../../wardrobe/model/clothing.types';
import {
  buildNewClothingRecord,
  isClothingDraftDirty,
  patchClothingRecordInList,
  recordToClothingDraft,
  removeClothingRecordFromList,
} from './clothingDemo.helpers';

const sampleRecord: ClothingRecord = Object.freeze({
  id: 'cl-1',
  name: 'Keten Gömlek',
  imageUri: 'https://example.com/a.jpg',
  category: 'UST_GIYIM',
  color: 'Ekru',
  season: 'YAZ',
  subCategory: 'Gömlek',
  hasPrint: false,
  usage: 'Günlük',
  status: 'TEMIZ',
  favorite: false,
  rating: 4,
  createdAt: '2026-11-20T10:00:00.000Z',
});

describe('clothingDemo.helpers', () => {
  it('taslak değişiklik kontrolünü doğru yapar', () => {
    const draft = recordToClothingDraft(sampleRecord);
    expect(isClothingDraftDirty(sampleRecord, draft)).toBe(false);
    expect(isClothingDraftDirty(sampleRecord, { ...draft, color: 'Beyaz' })).toBe(true);
  });

  it('yeni kıyafet kaydını varsayılan durum ve puansız olarak üretir', () => {
    const draft = recordToClothingDraft(sampleRecord);
    const created = buildNewClothingRecord(
      'cl-99',
      draft,
      'https://example.com/new.jpg',
      '2026-11-22T12:00:00.000Z'
    );

    expect(created).toEqual({
      ...draft,
      id: 'cl-99',
      imageUri: 'https://example.com/new.jpg',
      status: 'TEMIZ',
      favorite: false,
      rating: null,
      createdAt: '2026-11-22T12:00:00.000Z',
    });
  });

  it('güncelleme ve silme işlemlerinde yalnızca hedef kaydı değiştirir ve girdiyi bozmaz', () => {
    const second: ClothingRecord = Object.freeze({
      ...sampleRecord,
      id: 'cl-2',
      name: 'Deri Ceket',
    });
    const list = Object.freeze([sampleRecord, second]);

    const updated = patchClothingRecordInList(list, 'cl-1', { favorite: true, rating: null });
    expect(updated[0].favorite).toBe(true);
    expect(updated[0].rating).toBeNull();
    expect(updated[1]).toEqual(second);
    expect(list[0].favorite).toBe(false);

    const remaining = removeClothingRecordFromList(list, 'cl-1');
    expect(remaining.map((item) => item.id)).toEqual(['cl-2']);
    expect(list.length).toBe(2);
  });
});

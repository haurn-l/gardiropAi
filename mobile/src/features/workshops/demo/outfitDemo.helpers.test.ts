import { describe, expect, it } from 'vitest';
import type { OutfitRecord } from '../../outfits/model/outfit.types';
import {
  prependOutfitToList,
  removeOutfitFromList,
  updateOutfitRatingInList,
} from './outfitDemo.helpers';

const first: OutfitRecord = Object.freeze({
  id: 'out-1',
  name: 'Ofis Kombini',
  createdAt: '2026-11-20T10:00:00.000Z',
  rating: 3,
  items: Object.freeze([]),
});

const second: OutfitRecord = Object.freeze({
  id: 'out-2',
  name: 'Hafta Sonu',
  createdAt: '2026-11-21T10:00:00.000Z',
  rating: null,
  items: Object.freeze([]),
});

describe('outfitDemo.helpers', () => {
  it('puan güncellemede yalnızca hedef kombini değiştirir ve girdiyi korur', () => {
    const list = Object.freeze([first, second]);
    const updated = updateOutfitRatingInList(list, 'out-1', 5);

    expect(updated[0].rating).toBe(5);
    expect(updated[1]).toBe(second);
    expect(list[0].rating).toBe(3);

    const cleared = updateOutfitRatingInList(updated, 'out-1', null);
    expect(cleared[0].rating).toBeNull();
  });

  it('kombin silme ve ekleme işlemlerini immutable biçimde uygular', () => {
    const list = Object.freeze([first, second]);
    const remaining = removeOutfitFromList(list, 'out-1');

    expect(remaining.map((o) => o.id)).toEqual(['out-2']);
    expect(list).toHaveLength(2);

    const created: OutfitRecord = Object.freeze({
      id: 'out-3',
      name: 'Yeni Kombin',
      createdAt: '2026-11-22T12:00:00.000Z',
      rating: null,
      items: Object.freeze([]),
    });
    const added = prependOutfitToList(remaining, created);

    expect(added.map((o) => o.id)).toEqual(['out-3', 'out-2']);
  });
});

import { describe, expect, it } from 'vitest';
import type { ClothingRecord } from '../../wardrobe/model/clothing.types';
import { buildLocalChatReply, createLocalChatPort } from './localChatPort';

function makeItem(
  id: string,
  category: ClothingRecord['category'],
  status: ClothingRecord['status'] = 'TEMIZ'
): ClothingRecord {
  return Object.freeze({
    id,
    name: `Parça ${id}`,
    category,
    color: 'Siyah',
    season: 'SONBAHAR',
    subCategory: 'Temel',
    hasPrint: false,
    usage: 'Günlük',
    status,
    favorite: false,
    rating: null,
    createdAt: '2026-11-20T10:00:00.000Z',
  });
}

describe('localChatPort', () => {
  const wardrobe: readonly ClothingRecord[] = Object.freeze([
    makeItem('c1', 'UST_GIYIM', 'TEMIZ'),
    makeItem('c2', 'ALT_GIYIM', 'TEMIZ'),
    makeItem('c3', 'DIS_GIYIM', 'TEMIZ'),
    makeItem('c4', 'UST_GIYIM', 'KIRLI'),
    makeItem('c5', 'AYAKKABI', 'KULLANIM_DISI'),
    makeItem('c6', 'ALT_GIYIM', 'TEMIZ'),
    makeItem('c7', 'DIS_GIYIM', 'TEMIZ'),
  ]);

  it('yalnızca TEMIZ parçaları seçer ve kirli/kullanım dışı parçaları dışlar', () => {
    const reply = buildLocalChatReply(
      { conversationId: 'conv-1', prompt: 'Ofis kombini', wardrobe },
      'sug-1'
    );

    expect(reply.suggestion).toBeDefined();
    const ids = reply.suggestion?.items.map((item) => item.id) ?? [];
    expect(ids).not.toContain('c4');
    expect(ids).not.toContain('c5');
    expect(ids.length).toBe(3);
  });

  it('temiz kıyafet yoksa öneri kartı olmadan bilgilendirme metni döner', () => {
    const dirtyOnly = [makeItem('d1', 'UST_GIYIM', 'KIRLI')];
    const reply = buildLocalChatReply(
      { conversationId: 'conv-1', prompt: 'Akşam kombini', wardrobe: dirtyOnly },
      'sug-2'
    );

    expect(reply.suggestion).toBeUndefined();
    expect(reply.text.length).toBeGreaterThan(0);
  });

  it('yenilemede sabitlenen parçaları korur ve diğer parçaları mümkünse değiştirir', () => {
    const reply = buildLocalChatReply(
      {
        conversationId: 'conv-1',
        prompt: 'Ofis kombini',
        wardrobe,
        pinnedItemIds: ['c1'],
        previousItemIds: ['c1', 'c2', 'c3'],
      },
      'sug-3'
    );

    const ids = reply.suggestion?.items.map((item) => item.id) ?? [];
    expect(ids).toContain('c1');
    expect(reply.suggestion?.pinnedItemIds).toEqual(['c1']);
    expect(ids).toContain('c6');
    expect(ids).toContain('c7');
  });

  it('hata simülasyonu açıkken createLocalChatPort hata fırlatır', async () => {
    const port = createLocalChatPort({
      getSimulateError: () => true,
      nextSuggestionId: () => 'sug-err',
      delayMs: 0,
    });

    await expect(
      port.sendMessage({ conversationId: 'conv-1', prompt: 'Test', wardrobe })
    ).rejects.toThrow();
  });
});

import { describe, expect, it } from 'vitest';
import type { ClothingRecord } from '../../wardrobe/model/clothing.types';
import type { ConversationRecord } from './chat.types';
import {
  canApproveSuggestion,
  deriveConversationTitle,
  MAX_CHAT_PROMPT_LENGTH,
  selectEligibleWardrobe,
  sortConversationsByUpdated,
  validateChatPrompt,
} from './chatHelpers';

function makeClothing(id: string, status: ClothingRecord['status']): ClothingRecord {
  return Object.freeze({
    id,
    name: `Parça ${id}`,
    category: 'UST_GIYIM',
    color: 'Siyah',
    season: 'ILKBAHAR',
    subCategory: 'Gömlek',
    hasPrint: false,
    usage: 'Günlük',
    status,
    favorite: false,
    rating: null,
    createdAt: '2026-11-20T10:00:00.000Z',
  });
}

describe('chatHelpers', () => {
  it('boş veya sınır üstü mesajları reddeder, geçerli mesajı kırpar', () => {
    expect(validateChatPrompt('   ').ok).toBe(false);
    expect(validateChatPrompt('a'.repeat(MAX_CHAT_PROMPT_LENGTH + 1)).ok).toBe(false);
    expect(validateChatPrompt('  Akşam yemeği için öneri  ')).toEqual({
      ok: true,
      text: 'Akşam yemeği için öneri',
    });
  });

  it('öneri havuzuna yalnızca TEMIZ kıyafetleri alır ve girdiyi değiştirmez', () => {
    const wardrobe = Object.freeze([
      makeClothing('c1', 'TEMIZ'),
      makeClothing('c2', 'KIRLI'),
      makeClothing('c3', 'KULLANIM_DISI'),
      makeClothing('c4', 'TEMIZ'),
    ]);

    const eligible = selectEligibleWardrobe(wardrobe);

    expect(eligible.map((item) => item.id)).toEqual(['c1', 'c4']);
    expect(wardrobe).toHaveLength(4);
  });

  it('ilk mesajdan kısa ve temiz sohbet başlığı türetir', () => {
    expect(deriveConversationTitle('   ')).toBe('Yeni sohbet');
    expect(deriveConversationTitle('Yağmurlu   gün   kombini')).toBe('Yağmurlu gün kombini');
    const longTitle = deriveConversationTitle('A'.repeat(70));
    expect(longTitle.length).toBeLessThanOrEqual(48);
    expect(longTitle.endsWith('…')).toBe(true);
  });

  it('onaylanmamış ve parçalı öneri için onay izni verir, onaylı veya boş öneriyi engeller', () => {
    const piece = makeClothing('c1', 'TEMIZ');
    expect(
      canApproveSuggestion({
        id: 'sug-1',
        title: 'Öneri',
        reason: 'Uygun',
        items: [piece],
        pinnedItemIds: [],
        approvedOutfitId: null,
        feedback: null,
      })
    ).toBe(true);

    expect(
      canApproveSuggestion({
        id: 'sug-2',
        title: 'Öneri',
        reason: 'Uygun',
        items: [piece],
        pinnedItemIds: [],
        approvedOutfitId: 'out-99',
        feedback: null,
      })
    ).toBe(false);

    expect(
      canApproveSuggestion({
        id: 'sug-3',
        title: 'Boş',
        reason: 'Parça yok',
        items: [],
        pinnedItemIds: [],
        approvedOutfitId: null,
        feedback: null,
      })
    ).toBe(false);
  });

  it('sohbetleri son güncellemeden eskiye sıralar, geçersiz tarihi sona alır', () => {
    const list: readonly ConversationRecord[] = Object.freeze([
      { id: 'conv-b', title: 'B', updatedAt: '2026-11-20T10:00:00.000Z', messages: [] },
      { id: 'conv-a', title: 'A', updatedAt: '2026-11-20T10:00:00.000Z', messages: [] },
      { id: 'conv-invalid', title: 'X', updatedAt: 'bozuk', messages: [] },
      { id: 'conv-new', title: 'Yeni', updatedAt: '2026-11-22T18:00:00.000Z', messages: [] },
    ]);

    const sorted = sortConversationsByUpdated(list);

    expect(sorted.map((c) => c.id)).toEqual(['conv-new', 'conv-a', 'conv-b', 'conv-invalid']);
    expect(list.map((c) => c.id)).toEqual(['conv-b', 'conv-a', 'conv-invalid', 'conv-new']);
  });
});

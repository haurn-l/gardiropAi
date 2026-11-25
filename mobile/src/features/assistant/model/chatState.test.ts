import { describe, expect, it } from 'vitest';
import type { ClothingRecord } from '../../wardrobe/model/clothing.types';
import type { ChatMessage } from './chat.types';
import {
  appendPendingUserMessage,
  markMessageFailed,
  markMessageRetrying,
  markSuggestionApprovedInMessages,
  resolveUserMessageWithReply,
  setSuggestionFeedbackInMessages,
  toggleSuggestionPinInMessages,
} from './chatState';

const samplePiece: ClothingRecord = Object.freeze({
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
});

const assistantWithSuggestion: ChatMessage = Object.freeze({
  id: 'msg-2',
  sender: 'assistant',
  text: 'Bugün için hafif bir kombin hazırladım.',
  createdAt: '2026-11-22T10:01:00.000Z',
  status: 'sent',
  suggestion: Object.freeze({
    id: 'sug-1',
    title: 'Hafif Günlük Kombin',
    reason: 'Temiz parçalarından mevsime uygun seçildi.',
    items: Object.freeze([samplePiece]),
    pinnedItemIds: Object.freeze([]),
    approvedOutfitId: null,
    feedback: null,
  }),
});

describe('chatState geçişleri', () => {
  it('gönderim -> hata -> tekrar dene -> yanıt yaşam döngüsünü immutable yönetir', () => {
    const initial: readonly ChatMessage[] = Object.freeze([]);
    const userMsg: ChatMessage = {
      id: 'msg-1',
      sender: 'user',
      text: 'Bugün ne giysem?',
      createdAt: '2026-11-22T10:00:00.000Z',
      status: 'sending',
    };

    const pending = appendPendingUserMessage(initial, userMsg);
    expect(pending[0].status).toBe('sending');
    expect(initial).toHaveLength(0);

    const failed = markMessageFailed(pending, 'msg-1', 'Bağlantı hatası');
    expect(failed[0].status).toBe('error');
    expect(failed[0].errorText).toBe('Bağlantı hatası');

    const retrying = markMessageRetrying(failed, 'msg-1');
    expect(retrying[0].status).toBe('sending');
    expect(retrying[0].errorText).toBeUndefined();

    const resolved = resolveUserMessageWithReply(retrying, 'msg-1', assistantWithSuggestion);
    expect(resolved).toHaveLength(2);
    expect(resolved[0].status).toBe('sent');
    expect(resolved[1].id).toBe('msg-2');
  });

  it('yalnızca önerideki parçaları sabitler ve tekrar basınca kaldırır', () => {
    const list = Object.freeze([assistantWithSuggestion]);

    const pinned = toggleSuggestionPinInMessages(list, 'msg-2', 'cl-1');
    expect(pinned[0].suggestion?.pinnedItemIds).toEqual(['cl-1']);
    expect(list[0].suggestion?.pinnedItemIds).toEqual([]);

    const ignored = toggleSuggestionPinInMessages(pinned, 'msg-2', 'olmayan-id');
    expect(ignored[0].suggestion?.pinnedItemIds).toEqual(['cl-1']);

    const unpinned = toggleSuggestionPinInMessages(pinned, 'msg-2', 'cl-1');
    expect(unpinned[0].suggestion?.pinnedItemIds).toEqual([]);
  });

  it('tekil onay kuralını uygular: onaylı öneri ikinci kez değiştirilmez', () => {
    const list = Object.freeze([assistantWithSuggestion]);
    const approved = markSuggestionApprovedInMessages(list, 'msg-2', 'out-101');
    expect(approved[0].suggestion?.approvedOutfitId).toBe('out-101');

    const secondAttempt = markSuggestionApprovedInMessages(approved, 'msg-2', 'out-202');
    expect(secondAttempt[0].suggestion?.approvedOutfitId).toBe('out-101');
  });

  it('öneri geri bildirimini değiştirir ve aynı seçime basınca temizler', () => {
    const list = Object.freeze([assistantWithSuggestion]);
    const liked = setSuggestionFeedbackInMessages(list, 'msg-2', 'like');
    expect(liked[0].suggestion?.feedback).toBe('like');

    const cleared = setSuggestionFeedbackInMessages(liked, 'msg-2', 'like');
    expect(cleared[0].suggestion?.feedback).toBeNull();

    const disliked = setSuggestionFeedbackInMessages(cleared, 'msg-2', 'dislike');
    expect(disliked[0].suggestion?.feedback).toBe('dislike');
  });
});

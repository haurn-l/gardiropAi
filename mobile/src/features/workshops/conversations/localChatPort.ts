import type { ChatPort, ChatReplyRequest, ChatReplyResult } from '../../assistant/model/chat.types';
import { deriveConversationTitle, selectEligibleWardrobe } from '../../assistant/model/chatHelpers';
import { createOutfitItemSnapshot } from '../../outfits/model/outfitSnapshot';
import type { ClothingRecord } from '../../wardrobe/model/clothing.types';

const MAX_SUGGESTION_ITEMS = 3;

function pickSuggestionItems(
  eligible: readonly ClothingRecord[],
  pinnedIds: readonly string[],
  previousIds: readonly string[]
): ClothingRecord[] {
  const pinnedSet = new Set(pinnedIds);
  const previousSet = new Set(previousIds);
  const pinned = eligible.filter((item) => pinnedSet.has(item.id));
  const unpinned = eligible.filter((item) => !pinnedSet.has(item.id));

  // Yenilemede önce önceki öneride olmayan temiz parçaları tercih et.
  const freshFirst = [
    ...unpinned.filter((item) => !previousSet.has(item.id)),
    ...unpinned.filter((item) => previousSet.has(item.id)),
  ];

  const picked: ClothingRecord[] = [...pinned];
  const usedCategories = new Set(picked.map((item) => item.category));

  for (const candidate of freshFirst) {
    if (picked.length >= MAX_SUGGESTION_ITEMS) {
      break;
    }
    if (!usedCategories.has(candidate.category)) {
      picked.push(candidate);
      usedCategories.add(candidate.category);
    }
  }

  for (const candidate of freshFirst) {
    if (picked.length >= MAX_SUGGESTION_ITEMS) {
      break;
    }
    if (!picked.some((item) => item.id === candidate.id)) {
      picked.push(candidate);
    }
  }

  return picked;
}

/**
 * İstek ve gardırop verisine göre deterministik yerel kombin yanıtı üretir.
 */
export function buildLocalChatReply(
  request: ChatReplyRequest,
  suggestionId: string
): ChatReplyResult {
  const eligible = selectEligibleWardrobe(request.wardrobe);
  if (eligible.length === 0) {
    return {
      text: 'Gardırobunda şu an temiz durumda kıyafet bulunamadı. Kıyafet durumlarını güncelleyip tekrar deneyebilirsin.',
    };
  }

  const pinnedIds = request.pinnedItemIds ?? [];
  const previousIds = request.previousItemIds ?? [];
  const picked = pickSuggestionItems(eligible, pinnedIds, previousIds);
  const validPinned = pinnedIds.filter((id) => picked.some((item) => item.id === id));
  const title = deriveConversationTitle(request.prompt, 'Günlük kombin');

  const reason =
    validPinned.length > 0
      ? `Sabitlediğin ${validPinned.length} parça korunarak temiz kıyafetlerinden yenilendi.`
      : 'Gardırobundaki temiz parçalar kategori dengesine göre seçildi.';

  return {
    text:
      validPinned.length > 0
        ? 'Sabitlediğin parçaları koruyarak yeni bir kombin hazırladım:'
        : 'İsteğine göre temiz kıyafetlerinden şu kombini öneriyorum:',
    suggestion: {
      id: suggestionId,
      title,
      reason,
      items: picked.map(createOutfitItemSnapshot),
      pinnedItemIds: validPinned,
    },
  };
}

/**
 * Örnek akış için ağ çağrısı yapmayan yerel ChatPort uygulamasını oluşturur.
 */
export function createLocalChatPort(options: {
  getSimulateError: () => boolean;
  nextSuggestionId: () => string;
  delayMs?: number;
}): ChatPort {
  const delayMs = options.delayMs ?? 220;

  return {
    async sendMessage(request: ChatReplyRequest): Promise<ChatReplyResult> {
      await new Promise((resolve) => setTimeout(resolve, delayMs));
      if (options.getSimulateError()) {
        throw new Error('Asistan yanıtı alınamadı. Lütfen tekrar dene.');
      }
      return buildLocalChatReply(request, options.nextSuggestionId());
    },
  };
}

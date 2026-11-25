import type { ClothingRecord } from '../../wardrobe/model/clothing.types';
import type { ConversationRecord, OutfitSuggestionDraft } from './chat.types';

export const MAX_CHAT_PROMPT_LENGTH = 500;
const MAX_TITLE_LENGTH = 48;

export type PromptValidationResult =
  | { ok: true; text: string }
  | { ok: false; error: string };

/**
 * Kullanıcı mesajını kırpar; boş veya sınır üstü metinleri reddeder.
 */
export function validateChatPrompt(raw: string): PromptValidationResult {
  const text = raw.trim();
  if (text.length === 0) {
    return { ok: false, error: 'Göndermek için bir mesaj yaz.' };
  }
  if (text.length > MAX_CHAT_PROMPT_LENGTH) {
    return {
      ok: false,
      error: `Mesaj en fazla ${MAX_CHAT_PROMPT_LENGTH} karakter olabilir.`,
    };
  }
  return { ok: true, text };
}

/**
 * Kombin önerisinde kullanılabilecek yalnızca temiz durumdaki kıyafetleri döndürür.
 * Kirli veya kullanım dışı parçalar öneri havuzuna alınmaz.
 */
export function selectEligibleWardrobe(
  wardrobe: readonly ClothingRecord[]
): ClothingRecord[] {
  return wardrobe.filter((item) => item.status === 'TEMIZ');
}

/**
 * İlk kullanıcı mesajından kısa ve okunaklı bir sohbet başlığı türetir.
 */
export function deriveConversationTitle(prompt: string, fallback = 'Yeni sohbet'): string {
  const cleaned = prompt.trim().replace(/\s+/g, ' ');
  if (cleaned.length === 0) {
    return fallback;
  }
  if (cleaned.length <= MAX_TITLE_LENGTH) {
    return cleaned;
  }
  return `${cleaned.slice(0, MAX_TITLE_LENGTH - 1).trimEnd()}…`;
}

/**
 * Önerinin kombin geçmişine kaydedilmeye uygun olup olmadığını belirler.
 * Zaten onaylanmış veya parçasız önerilerin yeniden kaydedilmesini önler.
 */
export function canApproveSuggestion(
  suggestion: OutfitSuggestionDraft | undefined
): boolean {
  return Boolean(
    suggestion && suggestion.approvedOutfitId === null && suggestion.items.length > 0
  );
}

function parseTimestamp(iso: string): number | null {
  if (typeof iso !== 'string' || iso.trim().length === 0) {
    return null;
  }
  const time = new Date(iso).getTime();
  return Number.isNaN(time) ? null : time;
}

/**
 * Sohbet geçmişini en son güncellenenden eskiye doğru yeni bir dizi olarak sıralar.
 * Geçersiz tarihleri sona taşır; eşitlikte id sırasıyla kararlı sonuç verir.
 */
export function sortConversationsByUpdated(
  conversations: readonly ConversationRecord[]
): ConversationRecord[] {
  return [...conversations].sort((a, b) => {
    const timeA = parseTimestamp(a.updatedAt);
    const timeB = parseTimestamp(b.updatedAt);

    if (timeA === null && timeB === null) {
      return a.id < b.id ? -1 : a.id > b.id ? 1 : 0;
    }
    if (timeA === null) {
      return 1;
    }
    if (timeB === null) {
      return -1;
    }
    if (timeA !== timeB) {
      return timeB - timeA;
    }
    return a.id < b.id ? -1 : a.id > b.id ? 1 : 0;
  });
}

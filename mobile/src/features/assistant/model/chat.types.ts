import type { OutfitItemSnapshot } from '../../outfits/model/outfit.types';
import type { ClothingRecord } from '../../wardrobe/model/clothing.types';

export type MessageSender = 'user' | 'assistant';

export type MessageStatus = 'sending' | 'sent' | 'error';

export type SuggestionFeedback = 'like' | 'dislike' | null;

/**
 * Asistanın bir sohbet yanıtında sunduğu kombin önerisidir.
 * Onaylandığında oluşan kombin kimliği kaydedilerek ikinci kez eklenmesi engellenir.
 */
export type OutfitSuggestionDraft = {
  id: string;
  title: string;
  reason: string;
  items: readonly OutfitItemSnapshot[];
  pinnedItemIds: readonly string[];
  approvedOutfitId: string | null;
  feedback: SuggestionFeedback;
};

/**
 * Sohbet akışındaki tek bir kullanıcı veya asistan mesajıdır.
 */
export type ChatMessage = {
  id: string;
  sender: MessageSender;
  text: string;
  createdAt: string;
  status: MessageStatus;
  errorText?: string;
  suggestion?: OutfitSuggestionDraft;
};

/**
 * Sohbet geçmişi listesi ve aktif konuşma ekranında kullanılan sohbet kaydıdır.
 */
export type ConversationRecord = {
  id: string;
  title: string;
  updatedAt: string;
  messages: readonly ChatMessage[];
};

export type ChatReplyRequest = {
  conversationId: string;
  prompt: string;
  wardrobe: readonly ClothingRecord[];
  pinnedItemIds?: readonly string[];
  previousItemIds?: readonly string[];
};

export type ChatReplyResult = {
  text: string;
  suggestion?: Omit<OutfitSuggestionDraft, 'approvedOutfitId' | 'feedback'>;
};

/**
 * Sohbet yanıtı üreten yerel veya uzak servisler için ortak sözleşmedir.
 * Ekranlar ve controller'lar doğrudan HTTP çağırmak yerine bu arayüzü kullanır.
 */
export type ChatPort = {
  sendMessage: (request: ChatReplyRequest) => Promise<ChatReplyResult>;
};

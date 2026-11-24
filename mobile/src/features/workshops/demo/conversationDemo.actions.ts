import type { ChatReplyResult, ConversationRecord } from '../../assistant/model/chat.types';
import { canApproveSuggestion, validateChatPrompt } from '../../assistant/model/chatHelpers';
import {
  appendPendingUserMessage, markMessageFailed, markMessageRetrying,
  markSuggestionApprovedInMessages, resolveUserMessageWithReply,
} from '../../assistant/model/chatState';
import type { OutfitRecord } from '../../outfits/model/outfit.types';
import { createOutfitRecord } from '../../outfits/model/outfitSnapshot';
import type { ClothingRecord } from '../../wardrobe/model/clothing.types';
import { createLocalChatPort } from '../conversations/localChatPort';
import {
  applyPromptTitleIfDefault, buildAssistantMessage,
  conversationSession, updateConversationInList,
} from './conversationDemo.helpers';

const chatPort = createLocalChatPort({
  getSimulateError: () => conversationSession.simulateError,
  nextSuggestionId: () => `sug-${conversationSession.nextSug++}`,
});

type AsyncActionDeps = {
  wardrobe: readonly ClothingRecord[];
  addOutfit: (outfit: OutfitRecord) => void;
  commit: (next: readonly ConversationRecord[]) => void;
};

function findMessage(conversationId: string, messageId: string) {
  return conversationSession.conversations
    .find((conv) => conv.id === conversationId)
    ?.messages.find((msg) => msg.id === messageId);
}

/** Oturumluk sohbet akışının asenkron gönderim, yenileme ve kombin onay işlemlerini üretir. */
export function createConversationAsyncActions({ wardrobe, addOutfit, commit }: AsyncActionDeps) {
  const patchConv = (id: string, fn: (c: ConversationRecord) => ConversationRecord) => {
    commit(updateConversationInList(conversationSession.conversations, id, fn));
  };

  function appendReply(conversationId: string, reply: ChatReplyResult, userMsgId?: string) {
    const now = new Date().toISOString();
    const replyMsg = buildAssistantMessage(`msg-${conversationSession.nextMsg++}`, reply, now);
    patchConv(conversationId, (conv) => ({
      ...conv,
      updatedAt: now,
      messages: userMsgId
        ? resolveUserMessageWithReply(conv.messages, userMsgId, replyMsg)
        : [...conv.messages, replyMsg],
    }));
  }

  async function deliverPrompt(conversationId: string, userMsgId: string, prompt: string) {
    try {
      const reply = await chatPort.sendMessage({ conversationId, prompt, wardrobe });
      appendReply(conversationId, reply, userMsgId);
    } catch (err) {
      const reason = err instanceof Error ? err.message : 'Mesaj gönderilemedi.';
      patchConv(conversationId, (conv) => ({
        ...conv,
        messages: markMessageFailed(conv.messages, userMsgId, reason),
      }));
    }
  }

  async function sendMessage(conversationId: string, rawPrompt: string) {
    const validated = validateChatPrompt(rawPrompt);
    if (!validated.ok) {
      throw new Error(validated.error);
    }
    const now = new Date().toISOString();
    const userMsgId = `msg-${conversationSession.nextMsg++}`;
    const pending = {
      id: userMsgId, sender: 'user' as const, text: validated.text,
      createdAt: now, status: 'sending' as const,
    };
    patchConv(conversationId, (conv) => ({
      ...conv,
      title: applyPromptTitleIfDefault(conv, validated.text),
      updatedAt: now,
      messages: appendPendingUserMessage(conv.messages, pending),
    }));
    await deliverPrompt(conversationId, userMsgId, validated.text);
  }

  async function retryMessage(conversationId: string, messageId: string) {
    const target = findMessage(conversationId, messageId);
    if (!target || target.status !== 'error') {
      return;
    }
    patchConv(conversationId, (conv) => ({
      ...conv,
      messages: markMessageRetrying(conv.messages, messageId),
    }));
    await deliverPrompt(conversationId, messageId, target.text);
  }

  async function regenerateSuggestion(conversationId: string, messageId: string) {
    const source = findMessage(conversationId, messageId)?.suggestion;
    if (!source) {
      return;
    }
    const reply = await chatPort.sendMessage({
      conversationId,
      prompt: source.title,
      wardrobe,
      pinnedItemIds: source.pinnedItemIds,
      previousItemIds: source.items.map((item) => item.id),
    });
    appendReply(conversationId, reply);
  }

  async function approveSuggestion(conversationId: string, messageId: string): Promise<OutfitRecord> {
    await new Promise((resolve) => setTimeout(resolve, 140));
    if (conversationSession.simulateError) {
      throw new Error('Kombin onaylanamadı. Lütfen tekrar dene.');
    }
    const source = findMessage(conversationId, messageId)?.suggestion;
    if (!source || !canApproveSuggestion(source)) {
      throw new Error('Bu öneri zaten onaylanmış veya parça içermiyor.');
    }
    const items = source.items.map((item) => ({ ...item }));
    const created = createOutfitRecord({
      id: `out-chat-${conversationSession.nextOutfit++}`,
      name: source.title, createdAt: new Date().toISOString(), rating: null, items,
    });
    addOutfit(created);
    patchConv(conversationId, (conv) => ({
      ...conv,
      messages: markSuggestionApprovedInMessages(conv.messages, messageId, created.id),
    }));
    return created;
  }

  return { sendMessage, retryMessage, regenerateSuggestion, approveSuggestion };
}

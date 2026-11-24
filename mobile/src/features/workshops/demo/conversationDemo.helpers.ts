import type {
  ChatMessage,
  ChatReplyResult,
  ConversationRecord,
  SuggestionFeedback,
} from '../../assistant/model/chat.types';
import { deriveConversationTitle } from '../../assistant/model/chatHelpers';
import type { OutfitRecord } from '../../outfits/model/outfit.types';
import { initialConversations } from '../conversations/conversationDemoData';

export const DEFAULT_CONVERSATION_TITLE = 'Yeni sohbet';

export const conversationSession = {
  conversations: initialConversations as readonly ConversationRecord[],
  simulateError: false,
  nextConv: initialConversations.length + 1,
  nextMsg: 100,
  nextSug: 100,
  nextOutfit: 1,
};

export function setSessionConversations(next: readonly ConversationRecord[]) {
  conversationSession.conversations = next;
}

export function setSessionSimulateError(value: boolean) {
  conversationSession.simulateError = value;
}

export function allocateConversationId(): string {
  return `conv-${String(conversationSession.nextConv++).padStart(2, '0')}`;
}

export type ConversationDemoContextValue = {
  conversations: readonly ConversationRecord[];
  simulateError: boolean;
  setSimulateError: (value: boolean) => void;
  getConversation: (id: string) => ConversationRecord | undefined;
  createConversation: () => ConversationRecord;
  deleteConversation: (id: string) => Promise<void>;
  sendMessage: (conversationId: string, rawPrompt: string) => Promise<void>;
  retryMessage: (conversationId: string, messageId: string) => Promise<void>;
  togglePin: (conversationId: string, messageId: string, itemId: string) => void;
  regenerateSuggestion: (conversationId: string, messageId: string) => Promise<void>;
  approveSuggestion: (conversationId: string, messageId: string) => Promise<OutfitRecord>;
  setFeedback: (
    conversationId: string,
    messageId: string,
    feedback: Exclude<SuggestionFeedback, null>
  ) => void;
};

export function createEmptyConversation(id: string, nowIso: string): ConversationRecord {
  return {
    id,
    title: DEFAULT_CONVERSATION_TITLE,
    updatedAt: nowIso,
    messages: [],
  };
}

export function buildAssistantMessage(
  id: string,
  reply: ChatReplyResult,
  nowIso: string
): ChatMessage {
  return {
    id,
    sender: 'assistant',
    text: reply.text,
    createdAt: nowIso,
    status: 'sent',
    suggestion: reply.suggestion
      ? { ...reply.suggestion, approvedOutfitId: null, feedback: null }
      : undefined,
  };
}

export function updateConversationInList(
  list: readonly ConversationRecord[],
  id: string,
  updater: (conversation: ConversationRecord) => ConversationRecord
): ConversationRecord[] {
  return list.map((conv) => (conv.id === id ? updater(conv) : conv));
}

export function applyPromptTitleIfDefault(
  conversation: ConversationRecord,
  prompt: string
): string {
  if (conversation.title === DEFAULT_CONVERSATION_TITLE && conversation.messages.length === 0) {
    return deriveConversationTitle(prompt, DEFAULT_CONVERSATION_TITLE);
  }
  return conversation.title;
}

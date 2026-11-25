import { createContext, useContext, useState, type ReactNode } from 'react';
import type { ConversationRecord, SuggestionFeedback } from '../../assistant/model/chat.types';
import {
  setSuggestionFeedbackInMessages,
  toggleSuggestionPinInMessages,
} from '../../assistant/model/chatState';
import { useClothingDemo } from './ClothingDemoContext';
import { createConversationAsyncActions } from './conversationDemo.actions';
import {
  allocateConversationId,
  conversationSession,
  createEmptyConversation,
  setSessionConversations,
  setSessionSimulateError,
  updateConversationInList,
  type ConversationDemoContextValue,
} from './conversationDemo.helpers';
import { useOutfitDemo } from './OutfitDemoContext';

const ConversationDemoContext = createContext<ConversationDemoContextValue | null>(null);

/** Oturumluk sohbet geçmişini ve kombin önerisi işlemlerini sağlayan context bileşenidir. */
export function ConversationDemoProvider({ children }: { children: ReactNode }) {
  const { items: wardrobe } = useClothingDemo();
  const { addOutfit } = useOutfitDemo();
  const [conversations, setConversations] = useState(() => conversationSession.conversations);
  const [simulateError, setSimulateErrorState] = useState(() => conversationSession.simulateError);

  function commit(next: readonly ConversationRecord[]) {
    setSessionConversations(next);
    setConversations(next);
  }

  function setSimulateError(value: boolean) {
    setSessionSimulateError(value);
    setSimulateErrorState(value);
  }

  function getConversation(id: string) {
    return conversations.find((conv) => conv.id === id);
  }

  function createConversation() {
    const created = createEmptyConversation(allocateConversationId(), new Date().toISOString());
    commit([created, ...conversationSession.conversations]);
    return created;
  }

  async function deleteConversation(id: string) {
    await new Promise((resolve) => setTimeout(resolve, 140));
    if (conversationSession.simulateError) {
      throw new Error('Sohbet silinemedi. Lütfen tekrar dene.');
    }
    commit(conversationSession.conversations.filter((conv) => conv.id !== id));
  }

  function togglePin(conversationId: string, messageId: string, itemId: string) {
    commit(
      updateConversationInList(conversationSession.conversations, conversationId, (conv) => ({
        ...conv,
        messages: toggleSuggestionPinInMessages(conv.messages, messageId, itemId),
      }))
    );
  }

  function setFeedback(
    conversationId: string,
    messageId: string,
    feedback: Exclude<SuggestionFeedback, null>
  ) {
    commit(
      updateConversationInList(conversationSession.conversations, conversationId, (conv) => ({
        ...conv,
        messages: setSuggestionFeedbackInMessages(conv.messages, messageId, feedback),
      }))
    );
  }

  const asyncActions = createConversationAsyncActions({ wardrobe, addOutfit, commit });

  return (
    <ConversationDemoContext.Provider
      value={{
        conversations,
        simulateError,
        setSimulateError,
        getConversation,
        createConversation,
        deleteConversation,
        togglePin,
        setFeedback,
        ...asyncActions,
      }}
    >
      {children}
    </ConversationDemoContext.Provider>
  );
}

export function useConversationDemo(): ConversationDemoContextValue {
  const value = useContext(ConversationDemoContext);
  if (!value) {
    throw new Error('useConversationDemo yalnızca DemoProvider içinde kullanılabilir.');
  }
  return value;
}

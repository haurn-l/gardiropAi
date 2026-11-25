import type { ChatMessage, SuggestionFeedback } from './chat.types';

/**
 * Gönderim aşamasındaki yeni kullanıcı mesajını dizinin sonuna ekler.
 */
export function appendPendingUserMessage(
  messages: readonly ChatMessage[],
  message: ChatMessage
): ChatMessage[] {
  return [...messages, { ...message, status: 'sending', errorText: undefined }];
}

/**
 * Gönderimi başarısız olan kullanıcı mesajını hata durumuna çeker.
 */
export function markMessageFailed(
  messages: readonly ChatMessage[],
  messageId: string,
  errorText: string
): ChatMessage[] {
  return messages.map((msg) =>
    msg.id === messageId ? { ...msg, status: 'error', errorText } : msg
  );
}

/**
 * Hata almış kullanıcı mesajını tekrar gönderim durumuna döndürür.
 */
export function markMessageRetrying(
  messages: readonly ChatMessage[],
  messageId: string
): ChatMessage[] {
  return messages.map((msg) =>
    msg.id === messageId ? { ...msg, status: 'sending', errorText: undefined } : msg
  );
}

/**
 * Kullanıcı mesajını gönderildi olarak işaretler ve asistan yanıtını ekler.
 */
export function resolveUserMessageWithReply(
  messages: readonly ChatMessage[],
  userMessageId: string,
  assistantMessage: ChatMessage
): ChatMessage[] {
  const updated = messages.map((msg) =>
    msg.id === userMessageId ? { ...msg, status: 'sent' as const, errorText: undefined } : msg
  );
  return [...updated, { ...assistantMessage, status: 'sent' }];
}

/**
 * Belirli bir öneri mesajındaki parça sabitleme durumunu değiştirir.
 * Yalnızca o öneride yer alan parça kimliklerini kabul eder.
 */
export function toggleSuggestionPinInMessages(
  messages: readonly ChatMessage[],
  messageId: string,
  itemId: string
): ChatMessage[] {
  return messages.map((msg) => {
    if (msg.id !== messageId || !msg.suggestion) {
      return msg;
    }
    const existsInSuggestion = msg.suggestion.items.some((item) => item.id === itemId);
    if (!existsInSuggestion) {
      return msg;
    }
    const alreadyPinned = msg.suggestion.pinnedItemIds.includes(itemId);
    const nextPinned = alreadyPinned
      ? msg.suggestion.pinnedItemIds.filter((id) => id !== itemId)
      : [...msg.suggestion.pinnedItemIds, itemId];

    return {
      ...msg,
      suggestion: {
        ...msg.suggestion,
        pinnedItemIds: nextPinned,
      },
    };
  });
}

/**
 * Öneriyi onaylandı olarak işaretler.
 * Zaten onaylanmış bir öneri tekrar değiştirilmez (tekil onay kuralı).
 */
export function markSuggestionApprovedInMessages(
  messages: readonly ChatMessage[],
  messageId: string,
  outfitId: string
): ChatMessage[] {
  return messages.map((msg) => {
    if (msg.id !== messageId || !msg.suggestion || msg.suggestion.approvedOutfitId !== null) {
      return msg;
    }
    return {
      ...msg,
      suggestion: {
        ...msg.suggestion,
        approvedOutfitId: outfitId,
      },
    };
  });
}

/**
 * Öneri mesajına verilen geri bildirimi günceller; aynı seçim tekrar seçilirse temizler.
 */
export function setSuggestionFeedbackInMessages(
  messages: readonly ChatMessage[],
  messageId: string,
  feedback: Exclude<SuggestionFeedback, null>
): ChatMessage[] {
  return messages.map((msg) => {
    if (msg.id !== messageId || !msg.suggestion) {
      return msg;
    }
    const nextFeedback: SuggestionFeedback =
      msg.suggestion.feedback === feedback ? null : feedback;
    return {
      ...msg,
      suggestion: {
        ...msg.suggestion,
        feedback: nextFeedback,
      },
    };
  });
}

package com.gardiropai.backend.dto.response;

import com.gardiropai.backend.entity.ChatDraftItem;
import com.gardiropai.backend.enums.SenderType;

import java.time.LocalDateTime;
import java.util.List;

public final class ChatResponses {
    private ChatResponses() {
    }

    public record Summary(Long id, String title, LocalDateTime createdAt) {
    }

    public record Detail(Long id, String title, LocalDateTime createdAt,
                         List<Message> messages, Draft draft) {
    }

    public record Message(Long id, SenderType senderRole, String content, LocalDateTime createdAt) {
    }

    public record Draft(long version, List<ChatDraftItem> items, Long savedCombineId) {
    }

    public record Confirmed(Long combineId) {
    }
}

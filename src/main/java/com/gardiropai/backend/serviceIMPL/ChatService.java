package com.gardiropai.backend.serviceIMPL;

import com.gardiropai.backend.dto.request.ChatRequests;
import com.gardiropai.backend.dto.request.CombineCreateRequest;
import com.gardiropai.backend.dto.response.ChatResponses;
import com.gardiropai.backend.entity.ChatDraftItem;
import com.gardiropai.backend.entity.ChatMessage;
import com.gardiropai.backend.entity.ChatSession;
import com.gardiropai.backend.entity.ClothingItem;
import com.gardiropai.backend.entity.User;
import com.gardiropai.backend.enums.ItemStatus;
import com.gardiropai.backend.enums.SenderType;
import com.gardiropai.backend.exception.ResourceNotFoundException;
import com.gardiropai.backend.repository.ChatMessageRepository;
import com.gardiropai.backend.repository.ChatSessionRepository;
import com.gardiropai.backend.repository.ClothingItemRepository;
import com.gardiropai.backend.repository.UserRepository;
import com.gardiropai.backend.service.CombineService;
import lombok.RequiredArgsConstructor;
import org.springframework.boot.context.event.ApplicationReadyEvent;
import org.springframework.context.event.EventListener;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.server.ResponseStatusException;

import java.util.HashSet;
import java.util.List;

@Service
@RequiredArgsConstructor
@Transactional(readOnly = true)
public class ChatService {
    private final ChatSessionRepository sessions;
    private final ChatMessageRepository messages;
    private final UserRepository users;
    private final ClothingItemRepository clothes;
    private final CombineService combines;

    @EventListener(ApplicationReadyEvent.class)
    @Transactional
    public void repairDeletedCombineLinks() {
        sessions.clearOrphanedSavedCombines();
    }

    @Transactional
    public ChatResponses.Detail start(String title) {
        ChatSession session = sessions.save(ChatSession.builder()
                .user(users.getOrCreateDemoUser())
                .title(title == null || title.isBlank() ? "Yeni sohbet" : title.strip())
                .build());
        return toDetail(session, List.of());
    }

    public List<ChatResponses.Summary> list() {
        return users.findFirstByOrderByIdAsc()
                .map(user -> sessions.findByUserIdOrderByCreatedAtDescIdDesc(user.getId()).stream()
                        .map(session -> new ChatResponses.Summary(
                                session.getId(), session.getTitle(), session.getCreatedAt()))
                        .toList())
                .orElseGet(List::of);
    }

    public ChatResponses.Detail get(Long id) {
        ChatSession session = findSession(id);
        List<ChatResponses.Message> history = messages.findByChatSessionIdOrderByCreatedAtAscIdAsc(id).stream()
                .map(ChatService::toMessage)
                .toList();
        return toDetail(session, history);
    }

    @Transactional
    public ChatResponses.Message addUserMessage(Long id, String content) {
        ChatMessage message = messages.save(ChatMessage.builder()
                .chatSession(findSession(id))
                .senderRole(SenderType.USER)
                .content(content.strip())
                .build());
        return toMessage(message);
    }

    @Transactional
    public ChatResponses.Draft replaceDraft(Long id, ChatRequests.ReplaceDraft request) {
        ChatSession session = lockDraft(id, request.version());
        List<ChatDraftItem> items = request.items().stream()
                .map(item -> new ChatDraftItem(item.clothingItemId(), item.locked()))
                .toList();
        List<Long> itemIds = items.stream().map(ChatDraftItem::clothingItemId).toList();
        if (new HashSet<>(itemIds).size() != itemIds.size()) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "Bir kıyafet taslakta yalnızca bir kez yer alabilir.");
        }
        if (!items.equals(draftItems(session))) {
            validateAvailableItems(session.getUser().getId(), itemIds, clothes.findAllById(itemIds));
            session.setDraftItems(items);
            session.setDraftVersion(session.getDraftVersion() + 1);
            session.setSavedCombineId(null);
        }
        return toDraft(session);
    }

    @Transactional
    public ChatResponses.Confirmed confirmDraft(Long id, long version) {
        ChatSession session = lockDraft(id, version);
        if (session.getSavedCombineId() != null) {
            return new ChatResponses.Confirmed(session.getSavedCombineId());
        }

        List<Long> itemIds = draftItems(session).stream().map(ChatDraftItem::clothingItemId).toList();
        if (itemIds.isEmpty()) {
            throw new ResponseStatusException(HttpStatus.CONFLICT, "Boş kombin taslağı kaydedilemez.");
        }

        Long userId = session.getUser().getId();
        validateAvailableItems(userId, itemIds, clothes.findForStatusUpdate(itemIds));
        CombineCreateRequest request = new CombineCreateRequest();
        request.setUserId(userId);
        request.setClothingItemIds(itemIds);
        Long combineId = combines.createCombine(request).getId();
        session.setSavedCombineId(combineId);
        return new ChatResponses.Confirmed(combineId);
    }

    private ChatSession findSession(Long id) {
        return sessions.findByIdAndUserId(id, demoUserId(id)).orElseThrow(() -> notFound(id));
    }

    private ChatSession lockDraft(Long id, long version) {
        ChatSession session = sessions.findForDraftUpdate(id, demoUserId(id)).orElseThrow(() -> notFound(id));
        if (session.getDraftVersion() != version) {
            throw new ResponseStatusException(HttpStatus.CONFLICT, "Kombin taslağı değişti. Güncel sohbeti yeniden yükleyin.");
        }
        return session;
    }

    private Long demoUserId(Long sessionId) {
        return users.findFirstByOrderByIdAsc().map(User::getId).orElseThrow(() -> notFound(sessionId));
    }

    private static ResourceNotFoundException notFound(Long id) {
        return new ResourceNotFoundException("Sohbet bulunamadı. ID: " + id);
    }

    private static void validateAvailableItems(Long userId, List<Long> itemIds, List<ClothingItem> found) {
        if (found.size() != itemIds.size()
                || found.stream().anyMatch(item -> !userId.equals(item.getUser().getId())
                        || item.getStatus() != ItemStatus.TEMIZ)) {
            throw new ResponseStatusException(HttpStatus.CONFLICT,
                    "Kombinde yalnızca gardıroptaki temiz kıyafetler kullanılabilir.");
        }
    }

    private static ChatResponses.Detail toDetail(ChatSession session, List<ChatResponses.Message> history) {
        return new ChatResponses.Detail(
                session.getId(), session.getTitle(), session.getCreatedAt(), history, toDraft(session));
    }

    private static ChatResponses.Message toMessage(ChatMessage message) {
        return new ChatResponses.Message(
                message.getId(), message.getSenderRole(), message.getContent(), message.getCreatedAt());
    }

    private static ChatResponses.Draft toDraft(ChatSession session) {
        return new ChatResponses.Draft(session.getDraftVersion(), draftItems(session), session.getSavedCombineId());
    }

    private static List<ChatDraftItem> draftItems(ChatSession session) {
        return session.getDraftItems() == null ? List.of() : List.copyOf(session.getDraftItems());
    }
}

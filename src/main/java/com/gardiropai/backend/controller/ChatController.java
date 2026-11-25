package com.gardiropai.backend.controller;

import com.gardiropai.backend.dto.request.ChatRequests;
import com.gardiropai.backend.dto.response.ChatResponses;
import com.gardiropai.backend.serviceIMPL.ChatService;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.*;

import java.util.List;

@RestController
@RequestMapping("/api/v1/chats")
@RequiredArgsConstructor
public class ChatController {
    private final ChatService chats;

    @PostMapping("/start")
    @ResponseStatus(HttpStatus.CREATED)
    public ChatResponses.Detail start(@Valid @RequestBody ChatRequests.Start request) {
        return chats.start(request.title());
    }

    @GetMapping("/all")
    public List<ChatResponses.Summary> list() {
        return chats.list();
    }

    @GetMapping("/{id}")
    public ChatResponses.Detail detail(@PathVariable Long id) {
        return chats.get(id);
    }

    @PostMapping("/{id}/messages")
    @ResponseStatus(HttpStatus.CREATED)
    public ChatResponses.Message sendMessage(@PathVariable Long id,
                                             @Valid @RequestBody ChatRequests.SendMessage request) {
        return chats.addUserMessage(id, request.content());
    }

    @PutMapping("/{id}/draft")
    public ChatResponses.Draft replaceDraft(@PathVariable Long id,
                                           @Valid @RequestBody ChatRequests.ReplaceDraft request) {
        return chats.replaceDraft(id, request);
    }

    @PostMapping("/{id}/draft/confirm")
    public ChatResponses.Confirmed confirmDraft(@PathVariable Long id,
                                               @Valid @RequestBody ChatRequests.ConfirmDraft request) {
        return chats.confirmDraft(id, request.version());
    }
}

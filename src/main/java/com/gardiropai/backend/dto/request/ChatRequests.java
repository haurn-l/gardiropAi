package com.gardiropai.backend.dto.request;

import jakarta.validation.Valid;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Positive;
import jakarta.validation.constraints.PositiveOrZero;
import jakarta.validation.constraints.Size;

import java.util.List;

public final class ChatRequests {
    private ChatRequests() {
    }

    public record Start(@Size(max = 255) String title) {
    }

    public record SendMessage(@NotBlank String content) {
    }

    public record DraftItem(@NotNull @Positive Long clothingItemId, @NotNull Boolean locked) {
    }

    public record ReplaceDraft(@NotNull @PositiveOrZero Long version,
                               @NotNull List<@NotNull @Valid DraftItem> items) {
    }

    public record ConfirmDraft(@NotNull @PositiveOrZero Long version) {
    }
}

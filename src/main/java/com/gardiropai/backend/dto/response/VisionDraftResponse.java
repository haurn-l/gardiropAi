package com.gardiropai.backend.dto.response;

import com.gardiropai.backend.enums.Category;
import com.gardiropai.backend.enums.Season;

import java.time.Instant;
import java.util.Map;
import java.util.UUID;

public record VisionDraftResponse(UUID draftId, int revision, String status, Category category, Instant expiresAt,
                                  Map<String, String> views, Suggestions suggestions, String frontImageUrl,
                                  String backImageUrl, Failure error, Long clothingItemId) {
    public record Suggestions(String subCategory, String color, Season season, Boolean hasPrint) {}

    public record Failure(String code, String stage, String message, boolean retryable) {}
}

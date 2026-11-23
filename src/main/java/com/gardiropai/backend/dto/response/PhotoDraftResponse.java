package com.gardiropai.backend.dto.response;

import java.util.UUID;

public record PhotoDraftResponse(UUID uploadId, String imageUrl) {}

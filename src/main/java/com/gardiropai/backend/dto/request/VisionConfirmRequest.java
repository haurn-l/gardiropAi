package com.gardiropai.backend.dto.request;

import jakarta.validation.Valid;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Positive;

public record VisionConfirmRequest(@NotNull @Positive Integer revision, @NotNull @Valid ClothingDetailsRequest details) {}

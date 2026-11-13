package com.gardiropai.backend.dto.request;

import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotEmpty;
import jakarta.validation.constraints.NotNull;
import lombok.Data;

import java.util.List;

@Data
public class CombineCreateRequest {

    @NotNull
    private Long userId;

    @NotEmpty
    private List<Long> clothingItemIds;

    @Min(1)
    @Max(5)
    private Integer ratingScore;
}

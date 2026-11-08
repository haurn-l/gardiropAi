package com.gardiropai.backend.dto.response;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.time.LocalDateTime;
import java.util.List;

@Data
@Builder
@AllArgsConstructor
@NoArgsConstructor
public class CombineResponse{

    private Long id;

    private Long userId;

    private List<ClothingResponse> clothingItems;

    private Integer ratingScore;

    private LocalDateTime createdAt;
}

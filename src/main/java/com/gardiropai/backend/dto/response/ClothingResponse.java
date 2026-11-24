package com.gardiropai.backend.dto.response;

import com.gardiropai.backend.enums.Category;
import com.gardiropai.backend.enums.ItemStatus;
import com.gardiropai.backend.enums.Season;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.time.Instant;
import java.util.List;

@Data
@Builder
@AllArgsConstructor
@NoArgsConstructor
public class ClothingResponse {

    private Long id;

    private String name;

    private String imageUrl;

    private Category category;

    private String subCategory;

    private String color;

    private Season season;

    private ItemStatus status;

    private Instant dirtySince;

    private Boolean hasPrint;

    private List<String> tags;

    private boolean favorite;

    private Integer userRating;
}

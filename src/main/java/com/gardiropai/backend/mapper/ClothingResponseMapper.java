package com.gardiropai.backend.mapper;

import com.gardiropai.backend.dto.response.ClothingResponse;
import com.gardiropai.backend.entity.ClothingItem;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Component;
import org.springframework.util.StringUtils;
import tools.jackson.databind.JsonNode;
import tools.jackson.databind.json.JsonMapper;

import java.util.List;

@Component
@RequiredArgsConstructor
public class ClothingResponseMapper {
    private final JsonMapper jsonMapper;

    public ClothingResponse toResponse(ClothingItem item) {
        return ClothingResponse.builder()
                .id(item.getId())
                .name(displayName(item))
                .imageUrl(item.getImageUrl())
                .backImageUrl(item.getBackImageUrl())
                .category(item.getCategory())
                .subCategory(item.getSubCategory())
                .color(item.getColor())
                .season(item.getSeason())
                .status(item.getStatus())
                .dirtySince(item.getDirtySince())
                .hasPrint(item.getHasPrint())
                .tags(readTags(item.getCustomTags()))
                .favorite(item.isFavorite())
                .userRating(item.getUserRating())
                .build();
    }

    private String displayName(ClothingItem item) {
        if (StringUtils.hasText(item.getName())) {
            return item.getName();
        }
        return StringUtils.hasText(item.getSubCategory()) ? item.getSubCategory() : "Kıyafet";
    }

    private List<String> readTags(String customTags) {
        if (customTags == null) {
            return List.of();
        }
        JsonNode tags = jsonMapper.readTree(customTags);
        return tags.values().stream()
                .filter(JsonNode::isString)
                .map(JsonNode::asString)
                .toList();
    }
}

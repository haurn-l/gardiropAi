package com.gardiropai.backend.dto.request;

import com.gardiropai.backend.enums.Category;
import com.gardiropai.backend.enums.Season;
import lombok.Data;

/**
 * Mobilden backend'e kıyafet eklerken gönderilecek JSON verisinin yapısı.
 */

@Data
public class ClothingCreateRequest {
    private Long userId; // Hangi kullanıcı ekliyor
    private String imageUrl;
    private Category category;
    private Season season;
    private String color;
}
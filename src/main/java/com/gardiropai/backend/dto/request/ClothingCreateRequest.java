package com.gardiropai.backend.dto.request;

import com.gardiropai.backend.enums.Category;
import com.gardiropai.backend.enums.Season;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Size;
import lombok.Data;

import java.util.List;

/**
 * Mobilden backend'e kıyafet eklerken gönderilecek JSON verisinin yapısı.
 */

@Data
public class ClothingCreateRequest {
    @NotNull(message = "Kullanıcı ID boş bırakılamaz")
    private Long userId;

    @NotBlank(message = "Kıyafet fotoğrafı (URL) boş olamaz")
    private String imageUrl;

    @Size(max = 255)
    private String name;

    @NotNull(message = "Kategori seçimi zorunludur")
    private Category category;

    @Size(max = 255)
    private String subCategory;

    @NotNull(message = "Mevsim seçimi zorunludur")
    private Season season;

    private String color; // Renk opsiyonel kalabilir

    private Boolean hasPrint;

    private List<@NotBlank String> tags;
}
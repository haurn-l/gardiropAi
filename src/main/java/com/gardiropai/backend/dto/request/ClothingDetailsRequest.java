package com.gardiropai.backend.dto.request;

import com.gardiropai.backend.enums.Category;
import com.gardiropai.backend.enums.Season;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Size;
import lombok.Data;

import java.util.List;

@Data
public class ClothingDetailsRequest {
    @Size(max = 255)
    private String name;

    @NotNull(message = "Kategori seçimi zorunludur")
    private Category category;

    @Size(max = 255)
    private String subCategory;

    @NotNull(message = "Mevsim seçimi zorunludur")
    private Season season;

    @Size(max = 255)
    private String color;

    private Boolean hasPrint;

    private List<@NotBlank String> tags;
}

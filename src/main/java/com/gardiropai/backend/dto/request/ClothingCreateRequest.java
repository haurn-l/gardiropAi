package com.gardiropai.backend.dto.request;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import lombok.Getter;
import lombok.Setter;

/**
 * Mobilden backend'e kıyafet eklerken gönderilecek JSON verisinin yapısı.
 */

@Getter
@Setter
public class ClothingCreateRequest extends ClothingDetailsRequest {
    @NotNull(message = "Kullanıcı ID boş bırakılamaz")
    private Long userId;

    @NotBlank(message = "Kıyafet fotoğrafı (URL) boş olamaz")
    private String imageUrl;
}

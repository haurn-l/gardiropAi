package com.gardiropai.backend.entity;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import lombok.AccessLevel;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;

import java.util.UUID;

@Entity
@Table(name = "clothing_photos")
@Getter
@NoArgsConstructor(access = AccessLevel.PROTECTED)
public class ClothingPhoto {
    @Id
    private UUID id;

    @Column(nullable = false, updatable = false)
    private String contentType;

    @Setter
    private Long clothingItemId;

    public ClothingPhoto(UUID id, String contentType) {
        this.id = id;
        this.contentType = contentType;
    }
}

package com.gardiropai.backend.entity;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import lombok.AccessLevel;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;
import org.hibernate.annotations.JdbcTypeCode;
import org.hibernate.type.SqlTypes;

import java.util.UUID;

@Entity
@Table(name = "clothing_vision_drafts")
@Getter
@NoArgsConstructor(access = AccessLevel.PROTECTED)
public class ClothingVisionDraft {
    @Id
    private UUID id;

    @Column(nullable = false, updatable = false)
    private String modelJobId;

    @Setter
    private Integer savedRevision;

    @Setter
    private Long clothingItemId;

    @Setter
    @JdbcTypeCode(SqlTypes.JSON)
    @Column(columnDefinition = "jsonb")
    private String embedding;
}

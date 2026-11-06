package com.gardiropai.backend.entity;

import jakarta.persistence.*;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;
import java.time.LocalDateTime;
import java.util.List;

/**
 * Combine (Kombin) Varlık Sınıfı
 *
 * Kullanıcının gardırobundaki kıyafetlerden (ClothingItem) oluşturulan geçmiş kombinleri temsil eder.
 * Yapay zeka veya kullanıcı tarafından oluşturulan kombinlerin içeriklerini,
 * oluşturulma tarihini ve kullanıcının bu kombine verdiği değerlendirme puanını tutar.
 */



@Entity
@Table(name = "combines")
@Data
@NoArgsConstructor
@AllArgsConstructor
@Builder
public class Combine {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    // Kombinin ait olduğu kullanıcı (Bir kullanıcının çok sayıda kombini olabilir)
    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "user_id", nullable = false)
    private User user;

    // Kombini oluşturan kıyafet parçaları (Çoka çok ilişki: Bir kombin çok kıyafet içerir, bir kıyafet çok kombinde olabilir)
    @ManyToMany(fetch = FetchType.LAZY)
    @JoinTable(
            name = "combine_clothing_items",
            joinColumns = @JoinColumn(name = "combine_id"),
            inverseJoinColumns = @JoinColumn(name = "clothing_item_id")
    )
    private List<ClothingItem> clothingItems;

    // Kullanıcının bu kombine verdiği beğeni puanı (Örn: 1 ile 5 arası)
    @Column(name = "rating_score")
    private Integer ratingScore;

    // Kombinin oluşturulduğu tarih (Geçmiş kombinleri sıralamak için)
    @Column(name = "created_at", updatable = false)
    private LocalDateTime createdAt;

    // Veritabanına ilk kayıt atıldığında anlık tarihi otomatik belirler
    @PrePersist
    protected void onCreate() {
        this.createdAt = LocalDateTime.now();
    }
}
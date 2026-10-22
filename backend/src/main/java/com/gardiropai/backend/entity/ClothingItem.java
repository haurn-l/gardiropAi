package com.gardiropai.backend.entity;

import com.gardiropai.backend.enums.Category;
import com.gardiropai.backend.enums.ItemStatus;
import com.gardiropai.backend.enums.Season;
import jakarta.persistence.*;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;


//Kullanıcıların gardırobuna eklediği her bir kıyafet parçası bu sınıfta tutulur.
@Entity
@Table(name = "clothes")
@Data
@NoArgsConstructor
@AllArgsConstructor
@Builder
public class ClothingItem {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "user_id", nullable = false) // Veritabanındaki Foreign Key sütunu
    private User user;

    @Column(name = "image_url") //lokaldeki fotoğrafın linki
    private String imageUrl;

    @Enumerated(EnumType.STRING) // Enum değerini veritabanına sayı (0,1) olarak değil, metin (UST_GIYIM) olarak kaydeder
    @Column(nullable = false)
    private Category category;

    @Column(name = "sub_category") // Örn: Gömlek, Pantolon, Bere
    private String subCategory;

    private String color; // Örn: Mavi, Siyah

    @Enumerated(EnumType.STRING)
    @Column(nullable = false)
    private Season season; // KIS, YAZ, SONBAHAR vb.

    @Column(name = "has_print")
    private Boolean hasPrint; // Baskılı mı düz mü?

    @Column(name = "user_rating") // Kullanıcının parçaya verdiği kişisel favori puanı (1-5)
    private Integer userRating;

    @Enumerated(EnumType.STRING)
    @Column(nullable = false)
    private ItemStatus status; // TEMIZ veya KIRLI statüsü, yapay zeka filtresi için en kritik alan!

    /**
     * Standart seçeneklerde (Dropdown) bulunmayan ekstra özellikleri tutmak için.
     * JSON formatında veya virgülle ayrılmış string olarak tutulabilir (Örn: "fosforlu, yirtik").
     */
    @Column(name = "custom_tags", columnDefinition = "jsonb")
    private String customTags;
}
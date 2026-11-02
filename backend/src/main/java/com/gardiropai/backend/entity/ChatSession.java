package com.gardiropai.backend.entity;

import jakarta.persistence.*;
import lombok.*;

import java.time.LocalDateTime;
import java.util.List;

/**
 * ChatSession (Sohbet Oturumu) Varlık Sınıfı
 *
 * Kullanıcının yapay zeka ile başlattığı her bir sohbet sayfasını temsil eder.
 */
@Entity
@Table(name = "chat_sessions")
@Data
@NoArgsConstructor
@AllArgsConstructor
@Builder
public class ChatSession {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    // Sohbeti başlatan kullanıcı
    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "user_id", nullable = false)
    private User user;

    // Frontend'de (Mobilde) geçmiş sohbetleri listelerken görünecek başlık
    // Örn: "Kışlık Kombin Önerisi", "Düğün için ne giysem?"
    private String title;

    // Sohbetin başlatıldığı tarih
    @Column(name = "created_at", updatable = false)
    private LocalDateTime createdAt;

    // Bu oturuma ait mesajların listesi (ChatMessage sınıfını yazınca hata gidecektir)
    @ToString.Exclude
    @EqualsAndHashCode.Exclude
    @OneToMany(mappedBy = "chatSession", cascade = CascadeType.ALL)
    private List<ChatMessage> messages;

    @PrePersist
    protected void onCreate() {
        this.createdAt = LocalDateTime.now();
    }
}
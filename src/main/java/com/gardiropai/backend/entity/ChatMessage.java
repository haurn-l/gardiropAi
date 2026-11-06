package com.gardiropai.backend.entity;

import com.gardiropai.backend.enums.SenderType;
import jakarta.persistence.*;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;
import java.time.LocalDateTime;

/**
 * ChatMessage (Sohbet Mesajı) Varlık Sınıfı
 *
 * İlgili sohbet oturumundaki (ChatSession) tekil mesajları tutar.
 * Mesajın kullanıcıdan mı yoksa yapay zekadan mı geldiğini ve
 * eğer yapay zeka bir kombin önerdiyse o kombinin bağlantısını barındırır.
 */
@Entity
@Table(name = "chat_messages")
@Data
@NoArgsConstructor
@AllArgsConstructor
@Builder
public class ChatMessage {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    // Mesajın hangi sohbet oturumuna ait olduğu
    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "chat_session_id", nullable = false)
    private ChatSession chatSession;

    // Mesajı gönderen taraf (Örn: "USER" veya "AI")
    // İstersen Enum (Role) olarak da değiştirebilirsin
    @Column(name = "sender_role", nullable = false)
    private SenderType senderRole;

    // Mesajın metin içeriği
    @Column(columnDefinition = "TEXT", nullable = false)
    private String content;

    // Eğer yapay zeka bu mesajda bir kombin oluşturduysa o kombinin referansı (Her mesajda kombin olmayacağı için nullable bırakılır)
    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "combine_id")
    private Combine combine;

    // Mesajın gönderildiği tarih ve saat
    @Column(name = "created_at", updatable = false)
    private LocalDateTime createdAt;

    @PrePersist
    protected void onCreate() {
        this.createdAt = LocalDateTime.now();
    }
}
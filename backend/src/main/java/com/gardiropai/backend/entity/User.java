package com.gardiropai.backend.entity;

import jakarta.persistence.*;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;
import java.time.LocalDateTime;

/**
 * Bu snif veritabanindaki 'users' tablosunu temsil edecek
 * Sisteme kayitli kullanicilari ve onlarin yapay zeka tarafindan öğrenilen stil tercihlerini tutmak için kullanilacak
 */
@Entity // bu anotasyon bir tablosu oldugnu belirtir
@Table(name = "users") // Veritabanındaki tablonun adini 'users' olarak belirler
@Data //  Otomatik olarak getter setter toString metodlarini uretir
@NoArgsConstructor // Parametresiz bos bir constructor olusturur
@AllArgsConstructor //tum alanlari iceren bir constructor olusturur
@Builder //  Builder pattern yazmayi kolaylastirir
public class User {

    @Id // Bu alanın PK oldugunu belirtir
    @GeneratedValue(strategy = GenerationType.IDENTITY) // ID'nin otomatik artirir
    private Long id;

    @Column(nullable = false, unique = true) // Bu sutun boş birakilamaz ve benzersiz olmalidir
    private String username;

    //Kullanıcının yapay zeka tarafından analiz edilen tarz verilerini tutar,postgreSQL'de esnek sorgular yapabilmek için 'jsonb' formatında saklıyoruz.
    @Column(name = "style_preferences", columnDefinition = "jsonb")
    private String stylePreferences;

    //Kullanici tarzini sifirlamak isterse bu tarihe bakılır.
    @Column(name = "preferences_reset_date")
    private LocalDateTime preferencesResetDate;
}
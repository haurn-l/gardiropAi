package com.gardiropai.backend.repository;

import com.gardiropai.backend.entity.ClothingItem;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.List;

/**
 * Bu interface, veritabanı ile 'clothes' tablosu arasındaki işlemleri yönetir.
 * JpaRepository sayesinde temel CRUD işlemleri otomatik olarak gelir.
 */
@Repository
public interface ClothingItemRepository extends JpaRepository<ClothingItem, Long> {
    // Özel sorgu örneği: Bir kullanıcının sadece TEMIZ kıyafetlerini getir
    List<ClothingItem> findByUserIdAndStatus(Long userId, com.gardiropai.backend.enums.ItemStatus status);
}
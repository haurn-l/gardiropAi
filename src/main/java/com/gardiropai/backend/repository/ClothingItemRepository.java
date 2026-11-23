package com.gardiropai.backend.repository;

import com.gardiropai.backend.entity.ClothingItem;
import com.gardiropai.backend.enums.Category;
import com.gardiropai.backend.enums.ItemStatus;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.stereotype.Repository;

import java.util.List;

/**
 * Bu interface, veritabanı ile 'clothes' tablosu arasındaki işlemleri yönetir.
 * JpaRepository sayesinde temel CRUD işlemleri otomatik olarak gelir.
 */
@Repository
public interface ClothingItemRepository extends JpaRepository<ClothingItem, Long> {
    // Özel sorgu örneği: Bir kullanıcının sadece TEMIZ kıyafetlerini getir
    List<ClothingItem> findByUserIdAndStatus(Long userId, ItemStatus status);
    List<ClothingItem> findByUserId(Long userId);

    @Query("""
            select item from ClothingItem item
            where item.user.id = :userId
              and (:status is null or item.status = :status)
              and (:category is null or item.category = :category)
              and (:favorite is null or item.favorite = :favorite)
            order by item.id
            """)
    List<ClothingItem> findWardrobeItems(@Param("userId") Long userId,
                                         @Param("status") ItemStatus status,
                                         @Param("category") Category category,
                                         @Param("favorite") Boolean favorite);
}
package com.gardiropai.backend.repository;

import com.gardiropai.backend.entity.ClothingPhoto;
import jakarta.persistence.LockModeType;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Lock;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

import java.util.Optional;
import java.util.UUID;

public interface ClothingPhotoRepository extends JpaRepository<ClothingPhoto, UUID> {
    @Lock(LockModeType.PESSIMISTIC_WRITE)
    @Query("select photo from ClothingPhoto photo where photo.id = :id")
    Optional<ClothingPhoto> findForUpdate(@Param("id") UUID id);

    Optional<ClothingPhoto> findByClothingItemId(Long clothingItemId);
}

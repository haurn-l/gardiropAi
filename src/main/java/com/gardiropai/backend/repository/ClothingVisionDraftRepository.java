package com.gardiropai.backend.repository;

import com.gardiropai.backend.entity.ClothingVisionDraft;
import jakarta.persistence.LockModeType;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Lock;
import org.springframework.data.jpa.repository.Modifying;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

import java.util.Optional;
import java.util.UUID;

public interface ClothingVisionDraftRepository extends JpaRepository<ClothingVisionDraft, UUID> {
    @Modifying
    @Query(value = """
            insert into clothing_vision_drafts (id, model_job_id) values (:id, :jobId)
            on conflict (id) do nothing
            """, nativeQuery = true)
    void createIfMissing(@Param("id") UUID id, @Param("jobId") String jobId);

    @Lock(LockModeType.PESSIMISTIC_WRITE)
    @Query("select draft from ClothingVisionDraft draft where draft.id = :id")
    Optional<ClothingVisionDraft> findForUpdate(@Param("id") UUID id);

    Optional<ClothingVisionDraft> findByClothingItemId(Long clothingItemId);
}

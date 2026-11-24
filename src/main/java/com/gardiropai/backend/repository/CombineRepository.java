package com.gardiropai.backend.repository;

import com.gardiropai.backend.entity.Combine;
import jakarta.persistence.LockModeType;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Lock;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.stereotype.Repository;

import java.util.List;
import java.util.Optional;

@Repository
public interface CombineRepository extends JpaRepository<Combine,Long> {
    List<Combine> findByUserIdOrderByCreatedAtDesc(Long userId);

    @Lock(LockModeType.PESSIMISTIC_WRITE)
    @Query("select outfit from Combine outfit where outfit.id = :combineId")
    Optional<Combine> findForUpdate(@Param("combineId") Long combineId);

    @Query("select distinct item.id from Combine outfit join outfit.clothingItems item where outfit.id = :combineId")
    List<Long> findClothingIds(@Param("combineId") Long combineId);
}

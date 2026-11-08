package com.gardiropai.backend.repository;

import com.gardiropai.backend.entity.Combine;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.List;

@Repository
public interface CombineRepository extends JpaRepository<Combine,Long> {
    List<Combine> findByUserIdOrderByCreatedAtDesc(Long userId);
}

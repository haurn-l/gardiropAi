package com.gardiropai.backend.repository;

import com.gardiropai.backend.entity.User;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.Optional;

public interface UserRepository extends JpaRepository<User, Long> {
    boolean existsByUsername(String username);

    Optional<User> findFirstByOrderByIdAsc();
}

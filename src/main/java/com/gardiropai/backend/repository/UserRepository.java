package com.gardiropai.backend.repository;

import com.gardiropai.backend.entity.User;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Modifying;
import org.springframework.data.jpa.repository.Query;

import java.util.Optional;

public interface UserRepository extends JpaRepository<User, Long> {
    boolean existsByUsername(String username);

    Optional<User> findFirstByOrderByIdAsc();

    @Modifying
    @Query(value = "insert into users (username) values ('demo') on conflict (username) do nothing",
           nativeQuery = true)
    void ensureDemoUser();
}

package com.gardiropai.backend.repository;

import com.gardiropai.backend.entity.ChatSession;
import jakarta.persistence.LockModeType;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Lock;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

import java.util.List;
import java.util.Optional;

public interface ChatSessionRepository extends JpaRepository<ChatSession, Long> {
    List<ChatSession> findByUserIdOrderByCreatedAtDescIdDesc(Long userId);

    Optional<ChatSession> findByIdAndUserId(Long id, Long userId);

    @Lock(LockModeType.PESSIMISTIC_WRITE)
    @Query("select chat from ChatSession chat where chat.id = :id and chat.user.id = :userId")
    Optional<ChatSession> findForDraftUpdate(@Param("id") Long id, @Param("userId") Long userId);
}

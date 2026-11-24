package com.gardiropai.backend.repository;

import com.gardiropai.backend.entity.ChatSession;
import jakarta.persistence.LockModeType;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Lock;
import org.springframework.data.jpa.repository.Modifying;
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

    @Modifying(flushAutomatically = true)
    @Query("""
            update ChatSession chat
            set chat.savedCombineId = null, chat.draftVersion = chat.draftVersion + 1
            where chat.savedCombineId = :combineId
            """)
    void clearSavedCombine(@Param("combineId") Long combineId);

    @Modifying
    @Query("""
            update ChatSession chat
            set chat.savedCombineId = null, chat.draftVersion = chat.draftVersion + 1
            where chat.savedCombineId is not null
              and not exists (select 1 from Combine outfit where outfit.id = chat.savedCombineId)
            """)
    void clearOrphanedSavedCombines();
}

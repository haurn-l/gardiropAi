package com.gardiropai.backend.service;

import com.gardiropai.backend.dto.request.ClothingCreateRequest;
import com.gardiropai.backend.entity.ClothingItem;
import com.gardiropai.backend.enums.ItemStatus;

import java.util.List;

/**
 * Kıyafet işlemleri için gerekli iş mantığı metotlarının tanımlandığı arayüz.
 */
public interface ClothingService {
    ClothingItem addClothingItem(ClothingCreateRequest request);
    List<ClothingItem> getAllCleanClothesByUser(Long userId);
    List<ClothingItem> getAllClothesByUser(Long userId);
    ClothingItem updateClothingStatus(Long itemId, ItemStatus newStatus);
    void deleteClothing(Long itemId);
}

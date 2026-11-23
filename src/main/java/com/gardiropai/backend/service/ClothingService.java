package com.gardiropai.backend.service;

import com.gardiropai.backend.dto.request.ClothingCreateRequest;
import com.gardiropai.backend.dto.response.ClothingResponse;
import com.gardiropai.backend.enums.Category;
import com.gardiropai.backend.enums.ItemStatus;

import java.util.List;

/**
 * Kıyafet işlemleri için gerekli iş mantığı metotlarının tanımlandığı arayüz.
 */
public interface ClothingService {
    ClothingResponse addClothingItem(ClothingCreateRequest request);
    List<ClothingResponse> getAllCleanClothesByUser(Long userId);
    List<ClothingResponse> getAllClothesByUser(Long userId);
    List<ClothingResponse> getAllClothes(ItemStatus status, Category category,
                                         String query, String tag, Boolean favorite);
    ClothingResponse getClothing(Long itemId);
    ClothingResponse updateClothingStatus(Long itemId, ItemStatus newStatus);
    ClothingResponse updateFavorite(Long itemId, boolean favorite);
    ClothingResponse rateClothing(Long itemId, int ratingScore);
    void deleteClothing(Long itemId);
}

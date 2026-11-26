package com.gardiropai.backend.service;

import com.gardiropai.backend.dto.request.ClothingCreateRequest;
import com.gardiropai.backend.dto.request.ClothingDetailsRequest;
import com.gardiropai.backend.dto.response.ClothingResponse;
import com.gardiropai.backend.enums.Category;
import com.gardiropai.backend.enums.ItemStatus;

import java.util.List;
import java.util.UUID;

/**
 * Kıyafet işlemleri için gerekli iş mantığı metotlarının tanımlandığı arayüz.
 */
public interface ClothingService {
    ClothingResponse addClothingItem(ClothingCreateRequest request);
    ClothingResponse confirmPhoto(UUID uploadId, ClothingDetailsRequest request);
    ClothingResponse saveVisionClothing(String frontImageUrl, String backImageUrl, ClothingDetailsRequest request);
    ClothingResponse updateDetails(Long itemId, ClothingDetailsRequest request);
    List<ClothingResponse> getAllCleanClothesByUser(Long userId);
    List<ClothingResponse> getAllClothesByUser(Long userId);
    List<ClothingResponse> getAllClothes(ItemStatus status, Category category,
                                         String query, String tag, Boolean favorite);
    ClothingResponse getClothing(Long itemId);
    ClothingResponse updateClothingStatus(Long itemId, ItemStatus newStatus);
    ClothingResponse markWorn(Long itemId);
    ClothingResponse updateFavorite(Long itemId, boolean favorite);
    ClothingResponse rateClothing(Long itemId, Integer ratingScore);
    void deleteClothing(Long itemId);
}

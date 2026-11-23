package com.gardiropai.backend.serviceIMPL;

import com.gardiropai.backend.dto.request.ClothingCreateRequest;
import com.gardiropai.backend.dto.response.ClothingResponse;
import com.gardiropai.backend.entity.ClothingItem;
import com.gardiropai.backend.entity.User;
import com.gardiropai.backend.enums.Category;
import com.gardiropai.backend.enums.ItemStatus;
import com.gardiropai.backend.exception.UserNotFoundException;
import com.gardiropai.backend.exception.ClothingNotFoundException;
import com.gardiropai.backend.mapper.ClothingResponseMapper;
import com.gardiropai.backend.repository.ClothingItemRepository;
import com.gardiropai.backend.repository.UserRepository;
import com.gardiropai.backend.service.ClothingService;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import tools.jackson.databind.json.JsonMapper;

import java.util.List;
import java.util.Locale;

/**
 * İş mantığının çalıştırıldığı, veritabanı kayıtlarının yapıldığı ana sınıf.
 */
@Service
@RequiredArgsConstructor
@Transactional(readOnly = true)
public class ClothingServiceImpl implements ClothingService {

    private static final Locale TURKISH = Locale.forLanguageTag("tr-TR");

    private final ClothingItemRepository clothingRepository;
    private final UserRepository userRepository;
    private final ClothingResponseMapper responseMapper;
    private final JsonMapper jsonMapper;

    @Override
    @Transactional
    public ClothingResponse addClothingItem(ClothingCreateRequest request) {
        User user = userRepository.findById(request.getUserId())
                .orElseThrow(() -> new UserNotFoundException("Kullanıcı bulunamadı. ID:" + request.getUserId()));

        ClothingItem newItem = ClothingItem.builder()
                .user(user)
                .name(request.getName())
                .imageUrl(request.getImageUrl())
                .category(request.getCategory())
                .subCategory(request.getSubCategory())
                .season(request.getSeason())
                .color(request.getColor())
                .hasPrint(request.getHasPrint())
                .customTags(request.getTags() == null ? null : jsonMapper.writeValueAsString(request.getTags()))
                .status(ItemStatus.TEMIZ)
                .build();

        return responseMapper.toResponse(clothingRepository.save(newItem));
    }

    @Override
    public List<ClothingResponse> getAllClothesByUser(Long userId) {
        return clothingRepository.findByUserId(userId).stream()
                .map(responseMapper::toResponse)
                .toList();
    }

    @Override
    public List<ClothingResponse> getWardrobe(Long userId, ItemStatus status, Category category,
                                             String query, String tag, Boolean favorite) {
        Long wardrobeUserId = userId != null
                ? userId
                : userRepository.findFirstByOrderByIdAsc().map(User::getId).orElse(null);
        if (wardrobeUserId == null) {
            return List.of();
        }

        String searchTerm = normalize(query);
        String tagFilter = normalize(tag);
        return clothingRepository.findWardrobeItems(wardrobeUserId, status, category, favorite).stream()
                .map(responseMapper::toResponse)
                .filter(item -> searchTerm.isEmpty() || matchesSearch(item, searchTerm))
                .filter(item -> tagFilter.isEmpty()
                        || item.getTags().stream().map(this::normalize).anyMatch(tagFilter::equals))
                .toList();
    }

    @Override
    public ClothingResponse getClothing(Long itemId) {
        return responseMapper.toResponse(findClothing(itemId));
    }

    @Override
    @Transactional
    public ClothingResponse updateClothingStatus(Long itemId, ItemStatus newStatus) {
        ClothingItem item = findClothing(itemId);
        item.setStatus(newStatus);
        return responseMapper.toResponse(item);
    }

    @Override
    @Transactional
    public ClothingResponse updateFavorite(Long itemId, boolean favorite) {
        ClothingItem item = findClothing(itemId);
        item.setFavorite(favorite);
        return responseMapper.toResponse(item);
    }

    @Override
    @Transactional
    public ClothingResponse rateClothing(Long itemId, int ratingScore) {
        ClothingItem item = findClothing(itemId);
        item.setUserRating(ratingScore);
        return responseMapper.toResponse(item);
    }

    @Override
    @Transactional
    public void deleteClothing(Long itemId) {
        if (!clothingRepository.existsById(itemId)) {
            throw new ClothingNotFoundException("Silinecek kıyafet bulunamadı. ID:" + itemId);
        }
        clothingRepository.deleteById(itemId);
    }

    @Override
    public List<ClothingResponse> getAllCleanClothesByUser(Long userId) {
        return clothingRepository.findByUserIdAndStatus(userId, ItemStatus.TEMIZ).stream()
                .map(responseMapper::toResponse)
                .toList();
    }

    private ClothingItem findClothing(Long itemId) {
        return clothingRepository.findById(itemId)
                .orElseThrow(() -> new ClothingNotFoundException("Kıyafet bulunamadı. ID: " + itemId));
    }

    private boolean matchesSearch(ClothingResponse item, String term) {
        return normalize(item.getName()).contains(term)
                || normalize(item.getSubCategory()).contains(term)
                || normalize(item.getColor()).contains(term)
                || item.getTags().stream().map(this::normalize).anyMatch(tag -> tag.contains(term));
    }

    private String normalize(String value) {
        return value == null ? "" : value.strip().toLowerCase(TURKISH);
    }
}
package com.gardiropai.backend.serviceIMPL;

import com.gardiropai.backend.dto.request.ClothingCreateRequest;
import com.gardiropai.backend.entity.ClothingItem;
import com.gardiropai.backend.entity.User;
import com.gardiropai.backend.enums.ItemStatus;
import com.gardiropai.backend.repository.ClothingItemRepository;
import com.gardiropai.backend.repository.UserRepository;
import com.gardiropai.backend.service.ClothingService;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;

import java.util.List;

/**
 * İş mantığının çalıştırıldığı, veritabanı kayıtlarının yapıldığı ana sınıf.
 */
@Service
@RequiredArgsConstructor
public class ClothingServiceImpl implements ClothingService {

    private final ClothingItemRepository clothingRepository;
    private final UserRepository userRepository; // User entity'sini bulmak için

    @Override
    public ClothingItem addClothingItem(ClothingCreateRequest request) {
        // Kullanıcıyı veritabanından bul
        User user = userRepository.findById(request.getUserId())
                .orElseThrow(() -> new RuntimeException("Kullanıcı bulunamadi"));

        // DTO'dan gelen veriyi Entity'e çevir ve veritabanına kaydet
        ClothingItem newItem = ClothingItem.builder()
                .user(user)
                .imageUrl(request.getImageUrl())
                .category(request.getCategory())
                .season(request.getSeason())
                .color(request.getColor())
                .status(ItemStatus.TEMIZ) // Yeni eklenen parça varsayılan olarak TEMIZdir
                .build();

        return clothingRepository.save(newItem);
    }
    @Override
    public List<ClothingItem> getAllClothesByUser(Long userId) {
        return clothingRepository.findByUserId(userId);
    }
    @Override
    public ClothingItem updateClothingStatus(Long itemId, ItemStatus newStatus) { // Temiz import kullanımı
        ClothingItem item = clothingRepository.findById(itemId)
                .orElseThrow(() -> new RuntimeException("Kıyafet bulunamadı. ID: " + itemId));

        item.setStatus(newStatus);
        return clothingRepository.save(item);
    }
    @Override
    public void deleteClothing(Long itemId) {
        if (!clothingRepository.existsById(itemId)) {
            throw new RuntimeException("Silinecek kıyafet bulunamadı.");
        }
        clothingRepository.deleteById(itemId);
    }
    @Override
    public List<ClothingItem> getAllCleanClothesByUser(Long userId) {
        return clothingRepository.findByUserIdAndStatus(userId, ItemStatus.TEMIZ);
    }
}
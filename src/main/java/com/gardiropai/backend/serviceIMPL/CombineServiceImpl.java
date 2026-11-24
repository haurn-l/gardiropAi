package com.gardiropai.backend.serviceIMPL;

import com.gardiropai.backend.dto.request.CombineCreateRequest;
import com.gardiropai.backend.dto.response.CombineResponse;
import com.gardiropai.backend.entity.ClothingItem;
import com.gardiropai.backend.entity.Combine;
import com.gardiropai.backend.entity.User;
import com.gardiropai.backend.exception.ClothingNotFoundException;
import com.gardiropai.backend.exception.CombineNotFoundException;
import com.gardiropai.backend.exception.UserNotFoundException;
import com.gardiropai.backend.mapper.ClothingResponseMapper;
import com.gardiropai.backend.repository.ChatSessionRepository;
import com.gardiropai.backend.repository.ClothingItemRepository;
import com.gardiropai.backend.repository.CombineRepository;
import com.gardiropai.backend.repository.UserRepository;
import com.gardiropai.backend.service.CombineService;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDateTime;
import java.util.List;
import java.util.stream.Collectors;

@Service
@RequiredArgsConstructor
public class CombineServiceImpl implements CombineService {

    private final CombineRepository combineRepository;
    private final UserRepository userRepository;
    private final ClothingItemRepository clothingRepository;
    private final ClothingResponseMapper clothingResponseMapper;
    private final ClothingCareService clothingCare;
    private final ChatSessionRepository chatSessions;

    @Override
    @Transactional
    public CombineResponse createCombine(CombineCreateRequest request) {
        //Kullanıcıyı bul
        User user = userRepository.findById(request.getUserId())
                .orElseThrow(() -> new UserNotFoundException("Kullanıcı bulunamadı. ID: " + request.getUserId()));

        //Kıyafetleri veritabanından getir
        List<ClothingItem> clothingItems = clothingRepository.findAllById(request.getClothingItemIds());

        //İstenen kıyafet sayısı ile veritabanında bulunan eşleşiyor mu
        if (clothingItems.size() != request.getClothingItemIds().size()) {
            throw new ClothingNotFoundException("Kombin için seçilen bazı kıyafetler veritabanında bulunamadı.");
        }

        //Seçilen kıyafetlerin hepsi bu kullanıcıya mı ait
        boolean allBelongToUser = clothingItems.stream()
                .allMatch(item -> item.getUser().getId().equals(user.getId()));
        if (!allBelongToUser) {
            throw new ClothingNotFoundException("Seçilen kıyafetlerden bazıları bu kullanıcıya ait değil!");
        }

        //Yeni Combine nesnesini oluştur ve kaydet
        Combine combine = Combine.builder()
                .user(user)
                .clothingItems(clothingItems)
                .ratingScore(request.getRatingScore())
                .favorite(Boolean.TRUE.equals(request.getFavorite()))
                .createdAt(LocalDateTime.now()) // Ne zaman oluşturulduğu bilgisini ekliyoruz
                .build();

        Combine savedCombine = combineRepository.save(combine);

        //DTO'ya dönüştürüp döndür
        return convertToCombineResponse(savedCombine);
    }

    @Override
    @Transactional(readOnly = true)
    public List<CombineResponse> getUserCombines(Long userId) {
        // Kullanıcı var mı kontrolü
        if (!userRepository.existsById(userId)) {
            throw new UserNotFoundException("Kullanıcı bulunamadı. ID: " + userId);
        }

        // Repository'e yazdığımız o sihirli metotla kullanıcı kombinlerini tarihe göre azalan sırayla getiriyoruz
        List<Combine> combines = combineRepository.findByUserIdOrderByCreatedAtDesc(userId);

        // Listeyi tek bir satırda Stream ile DTO listesine çeviriyoruz
        return combines.stream()
                .map(this::convertToCombineResponse)
                .collect(Collectors.toList());
    }

    @Override
    @Transactional
    public CombineResponse rateCombine(Long combineId, Integer ratingScore) {
        // Kombini bul
        Combine combine = combineRepository.findById(combineId)
                .orElseThrow(() -> new CombineNotFoundException("Puan verilecek kombin bulunamadı. ID: " + combineId));

        // Puanı güncelle
        combine.setRatingScore(ratingScore);

        // Kaydet ve DTO'ya çevir
        Combine updatedCombine = combineRepository.save(combine);
        return convertToCombineResponse(updatedCombine);
    }

    @Override
    @Transactional
    public CombineResponse updateFavorite(Long combineId, boolean favorite) {
        Combine combine = combineRepository.findById(combineId)
                .orElseThrow(() -> new CombineNotFoundException("Kombin bulunamadı. ID: " + combineId));
        combine.setFavorite(favorite);
        return convertToCombineResponse(combine);
    }

    @Override
    @Transactional
    public CombineResponse markWorn(Long combineId) {
        Combine combine = combineRepository.findForUpdate(combineId)
                .orElseThrow(() -> new CombineNotFoundException("Kombin bulunamadı. ID: " + combineId));

        clothingCare.markWornItems(combineRepository.findClothingIds(combineId));
        return convertToCombineResponse(combine);
    }

    @Override
    @Transactional
    public void deleteCombine(Long combineId) {
        Combine combine = combineRepository.findForUpdate(combineId)
                .orElseThrow(() -> new CombineNotFoundException("Silinecek kombin bulunamadı. ID: " + combineId));
        chatSessions.clearSavedCombine(combineId);
        combineRepository.delete(combine);
    }

    // --- YARDIMCI METOTLAR (ENTITY -> DTO DÖNÜŞÜMÜ) ---

    private CombineResponse convertToCombineResponse(Combine combine) {
        return CombineResponse.builder()
                .id(combine.getId())
                .userId(combine.getUser().getId())
                .clothingItems(combine.getClothingItems().stream()
                        .map(clothingResponseMapper::toResponse)
                        .collect(Collectors.toList()))
                .ratingScore(combine.getRatingScore())
                .favorite(combine.isFavorite())
                .createdAt(combine.getCreatedAt())
                .build();
    }
}

package com.gardiropai.backend.controller;

import com.gardiropai.backend.dto.request.ClothingCreateRequest;
import com.gardiropai.backend.entity.ClothingItem;
import com.gardiropai.backend.enums.ItemStatus;
import com.gardiropai.backend.service.ClothingService;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.List;

/**
 * Mobil uygulamanın HTTP istekleri atacağı REST Endpoints
 */
@RestController
@RequestMapping("/api/clothes") // Bu controller'ın temel URL yolu
@RequiredArgsConstructor
public class ClothingController {

    private final ClothingService clothingService;

    // POST isteği ile kıyafet ekleme
    @PostMapping("/add")
    public ResponseEntity<ClothingItem> addCloth(@Valid @RequestBody ClothingCreateRequest request) {
        ClothingItem savedItem = clothingService.addClothingItem(request);
        return ResponseEntity.ok(savedItem);
    }
    @GetMapping("/all/{userId}")
    public ResponseEntity<List<ClothingItem>> getAllClothes(@PathVariable Long userId) {
        return ResponseEntity.ok(clothingService.getAllClothesByUser(userId));
    }
    @GetMapping("/clean/{userId}")
    public ResponseEntity<List<ClothingItem>> getCleanClothes(@PathVariable Long userId) {
        return ResponseEntity.ok(clothingService.getAllCleanClothesByUser(userId));
    }

    // 3. YENİ METOT: Kıyafetin durumunu güncelle (Örn: Giyildi, kirlendi)
    @PutMapping("/{itemId}/status")
    public ResponseEntity<ClothingItem> updateStatus(
            @PathVariable Long itemId,
            @RequestParam ItemStatus status) {

        return ResponseEntity.ok(clothingService.updateClothingStatus(itemId, status));
    }


    // 4. YENİ METOT: Kıyafeti gardıroptan sil
    @DeleteMapping("/{itemId}")
    public ResponseEntity<Void> deleteCloth(@PathVariable Long itemId) {
        clothingService.deleteClothing(itemId);
        return ResponseEntity.noContent().build(); // 204 No Content döndürür
    }
}
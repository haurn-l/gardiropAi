package com.gardiropai.backend.controller;

import com.gardiropai.backend.dto.request.ClothingCreateRequest;
import com.gardiropai.backend.entity.ClothingItem;
import com.gardiropai.backend.service.ClothingService;
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
    public ResponseEntity<ClothingItem> addCloth(@RequestBody ClothingCreateRequest request) {
        ClothingItem savedItem = clothingService.addClothingItem(request);
        return ResponseEntity.ok(savedItem);
    }

    // GET isteği ile kullanıcının TEMIZ kıyafetlerini çekme
    @GetMapping("/clean/{userId}")
    public ResponseEntity<List<ClothingItem>> getCleanClothes(@PathVariable Long userId) {
        List<ClothingItem> cleanClothes = clothingService.getAllCleanClothesByUser(userId);
        return ResponseEntity.ok(cleanClothes);
    }
}
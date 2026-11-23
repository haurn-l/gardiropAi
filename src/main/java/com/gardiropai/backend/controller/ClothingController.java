package com.gardiropai.backend.controller;

import com.gardiropai.backend.dto.request.ClothingCreateRequest;
import com.gardiropai.backend.dto.response.ClothingResponse;
import com.gardiropai.backend.enums.Category;
import com.gardiropai.backend.enums.ItemStatus;
import com.gardiropai.backend.service.ClothingService;
import jakarta.validation.Valid;
import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
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

    @PostMapping("/add")
    public ResponseEntity<ClothingResponse> addCloth(@Valid @RequestBody ClothingCreateRequest request) {
        return ResponseEntity.ok(clothingService.addClothingItem(request));
    }

    @GetMapping
    public ResponseEntity<List<ClothingResponse>> getWardrobe(
            @RequestParam(required = false) Long userId,
            @RequestParam(required = false) ItemStatus status,
            @RequestParam(required = false) Category category,
            @RequestParam(name = "q", required = false) String query,
            @RequestParam(required = false) String tag,
            @RequestParam(required = false) Boolean favorite) {
        return ResponseEntity.ok(clothingService.getWardrobe(userId, status, category, query, tag, favorite));
    }

    @GetMapping("/all/{userId}")
    public ResponseEntity<List<ClothingResponse>> getAllClothes(@PathVariable Long userId) {
        return ResponseEntity.ok(clothingService.getAllClothesByUser(userId));
    }

    @GetMapping("/clean/{userId}")
    public ResponseEntity<List<ClothingResponse>> getCleanClothes(@PathVariable Long userId) {
        return ResponseEntity.ok(clothingService.getAllCleanClothesByUser(userId));
    }

    @GetMapping("/{itemId}")
    public ResponseEntity<ClothingResponse> getClothing(@PathVariable Long itemId) {
        return ResponseEntity.ok(clothingService.getClothing(itemId));
    }

    @PutMapping("/{itemId}/status")
    public ResponseEntity<ClothingResponse> updateStatus(
            @PathVariable Long itemId,
            @RequestParam ItemStatus status) {
        return ResponseEntity.ok(clothingService.updateClothingStatus(itemId, status));
    }

    @PutMapping("/{itemId}/favorite")
    public ResponseEntity<ClothingResponse> updateFavorite(
            @PathVariable Long itemId, @RequestParam boolean favorite) {
        return ResponseEntity.ok(clothingService.updateFavorite(itemId, favorite));
    }

    @PatchMapping("/{itemId}/rate")
    public ResponseEntity<ClothingResponse> rateClothing(
            @PathVariable Long itemId, @RequestParam @Min(1) @Max(5) int ratingScore) {
        return ResponseEntity.ok(clothingService.rateClothing(itemId, ratingScore));
    }

    @DeleteMapping("/{itemId}")
    public ResponseEntity<Void> deleteCloth(@PathVariable Long itemId) {
        clothingService.deleteClothing(itemId);
        return ResponseEntity.noContent().build();
    }
}
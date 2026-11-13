package com.gardiropai.backend.controller;

import com.gardiropai.backend.dto.request.CombineCreateRequest;
import com.gardiropai.backend.dto.response.CombineResponse;
import com.gardiropai.backend.service.CombineService;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.List;

/**
 * Kombin (Combine) işlemleri için REST API uç noktaları.
 * İstemciye Entity sızdırmadan yalnızca DTO nesneleri (CombineResponse) döner.
 */
@RestController
@RequestMapping("/api/v1/combines")
@RequiredArgsConstructor
public class CombineController {

    private final CombineService combineService;

    //Yeni kombin oluşturma (201 CREATED döner)
    @PostMapping
    public ResponseEntity<CombineResponse> createCombine(@Valid @RequestBody CombineCreateRequest request) {
        CombineResponse response = combineService.createCombine(request);
        return new ResponseEntity<>(response, HttpStatus.CREATED);
    }

    //Kullanıcının tüm kombinlerini listeleme (200 OK döner)
    @GetMapping("/user/{userId}")
    public ResponseEntity<List<CombineResponse>> getUserCombines(@PathVariable Long userId) {
        List<CombineResponse> combines = combineService.getUserCombines(userId);
        return ResponseEntity.ok(combines);
    }

    //Kombine puan verme
    @PatchMapping("/{combineId}/rate")
    public ResponseEntity<CombineResponse> rateCombine(
            @PathVariable Long combineId,
            @RequestParam Integer ratingScore) { // URL'de ?ratingScore=5 şeklinde gelir
        CombineResponse response = combineService.rateCombine(combineId, ratingScore);
        return ResponseEntity.ok(response);
    }

    //Kombini silme (İçerik dönmez, 204 NO CONTENT döner)
    @DeleteMapping("/{combineId}")
    public ResponseEntity<Void> deleteCombine(@PathVariable Long combineId) {
        combineService.deleteCombine(combineId);
        return ResponseEntity.noContent().build();
    }
}
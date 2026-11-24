package com.gardiropai.backend.controller;

import com.gardiropai.backend.dto.request.ClothingDetailsRequest;
import com.gardiropai.backend.dto.response.ClothingResponse;
import com.gardiropai.backend.dto.response.PhotoDraftResponse;
import com.gardiropai.backend.service.ClothingService;
import com.gardiropai.backend.serviceIMPL.LocalClothingPhotos;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.core.io.Resource;
import org.springframework.http.CacheControl;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.multipart.MultipartFile;

import java.io.IOException;
import java.util.UUID;

@RestController
@RequestMapping("/api/clothes")
@RequiredArgsConstructor
public class ClothingPhotoController {
    private final LocalClothingPhotos photos;
    private final ClothingService clothingService;

    @PostMapping(path = "/photo-drafts", consumes = MediaType.MULTIPART_FORM_DATA_VALUE)
    @ResponseStatus(HttpStatus.CREATED)
    public PhotoDraftResponse upload(@RequestPart("photo") MultipartFile photo) throws IOException {
        return photos.upload(photo);
    }

    @GetMapping("/photos/{id}")
    public ResponseEntity<Resource> read(@PathVariable UUID id) {
        LocalClothingPhotos.StoredPhoto photo = photos.read(id);
        return ResponseEntity.ok()
                .cacheControl(CacheControl.noCache())
                .contentType(photo.contentType())
                .body(photo.resource());
    }

    @PostMapping("/photo-drafts/{id}/confirm")
    @ResponseStatus(HttpStatus.CREATED)
    public ClothingResponse confirm(@PathVariable UUID id, @Valid @RequestBody ClothingDetailsRequest request) {
        return clothingService.confirmPhoto(id, request);
    }

    @DeleteMapping("/photo-drafts/{id}")
    @ResponseStatus(HttpStatus.NO_CONTENT)
    public void discard(@PathVariable UUID id) {
        photos.discard(id);
    }
}

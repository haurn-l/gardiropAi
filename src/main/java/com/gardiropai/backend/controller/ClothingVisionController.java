package com.gardiropai.backend.controller;

import com.gardiropai.backend.dto.request.VisionConfirmRequest;
import com.gardiropai.backend.dto.response.ClothingResponse;
import com.gardiropai.backend.dto.response.VisionDraftResponse;
import com.gardiropai.backend.enums.Category;
import com.gardiropai.backend.enums.PhotoView;
import com.gardiropai.backend.serviceIMPL.ClothingVisionService;
import jakarta.validation.Valid;
import jakarta.validation.constraints.Positive;
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
@RequestMapping("/api/clothes/vision-drafts")
@RequiredArgsConstructor
public class ClothingVisionController {
    private final ClothingVisionService vision;

    @PostMapping(path = "/start", consumes = MediaType.MULTIPART_FORM_DATA_VALUE)
    @ResponseStatus(HttpStatus.ACCEPTED)
    public VisionDraftResponse start(@RequestParam UUID draftId, @RequestParam Category category,
                                     @RequestPart("photo") MultipartFile photo) throws IOException {
        return vision.start(draftId, category, photo);
    }

    @PutMapping(path = "/{id}/views/{view}", consumes = MediaType.MULTIPART_FORM_DATA_VALUE)
    @ResponseStatus(HttpStatus.ACCEPTED)
    public VisionDraftResponse submit(@PathVariable UUID id, @PathVariable PhotoView view, @RequestParam UUID captureId,
                                      @RequestParam @Positive int revision, @RequestPart("photo") MultipartFile photo)
            throws IOException {
        return vision.submit(id, view, captureId, revision, photo);
    }

    @GetMapping("/{id}")
    public VisionDraftResponse detail(@PathVariable UUID id) {
        return vision.get(id);
    }

    @GetMapping("/{id}/images/{view}")
    public ResponseEntity<Resource> image(@PathVariable UUID id, @PathVariable PhotoView view,
                                          @RequestParam @Positive int revision) {
        return ResponseEntity.ok().cacheControl(CacheControl.noCache())
                .contentType(MediaType.parseMediaType("image/webp")).body(vision.image(id, view, revision));
    }

    @PostMapping("/{id}/confirm")
    @ResponseStatus(HttpStatus.CREATED)
    public ClothingResponse confirm(@PathVariable UUID id, @Valid @RequestBody VisionConfirmRequest request)
            throws IOException {
        return vision.confirm(id, request);
    }

    @DeleteMapping("/{id}")
    @ResponseStatus(HttpStatus.NO_CONTENT)
    public void discard(@PathVariable UUID id, @RequestParam @Positive int revision) {
        vision.discard(id, revision);
    }
}

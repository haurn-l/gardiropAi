package com.gardiropai.backend.serviceIMPL;

import com.gardiropai.backend.dto.response.PhotoDraftResponse;
import com.gardiropai.backend.entity.ClothingPhoto;
import com.gardiropai.backend.repository.ClothingPhotoRepository;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.core.io.FileSystemResource;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.transaction.support.TransactionSynchronization;
import org.springframework.transaction.support.TransactionSynchronizationManager;
import org.springframework.web.multipart.MultipartFile;
import org.springframework.web.server.ResponseStatusException;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardOpenOption;
import java.util.HexFormat;
import java.util.UUID;

@Service
public class LocalClothingPhotos {
    private static final Logger LOGGER = LoggerFactory.getLogger(LocalClothingPhotos.class);
    private static final String PHOTO_URL = "/api/clothes/photos/";
    private static final HexFormat HEX = HexFormat.of();

    private final ClothingPhotoRepository photos;
    private final Path originals;

    public LocalClothingPhotos(ClothingPhotoRepository photos,
                               @Value("${gardirop.photos.directory}") Path photoDirectory) {
        this.photos = photos;
        this.originals = photoDirectory.toAbsolutePath().normalize().resolve("originals");
    }

    public PhotoDraftResponse upload(MultipartFile image) throws IOException {
        byte[] bytes = image.getBytes();
        String header = HEX.formatHex(bytes, 0, Math.min(bytes.length, 8));
        String contentType;
        if (header.startsWith("ffd8ff")) {
            contentType = MediaType.IMAGE_JPEG_VALUE;
        } else if (header.equals("89504e470d0a1a0a")) {
            contentType = MediaType.IMAGE_PNG_VALUE;
        } else {
            throw new ResponseStatusException(HttpStatus.UNSUPPORTED_MEDIA_TYPE, "JPEG veya PNG fotoğraf seç.");
        }

        UUID id = UUID.randomUUID();
        Path file = photoPath(id, contentType);
        Files.createDirectories(originals);
        try {
            Files.write(file, bytes, StandardOpenOption.CREATE_NEW);
            photos.saveAndFlush(new ClothingPhoto(id, contentType));
        } catch (IOException | RuntimeException exception) {
            deleteOriginal(file);
            throw exception;
        }
        return new PhotoDraftResponse(id, url(id));
    }

    public ClothingPhoto lock(UUID id) {
        return photos.findForUpdate(id).orElseThrow(LocalClothingPhotos::missingPhoto);
    }

    public StoredPhoto read(UUID id) {
        ClothingPhoto photo = photos.findById(id).orElseThrow(LocalClothingPhotos::missingPhoto);
        FileSystemResource resource = new FileSystemResource(photoPath(id, photo.getContentType()));
        if (!resource.isReadable()) {
            throw missingPhoto();
        }
        return new StoredPhoto(resource, MediaType.parseMediaType(photo.getContentType()));
    }

    @Transactional
    public void discard(UUID id) {
        photos.findForUpdate(id).filter(photo -> photo.getClothingItemId() == null).ifPresent(this::remove);
    }

    public void removeForClothing(Long clothingItemId) {
        photos.findByClothingItemId(clothingItemId).ifPresent(this::remove);
    }

    public String url(UUID id) {
        return PHOTO_URL + id;
    }

    private Path photoPath(UUID id, String contentType) {
        String extension = MediaType.IMAGE_PNG_VALUE.equals(contentType) ? ".png" : ".jpg";
        return originals.resolve(id + extension);
    }

    private static ResponseStatusException missingPhoto() {
        return new ResponseStatusException(HttpStatus.NOT_FOUND, "Fotoğraf bulunamadı.");
    }

    private void remove(ClothingPhoto photo) {
        Path file = photoPath(photo.getId(), photo.getContentType());
        photos.delete(photo);
        TransactionSynchronizationManager.registerSynchronization(new TransactionSynchronization() {
            @Override
            public void afterCommit() {
                deleteOriginal(file);
            }
        });
    }

    private void deleteOriginal(Path file) {
        try {
            Files.deleteIfExists(file);
        } catch (IOException exception) {
            LOGGER.warn("Fotoğraf dosyası silinemedi: {}", file, exception);
        }
    }

    public record StoredPhoto(FileSystemResource resource, MediaType contentType) {}
}

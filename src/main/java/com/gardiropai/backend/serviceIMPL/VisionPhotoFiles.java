package com.gardiropai.backend.serviceIMPL;

import com.gardiropai.backend.entity.ClothingVisionDraft;
import com.gardiropai.backend.enums.PhotoView;
import com.gardiropai.backend.repository.ClothingVisionDraftRepository;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.core.io.FileSystemResource;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Component;
import org.springframework.transaction.support.TransactionSynchronization;
import org.springframework.transaction.support.TransactionSynchronizationManager;
import org.springframework.web.multipart.MultipartFile;
import org.springframework.web.server.ResponseStatusException;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.HexFormat;
import java.util.UUID;

@Component
public class VisionPhotoFiles {
    static final MediaType WEBP = MediaType.parseMediaType("image/webp");
    private static final Logger LOGGER = LoggerFactory.getLogger(VisionPhotoFiles.class);
    private final Path root;
    private final ClothingVisionDraftRepository drafts;

    public VisionPhotoFiles(@Value("${gardirop.photos.directory}") Path root, ClothingVisionDraftRepository drafts) {
        this.root = root.toAbsolutePath().normalize();
        this.drafts = drafts;
    }

    Upload readUpload(MultipartFile photo) throws IOException {
        byte[] bytes = photo.getBytes();
        String header = HexFormat.of().formatHex(bytes, 0, Math.min(bytes.length, 8));
        if (header.startsWith("ffd8ff")) return new Upload(bytes, MediaType.IMAGE_JPEG, ".jpg");
        if (header.equals("89504e470d0a1a0a")) return new Upload(bytes, MediaType.IMAGE_PNG, ".png");
        if (isWebp(bytes)) return new Upload(bytes, WEBP, ".webp");
        throw new ResponseStatusException(HttpStatus.UNSUPPORTED_MEDIA_TYPE, "JPEG, PNG veya WebP fotoğraf seç.");
    }

    static boolean isWebp(byte[] bytes) {
        return bytes.length >= 12
                && new String(bytes, 0, 4, StandardCharsets.US_ASCII).equals("RIFF")
                && new String(bytes, 8, 4, StandardCharsets.US_ASCII).equals("WEBP");
    }

    void saveOriginal(UUID draftId, PhotoView view, UUID captureId, Upload upload) throws IOException {
        Path dir = directory("originals", draftId);
        Files.createDirectories(dir);
        Files.write(dir.resolve(view + "-" + captureId + upload.extension()), upload.bytes());
    }

    void saveProcessed(UUID draftId, PhotoView view, byte[] bytes) throws IOException {
        Path path = processedPath(draftId, view);
        Files.createDirectories(path.getParent());
        Files.write(path, bytes);
    }

    FileSystemResource processed(UUID draftId, PhotoView view) {
        FileSystemResource file = new FileSystemResource(processedPath(draftId, view));
        if (!file.isReadable()) {
            throw new ResponseStatusException(HttpStatus.NOT_FOUND, "İşlenmiş fotoğraf bulunamadı.");
        }
        return file;
    }

    public void removeForClothing(Long clothingItemId) {
        drafts.findByClothingItemId(clothingItemId).ifPresent(this::remove);
    }

    void remove(ClothingVisionDraft draft) {
        UUID id = draft.getId();
        drafts.delete(draft);
        TransactionSynchronizationManager.registerSynchronization(new TransactionSynchronization() {
            @Override
            public void afterCommit() {
                removeDirectory(directory("originals", id));
                removeDirectory(directory("processed", id));
            }
        });
    }

    private Path processedPath(UUID draftId, PhotoView view) {
        return directory("processed", draftId).resolve(view + ".webp");
    }

    private Path directory(String storage, UUID draftId) {
        return root.resolve(storage).resolve(draftId.toString());
    }

    private void removeDirectory(Path directory) {
        if (!Files.isDirectory(directory)) return;
        try (var files = Files.list(directory)) {
            for (Path file : files.toList()) Files.deleteIfExists(file);
        } catch (IOException exception) {
            LOGGER.warn("Fotoğraf dosyaları silinemedi: {}", directory, exception);
            return;
        }
        try {
            Files.deleteIfExists(directory);
        } catch (IOException exception) {
            LOGGER.warn("Fotoğraf dizini silinemedi: {}", directory, exception);
        }
    }

    record Upload(byte[] bytes, MediaType contentType, String extension) {}
}

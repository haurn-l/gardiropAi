package com.gardiropai.backend.serviceIMPL;

import com.gardiropai.backend.dto.request.VisionConfirmRequest;
import com.gardiropai.backend.dto.response.ClothingResponse;
import com.gardiropai.backend.dto.response.VisionDraftResponse;
import com.gardiropai.backend.entity.ClothingVisionDraft;
import com.gardiropai.backend.enums.Category;
import com.gardiropai.backend.enums.PhotoView;
import com.gardiropai.backend.repository.ClothingVisionDraftRepository;
import com.gardiropai.backend.service.ClothingService;
import com.gardiropai.backend.serviceIMPL.ClothingVisionClient.Embedding;
import com.gardiropai.backend.serviceIMPL.ClothingVisionClient.Image;
import com.gardiropai.backend.serviceIMPL.ClothingVisionClient.Progress;
import com.gardiropai.backend.serviceIMPL.ClothingVisionClient.Result;
import lombok.RequiredArgsConstructor;
import org.springframework.core.io.ByteArrayResource;
import org.springframework.core.io.Resource;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.multipart.MultipartFile;
import org.springframework.web.server.ResponseStatusException;
import tools.jackson.databind.json.JsonMapper;

import java.io.IOException;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.Arrays;
import java.util.EnumSet;
import java.util.HexFormat;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.UUID;

@Service
@RequiredArgsConstructor
public class ClothingVisionService {
    private static final String ROUTE = "/api/clothes/vision-drafts/";
    private static final EnumSet<Category> SUPPORTED = EnumSet.of(Category.UST_GIYIM, Category.ALT_GIYIM, Category.DIS_GIYIM);

    private final ClothingVisionDraftRepository drafts;
    private final ClothingVisionClient model;
    private final VisionPhotoFiles files;
    private final ClothingService clothing;
    private final JsonMapper json;

    @Transactional(rollbackFor = IOException.class)
    public VisionDraftResponse start(UUID draftId, Category category, MultipartFile photo) throws IOException {
        if (!SUPPORTED.contains(category)) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "Model üst, alt ve dış giyimi destekliyor.");
        }
        var upload = files.readUpload(photo);
        Progress progress = model.start(draftId, category, upload);
        if (progress.jobId() == null || !progress.jobId().matches("[0-9a-f]{32}")) {
            throw invalidResult();
        }
        drafts.createIfMissing(draftId, progress.jobId());
        ClothingVisionDraft draft = lock(draftId);
        if (!draft.getModelJobId().equals(progress.jobId())) {
            throw new ResponseStatusException(HttpStatus.CONFLICT, "Bu taslak kimliği daha önce kullanıldı.");
        }
        if (draft.getClothingItemId() != null) return saved(draft);
        files.saveOriginal(draftId, PhotoView.FRONT, draftId, upload);
        return describe(draft, progress);
    }

    @Transactional(rollbackFor = IOException.class)
    public VisionDraftResponse submit(UUID draftId, PhotoView view, UUID captureId, int revision, MultipartFile photo)
            throws IOException {
        ClothingVisionDraft draft = lock(draftId);
        if (draft.getClothingItemId() != null) throw conflict();
        var upload = files.readUpload(photo);
        Progress progress = model.submit(draft.getModelJobId(), view, captureId, revision, upload);
        files.saveOriginal(draftId, view, captureId, upload);
        return describe(draft, progress);
    }

    public VisionDraftResponse get(UUID id) {
        ClothingVisionDraft draft = find(id);
        if (draft.getClothingItemId() != null) return saved(draft);
        return describe(draft, model.progress(draft.getModelJobId()));
    }

    public Resource image(UUID id, PhotoView view, int revision) {
        ClothingVisionDraft draft = find(id);
        if (draft.getSavedRevision() != null) {
            if (draft.getSavedRevision() != revision) throw conflict();
            return files.processed(id, view);
        }
        return new ByteArrayResource(imageBytes(result(draft, revision), view));
    }

    @Transactional(rollbackFor = IOException.class)
    public ClothingResponse confirm(UUID id, VisionConfirmRequest request) throws IOException {
        ClothingVisionDraft draft = lock(id);
        int revision = request.revision();
        if (draft.getClothingItemId() != null) {
            if (!draft.getSavedRevision().equals(revision)) throw conflict();
            return clothing.getClothing(draft.getClothingItemId());
        }
        Progress progress = model.progress(draft.getModelJobId());
        if (!ready(progress) || !Objects.equals(progress.resultRevision(), revision) || progress.revision() != revision) {
            throw conflict();
        }
        Result result = result(draft, revision);
        if (request.details().getCategory() != result.category()) {
            throw new ResponseStatusException(HttpStatus.CONFLICT, "Onay kategorisi analiz edilen kategoriyle eşleşmeli.");
        }
        Embedding embedding = model.embedding(draft.getModelJobId(), revision);
        validateEmbedding(result, embedding);
        byte[] front = imageBytes(result, PhotoView.FRONT);
        byte[] back = imageBytes(result, PhotoView.BACK);
        files.saveProcessed(id, PhotoView.FRONT, front);
        files.saveProcessed(id, PhotoView.BACK, back);
        ClothingResponse saved = clothing.saveVisionClothing(
                imageUrl(id, PhotoView.FRONT, revision), imageUrl(id, PhotoView.BACK, revision), request.details());
        draft.setEmbedding(json.writeValueAsString(embedding));
        draft.setSavedRevision(revision);
        draft.setClothingItemId(saved.getId());
        return saved;
    }

    @Transactional
    public void discard(UUID id, int revision) {
        ClothingVisionDraft draft = lock(id);
        if (draft.getClothingItemId() != null) throw conflict();
        try {
            model.cancel(draft.getModelJobId(), revision);
        } catch (ResponseStatusException exception) {
            if (!HttpStatus.GONE.equals(exception.getStatusCode())) throw exception;
        }
        files.remove(draft);
    }

    private VisionDraftResponse describe(ClothingVisionDraft draft, Progress progress) {
        if (!draft.getModelJobId().equals(progress.jobId()) || progress.revision() < 1 || progress.views() == null) {
            throw invalidResult();
        }
        Map<String, String> views = new LinkedHashMap<>();
        progress.views().forEach((view, data) -> views.put(view.name(), data.status()));
        if (ready(progress)) {
            if (!Objects.equals(progress.resultRevision(), progress.revision())) throw invalidResult();
            Result result = result(draft, progress.revision());
            return new VisionDraftResponse(draft.getId(), progress.revision(), progress.status(), progress.category(),
                    progress.expiresAt(), views, result.tags(), imageUrl(draft.getId(), PhotoView.FRONT, result.revision()),
                    imageUrl(draft.getId(), PhotoView.BACK, result.revision()), null, null);
        }
        return new VisionDraftResponse(draft.getId(), progress.revision(), progress.status(), progress.category(),
                progress.expiresAt(), views, null, null, null, progress.error(), null);
    }

    private VisionDraftResponse saved(ClothingVisionDraft draft) {
        ClothingResponse item = clothing.getClothing(draft.getClothingItemId());
        return new VisionDraftResponse(draft.getId(), draft.getSavedRevision(), "SAVED", item.getCategory(), null,
                Map.of(), null, item.getImageUrl(), item.getBackImageUrl(), null, item.getId());
    }

    private Result result(ClothingVisionDraft draft, int revision) {
        Result result = model.result(draft.getModelJobId(), revision);
        if (!draft.getModelJobId().equals(result.jobId()) || result.revision() != revision || result.images() == null) {
            throw invalidResult();
        }
        return result;
    }

    private byte[] imageBytes(Result result, PhotoView view) {
        Image image = result.images().get(view);
        if (image == null || !"image/webp".equals(image.contentType())) throw invalidResult();
        byte[] bytes = model.image(result.jobId(), result.revision(), view);
        if (!VisionPhotoFiles.isWebp(bytes) || bytes.length != image.byteLength() || !sha256(bytes).equalsIgnoreCase(image.sha256())) {
            throw invalidResult();
        }
        return bytes;
    }

    private static void validateEmbedding(Result result, Embedding embedding) {
        if (!result.jobId().equals(embedding.jobId()) || result.revision() != embedding.revision()
                || embedding.dimension() != 1536 || !"float32".equals(embedding.dtype())
                || !List.of(PhotoView.FRONT, PhotoView.BACK).equals(embedding.viewOrder())
                || embedding.values() == null || embedding.values().length != 1536
                || !Arrays.stream(embedding.values()).allMatch(Double::isFinite)
                || result.versions() == null || !Objects.equals(result.versions().embeddingRevision(), embedding.encoderRevision())
                || !Objects.equals(result.versions().fusionMethod(), embedding.fusionMethod())) {
            throw invalidResult();
        }
    }

    private ClothingVisionDraft find(UUID id) {
        return drafts.findById(id).orElseThrow(ClothingVisionService::notFound);
    }

    private ClothingVisionDraft lock(UUID id) {
        return drafts.findForUpdate(id).orElseThrow(ClothingVisionService::notFound);
    }

    private static boolean ready(Progress progress) {
        return "READY".equals(progress.status());
    }

    private static String imageUrl(UUID draftId, PhotoView view, int revision) {
        return ROUTE + draftId + "/images/" + view + "?revision=" + revision;
    }

    private static ResponseStatusException notFound() {
        return new ResponseStatusException(HttpStatus.NOT_FOUND, "Fotoğraf taslağı bulunamadı.");
    }

    private static ResponseStatusException conflict() {
        return new ResponseStatusException(HttpStatus.CONFLICT, "Fotoğraf sonucu henüz hazır değil veya sürümü değişti.");
    }

    private static ResponseStatusException invalidResult() {
        return new ResponseStatusException(HttpStatus.BAD_GATEWAY, "Görüntü işleme sonucu doğrulanamadı.");
    }

    private static String sha256(byte[] bytes) {
        try {
            return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(bytes));
        } catch (NoSuchAlgorithmException exception) {
            throw new IllegalStateException(exception);
        }
    }
}

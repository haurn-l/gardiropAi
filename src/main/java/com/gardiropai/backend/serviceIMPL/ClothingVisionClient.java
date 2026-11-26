package com.gardiropai.backend.serviceIMPL;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import com.gardiropai.backend.dto.response.VisionDraftResponse.Failure;
import com.gardiropai.backend.dto.response.VisionDraftResponse.Suggestions;
import com.gardiropai.backend.enums.Category;
import com.gardiropai.backend.enums.PhotoView;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.core.io.ByteArrayResource;
import org.springframework.http.HttpEntity;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.http.client.JdkClientHttpRequestFactory;
import org.springframework.stereotype.Component;
import org.springframework.util.LinkedMultiValueMap;
import org.springframework.util.MultiValueMap;
import org.springframework.web.client.ResourceAccessException;
import org.springframework.web.client.RestClient;
import org.springframework.web.client.RestClientException;
import org.springframework.web.client.RestClientResponseException;
import org.springframework.web.server.ResponseStatusException;

import java.net.http.HttpClient;
import java.time.Duration;
import java.time.Instant;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import java.util.function.Supplier;

@Component
public class ClothingVisionClient {
    private static final String JOBS = "/v1/clothing/jobs";
    private static final String JOB = JOBS + "/{jobId}";
    private static final String RESULT = JOB + "/results/{revision}";

    private final RestClient client;
    private final boolean configured;

    public ClothingVisionClient(@Value("${gardirop.vision.base-url}") String baseUrl,
                                @Value("${gardirop.vision.api-key}") String apiKey) {
        configured = !apiKey.isBlank();
        JdkClientHttpRequestFactory factory = new JdkClientHttpRequestFactory(
                HttpClient.newBuilder().connectTimeout(Duration.ofSeconds(3)).build());
        factory.setReadTimeout(Duration.ofSeconds(15));
        client = RestClient.builder().baseUrl(baseUrl).defaultHeader("X-API-Key", apiKey)
                .requestFactory(factory).build();
    }

    Progress start(UUID draftId, Category category, VisionPhotoFiles.Upload photo) {
        MultiValueMap<String, Object> form = form(photo, draftId);
        form.add("category", category.name());
        return read(() -> client.post().uri(JOBS).header("Idempotency-Key", draftId.toString())
                .contentType(MediaType.MULTIPART_FORM_DATA).body(form).retrieve().body(Progress.class));
    }

    Progress submit(String jobId, PhotoView view, UUID captureId, int revision, VisionPhotoFiles.Upload photo) {
        MultiValueMap<String, Object> form = form(photo, captureId);
        form.add("expectedRevision", Integer.toString(revision));
        return read(() -> client.put().uri(JOB + "/views/{view}", jobId, view.name())
                .contentType(MediaType.MULTIPART_FORM_DATA).body(form).retrieve().body(Progress.class));
    }

    Progress progress(String jobId) {
        return read(() -> client.get().uri(JOB, jobId).retrieve().body(Progress.class));
    }

    Result result(String jobId, int revision) {
        return read(() -> client.get().uri(RESULT, jobId, revision).retrieve().body(Result.class));
    }

    byte[] image(String jobId, int revision, PhotoView view) {
        return read(() -> client.get().uri(RESULT + "/images/{view}", jobId, revision, view.name())
                .retrieve().body(byte[].class));
    }

    Embedding embedding(String jobId, int revision) {
        return read(() -> client.get().uri(RESULT + "/embedding", jobId, revision).retrieve().body(Embedding.class));
    }

    void cancel(String jobId, int revision) {
        read(() -> client.delete().uri(JOB + "?expectedRevision={revision}", jobId, revision)
                .retrieve().toBodilessEntity());
    }

    private static MultiValueMap<String, Object> form(VisionPhotoFiles.Upload photo, UUID captureId) {
        MultiValueMap<String, Object> form = new LinkedMultiValueMap<>();
        HttpHeaders headers = new HttpHeaders();
        headers.setContentType(photo.contentType());
        headers.setContentDispositionFormData("image", "capture" + photo.extension());
        form.add("image", new HttpEntity<>(new ByteArrayResource(photo.bytes()), headers));
        form.add("captureId", captureId.toString());
        return form;
    }

    private <T> T read(Supplier<T> request) {
        if (!configured) {
            throw new ResponseStatusException(HttpStatus.SERVICE_UNAVAILABLE, "Görüntü işleme servisi yapılandırılmadı.");
        }
        try {
            T body = request.get();
            if (body == null) {
                throw new ResponseStatusException(HttpStatus.BAD_GATEWAY, "Görüntü işleme servisi boş yanıt döndürdü.");
            }
            return body;
        } catch (RestClientResponseException exception) {
            throw providerError(exception.getStatusCode().value());
        } catch (ResourceAccessException exception) {
            throw new ResponseStatusException(HttpStatus.SERVICE_UNAVAILABLE, "Görüntü işleme servisine ulaşılamadı.");
        } catch (RestClientException exception) {
            throw new ResponseStatusException(HttpStatus.BAD_GATEWAY, "Görüntü işleme yanıtı okunamadı.");
        }
    }

    private static ResponseStatusException providerError(int status) {
        return switch (status) {
            case 404, 410 -> new ResponseStatusException(HttpStatus.GONE, "Fotoğraf işinin süresi doldu veya iş silindi.");
            case 409 -> new ResponseStatusException(HttpStatus.CONFLICT, "Fotoğraf işi değişti. Taslağı yeniden yükle.");
            case 413, 415, 422 -> new ResponseStatusException(HttpStatus.valueOf(status), "Model fotoğrafı kabul etmedi.");
            case 429 -> new ResponseStatusException(HttpStatus.TOO_MANY_REQUESTS, "Görüntü işleme kuyruğu dolu. Tekrar dene.");
            default -> new ResponseStatusException(HttpStatus.BAD_GATEWAY, "Görüntü işleme servisi isteği tamamlayamadı.");
        };
    }

    @JsonIgnoreProperties(ignoreUnknown = true)
    record Progress(String jobId, int revision, Category category, String status, Instant expiresAt,
                    Map<PhotoView, ViewProgress> views, Integer resultRevision, Failure error) {}

    @JsonIgnoreProperties(ignoreUnknown = true)
    record ViewProgress(String status) {}

    @JsonIgnoreProperties(ignoreUnknown = true)
    record Result(String jobId, int revision, Category category, Suggestions tags, ModelVersions versions,
                  Map<PhotoView, Image> images) {}

    @JsonIgnoreProperties(ignoreUnknown = true)
    record ModelVersions(String embeddingRevision, String fusionMethod) {}

    @JsonIgnoreProperties(ignoreUnknown = true)
    record Image(String contentType, long byteLength, String sha256) {}

    @JsonIgnoreProperties(ignoreUnknown = true)
    record Embedding(String jobId, int revision, int dimension, String dtype, String model, String encoderRevision,
                     String fusionMethod, List<PhotoView> viewOrder, double[] values) {}
}

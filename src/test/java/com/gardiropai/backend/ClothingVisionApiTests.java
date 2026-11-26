package com.gardiropai.backend;

import com.sun.net.httpserver.HttpExchange;
import com.sun.net.httpserver.HttpServer;
import org.junit.jupiter.api.AfterAll;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.webmvc.test.autoconfigure.AutoConfigureMockMvc;
import org.springframework.http.HttpMethod;
import org.springframework.http.MediaType;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.mock.web.MockMultipartFile;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;
import org.springframework.test.web.servlet.MockMvc;
import tools.jackson.databind.JsonNode;
import tools.jackson.databind.json.JsonMapper;

import java.io.IOException;
import java.io.UncheckedIOException;
import java.net.InetSocketAddress;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.Base64;
import java.util.HexFormat;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import java.util.concurrent.CopyOnWriteArrayList;

import static org.assertj.core.api.Assertions.assertThat;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.delete;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.multipart;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.content;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@SpringBootTest
@AutoConfigureMockMvc
class ClothingVisionApiTests {
    private static final String API = "/api/clothes/vision-drafts";
    private static final byte[] PNG = Base64.getDecoder().decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jD2sAAAAASUVORK5CYII=");
    private static final byte[] WEBP = Base64.getDecoder().decode(
            "UklGRiIAAABXRUJQVlA4IBYAAAAwAQCdASoBAAEALmk0mk0iIiIiIgBoSygABc6zbAAA");
    private static final ModelFixture MODEL = new ModelFixture();

    @TempDir
    private static Path storage;

    @Autowired
    private MockMvc mvc;
    @Autowired
    private JsonMapper json;
    @Autowired
    private JdbcTemplate jdbc;

    @DynamicPropertySource
    static void configure(DynamicPropertyRegistry properties) {
        properties.add("gardirop.vision.base-url", MODEL::url);
        properties.add("gardirop.vision.api-key", () -> "fixture-only");
        properties.add("gardirop.photos.directory", () -> storage.toString());
    }

    @BeforeEach
    void resetFixture() {
        MODEL.ready = false;
        MODEL.corruptBack = false;
        MODEL.expired = false;
        MODEL.received.clear();
    }

    @AfterAll
    static void stopFixture() {
        MODEL.server.stop(0);
    }

    @Test
    void confirmsExactlyOneItemAndKeepsBothPhotosAndTheEmbeddingLocally() throws Exception {
        UUID draftId = start();
        String draft = API + "/" + draftId;
        UUID backCaptureId = UUID.randomUUID();
        String name = "Vision test " + draftId;

        mvc.perform(post(draft + "/confirm").contentType(MediaType.APPLICATION_JSON).content(confirmation(2, name)))
                .andExpect(status().isConflict());
        submitBack(draft, backCaptureId);
        mvc.perform(get(draft))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.status").value("READY"))
                .andExpect(jsonPath("$.suggestions.subCategory").value("T-shirt"))
                .andExpect(jsonPath("$.suggestions.season").doesNotExist());
        mvc.perform(get(draft + "/images/FRONT").param("revision", "3"))
                .andExpect(status().isOk()).andExpect(content().bytes(WEBP));
        mvc.perform(get("/api/clothes/all").param("q", name)).andExpect(jsonPath("$.length()").value(0));
        mvc.perform(post(draft + "/confirm").contentType(MediaType.APPLICATION_JSON).content(confirmation(2, name)))
                .andExpect(status().isConflict());

        String body = mvc.perform(post(draft + "/confirm").contentType(MediaType.APPLICATION_JSON)
                        .content(confirmation(3, name)))
                .andExpect(status().isCreated())
                .andExpect(jsonPath("$.color").value("Mavi"))
                .andExpect(jsonPath("$.season").value("YAZ"))
                .andReturn().getResponse().getContentAsString();
        JsonNode item = json.readTree(body);
        long itemId = item.required("id").asLong();
        assertThat(jdbc.queryForObject("""
                select jsonb_array_length(embedding->'values') from clothing_vision_drafts where id = ?
                """, Integer.class, draftId)).isEqualTo(1536);
        assertThat(storage.resolve("originals").resolve(draftId.toString()).resolve("FRONT-" + draftId + ".png")).exists();
        assertThat(storage.resolve("originals").resolve(draftId.toString()).resolve("BACK-" + backCaptureId + ".png")).exists();
        MODEL.expired = true;

        mvc.perform(post(draft + "/confirm").contentType(MediaType.APPLICATION_JSON).content(confirmation(3, name)))
                .andExpect(status().isCreated()).andExpect(jsonPath("$.id").value(itemId));
        mvc.perform(get(draft)).andExpect(jsonPath("$.status").value("SAVED"));
        mvc.perform(get(draft + "/images/BACK").param("revision", "3"))
                .andExpect(status().isOk()).andExpect(content().bytes(WEBP));
        mvc.perform(get("/api/clothes/all").param("q", name)).andExpect(jsonPath("$.length()").value(1));
        mvc.perform(delete("/api/clothes/{id}", itemId)).andExpect(status().isNoContent());
        mvc.perform(get(draft)).andExpect(status().isNotFound());
        assertThat(storage.resolve("processed").resolve(draftId.toString())).doesNotExist();

        assertThat(MODEL.received).allSatisfy(call -> assertThat(call.key()).isEqualTo("fixture-only"));
        assertThat(MODEL.received).anySatisfy(call -> {
            assertThat(call.method()).isEqualTo("POST");
            assertThat(call.idempotencyKey()).isEqualTo(draftId.toString());
            assertThat(call.body()).contains("name=\"image\"", "name=\"captureId\"", draftId.toString(), "UST_GIYIM");
        }).anySatisfy(call -> {
            assertThat(call.method()).isEqualTo("PUT");
            assertThat(call.body()).contains("name=\"image\"", "name=\"expectedRevision\"", backCaptureId.toString());
        });
    }

    @Test
    void rejectsACorruptPhotoAndCanDiscardTheUnconfirmedDraft() throws Exception {
        UUID id = start();
        String draft = API + "/" + id;
        String name = "Vision corrupted " + id;
        submitBack(draft, UUID.randomUUID());
        MODEL.corruptBack = true;
        mvc.perform(post(draft + "/confirm").contentType(MediaType.APPLICATION_JSON).content(confirmation(3, name)))
                .andExpect(status().isBadGateway());
        mvc.perform(get("/api/clothes/all").param("q", name)).andExpect(jsonPath("$.length()").value(0));
        mvc.perform(delete(draft).param("revision", "3")).andExpect(status().isNoContent());
        mvc.perform(get(draft)).andExpect(status().isNotFound());
        assertThat(Files.exists(storage.resolve("originals").resolve(id.toString()))).isFalse();
        assertThat(MODEL.received).anySatisfy(call -> {
            assertThat(call.method()).isEqualTo("DELETE");
            assertThat(call.path()).endsWith("?expectedRevision=3");
        });
    }

    private UUID start() throws Exception {
        UUID id = UUID.randomUUID();
        mvc.perform(multipart(API + "/start").file(photo()).param("draftId", id.toString()).param("category", "UST_GIYIM"))
                .andExpect(status().isAccepted()).andExpect(jsonPath("$.draftId").value(id.toString()))
                .andExpect(jsonPath("$.revision").value(2));
        return id;
    }

    private void submitBack(String draft, UUID captureId) throws Exception {
        mvc.perform(multipart(HttpMethod.PUT, draft + "/views/BACK").file(photo())
                        .param("revision", "2").param("captureId", captureId.toString()))
                .andExpect(status().isAccepted()).andExpect(jsonPath("$.revision").value(3));
    }

    private String confirmation(int revision, String name) {
        return json.writeValueAsString(Map.of("revision", revision, "details", Map.of(
                "name", name, "category", "UST_GIYIM", "color", "Mavi", "season", "YAZ")));
    }

    private static MockMultipartFile photo() {
        return new MockMultipartFile("photo", "shirt.png", "image/png", PNG);
    }

    private static final class ModelFixture {
        private static final String JOB_ID = "a1234567890abcdef1234567890abcde";
        private final HttpServer server;
        private final JsonMapper json = JsonMapper.builder().build();
        private final List<Call> received = new CopyOnWriteArrayList<>();
        private volatile boolean ready;
        private volatile boolean corruptBack;
        private volatile boolean expired;

        private ModelFixture() {
            try {
                server = HttpServer.create(new InetSocketAddress("127.0.0.1", 0), 0);
                server.createContext("/v1/clothing/jobs", this::handle);
                server.start();
            } catch (IOException exception) {
                throw new UncheckedIOException(exception);
            }
        }

        private String url() {
            return "http://127.0.0.1:" + server.getAddress().getPort();
        }

        private void handle(HttpExchange exchange) throws IOException {
            try (exchange) {
                String method = exchange.getRequestMethod();
                String path = exchange.getRequestURI().getPath();
                received.add(new Call(method, exchange.getRequestURI().toString(), exchange.getRequestHeaders().getFirst("X-API-Key"),
                        exchange.getRequestHeaders().getFirst("Idempotency-Key"),
                        new String(exchange.getRequestBody().readAllBytes(), StandardCharsets.ISO_8859_1)));
                if (expired) {
                    sendJson(exchange, 410, Map.of("error", Map.of("code", "JOB_EXPIRED")));
                } else if ("DELETE".equals(method)) {
                    exchange.sendResponseHeaders(204, -1);
                } else if (path.endsWith("/views/BACK")) {
                    ready = true;
                    sendJson(exchange, 202, progress());
                } else if (path.endsWith("/images/FRONT") || path.endsWith("/images/BACK")) {
                    byte[] bytes = corruptBack && path.endsWith("/BACK") ? PNG : WEBP;
                    send(exchange, 200, "image/webp", bytes);
                } else if (path.endsWith("/embedding")) {
                    sendJson(exchange, 200, Map.of("jobId", JOB_ID, "revision", 3, "dimension", 1536,
                            "dtype", "float32", "model", "fixture", "encoderRevision", "encoder-1", "fusionMethod",
                            "concat_unit_front_back_div_sqrt2", "viewOrder", List.of("FRONT", "BACK"),
                            "values", new double[1536]));
                } else if (path.endsWith("/results/3")) {
                    sendJson(exchange, 200, result());
                } else {
                    sendJson(exchange, "POST".equals(method) ? 202 : 200, progress());
                }
            }
        }

        private Map<String, Object> progress() {
            Map<String, Object> views = ready
                    ? Map.of("FRONT", Map.of("status", "READY"), "BACK", Map.of("status", "READY"))
                    : Map.of("FRONT", Map.of("status", "QUEUED"));
            Map<String, Object> body = new java.util.HashMap<>(Map.of("jobId", JOB_ID, "category", "UST_GIYIM",
                    "expiresAt", "2026-12-01T14:00:00+00:00", "views", views, "status", ready ? "READY" : "PROCESSING",
                    "revision", ready ? 3 : 2));
            if (ready) body.put("resultRevision", 3);
            return body;
        }

        private Map<String, Object> result() {
            try {
                Map<String, Object> image = Map.of("contentType", "image/webp", "byteLength", WEBP.length, "sha256",
                        HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(WEBP)));
                return Map.of("jobId", JOB_ID, "revision", 3, "category", "UST_GIYIM",
                        "tags", Map.of("subCategory", "T-shirt", "color", "Kırmızı"),
                        "versions", Map.of("embeddingRevision", "encoder-1", "fusionMethod", "concat_unit_front_back_div_sqrt2"),
                        "images", Map.of("FRONT", image, "BACK", image));
            } catch (NoSuchAlgorithmException exception) {
                throw new IllegalStateException(exception);
            }
        }

        private void sendJson(HttpExchange exchange, int status, Map<String, Object> payload) throws IOException {
            send(exchange, status, "application/json", json.writeValueAsBytes(payload));
        }

        private static void send(HttpExchange exchange, int status, String contentType, byte[] bytes) throws IOException {
            exchange.getResponseHeaders().set("Content-Type", contentType);
            exchange.sendResponseHeaders(status, bytes.length);
            exchange.getResponseBody().write(bytes);
        }

        private record Call(String method, String path, String key, String idempotencyKey, String body) {}
    }
}

package com.gardiropai.backend;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.webmvc.test.autoconfigure.AutoConfigureMockMvc;
import org.springframework.http.MediaType;
import org.springframework.mock.web.MockMultipartFile;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.transaction.annotation.Transactional;
import tools.jackson.databind.JsonNode;
import tools.jackson.databind.json.JsonMapper;

import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Base64;
import java.util.List;
import java.util.Map;
import java.util.UUID;

import static org.assertj.core.api.Assertions.assertThat;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.delete;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.multipart;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.put;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.content;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@SpringBootTest
@AutoConfigureMockMvc
@Transactional
class ClothingPhotoApiTests {
    private static final byte[] PNG = Base64.getDecoder().decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jD2sAAAAASUVORK5CYII=");

    @TempDir
    private static Path photoDirectory;

    @DynamicPropertySource
    static void storage(DynamicPropertyRegistry properties) {
        properties.add("gardirop.photos.directory", () -> photoDirectory.toString());
    }

    @Autowired
    private MockMvc mockMvc;

    @Autowired
    private JsonMapper jsonMapper;

    @Test
    void previewsAndConfirmsOnePersistentClothingRecord() throws Exception {
        JsonNode draft = upload();
        String uploadId = draft.required("uploadId").asString();
        String imageUrl = draft.required("imageUrl").asString();
        String name = "Fotoğraf testi " + UUID.randomUUID();
        String details = jsonMapper.writeValueAsString(Map.of(
                "name", name, "category", "UST_GIYIM", "season", "HER_MEVSIM", "tags", List.of("spor")));

        assertThat(Files.readAllBytes(photoDirectory.resolve("originals").resolve(uploadId + ".png")))
                .isEqualTo(PNG);
        mockMvc.perform(get(imageUrl))
                .andExpect(status().isOk())
                .andExpect(content().contentType(MediaType.IMAGE_PNG))
                .andExpect(content().bytes(PNG));
        mockMvc.perform(get("/api/clothes/all").param("q", name))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.length()").value(0));

        String saved = mockMvc.perform(post("/api/clothes/photo-drafts/{id}/confirm", uploadId)
                        .contentType(MediaType.APPLICATION_JSON).content(details))
                .andExpect(status().isCreated())
                .andExpect(jsonPath("$.imageUrl").value(imageUrl))
                .andExpect(jsonPath("$.status").value("TEMIZ"))
                .andReturn().getResponse().getContentAsString();
        long itemId = jsonMapper.readTree(saved).required("id").asLong();
        mockMvc.perform(post("/api/clothes/photo-drafts/{id}/confirm", uploadId)
                        .contentType(MediaType.APPLICATION_JSON).content(details))
                .andExpect(status().isCreated())
                .andExpect(jsonPath("$.id").value(itemId));
        mockMvc.perform(get("/api/clothes/all").param("q", name))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.length()").value(1));
        mockMvc.perform(put("/api/clothes/{id}/details", itemId)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {"name":"Güncellenen gömlek","category":"UST_GIYIM","season":"KIS"}
                                """))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.name").value("Güncellenen gömlek"))
                .andExpect(jsonPath("$.imageUrl").value(imageUrl));
    }

    @Test
    void rejectsOtherFileTypesAndDiscardsUnconfirmedPhotos() throws Exception {
        mockMvc.perform(multipart("/api/clothes/photo-drafts")
                        .file(new MockMultipartFile("photo", "file.txt", "text/plain", new byte[] {1, 2})))
                .andExpect(status().isUnsupportedMediaType());

        JsonNode draft = upload();
        mockMvc.perform(delete("/api/clothes/photo-drafts/{id}", draft.required("uploadId").asString()))
                .andExpect(status().isNoContent());
        mockMvc.perform(get(draft.required("imageUrl").asString()))
                .andExpect(status().isNotFound());
    }

    private JsonNode upload() throws Exception {
        String body = mockMvc.perform(multipart("/api/clothes/photo-drafts")
                        .file(new MockMultipartFile("photo", "shirt.png", "image/png", PNG)))
                .andExpect(status().isCreated())
                .andReturn().getResponse().getContentAsString();
        return jsonMapper.readTree(body);
    }
}

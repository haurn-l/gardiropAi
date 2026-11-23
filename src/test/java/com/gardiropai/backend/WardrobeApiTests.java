package com.gardiropai.backend;

import jakarta.persistence.EntityManager;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.webmvc.test.autoconfigure.AutoConfigureMockMvc;
import org.springframework.http.MediaType;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.transaction.annotation.Transactional;
import tools.jackson.databind.json.JsonMapper;

import java.util.List;
import java.util.Map;
import java.util.UUID;

import static org.assertj.core.api.Assertions.assertThat;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.patch;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.put;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@SpringBootTest
@AutoConfigureMockMvc
@Transactional
class WardrobeApiTests {
    @Autowired
    private MockMvc mockMvc;

    @Autowired
    private JdbcTemplate jdbcTemplate;

    @Autowired
    private EntityManager entityManager;

    @Autowired
    private JsonMapper jsonMapper;

    @Test
    void listsTheDemoWardrobeWithOrWithoutFilters() throws Exception {
        Long firstUserId = jdbcTemplate.queryForObject("select min(id) from users", Long.class);
        long userId = firstUserId == null ? createUser() : firstUserId;
        String tagSuffix = " " + UUID.randomUUID();
        String sportTag = "Karışık Spor" + tagSuffix;
        long match = addClothing(userId, "İpek gömlek", "UST_GIYIM", sportTag);
        long dirty = addClothing(userId, "İpek sweatshirt", "UST_GIYIM", sportTag);
        long otherCategory = addClothing(userId, "İpek pantolon", "ALT_GIYIM", sportTag);
        long otherTag = addClothing(userId, "İpek bluz", "UST_GIYIM", "Resmî");
        long otherName = addClothing(userId, "Pamuklu gömlek", "UST_GIYIM", sportTag);
        long otherUserId = createUser();
        long otherUserItem = addClothing(otherUserId, "İpek gömlek", "UST_GIYIM", sportTag);
        addClothing(userId, "İpek tişört", "UST_GIYIM", sportTag);

        for (long itemId : new long[] {match, dirty, otherCategory, otherTag, otherName, otherUserItem}) {
            mockMvc.perform(put("/api/clothes/{id}/favorite", itemId).param("favorite", "true"))
                    .andExpect(status().isOk());
        }
        mockMvc.perform(put("/api/clothes/{id}/status", dirty).param("status", "KIRLI"))
                .andExpect(status().isOk());

        entityManager.flush();
        entityManager.clear();
        String wardrobe = mockMvc.perform(get("/api/clothes/all"))
                .andExpect(status().isOk())
                .andReturn().getResponse().getContentAsString();
        assertThat(jsonMapper.readTree(wardrobe).values().stream()
                .map(item -> item.required("id").asLong())
                .toList())
                .contains(match, dirty, otherCategory, otherTag, otherName)
                .doesNotContain(otherUserItem);

        mockMvc.perform(get("/api/clothes/all/{userId}", otherUserId))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.length()").value(1))
                .andExpect(jsonPath("$[0].id").value(otherUserItem));

        mockMvc.perform(get("/api/clothes/all")
                        .param("status", "TEMIZ")
                        .param("category", "UST_GIYIM")
                        .param("favorite", "true")
                        .param("q", "  ipek ")
                        .param("tag", "KARIŞIK SPOR" + tagSuffix))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.length()").value(1))
                .andExpect(jsonPath("$[0].id").value(match))
                .andExpect(jsonPath("$[0].name").value("İpek gömlek"))
                .andExpect(jsonPath("$[0].tags[0]").value(sportTag))
                .andExpect(jsonPath("$[0].favorite").value(true));

        mockMvc.perform(get("/api/clothes/all").param("tag", "spor" + tagSuffix))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.length()").value(0));
        mockMvc.perform(get("/api/clothes/all").param("status", "GEÇERSİZ"))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.status").value(400));
    }

    @Test
    void storesClothingAndCombineFeedbackIndependentlyAndReturnsClothingDtos() throws Exception {
        long userId = createUser();
        long itemId = addClothing(userId, "Gri gömlek", "UST_GIYIM", "İş");
        long combineId = readId(mockMvc.perform(post("/api/v1/combines")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(jsonMapper.writeValueAsString(Map.of(
                                "userId", userId, "clothingItemIds", List.of(itemId), "favorite", true))))
                .andExpect(status().isCreated())
                .andExpect(jsonPath("$.favorite").value(true))
                .andReturn().getResponse().getContentAsString());

        mockMvc.perform(get("/api/clothes/clean/{userId}", userId))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$[0].name").value("Gri gömlek"))
                .andExpect(jsonPath("$[0].user").doesNotHaveJsonPath())
                .andExpect(jsonPath("$[0].combines").doesNotHaveJsonPath());
        mockMvc.perform(patch("/api/clothes/{id}/rate", itemId).param("ratingScore", "4"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.favorite").value(false));
        mockMvc.perform(put("/api/clothes/{id}/favorite", itemId).param("favorite", "true"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.userRating").value(4));
        mockMvc.perform(put("/api/v1/combines/{id}/favorite", combineId).param("favorite", "false"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.favorite").value(false));
        mockMvc.perform(patch("/api/v1/combines/{id}/rate", combineId).param("ratingScore", "5"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.favorite").value(false));
        mockMvc.perform(put("/api/v1/combines/{id}/favorite", combineId).param("favorite", "true"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.ratingScore").value(5));
        mockMvc.perform(patch("/api/clothes/{id}/rate", itemId).param("ratingScore", "0"))
                .andExpect(status().isBadRequest());
        mockMvc.perform(patch("/api/v1/combines/{id}/rate", combineId).param("ratingScore", "6"))
                .andExpect(status().isBadRequest());
        mockMvc.perform(put("/api/clothes/{id}/favorite", itemId).param("favorite", "false"))
                .andExpect(status().isOk());

        entityManager.flush();
        entityManager.clear();
        mockMvc.perform(get("/api/clothes/{id}", itemId))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.favorite").value(false))
                .andExpect(jsonPath("$.userRating").value(4));
        mockMvc.perform(get("/api/v1/combines/user/{id}", userId))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$[0].favorite").value(true))
                .andExpect(jsonPath("$[0].ratingScore").value(5))
                .andExpect(jsonPath("$[0].clothingItems[0].favorite").value(false));
    }

    private long createUser() {
        return jdbcTemplate.queryForObject("insert into users (username) values (?) returning id",
                Long.class, "wardrobe-test-" + UUID.randomUUID());
    }

    private long addClothing(long userId, String name, String category, String tag) throws Exception {
        return readId(mockMvc.perform(post("/api/clothes/add")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(jsonMapper.writeValueAsString(Map.of(
                                "userId", userId,
                                "name", name,
                                "imageUrl", "https://example.com/shirt.jpg",
                                "category", category,
                                "season", "HER_MEVSIM",
                                "tags", List.of(tag)))))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.favorite").value(false))
                .andReturn().getResponse().getContentAsString());
    }

    private long readId(String response) {
        return jsonMapper.readTree(response).required("id").asLong();
    }
}

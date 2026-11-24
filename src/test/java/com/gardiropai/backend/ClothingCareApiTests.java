package com.gardiropai.backend;

import com.gardiropai.backend.serviceIMPL.ClothingCareService;
import jakarta.persistence.EntityManager;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.webmvc.test.autoconfigure.AutoConfigureMockMvc;
import org.springframework.http.MediaType;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.transaction.annotation.Transactional;
import tools.jackson.databind.JsonNode;
import tools.jackson.databind.json.JsonMapper;

import java.time.OffsetDateTime;
import java.time.ZoneOffset;
import java.util.List;
import java.util.Map;
import java.util.UUID;

import static org.assertj.core.api.Assertions.assertThat;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.put;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@SpringBootTest
@AutoConfigureMockMvc
@Transactional
class ClothingCareApiTests {
    @Autowired
    private MockMvc mockMvc;
    @Autowired
    private JdbcTemplate jdbcTemplate;
    @Autowired
    private EntityManager entityManager;
    @Autowired
    private JsonMapper jsonMapper;
    @Autowired
    private ClothingCareService clothingCare;

    @Test
    void marksOnlyTheWornItemAndDoesNotResetItsTimerOnRetry() throws Exception {
        long userId = createUser();
        long worn = addClothing(userId);
        long untouched = addClothing(userId);

        JsonNode first = wearItem(worn);
        String firstDirtySince = first.required("dirtySince").asString();
        entityManager.flush();
        entityManager.clear();
        assertThat(wearItem(worn).required("dirtySince").asString()).isEqualTo(firstDirtySince);
        assertClothingStatus(untouched, "TEMIZ");

        mockMvc.perform(get("/api/clothes/clean/{id}", userId))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.length()").value(1))
                .andExpect(jsonPath("$[0].id").value(untouched));
    }

    @Test
    void savingAnOutfitKeepsItemsCleanAndWearingItUpdatesOnlyItsItems() throws Exception {
        long userId = createUser();
        long top = addClothing(userId);
        long bottom = addClothing(userId);
        long extra = addClothing(userId);
        long combineId = createCombine(userId, top, bottom);

        assertClothingStatus(top, "TEMIZ");
        assertClothingStatus(bottom, "TEMIZ");

        mockMvc.perform(put("/api/v1/combines/{id}/worn", combineId))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.id").value(combineId))
                .andExpect(jsonPath("$.clothingItems.length()").value(2))
                .andExpect(jsonPath("$.clothingItems[0].status").value("KIRLI"))
                .andExpect(jsonPath("$.clothingItems[1].status").value("KIRLI"))
                .andExpect(jsonPath("$.ratingScore").value(4))
                .andExpect(jsonPath("$.favorite").value(true));

        entityManager.flush();
        entityManager.clear();
        assertClothingStatus(top, "KIRLI");
        assertClothingStatus(bottom, "KIRLI");
        assertClothingStatus(extra, "TEMIZ");
        mockMvc.perform(get("/api/v1/combines/user/{id}", userId))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$[0].id").value(combineId));
    }

    @Test
    void unavailableItemBlocksTheEntireOutfitWear() throws Exception {
        long userId = createUser();
        long first = addClothing(userId);
        long unavailable = addClothing(userId);
        long combineId = createCombine(userId, first, unavailable);
        setStatus(unavailable, "KULLANIM_DISI");

        mockMvc.perform(put("/api/v1/combines/{id}/worn", combineId))
                .andExpect(status().isConflict());
        mockMvc.perform(put("/api/clothes/{id}/worn", unavailable))
                .andExpect(status().isConflict());

        assertClothingStatus(first, "TEMIZ");
        assertClothingStatus(unavailable, "KULLANIM_DISI");
    }

    @Test
    void cleansExpiredDirtyItemsAndRespectsNewerOrManualStatuses() throws Exception {
        long userId = createUser();
        long expired = addClothing(userId);
        long recent = addClothing(userId);
        long manuallyCleaned = addClothing(userId);
        long unavailable = addClothing(userId);
        long legacyDirty = addClothing(userId);

        wearItem(expired);
        setStatus(recent, "KIRLI");
        wearItem(manuallyCleaned);
        wearItem(unavailable);
        entityManager.flush();
        OffsetDateTime fourDaysAgo = OffsetDateTime.now(ZoneOffset.UTC).minusDays(4);
        jdbcTemplate.update("update clothes set dirty_since = ? where id in (?, ?, ?)",
                fourDaysAgo, expired, manuallyCleaned, unavailable);
        jdbcTemplate.update("update clothes set status = 'KIRLI' where id = ?", legacyDirty);
        entityManager.clear();

        setStatus(manuallyCleaned, "TEMIZ");
        setStatus(unavailable, "KULLANIM_DISI");
        clothingCare.cleanExpiredItems();
        entityManager.flush();
        entityManager.clear();

        assertClothingStatus(expired, "TEMIZ");
        assertClothingStatus(recent, "KIRLI");
        assertClothingStatus(manuallyCleaned, "TEMIZ");
        assertClothingStatus(unavailable, "KULLANIM_DISI");
        assertClothingStatus(legacyDirty, "KIRLI");
        assertThat(jdbcTemplate.queryForObject("select dirty_since is null from clothes where id = ?",
                Boolean.class, expired)).isTrue();
    }

    private long createUser() {
        return jdbcTemplate.queryForObject("insert into users (username) values (?) returning id",
                Long.class, "worn-test-" + UUID.randomUUID());
    }

    private long addClothing(long userId) throws Exception {
        String result = mockMvc.perform(post("/api/clothes/add")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(jsonMapper.writeValueAsString(Map.of(
                                "userId", userId, "imageUrl", "https://example.com/shirt.jpg",
                                "category", "UST_GIYIM", "season", "HER_MEVSIM"))))
                .andExpect(status().isOk())
                .andReturn().getResponse().getContentAsString();
        return jsonMapper.readTree(result).required("id").asLong();
    }

    private long createCombine(long userId, long first, long second) throws Exception {
        String result = mockMvc.perform(post("/api/v1/combines")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(jsonMapper.writeValueAsString(Map.of(
                                "userId", userId, "clothingItemIds", List.of(first, second),
                                "ratingScore", 4, "favorite", true))))
                .andExpect(status().isCreated())
                .andReturn().getResponse().getContentAsString();
        return jsonMapper.readTree(result).required("id").asLong();
    }

    private JsonNode wearItem(long itemId) throws Exception {
        String result = mockMvc.perform(put("/api/clothes/{id}/worn", itemId))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.status").value("KIRLI"))
                .andExpect(jsonPath("$.dirtySince").isString())
                .andReturn().getResponse().getContentAsString();
        return jsonMapper.readTree(result);
    }

    private void setStatus(long itemId, String nextStatus) throws Exception {
        mockMvc.perform(put("/api/clothes/{id}/status", itemId).param("status", nextStatus))
                .andExpect(status().isOk());
    }

    private void assertClothingStatus(long itemId, String expectedStatus) throws Exception {
        mockMvc.perform(get("/api/clothes/{id}", itemId))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.status").value(expectedStatus));
    }
}

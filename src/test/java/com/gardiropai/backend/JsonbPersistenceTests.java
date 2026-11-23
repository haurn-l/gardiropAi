package com.gardiropai.backend;

import com.gardiropai.backend.dto.request.ClothingCreateRequest;
import com.gardiropai.backend.dto.request.UserCreateRequest;
import com.gardiropai.backend.enums.Category;
import com.gardiropai.backend.enums.ItemStatus;
import com.gardiropai.backend.enums.Season;
import com.gardiropai.backend.service.ClothingService;
import com.gardiropai.backend.service.UserService;
import jakarta.persistence.EntityManager;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.transaction.annotation.Transactional;

import java.util.UUID;

import static org.assertj.core.api.Assertions.assertThat;

@SpringBootTest
@Transactional
class JsonbPersistenceTests {
    @Autowired
    private UserService userService;

    @Autowired
    private ClothingService clothingService;

    @Autowired
    private EntityManager entityManager;

    @Autowired
    private JdbcTemplate jdbcTemplate;

    @Test
    void registersUserAndStoresStylePreferencesAsJson() {
        UserCreateRequest request = new UserCreateRequest();
        request.setUsername("jsonb-test-" + UUID.randomUUID());

        Long userId = userService.createUser(request).getId();
        assertThat(jdbcTemplate.queryForObject(
                "select style_preferences is null from users where id = ?", Boolean.class, userId))
                .isTrue();

        userService.updateStylePreferences(userId, "{\"styles\":[\"casual\"]}");
        entityManager.flush();
        entityManager.clear();

        assertThat(jdbcTemplate.queryForObject(
                "select jsonb_typeof(style_preferences) from users where id = ?", String.class, userId))
                .isEqualTo("object");
        assertThat(jdbcTemplate.queryForObject(
                "select style_preferences -> 'styles' ->> 0 from users where id = ?", String.class, userId))
                .isEqualTo("casual");
        assertThat(userService.getUserById(userId).getStylePreferences()).contains("casual");
    }

    @Test
    void addsClothingAndKeepsExistingJsonTagsWhenStatusChanges() {
        Long userId = jdbcTemplate.queryForObject(
                "insert into users (username) values (?) returning id",
                Long.class, "jsonb-test-" + UUID.randomUUID());
        ClothingCreateRequest request = new ClothingCreateRequest();
        request.setUserId(userId);
        request.setCategory(Category.UST_GIYIM);
        request.setSeason(Season.HER_MEVSIM);
        request.setImageUrl("https://example.com/shirt.jpg");

        Long clothingId = clothingService.addClothingItem(request).getId();
        assertThat(jdbcTemplate.queryForObject(
                "select custom_tags is null from clothes where id = ?", Boolean.class, clothingId))
                .isTrue();

        jdbcTemplate.update("update clothes set custom_tags = cast(? as jsonb) where id = ?",
                "[\"sport\",\"casual\"]", clothingId);
        entityManager.clear();

        clothingService.updateClothingStatus(clothingId, ItemStatus.KIRLI);
        entityManager.flush();

        assertThat(jdbcTemplate.queryForObject(
                "select status from clothes where id = ?", String.class, clothingId))
                .isEqualTo("KIRLI");
        assertThat(jdbcTemplate.queryForObject(
                "select jsonb_typeof(custom_tags) from clothes where id = ?", String.class, clothingId))
                .isEqualTo("array");
        assertThat(jdbcTemplate.queryForObject(
                "select custom_tags ->> 1 from clothes where id = ?", String.class, clothingId))
                .isEqualTo("casual");
    }
}

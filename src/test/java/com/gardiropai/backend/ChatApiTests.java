package com.gardiropai.backend;

import com.gardiropai.backend.entity.User;
import com.gardiropai.backend.repository.UserRepository;
import jakarta.persistence.EntityManager;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.webmvc.test.autoconfigure.AutoConfigureMockMvc;
import org.springframework.http.MediaType;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.ResultActions;
import org.springframework.transaction.annotation.Transactional;
import tools.jackson.databind.json.JsonMapper;

import java.util.List;
import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.delete;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.put;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@SpringBootTest
@AutoConfigureMockMvc
@Transactional
class ChatApiTests {
    private static final String CHATS = "/api/v1/chats";

    @Autowired
    private MockMvc mvc;
    @Autowired
    private EntityManager entityManager;
    @Autowired
    private UserRepository users;
    @Autowired
    private JdbcTemplate jdbc;
    @Autowired
    private JsonMapper json;

    @Test
    void reopensChatWithFullHistoryAndPreservesLockedItemDuringEdit() throws Exception {
        long chatId = startChat();
        User user = users.findFirstByOrderByIdAsc().orElseThrow();
        long top = addItem(user, "UST_GIYIM");
        long original = addItem(user, "ALT_GIYIM");
        long replacement = addItem(user, "ALT_GIYIM");

        for (int i = 1; i <= 4; i++) {
            String message = "Mesaj " + i;
            mvc.perform(post(CHATS + "/{id}/messages", chatId)
                            .contentType(MediaType.APPLICATION_JSON)
                            .content(json.writeValueAsString(Map.of("content", message))))
                    .andExpect(status().isCreated())
                    .andExpect(jsonPath("$.content").value(message))
                    .andExpect(jsonPath("$.senderRole").value("USER"));
        }

        replaceDraft(chatId, 0, List.of(item(top, true), item(original, false)))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.version").value(1));
        flushAndClear();

        mvc.perform(get(CHATS + "/all"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$[0].id").value(chatId));
        mvc.perform(get(CHATS + "/{id}", chatId))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.messages.length()").value(4))
                .andExpect(jsonPath("$.messages[0].content").value("Mesaj 1"))
                .andExpect(jsonPath("$.messages[3].content").value("Mesaj 4"))
                .andExpect(jsonPath("$.draft.items[0].clothingItemId").value(top))
                .andExpect(jsonPath("$.draft.items[0].locked").value(true))
                .andExpect(jsonPath("$.draft.items[1].clothingItemId").value(original))
                .andExpect(jsonPath("$.draft.savedCombineId").isEmpty());

        replaceDraft(chatId, 1, List.of(item(top, true), item(replacement, false)))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.version").value(2));
        flushAndClear();

        mvc.perform(get(CHATS + "/{id}", chatId))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.draft.items[0].clothingItemId").value(top))
                .andExpect(jsonPath("$.draft.items[0].locked").value(true))
                .andExpect(jsonPath("$.draft.items[1].clothingItemId").value(replacement));
    }

    @Test
    void confirmationCreatesOneOutfitAndKeepsClothesCleanOnRetry() throws Exception {
        long chatId = startChat();
        User user = users.findFirstByOrderByIdAsc().orElseThrow();
        long top = addItem(user, "UST_GIYIM");
        long bottom = addItem(user, "ALT_GIYIM");
        int before = outfitCount(user.getId());

        replaceDraft(chatId, 0, List.of(item(top, true), item(bottom, false)))
                .andExpect(status().isOk());
        flushAndClear();
        assertThat(outfitCount(user.getId())).isEqualTo(before);

        long combineId = responseId(confirm(chatId, 1).andExpect(status().isOk()), "combineId");
        flushAndClear();

        confirm(chatId, 1).andExpect(status().isOk()).andExpect(jsonPath("$.combineId").value(combineId));
        assertThat(outfitCount(user.getId())).isEqualTo(before + 1);
        mvc.perform(get(CHATS + "/{id}", chatId))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.draft.savedCombineId").value(combineId));
        for (long id : List.of(top, bottom)) {
            mvc.perform(get("/api/clothes/{id}", id))
                    .andExpect(status().isOk())
                    .andExpect(jsonPath("$.status").value("TEMIZ"));
        }
    }

    @Test
    void deletingSavedOutfitReopensDraftAndInvalidatesPreviousConfirmation() throws Exception {
        long chatId = startChat();
        long otherChatId = startChat();
        User user = users.findFirstByOrderByIdAsc().orElseThrow();
        long top = addItem(user, "UST_GIYIM");
        long bottom = addItem(user, "ALT_GIYIM");
        int before = outfitCount(user.getId());

        replaceDraft(chatId, 0, List.of(item(top, true), item(bottom, false))).andExpect(status().isOk());
        replaceDraft(otherChatId, 0, List.of(item(bottom, false))).andExpect(status().isOk());
        long deletedId = responseId(confirm(chatId, 1).andExpect(status().isOk()), "combineId");
        long otherId = responseId(confirm(otherChatId, 1).andExpect(status().isOk()), "combineId");
        flushAndClear();

        mvc.perform(delete("/api/v1/combines/{id}", deletedId)).andExpect(status().isNoContent());
        flushAndClear();

        assertThat(outfitCount(user.getId())).isEqualTo(before + 1);
        mvc.perform(get(CHATS + "/{id}", chatId))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.draft.version").value(2))
                .andExpect(jsonPath("$.draft.savedCombineId").isEmpty())
                .andExpect(jsonPath("$.draft.items[0].clothingItemId").value(top))
                .andExpect(jsonPath("$.draft.items[0].locked").value(true))
                .andExpect(jsonPath("$.draft.items[1].clothingItemId").value(bottom));
        mvc.perform(get(CHATS + "/{id}", otherChatId))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.draft.version").value(1))
                .andExpect(jsonPath("$.draft.savedCombineId").value(otherId));

        confirm(chatId, 1).andExpect(status().isConflict());
        long replacementId = responseId(confirm(chatId, 2).andExpect(status().isOk()), "combineId");
        flushAndClear();

        assertThat(replacementId).isNotEqualTo(deletedId);
        assertThat(outfitCount(user.getId())).isEqualTo(before + 2);
        confirm(chatId, 2).andExpect(status().isOk()).andExpect(jsonPath("$.combineId").value(replacementId));
    }

    @Test
    void rejectsInvalidDraftsAndDoesNotSaveWhenASelectedItemBecomesDirty() throws Exception {
        long chatId = startChat();
        User user = users.findFirstByOrderByIdAsc().orElseThrow();
        long top = addItem(user, "UST_GIYIM");
        int before = outfitCount(user.getId());

        confirm(chatId, 0).andExpect(status().isConflict());
        replaceDraft(chatId, 0, List.of(item(top, false), item(top, true)))
                .andExpect(status().isBadRequest());
        replaceDraft(chatId, 0, List.of(Map.of("clothingItemId", top))).andExpect(status().isBadRequest());
        replaceDraft(chatId, 0, List.of(item(top, false))).andExpect(status().isOk());
        flushAndClear();

        replaceDraft(chatId, 0, List.of(item(top, true))).andExpect(status().isConflict());
        confirm(chatId, 0).andExpect(status().isConflict());
        mvc.perform(put("/api/clothes/{id}/worn", top)).andExpect(status().isOk());
        flushAndClear();

        confirm(chatId, 1).andExpect(status().isConflict());
        assertThat(outfitCount(user.getId())).isEqualTo(before);
    }

    private long startChat() throws Exception {
        return responseId(mvc.perform(post(CHATS + "/start")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{}"))
                .andExpect(status().isCreated())
                .andExpect(jsonPath("$.title").value("Yeni sohbet"))
                .andExpect(jsonPath("$.draft.version").value(0)), "id");
    }

    private ResultActions replaceDraft(long chatId, long version, List<Map<String, Object>> items) throws Exception {
        return mvc.perform(put(CHATS + "/{id}/draft", chatId)
                .contentType(MediaType.APPLICATION_JSON)
                .content(json.writeValueAsString(Map.of("version", version, "items", items))));
    }

    private ResultActions confirm(long chatId, long version) throws Exception {
        return mvc.perform(post(CHATS + "/{id}/draft/confirm", chatId)
                .contentType(MediaType.APPLICATION_JSON)
                .content(json.writeValueAsString(Map.of("version", version))));
    }

    private long addItem(User user, String category) {
        return jdbc.queryForObject("""
                insert into clothes (user_id, category, season, status)
                values (?, ?, 'HER_MEVSIM', 'TEMIZ') returning id
                """, Long.class, user.getId(), category);
    }

    private int outfitCount(long userId) {
        return jdbc.queryForObject("select count(*) from combines where user_id = ?", Integer.class, userId);
    }

    private long responseId(ResultActions result, String property) throws Exception {
        return json.readTree(result.andReturn().getResponse().getContentAsString()).required(property).asLong();
    }

    private void flushAndClear() {
        entityManager.flush();
        entityManager.clear();
    }

    private static Map<String, Object> item(long id, boolean locked) {
        return Map.of("clothingItemId", id, "locked", locked);
    }
}

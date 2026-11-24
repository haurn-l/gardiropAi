package com.gardiropai.backend.serviceIMPL;

import com.gardiropai.backend.entity.ClothingItem;
import com.gardiropai.backend.enums.ItemStatus;
import com.gardiropai.backend.exception.ClothingNotFoundException;
import com.gardiropai.backend.repository.ClothingItemRepository;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.HttpStatus;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.server.ResponseStatusException;

import java.time.Duration;
import java.time.Instant;
import java.time.temporal.ChronoUnit;
import java.util.List;

@Service
@Transactional
public class ClothingCareService {
    private final ClothingItemRepository clothingRepository;
    private final Duration cleanAfter;

    public ClothingCareService(ClothingItemRepository clothingRepository,
                               @Value("${gardirop.laundry.clean-after}") Duration cleanAfter) {
        if (cleanAfter.isZero() || cleanAfter.isNegative()) {
            throw new IllegalArgumentException("Otomatik temizlenme süresi pozitif olmalıdır.");
        }
        this.clothingRepository = clothingRepository;
        this.cleanAfter = cleanAfter;
    }

    public ClothingItem updateStatus(Long itemId, ItemStatus status) {
        ClothingItem item = findItems(List.of(itemId)).getFirst();
        applyStatus(item, status, Instant.now().truncatedTo(ChronoUnit.MILLIS));
        return item;
    }

    public ClothingItem markWorn(Long itemId) {
        return markWornItems(List.of(itemId)).getFirst();
    }

    public List<ClothingItem> markWornItems(List<Long> itemIds) {
        if (itemIds.isEmpty()) {
            throw new ResponseStatusException(HttpStatus.CONFLICT, "Kombinde giyilecek kıyafet bulunamadı.");
        }
        List<ClothingItem> items = findItems(itemIds);
        if (items.stream().anyMatch(item -> item.getStatus() == ItemStatus.KULLANIM_DISI)) {
            throw new ResponseStatusException(HttpStatus.CONFLICT, "Kullanım dışı kıyafet giyildi olarak işaretlenemez.");
        }

        Instant wornAt = Instant.now().truncatedTo(ChronoUnit.MILLIS);
        items.forEach(item -> applyStatus(item, ItemStatus.KIRLI, wornAt));
        return items;
    }

    @Scheduled(fixedDelayString = "${gardirop.laundry.check-interval}",
               initialDelayString = "${gardirop.laundry.check-interval}")
    public void cleanExpiredItems() {
        Instant now = Instant.now();
        clothingRepository.findExpiredForStatusUpdate(ItemStatus.KIRLI, now.minus(cleanAfter))
                .forEach(item -> applyStatus(item, ItemStatus.TEMIZ, now));
    }

    private List<ClothingItem> findItems(List<Long> itemIds) {
        List<ClothingItem> items = clothingRepository.findForStatusUpdate(itemIds);
        if (items.size() != itemIds.size()) {
            throw new ClothingNotFoundException("Güncellenecek kıyafet bulunamadı.");
        }
        return items;
    }

    private void applyStatus(ClothingItem item, ItemStatus status, Instant changedAt) {
        if (status != ItemStatus.KIRLI) {
            item.setDirtySince(null);
        } else if (item.getStatus() != ItemStatus.KIRLI || item.getDirtySince() == null) {
            item.setDirtySince(changedAt);
        }
        item.setStatus(status);
    }
}

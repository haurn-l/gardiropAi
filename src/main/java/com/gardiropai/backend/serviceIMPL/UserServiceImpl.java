package com.gardiropai.backend.serviceIMPL;

import com.gardiropai.backend.dto.request.UserCreateRequest;
import com.gardiropai.backend.dto.response.UserResponse;
import com.gardiropai.backend.entity.User;
import com.gardiropai.backend.exception.UserAlreadyExistsException;
import com.gardiropai.backend.exception.UserNotFoundException;
import com.gardiropai.backend.repository.UserRepository;
import com.gardiropai.backend.service.UserService;
import jakarta.transaction.Transactional;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;

import java.time.LocalDateTime;

@Service
@RequiredArgsConstructor
@Transactional
public class UserServiceImpl implements UserService {

    private final UserRepository userRepository;

    @Override
    public UserResponse createUser(UserCreateRequest request) {
        if (userRepository.existsByUsername(request.getUsername())) {
            throw new UserAlreadyExistsException("Bu kullanıcı adı zaten alınmış: " + request.getUsername());
        }

        User user = new User();
        user.setUsername(request.getUsername());
        User savedUser = userRepository.save(user);

        return convertToResponse(savedUser);
    }

    @Override
    public UserResponse getUserById(Long userId) {
        User user = getUserEntityById(userId);
        return convertToResponse(user);
    }

    @Override
    public UserResponse updateStylePreferences(Long userId, String newPreferences) {
        User user = getUserEntityById(userId);
        user.setStylePreferences(newPreferences);
        user.setPreferencesResetDate(LocalDateTime.now());

        User updatedUser = userRepository.save(user);
        return convertToResponse(updatedUser);
    }

    // --- YARDIMCI METOTLAR ---

    // 1. Sadece bu sınıfın içinde veritabanı güncellemesi yaparken kullanacağımız Entity getirme metodu
    private User getUserEntityById(Long userId) {
        return userRepository.findById(userId)
                .orElseThrow(() -> new UserNotFoundException("Kullanıcı bulunamadı. ID: " + userId));
    }

    // 2. Entity nesnesini güvenli DTO'ya çeviren merkezi metot
    private UserResponse convertToResponse(User user) {
        return UserResponse.builder()
                .id(user.getId())
                .username(user.getUsername())
                .stylePreferences(user.getStylePreferences())
                .preferencesResetDate(user.getPreferencesResetDate())
                .build();
    }
}
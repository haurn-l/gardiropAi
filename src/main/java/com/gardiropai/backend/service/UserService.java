package com.gardiropai.backend.service;

import com.gardiropai.backend.dto.request.UserCreateRequest;
import com.gardiropai.backend.dto.response.UserResponse;

public interface UserService {
    UserResponse createUser(UserCreateRequest request);
    UserResponse getUserById(Long userId);
    UserResponse updateStylePreferences(Long userId, String newPreferences);

}

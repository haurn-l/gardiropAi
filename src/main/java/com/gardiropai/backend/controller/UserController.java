package com.gardiropai.backend.controller;

import com.gardiropai.backend.dto.request.UserCreateRequest;
import com.gardiropai.backend.dto.response.UserResponse;
import com.gardiropai.backend.service.UserService;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

/**
 * User işlemleri için REST API uç noktalarını yönetir.
 *
 * Güvenlik ve performans standartları gereği bu katmandan dışarıya
 * doğrudan User dönülmez. Tüm dönüşüm (DTO Mapping) işlemleri
 * Service katmanında izole edilmiş olup, istemciye yalnızca
 * UserResponse DTO'su iletilir.
 */

@RestController
@RequestMapping("/api/v1/users")
@RequiredArgsConstructor
public class UserController {

    private final UserService userService;

    @PostMapping("/register")
    public ResponseEntity<UserResponse> createUser(@Valid @RequestBody UserCreateRequest request) {
        return new ResponseEntity<>(userService.createUser(request), HttpStatus.CREATED);
    }

    @GetMapping("/{userId}")
    public ResponseEntity<UserResponse> getUserProfile(@PathVariable Long userId) {
        return ResponseEntity.ok(userService.getUserById(userId));
    }

    @PutMapping("/{userId}/style")
    public ResponseEntity<UserResponse> updateStyle(
            @PathVariable Long userId,
            @RequestBody String newPreferences) { // JSON gövdesinden gelecek metin
        return ResponseEntity.ok(userService.updateStylePreferences(userId, newPreferences));
    }
}
package com.gardiropai.backend.exception;

public class ClothingNotFoundException extends ResourceNotFoundException {
    public ClothingNotFoundException(String message) {
        super(message);
    }
}
package com.gardiropai.backend.service;

import com.gardiropai.backend.dto.request.CombineCreateRequest;
import com.gardiropai.backend.dto.response.CombineResponse;
import com.gardiropai.backend.entity.User;

import java.util.List;

public interface CombineService {

    CombineResponse createCombine(CombineCreateRequest request);
    List<CombineResponse> getUserCombines(Long userId);
    CombineResponse rateCombine(Long combineId, Integer ratingScore);
    void deleteCombine(Long combineId);
}

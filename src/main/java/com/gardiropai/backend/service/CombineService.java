package com.gardiropai.backend.service;

import com.gardiropai.backend.dto.request.CombineCreateRequest;
import com.gardiropai.backend.dto.response.CombineResponse;

import java.util.List;

public interface CombineService {

    CombineResponse createCombine(CombineCreateRequest request);
    List<CombineResponse> getUserCombines(Long userId);
    CombineResponse rateCombine(Long combineId, Integer ratingScore);
    CombineResponse updateFavorite(Long combineId, boolean favorite);
    void deleteCombine(Long combineId);
}

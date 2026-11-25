"""Visual season suitability; never a claim about measured fabric properties."""

from gardirop_ai_clothing.labeling.attribute_bank import rank_group


def suggest_season(vectors, front, back):
    candidates = rank_group(vectors, front, back, "season")
    gap = candidates[0]["score"] - candidates[1]["score"]
    value = candidates[0]["label"] if gap >= 0.01 else None
    return {
        "value": value,
        "leading_suggestion": candidates[0]["label"],
        "status": "suggested" if value else "uncertain",
        "source": "marqo_zero_shot",
        "candidates": candidates,
        "score_gap": gap,
        "abstain_gap": 0.01,
        "threshold_calibrated": False,
    }

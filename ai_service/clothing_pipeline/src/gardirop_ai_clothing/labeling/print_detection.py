"""Logos, graphics and textile patterns count as has_print; inspect both views."""

from gardirop_ai_clothing.labeling.attribute_bank import rank_group


def detect_print(vectors, front, back):
    candidates = rank_group(vectors, front, back, "pattern")
    plain = next(c for c in candidates if c["label"] == "plain")
    decorated = [c for c in candidates if c["label"] != "plain"]
    # Compare non-plain vs plain within each view, then use the most decorated view.
    gaps = {
        view: max(c[f"{view}_score"] for c in decorated) - plain[f"{view}_score"]
        for view in ("front", "back")
    }
    gap = max(gaps.values())
    value = True if gap >= 0.015 else False if gap <= -0.015 else None
    winning_view = max(gaps, key=gaps.get)
    winner = max(decorated, key=lambda c: c[f"{winning_view}_score"])
    reason = "score_gap"
    # A repeating textile pattern on only one uncertain view can be seam/texture
    # confusion. Abstain rather than assert it; back-only graphics/logos still count.
    fabric_patterns = {"striped", "checked", "floral", "dotted", "other_pattern"}
    if value is True and winner["label"] in fabric_patterns:
        other_view = "back" if winning_view == "front" else "front"
        other_gap = winner[f"{other_view}_score"] - plain[f"{other_view}_score"]
        if other_gap <= 0:
            value = None
            reason = "single_view_fabric_pattern_needs_review"
    return {
        "value": value,
        "policy_version": "pattern-cross-view-review-v2",
        "decision_reason": reason,
        "leading_pattern": winner["label"],
        "leading_suggestion": gap > 0,
        "status": "uncertain" if value is None else "suggested",
        "source": "marqo_zero_shot",
        "candidates": candidates,
        "decoration_minus_plain": gaps,
        "abstain_gap": 0.015,
        "threshold_calibrated": False,
        "meaning": "Visible logo, lettering, graphic or textile pattern on either side.",
    }

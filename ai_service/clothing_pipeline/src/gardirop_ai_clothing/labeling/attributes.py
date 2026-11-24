"""CPU color analysis and frozen Marqo zero-shot attribute suggestions."""

from gardirop_ai_clothing.labeling.attribute_bank import ATTRIBUTE_VERSION, load_bank
from gardirop_ai_clothing.labeling.color import detect_pair_color
from gardirop_ai_clothing.labeling.print_detection import detect_print
from gardirop_ai_clothing.labeling.season import suggest_season


class AttributeService:
    def __init__(self, bank_dir):
        self.bank_dir = bank_dir
        self._bank = None

    def analyze(self, front, back):
        if self._bank is None:
            self._bank = load_bank(self.bank_dir)
        vectors, metadata = self._bank
        color = detect_pair_color(front.prepared.original_cutout, back.prepared.original_cutout)
        season = suggest_season(vectors, front.embedding, back.embedding)
        printed = detect_print(vectors, front.embedding, back.embedding)
        tags = {"color": color["value"], "season": season["value"], "has_print": printed["value"]}
        details = {
            "version": ATTRIBUTE_VERSION,
            "prototype_sha256": metadata["sha256"],
            "color": color,
            "season": season,
            "has_print": printed,
            "limits": [
                "Season and print are uncalibrated zero-shot suggestions, not trained attribute heads.",
                "Season is visual suitability, not verified fabric thickness or insulation.",
                "has_print includes logos, graphics and fabric patterns; camera lighting affects color.",
            ],
        }
        return tags, details

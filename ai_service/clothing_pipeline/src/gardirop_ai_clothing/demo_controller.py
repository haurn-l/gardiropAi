"""Thin local demo actions; the existing draft service owns all AI/lifecycle work."""

from dataclasses import replace
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from gardirop_ai_clothing.contracts import subcategories_for_category
from gardirop_ai_clothing.errors import DraftConflictError, ImageProcessingError
from gardirop_ai_clothing.exports import export_confirmed_draft
from gardirop_ai_clothing.jobs import DraftService
from gardirop_ai_clothing.schemas import ClothingTags, DraftStatus, PhotoTaskStatus, ViewType

STATUS_TEXT = {
    "WAITING_VIEWS": "Fotoğraflar bekleniyor / işleniyor",
    "ANALYZING": "Etiket önerisi hazırlanıyor",
    "REVIEW_READY": "İncelemeye hazır",
    "FAILED": "İşlem tamamlanamadı",
    "CONFIRMED": "Yerel olarak onaylandı",
    "CANCELLED": "İptal edildi",
    "EXPIRED": "Taslağın süresi doldu",
}
PHOTO_TEXT = {
    "QUEUED": "Sırada",
    "PROCESSING": "İşleniyor",
    "READY": "Hazır",
    "FAILED": "Başarısız — yeniden deneyebilirsin",
    "CANCELLED": "İptal edildi",
    "DISCARDED": "Yeni fotoğrafla değiştirildi",
}


class DemoController:
    def __init__(self, service: DraftService, export_dir: str | Path):
        self.service = service
        self.export_dir = Path(export_dir).expanduser().resolve()

    def list_drafts(self):
        with self.service.repository.lock:
            records = [self.service.get(i) for i in self.service.repository.ids()]
        records = sorted(records, key=lambda s: s["created_at"], reverse=True)
        return [
            (
                f"{datetime.fromtimestamp(s['created_at']):%d.%m %H:%M:%S} · {s['category']} · {STATUS_TEXT[s['status']]}",
                s["id"],
            )
            for s in records
            if s["status"] not in {DraftStatus.CANCELLED, DraftStatus.EXPIRED}
        ]

    def snapshot(self, draft_id):
        with self.service.repository.lock:
            state = self.service.get(draft_id)
            result = (
                self.service.get_result(draft_id)
                if state["status"] in {DraftStatus.REVIEW_READY, DraftStatus.CONFIRMED}
                else None
            )
            previews, photo_status, failures = {}, {}, []
            for view in ("FRONT", "BACK"):
                job = state["jobs"].get(state["views"].get(view))
                photo_status[view] = PHOTO_TEXT[job["status"]] if job else "Fotoğraf bekleniyor"
                previews[view] = None
                if job and job["status"] == PhotoTaskStatus.READY:
                    previews[view] = str(
                        self.service.repository.path(f"{job['view_path']}/clean.webp")
                    )
                if job and job["error"]:
                    failures.append(
                        f"{'Ön' if view == 'FRONT' else 'Arka'}: {job['error']['code']}"
                    )
            if state["error"]:
                failures.append(state["error"]["code"])
            return {
                "state": state,
                "status_text": STATUS_TEXT[state["status"]],
                "failures": failures,
                "photo_status": photo_status,
                "previews": previews,
                "subcategories": list(subcategories_for_category(state["category"])),
                "tags": result.tags.model_dump(mode="json")
                if result
                else ClothingTags().model_dump(mode="json"),
                "diagnostics": result.model_diagnostics if result else {},
                "result": result.model_dump(mode="json") if result else None,
            }

    @staticmethod
    def tag_sources(snapshot):
        if not snapshot["result"]:
            return []
        original = snapshot["diagnostics"].get("original_tags", {})
        final = snapshot["tags"]
        rows = [["Ana kategori", "—", snapshot["state"]["category"], "Kullanıcı seçimi"]]
        labels = {
            "sub_category": "Alt tür",
            "color": "Renk",
            "season": "Mevsim",
            "has_print": "Baskı / desen / logo",
            "user_rating": "Kullanıcı puanı",
            "item_status": "Temiz / kirli",
            "custom_tags": "Özel etiketler",
        }

        def display(value):
            if value is None or value == []:
                return "Belirtilmedi"
            if isinstance(value, bool):
                return "Var" if value else "Yok"
            if isinstance(value, list):
                return ", ".join(value)
            return str(value)

        for key, title in labels.items():
            prior, value = original.get(key), final[key]
            if key in {"user_rating", "item_status", "custom_tags"}:
                source = (
                    "Kullanıcı bilgisi"
                    if value is not None and value != []
                    else "Kullanıcı girişi bekleniyor"
                )
            elif key not in original:
                source = "Eski kayıt; tahmin ayrıntısı yok"
            elif value != prior:
                source = "Kullanıcı düzeltmesi"
            elif prior is None:
                source = "Belirsiz / öneri yok; adaylar ayrıntı panelinde"
            else:
                source = {
                    "sub_category": "Kategoriye özel LR",
                    "color": "Maskeli renk analizi",
                    "season": "Marqo sıfır örnekli öneri",
                    "has_print": "Marqo sıfır örnekli öneri",
                }[key]
            suggestion = display(prior)
            detail = snapshot["diagnostics"].get("attributes", {}).get(key, {})
            if prior is None and "leading_suggestion" in detail:
                suggestion = f"{display(detail['leading_suggestion'])} (belirsiz)"
            rows.append([title, suggestion, display(value), source])
        return rows

    def upload(
        self, draft_id, view_type, file_path, *, expected_revision, rotation=0, capture_id=None
    ):
        if not file_path:
            raise ImageProcessingError("Önce bir fotoğraf seç.")
        limit = self.service.analysis.images.max_upload_bytes
        with Path(file_path).open("rb") as stream:
            data = stream.read(limit + 1)
        options = replace(
            self.service.analysis.images.default_options, manual_rotation=float(rotation)
        )
        return self.service.submit_photo(
            draft_id,
            view_type=ViewType(view_type),
            capture_id=capture_id or uuid4().hex,
            image_bytes=data,
            expected_revision=expected_revision,
            options=options,
        )

    def retry_photo(self, draft_id, view, *, expected_revision):
        state = self.service.get(draft_id)
        job_id = state["views"].get(ViewType(view).value)
        if not job_id:
            raise DraftConflictError("Yeniden denemeden önce fotoğraf yükle.")
        return self.service.retry_photo(draft_id, job_id, expected_revision=expected_revision)

    def confirm_and_export(self, draft_id, tags, *, expected_revision):
        # Keep tag edits and confirmation atomic relative to other browser sessions.
        with self.service.repository.lock:
            state = self.service.get(draft_id)
            if state["revision"] != expected_revision or type(expected_revision) is not int:
                raise DraftConflictError(
                    "Sonuç değişti; güncel fotoğraf ve etiketleri tekrar incele."
                )
            if state["status"] == DraftStatus.CONFIRMED:
                if self.service.get_result(draft_id).tags != ClothingTags.model_validate(tags):
                    raise DraftConflictError("Onaylanmış kıyafetin etiketleri değiştirilemez.")
            else:
                state = self.service.edit_tags(draft_id, tags, expected_revision=expected_revision)
            self.service.confirm(draft_id, expected_revision=state["revision"])
            return export_confirmed_draft(
                self.service,
                draft_id,
                self.export_dir,
                expected_revision=state["revision"],
            )

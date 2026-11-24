"""Gradio adapter for the shared draft service; no inference implementation here."""

import logging
from functools import wraps

import gradio as gr
from PIL import Image
from pydantic import ValidationError

from gardirop_ai_clothing.demo_controller import DemoController
from gardirop_ai_clothing.errors import (
    ClothingPipelineError,
    DraftConflictError,
    DraftNotFoundError,
    JobQueueFullError,
)
from gardirop_ai_clothing.image.io import composite_rgba_on_white

LOG = logging.getLogger(__name__)
CATEGORIES = [("Üst giyim", "üst"), ("Alt giyim", "alt"), ("Dış giyim", "dış")]
ROTATIONS = [("Değiştirme", 0), ("Sola çevir", 90), ("Sağa çevir", -90), ("Ters çevir", 180)]


def preview_image(path):
    """Preserve source pixels and show legacy transparent records on real white."""
    with Image.open(path) as image:
        return composite_rgba_on_white(image.convert("RGBA"))


def empty_session(draft_id=None):
    return {"id": draft_id, "hydrated": None, "previews": {}, "category": None, "export": None}


def review_revision(session, token):
    """Token is a normal browser component, not mutable server-side State."""
    if not session or not session.get("id"):
        raise DraftConflictError("Önce yeni kıyafet başlat veya kayıtlı taslak seç.")
    if (
        not isinstance(token, dict)
        or token.get("id") != session["id"]
        or type(token.get("revision")) is not int
    ):
        raise DraftConflictError("Ekrandaki taslak değişti; durumu yenile.")
    return session["id"], token["revision"]


def hydrate_tags(session, draft_id, result_revision):
    # Status polling must not overwrite edits while the user is typing.
    return session.get("hydrated") != [draft_id, result_revision]


def _guard(callback):
    @wraps(callback)
    def guarded(*args, **kwargs):
        try:
            return callback(*args, **kwargs)
        except gr.Error:
            raise
        except JobQueueFullError as exc:
            raise gr.Error("Sistem meşgul. Biraz sonra tekrar dene.") from exc
        except DraftConflictError as exc:
            raise gr.Error(
                "Taslak değişti veya bu işlem için hazır değil. Durumu yenileyip tekrar dene."
            ) from exc
        except ValidationError as exc:
            raise gr.Error(
                "Etiketler geçerli değil. Alt türü seçili kategoriye göre kontrol et."
            ) from exc
        except (ClothingPipelineError, OSError, ValueError) as exc:
            LOG.exception("Local demo action failed")
            raise gr.Error(
                "İşlem tamamlanamadı. Fotoğrafı ve taslağın durumunu kontrol edip tekrar dene."
            ) from exc

    return guarded


def build_demo(controller: DemoController):
    with gr.Blocks(
        title="GardropAI · Kıyafet ekle", analytics_enabled=False, delete_cache=(3600, 3600)
    ) as demo:
        gr.Markdown(
            "# GardropAI\nKıyafetinin önünü ve arkasını yükle, etiketleri kontrol et ve onayla."
        )
        gr.Markdown(
            "Yerel demo · Onaylanan kıyafetler bu bilgisayarda indirilebilir bir paket olarak saklanır."
        )
        gr.Markdown(
            "Fotoğrafı iyi ışıkta, kıyafetin tamamı kadrajda kalacak şekilde yükle. "
            "Ana kategoriyi doğru seç; yönü gerekiyorsa elle düzelt. "
            "Temizlenmiş görseli tam ekranda inceleyebilir ve tam çözünürlükte PNG indirebilirsin. "
            "Onay paketindeki fotoğraflar beyaz zeminli, kayıpsız WebP olarak saklanır."
        )
        session = gr.State(empty_session())
        token = gr.JSON(value=None, visible=False)
        with gr.Row():
            category = gr.Dropdown(CATEGORIES, value="üst", label="Ana kategori")
            new = gr.Button("Yeni kıyafet", variant="primary")
            change_category = gr.Button("Kategori değişikliğini uygula", interactive=False)
        with gr.Row():
            drafts = gr.Dropdown(choices=[], label="Kayıtlı taslağa devam et", value=None)
            refresh = gr.Button("Durumu yenile")
        status = gr.Markdown("Başlamak için kategori seçip **Yeni kıyafet** düğmesine bas.")
        files, rotations, reprocess, retries, photo_status, previews = {}, {}, {}, {}, {}, {}
        with gr.Row():
            for view, title in (("FRONT", "Ön"), ("BACK", "Arka")):
                with gr.Column():
                    files[view] = gr.File(
                        label=f"{title} fotoğrafı seç / yeniden çek",
                        type="filepath",
                        file_types=[".jpg", ".jpeg", ".png", ".webp"],
                        interactive=False,
                    )
                    rotations[view] = gr.Dropdown(ROTATIONS, value=0, label="Gerekirse yönü düzelt")
                    reprocess[view] = gr.Button(
                        f"{title} fotoğrafı yeniden işle", interactive=False
                    )
                    photo_status[view] = gr.Markdown(f"{title}: Fotoğraf bekleniyor")
                    previews[view] = gr.Image(
                        label=f"Temizlenmiş {title.lower()}",
                        image_mode="RGB",
                        format="png",
                        type="pil",
                        interactive=False,
                        height=420,
                        buttons=["download", "fullscreen"],
                    )
                    retries[view] = gr.Button(f"{title} fotoğrafı tekrar dene", interactive=False)
        gr.Markdown(
            "### Tüm etiketler\nAlt tür, renk, mevsim ve baskı önerilerini kontrol et. Mevsim/baskı sıfır örnekli Marqo önerisidir; belirsiz değer boş kalabilir. Puan, temiz/kirli durumu ve özel etiketler kullanıcı bilgisidir."
        )
        with gr.Row():
            subtype = gr.Dropdown(choices=[], label="Alt tür", interactive=False)
            color = gr.Textbox(label="Renk", interactive=False)
            season = gr.Dropdown(
                [
                    ("Belirtilmedi", ""),
                    ("Kış", "KIS"),
                    ("Yaz", "YAZ"),
                    ("Sonbahar", "SONBAHAR"),
                    ("İlkbahar", "ILKBAHAR"),
                    ("Her mevsim", "HER_MEVSIM"),
                ],
                value="",
                label="Mevsim",
                allow_custom_value=True,
                interactive=False,
            )
            printed = gr.Radio(
                [("Belirtilmedi", "unset"), ("Var", "yes"), ("Yok", "no")],
                value="unset",
                label="Baskı / desen / logo",
                interactive=False,
            )
        with gr.Row():
            rating = gr.Dropdown(
                [("Belirtilmedi", 0), *[(str(i), i) for i in range(1, 6)]],
                value=0,
                label="Kullanıcı puanı (1–5)",
                interactive=False,
            )
            item_status = gr.Dropdown(
                [("Belirtilmedi", ""), ("Temiz", "TEMIZ"), ("Kirli", "KIRLI")],
                value="",
                label="Kıyafetin durumu",
                interactive=False,
            )
            custom_tags = gr.Textbox(label="Özel etiketler (virgülle ayır)", interactive=False)
        with gr.Accordion("Model önerileri ve etiket kaynakları", open=True):
            sources = gr.Dataframe(
                headers=["Alan", "Model / analiz önerisi", "Son kaydedilen değer", "Kaynak"],
                datatype="str",
                interactive=False,
                wrap=True,
            )
        with gr.Accordion("Tüm model çıktıları, skorlar ve embedding", open=False):
            gr.Markdown(
                "LR skorları margin, Marqo skorları kosinüs benzerliğidir; olasılık değildir. "
                "Renk payları maske içindeki piksel oranıdır. Mevsim/baskı eşikleri henüz doğruluk verisiyle kalibre edilmedi."
            )
            raw_outputs = gr.JSON(label="Ayrıntılı sonuç (embedding dahil)")
        with gr.Row():
            save = gr.Button("Etiketleri kaydet", interactive=False)
            retry_analysis = gr.Button("Etiket önerisini tekrar dene", interactive=False)
            confirm = gr.Button("Onayla ve ZIP indir", variant="primary", interactive=False)
            cancel = gr.Button("Taslağı iptal et", interactive=False)
        download = gr.File(label="Onaylı kıyafet paketi", interactive=False)
        timer = gr.Timer(2)
        outputs = [
            session,
            token,
            category,
            drafts,
            status,
            subtype,
            color,
            season,
            printed,
            rating,
            item_status,
            custom_tags,
            sources,
            raw_outputs,
            save,
            retry_analysis,
            confirm,
            cancel,
            download,
            change_category,
            *files.values(),
            *rotations.values(),
            *reprocess.values(),
            *retries.values(),
            *photo_status.values(),
            *previews.values(),
        ]
        options = {
            "outputs": outputs,
            "concurrency_limit": 1,
            "concurrency_id": "demo-actions",
            "api_visibility": "private",
            "show_progress": "hidden",
        }

        def render(current, *, reset_files=False, export_path=None):
            current = dict(current or empty_session())
            choices = controller.list_drafts()
            answer = {
                drafts: gr.update(
                    choices=choices,
                    value=current["id"] if current["id"] in {v for _, v in choices} else None,
                )
            }
            if not current["id"]:
                answer.update(
                    {
                        session: empty_session(),
                        token: None,
                        status: "Başlamak için kategori seçip **Yeni kıyafet** düğmesine bas.",
                        download: None,
                        subtype: gr.update(choices=[], value=None, interactive=False),
                        color: gr.update(value="", interactive=False),
                        season: gr.update(value="", interactive=False),
                        printed: gr.update(value="unset", interactive=False),
                        rating: gr.update(value=0, interactive=False),
                        item_status: gr.update(value="", interactive=False),
                        custom_tags: gr.update(value="", interactive=False),
                        sources: [],
                        raw_outputs: None,
                    }
                )
                for component in [
                    save,
                    confirm,
                    cancel,
                    retry_analysis,
                    change_category,
                    *files.values(),
                    *reprocess.values(),
                    *retries.values(),
                ]:
                    answer[component] = gr.update(interactive=False)
                for component in files.values():
                    answer[component] = gr.update(value=None, interactive=False)
                for view in previews:
                    answer[previews[view]] = None
                    answer[photo_status[view]] = "Fotoğraf bekleniyor"
                return answer
            try:
                snapshot = controller.snapshot(current["id"])
            except DraftNotFoundError:
                answer = render(empty_session(), reset_files=True)
                answer[status] = (
                    "Taslağın süresi doldu veya temizlendi. Yeni bir kıyafetle devam edebilirsin."
                )
                return answer
            state = snapshot["state"]
            active = state["status"] not in {"CONFIRMED", "CANCELLED", "EXPIRED"}
            review = state["status"] == "REVIEW_READY"
            confirmed = state["status"] == "CONFIRMED"
            update_tags = hydrate_tags(
                current, state["id"], state["result_revision"] if review or confirmed else None
            )
            parent_title = dict((value, label) for label, value in CATEGORIES)[state["category"]]
            text = f"**{snapshot['status_text']} · {parent_title}**"
            if snapshot["failures"]:
                text += " · Fotoğrafı veya etiket önerisini yeniden deneyebilirsin."
            if confirmed:
                text += " · ZIP paketini indirebilirsin."
            answer.update(
                {
                    token: {"id": state["id"], "revision": state["revision"]},
                    status: text,
                    save: gr.update(interactive=review),
                    confirm: gr.update(
                        interactive=review or confirmed,
                        value="ZIP'i indir" if confirmed else "Onayla ve ZIP indir",
                    ),
                    cancel: gr.update(interactive=active),
                    change_category: gr.update(interactive=active),
                    retry_analysis: gr.update(
                        interactive=active
                        and state["status"] == "FAILED"
                        and controller.service._ready(state)
                    ),
                }
            )
            if current["category"] != state["category"]:
                answer[category] = gr.update(value=state["category"])
            current["category"] = state["category"]
            for component, value in (
                (subtype, snapshot["tags"]["sub_category"]),
                (color, snapshot["tags"]["color"] or ""),
                (season, snapshot["tags"]["season"] or ""),
                (printed, {True: "yes", False: "no", None: "unset"}[snapshot["tags"]["has_print"]]),
                (rating, snapshot["tags"]["user_rating"] or 0),
                (item_status, snapshot["tags"]["item_status"] or ""),
                (custom_tags, ", ".join(snapshot["tags"]["custom_tags"])),
            ):
                kwargs = {"interactive": review}
                if component is subtype:
                    kwargs["choices"] = snapshot["subcategories"]
                if update_tags:
                    kwargs["value"] = value
                answer[component] = gr.update(**kwargs)
            if update_tags:
                answer[sources] = controller.tag_sources(snapshot)
                answer[raw_outputs] = snapshot["result"]
            current["hydrated"] = [
                state["id"],
                state["result_revision"] if review or confirmed else None,
            ]
            old_previews = current.get("previews", {})
            for view in previews:
                path = snapshot["previews"][view]
                if reset_files or path != old_previews.get(view):
                    if path:
                        try:
                            answer[previews[view]] = preview_image(path)
                        except FileNotFoundError:
                            answer[previews[view]] = None
                    else:
                        answer[previews[view]] = None
                answer[files[view]] = gr.update(
                    interactive=active, **({"value": None} if reset_files else {})
                )
                if reset_files:
                    answer[rotations[view]] = gr.update(value=0)
                answer[reprocess[view]] = gr.update(interactive=active)
                job = state["jobs"].get(state["views"].get(view))
                answer[retries[view]] = gr.update(
                    interactive=active and job is not None and job["status"] == "FAILED"
                )
                answer[photo_status[view]] = snapshot["photo_status"][view]
            current["previews"] = snapshot["previews"]
            if export_path:
                current["export"] = {"revision": state["revision"], "path": str(export_path)}
                answer[download] = str(export_path)
            elif (
                not confirmed
                or not current.get("export")
                or current["export"]["revision"] != state["revision"]
            ):
                current["export"] = None
                answer[download] = None
            answer[session] = current
            return answer

        @_guard
        def start(parent):
            state = controller.service.create_draft(parent)
            return render(empty_session(state["id"]), reset_files=True)

        @_guard
        def select(draft_id):
            return render(empty_session(draft_id), reset_files=True)

        def checked(current, view_token):
            return review_revision(current, view_token)

        def upload(view):
            @_guard
            def action(path, rotation, parent, current, view_token):
                draft_id, revision = checked(current, view_token)
                if controller.service.get(draft_id)["category"] != parent:
                    raise gr.Error("Önce kategori değişikliğini uygula.")
                controller.upload(
                    draft_id, view, path, expected_revision=revision, rotation=rotation
                )
                return render(current)

            return action

        def retry(view):
            @_guard
            def action(current, view_token):
                draft_id, revision = checked(current, view_token)
                controller.retry_photo(draft_id, view, expected_revision=revision)
                return render(current)

            return action

        @_guard
        def change(parent, current, view_token):
            draft_id, revision = checked(current, view_token)
            controller.service.change_category(draft_id, parent, expected_revision=revision)
            return render(current)

        def tag_action(export=False):
            @_guard
            def action(
                parent,
                sub,
                colour,
                season_value,
                print_value,
                rating_value,
                status_value,
                custom_value,
                current,
                view_token,
            ):
                draft_id, revision = checked(current, view_token)
                if controller.service.get(draft_id)["category"] != parent:
                    raise gr.Error("Önce kategori değişikliğini uygula.")
                tags = {
                    "sub_category": sub or None,
                    "color": colour.strip() or None,
                    "season": season_value.strip() or None,
                    "has_print": {"yes": True, "no": False, "unset": None}[print_value],
                    "user_rating": rating_value or None,
                    "item_status": status_value or None,
                    "custom_tags": tuple(
                        dict.fromkeys(v.strip() for v in custom_value.split(",") if v.strip())
                    ),
                }
                path = None
                if export:
                    path = controller.confirm_and_export(draft_id, tags, expected_revision=revision)
                else:
                    controller.service.edit_tags(draft_id, tags, expected_revision=revision)
                return render(current, export_path=path)

            return action

        @_guard
        def cancel_action(current, view_token):
            draft_id, revision = checked(current, view_token)
            controller.service.cancel(draft_id, expected_revision=revision)
            return render(current)

        @_guard
        def retry_pair(current, view_token):
            draft_id, revision = checked(current, view_token)
            controller.service.retry_analysis(draft_id, expected_revision=revision)
            return render(current)

        @_guard
        def poll(current):
            return render(current)

        @_guard
        def load():
            choices = controller.list_drafts()
            return render(empty_session(choices[0][1] if choices else None), reset_files=True)

        new.click(start, inputs=[category], **options)
        drafts.input(select, inputs=[drafts], **options)
        change_category.click(change, inputs=[category, session, token], **options)
        for view in files:
            inputs = [files[view], rotations[view], category, session, token]
            files[view].upload(upload(view), inputs=inputs, **options)
            reprocess[view].click(upload(view), inputs=inputs, **options)
            retries[view].click(retry(view), inputs=[session, token], **options)
        tag_inputs = [
            category,
            subtype,
            color,
            season,
            printed,
            rating,
            item_status,
            custom_tags,
            session,
            token,
        ]
        save.click(tag_action(), inputs=tag_inputs, **options)
        confirm.click(tag_action(export=True), inputs=tag_inputs, **options)
        cancel.click(cancel_action, inputs=[session, token], **options)
        retry_analysis.click(retry_pair, inputs=[session, token], **options)
        refresh.click(poll, inputs=[session], **options)
        timer.tick(poll, inputs=[session], trigger_mode="always_last", **options)
        demo.load(load, **options)
    demo.queue(max_size=32, default_concurrency_limit=1, api_open=False)
    return demo

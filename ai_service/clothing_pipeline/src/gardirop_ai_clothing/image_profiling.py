"""Stage instrumentation for the isolated benchmark process only."""

from gardirop_ai_clothing import pipeline


def attach_image_stage_profiling(images, recorder):
    replacements = []
    targets = [
        (pipeline, "decode_uploaded_image", "image_decode"),
        (images._segmenter, "predict_alpha", "segmentation_with_prepost"),
        (pipeline, "clean_alpha_mask", "mask_cleanup"),
        (pipeline, "create_cropped_rgba", "foreground_crop"),
        (pipeline, "canonicalize_garment", "canonicalize_and_white"),
        (pipeline, "encode_transparent_webp", "transparent_webp_encoding"),
        (pipeline, "encode_white_webp", "white_webp_encoding"),
    ]

    def instrument(original, event):
        def run(*args, **kwargs):
            with recorder.span(event):
                return original(*args, **kwargs)

        return run

    for owner, name, event in targets:
        original = getattr(owner, name)
        wrapped = instrument(original, event)
        setattr(owner, name, wrapped)
        replacements.append((owner, name, original, wrapped))

    def restore():
        for owner, name, original, wrapped in reversed(replacements):
            if getattr(owner, name) is wrapped:
                setattr(owner, name, original)

    return restore

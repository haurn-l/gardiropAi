
# ============================================================
# GardropAI - Clothing AI Pipeline
# Development, quality checks and testing
# ============================================================

.DEFAULT_GOAL := help

UV := uv
SRC := src
TESTS := tests

.PHONY: help setup lock doctor lint format-check \
        fix test test-unit test-integration \
        test-regression coverage check clean


# ------------------------------------------------------------
# Help
# ------------------------------------------------------------

help:
	@echo ""
	@echo "GardropAI Clothing Pipeline"
	@echo "----------------------------"
	@echo "make setup             Install project dependencies"
	@echo "make lock              Update dependency lockfile"
	@echo "make models-prepare    Download and verify pinned model files"
	@echo "make models-offline    Prepare using the existing HF cache only"
	@echo "make models-check      Require all model artifact files"
	@echo "make models-env        Check ML package imports and versions"
	@echo "make attributes-prepare  Prepare frozen text prototypes on CPU (no training)"
	@echo "make attributes-check    Verify prepared attribute prototypes"
	@echo "make demo              Open local clothing review/export UI at 127.0.0.1:7861"
	@echo "make api               Run the local AI HTTP service at 127.0.0.1:8001"
	@echo "make api-check         Check HTTP contracts without neural inference"
	@echo "make api-key           Prepare a private local service key (does not print it)"
	@echo "make smoke-http        Test local HTTP with two chosen photos; prompts for paths/category"
	@echo "make compare-api-shapes  Final ratio/fallback HTTP test; requires TRT_RUN= and BASELINE="
	@echo "make compare-trt-memory  Compare TensorRT warmup cache; requires TRT_RUN= and BASELINE="
	@echo "make api-trt-lean      Start opt-in TensorRT API with one startup cache release"
	@echo "make compare-api-trt   Compare fresh PyTorch/TensorRT HTTP; requires TRT_RUN=passed_run"
	@echo "make api-trt           Start opt-in TensorRT API; requires TRT_RUN=passed_run"
	@echo "make tensorrt-env      Prepare separate native TensorRT experiment environment"
	@echo "make compare-birefnet-trt  Build/cache/test TensorRT; requires ONNX_RUN=passed_run"
	@echo "make onnx-env          Prepare separate ONNX experiment environment (network download)"
	@echo "make compare-birefnet-onnx  Export/test fixed-shape BiRefNet; requires BASELINE=FP16_run"
	@echo "make optimization-env  Record CUDA/ONNX/TensorRT export prerequisites (no inference)"
	@echo "make compare-marqo     Compare fresh FP32 and candidate FP16; requires BASELINE=directory"
	@echo "make measure-api       Measure prepared API; compare previous outputs via BASELINE=directory"
	@echo "make baseline-api      Measure isolated real HTTP latency/RAM/VRAM (CUDA; REPEATS=5)"
	@echo "make demo-check        Build the UI without server/model inference"
	@echo "make smoke-drafts      Run one isolated local draft with real models"
	@echo "make smoke-pipeline    Process two raw photos through segmentation, Marqo and LR"
	@echo "make smoke-classifier  Verify fusion/LR against 40 recorded Colab outputs"
	@echo "make smoke-marqo       Encode one prepared fixture and check the saved reference"
	@echo "make doctor            Validate project configuration"
	@echo "make lint              Run Ruff lint checks"
	@echo "make format-check      Check Python formatting"
	@echo "make fix               Auto-fix lint and formatting"
	@echo "make test              Run all tests"
	@echo "make test-unit         Run unit tests"
	@echo "make test-integration  Run integration tests"
	@echo "make test-regression   Run regression tests"
	@echo "make coverage          Generate test coverage report"
	@echo "make check             Run all quality checks"
	@echo "make clean             Remove generated caches"
	@echo "make birefnet-revision  Fetch Hugging Face revision SHA"
	@echo "make acceptance-local  Real local checks: CASES=cases.json OUTPUT=new_folder DEVICE=cuda"
	@echo "make smoke-white-output Check white background and lossless WebP without models"
	@echo "make smoke-segmentation Check local Dynamic against the Colab mask reference"
	@echo ""


# ------------------------------------------------------------
# Environment
# ------------------------------------------------------------

setup:
	$(UV) sync

lock:
	$(UV) lock


doctor:
	@$(UV) run python -c "from gardirop_ai_clothing.config import get_settings; s = get_settings(); assert s.model_manifest_path.is_file(); print('Configuration OK:', s.environment, s.device)"
	@$(UV) run python scripts/validate_checkpoints.py


# ------------------------------------------------------------
# Code quality
# ------------------------------------------------------------


SRC := src
TESTS := tests
SCRIPTS := scripts

lint:
	$(UV) run ruff check $(SRC) $(TESTS) $(SCRIPTS)

format-check:
	$(UV) run ruff format --check $(SRC) $(TESTS) $(SCRIPTS)

fix:
	$(UV) run ruff check $(SRC) $(TESTS) $(SCRIPTS) --fix
	$(UV) run ruff format $(SRC) $(TESTS) $(SCRIPTS)


# ------------------------------------------------------------
# Testing
# ------------------------------------------------------------

test:
	$(UV) run pytest -q

test-unit:
	$(UV) run pytest -q $(TESTS)/unit

test-integration:
	@if find $(TESTS)/integration -type f -name 'test_*.py' \
		-print -quit | grep -q .; then \
		$(UV) run pytest -q $(TESTS)/integration; \
	else \
		echo "No integration tests yet."; \
	fi

test-regression:
	@if find $(TESTS)/regression -type f -name 'test_*.py' \
		-print -quit | grep -q .; then \
		$(UV) run pytest -q $(TESTS)/regression; \
	else \
		echo "No regression tests yet."; \
	fi

coverage:
	$(UV) run pytest -q \
		--cov=gardirop_ai_clothing \
		--cov-report=term-missing \
		--cov-report=html:outputs/coverage


# ------------------------------------------------------------
# Complete validation
# ------------------------------------------------------------

check: doctor lint format-check test
	@echo ""
	@echo "All GardropAI quality checks passed."


# ------------------------------------------------------------
# Cleanup
# ------------------------------------------------------------

birefnet-revision:
	$(UV) run python scripts/get_birefnet_revision.py

# Same verified local adapter as the demo; optional IMAGE and DEVICE.
.PHONY: smoke-segmentation smoke-birefnet
smoke-segmentation:
	HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 $(UV) run python scripts/smoke_birefnet.py $(if $(IMAGE),--image "$(IMAGE)",) $(if $(DEVICE),--device "$(DEVICE)",) $(if $(REVISION),--revision "$(REVISION)",)

smoke-birefnet: smoke-segmentation

clean:
	@find $(SRC) $(TESTS) -type d -name '__pycache__' \
		-prune -exec rm -rf {} +
	@rm -rf .pytest_cache .ruff_cache
	@echo "Python and test caches cleaned."

# Pinned model artifacts; downloading does not run inference.
.PHONY: models-prepare models-offline models-check

models-prepare:
	$(UV) run python scripts/prepare_models.py

models-offline:
	$(UV) run python scripts/prepare_models.py --offline

models-check:
	$(UV) run python scripts/validate_checkpoints.py --require-ready

.PHONY: models-env
models-env:
	$(UV) run python -c "import importlib.metadata as m; import torch, torchvision, transformers, open_clip; print({p: m.version(p) for p in ('torch', 'torchvision', 'transformers', 'open_clip_torch')}); print('CUDA available:', torch.cuda.is_available()); print('Imports OK; no inference performed.')"

# One prepared-image encoder check; uses pinned local files only.
.PHONY: smoke-marqo
smoke-marqo:
	HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 $(UV) run python scripts/smoke_marqo.py $(if $(IMAGE),--image "$(IMAGE)",) $(if $(DEVICE),--device "$(DEVICE)",)

# Recorded features only; no encoder, segmentation, downloads or training.
.PHONY: smoke-classifier
smoke-classifier:
	HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 $(UV) run python scripts/smoke_parent_lr.py

# Paired-photo integration using pinned local files. Optional FRONT/BACK/CATEGORY/DEVICE.
.PHONY: smoke-pipeline
smoke-pipeline:
	@test -z "$(FRONT)" -a -z "$(BACK)" -o -n "$(FRONT)" -a -n "$(BACK)" || (echo "Provide both FRONT and BACK."; exit 1)
	HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 $(UV) run python scripts/smoke_pipeline.py $(if $(FRONT),--front "$(FRONT)" --back "$(BACK)",) $(if $(CATEGORY),--category "$(CATEGORY)",) $(if $(DEVICE),--device "$(DEVICE)",)

# Local draft lifecycle; separate scratch store, real pinned local models.
.PHONY: smoke-drafts
smoke-drafts:
	HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 $(UV) run python scripts/smoke_drafts.py $(if $(DEVICE),--device "$(DEVICE)",)

# Thin local UI over the same draft/AI core. No public share link.
.PHONY: demo demo-check
demo:
	GRADIO_ANALYTICS_ENABLED=False HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 $(UV) run python scripts/local_demo.py $(if $(PORT),--port "$(PORT)",) $(if $(DEVICE),--device "$(DEVICE)",)

demo-check:
	GRADIO_ANALYTICS_ENABLED=False HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 $(UV) run python scripts/check_demo.py

# Small tokenizer download + one-time CPU text encoding; no fitting/image inference.
.PHONY: attributes-prepare attributes-check
attributes-prepare:
	$(UV) run python scripts/prepare_attributes.py $(if $(OFFLINE),--offline,)

attributes-check:
	HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 $(UV) run python scripts/prepare_attributes.py --check

# Recorded segmentation mask only; verifies real opaque white file bytes.
.PHONY: smoke-white-output
smoke-white-output:
	HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 $(UV) run python scripts/check_white_output.py

# Small demo acceptance evidence. Explicit manifest and new output directory required.
.PHONY: acceptance-local
acceptance-local:
	@test -n "$(CASES)" -a -n "$(OUTPUT)" || (echo "Provide CASES=manifest.json OUTPUT=new_directory"; exit 1)
	HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 HF_MODULES_CACHE="$(CURDIR)/outputs/hf_modules" $(UV) run python scripts/acceptance_local.py --cases "$(CASES)" --output "$(OUTPUT)" --device "$(if $(DEVICE),$(DEVICE),cuda)"

# Local HTTP interface; a single process, without automatic reload.
.PHONY: api api-check

api:
	HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 HF_MODULES_CACHE="$(CURDIR)/outputs/hf_modules" $(UV) run uvicorn gardirop_ai_clothing.app:app --host 127.0.0.1 --port $(if $(PORT),$(PORT),8001) --workers 1

api-check:
	HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 $(UV) run python scripts/check_api.py

# Manual local HTTP smoke; prompts when photo paths/category are omitted.
.PHONY: smoke-http
smoke-http:
	$(UV) run python scripts/smoke_http.py $(if $(FRONT),--front "$(FRONT)",) $(if $(BACK),--back "$(BACK)",) $(if $(CATEGORY),--category "$(CATEGORY)",) $(if $(CAPTURE_GAP),--capture-gap "$(CAPTURE_GAP)",)

# Shared backend-to-AI credential. Never print or overwrite an existing key.
.PHONY: api-key
api-key:
	$(UV) run python scripts/prepare_api_key.py

# Isolated diagnostic server; does not change inference precision or algorithms.
.PHONY: baseline-api
baseline-api:
	HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 $(UV) run python scripts/benchmark_api.py $(if $(REPEATS),--repeats "$(REPEATS)",) $(if $(PORT),--port "$(PORT)",)

# Prepared production path, with optional read-only baseline comparison.
.PHONY: measure-api
measure-api:
	HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 $(UV) run python scripts/benchmark_api.py --prepared $(if $(REPEATS),--repeats "$(REPEATS)",) $(if $(PORT),--port "$(PORT)",) $(if $(BASELINE),--compare "$(BASELINE)",)

# Sequential, isolated precision experiment; configured defaults are not changed.
.PHONY: compare-marqo
compare-marqo:
	@test -n "$(BASELINE)" || (echo "Provide BASELINE=completed_FP32_run_directory"; exit 1)
	HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 $(UV) run python scripts/compare_marqo_precision.py --baseline "$(BASELINE)" $(if $(REPEATS),--repeats "$(REPEATS)",)

# OPT-05A: prerequisites only. No install, export, engine build or server.
.PHONY: optimization-env
optimization-env:
	HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 $(UV) run python scripts/check_optimization_env.py

# OPT-05B uses its own overlay environment. The application lock/environment are unchanged.
.PHONY: onnx-env compare-birefnet-onnx
onnx-env:
	$(UV) run python scripts/prepare_onnx_env.py

compare-birefnet-onnx:
	@test -n "$(BASELINE)" || (echo "Provide BASELINE=completed_FP16_run_directory"; exit 1)
	HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 $(UV) run python scripts/compare_birefnet_onnx.py --baseline "$(BASELINE)" $(if $(REPEATS),--repeats "$(REPEATS)",)

# OPT-05C: native TensorRT experiment only; production keeps PyTorch.
.PHONY: tensorrt-env compare-birefnet-trt
tensorrt-env:
	$(UV) run python scripts/prepare_tensorrt_env.py

compare-birefnet-trt:
	@test -n "$(ONNX_RUN)" || (echo "Provide ONNX_RUN=passed_OPT05B_directory"; exit 1)
	HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 $(UV) run python scripts/compare_birefnet_trt.py --onnx-run "$(ONNX_RUN)" $(if $(REPEATS),--repeats "$(REPEATS)",)

# OPT-05D: explicitly selected runtime; ordinary make api keeps PyTorch.
.PHONY: api-trt compare-api-trt
api-trt:
	@test -n "$(TRT_RUN)" || (echo "Provide TRT_RUN=passed_OPT05C_directory"; exit 1)
	PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 ./.venv-trt/bin/python scripts/run_tensorrt_api.py --trt-run "$(TRT_RUN)"

compare-api-trt:
	@test -n "$(TRT_RUN)" || (echo "Provide TRT_RUN=passed_OPT05C_directory"; exit 1)
	HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 $(UV) run python scripts/compare_api_tensorrt.py --trt-run "$(TRT_RUN)" $(if $(REPEATS),--repeats "$(REPEATS)",)

# OPT-05E: release unused allocator cache once after warmup; models stay on CUDA.
.PHONY: compare-trt-memory api-trt-lean
compare-trt-memory:
	@test -n "$(TRT_RUN)" -a -n "$(BASELINE)" || (echo "Provide TRT_RUN=accepted_engine_run BASELINE=completed_TensorRT_API_run"; exit 1)
	HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 $(UV) run python scripts/compare_trt_memory.py --trt-run "$(TRT_RUN)" --baseline "$(BASELINE)" $(if $(REPEATS),--repeats "$(REPEATS)",)

api-trt-lean:
	@test -n "$(TRT_RUN)" || (echo "Provide TRT_RUN=passed_OPT05C_directory"; exit 1)
	PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 ./.venv-trt/bin/python scripts/run_tensorrt_api.py --trt-run "$(TRT_RUN)" --release-warmup-cache

# OPT-06: diagnostics only, with pixel-preserving padded variants of the same demo photos.
.PHONY: compare-api-shapes
compare-api-shapes:
	@test -n "$(TRT_RUN)" -a -n "$(BASELINE)" || (echo "Provide TRT_RUN=accepted_engine_run BASELINE=completed_TensorRT_API_run"; exit 1)
	HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 $(UV) run python scripts/compare_api_shapes.py --trt-run "$(TRT_RUN)" --baseline "$(BASELINE)" $(if $(REPEATS),--repeats "$(REPEATS)",)

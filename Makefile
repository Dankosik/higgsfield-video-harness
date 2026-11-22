SHELL := /bin/sh
.DEFAULT_GOAL := help

export PYTHONDONTWRITEBYTECODE := 1

PYTHON ?= python3
SHELL_FILES := $(wildcard scripts/*.sh)

.PHONY: help check test shellcheck docs-check check-instructions memory-lint \
	brief-check campaign-check campaign-init memory-compile retro-harvest memory-search \
	lookbook slice-grid qa-clip qa-batch qa-voice qa-render qa-pixel-diff \
	assemble animatic budget-status

help: ## List available commands
	@awk 'BEGIN {FS = ":.*## "} /^[a-zA-Z0-9_-]+:.*## / {printf "  %-24s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

check: check-instructions docs-check memory-lint shellcheck test ## Run all offline harness checks and unit/integration tests
	@$(PYTHON) scripts/check-brief.py campaigns/example-product-spot
	@$(PYTHON) scripts/check-campaign.py campaigns/example-product-spot

test: ## Run Python unittest suite (validators, mock hf_guard, synthetic FFmpeg QA, lookbook & assembly)
	$(PYTHON) -m unittest discover -s tests -p 'test_*.py' -v

shellcheck: ## Lint all shell scripts with ShellCheck
	@test -n "$(SHELL_FILES)" || exit 0; \
	command -v shellcheck >/dev/null 2>&1 || { echo "shellcheck not installed" >&2; exit 2; }; \
	shellcheck -x -- $(SHELL_FILES)

docs-check: ## Verify all relative Markdown links and heading anchors offline
	$(PYTHON) scripts/check-docs.py .

check-instructions: ## Validate .agents/ roles, skills, openai.yaml, and .codex/config.toml sync
	$(PYTHON) scripts/check-instructions.py .

memory-lint: ## Validate studio/ memory, brands/*/taste.md caps, taste-active.md freshness, and review logs
	$(PYTHON) scripts/check-memory.py .

memory-compile: ## Compile campaigns/<CAMPAIGN>/taste-log.md into conflict-free taste-active.md (CAMPAIGN=<slug|path>)
	@test -n "$(CAMPAIGN)" || { echo "memory-compile requires CAMPAIGN=<slug|path>" >&2; exit 2; }
	$(PYTHON) scripts/memory_compile.py "$(if $(wildcard $(CAMPAIGN)/taste-log.md),$(CAMPAIGN),$(if $(wildcard campaigns/$(CAMPAIGN)/taste-log.md),campaigns/$(CAMPAIGN),$(CAMPAIGN)))"

retro-harvest: ## Mine receipts, review logs, prompt churn, and Supersedes flips for R6 studio-retro (CAMPAIGN=<slug|path>)
	@test -n "$(CAMPAIGN)" || { echo "retro-harvest requires CAMPAIGN=<slug|path>" >&2; exit 2; }
	$(PYTHON) scripts/retro_harvest.py "$(if $(wildcard $(CAMPAIGN)/brief.md),$(CAMPAIGN),$(if $(wildcard campaigns/$(CAMPAIGN)/brief.md),campaigns/$(CAMPAIGN),$(CAMPAIGN)))" $(if $(OUT),--out "$(OUT)")

memory-search: ## Full-text BM25 search across studio/, brands/, and campaigns/ memory (Q="<terms>" [SCOPE=all|studio|brands|campaigns])
	@test -n "$(Q)" || { echo "memory-search requires Q='<terms>'" >&2; exit 2; }
	$(PYTHON) scripts/memory_search.py "$(Q)" $(if $(SCOPE),--scope "$(SCOPE)") $(if $(LIMIT),--limit "$(LIMIT)")

brief-check: ## Verify campaigns/<CAMPAIGN>/brief.md invariants (CAMPAIGN=<slug|path>)
	@test -n "$(CAMPAIGN)" || { echo "brief-check requires CAMPAIGN=<slug|path>" >&2; exit 2; }
	$(PYTHON) scripts/check-brief.py "$(if $(wildcard $(CAMPAIGN)/brief.md),$(CAMPAIGN),$(if $(wildcard campaigns/$(CAMPAIGN)/brief.md),campaigns/$(CAMPAIGN),$(CAMPAIGN)))"

campaign-check: ## Verify brief.md + taste-log.md + shotlist.json invariants & spend estimates (CAMPAIGN=<slug|path>)
	@test -n "$(CAMPAIGN)" || { echo "campaign-check requires CAMPAIGN=<slug|path>" >&2; exit 2; }
	$(PYTHON) scripts/check-campaign.py "$(if $(wildcard $(CAMPAIGN)/shotlist.json),$(CAMPAIGN),$(if $(wildcard campaigns/$(CAMPAIGN)/shotlist.json),campaigns/$(CAMPAIGN),$(CAMPAIGN)))"

campaign-init: ## Scaffold a new campaign folder with brief.md + taste-log.md (SLUG=<name> [BRAND=<brand>] [TRACK=<track>] [SUB_FLOWS=a,b])
	@test -n "$(SLUG)" || { echo "campaign-init requires SLUG=<name>" >&2; exit 2; }
	$(PYTHON) scripts/campaign_init.py --slug "$(SLUG)" $(if $(BRAND),--brand "$(BRAND)") $(if $(TRACK),--track "$(TRACK)") $(if $(SUB_FLOWS),--sub-flows "$(SUB_FLOWS)")

budget-status: ## Show spent vs remaining Campaign cap and per-round spend (CAMPAIGN=<slug|path>)
	@test -n "$(CAMPAIGN)" || { echo "budget-status requires CAMPAIGN=<slug|path>" >&2; exit 2; }
	$(PYTHON) scripts/hf_guard.py status --campaign "$(if $(wildcard $(CAMPAIGN)/brief.md),$(CAMPAIGN),$(if $(wildcard campaigns/$(CAMPAIGN)/brief.md),campaigns/$(CAMPAIGN),$(CAMPAIGN)))"

lookbook: ## Stitch 1+ images into a labeled A/B/C Lookbook or Stills Strip PNG (FILES="a.png b.png" OUT=<out.png>)
	@test -n "$(FILES)" && test -n "$(OUT)" || { echo "lookbook requires FILES='img1 img2 ...' OUT=<out.png>" >&2; exit 2; }
	$(PYTHON) scripts/qa_media.py lookbook $(FILES) --out "$(OUT)" $(if $(LABELS),--labels "$(LABELS)") $(if $(COLS),--cols "$(COLS)")

slice-grid: ## Slice a 2x2 or 3x3 angle sheet into standalone PNG tiles (FILE=<sheet.png> OUT_DIR=<dir> [ROWS=3] [COLS=3] [TRIM=0] [PREFIX=tile])
	@test -n "$(FILE)" && test -n "$(OUT_DIR)" || { echo "slice-grid requires FILE=<sheet.png> OUT_DIR=<dir>" >&2; exit 2; }
	$(PYTHON) scripts/qa_media.py slice "$(FILE)" --out-dir "$(OUT_DIR)" --rows "$(or $(ROWS),3)" --cols "$(or $(COLS),3)" --trim "$(or $(TRIM),0)" --prefix "$(or $(PREFIX),tile)"

qa-clip: ## Probe one video clip, optional 3x2 sheet, and optional 1:1 native crops (FILE=<mp4> [SHEET=<png>] [CROPS=<png>] [CROP_FOCUS=thirds|center|left|right])
	@test -n "$(FILE)" || { echo "qa-clip requires FILE=<path.mp4>" >&2; exit 2; }
	$(PYTHON) scripts/qa_media.py clip "$(FILE)" $(if $(SHEET),--sheet "$(SHEET)") $(if $(CROPS),--crops "$(CROPS)") $(if $(CROP_FOCUS),--crop-focus "$(CROP_FOCUS)")

qa-batch: ## Audit cross-shot resolution, FPS, and HF-sharpness consistency across R5 clips (FILES="a.mp4 b.mp4" [STRICT=1])
	@test -n "$(FILES)" || { echo "qa-batch requires FILES='clip1.mp4 clip2.mp4 ...'" >&2; exit 2; }
	$(PYTHON) scripts/qa_media.py batch $(FILES) $(if $(STRICT),--strict)

qa-voice: ## Check VO duration window using 100ms RMS energy (FILE=<wav> WINDOW=<sec>)
	@test -n "$(FILE)" && test -n "$(WINDOW)" || { echo "qa-voice requires FILE=<audio> WINDOW=<sec>" >&2; exit 2; }
	$(PYTHON) scripts/qa_media.py voice "$(FILE)" --window "$(WINDOW)"

qa-render: ## Validate final assembled render loudness, black/frozen frames, sheet, 1:1 crops, and optional <=20s review slices (FILE=<mp4> [SHEET=<png>] [CROPS=<png>] [SLICES_DIR=<dir>])
	@test -n "$(FILE)" || { echo "qa-render requires FILE=<path.mp4>" >&2; exit 2; }
	$(PYTHON) scripts/qa_media.py render "$(FILE)" $(if $(SHEET),--sheet "$(SHEET)") $(if $(CROPS),--crops "$(CROPS)") $(if $(CROP_FOCUS),--crop-focus "$(CROP_FOCUS)") $(if $(SLICES_DIR),--verify-slices-dir "$(SLICES_DIR)")

qa-pixel-diff: ## Verify untouched pass-through frames match source plate (FILE=<processed.mp4> PLATE=<source.mp4> [WINDOWS=2-7,12-17] [TOL=3.5])
	@test -n "$(FILE)" && test -n "$(PLATE)" || { echo "qa-pixel-diff requires FILE=<processed.mp4> PLATE=<source.mp4>" >&2; exit 2; }
	$(PYTHON) scripts/qa_media.py pixel-diff "$(FILE)" --plate "$(PLATE)" $(if $(WINDOWS),--windows "$(WINDOWS)") $(if $(TOL),--tolerance "$(TOL)")

assemble: ## Assemble selected takes from CAMPAIGN=<slug|path> into master.mp4 + stems/ (optional LUT=<.cube> GRAIN=<1..20> OVERLAY=<mov> DUCK_MUSIC=1 BPM=<N>)
	@test -n "$(CAMPAIGN)" || { echo "assemble requires CAMPAIGN=<slug|path>" >&2; exit 2; }
	@cdir="$(if $(wildcard $(CAMPAIGN)/shotlist.json),$(CAMPAIGN),$(if $(wildcard campaigns/$(CAMPAIGN)/shotlist.json),campaigns/$(CAMPAIGN),$(CAMPAIGN)))"; \
	bash scripts/assemble.sh --campaign "$$cdir" --manifest "$$cdir/shotlist.json" \
		--out "$(or $(OUT),$$cdir/media/exports/master.mp4)" \
		--stems-dir "$(or $(STEMS),$$cdir/media/exports/stems)" \
		$(if $(MUSIC),--music "$(MUSIC)") \
		$(if $(VO),--vo "$(VO)") \
		$(if $(LUT),--lut "$(LUT)") \
		$(if $(GRAIN),--grain "$(GRAIN)") \
		$(if $(OVERLAY),--overlay "$(OVERLAY)") \
		$(if $(BPM),--bpm "$(BPM)") \
		$(if $(DUCK_MUSIC),--duck-music)

animatic: ## Build a zero-video-credit still animatic from approved stills in CAMPAIGN=<slug|path>
	@test -n "$(CAMPAIGN)" || { echo "animatic requires CAMPAIGN=<slug|path>" >&2; exit 2; }
	@cdir="$(if $(wildcard $(CAMPAIGN)/shotlist.json),$(CAMPAIGN),$(if $(wildcard campaigns/$(CAMPAIGN)/shotlist.json),campaigns/$(CAMPAIGN),$(CAMPAIGN)))"; \
	bash scripts/assemble.sh --animatic --campaign "$$cdir" --manifest "$$cdir/shotlist.json" \
		--out "$(or $(OUT),$$cdir/media/exports/animatic.mp4)" \
		$(if $(MUSIC),--music "$(MUSIC)") \
		$(if $(VO),--vo "$(VO)")

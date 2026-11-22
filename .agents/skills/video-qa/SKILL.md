---
name: video-qa
description: "Internal technical, continuity, and Blind Viewer Read narrative QA plus Dailies grid packaging. Use when running qa_media.py probes, 1:1 crop strips, batch audits, or lookbook grids, or filtering defects, taste regressions, and narrative misreads before Director Dailies."
---

# Video QA

Canonical owner of deterministic media probes (`scripts/qa_media.py`), Dailies
grid packaging, mandatory `1:1` native-pixel crop verification, and the binary
pre-Dailies Visual Critic rubric. Follow
[Pre-Dailies Visual Critic](../../../docs/delegation.md#pre-dailies-visual-critic):
fresh `reviewer-agent` lanes filter defects, continuity breaks,
`TASTE_REGRESSION`s, and `NARRATIVE_DEFECT`s (Blind Viewer Read against
`Narrative Lock` per [`video-narrative`](../video-narrative/SKILL.md)) while
leaving `A / B / C` picks and `LOCKED` sign-off solely to the Director.

## Deterministic Probes & Grid Builders (`scripts/qa_media.py`)

Always pass `--json` when capturing reports for `reviewer-agent` handoffs
(`make qa-*` runs the same checks for human output):

- `scripts/qa_media.py clip <mp4> --sheet <png> [--crops <png>] [--crop-focus thirds|center|left|right] --json` (`make qa-clip`) — probes resolution, FPS, codec, duration, `video_bitrate_kbps`, `hf_edge_energy` (Laplacian sharpness proxy), audio, black gaps (`>= 0.5s`), `frozen_tail`, `fully_static_clip`, full-FPS **temporal stutter & motion-jerk telemetry** (`duplicate_frame_ratio`, `stutter_events`, `motion_jerk_spikes`), warns on `non_standard_dimensions` (`1918×1080`) and `low_video_bitrate`, writes a `3x2` contact sheet, and—when `--crops` is passed—writes an **unscaled `1:1` native-pixel 3-frame crop strip** (default `thirds` sweeps left/center/right).
- `scripts/qa_media.py batch <clip1> <clip2> ... [--strict] --json` (`make qa-batch`) — audits cross-shot resolution, FPS, non-multiple-of-4 dimensions, low `1080p` bitrate, `hf_sharpness_outlier` (`> 1.5×` clean median), **`inter_shot_luma_jump`** (`> 95` exposure jump across cuts), and **`bitrate_disparity`** (`> 4.0×` starved draft next to flagship) before `make assemble`.
- `scripts/qa_media.py pixel-diff <processed.mp4> --plate <source.mp4> [--windows "2-7,12-17"] [--tolerance 3.5] --json` (`make qa-pixel-diff`) — verifies untouched pass-through frames outside active VFX/V2V windows match the source plate (catches silent AE/FFmpeg color-management darkening).
- `scripts/qa_media.py voice <wav> --window <sec> --json` (`make qa-voice`) — checks 100ms RMS active speech bounds (`speech_start`, `speech_end`) against the target window and flags `leading_silence` (`>= 0.25s`) or `long_internal_pause` (`>= 0.45s`) for dialogue cadence tuning.
- `scripts/qa_media.py render <mp4> --sheet <png> [--crops <png>] [--verify-slices-dir <dir>] --json` (`make qa-render`) — enforces `-14 LUFS (±1.0 LU)` and `<= -1.0 dBTP` on `draft_cut.mp4` / `master.mp4`, and (when `--verify-slices-dir` is passed on masters `> 20s`) stream-copies `<= 20s` `part_XX.mp4` slices for fast `reviewer-agent` playback.
- `make lookbook FILES="..." OUT=<png> LABELS="A,B,C"` — burns visual badges onto tiles for `R2` Lookbooks and `R3` stills strips.
- `scripts/qa_media.py slice <sheet.png> --out-dir <dir> --rows 3 --cols 3 [--trim 4] --json` (`make slice-grid`) — splits `2x2`/`3x3` multi-angle sheets (`nano_banana_2_shots`) into standalone PNG tiles before upload.
- `scripts/qa_media.py log-review --campaign <dir> --round <R> --asset <id> --verdict <PASS|CONCERNS|FAIL|REVIEW_HANDOFF_INVALID> [--defect-class <CLASS>] [--qa-report <json>] [--sheet <png>] [--crops <png>] [--reviewer-id <id>] [--summary "..."] --json` — appends every `#review-result` to `campaigns/<slug>/qc/review-log.jsonl` under `flock`. **Fail-closed:** `R4`/`R4A`/`R4B`/`R5` `PASS` is mechanically rejected unless both `--qa-report` and `--sheet` point to existing files (plus `--crops` pointing to an existing `1:1` PNG for `R5`).

## Mandatory Direct MP4 Playback, Fast Turn Budget & Binary QC Rubric

Shrunk `480px` `3x2` sheets hide 94% of a clip's frames (micro-stutters,
warping limbs, popping logos, and bad dissolves) as well as halos and face melt.
Every `R4`/`R5` video review MUST be executed by a **fresh `reviewer-agent`
lane** (never self-graded by Root Producer) within a **fast bounded budget
(`<= 12` tool calls, batching text/JSON/PNGs up to 5–6 per turn and reading
at most 2 `.mp4` files per turn to avoid context compaction; zero ad-hoc
shell/Python slicing scripts)** that inspects: (1) `qa_media.py` JSON
(`temporal_stutter`, `motion_jerk`, `inter_shot_luma_jump`,
`bitrate_disparity`), (2) **actual `.mp4` playback via `read_file`** on hero
clips and pre-sliced `<= 20s` `qc/verify_slices/part_*.mp4` master segments,
(3) `1:1` `--crops` strips + `batch --strict --json` for every `R5` or upscaled
handoff, and (4) the **6-point brief/mobile audit** (product/place accuracy,
zero stray logos/garbled lettering, offer/copy accuracy, phone-size
readability, safe framing, cut-to-cut continuity):

| Observed Signal (JSON or `1:1` `--crops`) | Verdict | Defect Class | `reopen_owner` & Required Action |
| :--- | :--- | :--- | :--- |
| Missing `qa_media.py` JSON, `3x2` sheet, `R5` `--crops` strip, `R5` `batch --strict`, or `taste-log.md` | `REVIEW_HANDOFF_INVALID` | — | `Worker(<asset_id>)` — produce missing proof; never pass blindly |
| White/dark edge halo, ringing, muddy/plastic face, or eyelid/cheek color blotch on `--crops` | `FAIL` | `MEDIA_TECH_DEFECT` | `Root Producer` — stop upscaling; switch shot to native `1080p` path ([Mastering & Upscaling](../higgsfield-cli/references/mastering-and-upscaling.md)) |
| `non_standard_dimensions` (`1918×1080`), `resolution_mismatch`, or `fps_mismatch` in `batch` | `FAIL` | `MEDIA_TECH_DEFECT` | `Root Producer` — re-render natively at exact `1920×1080` & `fps_target` |
| `hf_sharpness_outlier` (`> 1.5×` clean median) + visible crunch/ringing on `--crops` | `FAIL` | `MEDIA_TECH_DEFECT` | `Root Producer` — replace upscaled outlier with native `1080p` take |
| `hf_sharpness_outlier` (`> 1.5×`) between clean native shots (zero halos/melt on `--crops`) | `CONCERNS` | `CONCERN` | `Root Producer` — confirm genuine scene detail; match via shared 35mm grain if needed |
| `low_video_bitrate` (`< 1800 kbps` at `1080p`) with visible compression softness/banding | `FAIL` | `MEDIA_TECH_DEFECT` | `Worker(<asset_id>)` — re-run with `--bitrate_mode high` (or alternate `1080p` engine) |
| 180° room flip, wrong reverse wall, teleporting door/window, or front-pose mirror clone | `FAIL` | `CONTINUITY_DEFECT` | `Root Producer` — lock missing Reverse Wall (`R2B`) and re-stage `R3` still with `N/E/S/W` `CAM` facing ([Locations & Props](../video-consistency/references/locations-and-props.md#6-spatial--prop-failure-diagnostics)) |
| Prop/building Scale Drift, *Lighting Bake-In*, or off-screen prop bleeding into frame | `FAIL` | `VISUAL_DRIFT_DEFECT` | `Worker(<asset_id>)` — prune off-screen refs, bind Scale Ref / neutral `#808080` prop plate, re-stage `R3` |
| Single handheld prop warps mid-clip while acting, camera, and set stay locked | `FAIL` | `VISUAL_DRIFT_DEFECT` | `Root Producer` — rescue surgically via `hf_mult_replace_object` / `kling4_0 --mode video-edit` (keep take) |
| Camera drifts on static hold, walls bend like rubber, pan edges strobe, or motion freezes stiff | `FAIL` | `VISUAL_DRIFT_DEFECT` | `Worker(<asset_id>)` — apply One Variable Per Re-roll fix ([Camera Control](../video-direction/references/camera-control.md#6-camera-failure-diagnostics)) |
| Face morphs on head turn, alien/warped teeth on smile, lens stare, or wide-shot face collapse | `FAIL` | `CONTINUITY_DEFECT` | `Worker(<asset_id>)` — bind `3/4`/profile + Expression Calibration (`R2B`), bake `40–60%` expression in `2k`/`4k` `R3`, strip face prose from video ([Characters & Expressions](../video-consistency/references/characters-and-expressions.md#6-face--expression-failure-diagnostics)) |
| Mid-clip face likeness softens on an otherwise golden acting take | `FAIL` | `VISUAL_DRIFT_DEFECT` | `Root Producer` — rescue surgically via `kling4_0 --mode video-edit` (bound to canonical `R2A` portrait) or Web Face Swap (keep performance) |
| Cold `R3`/`R4B` Blind Viewer Read triggers `Primary Misread Risk`, or a proof-bearing object fails `0.1s` instant recognition / referent cohesion | `FAIL` | `NARRATIVE_DEFECT` | `Root Producer` / `Worker(<asset_id>)` — replace ambiguous object silhouette or strengthen misread-foreclosing beat before animating ([Narrative Diagnostics](../video-narrative/references/narrative-diagnostics.md#symptom-to-fix-table)) |
| Shot fails the Deletion Test (zero-delta filler repeating an adjacent beat), breaks `BUT / THEREFORE` causality, over-explains (`2 + 2`), or breaks `Narrative Voice` | `FAIL` / `CONCERNS` | `NARRATIVE_DEFECT` | `Root Producer` — cut filler shot, restore `[PAUSE Ns]` / audio counterpoint, or align copy to `Narrative Lock` ([Narrative Diagnostics](../video-narrative/references/narrative-diagnostics.md#symptom-to-fix-table)) |
| Visible on-camera speaker's mouth flaps noticeably out of sync with VO, OR a silent/non-speaking character accidentally moves its mouth while another character or off-screen narrator speaks *(naturally silent closed-mouth characters under off-screen VO are valid)* | `FAIL` | `MEDIA_TECH_DEFECT` | `Root Producer` — for visible on-camera dialogue use audio-driven lip-sync (`intone` / Lipsync Studio / native-speech engine); for off-screen VO or listeners, explicitly direct closed-mouth silent expressions |
| Subtitle wall (`> 2` short lines / `> 7` words frozen `> 3.5s`), paraphrased captions contradicting spoken audio, or mispronounced VO inverting meaning | `FAIL` | `NARRATIVE_DEFECT` | `Root Producer` — split into verbatim `2–6` word cues turning every `1.0–2.5s` synced to actual audio timestamps; regenerate broken VO line (never ship an inverted joke) |
| Static `> 8s` single-camera shot causing pacing fatigue, warped hands/paws/held props, crawling background lines, or visible bridge jump-cut seam | `FAIL` | `VISUAL_DRIFT_DEFECT` | `Root Producer` / `Worker(<asset_id>)` — break into `3–6s` cuts/angles/reaction inserts or `4K` 2× punch-ins; never stretch `4–5` stills across `60s` |

## Four Audit Pillars & Root-Cause Escalation

- **Four visual & narrative audit pillars:** Inspect fixed primary artifacts
  only (`brief.md`, `taste-active.md`/`taste-log.md`, `style-bible.md`,
  `script.md`/`storyboard.md` `Narrative Lock`, `shotlist.json`,
  `media/references/`, candidate images/`3x2` sheets/`1:1` `--crops` strips,
  `qa_media.py --json` reports) across: (1) green `qa_media.py` JSON, (2)
  `continuity_lock` axes (facial bone structure, teeth/eyelid/gaze/expression
  continuity, 4-wall/reverse geography, prop/building scale, absence of
  *Lighting Bake-In* or off-screen bleed, mid/end-frame prop integrity) plus
  the exact `test_take_check` oracle
  ([Ad Craft Glossary](../../../docs/ad-craft-glossary.md)), (3) every active
  rule in `taste-active.md`/`taste-log.md`, and (4) **Blind Viewer Read** on
  `R3` (`stills_strip.png` / `animatic.mp4`) and `R4B` (`draft_cut.mp4`)
  against `Narrative Lock` (`0.1s` object readability, zero triggered
  `Primary Misread Risk`, `BUT / THEREFORE` chain, Deletion Test, `2 + 2`
  restraint — [Blind Viewer Read Protocol](../video-narrative/references/narrative-diagnostics.md#blind-viewer-read-protocol-r3--r4b-pre-dailies-qc);
  never judge creative taste).
- **Root-cause repair vs. honest escalation:** Return
  [Review Result](../../../docs/delegation.md#review-result). Inside
  `Max auto-retries/asset` and `--round-cap`, repair root causes on unlocked
  assets using **One Variable Per Re-roll** and the linked domain diagnostics
  ([Narrative](../video-narrative/references/narrative-diagnostics.md#symptom-to-fix-table),
  [Prompting](../video-direction/references/model-prompting.md#symptom-to-fix-prompt-diagnostics),
  [Camera](../video-direction/references/camera-control.md#6-camera-failure-diagnostics),
  [Spatial](../video-consistency/references/locations-and-props.md#6-spatial--prop-failure-diagnostics),
  [Faces](../video-consistency/references/characters-and-expressions.md#6-face--expression-failure-diagnostics),
  [Mastering](../higgsfield-cli/references/mastering-and-upscaling.md#3-step-by-step-r5-mastering--verification-runbook))
  rather than repeating identical prompts. If caps exhaust, surface any
  surviving borderline `CONCERN` openly in one line of Dailies.

*Done when:* every required `qa_media.py` JSON, `3x2` sheet, `R5` `1:1` `--crops`
strip, and `batch --strict` audit is inspected via vision tool, technical trash,
`TASTE_REGRESSION`s, and `NARRATIVE_DEFECT`s are filtered out, and clean Dailies
artifacts are ready for the Director.

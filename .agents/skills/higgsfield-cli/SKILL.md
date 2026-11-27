---
name: higgsfield-cli
description: "Live Higgsfield CLI, Web Unlimited, model selection, and R4->R5 mastering. Use when inspecting schemas or CEL rules, quoting or running guarded jobs/uploads via hf_guard.py, picking image/video/audio models, or planning native 1080p mastering and upscaling."
---

# Higgsfield CLI

Canonical owner of live Higgsfield schemas, credit-safe `hf_guard.py` execution,
`0 cr.` Web Unlimited routing, model selection, `R4 → R5` native mastering, and
Web UI vs. CLI boundaries.

## Reference Map

Load only the reference needed for the current decision:

| Need | Reference |
| --- | --- |
| `0 cr.` Web Unlimited browser protocol, image/video/audio benchmarks, round defaults & 30s stack presets | [`references/model-selection.md`](references/model-selection.md) |
| `R4 → R5` deterministic 5-path mastering, 5-step verification runbook, 6-rule Upscale Gate & upscaler specs | [`references/mastering-and-upscaling.md`](references/mastering-and-upscaling.md) |
| All live CLI CEL traps, parameter gotchas & copy-ready guarded `hf_guard.py` recipes | [`references/live-workflows.md`](references/live-workflows.md) |

## Core Rules

- **Live schema & cost truth:** Query `higgsfield model get <id> --json`,
  `workflow get <id> --json`, `voices list`, `preset list <type>`, `account status`,
  and `generate cost` before trusting static snapshots. Never pass private local
  file paths to `generate cost` before upload approval (local paths auto-upload);
  use cost-affecting flags or already-uploaded UUIDs only.
- **Mandatory spend & upload guard:** Route every paid CLI job through
  `python3 scripts/hf_guard.py preflight` / `run` and every tracked upload
  (including downloaded Web Unlimited files) through `hf_guard.py upload --round <R>`
  (`0 cr.`), honoring [Budget & Lock Invariants](../../../docs/workflow.md#budget--lock-invariants).
  Check `python3 scripts/hf_guard.py --help` for flags.
- **3-Tier Cost Ladder (Web `Unlimited` Mandatory Default):**
  1. **Priority 1 — Web `Unlimited` (`0 cr.`) via built-in `browser` subagent (DEFAULT):**
     On `ultra` and Unlimited-eligible plans, route active-rotation `R2`–`R5`
     image/video runs to `higgsfield.ai` via the built-in `browser` subagent
     without stopping to ask "CLI or Unlimited?". Verify the **Generate CTA
     button itself flips to `Unlimited` (`0 cr.`)** (not just a model badge,
     which may redirect to `/market` or Annual paywalls; excluded on MCP/CLI,
     Canvas, and Supercomputer), pause only for manual login/CAPTCHA, log via
     `hf_guard.py log-web`, and ingest via `hf_guard.py upload`.
  2. **Priority 2 — Economy `720p` / Latent CLI Drafts (FALLBACK ONLY):**
     Use paid CLI (`hf_guard.py run`) only for non-Unlimited tasks (audio/VO/SFX),
     models confirmed without a `0 cr.` CTA on `higgsfield.ai` (e.g. monthly
     `Ultra` video when 0 video models are in rotation), stalled web queues, or
     explicit Director requests for faster paid CLI batching.
  3. **Priority 3 — Native `1080p` CLI Finals (`R5`, FALLBACK ONLY):**
     Prefer Web `Unlimited` native `1080p` (`0 cr.`) whenever available; never
     pixel-upscale `480p` drafts into `1080p` masters. When using CLI for `R5`,
     graduate takes natively (`--bitrate_mode high` where supported—`0 cr.`
     surcharge) and reserve pixel upscalers strictly for clean `>= 720p` inputs
     (`<= 2×`) passing all 6 Upscale Gate rules + 1-shot `1:1` `--crops` pilot.

## Stage Endpoint Index

Use [`references/model-selection.md`](references/model-selection.md) for live
costs/benchmarks and [`references/live-workflows.md`](references/live-workflows.md)
for exact flags and CEL rules:

- **`R2`–`R3` Lookbooks, Asset Bibles & Stills:** `product-photoshoot`
  (`--model gpt_image_2`, modes: `product_shot`, `lifestyle_scene`,
  `closeup_product_with_person`, `hero_banner`, `ad_creative_pack` — issue
  separate `--count 1` calls per `--variant A|B|C` with distinct `--out` paths);
  `soul_location` / `soul_cast` (`0.12 cr.`) for fast exploration;
  `seedream_5_5`, `nano_banana_2_1`, `kling_image_4_0`, `gpt_image_2_6`,
  `seedream_v5_pro`, `flux_3_image` for `2k`–`8k` locks; brand/vector/type
  (`recraft_v4_1`, `ideogram_4_6`, `ideogram_vector`); spatial/cast utilities
  (`3d_jutsu_angles`, `nano_banana_2_shots`, `nano_banana_2_relight`,
  `nano_banana_2_skin_enhancer`, `nano_banana_2_ai_stylist`, `flux_kontext`,
  `outpaint`, `flux_2_pro_outpaint`, `image_background_remover`, wf
  `image_decompose`) and `higgsfield soul-id create` (`--soul-2` /
  `--soul-cinematic` → `text2image_soul_v2` / `soul_cinematic`).
- **`R4`–`R5` Motion, Camera, Acting, 3D & Rescue:** `seedance_2_5` (`omni_reference`,
  `--draft true` → `--draft_job_id`, `video_extension`, `6s` 2-shot pairs);
  `kling4_0` / `kling_4_0_flash` (`reference-to-video`, `video-edit`,
  `kling_element_ids`, `--dynamic_range hdr`); `kling_o3_image_reference` /
  `kling_o3_flf`; `wan3_0` / `wan3_0_prime` / `veo3_1` / `flux_3_video` /
  `minimax_h3` / `magi_2`; camera & promo workflows (`cinematic_studio_video_4_0`,
  `cinematic_studio_video_3_5`, `cinematic_studio_3_0`, `cinematic_studio_video_v2`,
  `draw_to_video`, `reframe`, `marketing_studio_video`, `marketing_studio_v2_video`);
  performance/dialogue (`kling3_0_motion_control`, `hf_mult_motion_control_flash`,
  `intone`); prop rescue (`hf_mult_replace_object_flash`, `flux_3_video_edit`);
  3D & compositing/finishing (`hunyuan3d_v3_1_text_to_3d`,
  `tripo_h3_1_multiview_to_3d`, `meshy_v7_image_to_3d`, `video_background_remover`,
  `depth_anything_video`, `topaz_hyperion_2_5`, `video_deflicker`).
- **`R3`–`R5` Audio & Advisory Analysis:** VO (`text2speech_v2` + `voices list`,
  `seed_audio`), multi-speaker (`elevenlabs_v4`), voice swap/dubbing
  (`voice_change`, `dubbing`), music (`elevenlabs_music_v2_5`, `sonilo_music`),
  SFX (`mirelo_text_to_audio`), optional advisory pacing read
  (`brain_activity --medias <id>`).

## Web UI vs. CLI Boundaries (Canonical)

- **Web-UI only studios & controls (`https://higgsfield.ai`, verified `2026-11-27`):**
  - **Active-rotation `Unlimited (0 cr.)` & CTA rule:** accessible **only** on
    standard `higgsfield.ai` surfaces—**never on MCP/CLI, Canvas, or
    Supercomputer**. Verify the **Generate CTA button itself flips to
    `Unlimited` (`0 cr.`)**; badges on gated models (`Nano Banana Pro`, `GPT
    Image 2`, `Seedance 2.5`, `Kling 3.0`) can redirect monthly `Ultra` users to
    `/market` or Annual upgrade paywalls.
  - **Web-only studios:** `Supercomputer / AI Motion Design` (formerly `Vibe
    Motion`, `/vibe-motion` → `/supercomputer`, plus `/ai-motion-designer` for
    AE + MCP; no `Unlimited`, no pre-gen alpha/ProRes toggle), `3D Jutsu`
    (desktop 3D set + QR smartphone camera tracking), `Popcorn`
    (`/storyboard-generator` Manual / Auto), `Canvas` (+ Figma plugin, no
    `Unlimited`), `Mr. Higgs / Assist`, and `Cinema Studio 4.0` (`/generate`:
    4 formats `Modern`/`DV Camcorder`/`8mm Film`/`35mm Film` + `Auto`, 5 lenses,
    3 apertures, 33 flat `#` camera presets; `Start/End Frame` only when
    switching to `Kling 3.0`; `Extend Video` on `/ai/video`; distinct from
    `Cinema Studio Image`/1.0–2.0 brand-camera racks).
  - **Web-only controls & unquotable CLI models:** `AI Cast`, `Face Swap`,
    `Lipsync Studio` (`Emotion Wheel` is not visible in CS 4.0), creating Cinema
    Studio Elements or `kling_element_ids`, interactive light placement, and
    quoting/running `topaz_video`, `topaz_image`, `sam_3_3d` (`alpha v2` CLI
    cost unsupported) or `sam_3_video` (CLI cost HTTP 500).
- **Opaque Cinema Studio preset UUIDs** (`camera_model_id`, `camera_lens_id`,
  `camera_aperture_id`, `light_id`, etc.) are absent from `preset list`: leave
  unset (`Auto`) and describe optics/light in prose, or configure once in Web
  and extract via `higgsfield generate get <id> --json` into
  [`cinema-presets.example.json`](../../../docs/cinema-presets.example.json) shape.

*Done when:* target models/workflows are verified against live schemas and
`generate cost`, `make campaign-check` passes CEL rules, and every paid call or
upload routes through `hf_guard.py` within approved caps.

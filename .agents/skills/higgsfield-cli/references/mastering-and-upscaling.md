# Video Mastering, Draft-to-Final Escalation & Upscaling Playbook

Executable decision spec for moving from `R4` motion drafts to broadcast-clean `R5` `1080p`/`4K` masters in Higgsfield without upscale halos, muddy faces, or cut-to-cut texture whiplash. Always confirm live pricing via `higgsfield generate cost` before quoting—credit snapshots below reflect the `ultra` plan (`2026-11`, 5s clips).

## 1. Hard Invariant: Zero `480p → 1080p` Pixel Upscaling

- **Never pixel-upscale `480p` drafts into `1080p` masters.** `854×480 → 1920×1080` is a **2.25× linear / 5.06× pixel-area** jump (>80% fabricated pixels) on `< 1 Mbps` compressed drafts, causing bright white edge halos, muddy/blotchy faces, `1.4×–2.0×` high-frequency crunch, and `1918×1080` rounding.
- **Worse economics than native `1080p`:** `480p` CS 4.0 (`15 cr.`) + `bytedance_video_upscale pro` (`10 cr.`) = **`25 cr./shot`** for haloed fake `1080p`, whereas **native `1080p`/`2K`** costs **`10 cr.`** (`2K` `minimax_h3`), **`12.5 cr.`** (`magi_2`), **`15 cr.`** (`wan3_0`), and **`18.75 cr.`** (`kling4_0 --duration 5`).
- **Never offer `480p → 1080p` pixel upscaling in `R4B` Dailies as a budget shortcut.** Quote native `1080p` paths below instead.

## 2. Deterministic Shot Routing Algorithm (`R1B` / `R4` → `R5`)

Evaluate each shot top-to-bottom and take the **first matching branch**:

1. **IF** the target engine has an active **`Unlimited` (`0 cr.`)** toggle on `higgsfield.ai` whose **Generate CTA flips to `Unlimited` (`0 cr.`)** (badges alone may redirect monthly plans to `/market` paywalls) and queue latency fits the round → **Path 1 (Web `Unlimited`)**: generate via the `browser` subagent (`0 cr.`), download, probe with `qa_media.py`, and ingest.
2. **ELSE IF** the shot requires **`> 10` reference images** OR **irreplaceable acting/mirror/VFX timing** that must transfer 1:1 from draft to final → **Path 2 (Latent Escalation)**:
   - `R4`: `seedance_2_5 --mode omni_reference --draft true` (`15 cr.`).
   - `R5`: `seedance_2_5 --mode omni_reference --draft_job_id <draft_job_id> --start_image <still_uuid> [--image_references ...] --resolution 1080p --bitrate_mode high` (`80 cr.`).
   - *Rule:* `--draft_job_id` accepts **only** a job UUID created by `seedance_2_5 --draft true` (expires ~7–14 days), and CLI CEL still requires `--start_image`/refs when `--mode omni_reference` is set. CLI `cinematic_studio_video_4_0` does **not** expose `--draft_job_id`.
3. **ELSE IF** the shot needs **multi-ref (`<= 10` images) or dynamic action/wardrobe choreography** at low `R5` cost → **Path 3A (Kling 4.0 Native `1080p`)**:
   - `R4`: `kling_4_0_flash --resolution 720p --duration 5` (`7.5 cr.`; no `end_image`) or `seedance_2_0_mini --resolution 720p` (`5 cr.`).
   - `R5`: `kling4_0 --mode reference-to-video --resolution 1080p --duration 5` (`18.75 cr.`; optional `--dynamic_range hdr` at `22.5 cr.`; default `duration` is `10`).
4. **ELSE IF** the shot is a **calm single-frame I2V or moody atmospheric beat** (`start_image` only, no multi-ref stack) → **Path 3B (Wan / Veo / MiniMax / Magi / FLUX Native `1080p`/`2K`)**:
   - `R4`: `wan3_0 --resolution 720p --duration 5` (`7.5 cr.`) or `seedance_2_0_mini --resolution 720p` (`5 cr.`).
   - `R5`: `minimax_h3 --duration 5` (`10 cr.`, native `2K`), `magi_2 --resolution 1080p --duration 5` (`12.5 cr.`, supports `seed`), `wan3_0 --resolution 1080p --duration 5` (`15 cr.`; verify FPS—may output `30fps`), `veo3_1 --variant veo-3-1-fast --quality high` (`16 cr.`, 4s), `wan3_0_prime --resolution 1080p --duration 5` (`27.5 cr.`), or `flux_3_video --resolution 1080p` (`40 cr.`).
5. **ELSE IF** an approved **golden `480p` take already exists without `--draft_job_id`** (e.g. legacy CS 4.0 CLI draft) and its exact choreography cannot be lost → **Path 4 (Motion-Locked Native `1080p` Rescue)**:
   - Run `kling4_0 --mode video-edit --resolution 1080p --duration 5` (`22.5 cr.`) passing `--video_references <draft_job_id>` + clean `R2`/`R3` `--image_references` so the model re-synthesizes fresh `1080p` skin, hair, and fabric over the locked motion.
   - Alternative: extract grayscale depth via `depth_anything_video --resolution 720p` (`7.57 cr.`) + clean refs into a native `1080p` generator.
6. **ELSE IF** the shot is **already clean native `>= 720p`** (`720p → 1080p` = `1.5×`, or `1080p → 2K/4K` ≤ `2.0×`) AND passes **every check in Section 4 (6-Rule Upscale Gate)** → **Path 5 (Selective Pixel Upscaling)**:
   - Prove on **1 high-risk shot first** (face + high-contrast edge) and verify `1:1` `--crops` before batching remaining shots.

### Keyframe & Bitrate Invariants (Apply Across All Paths)

- **Always set `--bitrate_mode high` on `1080p`/`4k` `seedance_2_5` and `cinematic_studio_video_4_0` finals:** Live CLI cost is identical to `standard` (`80 cr.`), preventing `1.1–3.0 Mbps` standard-bitrate compression softness.
- **Fix keyframe quality in `R3`, never with a video upscaler in `R5`:** Lock sharp `R3` stills (`seedream_5_5`, `flux_3_image`, `nano_banana_2_1`, `gpt_image_2_6`). If an `R3` still needs cleaner skin or higher resolution before animating, enhance the **still** once (`bytedance_image_upscale` `2k`/`4k`, `topaz_image`, or `nano_banana_2_skin_enhancer`) before `R4`. Never anchor a hero shot to a compressed `480p` video screenshot.

## 3. Step-by-Step `R5` Mastering & Verification Runbook

Execute these 5 steps in strict order during `R5`:

1. **Route & verify inputs (`0 cr.`):** Check each unlocked shot's draft `qa_media.py` JSON (`width`, `height`, `fps`, `video_bitrate_kbps`) and assign its Path (`1`–`5`) from Section 2. Confirm `make campaign-check` shows zero `bitrate_mode` or `480p`-upscale warnings.
2. **Pilot before batching (when changing engine or using Path 5):** If switching to a new `R5` engine or running any pixel upscaler, run **1 high-risk shot first** (human face + dark-on-light contrast edge) via `hf_guard.py run --round R5 ...`. Only launch parallel workers for the remaining unlocked shots after Step 4 passes on the pilot.
3. **Generate `3x2` sheet + `1:1` native crops per `R5` clip (`0 cr.`):**
   ```bash
   python3 scripts/qa_media.py clip <mp4> \
     --sheet campaigns/<slug>/qc/<id>_r5_sheet.png \
     --crops campaigns/<slug>/qc/<id>_r5_crops.png --json
   ```
   *(Default `--crop-focus thirds` sweeps left-center, center, and right-center across `20%`/`50%`/`80%` at unscaled `1:1` pixels; pass `--crop-focus left|center|right` if a face sits outside the sweep.)*
4. **Run cross-shot batch consistency audit + Visual Critic (`0 cr.`):**
   ```bash
   python3 scripts/qa_media.py batch campaigns/<slug>/media/shots/<r5_clips...> --strict --json
   ```
   Verify `ok == true` (zero `non_standard_dimensions` like `1918×1080` or `1278×720`, zero `resolution_mismatch` / `fps_mismatch`), inspect any `hf_sharpness_outlier` (`> 1.5×` clean median) or `low_video_bitrate` (`< 1800 kbps`) warnings, and spawn a fresh `reviewer-agent` (`fork_turns: "none"`) with **both** `_r5_sheet.png`, `_r5_crops.png`, and the `batch` JSON via `view_image`.
5. **Deterministic failure recovery (do not guess):**
   - **Halos, ringing, muddy/plastic face, color blotches, or `hf_sharpness_outlier` on an upscaled clip:** **Abort upscaling immediately**—never retry the same upscaler with another preset. Re-route the shot to Path 2 (`seedance_2_5 --draft_job_id`), Path 3 (native `1080p` `kling4_0`/`wan3_0`), or Path 4 (`kling4_0 --mode video-edit`).
   - **`non_standard_dimensions` (`1918×1080`) or `fps_mismatch` (`30fps` in `24fps` cut):** Regenerate natively at `1920×1080` matching `fps_target` instead of letting `assemble.sh` pad or drop frames.
   - **`low_video_bitrate` (`< 1800 kbps` at `1080p`) with visible compression softness:** Confirm `--bitrate_mode high` on `seedance_2_5` / `cinematic_studio_video_4_0` or switch to `kling4_0` / `wan3_0_prime`.

## 4. The 6-Rule Upscale Gate (All 6 Must Pass for Path 5)

If **any single row** hits Red Light, skip Path 5 and use Paths 1–4:

| # | Check | Green Light (May Run 1-Shot Pilot) | Red Light (Abort—Use Native `1080p`) |
| :--- | :--- | :--- | :--- |
| **1** | **Resolution & scale** | Native `>= 720p` AND single-pass scale `<= 2.0×` linear (`720p→1080p` = `1.5×`, `1080p→4K` = `2.0×`) | Any `480p` clip (`2.25×` / `5.06×` area) or `> 2×` single-pass jump |
| **2** | **Raw bitrate & cleanliness** | Raw generator export (never NLE re-encoded), `>= 1500 kbps` (`720p`) / `>= 3000 kbps` (`1080p`), zero macroblocking/flicker | `< 1000 kbps` compressed drafts, blocky walls/skin, or unstable shimmer |
| **3** | **Content risk** | Medium/close faces already crisp in source, products, interiors, calm motion | Wide-shot faces (`< 90px` tall), sequins/glitter/fine weave, tiny text/UI, or warped hands/anatomy |
| **4** | **FPS parity** | Upscaler output FPS equals source FPS (`24→24` or `30→30`) | Forcing `30→24fps` drops or `24→60fps` interpolation inside upscaling |
| **5** | **Cross-shot optical match** | `qa_media.py batch --strict` passes (`ok == true`, uniform resolution & FPS) and `--crops` shows matching texture (`hf_ratio <= 1.5×`) | Splicing soft native `1080p` (`hf ~ 1.2`) next to crunchy upscaled takes (`hf ~ 1.6–2.4`) |
| **6** | **1-shot `1:1` crop proof** | Single hardest face/contrast shot passes `reviewer-agent` on `--crops` (`1:1` pixels) | Batch-upscaling before piloting or judging solely from `480px` `3x2` sheets |

## 5. Tool-by-Tool Execution Spec (Upscalers, Still Enhancers & Finishing)

| Tool (`job_type` / external) | Role & Live Cost | When to Use | Required Flags, Settings & Live Traps |
| :--- | :--- | :--- | :--- |
| **`topaz_video`** *(Starlight Precise / Proteus)* | Video upscaler (Web UI / Desktop / API) | **Default choice for Path 5 on faces, skin pores, hair, and organic cinema texture** (`720p→1080p`, `1080p→4K`) | **CLI trap:** `higgsfield generate cost topaz_video` is unsupported (`alpha v2 cost estimation`); quote & run in Higgsfield Web UI or externally. Keep `Sharpen` low (`0–20`); never stack two upscale passes. |
| **SeedVR2 7B** *(external ComfyUI / API)* | Open-weight temporal diffusion SR (`0 cr.` local, 16GB+ VRAM) | Clean temporal restoration of native `720p`/`1080p` without hard edge halos | Prefer **7B** FP16/FP8 weights over 3B or heavy INT8 on faces; requires clean `>= 720p` source. |
| **`bytedance_video_upscale`** | Cloud video upscaler: `standard` `1 cr.`, `pro` `10 cr.` (`1080p`) / `37.5 cr.` (`4K`) | Fast bump ONLY on **already-clean `720p`/`1080p`** products/graphics | Pass a **video job UUID** (never a raw URL) to `--video_references`, match `--fps` to source, and test `standard` (`1 cr.`) first. **Trap:** `pro` on compressed `480p` causes white halos, face blotches, `1.4×–2.0×` HF crunch, and `1918×1080` rounding. |
| **`topaz_hyperion_2_5`** | **NOT a resolution upscaler**—Inverse Tone Mapping (`prores` / `exr` / `h265`) | Expanding clean native `1080p`/`4K` 8-bit SDR clips to **10-bit ProRes / 16-bit EXR** for DaVinci Resolve grading | **Schema trap:** rejects dimensions not divisible by 4 (accepts `1920×1080`; fails on `854×480` and `1918×1080`). |
| **`depth_anything_video`** | Grayscale depth extractor (`7.57 cr.` at `720p`) | Path 4 motion/depth guide extraction from an approved draft | `--colormap grayscale --variant VDA-Large --resolution 720p --video_references <job_uuid>`. |
| **`bytedance_image_upscale` / `topaz_image` / `nano_banana_2_skin_enhancer`** | `R3` still enhancers (before video) | Upgrading a locked `R3` keyframe still to crisp `2k`/`4k` or natural skin before `R4` animation | `bytedance_image_upscale` requires exactly 1 `--image_references` (`--resolution 2k|4k`); `topaz_image` requires `--output_width` + `--output_height`; `nano_banana_2_skin_enhancer` requires `--preset_id`. |
| **`video_deflicker` / `fps_boost`** | Utility cleanup / frame interpolation | Mild lighting flicker on clean native renders (`video_deflicker`) | Avoid `fps_boost` on fast hands, hair, or cloth snaps—optical flow creates morphing ghosts and doubles cost. |

## 6. Post-Production Texture Unification

- **Never stack AI upscalers:** two sequential enhancement passes compound halos and plastic skin.
- **Unify mixed native engines in finishing:** when a cut blends two native engines (e.g. `cinematic_studio_video_4_0` + `kling4_0` or `wan3_0`), either apply a shared 3D LUT and subtle temporal 35mm film grain directly at `0 cr.` via `make assemble CAMPAIGN=<slug> LUT=<grade.cube> GRAIN=4` (`scripts/assemble.sh --lut <file.cube> --grain <1..20>`), or grade the exported unbaked `media/exports/stems/` in DaVinci Resolve (optionally expanding `1920×1080` clips via `topaz_hyperion_2_5` first) so every cut reads as one camera.
- **Keep scaling lossless-intent:** `assemble.sh` applies `flags=lanczos` and warns on resolution/FPS mismatches; fix mismatches at the clip source before final delivery.

*Done when:* every `R5` clip followed Paths 1–4 (or passed all 6 Upscale Gate checks + 1-shot pilot), `qa_media.py clip --crops` and `qa_media.py batch --strict` pass with zero errors, and fresh `reviewer-agent` passes both `3x2` sheets and `1:1` native crops via `view_image`.

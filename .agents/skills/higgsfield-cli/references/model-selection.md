# Model Selection, Benchmarks & Web Unlimited-First Routing

Benchmark-grounded routing for choosing **free Web Unlimited (`0 cr.`)**,
**economy CLI drafts**, or **flagship CLI finals** across `R2`–`R5`. Always
confirm live CLI pricing via `higgsfield generate cost` before quoting—credit
snapshots below reflect the `ultra` plan verified on live `higgsfield 1.2.3` as
of `2026-11-27` and may drift.

## Generation Priority Ladder

Web `Unlimited` (`0 cr.`) is the **mandatory default** for active-rotation image
and video rounds on Unlimited-eligible subscriptions—never quote CLI credits as
the default price for models confirmed `0 cr.` in the live Web UI.
**Rotation, scope & CTA trap (host-verified `2026-11-27`):** Official fine print
states *"Unlimited models and Free Generations on plans are accessible only via
higgsfield.ai and are not accessible on MCP/CLI, Canvas or Supercomputer."*
Always verify the **Generate CTA button itself flips to `Unlimited` (`0 cr.`)**,
not just a model-card badge/switch: on monthly `Ultra`, models such as
`Nano Banana Pro`, `GPT Image 2`, `Seedance 2.5`, and `Kling 3.0` display
`Unlimited` badges/switches that redirect to `/market#image-unlimited`,
`/market#video-unlimited`, or Annual upgrade paywalls.

- **Verified monthly `Ultra` active `Unlimited (0 cr.)` snapshot (`2026-11-27`):**
  - `/ai/image`: `Seedream 5.0 lite` (`2K/3K/4K`), `Seedream 4.5` (`2K/4K`),
    `Nano Banana`, `FLUX.2 Pro` (`1K/2K`), `Kling O1` (`1K/2K`), plus `Soul
    Cinema` (plan Free Generations pool).
  - Video on monthly `Ultra`: **`0` active Unlimited video models** (annual or
    `/market#video-unlimited` add-on gated; re-verify CTA button each session).

1. **Web UI `Unlimited` (`0 cr.`) via built-in browser agent (Priority 1 — DEFAULT):**
   On `ultra` and eligible plans, route active-rotation image/video runs to the
   built-in `browser` subagent on `higgsfield.ai` first (never Canvas or
   Supercomputer, which are excluded from Unlimited), verify the **Generate CTA
   button itself reads `Unlimited` (`0 cr.`)** before triggering (fail closed:
   never click a paid web button or paywall redirect without Director approval),
   and download outputs straight into `campaigns/<slug>/media/`.
2. **Economy CLI drafts (Priority 2 — FALLBACK ONLY):** Use paid CLI via
   `hf_guard.py run` only when the target model has no `0 cr.` CTA button on
   `higgsfield.ai` (e.g., audio/TTS/SFX, 3D, compositing utilities, monthly
   `Ultra` video when 0 video models are in rotation, or paywall-gated image
   models), the web queue stalls critically, or the Director explicitly asks to
   spend CLI credits for parallel speed (`0.12–0.75 cr.` stills; `5–7.5 cr.`
   `720p` video or `15 cr.` `seedance_2_5 --draft true`).
3. **Flagship CLI finals (Priority 3 — FALLBACK ONLY):** Check Web `Unlimited`
   CTA first; reserve paid flagship CLI `1080p` renders (`15–80 cr.`) strictly
   for Director-approved `R5` upgrades or high-risk multi-reference `R4A` pilots
   where `Unlimited` is unavailable.

## Built-In Browser Agent Protocol (`higgsfield.ai` Unlimited, `0 cr.`)

Use this mandatory default workflow to capture `0 cr.` Unlimited image or video
generations without violating anti-bot boundaries:

1. **Launch in the user's logged-in browser pane:** delegate to the `browser`
   subagent (`Model: "flash"`) to open `https://higgsfield.ai`, select the
   target model, and verify **four mandatory pre-click checks**:
   - **`Unlimited` toggle is ON** AND the **Generate CTA button itself flips to
     `Unlimited` (`0 cr.`)** (do NOT trust a model-card badge alone—if toggling
     redirects to `/market` or an Annual paywall, or the CTA shows `> 0`, STOP
     without clicking and report which models actually flip the CTA to
     `Unlimited`).
   - **Duration dropdown matches the prompt:** Higgsfield Web UI silently
     retains the previous run's duration even when the prompt states another
     length — explicitly verify and set `duration` before every click.
   - **Genjutsu mode selector (`hf-mult-motion-control`):** Recreate/default
     links open `Motion transfer`; manually switch to **`Objects swap`** before
     clicking Generate for outfit or prop replacements.
   - **`@Element` name parity:** keep identical `@char_*`, `@loc_*`, `@prop_*`
     handles across `shotlist.json` (`element_handle`) and Cinema Studio folders
     (`CHAR / PROPS / LOCATION / SCENES`) so pasted prompts auto-attach assets.
2. **CAPTCHA / Login handoff (hard rule):** Never attempt to solve, click
   through, or bypass a CAPTCHA, Cloudflare Turnstile, or login wall. Pause
   immediately, notify the Director to complete login or solve the CAPTCHA
   directly in the visible browser pane, and wait for confirmation.
3. **Resume the same browser session:** Once the Director confirms the CAPTCHA
   or login is cleared, call `send_message` on the **existing** browser
   subagent conversation ID (do not spawn a fresh tab/agent) so it continues in
   the cleared session to trigger the Unlimited generation(s) and download the
   outputs.
4. **Ingest & log into campaign truth:** Move/copy downloaded assets into the
   expected `campaigns/<slug>/media/{lookbook,stills,shots}/` path, record every
   `0 cr.` Web Unlimited generation trace via `hf_guard.py log-web`, run
   `scripts/qa_media.py` and fresh `reviewer-agent` QC (logging verdicts via
   `qa_media.py log-review`), record the selected file in `shotlist.json`, and
   upload approved stills/lookbook winners via `hf_guard.py upload --round <R>`
   (`0 cr.`) so downstream shots stay UUID-locked.
5. **Fallback trigger & image-only Unlimited caching:** Some `Ultra`
   subscriptions include **`Unlimited (0 cr.)` for images only** (toggling
   video `Unlimited` redirects to `/market#image-unlimited`). Verify video
   `Unlimited` availability **once per campaign session**; if video Unlimited
   redirects or is unavailable for the needed model, cache that truth for the
   session (stop re-probing video Unlimited), quote live CLI costs, and fall
   back cleanly to Priority 2/3 via `hf_guard.py run`. Also fall back if queue
   wait stalls the round or the Director explicitly asks to spend CLI credits
   for speed.

*Done when:* asset is saved under `campaigns/<slug>/media/`, passes internal
QC, and (if used as a downstream reference) is uploaded via `hf_guard.py upload`.

## Photorealistic, Brand & Vector Image Models — Benchmarks & Case Routing

Based on Artificial Analysis Image Arena (blind human preference Elo) and live
`higgsfield 1.2.3` CLI quotes (`ultra` plan, verified `2026-11-27`):

| Model (`job_type`) | CLI Cost (verified) | Benchmark Strength & Schema Notes | Best Use Case |
| :--- | ---: | :--- | :--- |
| `soul_cinematic` / `text2image_soul_v2` / `soul_location` / `soul_cast` | `0.12 cr.` | Specialized cinematic, location & casting stills | Ultra-cheap `R2`–`R3` lookbook, architectural, casting & lighting exploration (or trained `Soul ID` stills) |
| `seedream_5_0_flash` | `0.50 cr.` | Fast clean realism | **Fast `R2`–`R3` photorealistic draft** |
| `gpt_image_2_6` (`low` 1k / `svg` / `gif` / `high` 2k) | `0.75 cr.` / **`2.00 cr.`** | Prompt adherence, geometry, mirrors, native **`svg`** (`0.75 cr.`, no refs) & **`gif`** (`0.75 cr.`); `medium` 1k `1.00 cr.`, `high` 1k `1.25 cr.` | Complex spatial/mirror staging, native vector `svg` icons/logos, or exact multi-element edits *(avoid for live-action skin—tends painterly)* |
| `seedream_v5_lite` / `nano_banana_2_lite` / `flux_2` | `1.00 cr.` | Solid mid-budget realism | Low-cost Lookbook `A / B / C` exploration |
| `recraft_v4_1` (`1k` std / `2k` vector) | `1.25 cr.` / **`10.00 cr.`** | Brand-locked graphics & clean vector (`1k` vector `2.50 cr.`, `2k` std `8.00 cr.`); strict **`#RRGGBB`** hex `colors`/`background_color` (no alpha) | Brand illustrations, icon sets, and strict HEX palette vector assets |
| `seedream_5_5` (`2k` / `4k`) | **`1.50 cr.`** / **`2.50 cr.`** | Top unretouched 35mm skin, fabric & architectural stone fidelity (`<= 10` refs, up to `4k`) — **cheaper than `seedream_v5_pro` (`2.50 cr.` 2k)!** | **Primary `R2B` Asset Bibles, `R3` hero keyframes & macro/fashion close-ups** |
| `nano_banana_2_1` (`1k` / `2k` / `4k`) | `1.50` / **`2.00`** / `3.00 cr.` | Top physical plausibility & multi-ref blending; supports **`video_references`**, **`thinking_level`** (`minimal\|medium\|high`), **`8:1`/`1:8`** ultra-wide & `seed` | **Hero `R3` stills** blending cast + location + wardrobe (or extracting stills from video refs) |
| `kling_image_4_0` (`2k` / `4k` / `8k`) | `2.00` / `3.00` / **`5.00 cr.`** | Ultra-high-resolution stills (**up to `8k`**); `image_references + kling_element_ids <= 10` | Ultra-crisp `4k`–`8k` hero plates and Kling-element-matched keyframes |
| `ideogram_4_6` / `ideogram_vector` | `2.00 cr.` (2k med) / `5.00` (`gen`) · `3.00` (`vec`) | Typography, posters & masked inpaint (`ideogram_4_6` `high` 4k `6.25 cr.`); vector generation & raster-to-SVG (`ideogram_vector`) | In-world typography plates, signage, and clean SVG vectorization |
| `seedream_v5_pro` (`2k`, max `2k`) | `2.50 cr.` | Structured prompt & orthographic sheet lock (`<= 10` refs) + `remove_bg`/`is_inpaint` | Use only when `remove_bg`/`is_inpaint` or explicit `width`/`height` is needed—otherwise prefer **`seedream_5_5`** (`1.50 cr.` 2k / `2.50 cr.` 4k) |
| `flux_3_image` (`1k` / `2k` / `4k`) | `2.00` / **`3.00`** / `19.00 cr.` | Benchmark leader for raw 35mm photographic skin, grain & non-plastic texture | **Hero editorial/35mm portraits & interiors** without heavy multi-ref edits |

## Video Models — Benchmarks & Case Routing

**Resolution, latent drafting & escalation truth (pixel upscaling vs. latent `Seedance 2.5` drafting):**
- **NEVER pixel-upscale `480p` drafts (`< 1 Mbps`) into `1080p`:** external/pixel upscalers (`bytedance_video_upscale`) on `480p` create halos, muddy faces, and shimmer. `cinematic_studio_video_4_0` caps at `1080p` (no `4k`) and does **not** expose `--draft` / `--draft_job_id` in CLI, so use `720p` drafts for non-latent engines.
- **DO use `seedance_2_5 --draft true` (`480p` latent draft at `~3 cr./s`) -> native `1080p` or `4K` finalize (`--draft_job_id`):** unlike pixel upscaling, `--draft_job_id` re-renders the exact locked camera, timing, and acting natively in `1080p` or `4K` (saving ~64% across 3–4 draft tries vs. straight `4K`).
- **Native `4K` 2× punch-in framing:** generating a flagship `Seedance 2.5` hero shot in native `4K` lets `assemble.sh` (`shots[].edit.crop_4k_punchin`) harvest both a wide and a crisp native `1080p` close-up from one take at `0 cr.`
- **Anti-Engine-Zoo & A-Roll First:** keep one primary video engine across a live-action block (avoid mixing 3–4 engines with 4×–20× bitrate disparity, and avoid economy `mini`/`flash` engines on flagship live-action photorealism). Lock talking-head **A-Roll first** before B-Roll, and audition vocal tone cheaply via `voice_change` post-generation instead of re-rolling video. Follow [Mastering & Upscaling](mastering-and-upscaling.md) for every `R4 → R5` upgrade decision.

Based on Artificial Analysis Video Arena (I2V/T2V Elo) and live `higgsfield 1.2.3`
CLI pricing (`ultra` plan, verified `2026-11-27`, 5s clips unless noted):

| Model / Workflow (`job_type`) | CLI Cost (5s) | Refs & Controls | Benchmark Strength | Best Use Case |
| :--- | ---: | :--- | :--- | :--- |
| `seedance_2_0_mini` (`480p` / `720p`) | `2.5 cr.` / **`5 cr.`** | `start_image`, `end_image`, `image_references` (`<= 9` images) | Fast lightweight Seedance motion | **Default `R4` economy `720p` draft** to prove rhythm, camera move & edit cut |
| `veo3_1_lite` / `veo3_1` (`fast high` 4s) | `6 cr.` / **`16 cr.`** (4s) | `start_image` / T2V (`duration` `4\|6\|8`, default `8`) | **Benchmark leader for atmospheric light, DOF & cinema audio** | Moody single-subject atmospheric native `1080p` shots without heavy wardrobe ref stacks |
| `kling_4_0_flash` (`720p` only) | **`7.5 cr.`** *(10s def = `15 cr.`)* | Up to 10 images + `video_references` (no `end_image`; pass `--duration 5`) | Fast multi-ref Kling 4.0 choreography | **Default `R4` `720p` draft** before native `1080p` `kling4_0` mastering |
| `kling3_0` (`--mode pro --sound off`, `1080p`) | **`8.75 cr.`** (`1.75 cr./s`, keep `<= 6s`) | `start_image` + opt. `end_image` | Crisp native `1080p` stylized motion at ultra-low cost | **Short (`3–6s`) silent-character / action / reaction / off-screen VO shots** for stylized 2D/3D/animal worlds *(direct natural closed-mouth expressions when silent under off-screen VO; for visible on-camera speaking faces where lip-sync matters, prefer `intone` / Lipsync Studio / native-speech models, and avoid `> 8s` single shots)* |
| `wan3_0` (`480p` / `720p` / `1080p`) | `3.75` / **`7.5`** / **`15 cr.`** | `start_image`+`end_image` OR ref media (mutually exclusive) | **Top Elo leader (~1175)**: natural fabric/light physics & subject stability | **Best value `720p` draft & cheapest native `1080p` master** for calm I2V takes *(verify FPS—may output `30fps`)* |
| `cinematic_studio_video_v2` (`--workflow`, `std` / `pro`) | `7.5 cr.` / **`10 cr.`** | Pro Kling + **`multi_shots`** + `multi_prompt` + **`speedramp`** + **`kling_element_ids`** | Affordable multi-shot & speedramp workflow | **Best budget Kling multi-shot / speedramp / element-locked clip** (CLI alternative since `kling4_0` lacks `multi_shots`) |
| `minimax_h3` vs `minimax_h3_max` | **`10 cr.`** (`2K`) / `12.5 cr.` (`768p`) | `start_image`+`end_image` OR ref media (mutually exclusive) | **Top-5 Elo (~1161)**: strong character likeness retention | **Always prefer `minimax_h3` (`10 cr.` native `2K`)** over `minimax_h3_max` (`12.5 cr.` capped at `768p`) for calm portraits |
| `magi_2` (`1080p` only) | **`12.5 cr.`** | `start_image`+`end_image` OR ref media + **`seed`** | Native `1080p` with deterministic **`seed`** control | Reproducible native `1080p` A/B prompt iterations at economy cost |
| `kling4_0` (`720p` / `1080p` SDR / `1080p` HDR / `4k`) | `12.5` / **`18.75`** / **`22.5`** / `45 cr.` *(def 10s = `37.5 cr.`!)* | Up to 10 images + `video_references` + `--dynamic_range hdr` (`video-edit` `22.5 cr.`; **NO `multi_shots` in CLI**) | Top motion stability, facial consistency, multi-ref control & native stereo | **Default value native `1080p` `R5` master** & motion-locked `video-edit` rescue — **always pass `--duration 5`** |
| `wan3_0_prime` (`720p` / `1080p`) | `13.75 cr.` / **`27.5 cr.`** | `start_image`+`end_image` OR ref media | Elevated fine skin/fabric micro-detail over `wan3_0` | Premium native `1080p` character portraits and tactile single-subject hero takes |
| `flux_3_video` (`720p` / `1080p`) | `30 cr.` / **`40 cr.`** | Up to 10 images OR `video_references` (mutually exclusive; `2k`/`4k` supported) | Editorial FLUX 3 color science and crisp single-frame look | Stylized fashion/editorial hero shots prioritizing color grade over long choreography |
| `seedance_2_5` (`--draft true` → `1080p` / `4k`) | `15 cr.` → **`80 cr.`** (`6s`: `18→96 cr.`; `4k`: `140 cr.`) | Up to 30 images / 50 refs (`omni_reference`) + `--draft_job_id` + free `--bitrate_mode high` | **Top-5 Elo (~1160)**: multi-shot narrative, exact draft-to-final latent lock & VFX | **Gold standard `R4 → R5` CLI path** when exact acting/timing must transfer 1:1 into native `1080p` (`--bitrate_mode high`); pair adjacent cuts as `6s` 2-shots (`48 cr./cut`) |
| `cinematic_studio_video_4_0` (`--workflow`, `480p`/`720p`/`1080p`) | `15` / `35` / **`80 cr.`** | Up to 30 images / 50 refs (`omni_reference`) + free `--bitrate_mode high` *(no `4k`, no CLI `--draft_job_id`)* | Best multi-reference continuity + native diegetic foley + Web Cinema Studio presets | Direct native `1080p` (`--bitrate_mode high`) hero shots or Web Cinema Studio upgrades—avoid `480p` CLI drafts if you need 1:1 `R5` escalation |

## Acting, Rescue, 3D, Motion-Graphics & Compositing Tools

Live `higgsfield 1.2.3` CLI quotes (`ultra` plan, verified `2026-11-27`, 5s clip basis unless noted):

| Category | Model / Workflow (`job_type`) | CLI Cost (verified) | Live Notes & Routing |
| :--- | :--- | ---: | :--- |
| **Motion Control (Genjutsu)** | `hf_mult_motion_control_flash` vs `hf_mult_motion_control` | **`10 cr.`** (`1080p` only) vs `100 cr.` (`1080p`) / `35 cr.` (`720p`) | **10× cheaper `_flash` Lite (`1080p` only)** — always pilot `_flash` first (`>= 1` image + exact `1` video ref); or `kling3_0_motion_control` (`--workflow`, `10 cr.` std / `15 cr.` pro, no `--prompt`) |
| **Prop / Object Swap (Genjutsu)** | `hf_mult_replace_object_flash` vs `hf_mult_replace_object` | **`12 cr.`** (`1080p` only) vs `120 cr.` (`1080p`) | **10× cheaper `_flash` Lite (`1080p` only)** — surgical object swap on locked clips (`>= 1` image + exact `1` video ref) |
| **Audio-Driven Lip-Sync** | `intone` | **`~18 cr./s`** (`1080p`, e.g. `128–272 cr.` for `7–14s`; `~8.5 cr./s` `720p`) | Keep CLI dialogue lines short (**`3–6s`**) or check Web `Unlimited` first |
| **Motion / SaaS Promo** | `marketing_studio_v2_video` (`--workflow`) | **`31.1 cr.`** (`saas_motion`, flat **`720p == 1080p`**) | **Always pick `1080p`** on `saas_motion` (same price as `720p`); 10 `--type` modes incl. `2d_motion`, `hypermotion`, `mixed_media`, `saas_motion`, `app_video` (see [Live Workflows](live-workflows.md)) |
| **Web Code-to-Video Studio** | `Supercomputer / AI Motion Design` *(Web-only, `/vibe-motion` → `/supercomputer`)* | Web credits *(excluded from `Unlimited`)* | `Motion Design` / `Editorial Motion Graphics`, `Brandkit`, `Higgsfield explainer` presets & `Agent mode` (plus `/ai-motion-designer` for AE + MCP); up to `4K` export, **no `Unlimited` toggle and no pre-gen ProRes/WebM/alpha/60fps toggle** |
| **3D Asset Generation** | `hunyuan3d_v3_1_text_to_3d` / `tripo_h3_1_multiview_to_3d` / `meshy_v7_image_to_3d` | **`7 cr.`** (`std`) · **`16 cr.`** (`pro`+PBR) / **`9 cr.`** / **`38 cr.`** | `hunyuan3d` `enable_pbr=true` requires `mode=pro` (`std` caps prompt `<= 200` chars); `tripo` multi-view `image_references`; `meshy` adds optional rigging/animation |
| **Matting & Depth** | `video_background_remover` / `depth_anything_video` | **`1 cr.`** / **`7.57 cr.`** (`720p`) | Alpha/matting cutout (`1 cr.`) and grayscale Z-depth pass (`7.57 cr.`) for weaving typography/graphics behind or in front of 3D motion |
| **HDR / 10-bit Finishing** | `topaz_hyperion_2_5` | **`13–16 cr.`** (`13 cr.` 24fps / **`16 cr.`** 30fps `1080p`) | SDR → 10-bit `prores` / `exr` / `h265` inverse tone mapping; **dims must be divisible by 4** (rejects `854×480` & `1918×1080`) |

## Audio & Advisory Models (`R3`–`R5`)

| Category | Model / Workflow (`job_type`) | Notes & Live Routing |
| :--- | :--- | :--- |
| **Voiceover (VO)** | `text2speech_v2` (`--variant elevenlabs\|seed_speech\|...`), `seed_audio` | Pair with `higgsfield voices list` (`--voice_id`, `--voice_type preset\|element`); check timing via `make qa-voice` |
| **Multi-Speaker Dialogue** | `elevenlabs_v4` (`--dialogue`) | Multi-voice scenes; lock voice WAVs in `R3` before `intone` lip-sync |
| **Voice Swap / Dubbing** | `voice_change` (`1 cr.`), `dubbing` (`15 cr.`) *(workflows, 5s)* | Re-voice or dub locked clips via `--workflow` (`--duration` is cost-only; `hf_guard.py` strips it on exec) |
| **Music Score** | `sonilo_music` (economy), `elevenlabs_music_v2_5` (flagship) | Generate uncut beat-locked score separately; keep video clips diegetic-only |
| **Foley / SFX** | `mirelo_text_to_audio` | Clean standalone diegetic sound layers |
| **Advisory Pacing Read** | `brain_activity` (`--medias <id>`) | Optional post-cut pacing/virality read (text output; run only when approved) |

## Quick Round-by-Round Defaults & Stack Presets

- **`R2` Lookbook & `R3` Draft Stills:** Web `Unlimited` (`0 cr.`, verify active
  rotation) first → else CLI `soul_location` / `soul_cast` / `text2image_soul_v2`
  (`0.12 cr.`), `seedream_5_0_flash` (`0.50 cr.`), or `gpt_image_2_6` (`0.75 cr.`
  `low` 1k / native `svg`).
- **`R2B` Asset Bibles & `R3` Locked Hero Stills:** Web `Unlimited` (`0 cr.`)
  if in rotation → else **`seedream_5_5` (`1.50 cr.` 2k / `2.50 cr.` 4k)** as the
  default photorealistic workhorse (cheaper than `seedream_v5_pro` `2.50 cr.`),
  `nano_banana_2_1` (`2.00 cr.` 2k, multi-ref / `video_references`),
  `kling_image_4_0` (`2.00 cr.` 2k / `5.00 cr.` 8k), `flux_3_image` (`3.00 cr.`
  2k), or `recraft_v4_1` / `ideogram_4_6` for strict HEX vectors & signage.
- **`R4A` / `R4B` Motion Drafts:** Web `Unlimited` (`0 cr.`) first → else CLI
  `seedance_2_0_mini` (`720p`, `5 cr.`) / `kling_4_0_flash` (`720p`, `7.5 cr.`,
  pass `--duration 5`) / `wan3_0` (`720p`, `7.5 cr.`) for clean legible drafts;
  use **`seedance_2_5 --draft true` (`15 cr.` 5s / `18 cr.` 6s 2-shot)** whenever
  an `R4A`/`R4B` take needs guaranteed 1:1 latent escalation to native `1080p`
  via `--draft_job_id`.
- **`R5` Final Master (`1080p`):** Follow the deterministic 5-path algorithm and
  6-rule Upscale Gate in [Mastering & Upscaling](mastering-and-upscaling.md)
  (Web `Unlimited` → `seedance_2_5 --draft_job_id --bitrate_mode high` → value
  native `1080p` `wan3_0` `15 cr.` / `magi_2` `12.5 cr.` / `minimax_h3` `10 cr.`
  `2K` / `kling4_0` `18.75 cr.` `--duration 5` / `veo3_1` / `wan3_0_prime`
  `27.5 cr.` → motion-locked `kling4_0 --mode video-edit` → direct
  `cinematic_studio_video_4_0`; never pixel-upscale `480p` drafts).

### Two Proven 30s Production Stack Presets (Native `1080p`)

1. **Commercial Hybrid (~`220–360 cr.`):** `soul_location`/`soul_cast` (`0.12 cr.`)
   world scout → `seedream_5_5` (`1.50 cr.` 2k / `2.50 cr.` 4k) for `R2B`/`R3` →
   `wan3_0` (`15 cr.`), `magi_2` (`12.5 cr.`), or `kling4_0 --duration 5`
   (`18.75 cr.`) native `1080p` on clean single-beat shots + `seedance_2_5`
   (`15→80 cr.`, or `18→96 cr.` `6s` 2-shot) strictly on `2–3` hero acting or
   complex-continuity beats.
2. **Cinema / Flagship Narrative (~`620–960 cr.`):** `soul_location`/`text2image_soul_v2`
   (`0.12 cr.`) → orthographic `#808080` prop/cast/location bibles + `2k`/`4k`
   keyframes on `seedream_5_5` (`1.50–2.50 cr.`) → `seedance_2_5` (`--draft true`
   → `--draft_job_id --resolution 1080p --bitrate_mode high`) in paired `6s`
   2-shot blocks (`3s + HARD CUT + 3s` = `48 cr./cut`), finished with unified
   post color grade and dedicated foley/sound mix.

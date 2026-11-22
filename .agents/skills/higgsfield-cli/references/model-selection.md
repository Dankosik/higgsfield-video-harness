# Model Selection, Benchmarks & Web Unlimited-First Routing

Benchmark-grounded routing for choosing **free Web Unlimited (`0 cr.`)**,
**economy CLI drafts**, or **flagship CLI finals** across `R2`–`R5`. Always
confirm live CLI pricing via `higgsfield generate cost` before quoting—credit
snapshots below reflect the `ultra` plan as of `2026-11` and may drift.

## Generation Priority Ladder

Web `Unlimited` (`0 cr.`) is the **mandatory default** for all image and video
rounds on Unlimited-eligible subscriptions—never quote CLI credits as the
default price or pause to debate CLI vs. Web for Unlimited-eligible visuals:

1. **Web UI `Unlimited` (`0 cr.`) via built-in browser agent (Priority 1 — DEFAULT):**
   On `ultra` and eligible plans, the **Unlimited (`0 cr.`)** toggle works
   **only** inside the `higgsfield.ai` web app—CLI, API, and MCP always charge
   credits even for Unlimited-eligible models. Route every `R2`–`R5` image and
   video generation to the built-in `browser` subagent first, verify the
   **`Unlimited` toggle is ON and the Generate button reads `0` / Unlimited**
   before triggering (fail closed: never trigger a non-zero web spend without
   Director approval), and download outputs straight into `campaigns/<slug>/media/`.
2. **Economy CLI drafts (Priority 2 — FALLBACK ONLY):** Use paid CLI via
   `hf_guard.py run` only when the target model has no active `Unlimited` toggle
   on `higgsfield.ai` (e.g., audio/TTS/SFX or excluded models), the web queue
   stalls critically, or the Director explicitly asks to spend CLI credits for
   parallel speed (`0.12–0.5 cr.` stills; `5–10 cr.` `720p` video or `12–15 cr.`
   `seedance_2_5 --draft true`).
3. **Flagship CLI finals (Priority 3 — FALLBACK ONLY):** Check Web `Unlimited`
   native `1080p` first; reserve paid flagship CLI `1080p` renders (`15–80 cr.`)
   strictly for Director-approved `R5` upgrades or high-risk multi-reference
   `R4A` pilots where `Unlimited` is unavailable.

## Built-In Browser Agent Protocol (`higgsfield.ai` Unlimited, `0 cr.`)

Use this mandatory default workflow to capture `0 cr.` Unlimited image or video
generations without violating anti-bot boundaries:

1. **Launch in the user's logged-in browser pane:** delegate to the `browser`
   subagent (`Model: "flash"`) to open `https://higgsfield.ai`, select the
   target model, and verify **four mandatory pre-click checks**:
   - **`Unlimited` toggle is ON** AND the Generate button reads **`0` credits /
     Unlimited** (fail closed: if `> 0`, STOP without clicking and report which
     models ARE `Unlimited`-enabled).
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

## Photorealistic Image Models — Benchmarks & Case Routing

Based on Artificial Analysis Image Arena (blind human preference Elo) and live
Higgsfield CLI pricing:

| Model (`job_type`) | CLI Cost (approx.) | Benchmark Strength | Best Use Case |
| :--- | ---: | :--- | :--- |
| `soul_cinematic` / `text2image_soul_v2` / `soul_location` / `soul_cast` | `0.12 cr.` | Specialized cinematic, location & casting stills | Ultra-cheap `R2`–`R3` lookbook, architectural, casting & lighting exploration (or trained `Soul ID` stills) |
| `gpt_image_2_6` (standard) | `0.25 cr.` | Top-tier prompt adherence, geometry, mirrors, multi-ref edits | **Default `R2`–`R3` economy draft** and complex spatial/reflection staging |
| `seedream_5_0_flash` | `0.50 cr.` | Fast clean realism | **Fast `R2`–`R3` photorealistic draft** (7× cheaper than `seedream_5_5`) |
| `seedream_v5_lite` / `nano_banana_2_lite` / `flux_2` | `1.00 cr.` | Solid mid-budget realism | Low-cost Lookbook `A / B / C` exploration when `0.25–0.5 cr.` drifts |
| `nano_banana_2_1` / `nano_banana_pro` | `1.50–2.00 cr.` | Top physical plausibility, lighting coherence & multi-ref blending | **Best value hero stills (`R3`)** blending cast + location + wardrobe refs |
| `flux_3_image` | `2.00 cr.` | Benchmark leader for raw 35mm photographic skin, grain & non-plastic texture | **Hero editorial/35mm portraits & interiors** without heavy multi-ref edits |
| `seedream_v5_pro` / `kling_image_4_0` | `2.50 cr.` / live | Strong adherence to long structured prompts, orthographic prop/cast sheets & `%`-palette lock (`<= 10` refs, `2k`–`4k`) | **Workhorse `R2B` Asset Bibles & `R3` scene keyframes** (`seedream_v5_pro` is 30% cheaper than `5_5` and native ByteDance match for `seedance_2_5`) |
| `gpt_image_2_6` (high quality) | `2.75 cr.` | Complex prompt logic, typography, strict single-item swaps | Hero frames needing exact multi-element control or mirror continuity |
| `seedream_5_5` | `3.50 cr.` | Top commercial/fashion detail & fabric fidelity under close inspection | **Flagship `R3` macro/fashion close-ups** (wool, leather, knit, hero textures) |

## Video Models — Benchmarks & Case Routing

**Resolution, latent drafting & escalation truth (pixel upscaling vs. latent `Seedance 2.5` drafting):**
- **NEVER pixel-upscale `480p` drafts (`< 1 Mbps`) into `1080p`:** external/pixel upscalers (`bytedance_video_upscale`) on `480p` create halos, muddy faces, and shimmer. `cinematic_studio_video_4_0` does **not** expose `--draft_job_id` in CLI, so use `720p` drafts for non-latent engines.
- **DO use `seedance_2_5 --draft true` (`480p` latent draft at `~3 cr./s`) -> native `1080p` or `4K` finalize (`--draft_job_id`):** unlike pixel upscaling, `--draft_job_id` re-renders the exact locked camera, timing, and acting natively in `1080p` or `4K` (saving ~64% across 3–4 draft tries vs. straight `4K`).
- **Native `4K` 2× punch-in framing:** generating a flagship `Seedance 2.5` hero shot in native `4K` lets `assemble.sh` (`shots[].edit.crop_4k_punchin`) harvest both a wide and a crisp native `1080p` close-up from one take at `0 cr.`
- **Anti-Engine-Zoo & A-Roll First:** keep one primary video engine across a live-action block (avoid mixing 3–4 engines with 4×–20× bitrate disparity, and avoid economy `mini`/`flash` engines on flagship live-action photorealism). Lock talking-head **A-Roll first** before B-Roll, and audition vocal tone cheaply via `voice_change` post-generation instead of re-rolling video. Follow [Mastering & Upscaling](mastering-and-upscaling.md) for every `R4 → R5` upgrade decision.

Based on Artificial Analysis Video Arena (I2V/T2V Elo) and live CLI pricing
(5s clips unless noted):

| Model / Workflow (`job_type`) | CLI Cost (5s) | Refs Supported | Benchmark Strength | Best Use Case |
| :--- | ---: | :--- | :--- | :--- |
| `seedance_2_0_mini` (`480p` / `720p`) | `2.5 cr.` (`4s` = `2 cr.`) / **`5 cr.`** | `start_image`, `end_image`, `image_references` | Fast lightweight Seedance motion | **Default `R4` economy `720p` draft** (3× cheaper than `480p` CS 4.0) to prove rhythm, camera move & edit cut |
| `kling_4_0_flash` (`720p`) | **`7.5 cr.`** | Up to 10 images + `video_references` (`video-edit`, `reference-to-video`) | Fast multi-ref Kling 4.0 choreography | **Default `R4` `720p` draft** before native `1080p` `kling4_0` mastering |
| `kling3_0` (`--mode pro --sound off`, `1080p`) | **`8.75 cr.`** (`1.75 cr./s`, keep `<= 6s`) | `start_image` + opt. `end_image` | Crisp native `1080p` stylized motion at ultra-low cost | **Short (`3–6s`) silent-character / action / reaction / off-screen VO shots** for stylized 2D/3D/animal worlds *(direct natural closed-mouth expressions when silent under off-screen VO; for visible on-camera speaking faces where lip-sync matters, prefer `intone` / Lipsync Studio / native-speech models, and avoid `> 8s` single shots where paws/props warp)* |
| `wan3_0` (`480p` / `720p` / `1080p`) | `5 cr.` / **`8.75 cr.`** / **`17.5 cr.`** | `start_image`+`end_image` OR `image_references` (mutually exclusive) | **Top Elo leader (~1175)**: natural fabric/light physics & subject stability | **Best value `720p` draft & cheapest native `1080p` master** for calm I2V takes *(verify FPS—may output 30fps)* |
| `kling4_0` (`720p` / `1080p` / `4k`) | `12.5 cr.` / **`18.75 cr.`** (`video-edit` `22.5 cr.`) / `45 cr.` | Up to 10 images (`start`/`end` + `image_references`) + `video_references` + `--dynamic_range hdr` | Top motion stability, facial consistency, multi-ref control & native stereo | **Default value native `1080p` `R5` master** (4.3× cheaper than CS 4.0 `1080p`) and motion-locked `video-edit` rescue |
| `veo3_1_lite` / `veo3_1` (`fast high` 4s / `preview`) | `12 cr.` / **`16 cr.`** (4s fast high) / `32 cr.` | `start_image` / T2V | **Benchmark leader for atmospheric light, DOF & cinema audio** | Moody single-subject atmospheric native `1080p` shots without heavy wardrobe ref stacks |
| `wan3_0_prime` (`720p` / `1080p`) | `15 cr.` / **`30 cr.`** | `start_image`+`end_image` OR `image_references` | Elevated fine skin/fabric micro-detail over `wan3_0` | Premium native `1080p` character portraits and tactile single-subject hero takes |
| `flux_3_video` (`720p` / `1080p` / `2k` / `4k`) | `30 cr.` / **`40 cr.`** | Up to 10 images OR `video_references` (mutually exclusive) | Editorial FLUX 3 color science and crisp single-frame look | Stylized fashion/editorial hero shots prioritizing color grade over long choreography |
| `minimax_h3` / `minimax_h3_max` | `10–12.5 cr.` | `start_image` / refs | **Top-5 Elo (~1161)**: strong character likeness retention | Calm portrait/character shots where face stability matters |
| `seedance_2_5` (`--draft true` → `1080p` / `4k`) | `15 cr.` → **`80 cr.`** (`5s`); `18 cr.` → **`96 cr.`** (`6s` 2-shot = `48 cr./cut`); `140 cr.` `4k` | Up to 30 images / 50 refs (`omni_reference`) + `--draft_job_id` + free `--bitrate_mode high` | **Top-5 Elo (~1160)**: multi-shot narrative, exact draft-to-final latent lock & VFX | **Gold standard `R4 → R5` CLI path** when exact acting/timing must transfer 1:1 into native `1080p` (`--bitrate_mode high`); pair adjacent cuts as `6s` 2-shots (`3s + HARD CUT + 3s`) to halve per-cut cost |
| `cinematic_studio_video_4_0` (`480p` / `720p` / `1080p`) | `15` / `35` / **`80 cr.`** | Up to 30 images / 50 refs (`omni_reference`) + free `--bitrate_mode high` *(no CLI `--draft_job_id`)* | Best multi-reference continuity + native diegetic foley + Web Cinema Studio presets | Direct native `1080p` (`--bitrate_mode high`) hero shots or Web Cinema Studio upgrades—avoid `480p` CLI drafts if you need 1:1 `R5` escalation |

## Audio & Advisory Models (`R3`–`R5`)

| Category | Model / Workflow (`job_type`) | Notes & Live Routing |
| :--- | :--- | :--- |
| **Voiceover (VO)** | `text2speech_v2` (`--variant elevenlabs\|seed_speech\|...`), `seed_audio` | Pair with `higgsfield voices list` (`--voice_id`, `--voice_type preset\|element`); check timing via `make qa-voice` |
| **Multi-Speaker Dialogue** | `elevenlabs_v4` (`--dialogue`) | Multi-voice scenes; lock voice WAVs in `R3` before `intone` lip-sync |
| **Voice Swap / Dubbing** | `voice_change`, `dubbing` *(workflows)* | Re-voice or dub locked clips (`--duration` is cost-only; `hf_guard.py` strips it on exec) |
| **Music Score** | `sonilo_music` (economy), `elevenlabs_music_v2_5` (flagship) | Generate uncut beat-locked score separately; keep video clips diegetic-only |
| **Foley / SFX** | `mirelo_text_to_audio` | Clean standalone diegetic sound layers |
| **Advisory Pacing Read** | `brain_activity` (`--kind analysis`) | Optional post-cut virality/pacing read (run only when approved) |

## Quick Round-by-Round Defaults & Stack Presets

- **`R2` Lookbook & `R3` Draft Stills:** Web `Unlimited` (`0 cr.`) first →
  else CLI `soul_location` / `soul_cast` / `text2image_soul_v2` (`0.12 cr.`),
  `gpt_image_2_6` (`0.25 cr.`), or `seedream_5_0_flash` (`0.5 cr.`).
- **`R2B` Asset Bibles & `R3` Locked Hero Stills:** Web `Unlimited` (`0 cr.`)
  if eligible → else **`seedream_v5_pro` (`2.5 cr.`)** (workhorse orthographic
  prop/cast/location bibles & `2k` scene keyframes), `nano_banana_2_1`
  (`1.5 cr.`), `flux_3_image` (`2 cr.`), or **`seedream_5_5` (`3.5 cr.`)**
  reserved for macro/fabric hero close-ups.
- **`R4A` / `R4B` Motion Drafts:** Web `Unlimited` (`0 cr.`) first → else CLI
  `seedance_2_0_mini` (`720p`, `5 cr.`) / `kling_4_0_flash` (`720p`, `7.5 cr.`) /
  `wan3_0` (`720p`, `8.75 cr.`) for clean legible drafts; use **`seedance_2_5`
  `--draft true` (`15 cr.` 5s / `18 cr.` 6s 2-shot)** whenever an `R4A`/`R4B`
  take needs guaranteed 1:1 latent escalation to native `1080p` via
  `--draft_job_id`.
- **`R5` Final Master (`1080p`):** Follow the deterministic 5-path algorithm and
  6-rule Upscale Gate in [Mastering & Upscaling](mastering-and-upscaling.md)
  (Web `Unlimited` → `seedance_2_5 --draft_job_id --bitrate_mode high` → value
  native `1080p` `kling4_0`/`wan3_0`/`veo3_1`/`wan3_0_prime` → motion-locked
  `kling4_0 --mode video-edit` → direct `cinematic_studio_video_4_0`; never
  pixel-upscale `480p` drafts).

### Two Proven 30s Production Stack Presets (Native `1080p`)

1. **Commercial Hybrid (~`250–400 cr.`):** `soul_location`/`soul_cast` (`0.12 cr.`)
   world scout → `seedream_v5_pro` (`2.5 cr.`) + selective `seedream_5_5` (`3.5 cr.`)
   for `R2B`/`R3` → `wan3_0` (`17.5 cr.`) or `kling4_0` (`18.75 cr.`) native
   `1080p` on clean single-beat shots + `seedance_2_5` (`15→80 cr.`, or `18→96 cr.`
   `6s` 2-shot) strictly on `2–3` hero acting or complex-continuity beats.
2. **Cinema / Flagship Narrative (~`650–1,000 cr.`):** `soul_location`/`text2image_soul_v2`
   (`0.12 cr.`) → orthographic `#808080` prop/cast/location bibles + `2k` keyframes
   on `seedream_v5_pro` (`2.5 cr.`) / `seedream_5_5` (`3.5 cr.`) → `seedance_2_5`
   (`--draft true` → `--draft_job_id --resolution 1080p --bitrate_mode high`) in
   paired `6s` 2-shot blocks (`3s + HARD CUT + 3s` = `48 cr./cut`), finished with
   unified post color grade and dedicated foley/sound mix.

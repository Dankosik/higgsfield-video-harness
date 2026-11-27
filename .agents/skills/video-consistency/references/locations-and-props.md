# Locations, Buildings & Props Continuity Runbook

Executable protocol for building, wiring, and preserving **locations (interiors), buildings (exteriors), props, and vehicles** within a scene and across cuts in Higgsfield and modern DiT video models. Verify live schemas and prices via `higgsfield model get <id> --json`, `workflow get <id> --json`, and `generate cost` before quoting; validate reference budgets offline via `make campaign-check CAMPAIGN=<slug>`.

## 1. Fast Plate Triage (IF / THEN)

Run this triage during `R1B` before planning `R2` credits so simple 1-angle spots never burn extra plates and complex cuts never skip required geometry:

| IF the storyboard / brief contains… | THEN require this plate / tier | Tool / Path |
| :--- | :--- | :--- |
| **Single-angle room or exterior** (camera stays on one side, no mirror) | **Tier 1:** 1 Empty Master Wide (`24–28mm`) only — skip Reverse Wall | `soul_location` (`0.12 cr.`) → Web `Unlimited` / `seedream_v5_pro` / `seedream_5_5` / `nano_banana_2_1` |
| **Reverse shots, OTS dialogue, 180° coverage, or mirror/glass reflections** | **Tier 1+:** Empty Master Wide **+ Reverse Wall (`~120–180°`)** | Lock Master (`R2A`) → derive Reverse Wall (`R2B`) via `3d_jutsu_angles` or `nano_banana_2_1` |
| **4+ camera angles or corner trucks/orbits inside one room** | **Tier 2:** Master + Reverse + **Corner (`45–90°`) / Isometric Plan** (or 3×3 sheet → sliced tiles) | `nano_banana_2_shots` → `make slice-grid` (`qa_media.py slice`) → upload winning tiles |
| **Same set across time-of-day, weather, or persistent prop state (2+ shots)** | **State Plate** derived from the locked Master (never re-roll from scratch) | `nano_banana_2_relight` (lighting) or `flux_kontext` / `nano_banana_2_1` (state) |
| **Hero prop or building seen in BOTH wide (`WS`/`MS`) and close (`CU`/`ECU`)** | **Scale Reference** plate (prop in plain hand / building with ~2.1m doorway) + Macro Detail *(ECU only)* | `R2B` derived plate (`variants_requested: 1`) or real photo in `media/references/` |
| **Client photo has wrong `aspect_ratio` or background clutter** | Normalize **before** locking `R2` Master (`outpaint` to campaign ratio; isolate prop) | `outpaint` / `flux_2_pro_outpaint`; `image_background_remover` / `image_decompose` |
| **Complex multi-room building, continuous flythrough, or 20+ shots on one set** | **Tier 3 3D Anchor:** persistent 3D mesh/splat (`World Labs Marble` / 3DGS `.ply` / Blender greybox) | Render angle stills from virtual cameras → photoreal pass in `R3` or `depth_anything_video` |

## 2. Round-by-Round Execution Protocol

Execute in strict round order. Never invent new walls, scales, or props inside `R4/R5` video prompts.

### Step A — `R1B` Spatial Blueprint & Manifest (`0 cr.`)
1. Write an absolute **4-Wall Spatial Map (`N / E / S / W`)** plus fixed key-light source and prop scale ratios inside `storyboard.md` and `shotlist.json` (`continuity_lock`).
2. Tag every shot in `storyboard.md` with **`CAM`** (position + facing wall), **`EYELINE`**, and mutable **`PROP STATE`**.
3. Run Section 1 Triage and declare all needed `R2A` Masters (`variants_requested: 3`) and `R2B` derived plates (`variants_requested: 1`) in `shotlist.json` using per-entity ID prefixes (`loc_<set>_*`, `bldg_<name>_*`, `prop_<item>_*`).
4. Run `make campaign-check CAMPAIGN=<slug>` to verify hard CEL limits, optimal ref budgets (`3–5` max `6` stills, `2–4` max `5` video), and `Campaign cap`.
- *Done when:* `make campaign-check` passes with zero errors, every multi-angle/reverse/mirror set has a planned Reverse Wall, and every shot declares only visible refs.

### Step B — `R2A` Master Taste Lock (Unlimited-First)
1. Follow [Model Selection](../../higgsfield-cli/references/model-selection.md): check **`higgsfield.ai` Web `Unlimited` (`0 cr.`)** first for multi-plate Asset Bibles; fall back to `soul_location` (`0.12 cr.`) / economy CLI drafts → hero `2k`/`4k` lock (`seedream_5_5` `1.5 cr.` `2k` / `2.5 cr.` `4k`, `nano_banana_2_1` `2 cr.` `2k` / `3 cr.` `4k`, `seedream_v5_pro` `2.5 cr.` at `2k` max, or `flux_3_image` `3 cr.` `2k`).
2. Generate `A / B / C` variants of **Empty Masters** (zero people, zero stray clutter) and **`#808080` matte mid-gray Props** (`5000–5600K` soft diffused light, soft contact shadow). Keep invented characters isolated *without* hero props in `R2A`.
3. Filter via fresh `reviewer-agent`, ship `Dailies 2`, upload approved winners via `hf_guard.py upload --round R2`, and set `status: "LOCKED"` + `approved_upload_id` in `shotlist.json`.
- *Done when:* every primary location, building, prop, and cast Master is `LOCKED` with an `approved_upload_id`.

### Step C — `R2B` Plate Expansion (Only Triggered Plates)
1. For each plate triggered by Section 1 Triage, generate from the **locked `R2A` Master UUID** using `variants_requested: 1` (never burn 3× variants on an already-locked room):
   - Specific reverse/3/4/high angle → `3d_jutsu_angles` (`--resolution 2k`) or `nano_banana_2_1` (`2k`/`4k`).
   - Full angle pack from 1 master → `nano_banana_2_shots` → slice clean tiles with `make slice-grid FILE=<sheet.png> OUT_DIR=<dir> ROWS=3 COLS=3 TRIM=4 PREFIX=loc_<set>` → inspect via `view_image` → keep only winning tiles.
   - Lighting/time-of-day shift → `nano_banana_2_relight` (see Section 5 cube codes) or `flux_kontext`.
   - Mismatched client ratio or cluttered photo → `outpaint` / `flux_2_pro_outpaint` or `image_background_remover` / `image_decompose`.
2. Inspect derived plates via `reviewer-agent` against the `R2A` Master (same architecture, finishes, and proportions), upload winners via `hf_guard.py upload --round R2`, and lock UUIDs in `shotlist.json` (`lookbook[]` or `references[]`).
- *Done when:* every Reverse Wall, State Plate, and Scale Reference needed by `storyboard.md` is uploaded, QA-verified, and registered in `shotlist.json`.

### Step D — `R3` Keyframe Assembly (`2k`/`4k` Stills)
1. For each shot, bind **3–5 visible-only refs** (`1–2` matching location/wall plates + `1` cast + `1–2` visible props). Omit off-screen props and unused walls (**Visibility Pruning**).
2. Write the still prompt using the **4-part `R3` template** in Section 3 (`[Camera + Facing Wall] + [Placement & Contact Shadow] + [Scale Ratio] + [Pigment Isolation]`).
3. Render at **`2k` or `4k`** (`seedream_5_5`, `nano_banana_2_1`, `kling_image_4_0`, or `seedream_v5_pro` at `2k` max), audit via `reviewer-agent` (check 4-wall geography, reflections, doorway thresholds, prop scale, and state), ship `Dailies 3` + `animatic.mp4`, lock approved stills, and upload via `hf_guard.py upload --round R3`.
- *Done when:* every shot's spatial geometry, scale, reflection, and lighting continuity is visibly proven in `LOCKED` `R3` stills before spending a single video credit.

### Step E — `R4 / R5` Delta Motion & Surgical Prop Rescue
1. For each shot, bind **2–4 visible-only images**: `1` locked `R3` `--start_image` + `1–2` highest-risk canonical **`R2`** UUIDs (rotating prop or wall revealed by camera move) + optional `1` locked `R3` `--end_image`. Honor hard CEL rules (`wan3_0` / `wan3_0_prime` / `minimax_h3` forbid combining `start_image`/`end_image` with reference media; `flux_3_video` forbids mixing images with `video_references` — see [Live Workflows](../../higgsfield-cli/references/live-workflows.md)).
2. **Canonical Source Law:** Never chain compressed video screenshots shot-over-shot (*photocopy cascade*). If bridging continuous action via `sNN.last_frame`, always include the original locked `R2` prop/location UUIDs in `--image_references`.
3. Choose motion topology:
   - **Standard cut-by-cut:** `seedance_2_5 --mode omni_reference` (`--draft true` → `--draft_job_id` + `--bitrate_mode high`) or `kling4_0 --mode reference-to-video --duration 5` *(pass `--duration` explicitly; live default is `10s` = `37.5 cr.` at `1080p`)*.
   - **2–4 cuts inside ONE room:** native CLI multi-shot (`kling_o3_image_reference --multi_shots true --multi_prompt [...]`) or timecoded `seedance_2_5` 2-shot blocks *(live `kling4_0` has no CLI `multi_shots`/`multi_prompt`)*.
   - **Unbroken camera continuation:** `--mode video_extension --extension_mode forward|backward` (`seedance_2_5` / `cinematic_studio_video_4_0`), or `--start_image` + `--end_image` when physically traversable in 5s with a true 3D verb (`Dolly`/`Truck`, never `Zoom`/`Pan`).
4. Write a **delta-only** video prompt pairing every `@ImageN` tag with its concrete noun (never restate static room walls or prop appearance).
5. **Surgical Prop Rescue:** If a take nails acting and camera motion but one prop drifts mid-clip, repair it with `hf_mult_replace_object_flash` (`12 cr.`, `1080p`-only), `hf_mult_replace_object` (`120 cr.`), or `kling4_0 --mode video-edit --duration 5` (`22.5 cr.`) bound to the canonical `R2` prop plate instead of discarding the clip.
- *Done when:* `3x2` contact sheets (and `1:1` `--crops` on `R5`) pass `reviewer-agent` on start, middle, and end frames with zero 180° flips, scale jumps, prop morphing, or post-transition `xfade` band-aids.

## 3. Copy-Ready Templates

### A. 4-Wall Spatial Map & Per-Shot Tag (`storyboard.md` & `shotlist.json`)
```text
Spatial Map (loc_apt):
- North wall: tall arched window (primary 5200K daylight, dusty-teal curtains)
- East wall: white bookshelves with ceramics + framed black-and-white print
- South wall: warm oak entry door (brass handle, opens inward left)
- West wall: petrol-teal velvet sofa + tall oak-framed rectangular mirror

Shot Tag (add to every shot header/carry):
CAM: near South door facing North-West (35mm) | EYELINE: screen-left toward West mirror | PROP STATE: matte-black carry-on OPEN on wool rug, lamp OFF
```

### B. `shotlist.json` Wiring (`R2A` Master + `R2B` Derived + Cropped Tile → `R3` → `R4/R5`)
```json
"references": [
  { "id": "loc_apt_corner_tile", "kind": "location_angle", "local_path": "media/lookbook/locations/tiles/loc_apt_r0_c1.png", "upload_id": "<uuid>" },
  { "id": "prop_kettle_scale", "kind": "prop_scale", "local_path": "media/references/kettle_in_hand.jpg", "upload_id": "<uuid>" }
],
"lookbook": [
  { "id": "loc_apt_master", "kind": "location", "variants_requested": 3, "status": "LOCKED", "approved_variant": "A", "approved_upload_id": "<master_uuid>", "estimated_credits": 4.5 },
  { "id": "loc_apt_reverse", "kind": "location", "variants_requested": 1, "status": "LOCKED", "approved_variant": "A", "approved_upload_id": "<reverse_uuid>", "estimated_credits": 2.5 },
  { "id": "loc_apt_night", "kind": "location", "variants_requested": 1, "status": "LOCKED", "approved_variant": "A", "approved_upload_id": "<night_uuid>", "estimated_credits": 1.5 },
  { "id": "prop_kettle_hero", "kind": "object", "variants_requested": 3, "status": "LOCKED", "approved_variant": "B", "approved_upload_id": "<prop_uuid>", "estimated_credits": 6.0 }
],
"shots": [{
  "id": "s02",
  "still": { "model": "nano_banana_2_1", "references": ["loc_apt_reverse", "loc_apt_master", "lb_cast", "prop_kettle_hero"] },
  "video": { "model": "seedance_2_5", "mode": "omni_reference", "start_image_from": "s02.still", "image_references": ["prop_kettle_hero", "loc_apt_reverse"] }
}]
```

### C. Fill-in-the-Blank Prompt Skeletons
- **`R2A` Empty Location Master:** `Empty architectural film still, 24mm lens, locked-off eye-level wide shot of <room/exterior>, completely uninhabited with zero people and zero loose tabletop clutter. <North/East/South/West key fixtures>. <4-part motivated lighting>. PALETTE, stated first: <45% dominant>, <35% secondary>, <20% accent>. Unretouched 35mm cinema still; tech tail palette: <same 45%/35%/20% split>, <aspect_ratio>.`
- **`R2A` Neutral Orthographic Prop Plate:** `Prop reference plate. Isolated object study of <exact prop form, materials & critical hardware invariants—explicitly naming absent/matte parts>, centered in pure orthographic side profile (or 3/4 hero angle + matching reverse view) square to the lens with zero perspective skew on a flat seamless neutral mid-gray (#808080 / #8E8A84) backdrop with soft grounded contact shadow. Broad soft color-neutral 5400K studio light, deep edge-to-edge focus, zero harsh shadows, zero color grade—a reference plate built to be read and reused, not a cinematic hero shot.`
- **`R3` Multi-Ref Scene Assembly (`2k`/`4k`):** `<focal length> <shot scale> inside the <location> from Image 1 (camera near <wall> facing <wall>). The <character> from Image 2 <pose & eyeline> beside the <prop> from Image 3. Place the <prop> squarely on <surface> with a soft grounded contact shadow matching the <key light direction>; keep <prop height/size> roughly <scale ratio> beside <benchmark>. Strictly preserve the <prop>'s original <color/finish> without wall color bleed.`
- **`R4/R5` Delta-Only Motion (`omni_reference`):** `Starting from the opening frame, preserve the exact <prop> geometry from @Image2 and the <wall/fixture> from @Image3. <One dominant camera move>. 0-2s: <counted physical beat 1 + gaze anchor>. 2-5s: <counted physical beat 2 + secondary physics>. Audio: <concrete diegetic foley + room tone>. NO MUSIC. NO BACKGROUND SCORE. Native diegetic sound only.`

## 4. Canonical Input Standards & High-Risk Edge Cases

- **Interiors (3–4 plates):** Empty Master Wide (`24–28mm`) + Reverse Wall (`~120–180°`) + Corner (`45–90°`) or Isometric Floor Plan + optional Hero Detail Zone. Match `aspect_ratio`, base light, and **Percentage Palette** (`45% / 35% / 20%`) across plates.
- **Buildings (3–4 plates):** 3/4 Hero Facade + Street-Level Approach + Reverse Exit View + optional Aerial/Isometric Massing. Include real-world scale anchors (~2.1m door, steps, lamppost, parked car); leave tiny building signage out and composite legible signs in post.
- **Props (2–4 plates):** Flat `#808080` / `#8E8A84` matte mid-gray background (pure white only for dark matte objects *with* contact shadow), broad color-neutral `5000–5600K` light (prevents *Lighting Bake-In*), deep edge-to-edge focus, zero clutter: **Orthographic Side Profile** (zero perspective skew, explicit hardware invariants, *"built to be read and reused, not a hero shot"*) + Hero 3/4 / Reverse pair + Scale Reference (in hand/beside benchmark) + Macro Detail (`CU`/`ECU` only).
- **Vehicles & large machinery:** Exterior 3/4 + Side/Rear + separate Interior Cabin/Dashboard plate; keep plates/screens angled away or blank for post compositing.
- **Mirrors, glass & reflections:** Reflections show the **opposite wall** and **rear** of the subject/prop—bind the Reverse Wall plate in `R3` and name the reflected wall/back explicitly so models never clone the front pose or invent a foreign room.
- **Exterior ↔ Interior thresholds & through-glass composites:** Lock a **Threshold Anchor** matching door color, handle, swing direction on both sides, and matching exterior sky/weather/street through windows. Whenever shots look *through* a window or glazed door between exterior and interior, pre-composite the facade + glazed door + interior hallway/staircase in `Seedream 5.5` (`1.5k`–`2k`) into one continuity plate so background architecture stays locked across cuts.
- **Location Anti-Composition-Lock (`omni_reference` video):** Whenever binding a wide location plate into multi-shot video (`seedance_2_5`), state explicitly: `Image N defines ONLY the location—choose camera angles for the action rather than reproducing the reference composition.` so the model navigates the 3D space instead of freezing on the still's framing.
- **Prop State Permanence:** Track mutable states (open/closed suitcase, liquid level, garment worn vs. draped, wet/dry ground, lamp ON/OFF) in `Continuity carry`; derive a locked State Plate whenever a changed state persists across 2+ shots.
- **Multi-location isolation & lens family:** Prefix IDs per location (`loc_apt_*`, `loc_street_*`); never mix Location A refs into Location B shots except across a shared doorway. Keep focal lengths inside one coherent family per space (`24–35mm` wide/medium, `50–85mm` close-ups).

## 5. Reference Budgets & Higgsfield Tool Routing

Exceeding optimal counts triggers **attention dilution**, **attribute bleed**, and **rigid stagnation**. `make campaign-check` mechanically enforces hard CEL limits (errors) and flags optimal-budget or photocopy violations (warnings). For canonical full pricing and CEL recipes, see [`higgsfield-cli`](../../higgsfield-cli/SKILL.md) ([Model Selection](../../higgsfield-cli/references/model-selection.md) & [Live Workflows](../../higgsfield-cli/references/live-workflows.md)).

### Live Higgsfield Limits vs. Optimal Count

| Stage / Model (`job_type`) | Hard CLI Limit (CEL) | **Optimal Count** | Key Constraint |
| :--- | :--- | :--- | :--- |
| **Image (`R3`)** | | | |
| `nano_banana_pro` / `nano_banana_2_1` | `<= 14` (`<= 13` + mask) | **3–5** (max 6) | Top spatial reasoning & multi-ref blending; render at **`2k`/`4k`** (`2_1`: `2`/`3 cr.`, `pro`: `2`/`4 cr.`) |
| `seedream_5_5` / `seedream_v5_pro` | `<= 10` | **3–5** | `seedream_5_5` (`1.5 cr.` `2k` / `2.5 cr.` `4k`) flagship bibles & keyframes; `seedream_v5_pro` (`2.5 cr.`, caps at `2k`) |
| `kling_image_4_0` / `kling_omni_image` | `<= 10` (`kling_image_4_0` incl. `kling_element_ids`) | **3–5** | Strong storyboard staging (`kling_image_4_0` `2k`–`8k`; `kling_omni_image` `1k`–`2k`) |
| `gpt_image_2_6` | `image_references[]` | **2–4** | Strong mirror/spatial logic (check photoreal taste) |
| `flux_kontext` | `<= 4` | **1–2** | Single-step edits, reverse walls & state shifts (`1.5 cr.`) |
| `3d_jutsu_angles` | `<= 10` | **1–3** | Dedicated 3D angle re-projection at `2k` (`2.5 cr.`) |
| `nano_banana_2_shots` / `outpaint` / `flux_2_pro_outpaint` / `image_background_remover` / `image_decompose` | **Exactly `1`** | **1** | Accept **no `--prompt`**; quote `generate cost` only with an uploaded UUID |
| **Video (`R4`/`R5`)** | | | |
| `seedance_2_5` / `cinematic_studio_video_4_0` (`omni_reference`) | `<= 30` imgs (`<= 50` media) | **2–4** (max 5: `start` + 1–3 refs + opt. `end`) | `> 5` images trigger bleed & stiff motion; pass `--bitrate_mode high` at `1080p` (`CS 4.0` caps at `1080p`, no `--draft`) |
| `kling4_0` (`reference-to-video`) | `<= 10` imgs (`<= 15` w/ video+elements) | **2–4** (`start` + `1–2` refs/elements + opt. `end`) | Native `720p`/`1080p`/`4k` (`18.75 cr.` 5s `1080p`), `kling_element_ids`; pass `--duration 5` (defaults to `10s` = `37.5 cr.`) |
| `kling_4_0_flash` (`reference-to-video`) | `<= 10` imgs (`<= 15` w/ video+elements) | **2–4** (`start` + `1–2` refs/elements; **no `end_image`**) | **`720p`-only** fast draft (`7.5 cr.` 5s / `15 cr.` default `10s`); omits `end_image` |
| `flux_3_video` | `<= 10` imgs | **1–3** | **CEL:** cannot mix image inputs with `video_references` |
| `wan3_0` / `wan3_0_prime` | `start`+`end` **OR** `image_references` | **1–2** (`start` or `start+end`) | **CEL:** `start`/`end` and reference media are mutually exclusive—bake continuity in `R3` |
| `veo3_1` | CLI: **1** (`start_image`); external Ingredients: `3` | **1** (CLI) / **2–3** (Ingredients) | Clean `R3` keyframe I2V keeps camera fluid |

### Tool-by-Job Quick Lookup

| Job | Tool (`job_type`) | Live Cost\* | Notes |
| :--- | :--- | :--- | :--- |
| Fast `R2` architectural lookbook | `soul_location` / `cinematic_studio_soul_location` | `0.12 cr.` | Cheap `A/B/C` search before hero lock |
| Expand mismatched client ratio | `outpaint` / `flux_2_pro_outpaint` | live quote | `outpaint --aspect_ratio 16:9` or `--expand_left/right/top/bottom` |
| Mint 9 angles in 1 latent pass | `nano_banana_2_shots` → `make slice-grid` | live quote | Always slice to clean standalone PNGs before video |
| Specific 3D angle (reverse, 3/4) | `3d_jutsu_angles` (`--resolution 2k`) | `2.5 cr.` | Re-projects locked Master cleanly |
| Strip clutter / split layers | `image_background_remover` / wf `image_decompose` | live / `2.0 cr.` | Background cutout vs. granular foreground/background layers |
| Relight set without moving walls | `nano_banana_2_relight` / `flux_kontext` | live / `1.5 cr.` | Requires `light_source`, `light_quality`, `color`, `brightness` |
| 2–4 cuts inside one room | `kling_o3_image_reference --multi_shots true` | `6.25–10 cr.` (5s) | Shared latent space holds walls/props across cuts |
| Unbroken same-set extension | `seedance_2_5` / `cinematic_studio_video_4_0 --mode video_extension` | live quote | `--extension_mode forward\|backward` |
| Fix 1 drifted prop in locked clip | `hf_mult_replace_object_flash` / `hf_mult_replace_object` / `kling4_0 --mode video-edit` | `12` / `120` / `22.5 cr.` (5s) | Genjutsu Lite (`1080p`-only, 10× cheaper) / Genjutsu (`480p`–`1080p`) / Kling edit (`--duration 5`) |
| Tier 3 depth pass | `depth_anything_video` (`--colormap grayscale --variant VDA-Large`) | `7.57 cr.` (`720p`) | Locks 3D geometry from greybox or draft |

*\*Web UI vs. CLI Elements boundary: creating Cinema Studio 4.0 **Elements** (`@Location`, `@Prop`) and creating **Kling Elements** (`kling_element_ids`) are Web UI actions; in CLI, bind pre-existing `kling_element_ids` or uploaded `--image_references` UUIDs. Always pair `@ImageN` tags with concrete object nouns (`the kettle from @Image2`) to prevent 1-index ambiguity alongside `--start_image`.*

**`nano_banana_2_relight` `--light_source` 26-point 3D cube:** `<depth: f(ront)|m(id)|b(ack)><height: u(p)|m(id)|d(own)><side: l(eft)|m(id)|r(ight)>` (all 27 minus `mmm`). Examples: `ful` = front-upper-left key, `mml` = pure eye-level left window, `bur` = back-upper-right rim, `fum` = overhead front fill.

## 6. Spatial & Prop Failure Diagnostics

| Observed Symptom | Root Cause | Exact Fix |
| :--- | :--- | :--- |
| **Reverse shot invents new room or flips furniture 180°** | Missing Reverse Wall plate or camera-relative left/right text | Generate & lock **Reverse Wall** (`3d_jutsu_angles` / `nano_banana_2_1`) from `N/E/S/W` map; re-stage `R3` still with explicit `CAM` facing & eyeline |
| **Mirror / window reflection shows wrong room or front-pose clone** | Missing Reverse Wall plate or unspecified reflection content | Attach locked **Reverse Wall** in `R3` and describe reflected opposite wall + rear of subject explicitly |
| **Prop or building shifts size across cuts (`Scale Drift`)** | No relative size benchmark or jump from `WS` to `ECU` | Add **Scale Reference** plate to `R3` and state explicit size ratio (`kettle ~1.3× mug`) |
| **Prop carries neon/wrong shadows in daylight (`Lighting Bake-In`)** | Prop ref shot under colored or harsh directional light | Regenerate prop on `#808080` gray under diffused `5000–5600K` light, or neutralize via `nano_banana_2_relight` |
| **Video freezes stiff ("living photo") or colors bleed** | Reference overload (`> 5–6`), duplicates, or off-screen refs | Prune to **2–4 visible refs**, remove off-screen assets, and isolate `@ImageN` noun roles |
| **Walls stretch like rubber during camera move** | `Pan`/`Zoom` used for 3D parallax, or start→end > 5s distance | Switch verb to `Lateral truck`/`Slow dolly-in`, shorten delta, or escalate to Tier 3 depth/3D |
| **Background clutter follows prop into every scene** | Source prop photo sat on a messy surface | Isolate with `image_background_remover` / `image_decompose` or regenerate on `#808080` gray |
| **Grid borders or split-screen flicker in video** | Raw 2×2/3×3 contact sheet passed straight to video model | Slice with `make slice-grid ... TRIM=4`, upload individual PNG tiles via `hf_guard.py upload` |
| **Textures turn muddy by Shot 4–5** | Photocopy cascade (chaining compressed video screenshots) | Re-anchor `R3` stills and `R4/R5` `--image_references` to original `LOCKED` `R2` Master UUIDs |
| **One prop warps mid-take on an otherwise great clip** | Diffusion drift on moving handheld object | Rescue surgically with `hf_mult_replace_object_flash` (`12 cr.`, `1080p`-only), `hf_mult_replace_object` (`120 cr.`), or `kling4_0 --mode video-edit --duration 5` |

## 7. Surgical 1:1 Repairs, Specialty Prop Plates & Unified Palette Cards

- **Unified `Palette Card` (HEX Lock):** Define one compact HEX palette card in
  `style-bible.md` (highlights, midtones, shadows, accent) and attach it to
  *every* `R2` location prompt (`Soul Cinema`) so all sets share one grade
  before video generation.
- **Surgical `Seedream 5.0 Pro` Repairs Over Blind Re-Rolls:** Whenever a
  location, prop, or video frame misses one concrete detail (wrong seat count,
  garbled panel text, stray logo, wrong lighting mood), never re-roll the whole
  asset from scratch — run a surgical 1:1 edit:
  1. **1:1 Detail Fix:** Start with `LOCKED — the entire image one-to-one with
     the input, highest priority`, followed by `THE ONLY CHANGE — <exact fix>`
     and `no reframe, no zoom, no glow`.
  2. **`RELIGHT ONLY`:** Keep exact camera, lens, and furniture; change only
     exposure/time-of-day (`RELIGHT ONLY. Nothing moves, nothing is added or
     removed`).
  3. **Targeted Video Frame Repair:** Extract a broken `R4` frame (e.g., garbled
     button/signage), repair only that zone in `Seedream 5.0 Pro`, and inject it
     back into `Seedance 2.5` as `@Image 1` with explicit time-window override.
- **Specialty Prop & Product Reference Formats:**
  - *Two-Panel Closed/Open Product Sheet:* Left = closed product, Right = open
    mechanism/interior, identical scale/height on neutral grey (`100mm macro`).
  - *Hollow Wearable Props:* Specify `THE OBJECT IS EMPTY AND HOLLOW` (no
    mannequin limb inside) so garments/braces fit any actor cleanly.
  - *Isolated Text/Note Props:* Never rely on video prompts to spell handwritten
    notes or documents — generate an isolated still on pure `#000000` (batch 4–8
    stills) and attach the winner as `@Image`.
  - *Heavy Props / Creatures (`Clay -> Macro -> Flash`):* Route bespoke heavy
    props and creatures through matte dark-grey clay -> `1:1` flash macro
    swatches -> unstylized frontal-flash "boring makeup-test photo"; **rooms
    skip clay** and stay on `Soul Cinema` for natural wear/imperfection (see
    [`video-previz-vfx`](../../video-previz-vfx/SKILL.md)).
  - *Clay-Render Plate Placeholders & Exclusion Marks:* On busy street/location
    plates, paint a flat green clay block (`Seedream 5.5`) to lock hero vehicle
    perspective/contact shadow, or circle clutter in red for explicit removal.

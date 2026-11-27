# Camera Control, Optics & Motion Routing Playbook

Executable decision spec for choosing **which Higgsfield camera tool to use, when, why, and how to direct optics, camera moves, rigs, speedramps, and transitions** without morphing, drift, or credit waste. For live CLI credit quotes, model benchmarks, and CEL/default flag traps, cross-check [Model Selection](../../higgsfield-cli/references/model-selection.md) and [Live Workflows](../../higgsfield-cli/references/live-workflows.md).

## 1. Four Hard Camera Invariants

1. **Hero Frame First & Delta Separation:** Lock framing, focal length, lens character, aperture feel, lighting, and perspective in `2k`/`4k` `R3` stills before animating (I2V amplifies still flaws). In video prompts, describe **only temporal delta** (camera trajectory, counted action, secondary physics, diegetic audio)—never re-describe static appearance or room layout.
2. **Zero Double-Command:** When a mechanical control owns the camera—Web Cinema Studio movement preset/`#` tag, CLI `--camera_style`, `--speedramp`, `Draw To Video` arrows, or `@Video` motion transfer—**omit competing camera movement instructions from prompt text**. Let the mechanical layer own the trajectory while prose drives subject action, physics, and audio (keep at most a neutral stabilizer like `horizon level`).
3. **One-Move Rule & Explicit Stillness:** Direct **one dominant camera axis per 5s shot**. When stacking UI presets (`Mix` / `#` tags in Web Cinema Studio), combine at most **2 compatible axes** (e.g. `Slow Truck Right` + `Subtle Crane Up`) and respect selection order, which governs trajectory sequence. Whenever a static frame is intended, state `Locked-off static tripod shot, horizon level` explicitly—omitting camera phrasing lets DiT models inject wandering drift.
4. **3D Parallax vs. Nodal Optics:** Match camera verbs to real 3D geometry ([Camera Grammar](prompt-patterns.md#camera-grammar-and-geometric-pairs))—use `Dolly` (not `Zoom`), `Truck`/`Track` (not `Pan`), and `Pedestal`/`Crane` (not `Tilt`) whenever perspective or occluded background shifts; reserve `Zoom`/`Pan`/`Tilt` for fixed-axis optical/nodal moves.

## 2. Deterministic Camera Tool-Routing Algorithm

Evaluate each shot top-to-bottom and take the **first matching branch** (check [Live Workflows](../../higgsfield-cli/references/live-workflows.md) for exact CLI ref/CEL constraints and [Model Selection](../../higgsfield-cli/references/model-selection.md) for live pricing):

1. **IF replicating an exact real-world camera path or choreography from reference footage** → **Motion Transfer:**
   - **Scene + camera + choreography transfer onto 1+ asset refs:** `hf_mult_motion_control_flash` (fast `1080p` value) or `hf_mult_motion_control` (**Genjutsu**) OR `seedance_2_5 --mode omni_reference` with `@Video1` (`"Follow the exact camera trajectory and pacing of @Video1"`).
   - **Human performance + framing transfer from reference video onto 1 character image:** workflow `kling3_0_motion_control` (`--background_source input_image|input_video`).
   - **Re-rendering an approved draft's locked camera natively at `1080p`:** `kling4_0 --mode video-edit --resolution 1080p --duration 5` (pass `--duration` explicitly; default is `10`) or grayscale depth extraction via `depth_anything_video` (`--colormap grayscale --variant VDA-Large`).
2. **ELSE IF building a complex/impossible 3D trajectory from scratch** (flythrough through doorways, tight multi-angle architectural orbit, custom handheld path that text prompts distort) → **Web `3D Jutsu` (Desktop + Smartphone QR Virtual Camera) → Video Render:**
   - Stage the 3D set on desktop in Higgsfield **`3D Jutsu`** (proxy geometry or generated 3D assets, `Look at` target, focal length/FOV), OR **scan the on-screen QR code with a smartphone** to use the phone as a real-time 6DoF virtual camera rig recording authentic handheld, dolly, push-in, or orbit paths live inside the 3D scene.
   - Export the previz MP4 and pass it as `@Video1` into `seedance_2_5 --mode omni_reference` (or `hf_mult_motion_control_flash` / `hf_mult_motion_control` Genjutsu) with locked `R2`/`R3` image refs so final pixels inherit the exact 3D camera track 1:1.
3. **ELSE IF bridging two exact target compositions** (e.g. establishing wide → locked product/hero end-frame) → **Start + End Frame Interpolation:**
   - Generate matched `2k`/`4k` Start and End plates first (`3d_jutsu_angles`, Web `Angles` 360° swivel, or sliced `nano_banana_2_shots` tiles via `make slice-grid`).
   - Animate with `--start_image` + `--end_image` via CLI (`seedance_2_5`, `kling4_0`, `kling_o3_flf`, `wan3_0`, `cinematic_studio_video_4_0`; check [Live Workflows](../../higgsfield-cli/references/live-workflows.md) for FLF CEL rules) or in Web Cinema Studio by switching the Video model to **`Kling 3.0`** (Web CS 4.0 omits the `Start/End Frame` control). Keep physical distance traversable within clip duration and match camera verb to the real 3D perspective shift.
4. **ELSE IF delivering 2–6 cohesive cuts inside ONE shared location** → **Native Multi-Shot:**
   - Use native CLI `--multi_shots` engines—`kling_o3_image_reference` (`--multi_shots true --multi_prompt [...]`), `kling_o3_flf` (`--multi_shots true`), `cinematic_studio_video_v2`, `cinematic_studio_video_3_5`, or `cinematic_studio_3_0` (`--multi_shots true --multi_shot_mode auto|custom`)—OR timecoded multi-shot blocks on `seedance_2_5 --mode omni_reference` (e.g. `6s` paired `3s + HARD CUT + 3s` blocks or `20–30s` sequences; see [Prompt Patterns](prompt-patterns.md)) so shared latent space preserves grain, exposure, lighting, walls, and wardrobe across cuts. *(Note: in live CLI `1.2.3`, `kling4_0` has **no** `multi_shots`/`multi_prompt` parameters—route multi-shot Kling cuts via `kling_o3_*` or `cinematic_studio_video_v2`.)*
5. **ELSE IF needing deterministic optical gear, stylized camera presets, `camera_style`, `speedramp`, or social hypermotion templates** → **Cinema Studio / Hypermotion Family:**
   - **Web Cinema Studio 4.0 Video Director's Panel (`https://higgsfield.ai/cinema-studio`, `/generate` Video mode):** Rebuilt video optics wheels—`CAMERA` (`Auto`, `Modern`, `35mm Film`, `8mm Film`, `DV Camcorder`), `LENS` (`Auto`, `Clean Sharp`, `Anamorphic`, `Vintage Anamorphic`, `Warm Vintage`, `Halation Vintage`), and `APERTURE` (`Auto`, `f/1.4 Wide Open`, `f/4 Moderate`, `f/11 Deep Focus`)—paired with `References (0/50)`, `Film setup` (`Genre` / `Era` / `Tempo`), `Color palette`, `Lighting`, `Elements`, and a flat list of **33 `#` camera movement presets** (no category tabs; e.g., `#Robo Arm`, `#Lazy Susan`, `#Through Object In/Out`). **Web UI boundaries:** `Start/End Frame` appears only when switching Video model to **`Kling 3.0`** (use CLI `seedance_2_5` / `kling4_0` / `kling_o3_flf` for FLF), **`Extend Video`** lives on a separate tab at `/ai/video` (CLI: `seedance_2_5 --mode video_extension`), **`Emotion Wheel`** is not present in CS 4.0, and **`Storyboard`** is separate (`Popcorn` `/storyboard-generator`). *(CLI boundary: opaque preset UUIDs are absent from `preset list`—configure once in Web and extract via `higgsfield generate get <id> --json` into [`docs/cinema-presets.json`](../../../../docs/cinema-presets.example.json) shape, or leave `Auto` and describe optics in prose.)*
   - **Cinema Studio Image (`cinematic_studio_image`) / earlier 1.0–2.0 camera racks:** Distinct from the 4.0 Video Panel—exposes named physical brand camera bodies (`ARRI Alexa 35`, `RED V-Raptor`, `Sony Venice`, `IMAX`, `Panavision`, `Arriflex 16SR`), named cinema lenses, and explicit focal length (`camera_focal_length_id`) for `R3` still locks.
   - **CLI Cinema Studio 3.5 (`cinematic_studio_video_3_5`):** Explicit CLI `--camera_style` (9 styles in Section 4B), `--light_scheme` (`soft_cross|contre_jour|overhead_fall|window|practicals|silhouette`), and `--color_grading` (`naturalistic_clean|bleached_warm|hyper_neon|teal_orange_epic|sodium_decay|cold_steel|bleach_bypass|classic_bw`). *(Verify mandatory `--duration` and `--prompt_language` defaults and CEL exclusions in [Live Workflows](../../higgsfield-cli/references/live-workflows.md).)*
   - **CLI Cinema Studio 3.0 / V2 (`cinematic_studio_3_0`, `cinematic_studio_video_v2`):** Explicit CLI `--speedramp` (Section 4C), native `--multi_shots`, or `4k` output (`3_0`). *(Check `prompt_language` defaults in [Live Workflows](../../higgsfield-cli/references/live-workflows.md).)*
   - **Social / Product Hypermotion (`marketing_studio_v2_video --type hypermotion`):** One-tap kinetic product/social camera templates discoverable via `higgsfield preset list marketing-studio-v2 --type hypermotion` (see [Live Workflows](../../higgsfield-cli/references/live-workflows.md) for `input_images` and `style_id`/`preset_id` CEL rules).
6. **ELSE IF directing a single-object trajectory or simple 2D sweep visually without prose ambiguity** → **Draw To Video (`draw_to_video`):**
   - Draw minimal, short, non-overlapping arrows on the sketch (single arrow on object = local motion; parallel canvas arrows = pan/track; radial outward arrows = zoom) and pair with concise style/atmosphere text only (Zero Double-Command). *(CLI caveat: live CLI `draw_to_video` requires `--video` alongside `== 1` sketch in `image_references` and `--prompt`—see [Live Workflows](../../higgsfield-cli/references/live-workflows.md); use Web Draw To Video when driving from a still sketch alone.)*
7. **ELSE (default for ~70% of commercial shots: clean single-move narrative or product beat)** → **Locked `R3` Keyframe + I2V Delta Prompt:**
   - Route per [Model Selection](../../higgsfield-cli/references/model-selection.md): verified `0 cr.` Web `Unlimited` (confirm CTA button itself flips to `Unlimited`) → economy `720p` draft (`seedance_2_0_mini`, `kling_4_0_flash`, `wan3_0`) or `seedance_2_5 --draft true` (for 1:1 `--draft_job_id` escalation) → native `1080p` master (`kling4_0 --duration 5`, `wan3_0`, `veo3_1`, `seedance_2_5 --draft_job_id --bitrate_mode high`, `cinematic_studio_video_4_0 --bitrate_mode high`). For zero-actor abstract spots, sub-0.5s `2K` still montages, and pixel-locked living stills, see [Motion & Abstract Direction](motion-and-abstract.md).
8. **Post-generation aspect-ratio adaptation or pan cleanup (only on already-locked clips):**
   - **`reframe` (`--workflow`):** Adapts a finalized clip across `16:9` / `9:16` / `21:9` / `1:1` without re-rolling action. Generate in the target ratio or `outpaint` stills pre-video whenever possible; reserve `reframe` strictly for second-ratio delivery of an irreplaceable master (see [Model Selection](../../higgsfield-cli/references/model-selection.md) and [Live Workflows](../../higgsfield-cli/references/live-workflows.md)).
   - **`video_deflicker` / `fps_boost`:** Use `video_deflicker` on clean native clips with mild lighting/texture shimmer; avoid `fps_boost` on fast hands, hair, or fabric snaps (optical-flow ghosting).

## 3. Optics Playbook (Lock Before Motion)

Keep all shots inside one location within **one coherent lens family** (`24–35mm` for wide/medium coverage, `50–85mm` for close-ups); unmotivated jumps from `14mm` to `85mm` break spatial realism.

### A. Focal Length × Diagonal FOV × Motion × Risk

On multi-shot / photochemical engines (`seedance_2_5`), pairing camera height with explicit **diagonal FOV degrees** (`84° / 47° / 29° / 18°`) locks optical perspective and compression far more reliably than vague labels (`wide`, `close-up`):

| Focal Length | Diagonal FOV (35mm FF) | Optical & Psychological Effect | Best Camera Moves | Failure Risk |
| :--- | :--- | :--- | :--- | :--- |
| **Ultra-Wide (`8–14mm`)** | `114°–140°` | Exaggerated foreground scale, edge distortion, frantic energy / claustrophobia | `FPV Drone`, `Snorricam`, `Crash Zoom`, aggressive POV tracking | Corner wall bending; avoid on calm human portraits |
| **Wide (`18–24mm`)** | **`~84°`** (`24mm`) | Strong 3D parallax, readable geography, immersive action inside the space | `Dolly In/Out`, `Truck`, `Crane Up/Down`, dynamic handheld | Tilted horizon if `horizon level` is omitted |
| **Classic Cinema (`35mm`)** | `~63°` | Natural human field of view, grounded presence in room | `Slow Dolly`, `Lateral Track`, `Handheld` (`intimate_observer`), `Static` | **Lowest artifact risk**—default workhorse for AI video |
| **Standard (`50mm`)** | **`~47°`** | Undistorted faces, gentle compression, physical blocking & unbroken one-takes | `Slow Push-In`, `Locked-off Tripod`, `45–90° Arc`, continuous handheld | Default for dialogue, two-shots, OTS, and tabletop product shots |
| **Short Tele (`75–85mm`)** | **`~29°`** (`85mm`) | Tight detail / tactile inserts (hands, props, eyes) with strong subject isolation | `Locked-off Tripod`, reactive handheld inserts, micro-`Dolly In` | **High warp risk on fast pans/orbits** (shallow DOF + compression tears background) |
| **Telephoto ECU (`135mm`)** | **`~18°`** | Intense frontal extreme close-up (forehead/chin near frame edges) & window-glass POV compression | Held reactive handheld, subtle breathing sway, deliberate focus slip | Extreme shake magnification; keep subject movement small |

### B. Aperture (`f/`-Stop) as Stability Lever

- **`f/1.4` (Wide Open):** Extreme shallow DOF and creamy bokeh; hides distant background micro-shimmer on portraits, but focus plane can breathe during complex camera travel.
- **`f/4` (Moderate — default):** Crisp subject with legible, non-distracting environment; best balance for 70% of narrative and commercial shots.
- **`f/11` (Deep Focus):** Front-to-back sharpness; required for complex tracking shots, `Crane`/`Helicopter`, architecture, and two-plane staging where background detail must stay solid.

### C. Cinema Studio 4.0 Video Panel vs. Image / Brand Camera Racks

Keep the two optics paradigms distinct so Web UI selections match real controls while `R3` stills and prose keep full focal specificity:

- **Cinema Studio 4.0 Video Director's Panel:** `CAMERA` (`Auto` + 4 format bodies: `Modern`, `35mm Film`, `8mm Film`, `DV Camcorder`) × `LENS` (`Auto` + 5 lens characters: `Clean Sharp`, `Anamorphic`, `Vintage Anamorphic`, `Warm Vintage`, `Halation Vintage`) × `APERTURE` (`Auto` + `f/1.4 Wide Open`, `f/4 Moderate`, `f/11 Deep Focus`). No brand-camera dropdown or separate focal-length selector on Video 4.0—lock focal length (`24mm`–`135mm`) in the `R3` still or prompt text.
- **Cinema Studio Image (`cinematic_studio_image`) & earlier 1.0–2.0 camera racks:** Named physical brand bodies (`ARRI Alexa 35`, `RED V-Raptor`, `Sony Venice`, `IMAX`, `Panavision`, `Arriflex 16SR`), named cinema glass (`ARRI Signature Prime`, `Hawk V-Lite`, `Cooke`, `Helios`, `Panavision Spherical`), plus explicit focal length (`camera_focal_length_id`).

| Visual Goal | CS 4.0 Video Panel (`Format / Lens / Aperture`) | CS Image / Prose Optics (`Brand Body / Glass / Focal`) | Motion Pairing |
| :--- | :--- | :--- | :--- |
| **Commercial Macro / Product Hero** | `Modern` · `Clean Sharp` · `f/4` | `ARRI Alexa 35` · `ARRI Signature Prime` · `50mm` | `Locked-off` or `Slow Dolly In` (`#Robo Arm` / `#Lazy Susan`) |
| **Gritty Urban Night / Action** | `Modern` or `35mm Film` · `Anamorphic` · `f/1.4` | `RED V-Raptor` or `Sony Venice` · `Hawk V-Lite` · `35–50mm` | `Tracking` or `Handheld` (`documentary_snap`) |
| **Intimate Portrait / Memory** | `35mm Film` (or `8mm Film`) · `Warm Vintage` or `Halation Vintage` · `f/1.4` | `Arriflex 16SR` / `35mm` · `Cooke` or `Helios` · `75–85mm` | `intimate_observer` or subtle `Slow Push-In` |
| **Raw Camcorder / Archival POV** | `DV Camcorder` · `Vintage Anamorphic` or `Clean Sharp` · `f/4–f/11` | `Arriflex 16SR` / handheld DV · `24–35mm` | Reactive handheld or `documentary_snap` |
| **Epic Landscape / World-Building** | `Modern` or `35mm Film` · `Clean Sharp` · `f/11` | `IMAX` / `Panavision` · `Panavision Spherical` · `18–24mm` | `Crane Up` or `Helicopter Shot` |

*(Pairing `35mm Film`/`8mm Film` or Era `1970s–1990s` in Cinema Studio introduces natural organic grain that masks subtle diffusion micro-artifacts better than sterile high-gloss digital presets.)*

## 4. Moves, Rigs, `camera_style`, Speedramps & Transitions

### A. Motivated Move Matrix & Special Rigs

| Move / Rig | Narrative / Commercial Job | Preconditions for Clean Execution |
| :--- | :--- | :--- |
| **`Locked-off static tripod`** | Product legibility, deadpan timing, letting in-frame acting carry the beat | Default whenever subject motion already fills the frame; state explicitly |
| **`Reactive "Slightly Late" Handheld`** | Grounded documentary/cinema tactility (following a hand pick-up or glance) | Direct handheld that settles with and rises *slightly late* behind the gesture (never sterile gimbal perfection); pair with a **locked focus plane** (`no rack focus`) on shallow-DOF `85mm` foreground-prop + sharp-eyes two-plane shots |
| **`Slow Dolly In` / `Out`** | Intimacy, tension, realization (`In`); context reveal, solitude (`Out`) | `35–50mm`, calm pace; add `eases smoothly into a gentle hold` to avoid abrupt clip stops |
| **`Lateral Truck` / `Tracking`** | Spatial reveal past foreground occlusion; pacing alongside a walking subject | Match camera speed to subject stride; keep foreground occluders simple |
| **`45–90° Arc` vs. `360 Orbit`** | Hero product or fashion showcase | **Prefer `45–90° Arc`** in 5s over full `360 Orbit` (360° forces rapid unobserved-back hallucination unless anchored via `3D Jutsu` or multi-angle `R2` plates) |
| **`Crane Up/Down` / `Pedestal`** | Clearing foreground surfaces; shifting between intimate detail and room/site scale | `18–35mm`, `f/4–f/11`, explicit `horizon level` |
| **`Robo Arm` (Bolt/KUKA)** | High-precision luxury product whip/stop trajectories | Clean studio/uncluttered backdrop; single hero object; use Cinema Studio preset |
| **`FPV Drone` / `Helicopter`** | High-energy spatial opener or architectural flythrough | `14–24mm`, `f/11`; use `3D Jutsu` previz whenever threading tight openings |
| **`Snorricam`** | Panic, disorientation, claustrophobic subjective intensity | Wide lens (`14–24mm`), face anchored centered, clear separation between actor and background |
| **`Bullet Time` / `Dolly Zoom`** | Stylized time-freeze showcase / sudden psychological dread (Vertigo) | Stationary or slow-mo hero subject; clean foreground/background depth separation; use native preset rather than prose alone |
| **`Crash Zoom` / `Whip Pan` / `Dutch Angle`** | 0–2s hook, comedic punch, kinetic cut, or visual unease | Keep duration tight; plan cut point at peak blur for `Whip Pan` |
| **`Push to Glass` / `Head Tracking`** | Barrier-crossing scene reveal / locked subject-centered action follow | Keep barrier surface simple (`Push to Glass`); use `Head Tracking` on uncluttered backgrounds to avoid edge smearing |

#### Physical Handheld Operator & Continuous One-Take Protocol (Anti-Gimbal Realism)

Plain `"handheld"` is routinely smoothed into floaty AI gimbal drift. For true documentary/cinema handheld (especially on `seedance_2_5` `20–30s` scenes):
1. **Explicit Operator Physics Block:** Lead the prompt with physical forces (operator's hands, breathing, weight shifts, uneven footsteps, irregular jolts, sway, bounce, overshoot & snap-back) paired with a hard anti-stabilization guardrail: `NEVER smooth, NEVER gimbal, NEVER stabilised, NEVER a tripod, NEVER a static hold`.
   - *Outdoor / high-emotion scenes:* allow `sudden rolls` and environmental buffeting (`a strong gust knocks the framing briefly sideways; the operator recovers without an edit`).
   - *Calm interior / architectural scenes:* append `Keep the horizon level and architectural verticals upright. No camera roll or Dutch angles.`
2. **Reactive Lag & Imperfect Focus:** Direct the camera as a human operator reacting a beat *after* the actor—never predicting the choreography (`the operator takes two uneven steps, overshoots the running child, and snaps back`; `pans left slightly lagging behind her gaze`; `focus slips briefly past the lashes and finds the iris again`).
3. **Physical Relocation & 180° Axis Lock (One-Takes & Multi-Shot):** State `Changes in framing come from physical camera movement; the camera never passes through windows, walls, or bodies` (forbid unmotivated push-ins/zooms). Pin one side of the axis (`Keep all camera positions on her right side of the axis`) and forbid mirroring (`Achieve the opposite profile by camera placement, never by horizontally mirroring the image or architecture`).

### B. Live CLI `--camera_style` (`cinematic_studio_video_3_5`)

Use only when `style_prompt` is omitted (CEL mutually exclusive):
- `classic_static` — rigid tripod stillness.
- `silent_machine` — clinical, motorized, zero-jitter tracking (thriller, tech, architecture).
- `one_take` — unbroken single-shot continuity across movement.
- `epic_scale` — sweeping, grand-scale establishing moves.
- `intimate_observer` — subtle, restrained human handheld for drama and dialogue.
- `impossible_camera` — non-physical virtual trajectories (threading tight gaps/surfaces).
- `documentary_snap` — reactive real-time handheld energy.
- `raw_chaos` — frantic, high-energy handheld action.
- `dreamy_flow` — floating, slowed, lyrical drift.

### C. Live CLI `--speedramp` (`cinematic_studio_3_0` vs. `cinematic_studio_video_v2`)

- **`cinematic_studio_3_0` enums:** `auto`, `linear`, `slowmo`, `super_slowmo`, `speedup`, `fast_to_slowmo` (hero impact/pour climax), `slowmo_to_fast`, `impact` (kinetic contact accent).
- **`cinematic_studio_video_v2` enums:** `auto`, `custom`, `linear`, `slowmo`, `speedup`, `impact`. *(Web Cinema Studio also exposes `Flash In`, `Flash Out`, `Bullet Time`, and `Ramp Up`.)*

### D. In-Camera Transitions (Zero Post `xfade` Band-Aids)

- **Whip Pan Bridge:** End Shot A with `fast whip pan right into heavy horizontal motion blur`; open Shot B with `fast whip pan arriving from the left, settling smoothly onto <subject>`. Cut cleanly on 2–3 peak-blur frames.
- **Foreground Wipe / `#Through Object In/Out`:** Track Shot A laterally behind a dark vertical occluder (pillar, doorway frame) or pass through a clean geometric aperture (`#Through Object In/Out`) until frame fills; emerge Shot B in the same direction from a matching edge.
- **Match-on-Direction & Abstract Match Cuts:** Pair equal-velocity moves (`slow dolly-in` → `slow dolly-in` closer scale) respecting the `180°` axis and `30°` scale/angle shift. For zero-actor silhouette match cuts (`±5%` centroid/diameter), sub-0.5s `2K` still montages, and pixel-locked finish swaps, see [Motion & Abstract Direction](motion-and-abstract.md).

## 5. Execution Rules & Engine Calibration

- **Speed Contrast Law:** Never pair a sprinting/explosive subject with fast multi-axis camera travel over a high-frequency background. Contrast states: stationary subject + expressive camera, OR dynamic subject (counted mechanical steps, `1–2` beats per 5s) + locked tripod or pace-matched tracking.
- **Gaze Anchor & Horizon Lock:** Include an explicit **Gaze Anchor** on every non-UGC human shot (`eyes focused down on the clasp, never looking at the camera`) so camera motion never triggers vlog-style lens stare. Add `tripod fixed, horizon level` on pans, tilts, trucks, and pedestals.
- **Optimal Video Reference Budget (`2–4` Visible Refs, max `5`):** Exceeding `5` image references freezes optical flow into a stiff "living photo" and bleeds pigments. Bind `1` `R3` `--start_image` + `1–2` highest-risk canonical `R2` refs + optional `1` `--end_image`, and pre-lock a **Reverse Wall plate** (`3d_jutsu_angles`) for any OTS, 180° reverse, or mirror shot ([Locations, Buildings & Props](../../video-consistency/references/locations-and-props.md)).
- **Camera-First Engine Strengths** *(word sweet spots in [Model Prompting](model-prompting.md); pricing & CEL traps in [Model Selection](../../higgsfield-cli/references/model-selection.md) and [Live Workflows](../../higgsfield-cli/references/live-workflows.md))*:
  - **`seedance_2_5`:** 1:1 draft-to-final camera lock (`--draft true` → `--draft_job_id --bitrate_mode high`), paired `3s + HARD CUT + 3s` blocks, `3D Jutsu` `@Video1` tracking, and `video_extension` (`forward`/`backward`).
  - **`cinematic_studio_video_4_0`:** Web Director's Panel optics + 33 flat `#` presets, `References (0/50)`, and native diegetic foley (`--bitrate_mode high`; Web `Start/End` requires switching to `Kling 3.0`, and `Extend Video` lives on `/ai/video`).
  - **`kling4_0`:** Native `1080p`/`4k` (`sdr`/`hdr`), action physics, up to 10 refs, and `video-edit` motion-locked rescues *(no CLI `--multi_shots`; verify explicit `--duration` in [Live Workflows](../../higgsfield-cli/references/live-workflows.md))*.
  - **`kling_o3_image_reference` / `kling_o3_flf` / `cinematic_studio_video_v2`:** Native CLI `--multi_shots true` shared-set cuts (`cinematic_studio_video_v2` adds `--speedramp` and `kling_element_ids`).
  - **`veo3_1`:** Atmospheric light, natural shallow DOF, and smooth single-subject cinema glides.
  - **`wan3_0` / `wan3_0_prime`:** Natural fabric/water/light physics on calm single-frame takes *(verify FPS—may output `30fps`)*.
  - **`minimax_h3`:** Facial likeness retention on calm pushes (strict One-Move Rule + Gaze Anchor).
  - **`flux_3_video`:** Crisp editorial color grade on calm fashion/product takes.
- **Cheap Trajectory Validation & Full-Clip Review:** Validate camera path first on verified Web `Unlimited` (`0 cr.`, CTA confirmed) or cheap `720p` / `--draft true` runs. Inspect the **entire clip** (start, middle, end—check frame edges for wobble/shimmer, not just Frame 1). Generate 1–2s handles when pacing allows so post assembly can trim weak tails. Change **One Variable Per Re-roll** on retries.

## 6. Camera Failure Diagnostics

| Observed Camera Defect | Root Cause | Exact Fix (One Variable Per Re-roll) |
| :--- | :--- | :--- |
| **Unwanted floating drift on static shot** | Camera behavior omitted from prompt/preset | Add `Locked-off static tripod shot, horizon level` or select `Static` / `classic_static` |
| **Floaty / over-stabilized "AI gimbal" when handheld was asked** | Vague `"handheld"` text ignored by model | Replace with Physical Handheld Operator Block (breathing, weight shifts, overshoot/snap-back, `NEVER smooth, NEVER gimbal, NEVER stabilised`) + reactive lag beats |
| **Rubber-bending walls or floor warp** | `Pan`/`Zoom` used for 3D parallax OR `Start → End` jump exceeds 5s | Switch verb to `Lateral truck` / `Slow dolly-in`, shorten spatial delta, or route via `3D Jutsu` previz |
| **Camera ignores text or jitters violently** | Active UI preset / `--camera_style` / `@Video1` conflicts with prose camera verbs | Enforce **Zero Double-Command**—remove camera verbs from prose and keep prompt within model word sweet spot |
| **Stiff "living photo" (frozen camera)** | Reference overload (`> 5` images) or static scene restated in motion text | Prune to `2–4` visible refs and strip all static wardrobe/set description from video prompt |
| **Pan edge shimmer / strobe on brick, leaves, or mesh** | Fast pan over high-frequency pattern at `f/11` or FPS mismatch | Slow move (`Calm`), widen aperture (`f/2.8–f/4`), verify `24fps` parity, or run `video_deflicker` on clean native output |
| **Abrupt halt or speed jerk at end of clip** | Unbuffered trajectory hitting 5s boundary | Add easing (`eases smoothly into a gentle hold`), apply `--speedramp fast_to_slowmo`, or trim 0.5–1s tail in assembly |
| **Subject stares at lens during orbit/dolly** | Missing eyeline anchor | Add explicit **Gaze Anchor** (`eyes fixed on <object>, never looking at the camera`) |
| **Great camera move, but 1 prop/object morphs** | Diffusion drift on moving detail | Keep the golden camera take—rescue surgically via `hf_mult_replace_object_flash` (`1080p`) / `hf_mult_replace_object` (Genjutsu) or `kling4_0 --mode video-edit --duration 5` |
| **Reverse shot flips room 180°** | Missing Reverse Wall plate or camera-relative left/right text | Lock Reverse Wall (`3d_jutsu_angles`) from `N/E/S/W` map and re-stage `R3` still |

*Done when:* every shot is routed through Section 2's top matching camera tool, locks optics inside one coherent lens family in `R3`, obeys the One-Move Rule and Zero Double-Command, keeps `2–4` visible refs with explicit Gaze Anchor and parallax-accurate verbs, and passes full-clip edge-stability review before native `1080p` mastering.

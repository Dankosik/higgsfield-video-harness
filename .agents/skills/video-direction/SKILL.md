---
name: video-direction
description: "Video/still prompt craft, optics, and camera control grounded in Taste Memory. Use when writing Lookbook, still, or motion prompts, choosing optics or camera tools/rigs/speedramps, calibrating per model, fixing prompt/camera defects, or writing anti-IP/VO copy."
---

# Video Direction

Canonical owner of Taste-Memory-grounded still/video prompting, optics, camera
control, native audio/dialogue directives, anti-IP rewrites, and prompt-level
failure diagnostics.

## Reference Map

Load only the reference needed for the current task:

| Need | Reference |
| --- | --- |
| Observable proxies, `taste-log.md` translation, `%` Palette Lock, Room-Light Integration & Photochemical Lookblock, `R2`/`R3`/`R4`/`R5` blueprints (I2V, Start+End, Omni-Ref, T2V, Multi-Shot, `6s` 2-Shot, `20–30s` Photochemical Multi-Shot/One-Take), Camera Grammar, 4-part lighting, Anti-IP & Phonetic VO | [`references/prompt-patterns.md`](references/prompt-patterns.md) |
| 8-branch Higgsfield camera tool routing, optics & diagonal FOV playbook (`84°/47°/29°/18°`), physical handheld operator & one-take protocol, rigs/moves, CLI `camera_style`/`speedramp` enums, in-camera transitions & camera failure diagnostics | [`references/camera-control.md`](references/camera-control.md) |
| Model-by-model word sweet spots & syntax, language/negation rules, `CRITICAL CORRECTION` retries & prompt/audio/IP failure diagnostics | [`references/model-prompting.md`](references/model-prompting.md) |
| Optional ultra-lean stylized `720p High` `12–20s` multi-shot `Seedance 2.5` spec pipeline (`PARAMS {}`, HEX palette, `LOCK MANIFEST`, `中文强制锁定`) | [`references/seedance-spec-case-study.md`](references/seedance-spec-case-study.md) |

## Core Direction Laws

- **Taste Memory & observable captioner prose:** Read `campaigns/<slug>/taste-log.md`
  (and `brands/<brand>/taste.md`) before drafting; honor every `LOCKED` anchor.
  Write concise, chronological, **present-tense English** describing only what
  the lens sees and the mic hears (keep spoken dialogue in its target language).
  Replace buzzwords (`cinematic`, `photorealistic`, `4k`) and internal emotions
  with observable physical proxies (posture, grip, gaze, material finish, 4-part
  motivated lighting). State every `Never` rule as its positive physical
  opposite. On multi-shot stills, lock a **Percentage Palette** (`45% / 35% / 20%`,
  stated first and echoed in the tech tail); on multi-ref composites, specify
  **Room-Light Integration** (surface bounce, lens-to-subject haze with lifted
  blacks, ambient room tint on skin, zero fake rim/key on documentary scenes).
- **True `R2` Lookbook contrast (`A / B / C`):** Hold brand and product
  invariants fixed while varying orthogonal visual axes (lighting temperature/mood,
  material finish, camera distance, architectural backdrop) — never synonym
  paraphrases.
- **Statics vs. motion separation (`R3` → `R4`/`R5`):** Lock composition, lens
  feel, lighting direction, wardrobe, architecture, and product geometry in
  `R3` stills (fix still flaws before animating). Map `storyboard.md` `Start frame`
  → `R3` still, `Action` → `R4`/`R5` motion prompt, `End frame` → `--end_image`
  or next-shot handoff:
  - **I2V (`--start_image`):** write **temporal delta only** (action, secondary
    physics, camera move, diegetic audio); use short functional nouns (`the woman`,
    `the bag`) without restating face, wardrobe, or room layout.
  - **Start + End (`--start_image` + `--end_image`):** keep distance physically
    traversable inside clip duration and match camera verb to the real 3D
    perspective shift.
  - **Omni-Reference / Multi-Ref:** assign one explicit role per `@ImageN` /
    `@VideoN` / `@AudioN` inside [`video-consistency`](../video-consistency/SKILL.md)'s
    visible-only reference budget.
- **Beat budget, physical mechanics & Gaze Anchor:** One primary subject per
  shot; **1–2 concrete physical beats per 5s** (`2–3` per `8–10s`) with counted
  steps and secondary physics (weight, resistance, cloth inertia, ambient drift).
  State an explicit **Gaze Anchor** on every non-UGC human shot (`eyes focused
  down on the clasp, never looking at the camera`). Use continuous prose for
  slow performance, timestamped micro-beats (`0-2s`, `2-5s`) for timed stages,
  and `[MASTER PROMPT]` + `[SHOT 1..N]` only on native multi-shot engines.
- **Camera control, optics & narrative motivation:** Route every shot through
  [`references/camera-control.md`](references/camera-control.md) and align
  framing, camera stillness vs. movement, lighting shifts, and `0.1s` hero
  object silhouettes to each shot's **`Narrative job`**
  ([`video-narrative`](../video-narrative/SKILL.md)). Keep one coherent lens
  family per set (`24–35mm` wide/medium, `50–85mm` close-ups), direct **one
  dominant camera move per shot** (state `Locked-off static tripod shot,
  horizon level` whenever stillness or a proof/swap turn carries the meaning),
  obey **Zero Double-Command** (omit prose camera verbs when a UI preset,
  `--camera_style`, `--speedramp`, or `@Video` owns motion), and distinguish 3D
  translation (`Dolly`, `Truck`, `Crane`) from nodal/optical moves (`Zoom`,
  `Pan`, `Tilt`).
- **Production & Prompt Architecture (choose 1 in `R1B`):**
  1. **Commercial Hybrid (default 15–30s spots):** delta-only prose tuned to
     each engine's word sweet spot (`references/model-prompting.md`).
  2. **Cinema Spec (`Seedream 5.0 Pro` + `Seedance 2.5` `6s` 2-shot pairs):**
     structured labeled prose (`REFERENCE ROLES`, `LIGHT INTEGRATION`, `SHOT A`
     / `HARD CUT` / `SHOT B`, numbered `AUDIO`, closing `POSITIVE CONSTRAINTS`,
     inline `CRITICAL CORRECTION` on `v2+` — `references/prompt-patterns.md`).
  3. **Ultra-Lean Stylized Multi-Shot (optional `12–20s` `720p High` shorts):**
     modular `PARAMS {}`, `HEX` palette, `LOCK MANIFEST`, optional `中文强制锁定`
     (`references/seedance-spec-case-study.md`).
  *(Use JSON only as an internal pipeline checklist, never as raw video-model syntax.)*
- **Native audio, smart lip-sync vs. off-screen VO routing, anti-subtitle dialogue & read-aloud budget:**
  Tie every sound to a visible source + room tone, and end every non-UGC video
  prompt with the literal line `"NO MUSIC. NO BACKGROUND SCORE. Native diegetic
  sound only."`. Match mouth direction to the shot's audio mode:
  1. **Silent character under off-screen VO / narrator / inner monologue / B-roll:**
     silent I2V (`--sound off`) is completely valid—explicitly direct natural
     non-speaking expressions (*mouth closed, listening, smiling, reacting, zero
     accidental talking or jaw movement*).
  2. **Visible on-camera speaker (`MCU`/`CU` delivering the line directly):**
     avoid pasting external VO onto silent un-synced jaw-flapping—route to
     audio-driven lip-sync (`intone` / Lipsync Studio) or native in-model speech
     (`Character says in natural Russian, low calm voice: ...` + `No subtitles,
     no captions, no on-screen text.`).
  3. **Multi-character shots:** explicitly keep the **silent listener's mouth
     closed** so the wrong character never moves its mouth while another speaks.
  Enforce `ad-script`'s **read-aloud budget**
  ([Ad Craft Glossary](../../../docs/ad-craft-glossary.md): `<= 2.0 wps`
  Russian, `<= 2.3 wps` English after subtracting `[PAUSE Ns]`) and spell brand
  names phonetically in VO prompts.
- **Anti-IP, typography & One Variable Per Re-roll:** Decompose IP/brands/directors
  into raw materials, silhouette, geometry, and light. Composite fine typography
  and UI in post. On `ITERATING` retries (`v1 -> v2`), change **one failing axis
  only** using [`references/model-prompting.md`](references/model-prompting.md#symptom-to-fix-prompt-diagnostics).

*Done when:* every prompt honors active `taste-log.md` and `LOCKED` anchors,
fits the target engine's word and beat budgets, keeps statics out of I2V delta
text, declares camera/gaze/audio explicitly, and passes anti-IP and read-aloud
checks.

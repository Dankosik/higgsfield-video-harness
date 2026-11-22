---
name: hybrid-motion-graphics
description: "Hybrid AI + code/NLE launch films, SaaS demos, kinetic typography, HTML design sheets, 9-frame storyboards, BPM timelines, and tracked post-production cleanup. Use when building launch videos, UI/SaaS motion graphics, or precision brand overlays."
---

# Hybrid Motion Graphics & Launch Films (`hybrid_motion_launch`)

Canonical workflow for combining **Higgsfield AI visuals** with **editable code
or NLE motion layers** (Remotion, After Effects JSX, Blender Cycles, or Claude
Code) so typography, UI, cursors, and brand logos stay razor-sharp.

## 1. Upfront Gates Before Video Spend (`R1B` -> `R2`)

1. **HTML Design Sheet First:** When a spot uses kinetic typography, UI cards,
   or motion overlays over talking-head footage, author the typography/color
   design sheet in **HTML** first — fonts, weights, and layout tokens survive
   transfer far better than text guesses.
2. **9-Frame Storyboard Gate (`marketing_studio_image`):** Generate a cheap
   9-frame visual storyboard first to lock layout, framing, and brand palette
   before generating full video.
3. **Object Prep & Audio-First Gates:**
   - *3D product launch films:* Lock full rigged geometry + final studio stills
     before any camera animation; extract exact music `BPM` and hit timestamps
     first (`ElevenLabs Music v2.5`), and extend music by **repeating whole
     beats on-beat** if edits add frames (never regenerate the score).
   - *Explainers / dialogue motion:* Generate and measure real voice take
     durations **before** keyframing animation; regenerate overflowing takes.

## 2. Strict Layer Separation & Shared Timeline

- **Code/NLE owns text, UI & graphics; AI owns clean-background footage:**
  Keep UI windows, cursors, HUD tracking markers, callouts, and kinetic type in
  editable code (Remotion / AE native Shape Layers + live text), and keep
  Higgsfield assets minimal on plain/transparent backgrounds (genuine alpha or
  `#000000`) on separate layers.
- **Single-Variable Accent & Shared Clock:** Store the brand accent color in
  one shared variable across 3D/2D layers. Compute all cut boundaries from
  **absolute musical time (`BPM`)** rounded once to the nearest frame — never
  accumulate per-scene rounding drift.
- **3-Role Isolation for Motion Over Real Footage (`minimax_h3_max` / post):**
  - `Video 1` = identity, wardrobe, room, lighting, lens only.
  - `Audio 1` = voice timbre only (`Do NOT reuse original speech or timing`).
  - `Image 1` / HTML sheet = graphic design tokens only (`never copy layout or
    background`).
- **On-Screen Typography Hygiene (`TEXT LOCK`):** Whenever text must render
  inside a video model (`marketing_studio_video` / `minimax_h3`), list every
  exact quoted string in order, lock one geometric font, forbid translation,
  paraphrasing, watermarks, or jitter/boil, keep headlines flat in screen space
  (never covering eyes/mouth), and **freeze the final `1.2–2.0s`** cleanly on
  the CTA (`END IMAGE` lock + `PERSISTENCE LOCK`).

## 3. High-Leverage Post-Production Patterns

- **3D & Render-Pass FX:** For Blender Cycles launch films, render **depth**,
  **part-ID**, and **temperature** passes alongside beauty frames so late HUD,
  tracking-marker, or thermal notes run purely in compositing without 3D
  re-animation. Put title words as real 3D scene geometry (or anamorphic Z-cut
  slices) so they inherit real light and DOF.
- **Vector Redraw & ASCII Caching:** Never puppet-warp flat raster illustrations
  — redraw moving elements as native vector Shape Layers (`12 fps Posterize
  Time`), testing 1 character's contacts (hand/mouth/feet) before scaling. For
  ASCII effects, cache dual transparent PNG sequences (`main` + `bg`) in fixed
  grid cells with static-region flicker suppression.
- **Tracked Micro-Branding & Lens-Portal Transitions:** When a hero AI take has
  great motion but misses tiny engraved logos (e.g., eyewear temple mark), fix
  it via **tracked post compositing** rather than burning video re-rolls.
- **Fast Multi-Format & Localization:** Keep organized editable project bins
  (`SOURCE / AUDIO / HIGGSFIELD_ASSETS / CAPTIONS / CUTAWAYS / MASTER`),
  duplicate nested precomps to recompose `16:9 -> 9:16` (`~15 min`), and
  approve translated copy tables before regenerating localized voice/clips.
- **Post-LUT Compositing:** Export transparent overlays as `1080p` ProRes 4444
  and composite **after** creative LUT/grain via `assemble.sh --overlay`.

## 4. Remotion Sub-Flow Recipe (`sub_flows: ["remotion_overlays"]`)

**Mandatory read:** Whenever `brief.md` or `shotlist.json` declares
`sub_flows: ["remotion_overlays"]`, read this skill *before* coding or rendering
overlays. Use this plug-in sub-flow whenever a `scratch_cinema` or other primary
campaign needs animated brand logos, kinetic titles, callout badges, or custom
animated endcards embedded into the main video without switching the primary
track:

1. **Lock base cut timing first:** Build `draft_cut.mp4` or `video_only.mp4`
   (`R4B`/`R5`) so exact `fps_target`, resolution (`1920x1080` or `1080x1920`),
   and shot/VO hit timestamps are truth — never guess overlay timings.
2. **Design & code the transparent layer (Caption Pacing & Verbatim Sync Law):**
   Pull brand hex colors, fonts, and logo vectors from `brands/<brand>/brand.md`
   and `style-bible.md` (draft an HTML Design Sheet first when iterating
   typography). For Shorts/Reels subtitles and kinetic captions:
   - Keep **max `2–6` words (`<= 2` short lines)** per cue turning over every
     **`1.0–2.5s`** — NEVER park 3-line walls of text on screen for `5–9s`.
   - **Verbatim word-level sync:** align every cue strictly to the **actual
     spoken audio timestamps** (word-by-word or phrase-by-phrase measured from
     the audio waveform/ASR, never guessed from shot duration), matching spoken
     words verbatim. If a VO take has a mispronunciation or dropped word,
     regenerate that audio line instead of letting captions contradict speech.
   - Build the composition in **Remotion** (or native RGBA renderer) with
     transparent background, exact `fps_target`, `durationInFrames`, and mobile
     safe-zone margins (`y = 62–76%` in `9:16`, never covering faces/props).
3. **Render with true alpha into `media/work/`:** Export transparent `1080p`
   **ProRes 4444** (`--codec=prores --prores-profile=4444
   --pixel-format=yuva444p10le`, or a transparent PNG sequence if ProRes 4444 is
   unavailable) into `campaigns/<slug>/media/work/overlay.mov` (keep gigabyte
   intermediate renders in `media/work/`, never inside client `media/exports/`).
4. **Composite post-LUT & verify:** Run
   `make assemble CAMPAIGN=<slug> LUT=<grade.cube> GRAIN=4 OVERLAY=campaigns/<slug>/media/work/overlay.mov`
   so creative color grading never shifts brand hex colors, then verify exact
   brand color fidelity and phone-size legibility in `reviewer-agent`.

*Tool availability fallback:* Default to **HTML Design Sheet + Remotion /
browser-rendered RGBA PNG/MOV + `scripts/assemble.sh --overlay`** (zero
commercial NLE required). Use the After Effects JSX branch only when Adobe
After Effects is verified installed locally.

*Done when:* Design tokens and beat grid are locked before rendering, AI and
code/UI layers stay cleanly separated, overlays composite post-LUT, and final
MP4 passes `qa_media.py render` + mobile readability inspection.

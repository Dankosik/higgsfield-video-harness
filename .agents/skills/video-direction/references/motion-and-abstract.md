# Motion Design, Abstract Objects & Zero-Actor Commercials

Canonical direction playbook for **zero-actor product films, abstract sculptural motion, and Apple / OpenAI / SaaS launch aesthetics**. For live model quotes and CLI CEL/flag rules, cross-check [Model Selection](../../higgsfield-cli/references/model-selection.md) and [Live Workflows](../../higgsfield-cli/references/live-workflows.md); for finishing order and compositing tiers, see [Video Assembly](../../video-assembly/SKILL.md).

## 1. Physical Material Micro-Grammar & 4-Part Studio Lighting

Replace empty CGI buzzwords (`photorealistic`, `3D render`, `sleek`, `minimalist aesthetic`) with observable light-interaction prose, one directional motivated studio key, and a mirrored HEX Percentage Palette Lock.

### A. Material Micro-Grammar (Observable Light Interaction)

| Material Class | Positive Observable Micro-Grammar | Avoid (Failure Trigger) |
| :--- | :--- | :--- |
| **Optical borosilicate glass** | Thick architectural bevels, crisp internal specular refraction, clean liquid meniscus edge, sharp transparent rim catching directional key | *"Glowing glass"*, *"shimmering caustics on stone"* (hallucinates watery waves on opaque surfaces) |
| **Satin translucent polycarbonate / matte resin** | Soft subsurface edge scatter, gentle internal light diffusion, smooth bead-blasted matte sheen with broad low-contrast highlight roll-off | *"Plastic"*, *"shiny translucent"* (renders cheap wet acrylic glare) |
| **Micro-blasted anodized aluminum / brushed titanium** | Fine anisotropic micro-brushed directional highlight roll-off, crisp chamfered metallic edges; for dark finishes, *"deep powder-coated satin-matte obsidian metal absorbing light cleanly without turning silver"* | *"Chrome"*, *"mirror metallic"* (reflects hallucinated rooms/crew and flickers across frames) |
| **Honed travertine / matte stoneware** | Open natural mineral pores, dry unglazed ceramic micro-grain, crisp grounded contact shadows resting squarely on the surface | *"Polished marble"*, *"glittering mineral dust"* (produces noisy specular shimmer/flicker) |
| **Ferrofluid / raw silk** | Viscous dark liquid-metal surface tension with narrow high-contrast specular ridges (ferrofluid) OR unbleached matte woven silk with slow weighted micro-folds and natural drape inertia | *"Swirling magic liquid"* or *"floating fabric"* (triggers chaotic morphing) |

### B. 4-Part Studio Lighting, `0.1s` Silhouettes & Mirrored HEX Palette Lock

- **Single directional motivated key:** Build every studio plate with the 4-part formula ([Prompt Patterns](prompt-patterns.md))—e.g. *`crisp directional 4800K architectural daylight from a tall camera-left window casting clean stationary diagonal shadows across honed stone`*, paired with natural ambient bounce fill and honest grounded contact shadows (zero neon rim light, zero floating volumetric haze, zero unmotivated specular flashes).
- **`0.1s` instant-read silhouette test:** Every hero object must read unmistakably on mute in `0.1s` without captions. Reject ambiguous sculptures (e.g., a turned-off mushroom dome mistaken for abstract decor); choose iconic functional geometry plus honest practical cues (e.g., an articulated architectural desk lamp switched ON with a steady warm `2700K` downward pool on the stone below).
- **Mirrored Percentage Palette Lock (with HEX):** Lock multi-shot studio grade before post by declaring exact 3-band color proportions with `#RRGGBB` values early and echoing the same ratio in the tech tail:
  - *Example (architectural travertine studio world):* `PALETTE, stated first: 50% honed pale warm travertine & matte ivory plaster (#E6E0D6 / #F2EFEA), 30% matte charcoal stoneware & satin-matte obsidian anodized metal (#24282E / #17191D), 20% brushed stainless steel (#CFD4DA), clear champagne crystal (#E5D4B3), warm 2700K practical glow, and pale bent oak (#C9A87C).` ... `Shot on 50mm spherical lens, f/5.6, natural medium-format grain; tech tail palette: travertine & plaster 50%, charcoal & obsidian 30%, steel/crystal/oak accents 20%.`

## 2. Three Proven Abstract Motion Prompt Archetypes

### A. Pixel-Locked Living Still / Surgical Finish Swap (The Stationary-Light Law)

Use `--start_image == --end_image` on `seedance_2_5 --mode omni_reference` (or matching locked-off tripod pair `S04` → `S05` animated separately) when holding a calm hero tableau or executing a pixel-locked finish swap.

- **The Stationary-Light Law (verified locked-tabletop `v1 → v2` QC finding):** Asking a video model for *"breathing daylight"*, *"gliding studio light across metal"*, or *"delicate caustic shimmer across the stone"* breaks locked tabletops—causing practical `2700K` bulbs to dim mid-clip, curved ghost lens-flare ribbons to drift across wall caption zones, watery swimming-pool caustic ribbons to appear on solid opaque stone, and plinth shadows to sweep/invert across the cut seam.
- **Exact fix:** Lock stationary directional daylight, motionless diagonal sunlight edges and contact shadows from frame 1 to the final frame, exact millimeter object coordinates, and constant practical Kelvin luminance (`never dimming or flickering`). Confine micro-motion strictly to ultra-subtle 35mm cinema atmosphere, microscopic steady refraction *inside* clear glass, and authentic fine film grain.

```text
Locked-off static tripod shot, horizon level, zero camera movement throughout the entire 4 seconds. Fixed stationary architectural daylight from the tall camera-left window: the diagonal sunlight edge and contact shadows on the honed pale travertine plinth and ivory plaster wall remain completely stationary in their exact starting positions from frame 1 to the final frame. All unbranded objects on the slab remain 100% motionless in their exact millimeter coordinates; the desk lamp holds its satin-matte finish and stays steadily switched ON at constant warm 2700K brightness, never dimming or flickering. Micro-motion consists strictly of ultra-subtle natural 35mm cinema atmosphere, microscopic steady refraction inside the clear glass flacon, and authentic fine film grain. Zero lens flares, zero curved light streaks, zero watery caustic stripes on solid stone, zero moving shadows, zero logos or text.
Audio: Quiet studio room tone only.
NO MUSIC. NO BACKGROUND SCORE. Native diegetic sound only.
```

### B. Sculptural Kinetic Macro / Robo-Arm Showcase

Use a clean uncluttered studio backdrop, one hero object, and `50mm` or `85mm` at `f/4`. Prefer a **`45–90° Arc`** in 5s over a full `360° Orbit` (which forces unobserved-back hallucination unless anchored via `3D Jutsu` or multi-angle `R2` plates). When driving the move via Web Cinema Studio `#Robo Arm` or `#Lazy Susan`, obey **Zero Double-Command** ([Camera Control](camera-control.md#1-four-hard-camera-invariants))—omit prose camera verbs so the mechanical preset owns the trajectory while prose governs material light-play and sound:

```text
[When using Web Cinema Studio #Robo Arm or #Lazy Susan — omit camera verbs]
Horizon level. The unbranded micro-blasted anodized aluminum cylinder rests squarely on the honed pale travertine plinth under crisp directional 4800K daylight from camera-left. As light travels smoothly across the chamfered upper bezel and anisotropic brushed flank, the grounded contact shadow stays tight and solid against the stone pores while the satin translucent resin core diffuses a soft uniform internal glow. Fine natural 35mm film grain, zero floating particles, zero logos or text.
Audio: Clean quiet studio room tone with faint resonant air presence.
NO MUSIC. NO BACKGROUND SCORE. Native diegetic sound only.
```

*(When prompting without a UI preset, open with `Smooth steady 60-degree arc clockwise around the hero object, easing smoothly into a gentle hold at 4.5s, horizon level.`)*

### C. Abstract Form-to-Form Morph (Locked-Stage FLF)

Use First/Last Frame interpolation (`--start_image` + `--end_image` on `seedance_2_5`, `kling4_0`, `kling_o3_flf`, `wan3_0`, or `cinematic_studio_video_4_0`).

- **Hard precondition:** Both `R3` stills MUST share an **identical locked plinth/backdrop, identical lens focal length & camera position, and identical directional key light + shadow footprint** so 100% of diffusion capacity focuses on clean physical form transformation instead of warping the room into morph soup.

```text
Locked-off static tripod shot, horizon level, fixed stationary 4800K architectural daylight from camera-left with motionless background wall and plinth shadows. Over 4 seconds, the matte charcoal stoneware sphere at center frame parts cleanly along vertical machined seams and unfolds smoothly with weighted mechanical precision into the beveled optical borosilicate glass prism, settling squarely onto the exact same travertine footprint with crisp internal refraction and a stable grounded contact shadow. Organic 35mm film grain, zero camera drift, zero logos or text.
Audio: Soft dry ceramic slide transitioning into one crisp resonant glass settle on stone, quiet studio room tone.
NO MUSIC. NO BACKGROUND SCORE. Native diegetic sound only.
```

## 3. Seamless Transitions, Match Cuts & Zero-Video-Credit Pacing

- **Sub-0.5s `2K` Still Montage:** On cuts shorter than `0.50s` (`<= 12 frames @ 24fps`), viewers perceive rhythmic kinetic energy, silhouette contrast, and camera-angle variety rather than intra-shot optical flow. Generate verified `0 cr.` Web `Unlimited` `2K` studio plates (confirm the CTA button flips to `Unlimited`) across **4 locked real studio camera angles** (Frontal `50mm`, `90°` Top-Down Overhead, Heroic Low `3/4`, Tight Horizontal `85mm` Profile) on one locked studio surface/light, and cut pure `0.00s` hard cuts on an integer BPM grid—e.g., **`120 BPM @ 24fps`** (`12 → 8 → 6 → 4` frames = `0.50s → 0.33s → 0.25s → 0.17s`) synced to dry acoustic percussion and product foley. Reserve video credits strictly for the long-hold hero climax (`>= 2.5–4.0s`) after an abrupt silence turn; never substitute cheap digital crop-zooms or post `xfade` dissolves for real multi-angle plates.
- **Pixel-Locked Surgical Finish Swap (Zero Morph Soup):** Never ask a video model to morph one product colorway/material into another mid-clip (causes liquid-metal melting and drifts neighboring props). Instead: lock `R3` Still A → derive Still B via a single-variable edit holding camera, plinth, shadows, and neighboring objects 100% identical → animate Still A and Still B separately as pixel-locked living stills (`--start_image == --end_image` under the Stationary-Light Law) → cut cleanly at **`0.00s` dead-on an isolated tactile foley click** (e.g., anodized switch click).
- **Silhouette Match Cuts (`±5%` Centroid & Diameter):** Align successive hero objects' visual center `(x, y)` and bounding diameter within `±5%` across categories (e.g., watch dial → telephoto lens barrel → stoneware bowl rim → lamp base) so high-speed `0.00s` hard cuts maintain effortless optical eye-lock without jump fatigue.
- **Seamless Lead/Tail Holds (`video_extension`):** Use `seedance_2_5 --mode video_extension --extension_mode forward|backward` (see [Live Workflows](../../higgsfield-cli/references/live-workflows.md)) to extend an already-locked hero clip inside the exact same grain, exposure, and lighting rather than splicing a mismatched second take.
- **In-Camera Bridges:** Pair `Whip Pan` (cut on 2–3 peak-blur frames), `Foreground Wipe`, and Cinema Studio `#Through Object In` / `#Through Object Out` (passing through a clean aperture, glass edge, or dark silhouette) instead of post editing transitions—see [Camera Control](camera-control.md#d-in-camera-transitions-zero-post-xfade-band-aids).

## 4. Five-Way Tool Routing & Four Hybrid Zero-Actor Recipes

Choose the right production lane per shot (verify live pricing/CEL in [Model Selection](../../higgsfield-cli/references/model-selection.md) and [Live Workflows](../../higgsfield-cli/references/live-workflows.md); enforce finishing order in [Video Assembly](../../video-assembly/SKILL.md)):

| Lane | Primary Tools | Owns Best | Never Use For |
| :--- | :--- | :--- | :--- |
| **(a) Generative Video Models** | `seedance_2_5`, `cinematic_studio_video_4_0`, `kling4_0`, `wan3_0`, `veo3_1`, `flux_3_video` | Tactile physical light, glass refraction, studio tabletop living stills, FLF material morphs, organic 35mm texture | Small UI text, Cyrillic copy, exact SVG wordmarks, sub-0.5s montage flashes |
| **(b) Marketing Studio / Explainer Templates** | `marketing_studio_v2_video` (`saas_motion`, `2d_motion`, `hypermotion`, `mixed_media`, `app_video`) + `higgsfield preset list video-explainer` / `marketing-studio-v2` | Fast stylized SaaS/app motion layouts and kinetic product templates (`1080p` flat-rate quoting; verify `input_images` CEL in [Live Workflows](../../higgsfield-cli/references/live-workflows.md)) | Bespoke brand typography or zero-template flagship launch identity |
| **(c) 3D Asset Gen + `3D Jutsu` QR Camera** | `hunyuan3d_v3_1_text_to_3d`, `tripo_h3_1_multiview_to_3d`, `meshy_v7_image_to_3d` → Web `3D Jutsu` (desktop + **smartphone QR virtual camera**) → `@Video1` in `seedance_2_5` / Genjutsu (`hf_mult_motion_control*`) | Exact multi-angle sculptural geometry, 360° hero orbits, tight architectural flythroughs with real physical camera paths | Simple locked tabletop holds where `R3` stills + I2V already suffice |
| **(d) Web `Supercomputer / AI Motion Design` (ex-Vibe Motion)** | Higgsfield **`Supercomputer / AI Motion Design`** (`/vibe-motion` → `/supercomputer`, landing `/ai-motion-design` + `/ai-motion-designer` for AE + ChatGPT/MCP): `Motion Design` & `Editorial Motion Graphics` skills (`with subtitles`), `Brandkit`, `Higgsfield explainer` presets, `Agent mode`, up to `4K` export | Rapid browser proofs of kinetic typography, clean SaaS UI explainers, and Brand-Kit motion cards without writing code | `0 cr.` Unlimited runs (**no `Unlimited` toggle**; excluded from plan Unlimited), pre-gen **ProRes / WebM / alpha / `60fps`** exports (no UI toggles), complex non-Latin kerning locks, or deterministic multi-sample shutter-blur SVG unfolds |
| **(e) Local Deterministic Code / Compositor + Matte/Depth** | Local **Remotion**, Python + `resvg-py`, or After Effects + `video_background_remover` / `depth_anything_video` | `$0` deterministic `24fps`/`60fps` UI, Cyrillic/editorial type, exact math curves, 3-sample shutter-blurred SVG unfolds (`endtag-fold`), depth-woven type behind/in front of 3D motion, `ProRes 4444` alpha | Organic glass/stone/fabric physical photography |

### Four Proven Hybrid Zero-Actor Recipes

1. **Apple-Style Kinetic Montage + Living-Still Swap:** Shoot `0 cr.` Web `Unlimited` `2K` plates across 4 studio camera rigs → cut at `120 BPM @ 24fps` (`12→8→6→4f`) over dry percussion → drop into abrupt deadpan silence (`2.0–2.2s`) with clean editorial typography → reveal pixel-locked `S04 → S05` `1080p` living-still finish swap (`seedance_2_5`, Stationary-Light Law) cut at `0.00s` on an isolated foley click → hard-cut into a deterministic local `resvg-py`/Remotion unfolding SVG wordmark composited **after** creative LUT.
2. **3D-Locked Sculptural Hero Orbit / Flythrough:** Mint PBR mesh (`hunyuan3d_v3_1_text_to_3d`, `tripo_h3_1_multiview_to_3d`, or `meshy_v7_image_to_3d`) or multi-angle `R2` plates → stage in Web `3D Jutsu` and record a live handheld/dolly orbit via smartphone QR tracking → pass previz MP4 as `@Video1` into `seedance_2_5` or `hf_mult_motion_control_flash` with locked `R2`/`R3` material stills → finish with unified LUT + grain.
3. **Depth-Woven Kinetic Type Over Tactile 3D Motion:** Render clean text-free tactile motion in lane (a) or (c) → extract foreground alpha (`video_background_remover`) or grayscale depth map (`depth_anything_video --colormap grayscale --variant VDA-Large`) → composite local Remotion / AE / Python typography cleanly *behind* the moving foreground sculpture and *in front of* the studio backdrop after applying creative LUT to the footage.
4. **SaaS Product Launch Proof-to-Master Hybrid:** Rapidly prove kinetic layout and pacing in Web `Supercomputer / AI Motion Design` (formerly `Vibe Motion`) or `marketing_studio_v2_video` (`saas_motion` / `app_video` / `video-explainer` refs) during `R2`/`R3` → shoot tactile hero cutaways in lane (a) → rebuild final high-stakes UI, Cyrillic typography, and official SVG brand marks deterministically in local Remotion or Python+`resvg-py` (`ProRes 4444` alpha) for pixel-exact `R5` delivery.

## 5. Five Abstract Failure Modes & Surgical Fixes

Apply **One Variable Per Re-roll** when diagnosing `R3`–`R5` abstract or motion-design defects:

| Failure Mode | Root Cause | Surgical Fix |
| :--- | :--- | :--- |
| **1. Template Look** *(stock wipes, neon HUD grids, sterile CGI plastic)* | Buzzword prompts, unmotivated editing transitions, or unstyled template defaults | Strip neon/HUD/CGI buzzwords; write physical material micro-grammar + single motivated 4-part studio key + pure `0.00s` hard cuts + natural 35mm grain; reserve templates for deliberate graphic beats |
| **2. Geometry Melt** *(warping silhouettes, drifting proportions, hallucinated backs)* | `360°` text-prompted orbit, mismatched FLF plinth/lens, or `> 5` image refs | Restrict text-driven orbits to `45–90° Arc`, lock identical plinth/lens/light across FLF pairs, prune to `2–4` visible refs, or drive exact geometry via `3D Jutsu` previz (`@Video1`) |
| **3. Caustic / Shadow Drift** *(swimming-pool stripes on stone, ghost flares, dimming bulbs, shifting shadows)* | Prompt asked for *"breathing daylight"*, *"gliding light"*, or *"shimmering caustics"* on a locked hold | Enforce the **Stationary-Light Law**: lock fixed sunlight edge, motionless shadows, and constant practical Kelvin luminance from frame 1 to final frame; restrict micro-motion to subtle 35mm atmosphere and internal glass refraction only |
| **4. Garbled AI Text / Logos** *(warped letters, mangled Cyrillic, invented trademarks)* | Asking diffusion/video models to render fine copy, UI, or brand wordmarks | Enforce the **0-Text Diffusion Boundary**: prompt 100% unbranded text-free plates/clips (`zero logos, zero text`) and composite crisp typography, UI, and SVG wordmarks in `Supercomputer / AI Motion Design` (proofs) or local Remotion / Python+`resvg-py` / AE after LUT |
| **5. Cross-Engine Contrast / Color Jumps** *(black-level or exposure pop between still montage, video climax, and title cards)* | Missing HEX palette lock or LUT applied unevenly across stills, video, and graphics | Lock mirrored HEX Percentage Palette across all `R2`/`R3` plates, then apply one shared 3D LUT + matched temporal grain strictly to photographic plates and live video **before** compositing clean vector/typography cards ([Video Assembly](../../video-assembly/SKILL.md)) |

*Done when:* zero-actor plates lock physical material micro-grammar, single motivated studio key, `0.1s` silhouettes, and mirrored HEX palettes; locked holds obey the Stationary-Light Law; sub-0.5s openings use multi-angle `2K` stills instead of wasted video credits; all text/logos obey the 0-Text Diffusion Boundary; and every shot routes to the right lane across generative, 3D, Web `Supercomputer / AI Motion Design`, and local deterministic compositors.

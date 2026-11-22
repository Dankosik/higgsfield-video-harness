# Production Flow Router (`production_track`)

Automatically classify every incoming video request during `R0` based on its
**inputs**, **deliverable format**, and **staging complexity**, then follow the
selected track without loading unrelated branch skills. Record the chosen track
in `brief.md` and optional `shotlist.json` (`"production_track": "<track>"`).

## Auto-Detection Matrix

Evaluate signals top-to-bottom on the user's first request (plus attached files
or URLs):

| Priority | Signals (Inputs / Goal / Format) | `production_track` | Owning Track Skill & Route Adaptation |
| :---: | :--- | :--- | :--- |
| 1 | User supplies **existing live-action footage** of a speaker or scene (`<= 10 min`) and wants new angles, lighting, locations, outfits, props, or color without losing the real take | `v2v_one_take` | Load [`video-v2v-rewrite`](../.agents/skills/video-v2v-rewrite/SKILL.md). Skip `R2`/`R3` from-scratch lookbooks; chunk source to `<= 30s`, chain single-variable V2V passes (`Seedance 2.5` / `Genjutsu` / `Editing Room`) with `t -> t` performance lock. |
| 2 | Brief requires **creatures, VFX compositing, impossible mirrors/loops, dense 15–30s multi-character choreography, or live-action plate integration** | `previz_3d_vfx` | Load [`video-previz-vfx`](../.agents/skills/video-previz-vfx/SKILL.md). Insert the 4-tier Spatial Blocking Gate in `R1B` (`B&W storyboard` -> `X/Y% map` -> `Clay placeholder` -> `3D Jutsu` / `Blender`), `Clay -> Macro -> Flash` asset builds, `360°`/Mannequin face swaps, and `qa_media.py pixel-diff` QA. |
| 3 | Brief asks for a **SaaS/app/product launch film, UI demo, kinetic typography, HUD overlays, or motion graphics** combining code/NLE layers with AI visuals | `hybrid_motion_launch` | Load [`hybrid-motion-graphics`](../.agents/skills/hybrid-motion-graphics/SKILL.md). Add HTML Design Sheet + 9-frame `marketing_studio_image` gate in `R1B`/`R2`, isolate AI raster/video from editable code/AE/Remotion UI layers, snap cuts to `BPM`, and composite overlays post-LUT. |
| 4 | Brief targets **paid social performance ads (Meta/TikTok/Reels)** needing multi-angle static + `9:16` video batches for an e-commerce product or local/B2B service | `performance_ads` | Load [`performance-ads`](../.agents/skills/performance-ads/SKILL.md). Run review/objection research in `R0`, map `PROOF` (e-com) / `QUEST` (services) / `STOP` angles in `R1A`, produce static + `9:16` safe-zone video sets, and recompose (never scale down) across `1:1` / `9:16`. |
| 5 | Brief asks for a **3–5 min faceless YouTube documentary/explainer** OR **batch vertical clipping/repurposing** from a long video/podcast | `youtube_and_clipping` | Load [`youtube-clipping`](../.agents/skills/youtube-clipping/SKILL.md). Gate research -> moodboard before media spend; enforce `9:16` Shorts safe zones, 3-option A/B thumbnail packaging, and 1-clip approval before 10-clip batching. |
| 6 | **Default:** Brand commercial, narrative short film, resort/product promo, or multi-shot campaign built from scratch (`16:9` or `9:16`) | `scratch_cinema` | Follow canonical [`docs/workflow.md`](workflow.md) (`R0`–`R6`) with mandatory `R0` real-photo grounding, decoupled `CHAR`/`OUTFIT` bibles, single-flagship-engine discipline (`Seedance 2.5` `480p Draft -> 1080p/4K` or Web Unlimited), fresh `reviewer-agent` MP4 QA, and `assemble.sh` v2. |

## Composable Sub-Flows (`sub_flows`)

Keep **one** sticky `production_track` as the campaign backbone, and attach
optional plug-in **`sub_flows`** (declared in `brief.md` and `shotlist.json`:
`"sub_flows": ["remotion_overlays"]`) whenever specific shots or finishing
stages need specialized craft **without** switching the main track:

| Sub-Flow (`sub_flows[]`) | When to Attach | Where It Plugs In | Owning Skill & Delivery |
| :--- | :--- | :--- | :--- |
| `remotion_overlays` | Animated logos, endcards, kinetic typography, callout cards, HUDs, or UI graphics layered over or spliced into the main video | `R5` post-LUT finishing (`--overlay`) or dedicated graphic insert shot | [`hybrid-motion-graphics`](../.agents/skills/hybrid-motion-graphics/SKILL.md) -> transparent `1080p` ProRes 4444 (`yuva444p10le`) composited **after** LUT/grain via `assemble.sh --overlay` |
| `vfx_hero_shot` | 1–2 shots inside a normal spot need a creature (`Clay -> Macro -> Flash`), clay placeholder, 3D previz, or tracked VFX pass | `R1B` blocking + target shot(s) in `R4/R5` + `pixel-diff` QA | [`video-previz-vfx`](../.agents/skills/video-previz-vfx/SKILL.md) -> isolated to tagged shots only |
| `v2v_rescue_or_recam` | 1–2 live-action or approved shots need an alternate angle, relight, or object/outfit swap while keeping exact performance | Target shot(s) in `R4/R5` | [`video-v2v-rewrite`](../.agents/skills/video-v2v-rewrite/SKILL.md) -> single-variable V2V pass (`Seedance 2.5` / `Genjutsu` / `Editing Room`) |
| `shorts_cutdown` | Repurpose the finished `16:9` `master.mp4` into 2–3 vertical `9:16` Shorts/Reels after final sign-off | Post-`R5` derivative export (`0` video gen credits) | [`youtube-clipping`](../.agents/skills/youtube-clipping/SKILL.md) -> `assemble.sh` `trim_in/out` + `9:16` safe-zone reframe |

Sub-flow skills are loaded **only** on the specific shot or stage where they
execute (zero token tax during unrelated rounds) and never alter the locked
primary `production_track`. **Mandatory read before execution:** whenever a
campaign declares any entry in `sub_flows[]` (`brief.md` / `shotlist.json`),
the actor owning that stage MUST read that sub-flow's owning `SKILL.md` before
authoring, coding, or rendering it (e.g. read `hybrid-motion-graphics/SKILL.md`
before building `remotion_overlays`).

## Sticky Track Lock & Zero Re-Asking Contract

1. **Automatic classification once in `R0`:** Inspect the Director's first
   message, attached files, and URLs against the matrix above.
   - If the match is clear (90% of requests), pick `production_track`
     automatically, scaffold `brief.md` via `campaign_init.py --track <track>`
     (writing `production_track: <track>` right under `status:`), and state the
     chosen flow in **one jargon-free line** during `R0` (or proceed directly
     when autonomous).
   - Ask **at most 1 short clarifying question** during `R0` grilling *only* if
     two tracks genuinely conflict (e.g., user attached both raw talking-head
     footage and a product-launch brief).
2. **Locked for the entire campaign (`R1`–`R5`):** Once `brief.md` moves to
   `status: active` (and `shotlist.json` records `"production_track"`), the
   selected track is **sticky and locked**. Every subsequent round and subagent
   reads `production_track` from `brief.md` / `shotlist.json`, follows that
   single track, **never re-runs flow detection**, **never re-asks which flow
   to use**, and **never switches tracks silently**.
3. **Explicit pivot only:** Changing `production_track` mid-campaign requires
   an explicit Director request, updating `production_track` in `brief.md` and
   `shotlist.json`, and logging a `TL-NN` entry in `taste-log.md`.
4. **Additive secondary skills without switching tracks:** When a
   `scratch_cinema` spot contains one VFX shot or one launch-style endcard,
   keep `production_track: scratch_cinema` locked and load only the single
   needed secondary skill (`video-previz-vfx` or `hybrid-motion-graphics`) for
   that shot.
5. **Universal invariants across ALL 6 tracks:** `AGENTS.md` Studio Law, Web
   `Unlimited` (`0 cr.`) priority, `LOCKED` asset immutability, `hf_guard.py`
   budget walls, independent `reviewer-agent` MP4 + `qa_media.py` verification,
   and `assemble.sh` finishing apply to every track.

*Done when:* `production_track` is detected once in `R0`, persisted in
`brief.md` + `shotlist.json`, locked for `R1`–`R5` without re-asking, and only
its owning track skill is loaded.

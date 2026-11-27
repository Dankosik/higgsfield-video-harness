# Studio Workflow (`R0` → `R5`)

Run every multi-shot video, commercial, or branded spot through six interactive
rounds between the **Director (human)** and **Production Crew (agents)**. Keep
the Root Producer in one continuous session across `R0`–`R5` so the Director's
verbatim *why* stays a primary source. Each round executes full technical craft
internally and stops with one **Dailies Packet** for taste feedback and
next-round credit approval.

For JSON shapes and CLI flags, inspect the living fixtures and tools directly:
[`campaigns/example-product-spot/`](../campaigns/example-product-spot),
`scripts/check-brief.py`, `scripts/check-campaign.py`, and
`scripts/hf_guard.py --help`. Load the owning skill when a round needs
technical or narrative craft:
[`video-narrative`](../.agents/skills/video-narrative/SKILL.md),
[`higgsfield-cli`](../.agents/skills/higgsfield-cli/SKILL.md),
[`video-direction`](../.agents/skills/video-direction/SKILL.md),
[`video-consistency`](../.agents/skills/video-consistency/SKILL.md),
[`video-qa`](../.agents/skills/video-qa/SKILL.md), and
[`video-assembly`](../.agents/skills/video-assembly/SKILL.md).

## The 6 Rounds

### R0 — Brief (`0 cr.`)
- **Craft:** First classify `production_track` (and optional `sub_flows`) via
  [Flow Router](flows.md) and load only its owning track skill if non-default.
  Ground via `evidence-agent` in `higgsfield account status`, `workspace list`,
  `studio/director.md` (plus `studio/director.local.md` if present),
  `studio/engine-memory.md`, `brands/<brand>/{brand.md,taste.md}`, and local
  photos under `media/references/`. **Mandatory visual grounding:** whenever the
  request references a real website, brand, product, or location URL, collect
  real reference photographs into `media/references/` *before* `R2` (never rely
  on text scraping alone). Run light [Grilling](grilling.md) (3–5 meaning-only
  questions: viewer state shift `Before -> After`, human & brand truth, primary
  misread risk, spoken pronunciation, taboos, `Campaign cap`). Scaffold with
  `make campaign-init`, write
  plain-language `brief.md` (`status: draft`), seed `taste-log.md` from
  `brands/<brand>/taste.md` when present, compile `taste-active.md` via
  `make memory-compile CAMPAIGN=<slug>`, and run
  `make brief-check CAMPAIGN=<slug>`.
- **Dailies 0:** Short `brief.md` card + seeded taste anchors + `Campaign cap`
  confirmation. Once confirmed, flip `brief.md` to `status: active` and re-run
  `make brief-check CAMPAIGN=<slug>`.
- *Done when:* Director confirms `Dailies 0`, `brief.md` is `status: active`,
  and `make brief-check` passes with zero jargon and zero requester-owned open
  questions.

### R1 — Story & Cost Ticket (`0 cr.`)
- **R1A (Concept):** For commercials, run `ad-references` (skip if Director
  supplied an angle or reference spots) → `ad-concepts` (4–5 orthogonal
  swap-tested pitches grounded in **Human Truth** and **State Shift** per
  [`video-narrative`](../.agents/skills/video-narrative/SKILL.md)); for
  non-commercials (brand films, product launches, shorts, docs), draft 2–3
  contrasting narrative treatments via
  [`video-narrative`](../.agents/skills/video-narrative/SKILL.md).
  Stop with **Dailies 1A** so the Director picks or blends a direction.
- **R1B (Blueprint & Quote):** Run `ad-script` (`Narrative Lock`, `Time | Video
  | Audio`, `BUT / THEREFORE` causal spine, read-aloud budget, mute test) →
  `ad-storyboard` (`Narrative Lock`, `Continuity Lock`, per-shot `Narrative job`
  passing the **Deletion Test**, `test_take_check`) → `style-bible.md`. Enforce
  the **Shot-Density & Anti-Static-Slideshow Gate**: target **`2.5–5.5s`**
  average shot duration (`10–18` distinct shots/angles for a `45–60s` Short;
  `6–10` for a `30s` spot). Even when reusing user-supplied stills, **never
  stretch 5 stills into `11–15s` single-shot I2V clips** — derive complementary
  close-ups, reverse angles, cutaways, or `4K` 2× punch-ins in `R2B`/`R3` first.
  Commit upfront to:
  1. One **Production Track** (`Live-Action Cinema` vs. `Zero-Actor
     Sculptural/Product` vs. `Abstract / SaaS Motion Hybrid`, aligned with
     [Flow Router](flows.md)), assigning per shot whether it uses `Sub-0.5s 2K
     Still Montage` (`still_only`, `0` video cr.), generative video, `3D (.glb)
     -> 3D Jutsu (QR camera)`, or `Supercomputer / AI Motion Design` vs. local
     `Remotion / resvg-py`.
  2. One **Prompt Architecture** (`Commercial Hybrid` default, `Cinema Spec`, or
     optional `Ultra-Lean Stylized Multi-Shot` — see
     [`video-direction`](../.agents/skills/video-direction/SKILL.md)).
  3. A **1-step active Web `Unlimited` rotation check** (read `ENG-06` in
     [`studio/engine-memory.md`](../studio/engine-memory.md) or confirm live in
     browser that the **Generate CTA button itself flips to `Unlimited`
     (`0 cr.`)**, never trusting promo badges alone; `MCP`/`CLI`, `Canvas`, and
     `Supercomputer` are excluded) so `R4`/`R5` tickets never assume unavailable
     video `Unlimited` and route inactive-rotation visuals straight to `Sub-0.5s
     2K Still Montage` or economy native CLI without empty browser loops.
  Plan spatial/cast plates (`R2A`/`R2B`) per
  [`video-consistency`](../.agents/skills/video-consistency/SKILL.md), and
  choose each shot's camera route and `R4 → R5` native mastering path per
  [`higgsfield-cli`](../.agents/skills/higgsfield-cli/SKILL.md) so drafts never
  dead-end in `480p` upscaling. Dispatch `evidence-agent` to inspect live
  schemas (including hidden `duration` / `prompt_language` defaults) and run
  live `higgsfield generate cost` per round (using cost params or uploaded UUIDs
  only—never private local file paths, which `generate cost` auto-uploads).
  Write `shotlist.json` + initial `prompts/` and verify `make campaign-check
  CAMPAIGN=<slug>` (`R2 + R3 + R4 + R5 <= Campaign cap`).
- **Dailies 1B:** Readable beat-by-beat story + clear budget ticket separating
  **CTA-verified `0 cr.` Web `Unlimited` active-rotation visuals** (and `0`
  video-cr. `Sub-0.5s 2K Still Montage` shots) from non-Unlimited visuals (e.g.,
  video when Web Unlimited video is inactive) and CLI-only items (audio/SFX,
  3D/matting), plus live CLI quotes, approval ask for uploading local
  `media/references/` photos (if any), and proposed `--round-cap` whenever the
  next round has paid CLI items.
- *Done when:* Director picks a direction (`1A`), `make campaign-check` passes
  (`1B`), and Director confirms story/direction plus any private reference
  uploads or paid `--round-cap` (if non-Unlimited spend applies).

### R2 — Casting & World Asset Bible (`0 cr.` Web Unlimited default; `~20–45 cr.` CLI fallback; skip if `lookbook: []`)
- **Skip rule:** Skip `R2` automatically when real photos in `media/references/`
  already cover every hero object, character, and location (`lookbook: []`);
  upload those photos at the start of `R3` via `hf_guard.py upload --round R3`
  and save `references[].upload_id` in `shotlist.json`.
- **R2A (Discovery & Master Lock):** Upload approved local `media/references/`
  photos needed for Lookbook generation via `hf_guard.py upload --round R2`
  (`references[].upload_id`). Organize outputs by entity type under
  `media/lookbook/{characters,locations,props}/`. Generate 2–3 contrasting
  variants (`A`, `B`, `C`, version `1`) per `lookbook[]` entity using
  **CTA-verified `higgsfield.ai` Web `Unlimited` (`0 cr.`) via the built-in
  `browser` subagent by default** (per [`higgsfield-cli`](../.agents/skills/higgsfield-cli/SKILL.md)
  and [`video-consistency`](../.agents/skills/video-consistency/SKILL.md)),
  falling back to parallel `worker-agent` CLI `hf_guard.py run --round R2
  --round-cap <cap>` only when `Unlimited` is unavailable or Director asks for
  paid CLI speed. Filter defects and `TASTE_REGRESSION`s via fresh
  `reviewer-agent`, then build one labeled grid with
  `make lookbook FILES="..." OUT=campaigns/<slug>/qc/lookbook.png LABELS="A,B,C"`.
- **Dailies 2:** `qc/lookbook.png` + comparative picks + `R2B`/`R3` ticket
  (`0 cr.` Web Unlimited for visuals + exact CLI cost for audio/non-Unlimited).
  Upload chosen winners via `hf_guard.py upload --round R2`, record
  `approved_variant`, `approved_take`, and `approved_upload_id`, and set
  `status: "LOCKED"` in `shotlist.json`.
- **R2B (Asset Bible Gate — before `R3`, skip only on simple single-angle spots):**
  Whenever the storyboard uses reverse angles, mirrors, multi-angle sets,
  recurring props, or expressive/turning characters, expand locked `R2A`
  Masters (`variants_requested: 1`) into only the triggered canonical plates
  (Reverse Walls, multi-angle/state plates, orthographic `#808080` prop plates,
  Character Bible / Expression Calibration plates, or optional `Soul ID` /
  Kling Elements) via CTA-verified Web `Unlimited` (`0 cr.`) first per
  [`video-consistency`](../.agents/skills/video-consistency/SKILL.md), slice
  any angle sheets with `make slice-grid`, audit via `reviewer-agent`, upload
  via `hf_guard.py upload --round R2`, and lock their UUIDs before `R3`.
  - **Optional 3D / Motion Previz Gate:** When storyboards require impossible 3D
    flythroughs or true `360°` rigid-object orbits, generate a `.glb` mesh via
    `Hunyuan3D` / `Tripo` / `Meshy` → stage and capture the real camera path in
    Web `3D Jutsu` via QR smartphone tracking → export the previz MP4 and upload
    it via `hf_guard.py upload --round R2` for `R4` `@Video1` motion lock.
- *Done when:* every triggered `R2A` Master and `R2B` Bible plate is `LOCKED`
  with a verified `approved_upload_id` (or `R2` is skipped with `lookbook: []`)
  and Director approves `R3` direction (plus `--round-cap` for any paid CLI
  audio/non-Unlimited items).

### R3 — Keyframe Stills & Still Animatic (`0 cr.` Web Unlimited stills + `~5 cr.` audio; `~30–50 cr.` CLI fallback)
- **Craft:** If `R2` was skipped, upload approved local `media/references/` via
  `hf_guard.py upload --round R3` (`references[].upload_id`). Generate `s01..sN`
  `2k`/`4k` stills via **CTA-verified Web `Unlimited` (`0 cr.`) first** (falling
  back to parallel `hf_guard.py run --round R3 --round-cap <cap>` only when
  unavailable) bound to `LOCKED` UUIDs, `Continuity Lock`, `taste-log.md`, and visible-only
  reference budgets. Generate enabled VO (verify via `make qa-voice` /
  `scripts/qa_media.py voice <wav> --window <sec> --json`; rewrite copy and
  regenerate on overflow instead of speeding up with `atempo`) and enabled
  rough music via `hf_guard.py run`. Filter via fresh `reviewer-agent`, record
  `still.selected_take` and audio `selected_file` in `shotlist.json`, build
  `qc/stills_strip.png` (`make lookbook`), and render
  `media/exports/animatic.mp4` via `make animatic CAMPAIGN=<slug>` (`0` video
  credits; see [`video-assembly`](../.agents/skills/video-assembly/SKILL.md)).
  Verify `0.1s` instant-read silhouettes and run a fresh `reviewer-agent`
  **Blind Viewer Read** against `Narrative Lock` (`NARRATIVE_DEFECT` filter per
  [`video-narrative`](../.agents/skills/video-narrative/SKILL.md)) on
  `stills_strip.png` + `animatic.mp4` before Dailies 3.
- **Dailies 3:** `stills_strip.png` + `animatic.mp4` + `R4A` (or `R4` if zero
  shots carry `test_take_check`) ticket (CTA-verified `0 cr.` Web `Unlimited` if
  active in rotation, `0` video-cr. `still_only` montage plates, and exact CLI
  quote for non-Unlimited video). Lock approved stills/audio (`status: "LOCKED"`)
  and upload locked stills via `hf_guard.py upload --round R3`.
- *Done when:* Director locks all required stills and audio after reviewing
  `animatic.mp4`, locked stills are uploaded, and Director approves `R4A`/`R4`
  (plus `--round-cap` if CLI fallback applies).

### R4 — Motion Dailies (CTA-verified Web `Unlimited` when active; `~45–90 cr.` CLI fallback)
- **Mandatory craft reads, single-flagship-engine discipline & draft-to-final routing:**
  Before authoring `R4`/`R5` video prompts, read
  [`video-direction`](../.agents/skills/video-direction/SKILL.md) (and
  [`video-consistency`](../.agents/skills/video-consistency/SKILL.md) for
  recurring characters/sets); before executing any declared `sub_flows[]` stage
  (e.g. `remotion_overlays`), read that sub-flow's owning `SKILL.md` from
  [Flow Router](flows.md). Keep one cohesive video engine across a continuous
  live-action sequence (avoid mixing 3–4 disparate engines or starved
  `mini`/`flash` drafts that produce inconsistent color, lens, and bitrate). Use
  Web `Unlimited` (`0 cr.`) when `R1B`/live browser confirms the **Generate CTA
  button flips to `Unlimited` (`0 cr.`)**; when Web `Unlimited` video is
  inactive, skip empty browser loops and route directly to `still_only`
  `Sub-0.5s 2K Still Montage` (`0` video cr.) or approved CLI runs (never
  silently switch to paid CLI without Director approval). For complex `8–30s`
  multi-shot blocks in CLI, prefer **`seedance_2_5 --draft true` (`480p` latent
  draft at `3 cr./s`) -> native `1080p`/`4K` `--draft_job_id`** (~64% savings
  with 1:1 timing lock) over dead-end `480p` pixel upscaling. On dialogue-heavy
  spots, lock **A-Roll first** before shooting B-Roll, and use post `Voice
  Change` rather than re-rolling video for vocal tone.
- **R4A (Risk-First Pilot):** Shoot shots with `test_take_check != null` first
  via CTA-verified Web `Unlimited` (`0 cr.`) or approved CLI
  (`hf_guard.py run --round R4A --round-cap <r4a_cap>`). Probe with
  `scripts/qa_media.py clip <mp4> --sheet <png> --json` (checking temporal
  stutter/jerk telemetry) and dispatch a **fresh `reviewer-agent`** (never
  self-grade) that watches actual `.mp4` playback via `read_file` and logs via
  `qa_media.py log-review --qa-report <json> --sheet <png>`. Stop with **Dailies 4A**.
  *(Skip `R4A` only when zero shots carry `test_take_check` and Director
  approved batch `R4` on Dailies 3.)*
- **R4B (Batch Draft & Cut):** Shoot remaining unlocked shots via CTA-verified
  Web `Unlimited` (`0 cr.`) or approved CLI (`hf_guard.py run --round R4B
  --round-cap <r4b_cap>`, using `batch=2` on hard beats and harvesting clean
  sub-clips via `shots[].edit.trim_in/out` in `scripts/assemble.sh`, never
  bypassing `assemble.sh` with ad-hoc `xfade` scripts). Probe every clip
  (`qa_media.py clip` + `qa_media.py batch`), filter via **fresh
  `reviewer-agent`** watching `.mp4` playback, record `video.selected_take`
  (and optional `edit` trims/grades) in `shotlist.json`, and assemble
  `draft_cut.mp4` via `make assemble
  CAMPAIGN=<slug> OUT=campaigns/<slug>/media/exports/draft_cut.mp4` (`-14 LUFS`,
  `<= -1.0 dBTP`). Re-run `reviewer-agent`'s **Blind Viewer Read** on
  `draft_cut.mp4` (arc clarity in motion, `2 + 2` pause room, audio counterpoint)
  before Dailies 4B.
- **Dailies 4B:** Playable `draft_cut.mp4` + **per-shot native `1080p` upgrade
  plan** for `R5` (CTA-verified `0 cr.` Web `Unlimited` native `1080p` if
  active in rotation, or exact per-shot CLI prices; never offer
  `480p → 1080p` pixel upscaling as a shortcut). Mark shots kept as-is (already
  native `1080p`, `still_only`, or no upgrade needed) `LOCKED`; keep shots
  scheduled for `R5` `1080p` upgrade unlocked (`IN_REVIEW` or `ITERATING`,
  bumping `version` if prompt/parameters change) so `hf_guard.py` permits `R5`.
- *Done when:* pilot passes Dailies 4A (when applicable), Director approves cut
  rhythm in `draft_cut.mp4`, kept shots are `LOCKED`, upgrade targets stay
  unlocked, and Director approves `R5` (plus `--round-cap` if CLI applies).

### R5 — Final Master (`1080p`, CTA-verified Web `Unlimited` when active / approved CLI quote)
- **Craft:** Upgrade **only** Director-approved unlocked shots to **native
  `1080p`** via CTA-verified Web `Unlimited` (`0 cr.`) when active in rotation,
  or approved CLI (`hf_guard.py run --round R5 --round-cap <r5_cap>`) following
  the mastering runbook and strict Upscale Gate in
  [`higgsfield-cli`](../.agents/skills/higgsfield-cli/SKILL.md) (never
  pixel-upscale `480p` drafts). Probe every upgraded clip with
  `qa_media.py clip <mp4> --sheet <sheet.png> --crops <crops.png> --json`, run
  `qa_media.py batch <r5_clips...> --strict --json`, and filter via fresh
  `reviewer-agent` against [`video-qa`](../.agents/skills/video-qa/SKILL.md)'s
  binary rubric (inspecting both `3x2` sheets and `1:1` native-pixel crops).
  Update `video.selected_take` in `shotlist.json`, assemble `master.mp4` +
  `stems/` with optional finishing unification (`LUT`/`GRAIN` or Resolve) and
  post overlays per
  [`video-assembly`](../.agents/skills/video-assembly/SKILL.md), and verify
  `make qa-render FILE=campaigns/<slug>/media/exports/master.mp4 SHEET=campaigns/<slug>/qc/master_sheet.png CROPS=campaigns/<slug>/qc/master_crops.png SLICES_DIR=campaigns/<slug>/qc/verify_slices`
  (handing the `<= 20s` slices directly to `reviewer-agent` for fast final playback QC).
- **Final Dailies 5:** `master.mp4` + `stems/` + spend receipt
  (`make budget-status CAMPAIGN=<slug>`) + offer to run `R6` consolidation
  ([`studio-retro`](../.agents/skills/studio-retro/SKILL.md)). On sign-off, mark
  upgraded shots `LOCKED` and flip `brief.md` to `status: done`.
- *Done when:* Director signs off on `master.mp4`, `make qa-render` passes, all
  final assets are `LOCKED`, and `brief.md` is `status: done`.

### R6 — Studio Retro & Consolidation (`0 cr.`, optional post-campaign Dream loop)
- **Craft:** Invoke user-triggered
  [`studio-retro`](../.agents/skills/studio-retro/SKILL.md): run
  `make retro-harvest CAMPAIGN=<slug>` and `make memory-lint` to mine
  `receipts.jsonl` (paid CLI + `log-web`), `qc/review-log.jsonl`, prompt churn,
  and `Supersedes` flips; route durable lessons as atomic ACE deltas to
  `studio/director.md`, `brands/<brand>/taste.md`, `studio/engine-memory.md`, or
  graduated code/skills + `studio/evolution-log.md`.
- *Done when:* `make check` passes and the Director approves the Retro Dailies
  diff (one-way door).

## Dailies Packet & Feedback Loop

Every round terminates in four compact blocks:
1. **What to inspect** — one consolidated artifact (`lookbook.png`,
   `stills_strip.png` + `animatic.mp4`, pilot clip, `draft_cut.mp4`, or
   `master.mp4` + `stems/`). On macOS with `Auto-open dailies: true`, run
   `open <artifact>` right before posting.
2. **Filtered internally** — one plain sentence summarizing defects or taste
   regressions caught internally (logged via `qa_media.py log-review`), or
   honestly surfacing any surviving borderline concern after retries exhaust.
3. **Comparative taste questions** — 2–3 jargon-free questions inviting `A / B / C`
   picks, blends, or visceral reactions.
4. **Cost ticket** — spent so far, remaining `Campaign cap`, exact itemized live
   quote for the **next single round only**, and proposed round cap (enforced
   internally via `--round-cap`).

When the Director reacts:
1. **Distill into `taste-log.md` and compile `taste-active.md`:** append
   `### TL-<NN> (R<k> — <stage>)` using the canonical bullets checked by
   `check-campaign.py`:
   - `Approved / LOCKED` · `More of` · `Change / Steer` · `Never`
   - Add `- **Supersedes:** TL-<prev>` (or `TL-<prev>[Category]` / `TL-<prev> (scope)`)
     whenever a new reaction overrides an earlier entry, then run
     `make memory-compile CAMPAIGN=<slug>` so downstream subagents read a fresh,
     contradiction-free `taste-active.md`.
   *(Surface any conflict with an earlier `TL-NN` as one `A / B` question before
   spending.)*
2. **Update `shotlist.json` (Root Producer only):** set approved items to
   `LOCKED`; set **only** steered items to `ITERATING`, bump `version` (`1 -> 2`),
   write a new versioned prompt file (`prompts/<id>_v2.txt`, keeping `v1`
   intact), and run `make campaign-check CAMPAIGN=<slug>`.
3. **Quote surgical micro-cost before re-rolling:** run live `generate cost` for
   only the `ITERATING` asset(s), confirm what stays `LOCKED` (`0 cr.`), and get
   a quick **"Go"** before calling `hf_guard.py` with cumulative
   `--round-cap <current_round_spent + approved_delta_cap>` (checked via
   `make budget-status`) and `--version <N>`.

## Budget & Lock Invariants

Enforced mechanically by `scripts/hf_guard.py` (never bypassed in prose):
- **Dual wall:** every `preflight` and `run` requires active `brief.md`
  (`Campaign cap`), `--round {R2,R3,R4,R4A,R4B,R5}`, and mandatory cumulative
  `--round-cap`.
- **Per-variant / per-version retries:** `--variant A|B|C` is allowed only when
  `--kind lookbook` (capped at `Lookbook variants`), and surgical re-rolls pass
  `--version <N>` (matched against `shotlist.json`), granting each option or
  version its own `1 + Max auto-retries/asset` attempts.
- **No CLI lock bypass:** `preflight` and `run` refuse `LOCKED` lookbook, still,
  video, and audio assets (`asset_locked`) and fail closed on corrupt
  `shotlist.json` or `receipts.jsonl`. There is no `--force-unlock` flag—only
  Root Producer edits `shotlist.json` (`LOCKED` → `ITERATING`, bumping `version`)
  after explicit Director approval and logs `Supersedes TL-<prev>` in
  `taste-log.md`.

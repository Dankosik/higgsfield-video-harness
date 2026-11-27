---
name: ad-script
description: Three-column commercial script with read-aloud budget and mute test. Use when writing a timed video ad script from a brief or premise, or auditing a draft script for pacing and sound-off comprehension.
---

## Process

1. **Lock inputs and route.**
   - Premise options requested: invoke `ad-concepts` and stop.
   - Existing draft script supplied: read [`draft-audit.md`](./draft-audit.md) and run that workflow instead of steps 2 to 5.
   - New script requested: ask once only if product or exact runtime is missing; when a direct brief omits a premise ("Write a 20-second ad for X"), commit to one **dramatic situation** passing the **swap test** and proceed.
   - **Exit gate**: four inputs are locked before step 2: exact runtime in seconds, product with one **single-minded proposition** (secondary claims parked out of scope), one **product-locked** **dramatic situation**, and any tone or **transferable mechanisms**.

2. **Build the Narrative Lock and timed visual spine first.**
   - Lock the 6-line **Narrative lock** (`Human truth`, `State shift`, `POV & narrative voice`, `Causal spine`, `2 + 2 rule`, `Primary misread risk`) per [`video-narrative`](../video-narrative/SKILL.md) before drafting rows.
   - Populate `Time` and `Video` from opening hook through physical proof and **brand entry** to closing **button** before writing any spoken line, verifying every beat transition links via **`BUT`** or **`THEREFORE`** (zero `AND THEN` slideshow rows).
   - Express every emotion and product claim as camera-observable reality (physical actions, objects, facial reactions, physical material/light transformations, kinetic silhouette contrast, environment, diegetic text).
   - **Exit gate**: `Narrative Lock` is complete, contiguous `MM:SS-MM:SS` beats sum strictly to target runtime with zero gaps or overlaps, every transition carries a `BUT`/`THEREFORE` link, every `Video` cell passes the camera-lens test (zero internal states, off-screen backstory, or abstract summaries), and physical proof plus **brand entry** land on or before the **button**.

3. **Layer Audio as counterpoint.**
   - Populate `Audio` (`## Format`) as **audio counterpoint**: every spoken line adds subtext, irony, rhythm, or a twist absent from `Video`. Replace any line that captions visible action with `SFX:` or an **earned pause** (`[PAUSE Ns]`).
   - **Zero-actor / sculptural / abstract motion spots:** Spots without dialogue or actors may run entirely `[visual/SFX only]` paired with sparse editorial supers (zero `VO:` or `CHARACTER:` lines), letting isolated tactile foley, silence turns, and rhythmic percussion carry counterpoint.
   - Place at least one **earned pause** or visual/SFX-only beat at the key reveal, reaction, or proof turn (omit only for declared patter).
   - **Exit gate**: zero captioning lines remain, and every silence or reaction hold carries an explicit `[PAUSE Ns]` duration.

4. **Audit the read-aloud budget.**
   - Pick a delivery tier from `## Cadence` and verify spoken pace **per beat** and **across the full spot** (for zero-spoken-word `[visual/SFX only]` spots, log `[visual/SFX only]` per beat and `0 spoken words`, `Verdict: PASS`):
     - Count spoken words only (`VO:` and `CHARACTER:`); exclude cue labels, `SFX:`, `MUSIC:`, and parenthetical delivery notes.
     - Subtract every `[PAUSE Ns]` and visual/SFX-only hold from beat duration to get net speaking seconds.
     - Check both words/sec and syllable density against the declared tier.
   - When any beat or total exceeds ceiling, cut spoken words while preserving **earned pauses**; adjust beat durations only when visual action needs more room.
   - **Exit gate**: every beat and the full spot sit at or under the stated cadence ceiling, all **earned pauses** remain intact, and cumulative timestamps still match target runtime.

5. **Run the mute test.**
   - Strip all spoken audio (`VO:` and `CHARACTER:`) and explanatory supers or cards.
   - Perform a blind read strictly of `Video` as written: state what a muted viewer learns about the product, cite the exact beat timecode(s) carrying physical proof (on zero-actor, sculptural, or abstract motion spots, physical material/light transformation or kinetic contrast carries the proof directly without leaning on supers), and separately list what lives only in `Audio`.
   - **Exit gate**: the **single-minded proposition** is provable strictly from the cited `Video` beats (`Verdict: PASS`). If any part of the core claim depends on spoken audio or explanatory copy, rewrite `Video` so physical action, material/light shift, or kinetic contrast carries the proof, then re-run step 4 before delivering.

## Cadence

- **Baseline conversational**: `<= 2.3 words/sec` in English, `<= 2.0 words/sec` in longer-word languages (Russian, German, etc.); `<= 4.5 syllables/sec` baseline ceiling across languages.
- **Deadpan or dramatic**: `<= 1.8 words/sec` (EN) / `<= 1.6 words/sec` (longer-word languages).
- **Deliberate patter**: up to `3.0 words/sec` (EN) / `2.6 words/sec` (longer-word languages); declare explicitly in Header.

## Format

1. **Header**: Product, **single-minded proposition**, exact runtime, **brand entry** timestamp, delivery cadence and wps ceiling.
2. **Narrative Lock**: the 6 meaning invariants from [`video-narrative`](../video-narrative/SKILL.md) (including explicit `BUT / THEREFORE` **Causal spine** and `Primary misread risk`).
3. **Three-column script** (Markdown table):

| Time | Video | Audio |
| --- | --- | --- |
| `0:00-0:03` | Camera-observable action | `VO:`, `CHARACTER:`, `SFX:`, `MUSIC:`, `[PAUSE Ns]` |

4. **Read-aloud budget**: per-beat lines (`0:00-0:03: 4w / 2.0s = 2.0 wps, [PAUSE 1s]` or `[visual/SFX only]`) plus totals (`spoken words`, `pause/visual-only sec`, `net speaking sec`, `overall wps`, `Verdict: PASS`).
5. **Mute test**: `Visual-only read` (citing proof beat timecodes and verifying `Primary misread risk` stays foreclosed), `Audio-only layer`, `Verdict: PASS`.

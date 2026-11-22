---
name: video-narrative
description: "Narrative architecture for commercials, brand films, product launches, shorts, and docs. Use when building a Narrative Lock, auditing BUT/THEREFORE causality, checking 0.1s instant-read semiotics, cutting filler beats, motivating camera/edit choices, or running a Blind Viewer Read."
---

# Video Narrative

Canonical owner of **narrative architecture** across commercials, brand films,
product launches, short films, documentaries, and social spots. Taste governs
*how it looks and sounds*; `video-consistency` governs *physical world
continuity*; **`video-narrative` governs how audiovisual facts build causal
meaning, viewer state shift, and unambiguous comprehension across cuts**.

## Reference Map

Load only the reference needed for the current task:

| Need | Reference |
| --- | --- |
| Runtime-scaled narrative structures (`6s`, `15s`, `20–30s`, `45–90s+`), protagonist modes (object/sensory zero-actor vs. human-POV vs. contrast vs. doc), `BUT / THEREFORE` examples, `2 + 2` pacing & Kuleshov cuts | [`references/narrative-structures.md`](references/narrative-structures.md) |
| Symptom-to-fix narrative diagnostics (`Primary Misread`, `AND THEN` slideshow, zero-delta filler, `0.1s` silhouette ambiguity, synthetic referent grouping, over-explaining, voice break, melodrama) | [`references/narrative-diagnostics.md`](references/narrative-diagnostics.md) |

## Core Narrative Laws

- **Four-layer separation (Narrative != Plot != Voiceover):**
  1. *Proposition / Theme* = what you want to say (a thesis, not a film).
  2. *Plot* = chronological sequence of events (`what happens`).
  3. *Narrative* = causal architecture, POV, viewer state shift, and information
     design (`why each beat forces the next and how the viewer assembles meaning`).
  4. *Taste / Craft* = optics, light, texture, pacing, and mix (`how it feels`).
  Narrative **never requires actors or narration**: in object or sensory spots,
  the **viewer's own cognitive/sensory state** is the protagonist.
- **Lock the 6-line `Narrative Lock` in `R1B`:** Pair `Narrative Lock` alongside
  `Continuity Lock` at the top of `script.md` and `storyboard.md` (and mirror it
  in `shotlist.json`'s `narrative_lock`):
  1. **Human truth:** one lived-in friction, desire, or physical reality a cold
     viewer recognizes instantly—never a synthetic ad-logic grouping.
  2. **State shift (`Before -> Turn -> After`):** the exact mental or sensory
     state entering the film, the observable pivot, and the state left behind.
  3. **POV & narrative voice:** whose eyes we watch through, tonal distance
     (intimate irony, architectural restraint, observational doc, kinetic wit),
     and the exact voice-breakers forbidden in copy or performance.
  4. **Causal spine (`BUT / THEREFORE`):** 3–5 story turns linked strictly by
     **`BUT`** (conflict/contrast/pivot) or **`THEREFORE`** (consequence)—zero
     **`AND THEN`** slideshow links.
  5. **`2 + 2` rule (earned subtext):** the conclusion left unsaid so the viewer
     completes it themselves; never caption visible action with VO, counters, or
     crutch closing lines.
  6. **Primary misread risk:** what a cold first-time viewer is most likely to
     mistake the video or product for (e.g., wrong category, hardware vs. software,
     parody), and the exact observable beat that forecloses that misread.
- **Per-shot `Narrative job` & Deletion Test (No-Filler Law):** Every shot
  (`S01..SN`) declares a `beat_function` (`hook`, `setup`, `tension`,
  `escalation`, `turn`, `proof`, `payoff`, `breath`, or `button`) and a
  one-line `delta` (*what shifts in the viewer's understanding by shot end*).
  Apply the **Deletion Test** in `R1B` (`0 cr.`): if deleting shot `S0X` leaves
  the causal chain and emotional turn intact, cut it before generating stills or
  motion—never shoot transitional walks or duplicate beats that stall momentum.
  Pair this with the **Shot-Density Law**: keep single-camera AI shots inside
  **`2.5–6.0s`** (`10–18` distinct shots/angles for a `45–60s` Short; `6–10` for
  a `30s` commercial) by adding reaction close-ups, reverse angles, or visual
  proof cutaways—never stretch `4–5` static drawings into `11–15s` talking-head
  loops.
- **`0.1s` Instant-Read Semiotics & Referent Cohesion (`R2`–`R3`):** Every
  meaning-bearing object, gesture, and wardrobe cue must read unmistakably in
  `<= 0.1s` on mute and on mobile screens without text labels (canonical
  silhouette, clear state—e.g., a switched-on architectural desk lamp rather
  than an ambiguous sculptural dome). Grouped objects/actions must belong
  cohesively to one believable real-world situation.
- **Narrative motivation of camera, light & edit (`R3`–`R5`):** Bind framing,
  camera stillness vs. movement, light shifts, and edit rhythm directly to each
  shot's `Narrative job`:
  - Lock the camera still (`Locked-off static tripod shot`) on proof/swap turns
    when the **subject change itself** carries the meaning.
  - Size `[PAUSE Ns]` holds in `video-assembly` to give the viewer's brain room
    to finish `2 + 2` before cutting, and let adjacent cuts generate Kuleshov
    meaning at the seam rather than explaining inside a single shot.
- **Blind Viewer Read (`R3` & `R4B` QC) vs. Director Taste:** In pre-Dailies QC
  ([`video-qa`](../video-qa/SKILL.md)), fresh `reviewer-agent` inspects
  `stills_strip.png`/`animatic.mp4` (`R3`) and `draft_cut.mp4` (`R4B`) cold
  (without builder rationales):
  1. Write a 2-line **cold viewer read** strictly from picture, visible text,
     and audio (*what happens, who/what this is, what category it reads as*).
  2. Audit strictly against the locked `Narrative Lock` and per-shot
     `Narrative job`, flagging objective breaks as **`NARRATIVE_DEFECT`**
     (`Primary Misread` triggered, `0.1s` unreadable object, zero-delta filler,
     broken `BUT/THEREFORE` seam, broken `2 + 2` over-explaining, or voice break).
  Creative taste and angle choice stay strictly with the Director—never judge
  whether an approved premise is "good," only whether the pixels deliver it.
- **Anti-melodrama guard:** Never inflate a crisp visual/tactile spot into a
  sentimental voiceover essay or forced human drama. Match narrative complexity
  strictly to runtime ([`references/narrative-structures.md`](references/narrative-structures.md)).

*Done when:* `Narrative Lock` is fixed with a verified `BUT / THEREFORE` spine
and explicit `Primary Misread Risk`, every shot passes the Deletion Test with a
distinct `Narrative job`, key objects pass `0.1s` instant-read and referent
cohesion before animation, and `R3`/`R4B` Blind Viewer Reads pass with zero
unresolved `NARRATIVE_DEFECT`s.

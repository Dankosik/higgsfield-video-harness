---
name: ad-storyboard
description: Storyboard a commercial script into a continuity-locked shot list for filming or video generation. Use when turning a timed script into numbered shots, or auditing visual continuity across cuts in an existing shot list.
---

## Process

1. **Gate the input and map script constraints.**
   - **Untimed idea**: stop here and offer to lock a timed script first (invoke `ad-script` if the user agrees). Proceed only once a timed script exists or the user explicitly overrides to storyboard from rough beats.
   - **Existing shot list**: extract the implicit **Continuity lock** from the supplied shots, then jump to steps 4 and 5 to report exact seam breaks, runtime errors, and unflagged hazards before offering a repaired shot list.
   - **Timed script**: extract exact target runtime (`0:00-0:XX`), **brand entry**, product proof beats, **earned pauses** (`[PAUSE Ns]`), and closing **button**; resolve any missing timestamps, duration mismatches, or unfilmable Video lines before step 2.

2. **Establish the Narrative lock and Continuity lock.** Carry the 6-line **Narrative lock** from `script.md` (per [`video-narrative`](../video-narrative/SKILL.md)) and fix all three physical cross-shot invariants once at the top using concrete physical anchors verifiable on a single frame:
   - **Product / Props**: physical form, finish, label/logo facing, explicit scale anchor against hands or fixtures (to prevent scale drift), and hero angle.
   - **Lighting and palette**: fixed key light side (`screen left`, `screen right`, `overhead`, or `back` relative to the primary axis), light quality (hard/soft), color temperature, and palette anchors.
   - **Space, cast, and axis**: absolute 4-wall Spatial Map (`North / East / South / West` fixtures and primary light source—never solely camera-relative left/right, which flip on reverse angles), cast markers (wardrobe, hair, accessories, active hand), screen-left/screen-right starting positions, screen direction, and **180-degree axis**. Name per-shot camera position and facing wall whenever coverage changes angle or crosses into a reverse shot. For **zero-actor / sculptural / abstract motion** spots, replace empty cast/wardrobe/eyeline fields with **Material & Surface Spec** (substrate finish, micro-texture, specular/refraction behavior, mirrored HEX palette) and **Transition Mechanic**.

3. **Break beats into numbered shots (`S01`, `S02`, ...)** following `Output format` below. Give each distinct visual beat or reaction its own shot, decoupled from script row boundaries, governed by four craft rules:
   - **Focal entry and eye-trace**: name the single element and frame zone the eye hits in the first half-second, placing the next shot's **focal entry** near the outgoing `End frame` focus unless deliberately jolting attention. Reserve `CU`/`ECU`/`Insert` for physical proof or turns.
   - **Observable keyframe continuity**: write `Start frame`, `Action`, and `End frame` strictly in observable camera reality so each following `Start frame` picks up the exact physical state left by the previous `End frame` and `Cut trigger`. Mark ultra-fast `< 0.5s` studio-plate shots (`<= 12 frames @ 24fps` on a locked BPM grid) as **`still_only`** (`0` video cr., assembled from multi-angle `2K` stills without burning video credits — see [Motion & Abstract Direction](../video-direction/references/motion-and-abstract.md)).
   - **Earned camera moves**: default to a static hold (`Locked-off static tripod shot`) whenever in-frame action carries the beat; state the specific reveal or pacing job for every pan, push, or tracking move, keeping one dominant camera move per shot, one coherent lens family per location, and parallax-accurate 3D verbs (`Dolly`/`Truck`/`Crane` vs. `Zoom`/`Pan`/`Tilt`) per [Camera Control](../video-direction/references/camera-control.md).
   - **Motivated cuts and 30-degree rule**: cut on a **motivated cut** (**cut-on-action**, **eyeline match**, or **audio cut** / **J-cut** / **L-cut**), changing shot scale (`WS`/`MS`/`MCU`/`CU`/`ECU`/`Insert`) or shifting camera angle by at least 30 degrees across consecutive shots of the same subject (reserve jump cuts for explicit comedic or kinetic beats).
   Map every script second, spoken line, `SFX`, and `[PAUSE Ns]` verbatim into `Audio sync` before step 4.

4. **Flag risky shots with a test-take check.** Attach a **test-take check** exclusively to shots carrying execution risk (hand-to-product grip, liquid or physics motion, legible label or UI text, reflections, tight comic timing, multi-subject blocking), naming both the exact failure mode and the observable pass check for a short trial take. Leave routine shots unflagged so every check stays high-signal.

5. **Run a cut-by-cut continuity audit and repair breaks.** Walk every adjacent seam (`S01 -> S02`, `S02 -> S03`, ...):
   - Sum shot durations explicitly (`S01 + S02 + ... = target`) with contiguous timestamps matching the exact target runtime, and verify spoken lines fit inside their spanning shot durations.
   - **Audit every seam and run the Deletion test:** audit every seam against the **Continuity lock** (product state/label, key light side, cast/wardrobe, active hand, screen direction, **180-degree axis**), **30-degree rule**, and `End frame -> Start frame` physical handoff, and run [`video-narrative`](../video-narrative/SKILL.md)'s **Deletion test** on every shot (cut any zero-delta filler shot whose removal leaves the **Causal spine** and turn intact).
   - Confirm product proof and the closing **button** hold long enough to read cleanly (at least 1.5-2.0s on legible packaging or copy, matching the script beat).
   - Repair any failing shot directly in the shot list before finalizing so every seam passes.

## Output format

1. **Narrative Lock** & **Continuity Lock**: the 6 meaning invariants plus the three physical locks from step 2.
2. **Shot list**: numbered entries (`S01`, `S02`, ...):
   - **Header**: `S01 | 0:00-0:03 (3.0s) | Shot scale, angle, camera (static hold or motivated move + job; append `still_only` for `< 0.5s` `0` video-cr. studio plates)`
   - **Narrative job**: `beat_function` (`hook`/`setup`/`tension`/`escalation`/`turn`/`proof`/`payoff`/`breath`/`button`) + viewer information/feeling delta
   - **Focal entry**: element and frame zone
   - **Start frame**: opening visual state
   - **Action**: observable movement across the shot *(or static studio-plate read on `still_only` cuts)*
   - **End frame**: outgoing visual state on the cut
   - **Cut trigger**: **motivated cut** type and exact cue
   - **Audio sync**: verbatim VO/dialogue (with J-cut/L-cut carry), `SFX`, or `[PAUSE Ns]`
   - **Continuity carry**: active hand, prop state, light side, and eyeline/screen direction bridged across neighbors — or, for zero-actor / abstract motion shots, **Material & Surface Spec** and **Transition Mechanic** (`Sub-0.5s 2K Still Montage`, `Pixel-Locked Surgical Finish Swap`, `Silhouette Match Cut ±5%`, `FLF Morph Bridge`, `In-Camera Wipe`)
   - **Test-take check** *(risky shots only)*: failure mode + observable pass check
3. **Cut-by-cut continuity audit**: explicit duration arithmetic (`S01 + S02 + ... = target`), one line per adjacent seam (`S01 -> S02`, ...) confirming lock compliance and handoff, proof/button hold verification, and highest-risk seams.

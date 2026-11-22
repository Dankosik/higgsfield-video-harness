---
name: video-assembly
description: "FFmpeg assembly, R3 still animatics, VO timing, and R4/R5 mastering. Use when building still animatics, checking VO windows, cutting FPS-locked clips, mixing to -14 LUFS, applying LUT/grain finishing, exporting stems, or choosing FFmpeg vs. Remotion."
---

# Video Assembly

Canonical owner of `R3` zero-video-credit still animatics, `R4`/`R5` FPS-locked
FFmpeg editing, VO timing validation, the Audio Level Law, `-14 LUFS` mastering,
finishing unification (`LUT` / `GRAIN`), unbaked `stems/`, and the FFmpeg vs.
Remotion compositor boundary.

## `R3` Zero-Video-Credit Still Animatic

Before requesting `R4` motion budget, record `still.selected_take` (and audio
`selected_file`) in `shotlist.json` and run `make animatic CAMPAIGN=<slug>`
(`scripts/assemble.sh --animatic`). Verify `ad-script`'s **mute test**
([Ad Craft Glossary](../../../docs/ad-craft-glossary.md)) first, then layer VO
and rough music so the Director judges framing, voice cadence, and cut rhythm
before spending video credits.

## `R4` / `R5` FPS Lock, Partial-Take Harvesting & Re-Encoded Assembly

- **Never bypass `scripts/assemble.sh` with ad-hoc FFmpeg scripts or mid-scene
  `xfade`/`fadewhite` dissolves on live-action cuts** (dissolves create
  double-exposed AI-slideshow artifacts; use motivated hard cuts or in-camera
  transitions, reserving `fade_out_black_s` strictly for endcard/black tails).
- **Per-shot editing in `shotlist.json` (`shots[].edit`):**
  - `source_clip` + `trim_in` / `trim_out` — **Partial-Take Harvesting** (slice
    the cleanest 2–4s windows out of `batch=2–4` or `15–30s` `Seedance 2.5`
    takes, and trim weak 1–2s handles cleanly).
  - `crop_4k_punchin` (`center_2x` / `left_2x` / `right_2x` / `w:h:x:y`) — pull
    a crisp `1080p` close-up out of a native `4K` wide take at `0 cr.`
  - `grade` (`brightness`, `contrast`, `saturation`, `gamma`, `wb_r`, `wb_b`) —
    per-shot pre-LUT exposure/WB matching so different scenes/engines unify
    before the shared `--lut`.
  - `fade_out_black_s` (`<= 2.0s`) — clean end-of-shot fade to black (endcard).
- `scripts/assemble.sh` locks clips to `shotlist.json`'s `fps_target` (falling
  back to Clip 1's probed FPS when omitted), scales with `flags=lanczos`, and
  warns whenever clip resolutions or native FPS diverge across inputs (fix
  `1918×1080` upscales or `30fps` takes in a `24fps` cut at the source rather
  than masking with pillarbox padding or pulldown judder). Pass `--bpm <N>` to
  verify alignment against an absolute musical clock (when edits add frames,
  extend music by repeating whole beats on-beat rather than regenerating).
- Pass `OUT=campaigns/<slug>/media/exports/draft_cut.mp4` during `R4B`
  (`make assemble` defaults to `master.mp4`).
- Honor `storyboard.md`'s `Cut trigger` (`cut-on-action`, `J-cut`, `L-cut`),
  Kuleshov seam meaning, and `[PAUSE Ns]` holds (giving viewers `1.5–2.5s` on
  key turns to complete `2 + 2` per
  [`video-narrative`](../video-narrative/SKILL.md)), and re-encode inside
  `assemble.sh` (`libx264 -crf 18 -pix_fmt yuv420p -g 30`, `aac 192k 48kHz
  stereo`) rather than `-c copy` concat to prevent cut freezes and A/V desync.

## VO Timing, Dialogue Cadence, Audio Level Law & `-14 LUFS` Mastering

- Measure VO bounds and cadence with `scripts/qa_media.py voice <wav> --window
  <sec> --json` (`make qa-voice`); when speech overflows its window, rewrite
  copy and regenerate instead of speeding up with `atempo`.
- **Dialogue Cadence & Turn-Taking Rules (avoid robotic gaps):**
  - Check `speech_start` and `internal_pauses` in `qa_media.py voice`: shave
    dead leading/trailing TTS silence (`>= 0.25s`) via
    `audio.voiceover.tracks[].trim_start_s` / `trim_end_s` in `shotlist.json`,
    and tighten punctuation or regenerate when mid-sentence TTS pauses exceed
    `0.40s` in fast-paced Shorts/comedy.
  - Never add a uniform mechanical `+0.15s` delay after every visual cut (which
    compounds with trailing WAV tails into stiff `0.30s+` speaker gaps shorter
    than mid-sentence breaths): use crisp `0.00–0.12s` handoffs or `-0.10` to
    `-0.20s` **J-cut audio lead-ins** (supported natively via overlapping
    `start_s` in `audio.voiceover.tracks[]`) for punchy dialogue, reserving
    `0.35–0.65s` silences strictly for intentional dramatic or comedic beats.
- Enforce the **Audio Level Law**: VO at `1.0` (`0 dB`), diegetic SFX `<= 0.20`,
  music `<= 0.16` under VO (`<= 0.35` music-only). Pass `DUCK_MUSIC=1`
  (`--duck-music`) to gently sidechain-duck the music bed whenever VO speaks.
- Master via two-pass `loudnorm=I=-14:TP=-1.5:LRA=11` so `make qa-render` passes
  `-14 LUFS (±1.0 LU)` and `<= -1.0 dBTP`.

## Stems, Finishing Unification & Post-LUT Overlays

- Every `make assemble` exports clean unbaked `media/exports/stems/`
  (`video_only.mp4`, `diegetic.wav`, `vo.wav`, `music.wav`, normalized clips).
- **Finishing unification:** When blending native `1080p` footage across engines
  or polishing a theatrical cut, balance per-shot `shots[].edit.grade`, then
  apply a shared 3D LUT and subtle temporal 35mm grain directly at `0 cr.` via
  `make assemble CAMPAIGN=<slug> LUT=<grade.cube> GRAIN=4 [OVERLAY=campaigns/<slug>/media/work/overlay.mov] [DUCK_MUSIC=1]`,
  OR grade exported `stems/` in DaVinci Resolve (optionally expanding
  `1920×1080` clips via `topaz_hyperion_2_5` 10-bit ProRes/EXR first; see
  [Mastering & Upscaling](../higgsfield-cli/references/mastering-and-upscaling.md)).
- **FFmpeg vs. Remotion/AE & Temp-File Hygiene:** Stay on pure FFmpeg by
  default; cross into
  [`hybrid-motion-graphics`](../hybrid-motion-graphics/SKILL.md) (Remotion /
  After Effects / HTML Design Sheet) when `brief.md` requires animated kinetic
  typography, captions, or crisp brand UI overlays. Always write intermediate
  `1080p` ProRes 4444 overlays (`overlay.mov`) into **`media/work/`** (never
  `media/exports/`) so gigabyte temp renders stay separate from final client
  deliverables, and composite **after** LUT/grain via `--overlay`.

*Done when:* `animatic.mp4` (`R3`), `draft_cut.mp4` (`R4B`), or `master.mp4` +
`stems/` (`R5`) builds cleanly with uniform FPS/resolution, VO fits without
`atempo`, and `make qa-render` passes `-14 LUFS (±1.0 LU)` and `<= -1.0 dBTP`.

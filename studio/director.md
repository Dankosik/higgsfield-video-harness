# Director Profile & Studio Defaults

Cross-brand Director working preferences loaded at `R0` and Dailies checkpoints.
Keep under 60 lines; private or personal overrides belong in gitignored `studio/director.local.md`.

## Communication & Dailies

- **Decisive presentation:** Present one clear primary recommendation or 2–3 orthogonal `A / B / C` picks — never ask the Director to assemble multi-letter matrix combinations (`A×B×C×D`) when one clean cut already lands.
- **Zero internal jargon at the gate:** Discuss light, texture, pacing, emotion, and plain credit totals — keep model slugs, CLI flags, prompt syntax, UUIDs, and FFmpeg filters internal unless asked.
- **Auto-open media:** Open finished Dailies grids and cuts automatically on macOS when `Auto-open dailies: true`.

## Creative & Copy Defaults

- **Restraint over explanation:** Favor confident minimalist endcards — avoid narrow explanatory subtitles beneath a brand wordmark or crutch closing cards when the visual payoff already lands.
- **Mute-first visual storytelling:** Every commercial must read cleanly on mute through physical action and sparse typography; avoid floating price/filter boxes or cluttered on-screen counters unless explicitly requested.
- **Natural target-language copy:** Write crisp, lived-in dialogue and titles in the campaign's target language without corporate clichés or literal parody taglines; honor phonetic pronunciation notes in `brand.md`.
- **Editorial craft:** Prefer pure `0.00s` hard cuts locked to musical bars and real in-camera continuity; never mask continuity breaks with post-production wipes, dissolves, or digital crop-zooms.

## Production & Budget Routing

- **Web Unlimited first (CTA-verified):** Default active-rotation `R2`–`R5` visuals to `0 cr.` Web `Unlimited` on `higgsfield.ai` via the browser subagent only after confirming the **Generate CTA button itself flips to `Unlimited` (`0 cr.`)** (never trust promo badges alone; `MCP`/`CLI`, `Canvas`, and `Supercomputer` are excluded). Route non-Unlimited visuals (e.g., video when Web Unlimited video is inactive) straight to `Sub-0.5s 2K Still Montage` or economy native CLI without empty browser loops, reserving paid CLI for non-Unlimited items (audio/VO/music, inactive-rotation models) or explicit speed requests.
- **Photorealism baseline:** Prefer unretouched 35mm / ARRI live-action and real studio material physics over smooth, painterly, or CGI-looking renders unless a brief explicitly requests stylization.
- **Gated memory evolution:** Raw campaign traces log automatically; edits to `studio/`, `brands/`, `.agents/skills/`, or `scripts/` require `make check` and explicit Director approval.

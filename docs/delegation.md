# Delegation & Internal QC

Keep every actor in the **Smart Zone**: one coherent outcome, bounded files,
primary artifacts (`brief.md`, compiled `taste-active.md` / `taste-log.md`,
`style-bible.md`, `shotlist.json`), and fresh history (`fork_turns: "none"`
where supported). Keep the **Root Producer** in one continuous session across
`R0`–`R5` so the Director's verbatim *why* stays a primary source; delegate AFK
parallel craft and unbiased QC to fresh subagents.

## Roles & Ownership

Four reusable role definitions live in [`.agents/roles/`](../.agents/roles)
(pre-wired for Codex Multi-Agent V2 in [`.codex/config.toml`](../.codex/config.toml)
with a 20-thread session ceiling, and directly mappable in any subagent-capable
agent harness; reserve thread slots for Visual Critic QC and recovery):

| Role | Effort | Owns |
| --- | --- | --- |
| `evidence-agent` | `low` | Read-only live Higgsfield schemas, `generate cost`, account/workspace checks, `brands/` & photo discovery, `ffprobe`/`receipts.jsonl` reduction |
| `specialist-agent` | `high` | Read-only narrative architecture (`Narrative Lock`), contrasting concepts, 3-column scripts, continuity-locked storyboards, prompt architecture, anti-IP rewrites |
| `worker-agent` | `medium` | Mutable leaf execution for one Lookbook entity, still, clip, audio stem, or assembly unit inside disjoint paths via `hf_guard.py`, `qa_media.py`, `assemble.sh` |
| `reviewer-agent` | `high` | Fresh read-only pre-Dailies Visual Critic (vision inspection) filtering technical defects, continuity breaks, `TASTE_REGRESSION`s, and `NARRATIVE_DEFECT`s (Blind Viewer Read) |

- **Disjoint asset paths (no Git worktrees for binaries):** parallel workers
  write strictly to assigned paths (`media/lookbook/{characters,locations,props}/*`,
  `media/stills/sNN-*`, `media/shots/sNN-*`, `media/audio/*`, `media/exports/*`,
  `prompts/<id>_*`, `qc/<id>-*`). Only the **Root Producer** edits `brief.md`,
  `taste-log.md`, `taste-active.md`, and `shotlist.json`. `hf_guard.py`
  serializes `receipts.jsonl` (paid CLI, `upload`, and `0 cr.` `log-web` traces)
  under `flock`, and `qa_media.py log-review` serializes `qc/review-log.jsonl`
  under `flock`.
- **Freshness & reuse:** start every subagent with fresh history
  (`fork_turns: "none"` where supported—no parent chat turns or builder
  rationales). Reuse a `worker-agent` only for bounded repair inside its
  unchanged asset, writable paths, and `--round-cap`; spawn a fresh actor when
  `version` bumps, scope changes, or independent QC runs.
- **Vision & tool boundaries:** inspect `lookbook.png`, stills, `3x2` contact
  sheets, and `R5`/upscale `1:1` `--crops` strips via `view_image` (or your
  harness's native image-reading tool), **and watch actual `.mp4` playback via
  `read_file` on video clips and assembled cuts** so temporal stutters and
  artifacts are never missed; run `open <artifact>` on macOS before posting
  Dailies when `Auto-open dailies: true`. Run all paid campaign jobs through
  `hf_guard.py` on `higgsfield` CLI, keeping MCP read-only.

## Pre-Dailies Visual Critic

Before assembling any Dailies Packet for generated media (`R2`–`R5`), spawn a
fresh read-only `reviewer-agent` (`fork_turns: "none"`) — **never self-grade
inside the Root Producer turn** — with primary inputs only (`brief.md`,
compiled `taste-active.md` or `taste-log.md`, `shotlist.json`, `qa_media.py
--json` reports including temporal stutter/jerk and cross-cut luma/bitrate
metrics, reference photos, `lookbook.png`/stills/`3x2` contact sheets, actual
`.mp4` video clips or pre-sliced `<= 20s` `qc/verify_slices/part_*.mp4` master
segments via `read_file`, plus `1:1` unscaled `--crops` strips and
`qa_media.py batch --strict --json` for `R5` masters) — zero builder rationale.
Log every returned `#review-result` via `scripts/qa_media.py log-review`
(passing `--qa-report`, `--sheet`, `--crops` for `R5`, and `--reviewer-id`;
`R4`/`R5` `PASS` fails closed without proof files) so `R6` (`studio-retro`) can
mine real defect patterns.

- **Fast bounded review handoff (`<= 12` tool calls, parallel batches):** For
  masters `> 20s`, always run `qa_media.py render --verify-slices-dir
  campaigns/<slug>/qc/verify_slices` first and hand exact paths to
  `reviewer-agent` so it batches text/JSON/PNGs (up to 5–6 per turn) and reads
  **at most 2 `.mp4` files per turn** (preventing context compaction and
  re-reads) instead of running ad-hoc shell/Python slicing scripts. Parallelize
  per-clip `R5` reviews (1–3 clips per lane) and never spawn redundant
  duplicate reviewers on clips that already passed.

- **Filter defects, leave taste to the Director:** score strictly with the
  binary rubric in [`video-qa`](../.agents/skills/video-qa/SKILL.md) using the
  `#review-result` defect classes below (including `R3`/`R4B` **Blind Viewer
  Read** against `Narrative Lock` per
  [`video-narrative`](../.agents/skills/video-narrative/SKILL.md)). Leave
  creative picks and `LOCKED` sign-off solely to the Director.
- **Fail closed on missing proof:** return `REVIEW_HANDOFF_INVALID` whenever
  required `qa_media.py` JSON, `taste-log.md`, contact sheets, `R5` `1:1`
  `--crops` strips, or `R5` `batch --strict` reports are missing.
- **Honest escalation:** fix root causes inside `Max auto-retries/asset` and
  `--round-cap` (tighten anchors, adjust motion beats, sanitize IP phrasing).
  When retries or round cap exhaust, surface any surviving borderline `CONCERN`
  openly in one line of Dailies for the Director's call.

## Parent-Owned Recovery

Technical obstacles belong to the Root Producer, never the Director:
- **Zero double-spend on timeouts & downloads:** `hf_guard.py` keeps timed-out
  or ambiguous jobs `in_progress` (resuming via `generate get`/`wait`/`list` or
  `soul-id get`/`wait`) and retries local `download_failed` saves without
  re-submitting. Reconcile `receipts.jsonl` with `higgsfield generate list --json`
  (or `soul-id list --json`) before replacing a stalled worker or clearing
  `reservation_in_flight`.
- **Fix root causes, stop at hard walls:** diagnose the cause before each retry
  (rewrite prompts positively on `ip_detected`, tighten anchors on drift, adjust
  beats) rather than repeating identical inputs. On `BUDGET_CAP`,
  `asset_locked`, `retry_limit_exceeded`, `variant_limit_exceeded`,
  `reservation_in_flight`, or repeated `POLICY_BLOCK`, workers return
  `NEEDS_PARENT` immediately.

## Output Envelopes

### Evidence Result
```text
question: <read-only discovery question>
commands_run: <exact CLI or probe commands>
locators: <paths, model/workflow IDs, receipt ranges>
findings: <exact JSON excerpts, live generate cost, or media metrics>
gaps: <none | missing file, auth gap, or unavailable schema field>
```

### Specialist Result
```text
angle: <concept | script | storyboard | lookbook contrast | prompt repair | anti-IP>
taste_anchors: <TL-NN IDs and LOCKED asset IDs honored>
proposal: <creative options, script/storyboard draft, or prompt text>
tradeoffs: <visual, pacing, or cost trade-off>
gaps: <none | missing brief.md truth or upstream asset>
```

### Worker Result
```text
round: <R2 | R3 | R4 | R4A | R4B | R5>
asset_id: <lookbook id | sNN.still | sNN.video | audio | export>
status: DONE | NEEDS_PARENT
outputs: <media, prompt, and QC paths written inside disjoint scope>
receipts: <reservation_id, job_id or upload_id, credits, attempt>
qa_summary: <qa_media.py JSON summary, contact-sheet/lookbook path, and R5/upscale 1:1 --crops path>
blocker: <none | BUDGET_CAP | asset_locked | POLICY_BLOCK | retry_limit_exceeded | variant_limit_exceeded | reservation_in_flight | error>
```

### Review Result
```text
candidate: <round and exact asset/sheet paths inspected>
verdict: PASS | CONCERNS | FAIL | REVIEW_HANDOFF_INVALID
findings: <anchor, defect class (MEDIA_TECH_DEFECT | VISUAL_DRIFT_DEFECT | TASTE_REGRESSION | CONTINUITY_DEFECT | NARRATIVE_DEFECT | POLICY_BLOCK | BUDGET_CAP | CONCERN | FOLLOW_UP), impact, or none>
evidence_boundary: <files, qa_media.py reports, and images inspected via view_image>
reopen_owner: <Worker(<asset_id>) | Root Producer | none>
```

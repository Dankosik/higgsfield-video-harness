# Studio Engine Memory (ACE Playbook)

Empirical model and pipeline observations tracked with ACE delta counters (`helpful` / `harmful`),
absolute verification dates (`YYYY-MM-DD`), and lifecycle status (`active`, `stale`, `graduated_to_code`, `archived`).
Keep under 120 lines; `scripts/check-memory.py` flags `active` rules older than 60 days for re-verification.

## Image & Video Models

- [ENG-01] model=bytedance_video_upscale | helpful=0 | harmful=3 | verified=2026-11-20 | status=graduated_to_code
  Upscaling `< 1 Mbps` `480p` drafts to `1080p` creates bright edge halos, muddy faces, `1.4x–2.0x` Laplacian oversharpening, and temporal shimmer. Always master flagship hero shots in native `1080p`; enforced by `qa_media.py batch --strict`, `--crops`, and `check-campaign.py`.
  Evidence: `git:77c9fd7`, `.agents/skills/higgsfield-cli/references/mastering-and-upscaling.md`

- [ENG-02] model=seedream_5_5 | helpful=5 | harmful=0 | verified=2026-11-21 | status=active
  Delivers unretouched 35mm / ARRI live-action skin, fabric, and architectural stone textures without painterly smoothing; strong primary anchor for `R2`/`R3` photorealistic stills (including `Seedream 5.0 Pro` on Web Unlimited).
  Evidence: `.agents/skills/higgsfield-cli/references/model-selection.md`

- [ENG-03] model=gpt_image_2_6 | helpful=0 | harmful=2 | verified=2026-11-20 | status=active
  Tends toward smoothed, painterly/illustrated skin and interior surfaces with heavy orange-vs-blue contrast on residential interiors; avoid for photorealistic live-action commercials.
  Evidence: `.agents/skills/higgsfield-cli/references/model-selection.md`

- [ENG-04] model=wan3_0 | helpful=4 | harmful=0 | verified=2026-11-20 | status=active
  Native `1920x1080` renders hold clean facial and fabric temporal stability without upscaler shimmer at economy CLI fallback pricing; pairs cleanly with `cinematic_studio_video_4_0` after per-shot color matching and shared `grain=2.0`.
  Evidence: `.agents/skills/higgsfield-cli/references/mastering-and-upscaling.md`

- [ENG-05] model=cinematic_studio_video_4_0 | helpful=3 | harmful=1 | verified=2026-11-20 | status=active
  Strong flagship native `1080p` hero motion and multi-beat choreography (`omni_reference`), but can output slightly lifted shadows and lower saturation vs. `wan3_0`; unify contrast and white balance per shot before applying a shared 3D LUT.
  Evidence: `.agents/skills/video-assembly/SKILL.md`

## Channels & Finishing Pipelines

- [ENG-06] model=higgsfield_web_unlimited | helpful=6 | harmful=0 | verified=2026-11-22 | status=active
  Default `0 cr.` visual channel on Unlimited-eligible plans; confirm the UI shows `Unlimited` ON / `0 credits` before queuing and log every run via `scripts/hf_guard.py log-web`. Note: some `Ultra` plans are **image-only Unlimited** (video toggle redirects to `/market#image-unlimited`); check once per session and cache so video rounds stop re-probing.
  Evidence: `.agents/skills/higgsfield-cli/references/model-selection.md`

- [ENG-07] model=remotion_prores4444_endcard | helpful=2 | harmful=0 | verified=2026-11-20 | status=active
  Export transparent brand wordmark/endcards as `1080p` ProRes 4444 (`yuva444p10le`) and composite them **after** creative 3D LUT grading (`assemble.sh --overlay`) so exact brand colors and typography never shift.
  Evidence: `.agents/skills/video-assembly/SKILL.md`

- [ENG-08] model=seedance_2_5 | helpful=5 | harmful=0 | verified=2026-11-22 | status=active
  Latent `480p` drafting (`--draft true`, ~3 cr./s) escalated natively via `--draft_job_id` to `1080p`/`4k` cuts multi-take iteration spend ~64% without pixel-upscale halos; native `4k` also enables clean 2x `1080p` punch-in crops via `assemble.sh`.
  Evidence: `.agents/skills/higgsfield-cli/references/model-selection.md`

- [ENG-09] model=seedance_2_0_mini | helpful=0 | harmful=3 | verified=2026-11-22 | status=active
  Mixing economy `mini`/`flash` video drafts (`seedance_2_0_mini`, `kling_4_0_flash`) or disparate engines (`veo3_1_lite` 2.7 Mbps next to `veo3_1` 61 Mbps) on flagship live-action commercials causes severe AI sheen, physics warp, and cross-cut bitrate disparity; stick to one flagship engine per live-action block.
  Evidence: `.agents/skills/higgsfield-cli/references/model-selection.md`

- [ENG-10] model=flux_3_image | helpful=3 | harmful=0 | verified=2026-11-22 | status=active
  Paired with uploaded real location reference photographs in `R0`/`R3`, `flux_3_image` and `seedream_5_5` eliminate postcard HDR sheen and hold authentic unretouched 35mm documentary color science on live-action scenes.
  Evidence: `.agents/skills/higgsfield-cli/references/model-selection.md`

- [ENG-11] model=kling3_0 | helpful=2 | harmful=2 | verified=2026-11-22 | status=active
  `kling3_0 --mode pro --sound off` (`~1.75 cr./s`) works well for short (`3–6s`) stylized 2D/3D/animal action, silent acting under off-screen VO, and reaction cutaways (direct natural closed-mouth expressions so mouths do not flap accidentally), but drifts past `8s` (warped paws/hands, crawling backgrounds, ear morphs) and should not be used for visible on-camera speaking faces where audio-driven lip-sync (`intone` / Lipsync Studio / native-speech models) is needed.
  Evidence: `.agents/skills/higgsfield-cli/references/model-selection.md`

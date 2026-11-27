#!/usr/bin/env python3
"""Static structural validator for Feedback-Loop Studio campaigns (brief.md + taste-log.md + shotlist.json)."""

from __future__ import annotations

import sys

sys.dont_write_bytecode = True

import argparse
import importlib.util
import json
import math
import re
from pathlib import Path
from typing import Any

VALID_ASSET_STATUSES = ("DRAFT", "IN_REVIEW", "ITERATING", "LOCKED")
VALID_ASSET_STATUS_SET = frozenset(VALID_ASSET_STATUSES)
VALID_LOOKBOOK_KINDS = frozenset({"character", "object", "location", "outfit"})
VALID_PRODUCTION_TRACKS = frozenset(
    {
        "scratch_cinema",
        "v2v_one_take",
        "previz_3d_vfx",
        "performance_ads",
        "hybrid_motion_launch",
        "youtube_and_clipping",
    }
)
VALID_SUB_FLOWS = frozenset(
    {
        "remotion_overlays",
        "vfx_hero_shot",
        "v2v_rescue_or_recam",
        "shorts_cutdown",
    }
)
PROMPT_TIME_RANGE_RE = re.compile(
    r"(?<!\d)(\d+(?:\.\d+)?)\s*[-–—]\s*(\d+(?:\.\d+)?)\s*s\b",
    re.IGNORECASE,
)
VALID_BEAT_FUNCTIONS = frozenset(
    {
        "hook",
        "setup",
        "tension",
        "escalation",
        "turn",
        "proof",
        "payoff",
        "breath",
        "button",
    }
)
NARRATIVE_LOCK_FIELDS = (
    "human_truth",
    "state_shift",
    "pov_and_voice",
    "causal_spine",
    "subtext_2_plus_2",
    "primary_misread_risk",
)
VALID_CS4_MODES = frozenset({"t2v", "omni_reference", "video_edit", "video_extension"})
VALID_CS35_CAMERA_STYLES = frozenset(
    {
        "classic_static",
        "silent_machine",
        "one_take",
        "epic_scale",
        "intimate_observer",
        "impossible_camera",
        "documentary_snap",
        "raw_chaos",
        "dreamy_flow",
    }
)
VALID_CS30_SPEEDRAMPS = frozenset(
    {
        "auto",
        "linear",
        "slowmo",
        "speedup",
        "fast_to_slowmo",
        "slowmo_to_fast",
        "super_slowmo",
        "impact",
    }
)
VALID_CS2_SPEEDRAMPS = frozenset({"auto", "custom", "linear", "slowmo", "speedup", "impact"})
STILL_HARD_REF_CAPS = {
    "text2image_soul_v2": 1,
    "soul_cinematic": 1,
    "cinematic_studio_image": 4,
    "flux_kontext": 4,
    "seedream_v5_pro": 10,
    "seedream_5_5": 10,
    "kling_image_4_0": 10,
    "kling_omni_image": 10,
    "3d_jutsu_angles": 10,
    "nano_banana_pro": 14,
    "nano_banana_2_1": 14,
}
VIDEO_HARD_IMG_CAPS = {
    "seedance_2_0": 9,
    "seedance_2_0_mini": 9,
    "kling4_0": 10,
    "kling_4_0_flash": 10,
    "flux_3_video": 10,
    "seedance_2_5": 30,
    "cinematic_studio_video_4_0": 30,
}
VALID_MSV2_SINGLE_IMAGE_TYPES = frozenset({"2d_motion", "hypermotion", "mixed_media"})
ENG08_DRIFT_PHRASES = (
    "breathing daylight",
    "gliding caustic",
    "caustic shimmer",
    "drifting light",
    "moving shadow",
    "gliding light",
)
ENG08_NEGATION_RE = re.compile(
    r"(?:^|[\s,(;/:-])(?:zero|no|without|forbid(?:s|ding)?)[ \t:]+(?:(?:any|subtle|visible|watery)[ \t]+)?$"
)
FENCE_RE = re.compile(r"^\s*(`{3,}|~{3,})")

STEERING_BULLET_RE = re.compile(
    r"^(\s*)[-*]\s+(?:\*\*|__)?"
    r"(Approved\s*/\s*LOCKED|More\s+of|Change\s*/\s*Steer|Never)"
    r"(?:\*\*|__)?\s*:\s*(?:\*\*|__)?\s*(.*)$",
    re.IGNORECASE,
)


def _load_sibling_module(filename: str, mod_name: str):
    mod_path = Path(__file__).resolve().with_name(filename)
    spec = importlib.util.spec_from_file_location(mod_name, mod_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load sibling module: {mod_path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_CHECK_BRIEF = _load_sibling_module("check-brief.py", "check_brief")
_MEMORY_COMPILE = _load_sibling_module("memory_compile.py", "memory_compile")


def _clean_num(val: float) -> int | float:
    return int(val) if float(val).is_integer() else round(val, 2)


def _is_valid_version(val: Any) -> bool:
    return isinstance(val, int) and not isinstance(val, bool) and val >= 1


def _validate_taste_log(
    taste_path: Path, errors: list[str], warnings: list[str]
) -> dict[str, Any]:
    """Validate taste-log.md (including Supersedes graph) and taste-active.md freshness."""
    parsed = _MEMORY_COMPILE.parse_taste_log(taste_path)
    errors.extend(parsed["errors"])
    warnings.extend(parsed["warnings"])

    active_path = taste_path.with_name("taste-active.md")
    active_present = active_path.is_file()
    active_fresh: bool | None = None

    if active_present:
        meta = _MEMORY_COMPILE.extract_active_metadata(active_path)
        if meta is None:
            active_fresh = False
            errors.append(
                "taste-active.md: missing compiled header; run `make memory-compile CAMPAIGN=<slug>`"
            )
        elif meta["source_hash"] != parsed["source_hash"]:
            active_fresh = False
            errors.append(
                f"taste-active.md: stale snapshot (hash {meta['source_hash']} != "
                f"taste-log.md {parsed['source_hash']}); run `make memory-compile CAMPAIGN=<slug>`"
            )
        else:
            active_fresh = True
            if meta["line_count"] > _MEMORY_COMPILE.DEFAULT_ACTIVE_MAX_LINES:
                warnings.append(
                    f"taste-active.md has {meta['line_count']} lines "
                    f"(soft cap <= {_MEMORY_COMPILE.DEFAULT_ACTIVE_MAX_LINES}); "
                    "supersede obsolete TL-NN entries or run studio-retro"
                )
    elif parsed["entry_count"] >= 4:
        warnings.append(
            f"taste-log.md has {parsed['entry_count']} entries without compiled taste-active.md; "
            "run `make memory-compile CAMPAIGN=<slug>`"
        )

    return {
        "entries": parsed["entry_count"],
        "active_present": active_present,
        "active_fresh": active_fresh,
    }


def _validate_shotlist(
    shotlist_path: Path,
    campaign_dir: Path,
    repo_root: Path,
    campaign_cap: int | None,
    errors: list[str],
    warnings: list[str],
) -> dict[str, Any]:
    status_counts = {st: 0 for st in VALID_ASSET_STATUSES}
    result: dict[str, Any] = {
        "shot_count": 0,
        "lookbook_count": 0,
        "status_counts": status_counts,
        "budget": {
            "r2_lookbook": 0,
            "r3_stills_audio": 0,
            "r4_draft_video": 0,
            "r5_final_video": 0,
            "planned_total": 0,
            "campaign_cap": campaign_cap,
            "remaining_planned": campaign_cap,
        },
    }

    try:
        data = json.loads(shotlist_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        errors.append(f"shotlist.json: failed to parse JSON: {exc}")
        return result

    if not isinstance(data, dict):
        errors.append("shotlist.json: root must be a JSON object")
        return result

    if data.get("schema_version") != 1:
        errors.append(
            f"shotlist.json: schema_version must be 1, got {data.get('schema_version')!r}"
        )

    raw_track = data.get("production_track")
    if raw_track is not None:
        if not isinstance(raw_track, str) or raw_track not in VALID_PRODUCTION_TRACKS:
            errors.append(
                f"shotlist.json: invalid production_track {raw_track!r} "
                f"(expected one of {sorted(VALID_PRODUCTION_TRACKS)})"
            )

    raw_sub_flows = data.get("sub_flows")
    if raw_sub_flows is not None:
        if not isinstance(raw_sub_flows, list):
            errors.append("shotlist.json: 'sub_flows' must be a list of valid sub-flow IDs")
        else:
            for sf in raw_sub_flows:
                if not isinstance(sf, str) or sf not in VALID_SUB_FLOWS:
                    errors.append(
                        f"shotlist.json: invalid sub_flows entry {sf!r} "
                        f"(expected one of {sorted(VALID_SUB_FLOWS)})"
                    )

    raw_campaign_ar = data.get("aspect_ratio")
    campaign_aspect_ratio = raw_campaign_ar.strip() if isinstance(raw_campaign_ar, str) else ""

    def _resolve_prompt_file(val: Any) -> Path | None:
        if not isinstance(val, str) or not val.strip():
            return None
        p = Path(val.strip())
        if p.is_absolute():
            return p if p.is_file() else None
        if (campaign_dir / p).is_file():
            return campaign_dir / p
        if (repo_root / p).is_file():
            return repo_root / p
        return None

    def _check_prompt_file(val: Any, ctx: str) -> None:
        if val is None:
            return
        if not isinstance(val, str):
            errors.append(f"shotlist.json ({ctx}): prompt_file must be a string, got {val!r}")
            return
        if not val.strip():
            return
        if _resolve_prompt_file(val) is None:
            errors.append(f"shotlist.json ({ctx}): prompt_file not found: {val}")

    def _check_still_model_guards(still_obj: dict[str, Any], ctx: str) -> None:
        s_model = str(still_obj.get("model") or "").strip()
        s_params = still_obj.get("params") if isinstance(still_obj.get("params"), dict) else {}
        if s_model == "seedream_v5_pro":
            for r_label, r_val in (
                ("resolution", still_obj.get("resolution")),
                ("params.resolution", s_params.get("resolution")),
            ):
                if r_val is not None and str(r_val).strip().lower() == "4k":
                    errors.append(
                        f"shotlist.json ({ctx}.{r_label}): 'seedream_v5_pro' live CLI caps "
                        "resolution at 2k (no '4k'); use 'seedream_5_5' for 4k"
                    )
        if s_model == "soul_cast":
            ar_direct = still_obj.get("aspect_ratio")
            ar_param = s_params.get("aspect_ratio")
            if ar_direct is not None and str(ar_direct).strip() != "16:9":
                errors.append(
                    f"shotlist.json ({ctx}.aspect_ratio): model 'soul_cast' live CLI only "
                    f"supports '16:9' aspect_ratio, got {ar_direct!r}"
                )
            if ar_param is not None and str(ar_param).strip() != "16:9":
                errors.append(
                    f"shotlist.json ({ctx}.params.aspect_ratio): model 'soul_cast' live CLI only "
                    f"supports '16:9' aspect_ratio, got {ar_param!r}"
                )
            if (
                ar_direct is None
                and ar_param is None
                and campaign_aspect_ratio
                and campaign_aspect_ratio != "16:9"
            ):
                errors.append(
                    f"shotlist.json ({ctx}): model 'soul_cast' live CLI only supports '16:9' "
                    f"aspect_ratio (inherited campaign aspect_ratio is {campaign_aspect_ratio!r}); "
                    "set explicit 'aspect_ratio': '16:9' or use another model"
                )

    def _num(val: Any, ctx: str) -> float:
        if val is None:
            return 0.0
        if isinstance(val, bool) or not isinstance(val, (int, float)):
            errors.append(f"shotlist.json ({ctx}): expected numeric credit value, got {val!r}")
            return 0.0
        f = float(val)
        if not math.isfinite(f) or f < 0:
            errors.append(f"shotlist.json ({ctx}): credit value must be finite and >= 0, got {val!r}")
            return 0.0
        return f

    def _req_num(obj: dict[str, Any], key: str, ctx: str) -> float:
        if key not in obj or obj[key] is None:
            errors.append(
                f"shotlist.json ({ctx}): missing or null required numeric credit field '{key}'"
            )
            return 0.0
        return _num(obj[key], f"{ctx}.{key}")

    def _check_status_and_version(
        obj: dict[str, Any],
        ctx: str,
        *,
        require_status: bool,
        count_status: bool = True,
    ) -> str | None:
        raw_status = obj.get("status")
        valid_st: str | None = None
        if raw_status is None:
            if require_status:
                errors.append(
                    f"shotlist.json ({ctx}): missing required 'status' "
                    f"(expected one of {list(VALID_ASSET_STATUSES)})"
                )
        elif not isinstance(raw_status, str) or raw_status not in VALID_ASSET_STATUS_SET:
            errors.append(
                f"shotlist.json ({ctx}): invalid status {raw_status!r} "
                f"(expected one of {list(VALID_ASSET_STATUSES)})"
            )
        else:
            valid_st = raw_status
            if count_status:
                status_counts[valid_st] += 1

        if "version" in obj and obj["version"] is not None and not _is_valid_version(obj["version"]):
            errors.append(
                f"shotlist.json ({ctx}): 'version' must be a positive integer (>= 1), "
                f"got {obj['version']!r}"
            )
        return valid_st

    # Optional continuity_lock
    if "continuity_lock" in data and data["continuity_lock"] is not None:
        cl = data["continuity_lock"]
        if not isinstance(cl, dict):
            errors.append("shotlist.json: 'continuity_lock' must be a JSON object")
        else:
            for field in ("product", "lighting_and_palette", "space_cast_axis"):
                val = cl.get(field)
                if (
                    not isinstance(val, str)
                    or not val.strip()
                    or _CHECK_BRIEF.is_placeholder(val)
                ):
                    errors.append(
                        f"shotlist.json (continuity_lock): missing, empty, or placeholder string '{field}'"
                    )

    # Optional narrative_lock (soft/backwards-compatible)
    if "narrative_lock" in data and data["narrative_lock"] is not None:
        nl = data["narrative_lock"]
        if not isinstance(nl, dict):
            errors.append("shotlist.json: 'narrative_lock' must be a JSON object")
        else:
            for field in NARRATIVE_LOCK_FIELDS:
                val = nl.get(field)
                if (
                    not isinstance(val, str)
                    or not val.strip()
                    or _CHECK_BRIEF.is_placeholder(val)
                ):
                    errors.append(
                        f"shotlist.json (narrative_lock): missing, empty, or placeholder string '{field}'"
                    )

    # Declared references
    declared_ref_ids: set[str] = set()
    raw_refs = data.get("references")
    if raw_refs is not None:
        if not isinstance(raw_refs, list):
            errors.append("shotlist.json: 'references' must be a list")
        else:
            for ridx, ref_obj in enumerate(raw_refs):
                if not isinstance(ref_obj, dict):
                    errors.append(f"shotlist.json: references[{ridx}] must be an object")
                    continue
                rid = ref_obj.get("id")
                if not isinstance(rid, str) or not rid.strip():
                    errors.append(f"shotlist.json: references[{ridx}] missing non-empty string 'id'")
                    continue
                rid_clean = rid.strip()
                if rid_clean in declared_ref_ids:
                    errors.append(f"shotlist.json: duplicate reference id '{rid_clean}'")
                declared_ref_ids.add(rid_clean)

    # Optional lookbook[]
    lookbook_ids: set[str] = set()
    r2_lookbook = 0.0
    raw_lookbook = data.get("lookbook")
    if raw_lookbook is not None:
        if not isinstance(raw_lookbook, list):
            errors.append("shotlist.json: 'lookbook' must be a list")
        else:
            result["lookbook_count"] = len(raw_lookbook)
            for lidx, lb in enumerate(raw_lookbook):
                ctx = f"lookbook[{lidx}]"
                if not isinstance(lb, dict):
                    errors.append(f"shotlist.json: {ctx} must be an object")
                    continue
                lid = lb.get("id")
                if not isinstance(lid, str) or not lid.strip():
                    errors.append(f"shotlist.json ({ctx}): missing non-empty string 'id'")
                    lid_clean = f"index_{lidx}"
                else:
                    lid_clean = lid.strip()
                    ctx = f"lookbook.{lid_clean}"
                    if lid_clean in lookbook_ids:
                        errors.append(f"shotlist.json: duplicate lookbook id '{lid_clean}'")
                    if lid_clean in declared_ref_ids:
                        errors.append(
                            f"shotlist.json: lookbook id '{lid_clean}' collides with references[].id"
                        )
                    lookbook_ids.add(lid_clean)

                lkind = lb.get("kind")
                if not isinstance(lkind, str) or lkind not in VALID_LOOKBOOK_KINDS:
                    errors.append(
                        f"shotlist.json ({ctx}): invalid kind {lkind!r} "
                        f"(expected one of {sorted(VALID_LOOKBOOK_KINDS)})"
                    )

                lb_status = _check_status_and_version(lb, ctx, require_status=True)

                variants = lb.get("variants_requested")
                if not isinstance(variants, int) or isinstance(variants, bool) or variants < 1:
                    errors.append(
                        f"shotlist.json ({ctx}): 'variants_requested' must be an integer >= 1, "
                        f"got {variants!r}"
                    )

                r2_lookbook += _req_num(lb, "estimated_credits", ctx)

                _check_prompt_file(lb.get("prompt_file"), ctx)
                _check_still_model_guards(lb, ctx)

                if lb_status == "LOCKED":
                    approved_var = lb.get("approved_variant")
                    if (
                        not isinstance(approved_var, str)
                        or not approved_var.strip()
                        or _CHECK_BRIEF.is_placeholder(approved_var)
                    ):
                        errors.append(
                            f"shotlist.json ({ctx}): status is LOCKED but 'approved_variant' "
                            "is missing, empty, or placeholder"
                        )

    all_ref_ids = declared_ref_ids | lookbook_ids

    def _check_ref_id_list(ref_list: Any, ctx: str) -> None:
        if ref_list is None:
            return
        if not isinstance(ref_list, list):
            errors.append(f"shotlist.json ({ctx}): expected list of reference/lookbook IDs")
            return
        for item in ref_list:
            if not isinstance(item, str) or not item.strip():
                errors.append(f"shotlist.json ({ctx}): invalid reference id {item!r}")
            elif item.strip() not in all_ref_ids:
                errors.append(
                    f"shotlist.json ({ctx}): references undeclared reference/lookbook id '{item.strip()}'"
                )

    shots = data.get("shots")
    if not isinstance(shots, list) or len(shots) == 0:
        errors.append("shotlist.json: 'shots' must be a non-empty list")
        return result

    result["shot_count"] = len(shots)
    shots_by_id: dict[str, dict[str, Any]] = {}
    still_sum = 0.0
    video_draft_sum = 0.0
    video_final_sum = 0.0
    audio_sum = 0.0
    total_duration_s = 0.0
    all_have_duration = True

    for idx, shot in enumerate(shots):
        if not isinstance(shot, dict):
            errors.append(f"shotlist.json: shots[{idx}] must be an object")
            continue
        sid = shot.get("id")
        if not isinstance(sid, str) or not sid.strip():
            errors.append(f"shotlist.json: shots[{idx}] missing non-empty string 'id'")
            continue
        sid = sid.strip()
        if sid in shots_by_id:
            errors.append(f"shotlist.json: duplicate shot id '{sid}'")
        shots_by_id[sid] = shot

        dur_val = shot.get("duration_s")
        if dur_val is None:
            errors.append(f"shotlist.json (shot {sid}): missing required positive 'duration_s'")
            all_have_duration = False
        elif isinstance(dur_val, bool) or not isinstance(dur_val, (int, float)) or not math.isfinite(float(dur_val)) or dur_val <= 0:
            errors.append(
                f"shotlist.json (shot {sid}.duration_s): must be a positive number, got {dur_val!r}"
            )
            all_have_duration = False
        else:
            total_duration_s += float(dur_val)

        _check_prompt_file(shot.get("prompt_file"), f"shot {sid}")
        _check_ref_id_list(shot.get("references"), f"shot {sid}.references")

        # Optional per-shot narrative_job (soft/backwards-compatible)
        if "narrative_job" in shot and shot["narrative_job"] is not None:
            nj = shot["narrative_job"]
            nj_ctx = f"shot {sid}.narrative_job"
            if not isinstance(nj, dict):
                errors.append(f"shotlist.json ({nj_ctx}): must be a JSON object")
            else:
                bf = nj.get("beat_function")
                if not isinstance(bf, str) or bf.strip().lower() not in VALID_BEAT_FUNCTIONS:
                    errors.append(
                        f"shotlist.json ({nj_ctx}): invalid 'beat_function' {bf!r} "
                        f"(expected one of {sorted(VALID_BEAT_FUNCTIONS)})"
                    )
                delta = nj.get("delta")
                if (
                    not isinstance(delta, str)
                    or not delta.strip()
                    or _CHECK_BRIEF.is_placeholder(delta)
                ):
                    errors.append(
                        f"shotlist.json ({nj_ctx}): missing, empty, or placeholder string 'delta'"
                    )

        # Optional per-shot test_take_check
        ttc_locations: list[tuple[str, Any]] = []
        if "test_take_check" in shot and shot["test_take_check"] is not None:
            ttc_locations.append((f"shot {sid}.test_take_check", shot["test_take_check"]))
        if (
            isinstance(shot.get("video"), dict)
            and "test_take_check" in shot["video"]
            and shot["video"]["test_take_check"] is not None
        ):
            ttc_locations.append(
                (f"shot {sid}.video.test_take_check", shot["video"]["test_take_check"])
            )
        for ttc_ctx, ttc in ttc_locations:
            if not isinstance(ttc, dict):
                errors.append(f"shotlist.json ({ttc_ctx}): must be a JSON object")
            else:
                for field in ("risk", "pass_check"):
                    val = ttc.get(field)
                    if (
                        not isinstance(val, str)
                        or not val.strip()
                        or _CHECK_BRIEF.is_placeholder(val)
                    ):
                        errors.append(
                            f"shotlist.json ({ttc_ctx}): missing, empty, or placeholder string '{field}'"
                        )

        still_only_raw = shot.get("still_only")
        still_only = False
        if still_only_raw is not None:
            if not isinstance(still_only_raw, bool):
                errors.append(
                    f"shotlist.json (shot {sid}.still_only): must be a boolean, got {still_only_raw!r}"
                )
            else:
                still_only = still_only_raw

        still = shot.get("still")
        if still is None:
            if still_only:
                errors.append(
                    f"shotlist.json (shot {sid}.still): 'still_only': true requires a valid 'still' object"
                )
        elif not isinstance(still, dict):
            errors.append(f"shotlist.json (shot {sid}.still): must be an object or null")
        else:
            _check_status_and_version(still, f"shot {sid}.still", require_status=True)
            still_sum += _req_num(still, "estimated_credits", f"shot {sid}.still")
            _check_prompt_file(still.get("prompt_file"), f"shot {sid}.still")
            _check_ref_id_list(still.get("references"), f"shot {sid}.still.references")
            _check_ref_id_list(
                still.get("image_references"), f"shot {sid}.still.image_references"
            )
            still_ref_count = (
                (len(still["references"]) if isinstance(still.get("references"), list) else 0)
                + (
                    len(still["image_references"])
                    if isinstance(still.get("image_references"), list)
                    else 0
                )
            )
            s_model = str(still.get("model") or "").strip()
            if s_model in STILL_HARD_REF_CAPS and still_ref_count > STILL_HARD_REF_CAPS[s_model]:
                errors.append(
                    f"shotlist.json (shot {sid}.still): {still_ref_count} image references "
                    f"exceeds live CEL limit ({STILL_HARD_REF_CAPS[s_model]}) for '{s_model}'"
                )
            elif still_ref_count > 6:
                warnings.append(
                    f"shotlist.json (shot {sid}.still): {still_ref_count} image references "
                    "exceeds optimal R3 still budget (3-5, max 6); prune off-screen refs to prevent attention dilution"
                )
            if s_model == "text2image_soul_v2" and still_ref_count > 0:
                s_params = still.get("params") if isinstance(still.get("params"), dict) else {}
                if still.get("style_id") or s_params.get("style_id"):
                    errors.append(
                        f"shotlist.json (shot {sid}.still): 'text2image_soul_v2' live CEL forbids "
                        "combining 'style_id' with image references"
                    )
            _check_still_model_guards(still, f"shot {sid}.still")

        video = shot.get("video")
        if still_only:
            if video is not None and not isinstance(video, dict):
                errors.append(
                    f"shotlist.json (shot {sid}.video): must be an object or null when 'still_only' is true"
                )
            elif isinstance(video, dict):
                warnings.append(
                    f"shotlist.json (shot {sid}): 'still_only' is true; ignoring non-null 'video' object (0 video credits counted)"
                )
        elif not isinstance(video, dict):
            errors.append(f"shotlist.json (shot {sid}.video): missing or non-object 'video'")
        else:
            _check_status_and_version(video, f"shot {sid}.video", require_status=True)
            video_draft_sum += _req_num(
                video, "estimated_draft_credits", f"shot {sid}.video"
            )
            video_final_sum += _req_num(
                video, "estimated_final_credits", f"shot {sid}.video"
            )
            v_model = video.get("model")
            draft_params = video.get("draft_params") if isinstance(video.get("draft_params"), dict) else {}
            final_params = video.get("final_params") if isinstance(video.get("final_params"), dict) else {}
            tier_dicts = [
                ("video", video),
                ("draft_params", draft_params),
                ("final_params", final_params),
            ]
            start_src = video.get("start_image_from")
            if start_src is None:
                start_src = shot.get("start_image_from")
            end_src = video.get("end_image_from")
            if end_src is None:
                end_src = shot.get("end_image_from")
            has_start = start_src is not None
            has_end = end_src is not None

            def _tier_ctx(tier_name: str, _sid: str = sid) -> str:
                return f"shot {_sid}.video" if tier_name == "video" else f"shot {_sid}.video.{tier_name}"

            if v_model == "cinematic_studio_video_4_0":
                if video.get("is_workflow") is not True:
                    errors.append(
                        f"shotlist.json (shot {sid}.video): model 'cinematic_studio_video_4_0' "
                        "requires 'is_workflow': true"
                    )
                vmode = video.get("mode")
                if not isinstance(vmode, str) or vmode not in VALID_CS4_MODES:
                    errors.append(
                        f"shotlist.json (shot {sid}.video): model 'cinematic_studio_video_4_0' "
                        f"requires 'mode' in {sorted(VALID_CS4_MODES)}, got {vmode!r}"
                    )
                if (has_start or has_end) and vmode != "omni_reference":
                    errors.append(
                        f"shotlist.json (shot {sid}.video): model 'cinematic_studio_video_4_0' "
                        "with non-null start_image_from/end_image_from requires "
                        f"'mode': 'omni_reference', got {vmode!r}"
                    )
                for tier_name, td in tier_dicts:
                    t_ctx = _tier_ctx(tier_name)
                    res = td.get("resolution")
                    if res is not None and str(res).strip().lower() == "4k":
                        errors.append(
                            f"shotlist.json ({t_ctx}): 'cinematic_studio_video_4_0' live CLI caps "
                            "resolution at 1080p (no '4k'); use 'seedance_2_5' for 4k"
                        )
                    for bad_key in ("draft", "draft_job_id"):
                        if td.get(bad_key) is not None:
                            errors.append(
                                f"shotlist.json ({t_ctx}): 'cinematic_studio_video_4_0' live CLI has no "
                                f"'{bad_key}' parameter; use 'seedance_2_5' for draft -> draft_job_id escalation"
                            )
                    cp = td.get("color_palette")
                    if isinstance(cp, str):
                        errors.append(
                            f"shotlist.json ({t_ctx}): 'cinematic_studio_video_4_0' 'color_palette' "
                            f"must be a JSON object/dict or null in live CLI 1.2.3, got string {cp!r}"
                        )
                    lid = td.get("light_id")
                    lc = td.get("light_custom")
                    if lid is not None and lid != "custom":
                        errors.append(
                            f"shotlist.json ({t_ctx}): 'cinematic_studio_video_4_0' 'light_id' must be "
                            f"'custom' or omitted in live CLI 1.2.3, got {lid!r}"
                        )
                    if lid is not None and lc is not None:
                        errors.append(
                            f"shotlist.json ({t_ctx}): 'cinematic_studio_video_4_0' live CEL forbids "
                            "setting both 'light_id' and 'light_custom' simultaneously"
                        )
                for tier_name, td in (("draft_params", draft_params), ("final_params", final_params)):
                    inherited_conflict = (
                        video.get("light_id") is not None
                        and "light_id" not in td
                        and td.get("light_custom") is not None
                    ) or (
                        video.get("light_custom") is not None
                        and "light_custom" not in td
                        and td.get("light_id") is not None
                    )
                    if inherited_conflict:
                        errors.append(
                            f"shotlist.json (shot {sid}.video.{tier_name}): 'cinematic_studio_video_4_0' "
                            "live CEL forbids setting both 'light_id' and 'light_custom' simultaneously"
                        )
            _check_prompt_file(video.get("prompt_file"), f"shot {sid}.video")
            _check_ref_id_list(video.get("references"), f"shot {sid}.video.references")
            _check_ref_id_list(
                video.get("image_references"), f"shot {sid}.video.image_references"
            )
            _check_ref_id_list(
                video.get("character_images"), f"shot {sid}.video.character_images"
            )
            _check_ref_id_list(
                video.get("video_references"), f"shot {sid}.video.video_references"
            )
            _check_ref_id_list(
                video.get("audio_references"), f"shot {sid}.video.audio_references"
            )
            loc_img = video.get("location_image")
            if loc_img is not None:
                if not isinstance(loc_img, str) or not loc_img.strip():
                    errors.append(
                        f"shotlist.json (shot {sid}.video.location_image): invalid reference {loc_img!r}"
                    )
                elif loc_img.strip() not in all_ref_ids:
                    errors.append(
                        f"shotlist.json (shot {sid}.video.location_image): references undeclared reference/lookbook id '{loc_img.strip()}'"
                    )
            if v_model in ("kling4_0", "kling_4_0_flash"):
                if v_model == "kling4_0":
                    for tier_name, td in tier_dicts:
                        t_ctx = _tier_ctx(tier_name)
                        for bad_key in ("multi_shots", "multi_prompt"):
                            if td.get(bad_key) is not None:
                                errors.append(
                                    f"shotlist.json ({t_ctx}): 'kling4_0' live CLI has no '{bad_key}' "
                                    "parameter; use 'cinematic_studio_video_v2', 'kling_o3_image_reference', "
                                    "or 'cinematic_studio_video_3_5' for multi-shot"
                                )
                elif v_model == "kling_4_0_flash":
                    for tier_name, td in tier_dicts:
                        t_ctx = _tier_ctx(tier_name)
                        res = td.get("resolution")
                        if res is not None and str(res).strip().lower() != "720p":
                            errors.append(
                                f"shotlist.json ({t_ctx}): 'kling_4_0_flash' live CLI is 720p-only, "
                                f"got resolution {res!r}; use 'kling4_0' for 1080p/4k"
                            )
                if (
                    isinstance(dur_val, (int, float))
                    and not isinstance(dur_val, bool)
                    and float(dur_val) != 10.0
                    and not any(td.get("duration") is not None for _, td in tier_dicts)
                ):
                    warnings.append(
                        f"shotlist.json (shot {sid}.video): '{v_model}' defaults "
                        "duration to 10s in live CLI (silently doubling 5s cost); "
                        "set 'duration' explicitly in draft_params/final_params"
                    )
            elif v_model == "kling3_0_motion_control":
                if video.get("is_workflow") is not True:
                    errors.append(
                        f"shotlist.json (shot {sid}.video): model 'kling3_0_motion_control' "
                        "requires 'is_workflow': true"
                    )
                if video.get("prompt_file"):
                    warnings.append(
                        f"shotlist.json (shot {sid}.video): 'kling3_0_motion_control' live CLI "
                        "accepts no '--prompt' flag; omit prompt_file or use hf_mult_motion_control"
                    )
                mc_imgs = len(video["image_references"]) if isinstance(video.get("image_references"), list) else 0
                mc_vids = len(video["video_references"]) if isinstance(video.get("video_references"), list) else 0
                if mc_imgs != 1:
                    errors.append(
                        f"shotlist.json (shot {sid}.video): 'kling3_0_motion_control' live CEL requires "
                        f"exactly 1 image_references entry (got {mc_imgs})"
                    )
                if mc_vids != 1:
                    errors.append(
                        f"shotlist.json (shot {sid}.video): 'kling3_0_motion_control' live CEL requires "
                        f"exactly 1 video_references entry (got {mc_vids})"
                    )
            elif v_model in (
                "hf_mult_motion_control",
                "hf_mult_motion_control_flash",
                "hf_mult_replace_object",
                "hf_mult_replace_object_flash",
            ):
                mc_imgs = len(video["image_references"]) if isinstance(video.get("image_references"), list) else 0
                mc_vids = len(video["video_references"]) if isinstance(video.get("video_references"), list) else 0
                if mc_imgs < 1:
                    errors.append(
                        f"shotlist.json (shot {sid}.video): '{v_model}' live CEL requires "
                        "at least 1 image_references entry"
                    )
                if mc_vids != 1:
                    errors.append(
                        f"shotlist.json (shot {sid}.video): '{v_model}' live CEL requires "
                        f"exactly 1 video_references entry (got {mc_vids})"
                    )
                if v_model in ("hf_mult_motion_control_flash", "hf_mult_replace_object_flash"):
                    for tier_name, td in tier_dicts:
                        t_ctx = _tier_ctx(tier_name)
                        res = td.get("resolution")
                        if res is not None and str(res).strip().lower() != "1080p":
                            errors.append(
                                f"shotlist.json ({t_ctx}): '{v_model}' live CLI is 1080p-only, "
                                f"got resolution {res!r}"
                            )
                elif v_model == "hf_mult_motion_control":
                    warnings.append(
                        f"shotlist.json (shot {sid}.video): 'hf_mult_motion_control' costs 100 cr. (1080p 5s); "
                        "pilot 10x cheaper 'hf_mult_motion_control_flash' (Genjutsu Lite, 10 cr. 1080p) first"
                    )
                elif v_model == "hf_mult_replace_object":
                    warnings.append(
                        f"shotlist.json (shot {sid}.video): 'hf_mult_replace_object' costs 120 cr. (1080p 5s); "
                        "pilot 10x cheaper 'hf_mult_replace_object_flash' (Genjutsu Lite, 12 cr. 1080p) first"
                    )
            elif v_model == "intone":
                in_imgs = len(video["image_references"]) if isinstance(video.get("image_references"), list) else 0
                in_chars = len(video["character_images"]) if isinstance(video.get("character_images"), list) else 0
                in_loc = video.get("location_image") is not None
                in_aud = len(video["audio_references"]) if isinstance(video.get("audio_references"), list) else 0
                if in_imgs > 0:
                    if in_imgs != 2 or in_chars > 0 or in_loc:
                        errors.append(
                            f"shotlist.json (shot {sid}.video): 'intone' live CEL requires image_references "
                            "to have exactly 2 entries (character, location) with neither character_images nor location_image"
                        )
                elif not (1 <= in_chars <= 2):
                    errors.append(
                        f"shotlist.json (shot {sid}.video): 'intone' live CEL requires "
                        f"1-2 character_images (or exactly 2 image_references), got {in_chars}"
                    )
                if not (1 <= in_aud <= 6):
                    errors.append(
                        f"shotlist.json (shot {sid}.video): 'intone' live CEL requires "
                        f"1-6 audio_references, got {in_aud}"
                    )
                if (
                    isinstance(dur_val, (int, float))
                    and not isinstance(dur_val, bool)
                    and float(dur_val) > 8.0
                ):
                    warnings.append(
                        f"shotlist.json (shot {sid}.video): 'intone' duration_s={dur_val}s exceeds 8s "
                        "(~18 cr./s at 1080p in CLI); keep CLI clips 3-6s or check Web Unlimited CTA first"
                    )
            elif v_model in ("cinematic_studio_video_3_5", "cinematic_studio_3_0", "cinematic_studio_video_v2"):
                if video.get("is_workflow") is not True:
                    errors.append(
                        f"shotlist.json (shot {sid}.video): model '{v_model}' "
                        "requires 'is_workflow': true"
                    )
                cs_media_total = (
                    (len(video["image_references"]) if isinstance(video.get("image_references"), list) else 0)
                    + (len(video["video_references"]) if isinstance(video.get("video_references"), list) else 0)
                    + (len(video["audio_references"]) if isinstance(video.get("audio_references"), list) else 0)
                    + (1 if has_start else 0)
                    + (1 if has_end else 0)
                )
                if v_model in ("cinematic_studio_video_3_5", "cinematic_studio_3_0") and cs_media_total > 15:
                    errors.append(
                        f"shotlist.json (shot {sid}.video): '{v_model}' live CEL allows at most "
                        f"15 total media references (got {cs_media_total})"
                    )
                if v_model == "cinematic_studio_video_3_5":
                    for tier_name, td in tier_dicts:
                        c_style = td.get("camera_style")
                        if c_style is not None and c_style not in VALID_CS35_CAMERA_STYLES:
                            errors.append(
                                f"shotlist.json (shot {sid}.video.{tier_name}): invalid camera_style "
                                f"{c_style!r} (expected one of {sorted(VALID_CS35_CAMERA_STYLES)})"
                            )
                        has_inline_axis = any(
                            td.get(k) is not None for k in ("camera_style", "light_scheme", "color_grading")
                        )
                        if has_inline_axis and td.get("style_prompt") is not None:
                            errors.append(
                                f"shotlist.json (shot {sid}.video.{tier_name}): 'cinematic_studio_video_3_5' "
                                "live CEL forbids combining camera_style/light_scheme/color_grading with style_prompt"
                            )
                    if not any(td.get("prompt_language") for _, td in tier_dicts):
                        warnings.append(
                            f"shotlist.json (shot {sid}.video): 'cinematic_studio_video_3_5' defaults "
                            "prompt_language to 'zh'; set 'prompt_language': 'en' explicitly for English prompts"
                        )
                    if (
                        isinstance(dur_val, (int, float))
                        and not isinstance(dur_val, bool)
                        and float(dur_val) != 15.0
                        and not any(td.get("duration") is not None for _, td in tier_dicts)
                    ):
                        warnings.append(
                            f"shotlist.json (shot {sid}.video): 'cinematic_studio_video_3_5' defaults "
                            "duration to 15s in live CLI; set 'duration' explicitly in draft_params/final_params"
                        )
                elif v_model == "cinematic_studio_3_0":
                    for tier_name, td in tier_dicts:
                        sr = td.get("speedramp")
                        if sr is not None and sr not in VALID_CS30_SPEEDRAMPS:
                            errors.append(
                                f"shotlist.json (shot {sid}.video.{tier_name}): invalid speedramp "
                                f"{sr!r} for 'cinematic_studio_3_0' (expected one of {sorted(VALID_CS30_SPEEDRAMPS)})"
                            )
                    if not any(td.get("prompt_language") for _, td in tier_dicts):
                        warnings.append(
                            f"shotlist.json (shot {sid}.video): 'cinematic_studio_3_0' defaults "
                            "prompt_language to 'zh'; set 'prompt_language': 'en' explicitly for English prompts"
                        )
                elif v_model == "cinematic_studio_video_v2":
                    for tier_name, td in tier_dicts:
                        sr = td.get("speedramp")
                        if sr is not None and sr not in VALID_CS2_SPEEDRAMPS:
                            errors.append(
                                f"shotlist.json (shot {sid}.video.{tier_name}): invalid speedramp "
                                f"{sr!r} for 'cinematic_studio_video_v2' (expected one of {sorted(VALID_CS2_SPEEDRAMPS)})"
                            )
            elif v_model == "draw_to_video":
                if video.get("is_workflow") is not True:
                    errors.append(
                        f"shotlist.json (shot {sid}.video): model 'draw_to_video' "
                        "requires 'is_workflow': true"
                    )
                dtv_imgs = len(video["image_references"]) if isinstance(video.get("image_references"), list) else 0
                if dtv_imgs != 1:
                    errors.append(
                        f"shotlist.json (shot {sid}.video): 'draw_to_video' live CEL requires "
                        f"exactly 1 sketch image in image_references (got {dtv_imgs})"
                    )
                dtv_vid_field = video.get("video")
                has_dtv_vid_field = (
                    (isinstance(dtv_vid_field, str) and bool(dtv_vid_field.strip()))
                    or (isinstance(dtv_vid_field, dict) and bool(dtv_vid_field))
                )
                dtv_vids = len(video["video_references"]) if isinstance(video.get("video_references"), list) else 0
                if not has_dtv_vid_field and dtv_vids != 1:
                    errors.append(
                        f"shotlist.json (shot {sid}.video): 'draw_to_video' live CLI requires "
                        f"a source video ('video' or exactly 1 'video_references' entry; got {dtv_vids} video_references)"
                    )
            elif v_model == "reframe":
                if video.get("is_workflow") is not True:
                    errors.append(
                        f"shotlist.json (shot {sid}.video): model 'reframe' "
                        "requires 'is_workflow': true"
                    )
                rf_vids = len(video["video_references"]) if isinstance(video.get("video_references"), list) else 0
                if rf_vids != 1:
                    errors.append(
                        f"shotlist.json (shot {sid}.video): 'reframe' live CEL requires "
                        f"exactly 1 video_references entry (got {rf_vids})"
                    )
            elif v_model in ("marketing_studio_v2_video", "marketing_studio_video"):
                if video.get("is_workflow") is not True:
                    errors.append(
                        f"shotlist.json (shot {sid}.video): model '{v_model}' "
                        "requires 'is_workflow': true"
                    )
                if v_model == "marketing_studio_v2_video":
                    def _count_ms_imgs(obj: dict[str, Any], key: str) -> int:
                        val = obj.get(key)
                        if isinstance(val, list):
                            return len(val)
                        if isinstance(val, str) and val.strip():
                            return 1
                        return 0

                    base_type = str(video.get("type") or "").strip()
                    base_in = _count_ms_imgs(video, "input_images")
                    base_ref = _count_ms_imgs(video, "image_references")
                    has_tier_ms_override = any(
                        any(k in td for k in ("type", "input_images", "image_references"))
                        for td in (draft_params, final_params)
                    )
                    if has_tier_ms_override:
                        for tier_name, td in (("draft_params", draft_params), ("final_params", final_params)):
                            t_type = str(td.get("type") if "type" in td else base_type).strip()
                            eff_in = _count_ms_imgs(td, "input_images") if "input_images" in td else base_in
                            eff_ref = _count_ms_imgs(td, "image_references") if "image_references" in td else base_ref
                            eff_total = eff_in + eff_ref
                            if t_type in VALID_MSV2_SINGLE_IMAGE_TYPES and eff_total != 1:
                                errors.append(
                                    f"shotlist.json (shot {sid}.video.{tier_name}): 'marketing_studio_v2_video' "
                                    f"type '{t_type}' live CEL requires exactly 1 input_images/image_references "
                                    f"entry (got {eff_total})"
                                )
                    elif base_type in VALID_MSV2_SINGLE_IMAGE_TYPES and (base_in + base_ref) != 1:
                        errors.append(
                            f"shotlist.json (shot {sid}.video): 'marketing_studio_v2_video' "
                            f"type '{base_type}' live CEL requires exactly 1 input_images/image_references "
                            f"entry (got {base_in + base_ref})"
                        )

                    saas_720_tiers: list[str] = []
                    if base_type == "saas_motion" and str(video.get("resolution") or "").strip().lower() == "720p":
                        saas_720_tiers.append("video")
                    for tier_name, td in (("draft_params", draft_params), ("final_params", final_params)):
                        t_type = str(td.get("type") if "type" in td else base_type).strip()
                        eff_res = td.get("resolution") if "resolution" in td else video.get("resolution")
                        if (
                            t_type == "saas_motion"
                            and eff_res is not None
                            and str(eff_res).strip().lower() == "720p"
                            and ("resolution" in td or ("type" in td and "video" not in saas_720_tiers))
                        ):
                            saas_720_tiers.append(tier_name)
                    if saas_720_tiers:
                        warnings.append(
                            f"shotlist.json (shot {sid}.video): 'marketing_studio_v2_video' type 'saas_motion' "
                            f"sets resolution '720p' in {', '.join(saas_720_tiers)}, but '1080p' is the exact "
                            "same flat 31.1 cr. cost; use '1080p'"
                        )
                else:
                    if (
                        isinstance(dur_val, (int, float))
                        and not isinstance(dur_val, bool)
                        and float(dur_val) != 15.0
                        and not any(td.get("duration") is not None for _, td in tier_dicts)
                    ):
                        warnings.append(
                            f"shotlist.json (shot {sid}.video): 'marketing_studio_video' defaults "
                            "duration to 15s in live CLI; set 'duration' explicitly in draft_params/final_params"
                        )
            elif v_model == "minimax_h3_max":
                warnings.append(
                    f"shotlist.json (shot {sid}.video): 'minimax_h3_max' costs 12.5 cr. and caps at 768p; "
                    "prefer 'minimax_h3' (10 cr. native 2K)"
                )
            if v_model in ("cinematic_studio_video_4_0", "seedance_2_5", "intone"):
                final_res = str(final_params.get("resolution") or "").lower()
                if final_res in ("1080p", "4k") and final_params.get("bitrate_mode") != "high":
                    warnings.append(
                        f"shotlist.json (shot {sid}.video.final_params): '{v_model}' at {final_res} "
                        "should set 'bitrate_mode': 'high' (0 cr. surcharge vs. standard)"
                    )
            if v_model in ("bytedance_video_upscale", "topaz_video", "video_upscale") and (
                str(draft_params.get("resolution") or "").lower() == "480p"
            ):
                warnings.append(
                    f"shotlist.json (shot {sid}.video): pixel-upscaling a 480p draft with '{v_model}' "
                    "causes halos/artifacts; prefer native 1080p or a clean >=720p source"
                )
            video_ref_count = (
                (len(video["image_references"]) if isinstance(video.get("image_references"), list) else 0)
                + (len(video["references"]) if isinstance(video.get("references"), list) else 0)
            )
            if v_model in (
                "kling3_0_motion_control",
                "hf_mult_motion_control",
                "hf_mult_motion_control_flash",
                "hf_mult_replace_object",
                "hf_mult_replace_object_flash",
                "intone",
                "draw_to_video",
            ) and (has_start or has_end):
                errors.append(
                    f"shotlist.json (shot {sid}.video): '{v_model}' live CLI does not accept "
                    "start_image/end_image; pass stills via image_references (or character_images for intone)"
                )
            if v_model in ("kling_4_0_flash", "reframe") and has_end:
                errors.append(
                    f"shotlist.json (shot {sid}.video): '{v_model}' live CLI does not accept "
                    "end_image; use kling4_0, kling_o3_flf, seedance_2_5, or wan3_0 for Start+End bridges"
                )
            if v_model == "kling_o3_flf" and has_end and not has_start:
                errors.append(
                    f"shotlist.json (shot {sid}.video): 'kling_o3_flf' live CEL requires "
                    "start_image whenever end_image is set"
                )
            total_video_imgs = video_ref_count + (1 if has_start else 0) + (1 if has_end else 0)
            if v_model in VIDEO_HARD_IMG_CAPS and total_video_imgs > VIDEO_HARD_IMG_CAPS[v_model]:
                errors.append(
                    f"shotlist.json (shot {sid}.video): {total_video_imgs} total images "
                    f"(start/end + image_references) exceeds live CEL limit ({VIDEO_HARD_IMG_CAPS[v_model]}) for '{v_model}'"
                )
            elif total_video_imgs > 5:
                warnings.append(
                    f"shotlist.json (shot {sid}.video): {total_video_imgs} total images "
                    "exceeds optimal R4/R5 video budget (2-5); prune off-screen refs to prevent texture bleed and rigid motion"
                )
            if v_model == "minimax_h3" and (has_start or has_end) and video_ref_count > 0:
                errors.append(
                    f"shotlist.json (shot {sid}.video): 'minimax_h3' live CEL forbids combining "
                    "start_image/end_image with image_references (mutually exclusive)"
                )
            if v_model in ("wan3_0", "wan3_0_prime") and (has_start or has_end) and video_ref_count > 0:
                warnings.append(
                    f"shotlist.json (shot {sid}.video): '{v_model}' live CEL forbids combining "
                    "start_image/end_image with image_references; omit --image_references at runtime or use seedance_2_5/kling4_0"
                )
            if (
                isinstance(start_src, str)
                and start_src.strip().endswith(".last_frame")
                and video_ref_count == 0
                and v_model in ("seedance_2_5", "cinematic_studio_video_4_0", "kling4_0", "kling_4_0_flash", "kling3_0")
            ):
                warnings.append(
                    f"shotlist.json (shot {sid}.video): bridging from '{start_src.strip()}' without "
                    "canonical R2 character/prop/location image_references risks photocopy cascade drift; include original locked IDs"
                )
            if (
                v_model in ("seedance_2_5", "cinematic_studio_video_4_0")
                and isinstance(start_src, str)
                and isinstance(end_src, str)
                and start_src.strip()
                and start_src.strip() == end_src.strip()
            ):
                pf_path = _resolve_prompt_file(video.get("prompt_file"))
                if pf_path is not None:
                    try:
                        prompt_lower = pf_path.read_text(encoding="utf-8").lower()
                    except OSError:
                        prompt_lower = ""
                    hit_phrases: list[str] = []
                    for phrase in ENG08_DRIFT_PHRASES:
                        for m in re.finditer(re.escape(phrase), prompt_lower):
                            prefix = prompt_lower[max(0, m.start() - 40) : m.start()]
                            if not ENG08_NEGATION_RE.search(prefix):
                                hit_phrases.append(phrase)
                                break
                    if hit_phrases:
                        warnings.append(
                            f"shotlist.json (shot {sid}.video): ENG-08 locked-tripod living still "
                            f"({start_src.strip()} == {end_src.strip()}) prompt '{video.get('prompt_file')}' "
                            f"contains drift-inducing phrase(s) {hit_phrases}; require stationary daylight "
                            "and fixed shadow edges to prevent caustic/shadow drift"
                        )

        shot_audio = shot.get("audio")
        if isinstance(shot_audio, dict):
            if shot_audio.get("enabled", True) is True:
                audio_sum += _num(
                    shot_audio.get("estimated_credits"), f"shot {sid}.audio.estimated_credits"
                )
            _check_prompt_file(shot_audio.get("prompt_file"), f"shot {sid}.audio")

        # Validate optional per-shot edit spec (trim_in, trim_out, crop_4k_punchin, grade, fade_out_black_s)
        edit_cfg = shot.get("edit")
        if edit_cfg is not None:
            if not isinstance(edit_cfg, dict):
                errors.append(f"shotlist.json (shot {sid}.edit): must be a JSON object")
            else:
                ti = edit_cfg.get("trim_in")
                to = edit_cfg.get("trim_out")
                if ti is not None and (isinstance(ti, bool) or not isinstance(ti, (int, float)) or ti < 0):
                    errors.append(f"shotlist.json (shot {sid}.edit.trim_in): must be a number >= 0")
                if to is not None and (isinstance(to, bool) or not isinstance(to, (int, float)) or to <= 0):
                    errors.append(f"shotlist.json (shot {sid}.edit.trim_out): must be a positive number")
                if isinstance(ti, (int, float)) and not isinstance(ti, bool) and isinstance(to, (int, float)) and not isinstance(to, bool) and to <= ti:
                    errors.append(f"shotlist.json (shot {sid}.edit): trim_out ({to}) must exceed trim_in ({ti})")
                fo = edit_cfg.get("fade_out_black_s")
                if fo is not None and (isinstance(fo, bool) or not isinstance(fo, (int, float)) or fo <= 0 or fo > 2.0):
                    errors.append(f"shotlist.json (shot {sid}.edit.fade_out_black_s): must be in (0, 2.0]")

        # Prompt timing validator for timecoded multi-beat video prompts
        if isinstance(video, dict) and isinstance(video.get("prompt_file"), str) and video["prompt_file"].strip():
            pf = Path(video["prompt_file"].strip())
            resolved_pf = pf if pf.is_absolute() else (campaign_dir / pf if (campaign_dir / pf).is_file() else repo_root / pf)
            shot_dur = shot.get("duration_s")
            # When edit.trim_out harvests a sub-window from a longer generated take, compare prompt
            # timecodes against the raw generation duration (final_params/draft_params.duration) first.
            has_trim = isinstance(edit_cfg, dict) and edit_cfg.get("trim_out") is not None
            raw_gen_dur = None
            if has_trim:
                for pdict in (final_params, draft_params, video):
                    cand = pdict.get("duration") if isinstance(pdict, dict) else None
                    if isinstance(cand, (int, float)) and not isinstance(cand, bool) and cand > 0:
                        raw_gen_dur = float(cand)
                        break
            target_prompt_dur = raw_gen_dur if has_trim else (
                float(shot_dur) if isinstance(shot_dur, (int, float)) and not isinstance(shot_dur, bool) and shot_dur > 0 else None
            )
            if resolved_pf.is_file() and target_prompt_dur is not None and target_prompt_dur > 0:
                try:
                    ptxt = resolved_pf.read_text(encoding="utf-8", errors="ignore")
                    ranges = [(float(m.group(1)), float(m.group(2))) for m in PROMPT_TIME_RANGE_RE.finditer(ptxt)]
                    valid_ranges = [(a, b) for a, b in ranges if b > a]
                    if len(valid_ranges) >= 2:
                        max_end = max(b for _, b in valid_ranges)
                        if abs(max_end - target_prompt_dur) > 0.5:
                            warnings.append(
                                f"shotlist.json (shot {sid}.video): prompt timecodes end at {max_end:g}s "
                                f"but target duration={target_prompt_dur:g}s (delta > 0.5s)"
                            )
                except OSError:
                    pass

        # Anti-static-shot / long-clip drift warning (> 8s single-shot I2V compounds morphing & stalls pacing)
        if isinstance(video, dict):
            vm = str(video.get("model") or "").strip()
            shot_dur_num = (
                float(shot["duration_s"])
                if isinstance(shot.get("duration_s"), (int, float)) and not isinstance(shot.get("duration_s"), bool)
                else None
            )
            multi_shot_flag = bool(
                (isinstance(final_params, dict) and final_params.get("multi_shots") is True)
                or (isinstance(draft_params, dict) and draft_params.get("multi_shots") is True)
                or video.get("multi_shots") is True
            )
            if (
                shot_dur_num is not None
                and shot_dur_num > 8.0
                and vm not in ("intone", "seedance_2_5", "cinematic_studio_video_4_0", "cinematic_studio_video_3_5", "cinematic_studio_3_0")
                and not multi_shot_flag
            ):
                warnings.append(
                    f"shotlist.json (shot {sid}.video): single-shot I2V duration ({shot_dur_num:g}s > 8s) on '{vm}' "
                    "compounds hand/face/object morphing and stalls pacing; split into 3-6s beats, add reaction/cutaway coverage, or use 4K punch-in / multi-shot"
                )

    # Duration check against target_duration_s (±0.5s)
    target_dur = data.get("target_duration_s")
    if target_dur is not None:
        if (
            isinstance(target_dur, bool)
            or not isinstance(target_dur, (int, float))
            or not math.isfinite(float(target_dur))
            or target_dur <= 0
        ):
            errors.append(
                f"shotlist.json: target_duration_s must be a positive number, got {target_dur!r}"
            )
        elif all_have_duration and abs(total_duration_s - float(target_dur)) > 0.5:
            errors.append(
                f"shotlist.json: sum(shots[].duration_s)={total_duration_s:.2f}s differs from "
                f"target_duration_s={float(target_dur):.2f}s by more than 0.5s"
            )

    # Validate start_image_from / end_image_from references
    for sid, shot in shots_by_id.items():
        refs_to_check: list[tuple[str, Any]] = []
        if "start_image_from" in shot:
            refs_to_check.append(("start_image_from", shot["start_image_from"]))
        if "end_image_from" in shot:
            refs_to_check.append(("end_image_from", shot["end_image_from"]))
        video = shot.get("video")
        if isinstance(video, dict):
            if "start_image_from" in video:
                refs_to_check.append(("video.start_image_from", video["start_image_from"]))
            if "end_image_from" in video:
                refs_to_check.append(("video.end_image_from", video["end_image_from"]))

        for field_label, ref_val in refs_to_check:
            if ref_val is None:
                continue
            if not isinstance(ref_val, str) or not ref_val.strip():
                errors.append(
                    f"shotlist.json (shot {sid}.{field_label}): invalid reference {ref_val!r}"
                )
                continue
            ref_str = ref_val.strip()
            if ref_str in all_ref_ids:
                continue
            m_still = re.match(r"^([^.]+)\.still$", ref_str)
            m_last = re.match(r"^([^.]+)\.last_frame$", ref_str)
            if m_still:
                target_id = m_still.group(1)
                target_shot = shots_by_id.get(target_id)
                if target_shot is None:
                    errors.append(
                        f"shotlist.json (shot {sid}.{field_label}): references unknown shot '{target_id}'"
                    )
                elif not isinstance(target_shot.get("still"), dict) or not target_shot["still"]:
                    errors.append(
                        f"shotlist.json (shot {sid}.{field_label}): target shot '{target_id}' has no 'still' defined"
                    )
            elif m_last:
                target_id = m_last.group(1)
                target_shot = shots_by_id.get(target_id)
                if target_shot is None:
                    errors.append(
                        f"shotlist.json (shot {sid}.{field_label}): references unknown shot '{target_id}'"
                    )
                elif (
                    target_shot.get("still_only") is True
                    or not isinstance(target_shot.get("video"), dict)
                    or not target_shot["video"]
                ):
                    errors.append(
                        f"shotlist.json (shot {sid}.{field_label}): target shot '{target_id}' has no 'video' defined"
                    )
            else:
                errors.append(
                    f"shotlist.json (shot {sid}.{field_label}): expected '<shot_id>.still', "
                    f"'<shot_id>.last_frame', reference ID, or lookbook ID, got '{ref_val}'"
                )

    # Top-level audio (sum credits ONLY when enabled is true!)
    top_audio = data.get("audio")
    if isinstance(top_audio, dict):
        if "estimated_credits" in top_audio and top_audio.get("enabled") is True:
            audio_sum += _num(top_audio.get("estimated_credits"), "audio.estimated_credits")
        _check_prompt_file(top_audio.get("prompt_file"), "audio")
        for track_name, track_obj in top_audio.items():
            if not isinstance(track_obj, dict):
                continue
            enabled = track_obj.get("enabled") is True
            _check_status_and_version(
                track_obj,
                f"audio.{track_name}",
                require_status=enabled,
                count_status=enabled,
            )
            if enabled:
                audio_sum += _num(
                    track_obj.get("estimated_credits"),
                    f"audio.{track_name}.estimated_credits",
                )
            _check_prompt_file(track_obj.get("prompt_file"), f"audio.{track_name}")
            tracks = track_obj.get("tracks")
            if isinstance(tracks, list):
                for tidx, tr in enumerate(tracks):
                    if isinstance(tr, dict):
                        _check_prompt_file(tr.get("prompt_file"), f"audio.{track_name}.tracks[{tidx}]")
                        _check_prompt_file(tr.get("script_file"), f"audio.{track_name}.tracks[{tidx}]")
                        ts_in = tr.get("trim_start_s")
                        ts_out = tr.get("trim_end_s")
                        if ts_in is not None and (isinstance(ts_in, bool) or not isinstance(ts_in, (int, float)) or ts_in < 0):
                            errors.append(f"shotlist.json (audio.{track_name}.tracks[{tidx}].trim_start_s): must be a number >= 0")
                        if ts_out is not None and (isinstance(ts_out, bool) or not isinstance(ts_out, (int, float)) or ts_out <= 0):
                            errors.append(f"shotlist.json (audio.{track_name}.tracks[{tidx}].trim_end_s): must be a positive number")
                        if (
                            isinstance(ts_in, (int, float))
                            and not isinstance(ts_in, bool)
                            and isinstance(ts_out, (int, float))
                            and not isinstance(ts_out, bool)
                            and ts_out <= ts_in
                        ):
                            errors.append(
                                f"shotlist.json (audio.{track_name}.tracks[{tidx}]): trim_end_s ({ts_out}) must exceed trim_start_s ({ts_in})"
                            )
    elif isinstance(top_audio, list):
        for idx, track_obj in enumerate(top_audio):
            if not isinstance(track_obj, dict):
                continue
            enabled = track_obj.get("enabled") is True
            _check_status_and_version(
                track_obj,
                f"audio[{idx}]",
                require_status=enabled,
                count_status=enabled,
            )
            if enabled:
                audio_sum += _num(
                    track_obj.get("estimated_credits"), f"audio[{idx}].estimated_credits"
                )
            _check_prompt_file(track_obj.get("prompt_file"), f"audio[{idx}]")

    r3_stills_audio = still_sum + audio_sum
    r4_draft_video = video_draft_sum
    r5_final_video = video_final_sum
    planned_total = r2_lookbook + r3_stills_audio + r4_draft_video + r5_final_video

    result["budget"] = {
        "r2_lookbook": _clean_num(r2_lookbook),
        "r3_stills_audio": _clean_num(r3_stills_audio),
        "r4_draft_video": _clean_num(r4_draft_video),
        "r5_final_video": _clean_num(r5_final_video),
        "planned_total": _clean_num(planned_total),
        "campaign_cap": campaign_cap,
        "remaining_planned": (
            _clean_num(campaign_cap - planned_total) if campaign_cap is not None else None
        ),
    }

    if campaign_cap is not None:
        if planned_total > campaign_cap:
            errors.append(
                f"shotlist.json: planned total ({_clean_num(planned_total)} credits across R2–R5) "
                f"exceeds brief.md Campaign cap ({campaign_cap} credits)"
            )
    else:
        warnings.append("brief.md Campaign cap unavailable; skipped shotlist cap comparison")

    return result


def resolve_shotlist_path(target: str | Path) -> Path:
    p = Path(target)
    if p.is_dir():
        return p / "shotlist.json"
    return p


def validate_campaign(
    target: str | Path, *, allow_draft: bool = False
) -> dict[str, Any]:
    """Validate cohesive campaign state (brief.md + optional taste-log.md + shotlist.json)."""
    shotlist_path = resolve_shotlist_path(target)
    errors: list[str] = []
    warnings: list[str] = []

    if not shotlist_path.is_file():
        return {
            "ok": False,
            "file_found": False,
            "campaign_dir": str(shotlist_path.parent),
            "shotlist_path": str(shotlist_path),
            "brief_status": None,
            "taste_log_entries": 0,
            "shot_count": 0,
            "lookbook_count": 0,
            "status_counts": {st: 0 for st in VALID_ASSET_STATUSES},
            "budget": None,
            "warnings": [],
            "errors": [f"shotlist file not found: {shotlist_path}"],
        }

    campaign_dir = shotlist_path.resolve().parent
    repo_root = _CHECK_BRIEF.find_repo_root(shotlist_path)

    # 1. brief.md
    brief_path = campaign_dir / "brief.md"
    brief_status: str | None = None
    campaign_cap: int | None = None
    if not brief_path.is_file():
        errors.append(f"missing required brief.md in campaign directory: {campaign_dir}")
    else:
        brief_report = _CHECK_BRIEF.validate_brief(brief_path)
        brief_status = brief_report.get("status")
        for berr in brief_report.get("errors") or []:
            errors.append(f"brief.md: {berr}")
        for bwarn in brief_report.get("warnings") or []:
            warnings.append(f"brief.md: {bwarn}")
        if brief_status not in {"active", "done"} and not allow_draft:
            errors.append(
                f"brief.md: status is '{brief_status}' "
                "(must be 'active' or 'done'; pass --allow-draft to allow draft)"
            )
        env = brief_report.get("budget_envelope") or {}
        if isinstance(env.get("campaign_cap"), int):
            campaign_cap = env["campaign_cap"]

    # 2. Optional taste-log.md & compiled taste-active.md
    taste_log_entries = 0
    taste_active_present = False
    taste_active_fresh: bool | None = None
    taste_path = campaign_dir / "taste-log.md"
    if taste_path.is_file():
        t_info = _validate_taste_log(taste_path, errors, warnings)
        taste_log_entries = t_info["entries"]
        taste_active_present = t_info["active_present"]
        taste_active_fresh = t_info["active_fresh"]

    # 3. shotlist.json
    sl = _validate_shotlist(
        shotlist_path, campaign_dir, repo_root, campaign_cap, errors, warnings
    )

    # 4. Receipt reconciliation check (detect shotlist.json vs receipts.jsonl model drift)
    receipts_path = campaign_dir / "receipts.jsonl"
    if receipts_path.is_file():
        try:
            sl_data = json.loads(shotlist_path.read_text(encoding="utf-8"))
            latest_vid_model: dict[str, str] = {}
            for line in receipts_path.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                rec = json.loads(line)
                if (
                    isinstance(rec, dict)
                    and rec.get("kind") == "video"
                    and rec.get("status") in ("ok", "completed", "succeeded")
                    and rec.get("shot")
                    and rec.get("model")
                ):
                    latest_vid_model[str(rec["shot"])] = str(rec["model"])
            for shot in sl_data.get("shots") or []:
                if not isinstance(shot, dict):
                    continue
                sid = str(shot.get("id") or "")
                vobj = shot.get("video")
                if sid in latest_vid_model and isinstance(vobj, dict) and vobj.get("model"):
                    if str(vobj["model"]) != latest_vid_model[sid]:
                        warnings.append(
                            f"shotlist.json (shot {sid}.video): manifest model '{vobj['model']}' differs "
                            f"from latest completed receipt model '{latest_vid_model[sid]}'; reconcile manifest"
                        )
        except (OSError, json.JSONDecodeError):
            pass

    # 5. R0 real-world visual grounding check (external brand/site URL with zero visual references)
    if brief_path.is_file():
        try:
            btext = brief_path.read_text(encoding="utf-8", errors="ignore")
            ext_urls = [
                u for u in re.findall(r"https?://[^\s)>\"']+", btext)
                if "higgsfield.ai" not in u.lower()
            ]
            sl_data = json.loads(shotlist_path.read_text(encoding="utf-8"))
            has_refs = bool(sl_data.get("references"))
            ref_dir = campaign_dir / "media" / "references"
            has_ref_files = ref_dir.is_dir() and any(
                p.is_file() and not p.name.startswith(".") for p in ref_dir.iterdir()
            )
            if ext_urls and not has_refs and not has_ref_files:
                warnings.append(
                    "R0 visual grounding: brief.md cites an external brand/site URL but no visual references "
                    "are registered in shotlist.json or media/references/; capture real reference photos before R2"
                )
        except (OSError, json.JSONDecodeError):
            pass

    return {
        "ok": len(errors) == 0,
        "file_found": True,
        "campaign_dir": str(campaign_dir),
        "shotlist_path": str(shotlist_path),
        "brief_status": brief_status,
        "taste_log_present": taste_path.is_file(),
        "taste_log_entries": taste_log_entries,
        "taste_active_present": taste_active_present,
        "taste_active_fresh": taste_active_fresh,
        "shot_count": sl["shot_count"],
        "lookbook_count": sl["lookbook_count"],
        "status_counts": sl["status_counts"],
        "budget": sl["budget"],
        "warnings": warnings,
        "errors": errors,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Validate campaign brief.md, optional taste-log.md, and shotlist.json."
    )
    parser.add_argument(
        "target",
        help="Path to campaign directory or shotlist.json file.",
    )
    parser.add_argument(
        "--allow-draft",
        action="store_true",
        help="Allow brief.md at status: draft without failing validation.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="as_json",
        help="Emit validation report as JSON.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    report = validate_campaign(args.target, allow_draft=args.allow_draft)

    if args.as_json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        if not report["file_found"]:
            print(f"ERROR: {report['errors'][0]}", file=sys.stderr)
            return 2

        state = "OK" if report["ok"] else "FAIL"
        print(
            f"[{state}] {report['shotlist_path']} "
            f"(brief={report['brief_status']}, shots={report['shot_count']}, "
            f"lookbook={report['lookbook_count']}, taste_log={report['taste_log_entries']} entries)"
        )
        sc = report["status_counts"]
        print(
            f"  Assets: LOCKED={sc['LOCKED']}, IN_REVIEW={sc['IN_REVIEW']}, "
            f"ITERATING={sc['ITERATING']}, DRAFT={sc['DRAFT']}"
        )
        b = report.get("budget")
        if b:
            cap_str = str(b["campaign_cap"]) if b["campaign_cap"] is not None else "?"
            print(
                f"  Budget: R2={b['r2_lookbook']}, R3={b['r3_stills_audio']}, "
                f"R4={b['r4_draft_video']}, R5={b['r5_final_video']} | "
                f"Total={b['planned_total']} / {cap_str} credits"
            )
        for w in report["warnings"]:
            print(f"  WARN: {w}")
        for e in report["errors"]:
            print(f"  ERROR: {e}")

    if not report["file_found"]:
        return 2
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())

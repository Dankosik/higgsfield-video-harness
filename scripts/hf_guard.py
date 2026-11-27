#!/usr/bin/env python3
"""Two-layer budget-enforcing, lock-aware, atomic-reservation wrapper around the higgsfield CLI."""

from __future__ import annotations

import sys

sys.dont_write_bytecode = True

import argparse
import contextlib
import datetime
import fcntl
import hashlib
import http.client
import importlib.util
import json
import math
import os
import shutil
import subprocess
import urllib.error
import urllib.parse
import urllib.request
import uuid
from collections.abc import Iterator
from pathlib import Path
from typing import Any

VALID_ROUNDS = ("R2", "R3", "R4", "R4A", "R4B", "R5")
VALID_KINDS = ("lookbook", "still", "video", "audio", "analysis")
VALID_HF_COMMANDS = ("generate", "product-photoshoot", "soul-id")
VALID_WEB_STATUSES = ("completed", "failed", "rejected", "ip_detected")

IN_FLIGHT_STATUSES = frozenset(
    {
        "reserved",
        "in_progress",
        "running",
        "queued",
        "pending",
        "processing",
        "submitted",
        "starting",
        "timeout",
        "timed_out",
    }
)
COMPLETED_STATUSES = frozenset({"completed", "succeeded", "success", "done", "finished"})
FAILED_STATUSES = frozenset(
    {"failed", "error", "cancelled", "canceled", "rejected", "ip_detected"}
)

AMBIGUOUS_TRANSPORT_MARKERS = (
    "timeout",
    "timed out",
    "deadline exceeded",
    "connection reset",
    "broken pipe",
    "unexpected eof",
    "502",
    "503",
    "504",
)


class CorruptReceiptsError(RuntimeError):
    """Raised when receipts.jsonl contains malformed JSONL data."""


class CorruptShotlistError(RuntimeError):
    """Raised when shotlist.json exists but cannot be parsed as a JSON object."""


def _load_check_brief():
    mod_path = Path(__file__).resolve().with_name("check-brief.py")
    spec = importlib.util.spec_from_file_location("check_brief", mod_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load sibling module: {mod_path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_CHECK_BRIEF = _load_check_brief()


def _utc_now_iso() -> str:
    return (
        datetime.datetime.now(datetime.UTC)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _is_number(val: Any) -> bool:
    return (
        isinstance(val, (int, float))
        and not isinstance(val, bool)
        and math.isfinite(float(val))
    )


def _extract_numeric_field(payload: Any, keys: tuple[str, ...]) -> float | None:
    """Search payload (shallow then nested dicts/lists) for the first finite numeric value matching keys."""
    if isinstance(payload, list):
        for item in payload:
            found = _extract_numeric_field(item, keys)
            if found is not None:
                return found
        return None
    if not isinstance(payload, dict):
        return None
    for k in keys:
        if k in payload:
            v = payload[k]
            if _is_number(v):
                return float(v)
            if isinstance(v, str):
                try:
                    f = float(v.strip())
                    if math.isfinite(f):
                        return f
                except ValueError:
                    pass
    for nested_key in ("data", "estimate", "result", "results", "account", "billing", "job", "jobs", "cost"):
        nested = payload.get(nested_key)
        if isinstance(nested, (dict, list)):
            found = _extract_numeric_field(nested, keys)
            if found is not None:
                return found
    for v in payload.values():
        if isinstance(v, (dict, list)):
            found = _extract_numeric_field(v, keys)
            if found is not None:
                return found
    return None


def _extract_string_field(payload: Any, keys: tuple[str, ...]) -> str | None:
    if isinstance(payload, list):
        for item in payload:
            if isinstance(item, str) and item.strip():
                if any(k in ("url", "output_url", "media_url") for k in keys):
                    return item.strip()
            elif isinstance(item, (dict, list)):
                found = _extract_string_field(item, keys)
                if found is not None:
                    return found
        return None
    if not isinstance(payload, dict):
        return None
    for k in keys:
        v = payload.get(k)
        if isinstance(v, str) and v.strip():
            return v.strip()
    for nested_key in (
        "data",
        "result",
        "results",
        "raw",
        "original",
        "min",
        "job",
        "output",
        "asset",
        "upload",
        "media",
        "image",
        "video",
        "audio",
    ):
        nested = payload.get(nested_key)
        if isinstance(nested, dict):
            found = _extract_string_field(nested, keys)
            if found is not None:
                return found
    for list_key in ("jobs", "outputs", "results", "assets", "files", "media", "items"):
        items = payload.get(list_key)
        if isinstance(items, list):
            for item in items:
                if isinstance(item, str) and item.strip():
                    if any(k in ("url", "output_url", "media_url") for k in keys):
                        return item.strip()
                elif isinstance(item, (dict, list)):
                    found = _extract_string_field(item, keys)
                    if found is not None:
                        return found
    return None


def _clean_num(val: float) -> int | float:
    return int(val) if float(val).is_integer() else round(val, 4)


def compute_params_hash(
    *,
    shot: str,
    kind: str,
    round_name: str,
    model: str,
    is_workflow: bool,
    args: list[str],
    hf_command: str = "generate",
    variant: str = "",
    version: int = 1,
) -> str:
    """Compute deterministic SHA-256 over canonical generation parameters."""
    payload: dict[str, Any] = {
        "shot": shot,
        "kind": kind,
        "round": round_name,
        "variant": variant,
        "version": version,
        "model": model,
        "is_workflow": bool(is_workflow),
        "args": list(args),
    }
    if hf_command != "generate":
        payload["command"] = hf_command
    canonical = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


@contextlib.contextmanager
def _receipts_lock(campaign_dir: Path) -> Iterator[None]:
    campaign_dir.mkdir(parents=True, exist_ok=True)
    lock_path = campaign_dir / ".receipts.lock"
    with lock_path.open("a+", encoding="utf-8") as lock_file:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)


def _read_receipts_raw(campaign_dir: Path) -> list[dict[str, Any]]:
    receipts_path = campaign_dir / "receipts.jsonl"
    if not receipts_path.is_file():
        return []
    records: list[dict[str, Any]] = []
    for lineno, raw_line in enumerate(
        receipts_path.read_text(encoding="utf-8").splitlines(), start=1
    ):
        line = raw_line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError as exc:
            raise CorruptReceiptsError(
                f"malformed JSON in {receipts_path}:{lineno}: {exc}"
            ) from exc
        if not isinstance(obj, dict):
            raise CorruptReceiptsError(
                f"expected JSON object in {receipts_path}:{lineno}, got {type(obj).__name__}"
            )
        records.append(obj)
    return records


def _collapse_receipts(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Collapse append-only journal by reservation_id and job_id (latest record wins)."""
    by_res: dict[str, int] = {}
    by_job: dict[str, int] = {}
    output: list[dict[str, Any]] = []

    for rec in records:
        if rec.get("status") == "dry_run":
            continue
        rid = rec.get("reservation_id")
        rid_key = rid.strip() if isinstance(rid, str) and rid.strip() else ""
        jid = rec.get("job_id")
        jid_key = jid.strip() if isinstance(jid, str) and jid.strip() else ""

        target_idx: int | None = None
        if rid_key and rid_key in by_res:
            target_idx = by_res[rid_key]
        elif jid_key and jid_key in by_job:
            target_idx = by_job[jid_key]

        if target_idx is not None:
            output[target_idx] = rec
            if rid_key:
                by_res[rid_key] = target_idx
            if jid_key:
                by_job[jid_key] = target_idx
        else:
            idx = len(output)
            output.append(rec)
            if rid_key:
                by_res[rid_key] = idx
            if jid_key:
                by_job[jid_key] = idx
    return output


def _append_receipt(campaign_dir: Path, record: dict[str, Any]) -> None:
    receipts_path = campaign_dir / "receipts.jsonl"
    with receipts_path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")
        fh.flush()
        os.fsync(fh.fileno())


def _effective_credits(rec: dict[str, Any]) -> float:
    """Compute effective spend for one collapsed receipt record."""
    status = str(rec.get("status") or "").lower()
    kind = str(rec.get("kind") or "video").lower()
    if kind == "upload":
        return 0.0
    if status == "rejected" and not str(rec.get("job_id") or "").strip():
        return 0.0
    if status in IN_FLIGHT_STATUSES:
        for key in ("credits", "estimated_credits"):
            v = rec.get(key)
            if _is_number(v) and float(v) > 0:
                return float(v)
        v = rec.get("credits")
        return float(v) if _is_number(v) and float(v) >= 0 else 0.0
    for key in ("actual_credits", "credits"):
        v = rec.get(key)
        if _is_number(v) and float(v) >= 0:
            return float(v)
    return 0.0


def _counts_as_attempt(rec: dict[str, Any]) -> bool:
    status = str(rec.get("status") or "").lower()
    kind = str(rec.get("kind") or "video").lower()
    channel = str(rec.get("channel") or "").lower()
    if kind == "upload" or channel == "web_unlimited":
        return False
    return not (status == "rejected" and not str(rec.get("job_id") or "").strip())


def _record_variant(rec: dict[str, Any]) -> str:
    val = rec.get("variant")
    return val.strip() if isinstance(val, str) else ""


def _record_version(rec: dict[str, Any]) -> int:
    val = rec.get("version")
    if isinstance(val, int) and not isinstance(val, bool) and val >= 1:
        return val
    return 1


def _summarize_receipts(
    records: list[dict[str, Any]],
) -> tuple[
    float,
    dict[str, float],
    dict[tuple[str, str, str, str, int], int],
    dict[tuple[str, str, int], set[str]],
    float,
]:
    """Return (total_spent, spent_by_round, attempts, lookbook_variants_seen, active_reserved)."""
    collapsed = _collapse_receipts(records)
    total_spent = 0.0
    active_reserved = 0.0
    spent_by_round: dict[str, float] = {r: 0.0 for r in VALID_ROUNDS}
    attempts: dict[tuple[str, str, str, str, int], int] = {}
    lookbook_variants_seen: dict[tuple[str, str, int], set[str]] = {}

    for rec in collapsed:
        round_name = str(rec.get("round") or "")
        shot = str(rec.get("shot") or "")
        kind = str(rec.get("kind") or "video")
        status = str(rec.get("status") or "").lower()
        variant = _record_variant(rec)
        version = _record_version(rec)

        eff = _effective_credits(rec)
        total_spent += eff
        if status in IN_FLIGHT_STATUSES:
            active_reserved += eff
        if round_name in spent_by_round:
            spent_by_round[round_name] += eff

        if shot and round_name and _counts_as_attempt(rec):
            key = (shot, kind, round_name, variant, version)
            attempts[key] = attempts.get(key, 0) + 1
            if kind == "lookbook" and variant:
                lb_key = (shot, round_name, version)
                lookbook_variants_seen.setdefault(lb_key, set()).add(variant)

    return total_spent, spent_by_round, attempts, lookbook_variants_seen, active_reserved


def _run_cli(cmd: list[str]) -> tuple[int, str, str, Any]:
    """Execute higgsfield CLI command and attempt to parse stdout as JSON."""
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError:
        return 127, "", f"higgsfield binary not found: {cmd[0]}", None

    parsed: Any = None
    stdout = proc.stdout.strip()
    if stdout:
        try:
            parsed = json.loads(stdout)
        except json.JSONDecodeError:
            decoder = json.JSONDecoder()
            idx = 0
            length = len(stdout)
            while idx < length:
                while idx < length and stdout[idx] not in "{[":
                    idx += 1
                if idx >= length:
                    break
                try:
                    obj, end = decoder.raw_decode(stdout, idx)
                    parsed = obj
                    idx = end
                except json.JSONDecodeError:
                    idx += 1
    return proc.returncode, proc.stdout, proc.stderr, parsed


def _resolve_hf_bin(cli_value: str | None) -> str:
    if cli_value:
        return cli_value
    return os.environ.get("HIGGSFIELD_BIN", "higgsfield")


def _load_envelope_or_error(
    campaign_dir: Path,
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    brief_path = campaign_dir / "brief.md"
    if not brief_path.is_file():
        return None, {
            "ok": False,
            "error_code": "brief_not_active",
            "message": f"brief.md not found in campaign directory: {campaign_dir}",
        }
    envelope = _CHECK_BRIEF.parse_budget_envelope(brief_path)
    if envelope.get("status") != "active":
        return None, {
            "ok": False,
            "error_code": "brief_not_active",
            "status": envelope.get("status"),
            "message": (
                f"brief.md status is '{envelope.get('status')}' "
                "(paid generations and uploads require status: active)"
            ),
        }
    if envelope.get("errors"):
        return None, {
            "ok": False,
            "error_code": "invalid_budget_envelope",
            "message": "; ".join(envelope["errors"]),
            "errors": envelope["errors"],
        }
    return envelope, None


def _validate_round_cap(round_cap: float | None) -> dict[str, Any] | None:
    if round_cap is None or not math.isfinite(round_cap) or round_cap < 0:
        return {
            "ok": False,
            "error_code": "invalid_round_cap",
            "round_cap": round_cap,
            "message": f"--round-cap must be a finite number >= 0, got {round_cap!r}",
        }
    return None


def _validate_variant_arg(kind: str, raw_variant: str | None) -> tuple[str, dict[str, Any] | None]:
    variant = (raw_variant or "").strip()
    if variant and kind != "lookbook":
        return "", {
            "ok": False,
            "error_code": "invalid_variant",
            "kind": kind,
            "variant": variant,
            "message": f"--variant is only allowed when --kind is 'lookbook' (got kind='{kind}')",
        }
    return variant, None


def _load_shotlist(campaign_dir: Path) -> dict[str, Any] | None:
    """Load shotlist.json fail-closed if present."""
    shotlist_path = campaign_dir / "shotlist.json"
    if not shotlist_path.is_file():
        return None
    try:
        data = json.loads(shotlist_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CorruptShotlistError(
            f"failed to read or parse {shotlist_path}: {exc}"
        ) from exc
    if not isinstance(data, dict):
        raise CorruptShotlistError(
            f"expected JSON object in {shotlist_path}, got {type(data).__name__}"
        )
    return data


def _resolve_shotlist_asset(
    data: dict[str, Any], shot: str, kind: str
) -> tuple[dict[str, Any] | None, dict[str, Any] | None, str | None]:
    """Resolve (asset_dict, parent_dict, asset_path) in shotlist.json for (shot, kind)."""
    if kind == "lookbook":
        for item in data.get("lookbook") or []:
            if isinstance(item, dict) and item.get("id") == shot:
                return item, None, f"lookbook.{shot}"
        return None, None, None

    if kind in ("still", "video"):
        for s in data.get("shots") or []:
            if isinstance(s, dict) and s.get("id") == shot:
                sub = s.get(kind)
                if isinstance(sub, dict):
                    return sub, None, f"shots.{shot}.{kind}"
        return None, None, None

    if kind == "audio":
        audio = data.get("audio")
        if isinstance(audio, dict):
            # (a) Direct section key match (e.g. music, voiceover, sfx)
            direct = audio.get(shot)
            if isinstance(direct, dict):
                return direct, None, f"audio.{shot}"

            # (c) Exact track ID match inside audio.<section>.tracks[]
            for sec_name, sec_obj in audio.items():
                if not isinstance(sec_obj, dict):
                    continue
                tracks = sec_obj.get("tracks")
                if isinstance(tracks, list):
                    for tr in tracks:
                        if isinstance(tr, dict) and tr.get("id") == shot:
                            return tr, sec_obj, f"audio.{sec_name}.tracks.{shot}"

            # (b) Prefix aliases (music*, vo*/voice*, sfx*)
            alias_target: str | None = None
            if shot.startswith("music"):
                alias_target = "music"
            elif shot.startswith(("vo", "voice")):
                alias_target = "voiceover"
            elif shot.startswith("sfx"):
                alias_target = "sfx"
            if alias_target and isinstance(audio.get(alias_target), dict):
                return audio[alias_target], None, f"audio.{alias_target}"

        # (d) Per-shot audio matching shots[].id
        for s in data.get("shots") or []:
            if isinstance(s, dict) and s.get("id") == shot:
                sa = s.get("audio")
                if isinstance(sa, dict):
                    return sa, None, f"shots.{shot}.audio"

    return None, None, None


def _check_asset_locked(
    shotlist_data: dict[str, Any] | None, shot: str, kind: str
) -> tuple[bool, str | None]:
    """Return (is_locked, asset_path) against loaded shotlist.json."""
    if shotlist_data is None:
        return False, None
    asset, parent, asset_path = _resolve_shotlist_asset(shotlist_data, shot, kind)
    if asset is None:
        return False, None
    asset_status = str(asset.get("status") or "").strip().upper()
    parent_status = (
        str(parent.get("status") or "").strip().upper() if isinstance(parent, dict) else ""
    )
    if asset_status == "LOCKED" or parent_status == "LOCKED":
        return True, asset_path
    return False, None


def _resolve_and_validate_version(
    shotlist_data: dict[str, Any] | None,
    shot: str,
    kind: str,
    cli_version: int | None,
) -> tuple[int | None, dict[str, Any] | None]:
    """Validate --version and reconcile against shotlist.json asset version."""
    if cli_version is not None and (isinstance(cli_version, bool) or cli_version < 1):
        return None, {
            "ok": False,
            "error_code": "invalid_version",
            "version": cli_version,
            "message": f"--version must be an integer >= 1, got {cli_version!r}",
        }

    shotlist_version: int | None = None
    asset_path: str | None = None
    if shotlist_data is not None:
        asset, parent, asset_path = _resolve_shotlist_asset(shotlist_data, shot, kind)
        raw_ver = None
        if isinstance(asset, dict) and asset.get("version") is not None:
            raw_ver = asset.get("version")
        elif isinstance(parent, dict) and parent.get("version") is not None:
            raw_ver = parent.get("version")
        if isinstance(raw_ver, int) and not isinstance(raw_ver, bool) and raw_ver >= 1:
            shotlist_version = raw_ver

    if shotlist_version is not None:
        if cli_version is None:
            return shotlist_version, None
        if cli_version != shotlist_version:
            return None, {
                "ok": False,
                "error_code": "version_mismatch",
                "shot": shot,
                "kind": kind,
                "asset": asset_path,
                "version": cli_version,
                "shotlist_version": shotlist_version,
                "message": (
                    f"--version {cli_version} does not match shotlist.json "
                    f"{asset_path} version {shotlist_version}"
                ),
            }
        return cli_version, None

    return (cli_version if cli_version is not None else 1), None


def _inspect_shotlist_guard(
    campaign_dir: Path,
    shot: str,
    kind: str,
    round_name: str,
    cli_version: int | None,
) -> tuple[int | None, dict[str, Any] | None]:
    """Fail-closed shotlist load, LOCKED check, and version validation."""
    try:
        shotlist_data = _load_shotlist(campaign_dir)
    except CorruptShotlistError as exc:
        return None, {
            "ok": False,
            "error_code": "corrupt_shotlist",
            "campaign": str(campaign_dir),
            "message": str(exc),
        }

    is_locked, asset_path = _check_asset_locked(shotlist_data, shot, kind)
    if is_locked:
        return None, {
            "ok": False,
            "error_code": "asset_locked",
            "campaign": str(campaign_dir),
            "shot": shot,
            "kind": kind,
            "round": round_name,
            "asset": asset_path,
            "message": (
                f"asset '{asset_path}' is LOCKED in shotlist.json; "
                "Root Producer must transition status to ITERATING and bump version "
                "after explicit Director unlock"
            ),
        }

    version, ver_err = _resolve_and_validate_version(shotlist_data, shot, kind, cli_version)
    if ver_err is not None:
        return None, ver_err
    return version, None


PRODUCT_PHOTOSHOOT_VALUE_FLAGS = frozenset(
    {"--mode", "--count", "--brand_context", "--product_context", "--interval", "--timeout"}
)
PRODUCT_PHOTOSHOOT_BOOL_FLAGS = frozenset({"--enhance-only"})
GLOBAL_CLI_BOOL_FLAGS = frozenset({"--json", "--no-color"})

MEDIA_FLAG_NAMES = frozenset(
    {
        "start_image",
        "end_image",
        "image",
        "images",
        "image_references",
        "image_reference",
        "video",
        "videos",
        "video_references",
        "video_reference",
        "audio",
        "audios",
        "audio_references",
        "audio_reference",
        "character_images",
        "character_image",
        "location_image",
        "location_images",
        "input_images",
        "input_image",
        "input_video",
        "input_videos",
        "input_audio",
        "product_image",
        "product_images",
        "ref_image",
        "ref_images",
        "reference_image",
        "reference_images",
        "reference_video",
        "reference_videos",
        "reference_audio",
        "mask",
        "mask_image",
        "media",
        "medias",
        "first_frame",
        "last_frame",
        "source_image",
        "source_video",
        "target_image",
        "target_video",
        "driving_video",
        "face_image",
        "style_image",
        "init_image",
    }
)

MEDIA_FILE_EXTENSIONS = (
    ".png",
    ".jpg",
    ".jpeg",
    ".webp",
    ".gif",
    ".bmp",
    ".tif",
    ".tiff",
    ".avif",
    ".heic",
    ".heif",
    ".svg",
    ".mp4",
    ".mov",
    ".mkv",
    ".webm",
    ".avi",
    ".m4v",
    ".wav",
    ".mp3",
    ".m4a",
    ".aac",
    ".flac",
    ".ogg",
    ".opus",
    ".glb",
    ".gltf",
    ".obj",
    ".fbx",
    ".usdz",
    ".exr",
    ".hdr",
)

_JSON_MEDIA_METADATA_KEYS = frozenset(
    {"type", "format", "mime_type", "media_type", "role", "mode"}
)


def _path_exists_on_disk(val: str) -> bool:
    """Return True if val (or its ~-expanded form) resolves to an existing local path."""
    try:
        p = Path(val)
        return p.exists() or p.expanduser().exists()
    except OSError:
        return False


def _looks_like_local_path(raw: str) -> bool:
    """Return True when raw is an existing local path or looks like a local filesystem path."""
    val = raw.strip()
    if not val:
        return False
    low = val.lower()
    if low.startswith(("http://", "https://")):
        return False
    if low.startswith("file://"):
        return True
    if val.startswith(("/", "./", "../", "~/", "~\\")):
        return True
    if "/" in val or "\\" in val:
        return True
    if any(low.endswith(ext) for ext in MEDIA_FILE_EXTENSIONS):
        return True
    return _path_exists_on_disk(val)


def _collect_json_media_strings(obj: Any) -> list[str]:
    """Collect candidate media string values from a parsed JSON array or object."""
    out: list[str] = []
    if isinstance(obj, str):
        out.append(obj)
    elif isinstance(obj, list):
        for item in obj:
            out.extend(_collect_json_media_strings(item))
    elif isinstance(obj, dict):
        for key, val in obj.items():
            if isinstance(key, str) and key.strip().lower() in _JSON_MEDIA_METADATA_KEYS:
                continue
            out.extend(_collect_json_media_strings(val))
    return out


def _inspect_media_value(
    raw_flag: str, raw_val: str
) -> tuple[str | None, list[dict[str, str]]]:
    """Check one media flag value for local paths; return (cost_safe_val_or_None, local_hits)."""
    stripped = raw_val.strip()
    if not stripped:
        return raw_val, []

    low = stripped.lower()
    if not low.startswith(("http://", "https://")) and _path_exists_on_disk(stripped):
        return None, [{"flag": raw_flag, "value": stripped}]

    if stripped.startswith(("[", "{")):
        try:
            parsed = json.loads(stripped)
        except json.JSONDecodeError:
            parsed = None
        if isinstance(parsed, list):
            hits: list[dict[str, str]] = []
            kept: list[Any] = []
            for item in parsed:
                item_hits = [
                    s for s in _collect_json_media_strings(item) if _looks_like_local_path(s)
                ]
                if item_hits:
                    for s in item_hits:
                        hits.append({"flag": raw_flag, "value": s.strip()})
                else:
                    kept.append(item)
            if not hits:
                return raw_val, []
            return (json.dumps(kept, ensure_ascii=False) if kept else None), hits
        if isinstance(parsed, dict):
            dict_hits = [
                {"flag": raw_flag, "value": s.strip()}
                for s in _collect_json_media_strings(parsed)
                if _looks_like_local_path(s)
            ]
            if not dict_hits:
                return raw_val, []
            return None, dict_hits

    if "," in stripped:
        parts = [p.strip() for p in stripped.split(",") if p.strip()]
        hits = []
        kept_parts: list[str] = []
        for part in parts:
            if _looks_like_local_path(part):
                hits.append({"flag": raw_flag, "value": part})
            else:
                kept_parts.append(part)
        if not hits:
            return raw_val, []
        return (",".join(kept_parts) if kept_parts else None), hits

    if _looks_like_local_path(stripped):
        return None, [{"flag": raw_flag, "value": stripped}]
    return raw_val, []


def _inspect_and_strip_local_media_paths(
    extra_args: list[str],
) -> tuple[list[str], list[dict[str, str]]]:
    """Inspect media-accepting flags for local file paths and return (cost_safe_args, hits)."""
    sanitized: list[str] = []
    hits: list[dict[str, str]] = []
    idx = 0
    total = len(extra_args)

    while idx < total:
        tok = extra_args[idx]
        if not tok.startswith("--") or tok == "--":
            sanitized.append(tok)
            idx += 1
            continue

        if "=" in tok:
            raw_flag, raw_val = tok.split("=", 1)
            norm = raw_flag[2:].strip().lower().replace("-", "_")
            if norm in MEDIA_FLAG_NAMES:
                clean_val, val_hits = _inspect_media_value(raw_flag, raw_val)
                hits.extend(val_hits)
                if clean_val is not None:
                    sanitized.append(f"{raw_flag}={clean_val}")
            else:
                sanitized.append(tok)
            idx += 1
            continue

        norm = tok[2:].strip().lower().replace("-", "_")
        if norm in MEDIA_FLAG_NAMES:
            val_start = idx + 1
            val_end = val_start
            while val_end < total and not extra_args[val_end].startswith("--"):
                val_end += 1
            if val_end == val_start:
                sanitized.append(tok)
                idx += 1
                continue
            kept_vals: list[str] = []
            for raw_val in extra_args[val_start:val_end]:
                clean_val, val_hits = _inspect_media_value(tok, raw_val)
                hits.extend(val_hits)
                if clean_val is not None:
                    kept_vals.append(clean_val)
            if kept_vals:
                sanitized.append(tok)
                sanitized.extend(kept_vals)
            idx = val_end
            continue

        sanitized.append(tok)
        if idx + 1 < total and not extra_args[idx + 1].startswith("--"):
            sanitized.append(extra_args[idx + 1])
            idx += 2
        else:
            idx += 1

    return sanitized, hits


def _extract_present_flag_names(extra_args: list[str]) -> set[str]:
    """Return normalized CLI flag names explicitly supplied with a non-empty value."""
    present: set[str] = set()
    idx = 0
    total = len(extra_args)
    while idx < total:
        tok = extra_args[idx]
        if not tok.startswith("--") or tok == "--":
            idx += 1
            continue
        if "=" in tok:
            raw_name, raw_val = tok[2:].split("=", 1)
            norm = raw_name.strip().lower().replace("-", "_")
            if norm and raw_val.strip():
                present.add(norm)
            idx += 1
            continue
        norm = tok[2:].strip().lower().replace("-", "_")
        if idx + 1 < total and not extra_args[idx + 1].startswith("--"):
            if norm and extra_args[idx + 1].strip():
                present.add(norm)
            idx += 2
        else:
            idx += 1
    return present


def _check_hidden_default_warnings(model: str, extra_args: list[str]) -> list[str]:
    """Return non-blocking warnings for verified live Higgsfield CLI hidden expensive defaults."""
    m = (model or "").strip().lower()
    if not m:
        return []
    present = _extract_present_flag_names(extra_args)
    out: list[str] = []

    if m in ("kling4_0", "kling_4_0_flash") and "duration" not in present:
        out.append(
            f"{m}: --duration omitted; CLI defaults to 10s (doubling 5s credit cost) — "
            "pass --duration 5 explicitly unless a 10s clip is intended"
        )

    if m in ("cinematic_studio_video_3_5", "marketing_studio_video") and "duration" not in present:
        out.append(
            f"{m}: --duration omitted; CLI defaults to 15s (3x 5s duration) — "
            "pass --duration 5 explicitly unless a 15s clip is intended"
        )

    if (
        m in ("cinematic_studio_video_3_5", "cinematic_studio_3_0")
        and "prompt_language" not in present
    ):
        out.append(
            f"{m}: --prompt_language omitted; CLI defaults to 'zh' — "
            "pass --prompt_language en explicitly for English prompts"
        )

    if m == "hf_mult_motion_control":
        out.append(
            "hf_mult_motion_control: full non-flash model costs up to 100 cr. (1080p/5s); "
            "consider 10x cheaper hf_mult_motion_control_flash (Lite, 10 cr. at 1080p) first"
        )
    elif m == "hf_mult_replace_object":
        out.append(
            "hf_mult_replace_object: full non-flash model costs up to 120 cr. (1080p/5s); "
            "consider 10x cheaper hf_mult_replace_object_flash (Lite, 12 cr. at 1080p) first"
        )

    return out


def _parse_positive_ascii_int(raw: str) -> int | None:
    """Parse a positive ASCII integer (accepting Go pflag `+N`, rejecting `0`, `-N`, Unicode digits)."""
    s = raw.strip()
    if not s or not s.isascii():
        return None
    if s[0] == "+":
        digits = s[1:]
    elif s[0] == "-":
        return None
    else:
        digits = s
    if not digits or not digits.isdigit():
        return None
    val = int(digits)
    return val if val >= 1 else None


def _matches_flag_eq(tok: str, flags: frozenset[str]) -> tuple[str | None, str]:
    for flag in flags:
        prefix = f"{flag}="
        if tok.startswith(prefix):
            return flag, tok[len(prefix) :]
    return None, ""


def _sanitize_fallback_cost_args(
    hf_command: str, extra_args: list[str]
) -> tuple[list[str], int, dict[str, Any] | None]:
    """Strip command-specific flags unsupported by `generate cost <model>` fallback."""
    if hf_command != "product-photoshoot":
        return list(extra_args), 1, None

    filtered: list[str] = []
    multiplier = 1
    idx = 0
    total = len(extra_args)
    while idx < total:
        tok = extra_args[idx]
        if tok == "--" or tok in GLOBAL_CLI_BOOL_FLAGS or _matches_flag_eq(tok, GLOBAL_CLI_BOOL_FLAGS)[0]:
            idx += 1
            continue
        if tok in PRODUCT_PHOTOSHOOT_BOOL_FLAGS or _matches_flag_eq(tok, PRODUCT_PHOTOSHOOT_BOOL_FLAGS)[0]:
            idx += 1
            continue
        if tok in PRODUCT_PHOTOSHOOT_VALUE_FLAGS:
            if idx + 1 >= total:
                if tok == "--count":
                    return [], 1, {
                        "ok": False,
                        "error_code": "invalid_count",
                        "message": "--count requires a positive integer >= 1",
                    }
                idx += 1
                continue
            val = extra_args[idx + 1]
            if tok == "--count":
                parsed_count = _parse_positive_ascii_int(val)
                if parsed_count is None:
                    return [], 1, {
                        "ok": False,
                        "error_code": "invalid_count",
                        "count": val,
                        "message": f"--count must be a positive ASCII integer >= 1, got {val!r}",
                    }
                multiplier = parsed_count
            idx += 2
            continue
        eq_flag, eq_val = _matches_flag_eq(tok, PRODUCT_PHOTOSHOOT_VALUE_FLAGS)
        if eq_flag is not None:
            if eq_flag == "--count":
                parsed_count = _parse_positive_ascii_int(eq_val)
                if parsed_count is None:
                    return [], 1, {
                        "ok": False,
                        "error_code": "invalid_count",
                        "count": eq_val,
                        "message": f"--count must be a positive ASCII integer >= 1, got {eq_val!r}",
                    }
                multiplier = parsed_count
            idx += 1
            continue
        filtered.append(tok)
        if tok.startswith("--") and "=" not in tok and idx + 1 < total:
            filtered.append(extra_args[idx + 1])
            idx += 2
        else:
            idx += 1
    return filtered, multiplier, None


def _filter_workflow_cost_args(
    extra_args: list[str], workflow_schema: dict[str, Any]
) -> list[str] | None:
    """Filter CLI args down to `cost_params` declared by `higgsfield workflow get --json`."""
    cost_params = workflow_schema.get("cost_params")
    if not isinstance(cost_params, list):
        return None
    allowed_names = {
        str(p["name"]).strip().replace("-", "_")
        for p in cost_params
        if isinstance(p, dict) and isinstance(p.get("name"), str) and p["name"].strip()
    }
    bool_names = {"json", "no_color"} | {
        str(p["name"]).strip().replace("-", "_")
        for p in (*(workflow_schema.get("params") or []), *cost_params)
        if isinstance(p, dict)
        and isinstance(p.get("name"), str)
        and str(p.get("type") or "").startswith("boolean")
    }
    filtered: list[str] = []
    idx = 0
    total = len(extra_args)
    while idx < total:
        tok = extra_args[idx]
        if (
            not tok.startswith("--")
            or tok == "--"
            or tok in GLOBAL_CLI_BOOL_FLAGS
            or _matches_flag_eq(tok, GLOBAL_CLI_BOOL_FLAGS)[0]
        ):
            idx += 1
            continue
        if "=" in tok:
            name = tok[2:].split("=", 1)[0].replace("-", "_")
            if name in allowed_names:
                filtered.append(tok)
            idx += 1
            continue
        name = tok[2:].replace("-", "_")
        has_value = idx + 1 < total and (
            name not in bool_names
            or extra_args[idx + 1].lower() in ("true", "false", "1", "0")
        )
        if name in allowed_names:
            filtered.append(tok)
            if has_value:
                filtered.append(extra_args[idx + 1])
        idx += 2 if has_value else 1
    return filtered


def _filter_workflow_exec_args(
    cli_args: list[str], workflow_schema: dict[str, Any]
) -> list[str]:
    """Strip cost-only workflow params (in cost_params but absent from params) before execution."""
    cost_params = workflow_schema.get("cost_params")
    exec_params = workflow_schema.get("params")
    if not isinstance(cost_params, list) or not isinstance(exec_params, list):
        return list(cli_args)
    exec_names = {
        str(p["name"]).strip().replace("-", "_")
        for p in exec_params
        if isinstance(p, dict) and isinstance(p.get("name"), str) and p["name"].strip()
    }
    cost_only_names = {
        str(p["name"]).strip().replace("-", "_")
        for p in cost_params
        if isinstance(p, dict) and isinstance(p.get("name"), str) and p["name"].strip()
    } - exec_names
    if not cost_only_names:
        return list(cli_args)
    bool_names = {"json", "no_color"} | {
        str(p["name"]).strip().replace("-", "_")
        for p in (*exec_params, *cost_params)
        if isinstance(p, dict)
        and isinstance(p.get("name"), str)
        and str(p.get("type") or "").startswith("boolean")
    }
    filtered: list[str] = []
    idx = 0
    total = len(cli_args)
    while idx < total:
        tok = cli_args[idx]
        if not tok.startswith("--") or tok == "--":
            filtered.append(tok)
            idx += 1
            continue
        if "=" in tok:
            name = tok[2:].split("=", 1)[0].replace("-", "_")
            if name not in cost_only_names:
                filtered.append(tok)
            idx += 1
            continue
        name = tok[2:].replace("-", "_")
        has_value = idx + 1 < total and (
            name not in bool_names
            or cli_args[idx + 1].lower() in ("true", "false", "1", "0")
        )
        if name not in cost_only_names:
            filtered.append(tok)
            if has_value:
                filtered.append(cli_args[idx + 1])
        idx += 2 if has_value else 1
    return filtered


def _build_cost_cmd(
    hf_bin: str,
    hf_command: str,
    model: str,
    is_workflow: bool,
    extra_args: list[str],
) -> list[str]:
    if hf_command == "generate":
        cmd = [hf_bin, "generate", "cost"]
        if is_workflow:
            cmd.append("workflow")
        cmd.extend([model, *extra_args, "--json"])
        return cmd
    return [hf_bin, hf_command, "cost", *extra_args, "--json"]


def _build_exec_cmd(
    hf_bin: str,
    hf_command: str,
    model: str,
    is_workflow: bool,
    cli_args: list[str],
    wait_timeout: str,
) -> list[str]:
    if hf_command == "generate":
        subcmd = "workflow" if is_workflow else "create"
        return [
            hf_bin,
            "generate",
            subcmd,
            model,
            *cli_args,
            "--wait",
            "--wait-timeout",
            wait_timeout,
            "--json",
        ]
    if hf_command == "product-photoshoot":
        has_timeout = any(
            arg == "--timeout" or arg.startswith("--timeout=") for arg in cli_args
        )
        timeout_args = [] if has_timeout else ["--timeout", wait_timeout]
        return [hf_bin, hf_command, "create", *cli_args, *timeout_args, "--json"]
    return [hf_bin, hf_command, "create", *cli_args, "--json"]


def _build_get_cmd(hf_bin: str, hf_command: str, job_id: str) -> list[str]:
    if hf_command == "soul-id":
        return [hf_bin, "soul-id", "get", job_id, "--json"]
    return [hf_bin, "generate", "get", job_id, "--json"]


def _build_wait_cmd(
    hf_bin: str, hf_command: str, job_id: str, wait_timeout: str
) -> list[str]:
    if hf_command == "soul-id":
        return [hf_bin, "soul-id", "wait", job_id, "--json"]
    return [
        hf_bin,
        "generate",
        "wait",
        job_id,
        "--wait-timeout",
        wait_timeout,
        "--json",
    ]


def _do_preflight(
    *,
    campaign_dir: Path,
    shot: str,
    kind: str,
    round_name: str,
    round_cap: float,
    variant: str,
    cli_version: int | None,
    model: str,
    is_workflow: bool,
    hf_command: str,
    hf_bin: str,
    extra_args: list[str],
    records: list[dict[str, Any]] | None = None,
    resolved_version: int | None = None,
    block_local_paths: bool = True,
) -> tuple[int, dict[str, Any]]:
    rcap_err = _validate_round_cap(round_cap)
    if rcap_err is not None:
        return 2, rcap_err

    clean_variant, var_err = _validate_variant_arg(kind, variant)
    if var_err is not None:
        return 2, var_err

    envelope, env_err = _load_envelope_or_error(campaign_dir)
    if env_err is not None or envelope is None:
        return 2, env_err or {"ok": False, "error_code": "brief_not_active"}

    if resolved_version is None:
        version, sl_err = _inspect_shotlist_guard(
            campaign_dir, shot, kind, round_name, cli_version
        )
        if sl_err is not None or version is None:
            return 2, sl_err or {"ok": False, "error_code": "asset_locked"}
    else:
        version = resolved_version

    if records is None:
        try:
            records = _read_receipts_raw(campaign_dir)
        except CorruptReceiptsError as exc:
            return 2, {
                "ok": False,
                "error_code": "corrupt_receipts",
                "message": str(exc),
            }

    (
        total_spent,
        spent_by_round,
        attempts_map,
        lb_variants_seen,
        _,
    ) = _summarize_receipts(records)
    round_spent = spent_by_round.get(round_name, 0.0)
    campaign_cap = int(envelope["campaign_cap"])
    max_retries = int(envelope["max_retries"])
    lookbook_variants_cap = int(envelope["lookbook_variants"])
    max_attempts = 1 + max_retries

    # Enforce Lookbook variant count limit
    if kind == "lookbook" and clean_variant:
        seen_for_entity = set(lb_variants_seen.get((shot, round_name, version), set()))
        projected_variants = seen_for_entity | {clean_variant}
        if len(projected_variants) > lookbook_variants_cap:
            return 2, {
                "ok": False,
                "error_code": "variant_limit_exceeded",
                "campaign": str(campaign_dir),
                "shot": shot,
                "kind": kind,
                "round": round_name,
                "variant": clean_variant,
                "version": version,
                "variants_seen": sorted(seen_for_entity),
                "lookbook_variants": lookbook_variants_cap,
                "message": (
                    f"lookbook '{shot}' ({round_name}/v{version}) variant '{clean_variant}' "
                    f"exceeds brief.md Lookbook variants limit ({lookbook_variants_cap}; "
                    f"already seen: {sorted(seen_for_entity)})"
                ),
            }

    attempts_used = attempts_map.get((shot, kind, round_name, clean_variant, version), 0)
    if attempts_used >= max_attempts:
        return 2, {
            "ok": False,
            "error_code": "retry_limit_exceeded",
            "campaign": str(campaign_dir),
            "shot": shot,
            "kind": kind,
            "round": round_name,
            "variant": clean_variant or None,
            "version": version,
            "attempts_used": attempts_used,
            "max_attempts": max_attempts,
            "max_retries": max_retries,
            "message": (
                f"asset '{shot}' ({kind}/{round_name}"
                f"{'/' + clean_variant if clean_variant else ''}/v{version}) "
                f"has already used {attempts_used}/{max_attempts} allowed attempts "
                f"(max_retries={max_retries})"
            ),
        }

    warnings: list[str] = []
    warnings.extend(_check_hidden_default_warnings(model, extra_args))

    # Block or sanitize local file paths BEFORE calling remote CLI cost estimation
    # (live `higgsfield generate cost` silently uploads local paths to remote servers).
    cost_extra_args, local_path_hits = _inspect_and_strip_local_media_paths(extra_args)
    if local_path_hits:
        offending_flags: list[str] = []
        for hit in local_path_hits:
            if hit["flag"] not in offending_flags:
                offending_flags.append(hit["flag"])
        if block_local_paths:
            return 2, {
                "ok": False,
                "error_code": "local_path_in_cost_quote",
                "campaign": str(campaign_dir),
                "shot": shot,
                "kind": kind,
                "round": round_name,
                "model": model,
                "offending_flags": offending_flags,
                "offending_values": local_path_hits,
                "message": (
                    f"Refusing cost quote with local file path(s) in "
                    f"{', '.join(offending_flags)}: `higgsfield generate cost` silently "
                    "uploads local paths to remote servers. Upload approved media explicitly "
                    "via `hf_guard.py upload` and pass uploaded UUIDs (or quote with "
                    "cost-only flags without local file paths)."
                ),
            }
        warnings.append(
            f"stripped local file path(s) from cost quote ({', '.join(offending_flags)}) "
            "to prevent silent pre-execution upload; prefer `hf_guard.py upload` and pass "
            "uploaded UUIDs"
        )

    # Validate command-specific cost flags fail-closed before calling remote CLI
    fb_args: list[str] = []
    fb_mult = 1
    if hf_command == "product-photoshoot":
        fb_args, fb_mult, count_err = _sanitize_fallback_cost_args(hf_command, cost_extra_args)
        if count_err is not None:
            return 2, count_err

    # Account status (non-fatal warning if unavailable)
    account_balance: float | None = None
    acc_rc, _, acc_err, acc_json = _run_cli([hf_bin, "account", "status", "--json"])
    if acc_rc == 0 and isinstance(acc_json, dict):
        account_balance = _extract_numeric_field(
            acc_json, ("balance", "credits", "available_credits", "remaining_credits")
        )
    else:
        detail = acc_err.strip() or f"exit code {acc_rc}"
        warnings.append(f"account status unavailable: {detail}")

    # Cost estimation (mandatory)
    cost_multiplier = 1
    if hf_command == "generate" and is_workflow and cost_extra_args:
        wf_cost_args: list[str] = cost_extra_args
        wf_rc, _, _, wf_json = _run_cli([hf_bin, "workflow", "get", model, "--json"])
        if wf_rc == 0 and isinstance(wf_json, dict):
            filtered_wf = _filter_workflow_cost_args(cost_extra_args, wf_json)
            if filtered_wf is not None:
                wf_cost_args = filtered_wf
        cost_cmd = _build_cost_cmd(hf_bin, "generate", model, True, wf_cost_args)
        cost_rc, cost_out, cost_err, cost_json = _run_cli(cost_cmd)
    else:
        cost_cmd = _build_cost_cmd(hf_bin, hf_command, model, is_workflow, cost_extra_args)
        cost_rc, cost_out, cost_err, cost_json = _run_cli(cost_cmd)
        if (
            cost_rc not in (0, 127)
            and hf_command != "generate"
            and model
            and model != hf_command
        ):
            if hf_command != "product-photoshoot":
                fb_args, fb_mult, _ = _sanitize_fallback_cost_args(hf_command, cost_extra_args)
            fallback_cmd = _build_cost_cmd(hf_bin, "generate", model, False, fb_args)
            fb_rc, fb_out, fb_err, fb_json = _run_cli(fallback_cmd)
            if fb_rc != 127:
                cost_cmd, cost_rc, cost_out, cost_err, cost_json = (
                    fallback_cmd,
                    fb_rc,
                    fb_out,
                    fb_err,
                    fb_json,
                )
                cost_multiplier = fb_mult
    if cost_rc == 127:
        return 1, {
            "ok": False,
            "error_code": "cli_not_found",
            "message": cost_err.strip(),
        }
    if cost_rc != 0:
        return 1, {
            "ok": False,
            "error_code": "cost_estimation_failed",
            "command": cost_cmd,
            "exit_code": cost_rc,
            "stderr": cost_err.strip(),
            "stdout": cost_out.strip(),
            "message": f"higgsfield cost estimation failed (exit {cost_rc})",
        }

    estimated_credits = _extract_numeric_field(
        cost_json, ("estimated_credits", "credits", "cost", "total_credits", "price")
    )
    if (
        estimated_credits is None
        or not math.isfinite(estimated_credits)
        or estimated_credits < 0
    ):
        return 1, {
            "ok": False,
            "error_code": "cost_parse_failed",
            "command": cost_cmd,
            "raw_output": cost_out.strip(),
            "message": "could not parse finite non-negative credit estimate from higgsfield cost output",
        }
    estimated_credits *= cost_multiplier

    if account_balance is not None and account_balance < estimated_credits:
        warnings.append(
            f"account balance ({_clean_num(account_balance)} credits) is lower than "
            f"estimated cost ({_clean_num(estimated_credits)} credits)"
        )

    projected_campaign = total_spent + estimated_credits
    remaining_campaign_after = campaign_cap - projected_campaign

    if projected_campaign > campaign_cap:
        return 2, {
            "ok": False,
            "error_code": "campaign_budget_exceeded",
            "campaign": str(campaign_dir),
            "shot": shot,
            "kind": kind,
            "round": round_name,
            "variant": clean_variant or None,
            "version": version,
            "model": model,
            "estimated_credits": _clean_num(estimated_credits),
            "total_spent": _clean_num(total_spent),
            "campaign_cap": campaign_cap,
            "remaining_campaign_before": _clean_num(campaign_cap - total_spent),
            "remaining_campaign_after": _clean_num(remaining_campaign_after),
            "round_spent": _clean_num(round_spent),
            "round_cap": _clean_num(round_cap),
            "attempts_used": attempts_used,
            "max_attempts": max_attempts,
            "account_balance": _clean_num(account_balance) if account_balance is not None else None,
            "warnings": warnings,
            "message": (
                f"Campaign budget cap exceeded: spent {_clean_num(total_spent)} + "
                f"estimated {_clean_num(estimated_credits)} > campaign cap {campaign_cap} credits"
            ),
        }

    projected_round = round_spent + estimated_credits
    remaining_round_after = round_cap - projected_round
    if projected_round > round_cap:
        return 2, {
            "ok": False,
            "error_code": "round_budget_exceeded",
            "campaign": str(campaign_dir),
            "shot": shot,
            "kind": kind,
            "round": round_name,
            "variant": clean_variant or None,
            "version": version,
            "model": model,
            "estimated_credits": _clean_num(estimated_credits),
            "total_spent": _clean_num(total_spent),
            "campaign_cap": campaign_cap,
            "remaining_campaign": _clean_num(campaign_cap - total_spent),
            "round_spent": _clean_num(round_spent),
            "round_cap": _clean_num(round_cap),
            "remaining_round_before": _clean_num(round_cap - round_spent),
            "remaining_round_after": _clean_num(remaining_round_after),
            "attempts_used": attempts_used,
            "max_attempts": max_attempts,
            "account_balance": _clean_num(account_balance) if account_balance is not None else None,
            "warnings": warnings,
            "message": (
                f"{round_name} round budget cap exceeded: round spent "
                f"{_clean_num(round_spent)} + estimated {_clean_num(estimated_credits)} "
                f"> round cap {_clean_num(round_cap)} credits"
            ),
        }

    return 0, {
        "ok": True,
        "campaign": str(campaign_dir),
        "shot": shot,
        "kind": kind,
        "round": round_name,
        "variant": clean_variant or None,
        "version": version,
        "command": hf_command,
        "model": model,
        "is_workflow": is_workflow,
        "estimated_credits": _clean_num(estimated_credits),
        "total_spent": _clean_num(total_spent),
        "campaign_cap": campaign_cap,
        "remaining_campaign_after": _clean_num(remaining_campaign_after),
        "round_spent": _clean_num(round_spent),
        "round_cap": _clean_num(round_cap),
        "remaining_round_after": _clean_num(remaining_round_after),
        "attempts_used": attempts_used,
        "max_attempts": max_attempts,
        "account_balance": _clean_num(account_balance) if account_balance is not None else None,
        "warnings": warnings,
    }


def _extract_job_list(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        for key in ("jobs", "items", "data", "generations", "results"):
            val = payload.get(key)
            if isinstance(val, list):
                return [item for item in val if isinstance(item, dict)]
    return []


def _find_download_failed_receipt(
    records: list[dict[str, Any]],
    params_hash: str,
) -> dict[str, Any] | None:
    collapsed = _collapse_receipts(records)
    for rec in reversed(collapsed):
        if (
            rec.get("params_hash") == params_hash
            and str(rec.get("status") or "").lower() == "download_failed"
            and isinstance(rec.get("url"), str)
            and rec["url"].strip()
        ):
            return rec
    return None


def _recover_job_id_from_list(
    *,
    hf_bin: str,
    model: str,
    params_hash: str,
    known_job_ids: set[str],
) -> tuple[str | None, str | None]:
    """Query `generate list --json` once after an ambiguous timeout to reclaim a remote job_id."""
    list_rc, _, list_err, list_json = _run_cli([hf_bin, "generate", "list", "--json"])
    if list_rc != 0 or list_json is None:
        detail = list_err.strip() or f"exit code {list_rc}"
        return None, f"generate list recovery unavailable after ambiguous failure: {detail}"

    remote_jobs = _extract_job_list(list_json)
    # 1. Exact params_hash match
    for job in remote_jobs:
        rstatus = str(job.get("status") or "").lower()
        if rstatus in IN_FLIGHT_STATUSES or rstatus in COMPLETED_STATUSES:
            meta_hash = _extract_string_field(job, ("params_hash",))
            if not meta_hash and isinstance(job.get("metadata"), dict):
                meta_hash = _extract_string_field(job["metadata"], ("params_hash",))
            if meta_hash == params_hash:
                jid = _extract_string_field(
                    job, ("job_id", "id", "request_set_id", "request_id")
                )
                if jid:
                    return jid, None

    # 2. Match recent unseen job by model (prefer in-flight over completed)
    completed_fallback: str | None = None
    for job in remote_jobs:
        jid = _extract_string_field(job, ("job_id", "id", "request_set_id", "request_id"))
        if not jid or jid in known_job_ids:
            continue
        job_model = _extract_string_field(
            job, ("model", "model_id", "workflow", "workflow_id", "job_set_type")
        )
        if job_model != model:
            continue
        rstatus = str(job.get("status") or "").lower()
        if rstatus in IN_FLIGHT_STATUSES:
            return jid, None
        if rstatus in COMPLETED_STATUSES and completed_fallback is None:
            completed_fallback = jid
    return completed_fallback, None


def _find_in_flight_job(
    records: list[dict[str, Any]],
    params_hash: str,
    hf_bin: str,
    hf_command: str,
) -> dict[str, Any]:
    """Inspect collapsed receipts, `generate list`, and `<cmd> get` for in-flight work."""
    warnings: list[str] = []
    collapsed = _collapse_receipts(records)

    unresolved_receipt: dict[str, Any] | None = None
    for rec in reversed(collapsed):
        rec_status = str(rec.get("status") or "").lower()
        if rec.get("params_hash") == params_hash and rec_status in IN_FLIGHT_STATUSES:
            unresolved_receipt = rec
            break

    remote_jobs: list[dict[str, Any]] = []
    list_ok = False
    if hf_command in ("generate", "product-photoshoot"):
        list_rc, _, list_err, list_json = _run_cli([hf_bin, "generate", "list", "--json"])
        list_ok = list_rc == 0 and list_json is not None
        if list_ok:
            remote_jobs = _extract_job_list(list_json)
        else:
            detail = list_err.strip() or f"exit code {list_rc}"
            warnings.append(f"generate list unavailable during duplicate check: {detail}")

    remote_by_id: dict[str, dict[str, Any]] = {}
    for job in remote_jobs:
        jid = _extract_string_field(job, ("job_id", "id", "request_set_id", "request_id"))
        if jid:
            remote_by_id[jid] = job

    if unresolved_receipt is not None:
        rec_jid = str(unresolved_receipt.get("job_id") or "").strip()
        rec_rid = str(unresolved_receipt.get("reservation_id") or "").strip() or None
        rec_attempt = unresolved_receipt.get("attempt")
        attempt_int = int(rec_attempt) if isinstance(rec_attempt, int) else None
        est_raw = unresolved_receipt.get("estimated_credits")
        est_val = (
            float(est_raw)
            if _is_number(est_raw)
            else (
                float(unresolved_receipt["credits"])
                if _is_number(unresolved_receipt.get("credits"))
                else None
            )
        )

        if rec_jid:
            remote_job = remote_by_id.get(rec_jid)
            if remote_job is not None:
                rstatus = str(remote_job.get("status") or "").lower()
                if rstatus not in FAILED_STATUSES:
                    return {
                        "action": "wait",
                        "job_id": rec_jid,
                        "reservation_id": rec_rid,
                        "attempt": attempt_int,
                        "estimated_credits": est_val,
                        "get_payload": None,
                        "warnings": warnings,
                    }
            else:
                get_cmd = _build_get_cmd(hf_bin, hf_command, rec_jid)
                get_rc, _, get_err, get_json = _run_cli(get_cmd)
                if get_rc == 0 and isinstance(get_json, (dict, list)):
                    gstatus = str(
                        _extract_string_field(get_json, ("status", "state")) or ""
                    ).lower()
                    if gstatus in COMPLETED_STATUSES:
                        g_url = _extract_string_field(
                            get_json,
                            (
                                "result_url",
                                "url",
                                "output_url",
                                "media_url",
                                "video_url",
                                "image_url",
                                "audio_url",
                                "min_result_url",
                                "local_path",
                                "path",
                            ),
                        )
                        if g_url:
                            return {
                                "action": "use_get_result",
                                "job_id": rec_jid,
                                "reservation_id": rec_rid,
                                "attempt": attempt_int,
                                "estimated_credits": est_val,
                                "get_payload": get_json,
                                "warnings": warnings,
                            }
                        return {
                            "action": "wait",
                            "job_id": rec_jid,
                            "reservation_id": rec_rid,
                            "attempt": attempt_int,
                            "estimated_credits": est_val,
                            "get_payload": None,
                            "warnings": warnings,
                        }
                    if gstatus not in FAILED_STATUSES:
                        return {
                            "action": "wait",
                            "job_id": rec_jid,
                            "reservation_id": rec_rid,
                            "attempt": attempt_int,
                            "estimated_credits": est_val,
                            "get_payload": None,
                            "warnings": warnings,
                        }
                elif not list_ok:
                    detail = get_err.strip() or f"exit code {get_rc}"
                    warnings.append(
                        f"job get fallback unavailable ({detail}); waiting on {rec_jid}"
                    )
                    return {
                        "action": "wait",
                        "job_id": rec_jid,
                        "reservation_id": rec_rid,
                        "attempt": attempt_int,
                        "estimated_credits": est_val,
                        "get_payload": None,
                        "warnings": warnings,
                    }
                else:
                    detail = get_err.strip() or f"exit code {get_rc}"
                    warnings.append(
                        f"job '{rec_jid}' absent from list and job get failed ({detail}); "
                        "attempting wait before refusing"
                    )
                    return {
                        "action": "wait",
                        "job_id": rec_jid,
                        "reservation_id": rec_rid,
                        "attempt": attempt_int,
                        "estimated_credits": est_val,
                        "get_payload": None,
                        "warnings": warnings,
                    }
        else:
            for job in remote_jobs:
                rstatus = str(job.get("status") or "").lower()
                if rstatus in IN_FLIGHT_STATUSES or rstatus in COMPLETED_STATUSES:
                    meta_hash = _extract_string_field(job, ("params_hash",))
                    if not meta_hash and isinstance(job.get("metadata"), dict):
                        meta_hash = _extract_string_field(job["metadata"], ("params_hash",))
                    if meta_hash == params_hash:
                        jid = _extract_string_field(
                            job, ("job_id", "id", "request_set_id", "request_id")
                        )
                        if jid:
                            return {
                                "action": "wait",
                                "job_id": jid,
                                "reservation_id": rec_rid,
                                "attempt": attempt_int,
                                "estimated_credits": est_val,
                                "get_payload": None,
                                "warnings": warnings,
                            }
            return {
                "action": "blocked_reservation",
                "job_id": None,
                "reservation_id": rec_rid,
                "attempt": attempt_int,
                "estimated_credits": est_val,
                "get_payload": None,
                "warnings": warnings,
            }

    for job in remote_jobs:
        rstatus = str(job.get("status") or "").lower()
        if rstatus in IN_FLIGHT_STATUSES:
            meta_hash = _extract_string_field(job, ("params_hash",))
            if not meta_hash and isinstance(job.get("metadata"), dict):
                meta_hash = _extract_string_field(job["metadata"], ("params_hash",))
            if meta_hash == params_hash:
                jid = _extract_string_field(
                    job, ("job_id", "id", "request_set_id", "request_id")
                )
                if jid:
                    return {
                        "action": "wait",
                        "job_id": jid,
                        "reservation_id": None,
                        "attempt": None,
                        "estimated_credits": None,
                        "get_payload": None,
                        "warnings": warnings,
                    }

    return {
        "action": "none",
        "job_id": None,
        "reservation_id": None,
        "attempt": None,
        "estimated_credits": None,
        "get_payload": None,
        "warnings": warnings,
    }


def _normalize_job_status(raw_status: str | None, exit_code: int) -> str:
    if raw_status:
        low = raw_status.strip().lower()
        if low in COMPLETED_STATUSES:
            return "completed"
        if low in IN_FLIGHT_STATUSES:
            return "in_progress"
        if low in FAILED_STATUSES:
            return low
        return low
    return "completed" if exit_code == 0 else "failed"


def _download_or_copy(url_or_path: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    parsed = urllib.parse.urlparse(url_or_path)
    if parsed.scheme in ("http", "https"):
        req = urllib.request.Request(
            url_or_path,
            headers={"User-Agent": "higgsfield-video-harness/1.0"},
        )
        with urllib.request.urlopen(req, timeout=120) as resp, dest.open("wb") as out_fh:
            shutil.copyfileobj(resp, out_fh)
    elif parsed.scheme == "file":
        src = Path(urllib.request.url2pathname(parsed.path))
        shutil.copyfile(src, dest)
    else:
        src = Path(url_or_path)
        if not src.is_file():
            raise FileNotFoundError(f"media source not found: {url_or_path}")
        shutil.copyfile(src, dest)


def _append_prompt_file(
    prompt_file: str | None, extra_args: list[str]
) -> tuple[list[str] | None, dict[str, Any] | None]:
    cli_args = list(extra_args)
    if not prompt_file:
        return cli_args, None
    pf = Path(prompt_file)
    if not pf.is_file():
        return None, {
            "ok": False,
            "error_code": "prompt_file_not_found",
            "message": f"prompt file not found: {pf}",
        }
    prompt_text = pf.read_text(encoding="utf-8").strip()
    cli_args.extend(["--prompt", prompt_text])
    return cli_args, None


def _cmd_preflight(args: argparse.Namespace, extra_args: list[str]) -> int:
    campaign_dir = Path(args.campaign)
    hf_bin = _resolve_hf_bin(getattr(args, "higgsfield_bin", None))
    hf_command = args.hf_command
    model = args.model or (hf_command if hf_command != "generate" else None)
    if not model:
        print(
            json.dumps(
                {
                    "ok": False,
                    "error_code": "missing_model",
                    "message": "--model is required when --command is 'generate'",
                },
                indent=2,
            )
        )
        return 2

    cli_args, pf_err = _append_prompt_file(args.prompt_file, extra_args)
    if pf_err is not None or cli_args is None:
        print(json.dumps(pf_err, indent=2))
        return 2

    rc, payload = _do_preflight(
        campaign_dir=campaign_dir,
        shot=args.shot,
        kind=args.kind,
        round_name=args.round,
        round_cap=args.round_cap,
        variant=args.variant,
        cli_version=args.version,
        model=model,
        is_workflow=args.workflow,
        hf_command=hf_command,
        hf_bin=hf_bin,
        extra_args=cli_args,
    )
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return rc


def _cmd_upload(args: argparse.Namespace) -> int:
    campaign_dir = Path(args.campaign)
    file_path = Path(args.file)
    hf_bin = _resolve_hf_bin(getattr(args, "higgsfield_bin", None))

    if not campaign_dir.is_dir():
        print(
            json.dumps(
                {
                    "ok": False,
                    "error_code": "brief_not_active",
                    "message": f"campaign directory not found: {campaign_dir}",
                },
                indent=2,
            )
        )
        return 2

    _, env_err = _load_envelope_or_error(campaign_dir)
    if env_err is not None:
        print(json.dumps(env_err, indent=2, ensure_ascii=False))
        return 2

    if not file_path.is_file():
        print(
            json.dumps(
                {
                    "ok": False,
                    "error_code": "file_not_found",
                    "message": f"upload source file not found: {file_path}",
                },
                indent=2,
            )
        )
        return 2

    # Fail closed on corrupt receipts BEFORE uploading any private asset remotely
    with _receipts_lock(campaign_dir):
        try:
            _read_receipts_raw(campaign_dir)
        except CorruptReceiptsError as exc:
            print(
                json.dumps(
                    {
                        "ok": False,
                        "error_code": "corrupt_receipts",
                        "message": str(exc),
                    },
                    indent=2,
                )
            )
            return 2

    upload_cmd = [hf_bin, "upload", "create", str(file_path), "--json"]
    rc, out, err, parsed = _run_cli(upload_cmd)
    if rc == 127:
        print(
            json.dumps(
                {
                    "ok": False,
                    "error_code": "cli_not_found",
                    "message": err.strip(),
                },
                indent=2,
            )
        )
        return 1
    if rc != 0:
        print(
            json.dumps(
                {
                    "ok": False,
                    "error_code": "upload_failed",
                    "exit_code": rc,
                    "stderr": err.strip(),
                    "stdout": out.strip(),
                    "message": f"higgsfield upload create failed (exit {rc})",
                },
                indent=2,
                ensure_ascii=False,
            )
        )
        return 1

    upload_id = (
        _extract_string_field(parsed, ("upload_id", "id", "file_id", "asset_id"))
        if isinstance(parsed, dict)
        else None
    )
    if not upload_id:
        print(
            json.dumps(
                {
                    "ok": False,
                    "error_code": "upload_parse_failed",
                    "stdout": out.strip(),
                    "message": "upload succeeded but returned no upload_id",
                },
                indent=2,
                ensure_ascii=False,
            )
        )
        return 1

    media_url = (
        _extract_string_field(parsed, ("url", "file_url", "asset_url"))
        if isinstance(parsed, dict)
        else None
    )
    ref_id = args.ref_id or file_path.stem
    params_hash = hashlib.sha256(
        json.dumps(
            {"kind": "upload", "ref_id": ref_id, "file": str(file_path)},
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()

    receipt = {
        "ts": _utc_now_iso(),
        "reservation_id": f"upl-{uuid.uuid4().hex[:12]}",
        "shot": ref_id,
        "ref_id": ref_id,
        "kind": "upload",
        "round": args.round,
        "round_cap": None,
        "variant": None,
        "version": 1,
        "model": "upload",
        "is_workflow": False,
        "params_hash": params_hash,
        "job_id": upload_id,
        "upload_id": upload_id,
        "file": str(file_path),
        "status": "completed",
        "estimated_credits": 0.0,
        "actual_credits": 0.0,
        "credits": 0.0,
        "url": media_url,
        "out": None,
        "attempt": 0,
    }

    with _receipts_lock(campaign_dir):
        try:
            _read_receipts_raw(campaign_dir)
        except CorruptReceiptsError as exc:
            print(
                json.dumps(
                    {
                        "ok": False,
                        "error_code": "corrupt_receipts",
                        "message": str(exc),
                    },
                    indent=2,
                )
            )
            return 2
        _append_receipt(campaign_dir, receipt)

    print(
        json.dumps(
            {
                "ok": True,
                "upload_id": upload_id,
                "ref_id": ref_id,
                "round": args.round,
                "file": str(file_path),
                "url": media_url,
                "credits": 0,
                "receipt": receipt,
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    return 0


def _cmd_log_web(args: argparse.Namespace) -> int:
    """Record a 0-credit Web Unlimited generation trace in receipts.jsonl under flock."""
    campaign_dir = Path(args.campaign)
    if not campaign_dir.is_dir():
        print(
            json.dumps(
                {
                    "ok": False,
                    "error_code": "brief_not_active",
                    "message": f"campaign directory not found: {campaign_dir}",
                },
                indent=2,
            )
        )
        return 2

    _, env_err = _load_envelope_or_error(campaign_dir)
    if env_err is not None:
        print(json.dumps(env_err, indent=2, ensure_ascii=False))
        return 2

    clean_variant, var_err = _validate_variant_arg(args.kind, args.variant)
    if var_err is not None:
        print(json.dumps(var_err, indent=2, ensure_ascii=False))
        return 2

    version, sl_err = _inspect_shotlist_guard(
        campaign_dir, args.shot, args.kind, args.round, args.version
    )
    if sl_err is not None or version is None:
        print(json.dumps(sl_err, indent=2, ensure_ascii=False))
        return 2

    model = (args.model or "").strip()
    if not model:
        print(
            json.dumps(
                {
                    "ok": False,
                    "error_code": "missing_model",
                    "message": "--model must be a non-empty string",
                },
                indent=2,
            )
        )
        return 2

    refs = [r.strip() for r in (args.refs or []) if isinstance(r, str) and r.strip()]
    params_hash = hashlib.sha256(
        json.dumps(
            {
                "channel": "web_unlimited",
                "shot": args.shot,
                "kind": args.kind,
                "round": args.round,
                "variant": clean_variant or None,
                "version": version,
                "model": model,
                "prompt_file": args.prompt_file,
                "refs": refs,
                "out": args.out,
            },
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()

    with _receipts_lock(campaign_dir):
        try:
            records = _read_receipts_raw(campaign_dir)
        except CorruptReceiptsError as exc:
            print(
                json.dumps(
                    {
                        "ok": False,
                        "error_code": "corrupt_receipts",
                        "message": str(exc),
                    },
                    indent=2,
                )
            )
            return 2

        prior_web = sum(
            1
            for r in records
            if str(r.get("channel") or "").lower() == "web_unlimited"
            and str(r.get("shot") or "") == args.shot
            and str(r.get("kind") or "") == args.kind
            and str(r.get("round") or "") == args.round
            and _record_variant(r) == clean_variant
            and _record_version(r) == version
        )

        receipt = {
            "ts": _utc_now_iso(),
            "reservation_id": f"web-{uuid.uuid4().hex[:12]}",
            "channel": "web_unlimited",
            "shot": args.shot,
            "kind": args.kind,
            "round": args.round,
            "round_cap": None,
            "variant": clean_variant or None,
            "version": version,
            "command": "web_unlimited",
            "model": model,
            "is_workflow": False,
            "params_hash": params_hash,
            "job_id": (args.job_id or "").strip(),
            "status": args.status,
            "estimated_credits": 0.0,
            "actual_credits": 0.0,
            "credits": 0.0,
            "prompt_file": args.prompt_file,
            "refs": refs,
            "url": args.url,
            "out": args.out,
            "note": (args.note or "").strip() or None,
            "attempt": prior_web,
        }
        _append_receipt(campaign_dir, receipt)

    print(
        json.dumps(
            {
                "ok": True,
                "channel": "web_unlimited",
                "shot": args.shot,
                "kind": args.kind,
                "round": args.round,
                "variant": clean_variant or None,
                "version": version,
                "model": model,
                "status": args.status,
                "credits": 0,
                "attempt": prior_web,
                "receipt": receipt,
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    return 0


def _cmd_run(args: argparse.Namespace, extra_args: list[str]) -> int:
    campaign_dir = Path(args.campaign)
    hf_bin = _resolve_hf_bin(getattr(args, "higgsfield_bin", None))
    hf_command = args.hf_command
    model = args.model or (hf_command if hf_command != "generate" else None)
    if not model:
        print(
            json.dumps(
                {
                    "ok": False,
                    "error_code": "missing_model",
                    "message": "--model is required when --command is 'generate'",
                },
                indent=2,
            )
        )
        return 2

    rcap_err = _validate_round_cap(args.round_cap)
    if rcap_err is not None:
        print(json.dumps(rcap_err, indent=2))
        return 2

    clean_variant, var_err = _validate_variant_arg(args.kind, args.variant)
    if var_err is not None:
        print(json.dumps(var_err, indent=2))
        return 2

    cli_args, pf_err = _append_prompt_file(args.prompt_file, extra_args)
    if pf_err is not None or cli_args is None:
        print(json.dumps(pf_err, indent=2))
        return 2

    if not campaign_dir.is_dir():
        print(
            json.dumps(
                {
                    "ok": False,
                    "error_code": "brief_not_active",
                    "message": f"campaign directory not found: {campaign_dir}",
                },
                indent=2,
            )
        )
        return 2

    # Verify brief envelope even for resumed/download-retried runs
    _, env_err = _load_envelope_or_error(campaign_dir)
    if env_err is not None:
        print(json.dumps(env_err, indent=2, ensure_ascii=False))
        return 2

    # Fail-closed shotlist load, LOCKED asset check, and version validation
    version, sl_err = _inspect_shotlist_guard(
        campaign_dir, args.shot, args.kind, args.round, args.version
    )
    if sl_err is not None or version is None:
        print(json.dumps(sl_err, indent=2, ensure_ascii=False))
        return 2

    params_hash = compute_params_hash(
        shot=args.shot,
        kind=args.kind,
        round_name=args.round,
        model=model,
        is_workflow=args.workflow,
        args=cli_args,
        hf_command=hf_command,
        variant=clean_variant,
        version=version,
    )

    reservation_id: str | None = None
    attempt_idx = 0
    estimated_credits = 0.0
    resumed_job_id: str | None = None
    resumed_get_payload: dict[str, Any] | None = None
    download_retry_rec: dict[str, Any] | None = None
    preflight_info: dict[str, Any] | None = None
    known_job_ids: set[str] = set()
    warnings: list[str] = []

    # Phase 1: locked duplicate check, download_failed check, preflight, and atomic reservation
    with _receipts_lock(campaign_dir):
        try:
            records = _read_receipts_raw(campaign_dir)
        except CorruptReceiptsError as exc:
            print(
                json.dumps(
                    {
                        "ok": False,
                        "error_code": "corrupt_receipts",
                        "message": str(exc),
                    },
                    indent=2,
                )
            )
            return 2

        known_job_ids = {
            str(r.get("job_id") or "").strip()
            for r in records
            if str(r.get("job_id") or "").strip()
        }

        # 1a. Check if a previous run completed remotely but failed locally on download
        download_retry_rec = _find_download_failed_receipt(records, params_hash)

        if download_retry_rec is not None:
            reservation_id = (
                str(download_retry_rec.get("reservation_id") or "").strip()
                or f"res-{uuid.uuid4().hex[:12]}"
            )
            resumed_job_id = str(download_retry_rec.get("job_id") or "")
            attempt_idx = int(download_retry_rec.get("attempt") or 0)
            est_r = download_retry_rec.get("estimated_credits")
            estimated_credits = (
                float(est_r) if _is_number(est_r) else _effective_credits(download_retry_rec)
            )
            if args.dry_run:
                print(
                    json.dumps(
                        {
                            "ok": True,
                            "dry_run": True,
                            "resumed": True,
                            "download_retry": True,
                            "round": args.round,
                            "round_cap": _clean_num(args.round_cap),
                            "variant": clean_variant or None,
                            "version": version,
                            "job_id": resumed_job_id,
                            "url": download_retry_rec.get("url"),
                            "out": args.out,
                            "params_hash": params_hash,
                        },
                        indent=2,
                        ensure_ascii=False,
                    )
                )
                return 0
        else:
            # 1b. Check for in-flight remote job / active reservation
            dup_info = _find_in_flight_job(records, params_hash, hf_bin, hf_command)
            warnings.extend(dup_info["warnings"])
            action = dup_info["action"]

            if action == "blocked_reservation":
                print(
                    json.dumps(
                        {
                            "ok": False,
                            "error_code": "reservation_in_flight",
                            "reservation_id": dup_info["reservation_id"],
                            "job_id": dup_info["job_id"],
                            "params_hash": params_hash,
                            "message": (
                                "an unresolved reservation for this exact params_hash is already "
                                "active in receipts.jsonl; wait for completion or resolve manually "
                                "before retrying to prevent double-spend"
                            ),
                            "warnings": warnings,
                        },
                        indent=2,
                        ensure_ascii=False,
                    )
                )
                return 2

            if action in ("wait", "use_get_result"):
                resumed_job_id = dup_info["job_id"]
                reservation_id = dup_info["reservation_id"] or f"res-{uuid.uuid4().hex[:12]}"
                resumed_get_payload = dup_info["get_payload"]
                _, _, cur_attempts, _, _ = _summarize_receipts(records)
                attempt_idx = (
                    dup_info["attempt"]
                    if dup_info["attempt"] is not None
                    else cur_attempts.get(
                        (args.shot, args.kind, args.round, clean_variant, version), 0
                    )
                )
                estimated_credits = (
                    float(dup_info["estimated_credits"])
                    if dup_info["estimated_credits"] is not None
                    else 0.0
                )
                if args.dry_run:
                    wait_cmd = _build_wait_cmd(
                        hf_bin, hf_command, resumed_job_id or "", args.wait_timeout
                    )
                    plan = {
                        "ok": True,
                        "dry_run": True,
                        "resumed": True,
                        "round": args.round,
                        "round_cap": _clean_num(args.round_cap),
                        "variant": clean_variant or None,
                        "version": version,
                        "job_id": resumed_job_id,
                        "params_hash": params_hash,
                        "command": wait_cmd,
                        "out": args.out,
                        "warnings": warnings,
                    }
                    print(json.dumps(plan, indent=2, ensure_ascii=False))
                    return 0
            else:
                # 1c. Fresh submission: run preflight under lock so reservations count toward both caps
                pf_rc, preflight_info = _do_preflight(
                    campaign_dir=campaign_dir,
                    shot=args.shot,
                    kind=args.kind,
                    round_name=args.round,
                    round_cap=args.round_cap,
                    variant=clean_variant,
                    cli_version=args.version,
                    model=model,
                    is_workflow=args.workflow,
                    hf_command=hf_command,
                    hf_bin=hf_bin,
                    extra_args=cli_args,
                    records=records,
                    resolved_version=version,
                    block_local_paths=bool(args.dry_run),
                )
                if pf_rc != 0:
                    print(json.dumps(preflight_info, indent=2, ensure_ascii=False))
                    return pf_rc

                warnings.extend(preflight_info.get("warnings") or [])
                estimated_credits = float(preflight_info["estimated_credits"])
                attempt_idx = int(preflight_info["attempts_used"])

                if args.dry_run:
                    planned_cmd = _build_exec_cmd(
                        hf_bin, hf_command, model, args.workflow, cli_args, args.wait_timeout
                    )
                    plan = {
                        "ok": True,
                        "dry_run": True,
                        "campaign": str(campaign_dir),
                        "shot": args.shot,
                        "kind": args.kind,
                        "round": args.round,
                        "round_cap": _clean_num(args.round_cap),
                        "variant": clean_variant or None,
                        "version": version,
                        "command_type": hf_command,
                        "model": model,
                        "is_workflow": args.workflow,
                        "params_hash": params_hash,
                        "command": planned_cmd,
                        "out": args.out,
                        "preflight": preflight_info,
                        "warnings": warnings,
                    }
                    print(json.dumps(plan, indent=2, ensure_ascii=False))
                    return 0

                # Write atomic reservation BEFORE releasing lock and BEFORE remote CLI call
                reservation_id = f"res-{uuid.uuid4().hex[:12]}"
                reserved_rec = {
                    "ts": _utc_now_iso(),
                    "reservation_id": reservation_id,
                    "shot": args.shot,
                    "kind": args.kind,
                    "round": args.round,
                    "round_cap": _clean_num(args.round_cap),
                    "variant": clean_variant or None,
                    "version": version,
                    "command": hf_command,
                    "model": model,
                    "is_workflow": bool(args.workflow),
                    "params_hash": params_hash,
                    "job_id": "",
                    "status": "reserved",
                    "estimated_credits": _clean_num(estimated_credits),
                    "actual_credits": None,
                    "credits": _clean_num(estimated_credits),
                    "url": None,
                    "out": None,
                    "attempt": attempt_idx,
                }
                _append_receipt(campaign_dir, reserved_rec)

    # Phase 1.5: Handle download-only retry (zero remote submission, zero extra spend)
    if download_retry_rec is not None:
        media_url = str(download_retry_rec["url"])
        prev_actual = _effective_credits(download_retry_rec)
        download_error: str | None = None
        out_recorded: str | None = None
        if args.out:
            try:
                _download_or_copy(media_url, Path(args.out))
                out_recorded = args.out
            except (OSError, urllib.error.URLError, http.client.HTTPException) as exc:
                download_error = f"retry download failed for '{args.out}': {exc}"

        final_status = "completed" if download_error is None else "download_failed"
        terminal_rec = {
            "ts": _utc_now_iso(),
            "reservation_id": reservation_id,
            "shot": args.shot,
            "kind": args.kind,
            "round": args.round,
            "round_cap": _clean_num(args.round_cap),
            "variant": clean_variant or None,
            "version": version,
            "command": hf_command,
            "model": model,
            "is_workflow": bool(args.workflow),
            "params_hash": params_hash,
            "job_id": resumed_job_id or "",
            "status": final_status,
            "estimated_credits": _clean_num(estimated_credits),
            "actual_credits": _clean_num(prev_actual),
            "credits": _clean_num(prev_actual),
            "url": media_url,
            "out": out_recorded,
            "attempt": attempt_idx,
        }
        with _receipts_lock(campaign_dir):
            _append_receipt(campaign_dir, terminal_rec)

        result: dict[str, Any] = {
            "ok": download_error is None,
            "resumed": True,
            "download_retried": True,
            "round": args.round,
            "round_cap": _clean_num(args.round_cap),
            "variant": clean_variant or None,
            "version": version,
            "reservation_id": reservation_id,
            "job_id": terminal_rec["job_id"],
            "status": final_status,
            "estimated_credits": terminal_rec["estimated_credits"],
            "actual_credits": terminal_rec["actual_credits"],
            "credits": terminal_rec["credits"],
            "url": media_url,
            "out": out_recorded,
            "params_hash": params_hash,
            "attempt": attempt_idx,
            "receipt": terminal_rec,
            "warnings": warnings,
        }
        if download_error:
            result["error_code"] = "download_failed"
            result["error"] = download_error
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0 if download_error is None else 1

    # Phase 2: Execute remote CLI outside lock so parallel assets run concurrently
    if resumed_get_payload is not None:
        exec_rc = 0
        exec_out = json.dumps(resumed_get_payload)
        exec_err = ""
        exec_json: Any = resumed_get_payload
    elif resumed_job_id is not None:
        exec_cmd = _build_wait_cmd(hf_bin, hf_command, resumed_job_id, args.wait_timeout)
        exec_rc, exec_out, exec_err, exec_json = _run_cli(exec_cmd)
    else:
        exec_cli_args = cli_args
        if hf_command == "generate" and args.workflow and cli_args:
            wf_rc, _, _, wf_json = _run_cli([hf_bin, "workflow", "get", model, "--json"])
            if wf_rc == 0 and isinstance(wf_json, dict):
                exec_cli_args = _filter_workflow_exec_args(cli_args, wf_json)
        exec_cmd = _build_exec_cmd(
            hf_bin, hf_command, model, args.workflow, exec_cli_args, args.wait_timeout
        )
        exec_rc, exec_out, exec_err, exec_json = _run_cli(exec_cmd)

    # Parse response
    job_id = (
        _extract_string_field(exec_json, ("job_id", "id", "request_set_id", "request_id"))
        if isinstance(exec_json, (dict, list))
        else None
    ) or resumed_job_id or ""

    raw_status = (
        _extract_string_field(exec_json, ("status", "state"))
        if isinstance(exec_json, (dict, list))
        else None
    )
    status = _normalize_job_status(raw_status, exec_rc)
    is_completed = exec_rc == 0 and status == "completed"

    media_url = (
        _extract_string_field(
            exec_json,
            (
                "result_url",
                "url",
                "output_url",
                "media_url",
                "video_url",
                "image_url",
                "audio_url",
                "min_result_url",
                "local_path",
                "path",
            ),
        )
        if isinstance(exec_json, (dict, list))
        else None
    )

    reported_credits = (
        _extract_numeric_field(
            exec_json, ("credits", "credits_used", "actual_credits", "cost")
        )
        if isinstance(exec_json, (dict, list))
        else None
    )
    if reported_credits is not None and (
        not math.isfinite(reported_credits) or reported_credits < 0
    ):
        reported_credits = None

    # Classify terminal outcome and exact accounting
    download_error = None
    out_recorded = None
    actual_credits: float | None = None
    recorded_credits = 0.0

    if not job_id and not is_completed:
        combined_text = f"{exec_err} {exec_out}".lower()
        is_ambiguous_transport = exec_rc != 127 and any(
            marker in combined_text for marker in AMBIGUOUS_TRANSPORT_MARKERS
        )
        if is_ambiguous_transport:
            if hf_command == "generate":
                recovered_jid, rec_warn = _recover_job_id_from_list(
                    hf_bin=hf_bin,
                    model=model,
                    params_hash=params_hash,
                    known_job_ids=known_job_ids,
                )
                if rec_warn:
                    warnings.append(rec_warn)
                if recovered_jid:
                    job_id = recovered_jid
            status = "in_progress"
            actual_credits = None
            recorded_credits = estimated_credits
            warnings.append(
                "ambiguous timeout/transport failure without terminal job status; "
                "keeping reservation in_progress to prevent double-spend"
            )
        else:
            # Explicit non-timeout rejection with NO remote job created: release reservation
            status = "rejected"
            actual_credits = 0.0
            recorded_credits = 0.0
    elif status == "in_progress" or (job_id and raw_status is None and exec_rc != 0):
        # Timed out, still running remotely, or non-zero exit with known job_id & no terminal status:
        # preserve in_progress and retain estimated_credits reserved!
        status = "in_progress"
        actual_credits = None
        recorded_credits = (
            float(reported_credits)
            if reported_credits is not None and reported_credits > 0
            else estimated_credits
        )
    elif is_completed:
        actual_credits = (
            float(reported_credits) if reported_credits is not None else estimated_credits
        )
        recorded_credits = actual_credits
        if args.out:
            if not media_url:
                download_error = "generation completed but returned no media url or local_path"
                status = "download_failed"
                is_completed = False
            else:
                try:
                    _download_or_copy(media_url, Path(args.out))
                    out_recorded = args.out
                except (OSError, urllib.error.URLError, http.client.HTTPException) as exc:
                    download_error = f"failed to save output media to '{args.out}': {exc}"
                    status = "download_failed"
                    is_completed = False
    else:
        # Job created remotely (has job_id) and failed terminally
        actual_credits = float(reported_credits) if reported_credits is not None else 0.0
        recorded_credits = actual_credits

    # Phase 3: Re-acquire lock and append terminal receipt matching reservation_id
    terminal_rec = {
        "ts": _utc_now_iso(),
        "reservation_id": reservation_id,
        "shot": args.shot,
        "kind": args.kind,
        "round": args.round,
        "round_cap": _clean_num(args.round_cap),
        "variant": clean_variant or None,
        "version": version,
        "command": hf_command,
        "model": model,
        "is_workflow": bool(args.workflow),
        "params_hash": params_hash,
        "job_id": job_id,
        "status": status,
        "estimated_credits": _clean_num(estimated_credits),
        "actual_credits": _clean_num(actual_credits) if actual_credits is not None else None,
        "credits": _clean_num(recorded_credits),
        "url": media_url,
        "out": out_recorded,
        "attempt": attempt_idx,
    }
    with _receipts_lock(campaign_dir):
        _append_receipt(campaign_dir, terminal_rec)

    result = {
        "ok": is_completed,
        "resumed": resumed_job_id is not None,
        "round": args.round,
        "round_cap": _clean_num(args.round_cap),
        "variant": clean_variant or None,
        "version": version,
        "reservation_id": reservation_id,
        "job_id": job_id,
        "status": status,
        "estimated_credits": terminal_rec["estimated_credits"],
        "actual_credits": terminal_rec["actual_credits"],
        "credits": terminal_rec["credits"],
        "url": media_url,
        "out": out_recorded,
        "params_hash": params_hash,
        "attempt": attempt_idx,
        "receipt": terminal_rec,
        "warnings": warnings,
    }
    if exec_rc == 127:
        result["error_code"] = "cli_not_found"
        result["message"] = exec_err.strip()
    elif download_error:
        result["error_code"] = "download_failed"
        result["error"] = download_error
        if exec_out.strip():
            result["raw_stdout_preview"] = exec_out.strip()[:1500]
    elif not is_completed:
        result["exit_code"] = exec_rc
        if exec_err.strip():
            result["stderr"] = exec_err.strip()
        if exec_out.strip() and exec_json is None:
            result["stdout"] = exec_out.strip()

    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if is_completed else 1


def _cmd_status(args: argparse.Namespace) -> int:
    campaign_dir = Path(args.campaign)
    brief_path = campaign_dir / "brief.md"
    if not brief_path.is_file():
        err = {
            "ok": False,
            "error_code": "brief_not_found",
            "message": f"brief.md not found in {campaign_dir}",
        }
        if args.as_json:
            print(json.dumps(err, indent=2))
        else:
            print(f"ERROR: {err['message']}", file=sys.stderr)
        return 2

    envelope = _CHECK_BRIEF.parse_budget_envelope(brief_path)
    try:
        records = _read_receipts_raw(campaign_dir)
    except CorruptReceiptsError as exc:
        err = {
            "ok": False,
            "error_code": "corrupt_receipts",
            "message": str(exc),
        }
        if args.as_json:
            print(json.dumps(err, indent=2))
        else:
            print(f"ERROR: {err['message']}", file=sys.stderr)
        return 2

    collapsed = _collapse_receipts(records)
    total_spent, spent_by_round, attempts_map, _, active_reserved = _summarize_receipts(records)
    web_by_round: dict[str, int] = {r: 0 for r in VALID_ROUNDS}
    web_unlimited_total = 0
    for rec in collapsed:
        if str(rec.get("channel") or "").lower() == "web_unlimited":
            web_unlimited_total += 1
            rn = str(rec.get("round") or "")
            if rn in web_by_round:
                web_by_round[rn] += 1

    campaign_cap = envelope.get("campaign_cap")
    max_retries = envelope.get("max_retries")
    remaining_campaign = (
        _clean_num(campaign_cap - total_spent) if campaign_cap is not None else None
    )

    shots_summary: dict[str, dict[str, Any]] = {}
    for rec in collapsed:
        if not _counts_as_attempt(rec):
            continue
        shot = str(rec.get("shot") or "unknown")
        kind = str(rec.get("kind") or "video")
        round_name = str(rec.get("round") or "unknown")
        variant = _record_variant(rec)
        version = _record_version(rec)
        entry = shots_summary.setdefault(
            shot,
            {
                "attempts": {},
                "credits": 0.0,
                "latest_job_id": None,
                "latest_status": None,
            },
        )
        kr_parts = [kind, round_name]
        if variant:
            kr_parts.append(variant)
        if version != 1:
            kr_parts.append(f"v{version}")
        kr = "/".join(kr_parts)
        entry["attempts"][kr] = attempts_map.get(
            (shot, kind, round_name, variant, version), 0
        )
        entry["credits"] = _clean_num(float(entry["credits"]) + _effective_credits(rec))
        entry["latest_job_id"] = rec.get("job_id")
        entry["latest_status"] = rec.get("status")

    report = {
        "ok": True,
        "campaign": str(campaign_dir),
        "brief_status": envelope.get("status"),
        "campaign_cap": campaign_cap,
        "total_spent": _clean_num(total_spent),
        "active_reserved": _clean_num(active_reserved),
        "remaining_campaign": remaining_campaign,
        "lookbook_variants": envelope.get("lookbook_variants"),
        "max_retries": max_retries,
        "auto_open_dailies": envelope.get("auto_open_dailies"),
        "rounds": {
            r: {
                "spent": _clean_num(spent_by_round[r]),
                "web_unlimited_runs": web_by_round[r],
            }
            for r in VALID_ROUNDS
        },
        "web_unlimited_runs": web_unlimited_total,
        "receipt_count": len(records),
        "unique_job_count": len(collapsed),
        "shots": shots_summary,
    }

    if args.as_json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        print(
            f"Campaign: {campaign_dir} (brief={report['brief_status']}, "
            f"max_retries={max_retries}, lookbook_variants={report['lookbook_variants']})"
        )
        print(
            f"  Campaign cap: spent {report['total_spent']} / {campaign_cap} credits "
            f"(active_reserved: {report['active_reserved']}, remaining: {remaining_campaign}, "
            f"web_unlimited_runs: {web_unlimited_total})"
        )
        round_parts = ", ".join(
            f"{r}={report['rounds'][r]['spent']}" for r in VALID_ROUNDS
        )
        print(f"  Rounds spent: {round_parts}")
        if shots_summary:
            print("  Assets:")
            for sid in sorted(shots_summary):
                s = shots_summary[sid]
                att_str = ", ".join(f"{k}={v}" for k, v in sorted(s["attempts"].items()))
                print(
                    f"    - {sid}: credits={s['credits']} attempts=({att_str}) "
                    f"latest_job={s['latest_job_id']} status={s['latest_status']}"
                )
        else:
            print("  Assets: (no receipts yet)")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Two-layer budget-enforcing, lock-aware wrapper around the higgsfield CLI."
    )
    parser.add_argument(
        "--higgsfield-bin",
        default=None,
        help="Path to higgsfield executable (overrides HIGGSFIELD_BIN env var).",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # preflight
    pf = sub.add_parser(
        "preflight",
        help="Check brief status, asset lock, retry cap, Campaign cap, and mandatory --round-cap.",
    )
    pf.add_argument("--campaign", required=True, help="Campaign directory containing brief.md.")
    pf.add_argument("--shot", required=True, help="Shot, lookbook, or audio asset identifier.")
    pf.add_argument(
        "--kind",
        choices=VALID_KINDS,
        default="video",
        help="Generation kind for lock and retry accounting (default: video).",
    )
    pf.add_argument(
        "--round",
        required=True,
        choices=VALID_ROUNDS,
        help="Production round (R2, R3, R4, R4A, R4B, or R5).",
    )
    pf.add_argument(
        "--round-cap",
        type=float,
        required=True,
        help="Mandatory Director-approved cumulative credit ceiling for --round.",
    )
    pf.add_argument(
        "--variant",
        default="",
        help="Optional Lookbook variant tag (e.g. A, B, C); allowed only when --kind lookbook.",
    )
    pf.add_argument(
        "--version",
        type=int,
        default=None,
        help="Optional asset version (>= 1); auto-resolved from shotlist.json when omitted.",
    )
    pf.add_argument(
        "--command",
        dest="hf_command",
        choices=VALID_HF_COMMANDS,
        default="generate",
        help="Higgsfield CLI command namespace (default: generate).",
    )
    pf.add_argument(
        "--model",
        default=None,
        help="Higgsfield model or workflow identifier (required for --command generate).",
    )
    pf.add_argument("--workflow", action="store_true", help="Treat model as a Higgsfield workflow.")
    pf.add_argument("--prompt-file", default=None, help="Read prompt text from file and append --prompt.")
    pf.add_argument(
        "--higgsfield-bin",
        default=argparse.SUPPRESS,
        help="Path to higgsfield executable (overrides HIGGSFIELD_BIN env var).",
    )

    # run
    rn = sub.add_parser(
        "run",
        help="Run a guarded, lock-checked, deduplicated paid generation and record immutable receipts.",
    )
    rn.add_argument("--campaign", required=True, help="Campaign directory containing brief.md.")
    rn.add_argument("--shot", required=True, help="Shot, lookbook, or audio asset identifier.")
    rn.add_argument("--kind", required=True, choices=VALID_KINDS, help="Generation kind.")
    rn.add_argument(
        "--round",
        required=True,
        choices=VALID_ROUNDS,
        help="Production round (R2, R3, R4, R4A, R4B, or R5).",
    )
    rn.add_argument(
        "--round-cap",
        type=float,
        required=True,
        help="Mandatory Director-approved cumulative credit ceiling for --round.",
    )
    rn.add_argument(
        "--variant",
        default="",
        help="Optional Lookbook variant tag (e.g. A, B, C); allowed only when --kind lookbook.",
    )
    rn.add_argument(
        "--version",
        type=int,
        default=None,
        help="Optional asset version (>= 1); auto-resolved from shotlist.json when omitted.",
    )
    rn.add_argument(
        "--command",
        dest="hf_command",
        choices=VALID_HF_COMMANDS,
        default="generate",
        help="Higgsfield CLI command namespace (default: generate).",
    )
    rn.add_argument(
        "--model",
        default=None,
        help="Higgsfield model or workflow identifier (required for --command generate).",
    )
    rn.add_argument("--workflow", action="store_true", help="Invoke `generate workflow` instead of `create`.")
    rn.add_argument("--prompt-file", default=None, help="Read prompt text from file and append --prompt.")
    rn.add_argument("--out", default=None, help="Download or copy resulting media to this path.")
    rn.add_argument("--wait-timeout", default="20m", help="Timeout passed to --wait-timeout / --timeout (default: 20m).")
    rn.add_argument(
        "--dry-run",
        action="store_true",
        help="Run preflight and print planned command without executing or writing a paid receipt.",
    )
    rn.add_argument(
        "--higgsfield-bin",
        default=argparse.SUPPRESS,
        help="Path to higgsfield executable (overrides HIGGSFIELD_BIN env var).",
    )

    # upload
    up = sub.add_parser(
        "upload",
        help="Upload a local reference asset via `higgsfield upload create` and record a 0-credit receipt.",
    )
    up.add_argument("--campaign", required=True, help="Campaign directory containing brief.md.")
    up.add_argument("--file", required=True, help="Local image/video/audio file to upload.")
    up.add_argument("--ref-id", default=None, help="Reference identifier (e.g. ref_bag_front).")
    up.add_argument(
        "--round",
        choices=VALID_ROUNDS,
        default="R2",
        help="Production round for receipt metadata (default: R2).",
    )
    up.add_argument(
        "--higgsfield-bin",
        default=argparse.SUPPRESS,
        help="Path to higgsfield executable (overrides HIGGSFIELD_BIN env var).",
    )

    # log-web
    lw = sub.add_parser(
        "log-web",
        help="Log a 0-credit Web Unlimited generation trace into receipts.jsonl without consuming paid caps.",
    )
    lw.add_argument("--campaign", required=True, help="Campaign directory containing brief.md.")
    lw.add_argument("--shot", required=True, help="Shot, lookbook, or audio asset identifier.")
    lw.add_argument("--kind", required=True, choices=VALID_KINDS, help="Generation kind.")
    lw.add_argument(
        "--round",
        required=True,
        choices=VALID_ROUNDS,
        help="Production round (R2, R3, R4, R4A, R4B, or R5).",
    )
    lw.add_argument("--model", required=True, help="Model or workflow label used in Web Unlimited.")
    lw.add_argument(
        "--status",
        choices=VALID_WEB_STATUSES,
        default="completed",
        help="Observed generation outcome (default: completed).",
    )
    lw.add_argument(
        "--variant",
        default="",
        help="Optional Lookbook variant tag (A, B, C); allowed only when --kind lookbook.",
    )
    lw.add_argument(
        "--version",
        type=int,
        default=None,
        help="Optional asset version (>= 1); auto-resolved from shotlist.json when omitted.",
    )
    lw.add_argument("--prompt-file", default=None, help="Path to prompt text file used.")
    lw.add_argument("--out", default=None, help="Saved local media output path.")
    lw.add_argument("--url", default=None, help="Optional remote media URL.")
    lw.add_argument("--job-id", default=None, help="Optional Web job identifier.")
    lw.add_argument(
        "--ref",
        dest="refs",
        action="append",
        default=[],
        help="Reference/lookbook ID attached to the generation (repeatable).",
    )
    lw.add_argument("--note", default=None, help="Short factual trace note (e.g. failure cause or settings).")

    # status
    st = sub.add_parser(
        "status",
        help="Show spent vs remaining Campaign cap, active reserved, per-round spend, and per-asset attempts.",
    )
    st.add_argument("--campaign", required=True, help="Campaign directory.")
    st.add_argument("--json", action="store_true", dest="as_json", help="Emit JSON summary.")

    return parser


def main(argv: list[str] | None = None) -> int:
    raw_argv = list(sys.argv[1:] if argv is None else argv)
    if "--" in raw_argv:
        sep = raw_argv.index("--")
        own_argv = raw_argv[:sep]
        extra_args = raw_argv[sep + 1 :]
    else:
        own_argv = raw_argv
        extra_args = []

    parser = build_parser()
    args = parser.parse_args(own_argv)

    if args.command == "preflight":
        return _cmd_preflight(args, extra_args)
    if args.command == "run":
        return _cmd_run(args, extra_args)
    if args.command == "upload":
        return _cmd_upload(args)
    if args.command == "log-web":
        return _cmd_log_web(args)
    if args.command == "status":
        return _cmd_status(args)
    parser.error(f"unknown subcommand: {args.command}")
    return 2


if __name__ == "__main__":
    sys.exit(main())

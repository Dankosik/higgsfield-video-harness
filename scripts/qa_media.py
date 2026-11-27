#!/usr/bin/env python3
"""Deterministic media QA and 3x2 contact-sheet generator via ffmpeg/ffprobe."""

from __future__ import annotations

import sys

sys.dont_write_bytecode = True

import argparse
import contextlib
import datetime
import fcntl
import json
import math
import re
import shutil
import struct
import subprocess
import tempfile
import zlib
from collections.abc import Iterator
from pathlib import Path
from typing import Any

SAMPLE_W = 160
SAMPLE_H = 90
SAMPLE_FPS = 4
TILE_SIZE = 16
FRAME_BYTES = SAMPLE_W * SAMPLE_H
STILL_DIFF_THRESHOLD = 1.0
LOCKED_STILL_W = 160
LOCKED_STILL_H = 96
LOCKED_STILL_GRID = 8
LOCKED_STILL_DRIFT_THRESHOLD = 12.0
SILENT_MEAN_DB_THRESHOLD = -60.0
VOICE_RMS_ACTIVE_DB = -34.0

VALID_REVIEW_ROUNDS = ("R2", "R2A", "R2B", "R3", "R4", "R4A", "R4B", "R5")
VALID_REVIEW_VERDICTS = ("PASS", "CONCERNS", "FAIL", "REVIEW_HANDOFF_INVALID")
VALID_DEFECT_CLASSES = (
    "NONE",
    "MEDIA_TECH_DEFECT",
    "VISUAL_DRIFT_DEFECT",
    "TASTE_REGRESSION",
    "CONTINUITY_DEFECT",
    "NARRATIVE_DEFECT",
    "POLICY_BLOCK",
    "BUDGET_CAP",
    "CONCERN",
    "FOLLOW_UP",
)


def _ensure_ffmpeg_tools() -> tuple[str, str]:
    ffmpeg = shutil.which("ffmpeg")
    ffprobe = shutil.which("ffprobe")
    if not ffmpeg or not ffprobe:
        missing = [name for name, path in (("ffmpeg", ffmpeg), ("ffprobe", ffprobe)) if not path]
        raise RuntimeError(f"required tool(s) not found in PATH: {', '.join(missing)}")
    return ffmpeg, ffprobe


def _parse_rational(rate_str: str | None) -> float | None:
    if not rate_str or rate_str == "0/0":
        return None
    if "/" in rate_str:
        num_s, den_s = rate_str.split("/", 1)
        try:
            num, den = float(num_s), float(den_s)
            if den == 0:
                return None
            val = num / den
            return round(val, 4) if val > 0 else None
        except ValueError:
            return None
    try:
        val = float(rate_str)
        return round(val, 4) if val > 0 else None
    except ValueError:
        return None


def _parse_finite_float(val: Any) -> float | None:
    if val is None:
        return None
    try:
        f = float(val)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(f):
        return None
    return round(f, 3)


def _ffprobe_json(ffprobe: str, media_path: Path) -> dict[str, Any]:
    proc = subprocess.run(
        [
            ffprobe,
            "-v",
            "error",
            "-show_format",
            "-show_streams",
            "-of",
            "json",
            str(media_path),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"ffprobe failed (exit {proc.returncode}): {proc.stderr.strip()}")
    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"ffprobe returned invalid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise TypeError("ffprobe returned unexpected root type")
    return data


def _detect_black_gaps(
    ffmpeg: str, video_path: Path, black_min: float
) -> list[dict[str, float]]:
    proc = subprocess.run(
        [
            ffmpeg,
            "-v",
            "info",
            "-i",
            str(video_path),
            "-vf",
            f"blackdetect=d={black_min}:pix_th=0.10",
            "-an",
            "-f",
            "null",
            "-",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    gaps: list[dict[str, float]] = []
    for m in re.finditer(
        r"black_start:([0-9.]+)\s+black_end:([0-9.]+)\s+black_duration:([0-9.]+)",
        proc.stderr,
    ):
        gaps.append(
            {
                "start": round(float(m.group(1)), 3),
                "end": round(float(m.group(2)), 3),
                "duration": round(float(m.group(3)), 3),
            }
        )
    return gaps


def _max_tile_diff(frame_a: bytes, frame_b: bytes) -> float:
    if frame_a == frame_b:
        return 0.0
    max_diff = 0.0
    for ty in range(0, SAMPLE_H, TILE_SIZE):
        y_end = min(ty + TILE_SIZE, SAMPLE_H)
        for tx in range(0, SAMPLE_W, TILE_SIZE):
            x_end = min(tx + TILE_SIZE, SAMPLE_W)
            total = 0
            count = (y_end - ty) * (x_end - tx)
            for row in range(ty, y_end):
                offset = row * SAMPLE_W
                s_a = frame_a[offset + tx : offset + x_end]
                s_b = frame_b[offset + tx : offset + x_end]
                for pa, pb in zip(s_a, s_b):
                    diff = pa - pb
                    total += diff if diff >= 0 else -diff
            mean_diff = total / count
            max_diff = max(max_diff, mean_diff)
    return max_diff


def _analyze_motion(
    ffmpeg: str,
    video_path: Path,
    duration: float,
    max_still: float,
    max_frozen_tail: float | None = None,
) -> dict[str, Any]:
    proc = subprocess.run(
        [
            ffmpeg,
            "-v",
            "error",
            "-i",
            str(video_path),
            "-vf",
            f"fps={SAMPLE_FPS},scale={SAMPLE_W}:{SAMPLE_H},format=gray",
            "-f",
            "rawvideo",
            "-pix_fmt",
            "gray",
            "-",
        ],
        capture_output=True,
        check=False,
    )
    if proc.returncode != 0:
        err_msg = proc.stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(f"motion sampling failed: {err_msg}")

    raw = proc.stdout
    num_frames = len(raw) // FRAME_BYTES
    if num_frames < 2:
        return {
            "sampled_frames": num_frames,
            "moving_seconds": 0.0,
            "max_still_stretch": 0.0,
            "still_stretches": [],
            "frozen_tail": None,
        }

    dt = 1.0 / SAMPLE_FPS
    diffs: list[float] = []
    prev = raw[0:FRAME_BYTES]
    for i in range(1, num_frames):
        curr = raw[i * FRAME_BYTES : (i + 1) * FRAME_BYTES]
        diffs.append(_max_tile_diff(prev, curr))
        prev = curr

    # Identify contiguous still runs (max_tile_diff < STILL_DIFF_THRESHOLD)
    still_runs: list[dict[str, float]] = []
    run_start_idx: int | None = None
    for idx, d in enumerate(diffs):
        is_still = d < STILL_DIFF_THRESHOLD
        if is_still and run_start_idx is None:
            run_start_idx = idx
        elif not is_still and run_start_idx is not None:
            start_t = run_start_idx * dt
            end_t = idx * dt
            still_runs.append(
                {
                    "start": round(start_t, 3),
                    "end": round(end_t, 3),
                    "duration": round(end_t - start_t, 3),
                    "reaches_end": False,
                }
            )
            run_start_idx = None

    if run_start_idx is not None:
        start_t = run_start_idx * dt
        end_t = max(len(diffs) * dt, duration)
        still_runs.append(
            {
                "start": round(start_t, 3),
                "end": round(end_t, 3),
                "duration": round(end_t - start_t, 3),
                "reaches_end": True,
            }
        )

    long_still = [
        {"start": r["start"], "end": r["end"], "duration": r["duration"]}
        for r in still_runs
        if r["duration"] > max_still
    ]
    max_still_observed = max((r["duration"] for r in still_runs), default=0.0)

    # Compute moving time before any trailing still run
    tail_run = still_runs[-1] if (still_runs and still_runs[-1]["reaches_end"]) else None
    if tail_run is not None:
        tail_start_idx = round(tail_run["start"] / dt)
        moving_before_tail = sum(
            1 for d in diffs[:tail_start_idx] if d >= STILL_DIFF_THRESHOLD
        ) * dt
    else:
        moving_before_tail = sum(1 for d in diffs if d >= STILL_DIFF_THRESHOLD) * dt

    frozen_tail_threshold = max_still if max_frozen_tail is None else max_frozen_tail
    frozen_tail: dict[str, float] | None = None
    if max_still < 60.0 and tail_run is not None and tail_run["duration"] >= frozen_tail_threshold:
        moved_enough = moving_before_tail >= 1.5 or (
            duration > 0 and moving_before_tail >= 0.30 * duration and moving_before_tail > 0
        )
        mostly_frozen = duration > 0 and moving_before_tail > 0 and tail_run["duration"] >= 0.70 * duration
        if moved_enough or mostly_frozen:
            frozen_tail = {
                "start": tail_run["start"],
                "end": tail_run["end"],
                "duration": tail_run["duration"],
                "moving_before_tail": round(moving_before_tail, 3),
                "threshold": frozen_tail_threshold,
            }

    return {
        "sampled_frames": num_frames,
        "moving_seconds": round(
            sum(1 for d in diffs if d >= STILL_DIFF_THRESHOLD) * dt, 3
        ),
        "max_still_stretch": round(max_still_observed, 3),
        "still_stretches": long_still,
        "frozen_tail": frozen_tail,
    }


def _analyze_temporal_stutter(
    ffmpeg: str,
    video_path: Path,
    duration: float,
    fps: float | None,
) -> dict[str, Any]:
    """Detect frame-drop/duplicate-frame stutters and sudden single-frame motion jerks at native FPS."""
    sample_fps = min(24.0, max(12.0, float(fps))) if fps and fps > 0 else 24.0
    sample_dur = min(duration, 12.0)
    w, h = 160, 90
    frame_size = w * h
    proc = subprocess.run(
        [
            ffmpeg,
            "-v",
            "error",
            "-i",
            str(video_path),
            "-t",
            f"{sample_dur:.3f}",
            "-vf",
            f"fps={sample_fps:.3f},scale={w}:{h},format=gray",
            "-f",
            "rawvideo",
            "-pix_fmt",
            "gray",
            "-",
        ],
        capture_output=True,
        check=False,
    )
    if proc.returncode != 0 or len(proc.stdout) < frame_size * 4:
        return {
            "sampled_fps": round(sample_fps, 2),
            "sampled_frames": 0,
            "duplicate_frame_count": 0,
            "duplicate_frame_ratio": 0.0,
            "stutter_events": 0,
            "motion_jerk_spikes": 0,
        }

    raw = proc.stdout
    num_frames = len(raw) // frame_size
    diffs: list[float] = []
    for idx in range(num_frames - 1):
        a = raw[idx * frame_size : (idx + 1) * frame_size]
        b = raw[(idx + 1) * frame_size : (idx + 2) * frame_size]
        total = sum(abs(x - y) for x, y in zip(a, b))
        diffs.append(total / frame_size)

    moving_diffs = [d for d in diffs if d >= 0.35]
    moving_ratio = len(moving_diffs) / max(1, len(diffs))
    if moving_ratio < 0.35 or len(moving_diffs) < 4:
        return {
            "sampled_fps": round(sample_fps, 2),
            "sampled_frames": num_frames,
            "duplicate_frame_count": 0,
            "duplicate_frame_ratio": 0.0,
            "stutter_events": 0,
            "motion_jerk_spikes": 0,
        }

    dup_thresh = 0.12
    dup_flags = [d < dup_thresh for d in diffs]
    dup_count = sum(1 for f in dup_flags if f)
    dup_ratio = round(dup_count / len(diffs), 3)

    # Count mid-clip stutter bursts (>= 2 consecutive duplicate frames flanked by active motion)
    stutter_events = 0
    i = 0
    n = len(dup_flags)
    while i < n:
        if dup_flags[i]:
            j = i
            while j < n and dup_flags[j]:
                j += 1
            has_before = i > 0 and not dup_flags[i - 1]
            has_after = j < n and not dup_flags[j]
            if (j - i) >= 2 and has_before and has_after:
                stutter_events += 1
            i = j
        else:
            i += 1

    sorted_mov = sorted(moving_diffs)
    med = sorted_mov[len(sorted_mov) // 2]
    jerk_thresh = max(22.0, med * 4.5)
    jerk_spikes = sum(1 for d in diffs if d > jerk_thresh)

    return {
        "sampled_fps": round(sample_fps, 2),
        "sampled_frames": num_frames,
        "duplicate_frame_count": dup_count,
        "duplicate_frame_ratio": dup_ratio,
        "stutter_events": stutter_events,
        "motion_jerk_spikes": jerk_spikes,
    }


def _measure_boundary_luma(ffmpeg: str, video_path: Path, duration: float) -> tuple[float | None, float | None]:
    """Measure mean grayscale luma (0-255) on opening and closing frames for cut-jump detection."""
    w, h = 160, 90
    frame_size = w * h

    def _sample_at(ts: float) -> float | None:
        proc = subprocess.run(
            [
                ffmpeg,
                "-v",
                "error",
                "-ss",
                f"{max(0.0, ts):.3f}",
                "-i",
                str(video_path),
                "-frames:v",
                "1",
                "-vf",
                f"scale={w}:{h},format=gray",
                "-f",
                "rawvideo",
                "-pix_fmt",
                "gray",
                "-",
            ],
            capture_output=True,
            check=False,
        )
        if proc.returncode != 0 or len(proc.stdout) < frame_size:
            return None
        frame = proc.stdout[:frame_size]
        return round(sum(frame) / frame_size, 2)

    start_luma = _sample_at(min(0.05, duration * 0.1))
    end_luma = _sample_at(max(0.0, duration - 0.12))
    return start_luma, end_luma


def inspect_pixel_diff(
    processed_path: Path,
    plate_path: Path,
    *,
    active_windows: list[tuple[float, float]] | None = None,
    tolerance: float = 3.5,
    sample_fps: float = 2.0,
) -> dict[str, Any]:
    """Verify untouched pass-through frames outside active VFX windows match the source plate."""
    if not processed_path.is_file():
        raise FileNotFoundError(f"processed media not found: {processed_path}")
    if not plate_path.is_file():
        raise FileNotFoundError(f"source plate not found: {plate_path}")
    if not math.isfinite(tolerance) or tolerance < 0.0:
        raise ValueError("--tolerance must be >= 0")

    ffmpeg, ffprobe = _ensure_ffmpeg_tools()
    p_meta = _ffprobe_json(ffprobe, processed_path)
    s_meta = _ffprobe_json(ffprobe, plate_path)
    p_dur = _parse_finite_float((p_meta.get("format") or {}).get("duration")) or 0.0
    s_dur = _parse_finite_float((s_meta.get("format") or {}).get("duration")) or 0.0
    dur = min(p_dur, s_dur)
    if dur <= 0.0:
        raise RuntimeError("unable to determine overlapping video duration for pixel-diff")

    w, h = 160, 90
    frame_size = w * h * 3

    def _dump_rgb(path: Path) -> bytes:
        proc = subprocess.run(
            [
                ffmpeg,
                "-v",
                "error",
                "-i",
                str(path),
                "-t",
                f"{dur:.3f}",
                "-vf",
                f"fps={sample_fps:.3f},scale={w}:{h},format=rgb24",
                "-f",
                "rawvideo",
                "-pix_fmt",
                "rgb24",
                "-",
            ],
            capture_output=True,
            check=False,
        )
        if proc.returncode != 0:
            raise RuntimeError(f"ffmpeg failed reading {path}: {proc.stderr.decode(errors='ignore').strip()}")
        return proc.stdout

    raw_proc = _dump_rgb(processed_path)
    raw_plate = _dump_rgb(plate_path)
    n_frames = min(len(raw_proc), len(raw_plate)) // frame_size
    if n_frames == 0:
        raise RuntimeError("no overlapping frames extracted for pixel-diff")

    windows = active_windows or []
    dt = 1.0 / sample_fps
    passthrough_diffs: list[tuple[float, float]] = []
    active_diffs: list[tuple[float, float]] = []

    for idx in range(n_frames):
        ts = round(idx * dt, 3)
        a = raw_proc[idx * frame_size : (idx + 1) * frame_size]
        b = raw_plate[idx * frame_size : (idx + 1) * frame_size]
        mad = round(sum(abs(x - y) for x, y in zip(a, b)) / frame_size, 3)
        in_active = any(lo <= ts <= hi for lo, hi in windows)
        if in_active:
            active_diffs.append((ts, mad))
        else:
            passthrough_diffs.append((ts, mad))

    errors: list[dict[str, Any]] = []
    max_pt = max((d for _, d in passthrough_diffs), default=0.0)
    mean_pt = (
        round(sum(d for _, d in passthrough_diffs) / len(passthrough_diffs), 3)
        if passthrough_diffs
        else 0.0
    )
    violations = [{"time_s": ts, "mad": d} for ts, d in passthrough_diffs if d > tolerance]
    if violations:
        errors.append(
            {
                "code": "passthrough_drift",
                "message": (
                    f"{len(violations)} untouched pass-through frame(s) drifted from source plate "
                    f"(max MAD {max_pt} > tolerance {tolerance}; check AE/FFmpeg color management)"
                ),
                "max_mad": max_pt,
                "tolerance": tolerance,
                "sample_violations": violations[:5],
            }
        )

    return {
        "ok": len(errors) == 0,
        "command": "pixel-diff",
        "processed": str(processed_path),
        "plate": str(plate_path),
        "sampled_frames": n_frames,
        "passthrough_frames": len(passthrough_diffs),
        "active_frames": len(active_diffs),
        "mean_passthrough_mad": mean_pt,
        "max_passthrough_mad": max_pt,
        "tolerance": tolerance,
        "warnings": [],
        "errors": errors,
    }


def _extract_gray_frame(
    ffmpeg: str,
    video_path: Path,
    ts: float,
    width: int,
    height: int,
) -> bytes | None:
    expected = width * height
    candidates: list[float] = []
    for raw_ts in (ts, max(0.0, ts - 0.15), max(0.0, ts - 0.35)):
        rounded = round(raw_ts, 3)
        if rounded not in candidates:
            candidates.append(rounded)
    for attempt_ts in candidates:
        proc = subprocess.run(
            [
                ffmpeg,
                "-v",
                "error",
                "-ss",
                f"{attempt_ts:.3f}",
                "-i",
                str(video_path),
                "-frames:v",
                "1",
                "-vf",
                f"scale={width}:{height},format=gray",
                "-f",
                "rawvideo",
                "-pix_fmt",
                "gray",
                "-",
            ],
            capture_output=True,
            check=False,
        )
        if proc.returncode == 0 and len(proc.stdout) >= expected:
            return proc.stdout[:expected]
    return None


def _grid_tile_means(
    frame: bytes,
    width: int = LOCKED_STILL_W,
    height: int = LOCKED_STILL_H,
    grid: int = LOCKED_STILL_GRID,
) -> tuple[float, list[float]]:
    tile_w = width // grid
    tile_h = height // grid
    tile_count = tile_w * tile_h
    means: list[float] = []
    total_luma = 0
    for gy in range(grid):
        y0 = gy * tile_h
        y1 = y0 + tile_h
        for gx in range(grid):
            x0 = gx * tile_w
            x1 = x0 + tile_w
            tile_sum = 0
            for row in range(y0, y1):
                off = row * width
                tile_sum += sum(frame[off + x0 : off + x1])
            total_luma += tile_sum
            means.append(tile_sum / tile_count)
    return total_luma / (width * height), means


def _analyze_locked_still_drift(
    ffmpeg: str,
    video_path: Path,
    duration: float,
    drift_threshold: float,
) -> dict[str, Any]:
    """Compare opening anchor frame against 60%/80%/95% late frames on an 8x8 grayscale grid."""
    t_anchor = min(0.1, max(0.0, duration * 0.05))
    max_seek = max(0.0, duration - 0.05) if duration > 0.1 else 0.0
    late_specs = (
        (0.60, min(duration * 0.60, max_seek)),
        (0.80, min(duration * 0.80, max_seek)),
        (0.95, min(duration * 0.95, max_seek)),
    )

    anchor_raw = _extract_gray_frame(
        ffmpeg, video_path, t_anchor, LOCKED_STILL_W, LOCKED_STILL_H
    )
    if anchor_raw is None:
        raise RuntimeError(f"failed to extract locked-still anchor frame at {t_anchor:.3f}s")
    anchor_mean, anchor_tiles = _grid_tile_means(anchor_raw)

    max_tile_drift = 0.0
    mean_luma_shift = 0.0
    tail_drift = 0.0
    worst_tile: dict[str, Any] = {"row": 0, "col": 0, "time": round(t_anchor, 3)}
    sample_times: list[float] = []

    for frac, ts in late_specs:
        late_raw = _extract_gray_frame(
            ffmpeg, video_path, ts, LOCKED_STILL_W, LOCKED_STILL_H
        )
        if late_raw is None:
            raise RuntimeError(f"failed to extract locked-still late frame at {ts:.3f}s")
        sample_times.append(round(ts, 3))
        late_mean, late_tiles = _grid_tile_means(late_raw)
        luma_delta = abs(late_mean - anchor_mean)
        if luma_delta > mean_luma_shift:
            mean_luma_shift = luma_delta

        frame_max_tile = 0.0
        for idx, (m_late, m_anchor) in enumerate(zip(late_tiles, anchor_tiles)):
            delta = abs(m_late - m_anchor)
            if delta > frame_max_tile:
                frame_max_tile = delta
            if delta > max_tile_drift:
                max_tile_drift = delta
                worst_tile = {
                    "row": idx // LOCKED_STILL_GRID,
                    "col": idx % LOCKED_STILL_GRID,
                    "time": round(ts, 3),
                }
        if frac >= 0.65 and frame_max_tile > tail_drift:
            tail_drift = frame_max_tile

    passed = max_tile_drift <= drift_threshold
    return {
        "enabled": True,
        "grid": f"{LOCKED_STILL_GRID}x{LOCKED_STILL_GRID}",
        "anchor_time": round(t_anchor, 3),
        "sample_times": sample_times,
        "threshold": round(drift_threshold, 3),
        "mean_luma_shift": round(mean_luma_shift, 3),
        "max_tile_drift": round(max_tile_drift, 3),
        "tail_drift": round(tail_drift, 3),
        "worst_tile": worst_tile,
        "passed": passed,
    }


def _measure_volumedetect(ffmpeg: str, media_path: Path) -> dict[str, float | None]:
    proc = subprocess.run(
        [
            ffmpeg,
            "-v",
            "info",
            "-i",
            str(media_path),
            "-vn",
            "-af",
            "volumedetect",
            "-f",
            "null",
            "-",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    mean_m = re.search(r"mean_volume:\s*([-\d.]+)\s*dB", proc.stderr)
    max_m = re.search(r"max_volume:\s*([-\d.]+)\s*dB", proc.stderr)
    return {
        "mean_volume_db": _parse_finite_float(mean_m.group(1)) if mean_m else None,
        "max_volume_db": _parse_finite_float(max_m.group(1)) if max_m else None,
    }


def _measure_loudness(ffmpeg: str, media_path: Path) -> dict[str, float | None]:
    proc = subprocess.run(
        [
            ffmpeg,
            "-v",
            "info",
            "-i",
            str(media_path),
            "-vn",
            "-af",
            "loudnorm=I=-14:TP=-1:LRA=11:print_format=json",
            "-f",
            "null",
            "-",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    # Extract JSON block containing input_i from stderr
    matches = list(re.finditer(r"\{[^{}]*\"input_i\"[^{}]*\}", proc.stderr, re.DOTALL))
    if not matches:
        return {
            "integrated_lufs": None,
            "true_peak_dbtp": None,
            "lra": None,
            "threshold": None,
        }
    try:
        data = json.loads(matches[-1].group(0))
    except json.JSONDecodeError:
        return {
            "integrated_lufs": None,
            "true_peak_dbtp": None,
            "lra": None,
            "threshold": None,
        }
    return {
        "integrated_lufs": _parse_finite_float(data.get("input_i")),
        "true_peak_dbtp": _parse_finite_float(data.get("input_tp")),
        "lra": _parse_finite_float(data.get("input_lra")),
        "threshold": _parse_finite_float(data.get("input_thresh")),
    }


def _build_contact_sheet(
    ffmpeg: str, video_path: Path, duration: float, sheet_path: Path
) -> None:
    sheet_path.parent.mkdir(parents=True, exist_ok=True)
    t_start = min(0.2, max(0.0, duration * 0.1))
    t_end = max(t_start, duration - 0.2)
    if duration <= 0.4:
        t_start = 0.0
        t_end = max(0.0, duration - 0.02)

    timestamps = [
        t_start + (t_end - t_start) * (i / 5.0) for i in range(6)
    ]

    with tempfile.TemporaryDirectory(prefix="qa_sheet_") as tmp_dir:
        tmp = Path(tmp_dir)
        extracted: list[Path] = []
        for idx, ts in enumerate(timestamps):
            frame_out = tmp / f"f{idx}.png"
            proc = subprocess.run(
                [
                    ffmpeg,
                    "-v",
                    "error",
                    "-ss",
                    f"{ts:.3f}",
                    "-i",
                    str(video_path),
                    "-frames:v",
                    "1",
                    "-vf",
                    "scale=480:-2",
                    "-y",
                    str(frame_out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            if proc.returncode != 0 or not frame_out.is_file():
                # Retry slightly earlier if seek landed past final keyframe
                fallback_ts = max(0.0, ts - 0.15)
                proc2 = subprocess.run(
                    [
                        ffmpeg,
                        "-v",
                        "error",
                        "-ss",
                        f"{fallback_ts:.3f}",
                        "-i",
                        str(video_path),
                        "-frames:v",
                        "1",
                        "-vf",
                        "scale=480:-2",
                        "-y",
                        str(frame_out),
                    ],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                if proc2.returncode != 0 or not frame_out.is_file():
                    raise RuntimeError(
                        f"failed to extract contact sheet frame {idx} at {ts:.3f}s: "
                        f"{proc2.stderr.strip()}"
                    )
            extracted.append(frame_out)

        tile_proc = subprocess.run(
            [
                ffmpeg,
                "-v",
                "error",
                "-i",
                str(tmp / "f%d.png"),
                "-vf",
                "scale=480:-2,tile=3x2",
                "-frames:v",
                "1",
                "-y",
                str(sheet_path),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        if tile_proc.returncode != 0 or not sheet_path.is_file():
            raise RuntimeError(
                f"failed to tile 3x2 contact sheet: {tile_proc.stderr.strip()}"
            )


def _build_native_crop_strip(
    ffmpeg: str,
    video_path: Path,
    width: int,
    height: int,
    duration: float,
    crops_path: Path,
    *,
    crop_focus: str = "thirds",
) -> None:
    """Extract 3 unscaled 1:1 native-pixel crops (20%, 50%, 80%) for artifact/halo inspection."""
    crops_path.parent.mkdir(parents=True, exist_ok=True)
    crop_w = min(560, width)
    crop_h = min(560, height)
    crop_w -= crop_w % 2
    crop_h -= crop_h % 2
    crop_w = max(2, crop_w)
    crop_h = max(2, crop_h)
    span_x = max(0, width - crop_w)
    # Slightly upper-biased vertical crop aligns with faces/heads in standard 16:9 / 9:16 framing
    crop_y = max(0, int(round((height - crop_h) * 0.35)))

    if crop_focus == "left":
        x_offsets = [int(round(span_x * 0.18))] * 3
    elif crop_focus == "right":
        x_offsets = [int(round(span_x * 0.82))] * 3
    elif crop_focus == "center":
        x_offsets = [span_x // 2] * 3
    else:
        # Default "thirds" sweeps left-center, center, and right-center across 20%/50%/80%
        x_offsets = [
            int(round(span_x * 0.18)),
            span_x // 2,
            int(round(span_x * 0.82)),
        ]

    if duration <= 0.4:
        timestamps = [0.0, max(0.0, duration * 0.4), max(0.0, duration - 0.02)]
    else:
        timestamps = [duration * 0.20, duration * 0.50, duration * 0.80]

    with tempfile.TemporaryDirectory(prefix="qa_crops_") as tmp_dir:
        tmp = Path(tmp_dir)
        for idx, (ts, crop_x) in enumerate(zip(timestamps, x_offsets)):
            frame_out = tmp / f"c{idx}.png"
            crop_filter = f"crop={crop_w}:{crop_h}:{crop_x}:{crop_y}"
            proc = subprocess.run(
                [
                    ffmpeg,
                    "-v",
                    "error",
                    "-ss",
                    f"{ts:.3f}",
                    "-i",
                    str(video_path),
                    "-frames:v",
                    "1",
                    "-vf",
                    crop_filter,
                    "-y",
                    str(frame_out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            if proc.returncode != 0 or not frame_out.is_file():
                fallback_ts = max(0.0, ts - 0.15)
                proc2 = subprocess.run(
                    [
                        ffmpeg,
                        "-v",
                        "error",
                        "-ss",
                        f"{fallback_ts:.3f}",
                        "-i",
                        str(video_path),
                        "-frames:v",
                        "1",
                        "-vf",
                        crop_filter,
                        "-y",
                        str(frame_out),
                    ],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                if proc2.returncode != 0 or not frame_out.is_file():
                    raise RuntimeError(
                        f"failed to extract 1:1 crop frame {idx} at {ts:.3f}s: "
                        f"{proc2.stderr.strip()}"
                    )

        tile_proc = subprocess.run(
            [
                ffmpeg,
                "-v",
                "error",
                "-i",
                str(tmp / "c%d.png"),
                "-vf",
                "tile=3x1",
                "-frames:v",
                "1",
                "-y",
                str(crops_path),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        if tile_proc.returncode != 0 or not crops_path.is_file():
            raise RuntimeError(
                f"failed to tile 3x1 native crop strip: {tile_proc.stderr.strip()}"
            )


def _measure_hf_edge_energy(ffmpeg: str, video_path: Path, duration: float) -> float | None:
    """Measure mean 3x3 Laplacian edge energy across 3 sampled frames (sharpness/ringing proxy)."""
    if duration <= 0.4:
        timestamps = [0.0]
    else:
        timestamps = [duration * 0.25, duration * 0.50, duration * 0.75]
    samples: list[float] = []
    lap_vf = (
        "format=gray,"
        "convolution=0 -1 0 -1 4 -1 0 -1 0:0 -1 0 -1 4 -1 0 -1 0:"
        "0 -1 0 -1 4 -1 0 -1 0:0 -1 0 -1 4 -1 0 -1 0,"
        "signalstats,metadata=print:key=lavfi.signalstats.YAVG:file=-"
    )
    for ts in timestamps:
        proc = subprocess.run(
            [
                ffmpeg,
                "-v",
                "error",
                "-ss",
                f"{ts:.3f}",
                "-i",
                str(video_path),
                "-frames:v",
                "1",
                "-vf",
                lap_vf,
                "-f",
                "null",
                "-",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        if proc.returncode != 0:
            continue
        for m in re.finditer(r"YAVG=([0-9.]+)", proc.stdout):
            val = _parse_finite_float(m.group(1))
            if val is not None:
                samples.append(val)
    if not samples:
        return None
    return round(sum(samples) / len(samples), 3)


def inspect_clip(
    video_path: Path,
    *,
    sheet_path: Path | None = None,
    crops_path: Path | None = None,
    crop_focus: str = "thirds",
    max_still: float = 3.0,
    max_frozen_tail: float | None = None,
    black_min: float = 0.5,
    allow_silent: bool = False,
    strict: bool = False,
    locked_still: bool = False,
    drift_threshold: float = LOCKED_STILL_DRIFT_THRESHOLD,
) -> dict[str, Any]:
    if not math.isfinite(drift_threshold) or drift_threshold <= 0:
        raise ValueError("--drift-threshold must be a finite positive number")
    ffmpeg, ffprobe = _ensure_ffmpeg_tools()
    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []

    probe = _ffprobe_json(ffprobe, video_path)
    streams = probe.get("streams") or []
    fmt = probe.get("format") or {}

    vstream = next((s for s in streams if s.get("codec_type") == "video"), None)
    astream = next((s for s in streams if s.get("codec_type") == "audio"), None)

    duration = _parse_finite_float(fmt.get("duration"))
    if duration is None and vstream is not None:
        duration = _parse_finite_float(vstream.get("duration"))

    width = int(vstream["width"]) if vstream and vstream.get("width") else None
    height = int(vstream["height"]) if vstream and vstream.get("height") else None
    fps = None
    if vstream:
        fps = _parse_rational(vstream.get("avg_frame_rate")) or _parse_rational(
            vstream.get("r_frame_rate")
        )
    raw_vbr = _parse_finite_float(vstream.get("bit_rate")) if vstream else None
    if raw_vbr is None:
        raw_vbr = _parse_finite_float(fmt.get("bit_rate"))
    video_bitrate_kbps = round(raw_vbr / 1000.0, 1) if raw_vbr and raw_vbr > 0 else None

    metadata = {
        "duration": duration,
        "width": width,
        "height": height,
        "fps": fps,
        "video_codec": vstream.get("codec_name") if vstream else None,
        "video_bitrate_kbps": video_bitrate_kbps,
        "has_audio": astream is not None,
        "audio_codec": astream.get("codec_name") if astream else None,
        "sample_rate": int(astream["sample_rate"])
        if astream and astream.get("sample_rate")
        else None,
        "channels": int(astream["channels"])
        if astream and astream.get("channels")
        else None,
    }

    if vstream is None or not width or not height:
        errors.append({"code": "missing_video_stream", "message": "no valid video stream found"})
    if duration is None or duration <= 0:
        errors.append({"code": "invalid_duration", "message": f"invalid media duration: {duration}"})

    black_gaps: list[dict[str, float]] = []
    motion: dict[str, Any] = {}
    locked_still_check: dict[str, Any] = {"enabled": False}
    quality: dict[str, float | None] = {"hf_edge_energy": None}
    volume: dict[str, float | None] = {"mean_volume_db": None, "max_volume_db": None}
    loudness: dict[str, float | None] = {
        "integrated_lufs": None,
        "true_peak_dbtp": None,
        "lra": None,
        "threshold": None,
    }

    if vstream is not None and width and height and duration and duration > 0:
        max_dim = max(width, height)
        if width % 4 != 0 or height % 4 != 0:
            warnings.append(
                {
                    "code": "non_div4_dims",
                    "message": (
                        f"dimensions {width}x{height} are not divisible by 4 "
                        "(e.g. 1918x1080 upscale rounding or 854x480 draft; "
                        "incompatible with topaz_hyperion_2_5 and risks pillarbox padding)"
                    ),
                    "width": width,
                    "height": height,
                }
            )
        if max_dim >= 1200 and (width % 4 != 0 or height % 4 != 0):
            warnings.append(
                {
                    "code": "non_standard_dimensions",
                    "message": (
                        f"HD/master dimensions {width}x{height} are not divisible by 4 "
                        "(common upscale rounding artifact such as 1918x1080; triggers pillarbox padding and breaks Hyperion)"
                    ),
                    "width": width,
                    "height": height,
                }
            )
        if video_bitrate_kbps is not None:
            if max_dim >= 1900 and video_bitrate_kbps < 1800.0:
                warnings.append(
                    {
                        "code": "low_video_bitrate",
                        "message": (
                            f"1080p+ video bitrate is low ({video_bitrate_kbps} kbps < 1800 kbps); "
                            "prefer --bitrate_mode high on native 1080p masters"
                        ),
                        "video_bitrate_kbps": video_bitrate_kbps,
                        "threshold_kbps": 1800.0,
                    }
                )
            elif 640 <= max_dim < 1900 and video_bitrate_kbps < 900.0:
                warnings.append(
                    {
                        "code": "low_video_bitrate",
                        "message": (
                            f"video bitrate is low ({video_bitrate_kbps} kbps < 900 kbps); "
                            "compressed drafts this starved must never be pixel-upscaled"
                        ),
                        "video_bitrate_kbps": video_bitrate_kbps,
                        "threshold_kbps": 900.0,
                    }
                )

        quality["hf_edge_energy"] = _measure_hf_edge_energy(ffmpeg, video_path, duration)

        black_gaps = _detect_black_gaps(ffmpeg, video_path, black_min)
        for gap in black_gaps:
            errors.append(
                {
                    "code": "black_gap",
                    "message": (
                        f"black frame stretch detected: {gap['start']}s–{gap['end']}s "
                        f"({gap['duration']}s >= {black_min}s)"
                    ),
                    **gap,
                }
            )

        motion = _analyze_motion(
            ffmpeg,
            video_path,
            duration,
            max_still,
            max_frozen_tail=max_frozen_tail,
        )
        if not locked_still:
            if max_still < 60.0 and motion.get("moving_seconds", 0.0) == 0.0 and duration >= 1.5:
                errors.append(
                    {
                        "code": "fully_static_clip",
                        "message": (
                            f"clip is completely static across {duration}s (moving_seconds=0.0)"
                        ),
                        "duration": duration,
                        "moving_seconds": 0.0,
                    }
                )
            for st in motion.get("still_stretches") or []:
                entry = {
                    "code": "still_stretch",
                    "message": (
                        f"static frame stretch detected: {st['start']}s–{st['end']}s "
                        f"({st['duration']}s > {max_still}s)"
                    ),
                    **st,
                }
                if strict:
                    errors.append(entry)
                else:
                    warnings.append(entry)

            ft = motion.get("frozen_tail")
            if ft is not None:
                errors.append(
                    {
                        "code": "frozen_tail",
                        "message": (
                            f"frozen I2V tail detected: froze at {ft['start']}s–{ft['end']}s "
                            f"({ft['duration']}s) after {ft['moving_before_tail']}s of motion"
                        ),
                        **ft,
                    }
                )
        else:
            locked_still_check = _analyze_locked_still_drift(
                ffmpeg, video_path, duration, drift_threshold
            )
            if not locked_still_check["passed"]:
                wt = locked_still_check["worst_tile"]
                errors.append(
                    {
                        "code": "locked_still_drift",
                        "message": (
                            f"locked-still lighting/shadow drift detected: "
                            f"max_tile_drift={locked_still_check['max_tile_drift']} > "
                            f"{locked_still_check['threshold']} "
                            f"(mean_luma_shift={locked_still_check['mean_luma_shift']}, "
                            f"tail_drift={locked_still_check['tail_drift']}, "
                            f"worst tile r{wt['row']}c{wt['col']} at {wt['time']}s)"
                        ),
                        "max_tile_drift": locked_still_check["max_tile_drift"],
                        "mean_luma_shift": locked_still_check["mean_luma_shift"],
                        "tail_drift": locked_still_check["tail_drift"],
                        "threshold": locked_still_check["threshold"],
                        "worst_tile": wt,
                    }
                )

        if max_still < 60.0 and duration >= 1.5:
            temporal = _analyze_temporal_stutter(ffmpeg, video_path, duration, fps)
            motion["temporal"] = temporal
            if temporal["stutter_events"] >= 2 or temporal["duplicate_frame_ratio"] >= 0.18:
                warnings.append(
                    {
                        "code": "temporal_stutter",
                        "message": (
                            f"temporal stutter/duplicate frames detected "
                            f"(stutter_events={temporal['stutter_events']}, "
                            f"duplicate_frame_ratio={temporal['duplicate_frame_ratio']}) — "
                            "inspect actual MP4 playback for micro-freezes/judder"
                        ),
                        **temporal,
                    }
                )
            if duration <= 12.0 and temporal["motion_jerk_spikes"] >= 2:
                warnings.append(
                    {
                        "code": "motion_jerk",
                        "message": (
                            f"sudden motion jerk spikes detected "
                            f"(motion_jerk_spikes={temporal['motion_jerk_spikes']}) — "
                            "inspect actual MP4 playback for teleporting objects or glitches"
                        ),
                        **temporal,
                    }
                )

        if sheet_path is not None:
            _build_contact_sheet(ffmpeg, video_path, duration, sheet_path)
        if crops_path is not None:
            _build_native_crop_strip(
                ffmpeg,
                video_path,
                width,
                height,
                duration,
                crops_path,
                crop_focus=crop_focus,
            )

    if astream is None:
        if not allow_silent:
            errors.append(
                {"code": "silent_audio", "message": "missing audio stream (pass --allow-silent to permit)"}
            )
    else:
        volume = _measure_volumedetect(ffmpeg, video_path)
        loudness = _measure_loudness(ffmpeg, video_path)
        mean_db = volume["mean_volume_db"]
        if (mean_db is None or mean_db < SILENT_MEAN_DB_THRESHOLD) and not allow_silent:
            errors.append(
                {
                    "code": "silent_audio",
                    "message": (
                        f"audio track is silent (mean_volume={mean_db} dB < "
                        f"{SILENT_MEAN_DB_THRESHOLD} dB)"
                    ),
                    "mean_volume_db": mean_db,
                }
            )

    return {
        "ok": len(errors) == 0,
        "command": "clip",
        "path": str(video_path),
        "sheet": str(sheet_path) if sheet_path else None,
        "crops": str(crops_path) if crops_path else None,
        "metadata": metadata,
        "quality": quality,
        "black_gaps": black_gaps,
        "motion": motion,
        "locked_still_check": locked_still_check,
        "volume": volume,
        "loudness": loudness,
        "warnings": warnings,
        "errors": errors,
    }


def _build_verify_slices(
    ffmpeg: str,
    video_path: Path,
    duration: float,
    out_dir: Path,
    slice_seconds: float = 20.0,
) -> list[str]:
    """Stream-copy long masters into <= slice_seconds chunks for fast reviewer-agent MP4 playback."""
    if not math.isfinite(slice_seconds) or slice_seconds <= 0.0:
        raise ValueError("--slice-seconds must be a positive number")
    out_dir.mkdir(parents=True, exist_ok=True)
    for old in out_dir.glob("part_*.mp4"):
        old.unlink(missing_ok=True)
    if duration <= slice_seconds + 0.5:
        return [str(video_path)]
    pattern = str(out_dir / "part_%02d.mp4")
    proc = subprocess.run(
        [
            ffmpeg,
            "-v",
            "error",
            "-y",
            "-i",
            str(video_path),
            "-c",
            "copy",
            "-map",
            "0",
            "-f",
            "segment",
            "-segment_time",
            f"{slice_seconds:g}",
            "-reset_timestamps",
            "1",
            pattern,
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"failed to create verify slices: {proc.stderr.strip()}")
    slices = sorted(out_dir.glob("part_*.mp4"))
    return [str(p) for p in slices] if slices else [str(video_path)]


def inspect_render(
    video_path: Path,
    *,
    sheet_path: Path | None = None,
    crops_path: Path | None = None,
    crop_focus: str = "thirds",
    verify_slices_dir: Path | None = None,
    slice_seconds: float = 20.0,
    target_lufs: float = -14.0,
    lufs_tolerance: float = 1.0,
    max_true_peak: float = -1.0,
    max_still: float = 3.0,
    max_frozen_tail: float | None = None,
    black_min: float = 0.5,
    allow_silent: bool = False,
    skip_loudness_check: bool = False,
    strict: bool = False,
) -> dict[str, Any]:
    report = inspect_clip(
        video_path,
        sheet_path=sheet_path,
        crops_path=crops_path,
        crop_focus=crop_focus,
        max_still=max_still,
        max_frozen_tail=max_frozen_tail,
        black_min=black_min,
        allow_silent=allow_silent,
        strict=strict,
    )
    report["command"] = "render"

    duration = report["metadata"].get("duration") or 0.0
    loudness = report["loudness"]
    errors: list[dict[str, Any]] = report["errors"]

    if verify_slices_dir is not None and duration > 0.0:
        ffmpeg, _ = _ensure_ffmpeg_tools()
        report["verify_slices"] = _build_verify_slices(
            ffmpeg, video_path, float(duration), verify_slices_dir, slice_seconds=slice_seconds
        )
    else:
        report["verify_slices"] = None

    if (
        not allow_silent
        and not skip_loudness_check
        and duration >= 3.0
        and report["metadata"].get("has_audio")
    ):
        lufs = loudness.get("integrated_lufs")
        tp = loudness.get("true_peak_dbtp")
        low = target_lufs - lufs_tolerance
        high = target_lufs + lufs_tolerance
        if lufs is None or not (low <= lufs <= high):
            errors.append(
                {
                    "code": "loudness_out_of_range",
                    "message": (
                        f"integrated loudness {lufs} LUFS outside allowed range "
                        f"[{low:.1f}, {high:.1f}] LUFS"
                    ),
                    "integrated_lufs": lufs,
                    "target_lufs": target_lufs,
                    "tolerance": lufs_tolerance,
                }
            )
        if tp is None or tp > max_true_peak:
            errors.append(
                {
                    "code": "true_peak_exceeded",
                    "message": (
                        f"true peak {tp} dBTP exceeds limit {max_true_peak:.1f} dBTP"
                    ),
                    "true_peak_dbtp": tp,
                    "max_true_peak": max_true_peak,
                }
            )

    report["ok"] = len(errors) == 0
    return report


def inspect_batch(
    video_paths: list[Path],
    *,
    max_hf_ratio: float = 1.5,
    strict: bool = False,
) -> dict[str, Any]:
    """Audit cross-shot consistency (resolution, FPS, bitrate, HF edge energy) across a cut."""
    if not video_paths:
        raise ValueError("at least one video path is required")
    if not math.isfinite(max_hf_ratio) or max_hf_ratio <= 1.0:
        raise ValueError("--max-hf-ratio must be > 1.0")

    ffmpeg, ffprobe = _ensure_ffmpeg_tools()
    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    clips: list[dict[str, Any]] = []

    for vpath in video_paths:
        if not vpath.is_file():
            raise FileNotFoundError(f"media file not found: {vpath}")
        probe = _ffprobe_json(ffprobe, vpath)
        streams = probe.get("streams") or []
        fmt = probe.get("format") or {}
        vstream = next((s for s in streams if s.get("codec_type") == "video"), None)
        duration = _parse_finite_float(fmt.get("duration"))
        if duration is None and vstream is not None:
            duration = _parse_finite_float(vstream.get("duration"))
        width = int(vstream["width"]) if vstream and vstream.get("width") else None
        height = int(vstream["height"]) if vstream and vstream.get("height") else None
        fps = (
            (_parse_rational(vstream.get("avg_frame_rate")) or _parse_rational(vstream.get("r_frame_rate")))
            if vstream
            else None
        )
        raw_vbr = _parse_finite_float(vstream.get("bit_rate")) if vstream else None
        if raw_vbr is None:
            raw_vbr = _parse_finite_float(fmt.get("bit_rate"))
        vbr_kbps = round(raw_vbr / 1000.0, 1) if raw_vbr and raw_vbr > 0 else None
        hf = (
            _measure_hf_edge_energy(ffmpeg, vpath, duration)
            if vstream and duration and duration > 0
            else None
        )
        start_luma, end_luma = (
            _measure_boundary_luma(ffmpeg, vpath, duration)
            if vstream and duration and duration > 0
            else (None, None)
        )
        clips.append(
            {
                "path": str(vpath),
                "width": width,
                "height": height,
                "fps": fps,
                "duration": duration,
                "video_bitrate_kbps": vbr_kbps,
                "hf_edge_energy": hf,
                "start_luma": start_luma,
                "end_luma": end_luma,
            }
        )
        if not width or not height:
            errors.append(
                {"code": "missing_video_stream", "path": str(vpath), "message": f"{vpath}: missing video stream"}
            )
        elif width % 4 != 0 or height % 4 != 0:
            warnings.append(
                {
                    "code": "non_div4_dims",
                    "path": str(vpath),
                    "width": width,
                    "height": height,
                    "message": (
                        f"{vpath}: dimensions {width}x{height} are not divisible by 4 "
                        "(e.g. 1918x1080 upscale rounding or 854x480 draft; "
                        "incompatible with topaz_hyperion_2_5 and risks pillarbox padding)"
                    ),
                }
            )
            if max(width, height) >= 1200:
                errors.append(
                    {
                        "code": "non_standard_dimensions",
                        "path": str(vpath),
                        "width": width,
                        "height": height,
                        "message": (
                            f"{vpath}: HD dimensions {width}x{height} are not divisible by 4 "
                            "(upscale rounding artifact such as 1918x1080 or 1278x720)"
                        ),
                    }
                )
        if width and height and max(width, height) >= 1900 and vbr_kbps is not None and vbr_kbps < 1800.0:
            warnings.append(
                {
                    "code": "low_video_bitrate",
                    "path": str(vpath),
                    "video_bitrate_kbps": vbr_kbps,
                    "threshold_kbps": 1800.0,
                    "message": (
                        f"{vpath}: 1080p+ video bitrate is low ({vbr_kbps} kbps < 1800 kbps); "
                        "prefer --bitrate_mode high on native 1080p masters"
                    ),
                }
            )

    # Modal resolution (preferring valid multiple-of-4 dimensions so upscale rounding flags outliers) and FPS
    dims_list = [(c["width"], c["height"]) for c in clips if c["width"] and c["height"]]
    valid_dims = [d for d in dims_list if d[0] % 4 == 0 and d[1] % 4 == 0]
    fps_list = [round(float(c["fps"]), 2) for c in clips if c["fps"] is not None]
    hf_vals = sorted(float(c["hf_edge_energy"]) for c in clips if c["hf_edge_energy"] is not None)
    clean_hf_vals = sorted(
        float(c["hf_edge_energy"])
        for c in clips
        if c["hf_edge_energy"] is not None
        and c["width"]
        and c["height"]
        and c["width"] % 4 == 0
        and c["height"] % 4 == 0
    )

    dim_pool = valid_dims if valid_dims else dims_list
    modal_dims = max(set(dim_pool), key=dim_pool.count) if dim_pool else None
    modal_fps = max(set(fps_list), key=fps_list.count) if fps_list else None

    def _median(vals: list[float]) -> float | None:
        if not vals:
            return None
        mid = len(vals) // 2
        return vals[mid] if len(vals) % 2 == 1 else round((vals[mid - 1] + vals[mid]) / 2.0, 3)

    median_hf = _median(hf_vals)
    # Anchor HF sharpness baseline to median of valid mod-4 clips so upscale batches don't skew baseline up
    # and a single dark/bokeh native shot doesn't false-flag crisp detailed native shots.
    baseline_hf = _median(clean_hf_vals) if clean_hf_vals else median_hf

    for c in clips:
        if modal_dims and c["width"] and c["height"] and (c["width"], c["height"]) != modal_dims:
            entry = {
                "code": "resolution_mismatch",
                "path": c["path"],
                "got": f"{c['width']}x{c['height']}",
                "expected": f"{modal_dims[0]}x{modal_dims[1]}",
                "message": (
                    f"{c['path']}: resolution {c['width']}x{c['height']} differs from "
                    f"cut baseline {modal_dims[0]}x{modal_dims[1]}"
                ),
            }
            errors.append(entry)
        if modal_fps is not None and c["fps"] is not None and abs(float(c["fps"]) - modal_fps) > 0.25:
            entry = {
                "code": "fps_mismatch",
                "path": c["path"],
                "got": c["fps"],
                "expected": modal_fps,
                "message": (
                    f"{c['path']}: native FPS {c['fps']} differs from cut baseline {modal_fps} "
                    "(risk of pulldown judder)"
                ),
            }
            if strict:
                errors.append(entry)
            else:
                warnings.append(entry)
        if baseline_hf and baseline_hf > 0 and c["hf_edge_energy"] is not None:
            ratio = round(float(c["hf_edge_energy"]) / baseline_hf, 2)
            c["hf_ratio_to_baseline"] = ratio
            if ratio > max_hf_ratio:
                warnings.append(
                    {
                        "code": "hf_sharpness_outlier",
                        "path": c["path"],
                        "hf_edge_energy": c["hf_edge_energy"],
                        "baseline_hf": round(baseline_hf, 3),
                        "ratio": ratio,
                        "max_hf_ratio": max_hf_ratio,
                        "message": (
                            f"{c['path']}: hf_edge_energy={c['hf_edge_energy']} is {ratio}x clean median "
                            f"({round(baseline_hf, 3)}, limit {max_hf_ratio}x) — inspect 1:1 --crops to confirm "
                            "genuine scene texture vs. upscale halos/oversharpening"
                        ),
                    }
                )

    # Cross-cut exposure/luma jump & bitrate disparity checks
    for idx in range(len(clips) - 1):
        el = clips[idx].get("end_luma")
        sl = clips[idx + 1].get("start_luma")
        if el is not None and sl is not None and abs(float(el) - float(sl)) > 95.0:
            warnings.append(
                {
                    "code": "inter_shot_luma_jump",
                    "from_path": clips[idx]["path"],
                    "to_path": clips[idx + 1]["path"],
                    "end_luma": el,
                    "start_luma": sl,
                    "delta": round(abs(float(el) - float(sl)), 2),
                    "message": (
                        f"cut {idx + 1}->{idx + 2} ({Path(clips[idx]['path']).name} -> "
                        f"{Path(clips[idx + 1]['path']).name}): harsh exposure/luma jump "
                        f"({el} -> {sl}, delta={round(abs(float(el) - float(sl)), 1)} > 95); "
                        "add a visual bridge or per-shot pre-LUT grade match"
                    ),
                }
            )
    vbr_vals = [float(c["video_bitrate_kbps"]) for c in clips if c.get("video_bitrate_kbps") and float(c["video_bitrate_kbps"]) > 0]
    if len(vbr_vals) >= 2:
        min_vbr, max_vbr = min(vbr_vals), max(vbr_vals)
        if min_vbr > 0 and (max_vbr / min_vbr) > 4.0:
            warnings.append(
                {
                    "code": "bitrate_disparity",
                    "min_kbps": round(min_vbr, 1),
                    "max_kbps": round(max_vbr, 1),
                    "ratio": round(max_vbr / min_vbr, 2),
                    "message": (
                        f"severe cross-shot bitrate disparity ({round(min_vbr, 1)} kbps vs "
                        f"{round(max_vbr, 1)} kbps = {round(max_vbr / min_vbr, 1)}x > 4.0x); "
                        "avoid mixing starved low-bitrate drafts next to flagship masters"
                    ),
                }
            )

    return {
        "ok": len(errors) == 0,
        "command": "batch",
        "clip_count": len(clips),
        "baseline": {
            "resolution": f"{modal_dims[0]}x{modal_dims[1]}" if modal_dims else None,
            "fps": modal_fps,
            "median_hf_edge_energy": round(median_hf, 3) if median_hf is not None else None,
            "clean_median_hf_edge_energy": round(baseline_hf, 3) if baseline_hf is not None else None,
            "max_hf_ratio": max_hf_ratio,
        },
        "clips": clips,
        "warnings": warnings,
        "errors": errors,
    }


def inspect_voice(
    audio_path: Path,
    *,
    window: float,
    min_margin_low: float = 2.0,
    min_margin_high: float = 0.2,
) -> dict[str, Any]:
    ffmpeg, ffprobe = _ensure_ffmpeg_tools()
    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []

    probe = _ffprobe_json(ffprobe, audio_path)
    streams = probe.get("streams") or []
    fmt = probe.get("format") or {}
    astream = next((s for s in streams if s.get("codec_type") == "audio"), None)

    duration = _parse_finite_float(fmt.get("duration"))
    if duration is None and astream is not None:
        duration = _parse_finite_float(astream.get("duration"))

    metadata = {
        "duration": duration,
        "audio_codec": astream.get("codec_name") if astream else None,
        "sample_rate": int(astream["sample_rate"])
        if astream and astream.get("sample_rate")
        else None,
        "channels": int(astream["channels"])
        if astream and astream.get("channels")
        else None,
    }

    if astream is None:
        errors.append({"code": "missing_audio_stream", "message": "no readable audio stream found"})
        return {
            "ok": False,
            "command": "voice",
            "path": str(audio_path),
            "metadata": metadata,
            "window": window,
            "speech_end": None,
            "loudness": None,
            "warnings": warnings,
            "errors": errors,
        }

    proc = subprocess.run(
        [
            ffmpeg,
            "-v",
            "error",
            "-i",
            str(audio_path),
            "-af",
            (
                "aformat=channel_layouts=mono,aresample=16000,"
                "asetnsamples=n=1600:p=0,astats=metadata=1:reset=1,"
                "ametadata=mode=print:key=lavfi.astats.Overall.RMS_level:file=-"
            ),
            "-f",
            "null",
            "-",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"voice RMS analysis failed: {proc.stderr.strip()}")

    first_active_start: float | None = None
    last_active_end: float | None = None
    current_pts_time: float | None = None
    bins_analyzed = 0

    for line in proc.stdout.splitlines():
        pts_m = re.search(r"pts_time:([0-9.]+)", line)
        if pts_m:
            current_pts_time = float(pts_m.group(1))
            continue
        rms_m = re.match(r"lavfi\.astats\.Overall\.RMS_level=(.+)$", line.strip())
        if rms_m and current_pts_time is not None:
            bins_analyzed += 1
            rms_val = _parse_finite_float(rms_m.group(1))
            if rms_val is not None and rms_val > VOICE_RMS_ACTIVE_DB:
                if first_active_start is None:
                    first_active_start = round(current_pts_time, 3)
                last_active_end = round(current_pts_time + 0.1, 3)

    speech_start = first_active_start if first_active_start is not None else 0.0
    speech_end = last_active_end if last_active_end is not None else 0.0
    min_allowed = round(window - min_margin_low, 3)
    max_allowed = round(window - min_margin_high, 3)

    # Detect internal speech pauses >= 0.35s for dialogue cadence diagnostics
    internal_pauses: list[dict[str, float]] = []
    if first_active_start is not None and last_active_end is not None:
        sil_proc = subprocess.run(
            [
                ffmpeg,
                "-v",
                "info",
                "-i",
                str(audio_path),
                "-vn",
                "-af",
                "silencedetect=noise=-38dB:d=0.35",
                "-f",
                "null",
                "-",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        cur_sil_start: float | None = None
        for line in sil_proc.stderr.splitlines():
            m_st = re.search(r"silence_start:\s*([0-9.]+)", line)
            if m_st:
                cur_sil_start = float(m_st.group(1))
                continue
            m_end = re.search(r"silence_end:\s*([0-9.]+)\s*\|\s*silence_duration:\s*([0-9.]+)", line)
            if m_end:
                s_end = float(m_end.group(1))
                s_dur = float(m_end.group(2))
                s_start = cur_sil_start if cur_sil_start is not None else max(0.0, s_end - s_dur)
                cur_sil_start = None
                if s_start > (speech_start + 0.05) and s_end < (speech_end - 0.05):
                    internal_pauses.append(
                        {
                            "start": round(s_start, 3),
                            "end": round(s_end, 3),
                            "duration": round(s_dur, 3),
                        }
                    )
        if speech_start >= 0.25:
            warnings.append(
                {
                    "code": "leading_silence",
                    "speech_start": speech_start,
                    "message": (
                        f"leading silence before speech ({speech_start}s >= 0.25s); "
                        "set audio.voiceover.tracks[].trim_start_s or tighten start_s to avoid dead air at cut"
                    ),
                }
            )
        long_pauses = [p for p in internal_pauses if p["duration"] >= 0.45]
        if long_pauses:
            max_p = max(p["duration"] for p in long_pauses)
            warnings.append(
                {
                    "code": "long_internal_pause",
                    "max_pause_s": max_p,
                    "count": len(long_pauses),
                    "pauses": long_pauses,
                    "message": (
                        f"{len(long_pauses)} internal TTS pause(s) >= 0.45s (max {max_p}s); "
                        "for tight Shorts/dialogue cadence, tighten punctuation/script or ensure speaker turn gaps stay crisp"
                    ),
                }
            )

    if last_active_end is None:
        errors.append(
            {
                "code": "no_speech_detected",
                "message": f"no 100ms audio bin exceeded {VOICE_RMS_ACTIVE_DB} dBFS",
            }
        )
    elif speech_end < min_allowed:
        errors.append(
            {
                "code": "voice_too_short",
                "message": (
                    f"speech ends at {speech_end}s, shorter than minimum "
                    f"{min_allowed}s (window={window}s - {min_margin_low}s)"
                ),
                "speech_end": speech_end,
                "min_allowed": min_allowed,
            }
        )
    elif speech_end > max_allowed:
        errors.append(
            {
                "code": "voice_too_long",
                "message": (
                    f"speech ends at {speech_end}s, longer than maximum "
                    f"{max_allowed}s (window={window}s - {min_margin_high}s)"
                ),
                "speech_end": speech_end,
                "max_allowed": max_allowed,
            }
        )

    loudness = _measure_loudness(ffmpeg, audio_path)

    return {
        "ok": len(errors) == 0,
        "command": "voice",
        "path": str(audio_path),
        "metadata": metadata,
        "window": window,
        "min_allowed": min_allowed,
        "max_allowed": max_allowed,
        "speech_start": speech_start,
        "speech_end": speech_end,
        "internal_pauses": internal_pauses,
        "bins_analyzed": bins_analyzed,
        "loudness": loudness,
        "warnings": warnings,
        "errors": errors,
    }


# Compact 5x7 uppercase pixel bitmap font (each int is a 5-bit row, MSB = left pixel).
_FONT_5X7: dict[str, tuple[int, ...]] = {
    "A": (0b01110, 0b10001, 0b10001, 0b11111, 0b10001, 0b10001, 0b10001),
    "B": (0b11110, 0b10001, 0b10001, 0b11110, 0b10001, 0b10001, 0b11110),
    "C": (0b01110, 0b10001, 0b10000, 0b10000, 0b10000, 0b10001, 0b01110),
    "D": (0b11100, 0b10010, 0b10001, 0b10001, 0b10001, 0b10010, 0b11100),
    "E": (0b11111, 0b10000, 0b10000, 0b11110, 0b10000, 0b10000, 0b11111),
    "F": (0b11111, 0b10000, 0b10000, 0b11110, 0b10000, 0b10000, 0b10000),
    "G": (0b01110, 0b10001, 0b10000, 0b10111, 0b10001, 0b10001, 0b01110),
    "H": (0b10001, 0b10001, 0b10001, 0b11111, 0b10001, 0b10001, 0b10001),
    "I": (0b01110, 0b00100, 0b00100, 0b00100, 0b00100, 0b00100, 0b01110),
    "J": (0b00111, 0b00010, 0b00010, 0b00010, 0b10010, 0b10010, 0b01100),
    "K": (0b10001, 0b10010, 0b10100, 0b11000, 0b10100, 0b10010, 0b10001),
    "L": (0b10000, 0b10000, 0b10000, 0b10000, 0b10000, 0b10000, 0b11111),
    "M": (0b10001, 0b11011, 0b10101, 0b10101, 0b10001, 0b10001, 0b10001),
    "N": (0b10001, 0b11001, 0b10101, 0b10011, 0b10001, 0b10001, 0b10001),
    "O": (0b01110, 0b10001, 0b10001, 0b10001, 0b10001, 0b10001, 0b01110),
    "P": (0b11110, 0b10001, 0b10001, 0b11110, 0b10000, 0b10000, 0b10000),
    "Q": (0b01110, 0b10001, 0b10001, 0b10001, 0b10101, 0b10010, 0b01101),
    "R": (0b11110, 0b10001, 0b10001, 0b11110, 0b10100, 0b10010, 0b10001),
    "S": (0b01111, 0b10000, 0b10000, 0b01110, 0b00001, 0b00001, 0b11110),
    "T": (0b11111, 0b00100, 0b00100, 0b00100, 0b00100, 0b00100, 0b00100),
    "U": (0b10001, 0b10001, 0b10001, 0b10001, 0b10001, 0b10001, 0b01110),
    "V": (0b10001, 0b10001, 0b10001, 0b10001, 0b10001, 0b01010, 0b00100),
    "W": (0b10001, 0b10001, 0b10001, 0b10101, 0b10101, 0b11011, 0b10001),
    "X": (0b10001, 0b10001, 0b01010, 0b00100, 0b01010, 0b10001, 0b10001),
    "Y": (0b10001, 0b10001, 0b01010, 0b00100, 0b00100, 0b00100, 0b00100),
    "Z": (0b11111, 0b00001, 0b00010, 0b00100, 0b01000, 0b10000, 0b11111),
    "0": (0b01110, 0b10001, 0b10011, 0b10101, 0b11001, 0b10001, 0b01110),
    "1": (0b00100, 0b01100, 0b00100, 0b00100, 0b00100, 0b00100, 0b01110),
    "2": (0b01110, 0b10001, 0b00001, 0b00110, 0b01000, 0b10000, 0b11111),
    "3": (0b11110, 0b00001, 0b00001, 0b01110, 0b00001, 0b00001, 0b11110),
    "4": (0b00010, 0b00110, 0b01010, 0b10010, 0b11111, 0b00010, 0b00010),
    "5": (0b11111, 0b10000, 0b11110, 0b00001, 0b00001, 0b10001, 0b01110),
    "6": (0b01110, 0b10000, 0b11110, 0b10001, 0b10001, 0b10001, 0b01110),
    "7": (0b11111, 0b00001, 0b00010, 0b00100, 0b01000, 0b01000, 0b01000),
    "8": (0b01110, 0b10001, 0b10001, 0b01110, 0b10001, 0b10001, 0b01110),
    "9": (0b01110, 0b10001, 0b10001, 0b01111, 0b00001, 0b00001, 0b01110),
    "-": (0b00000, 0b00000, 0b00000, 0b11111, 0b00000, 0b00000, 0b00000),
    "_": (0b00000, 0b00000, 0b00000, 0b00000, 0b00000, 0b00000, 0b11111),
    ".": (0b00000, 0b00000, 0b00000, 0b00000, 0b00000, 0b01100, 0b01100),
    "/": (0b00001, 0b00010, 0b00010, 0b00100, 0b01000, 0b01000, 0b10000),
    ":": (0b00000, 0b01100, 0b01100, 0b00000, 0b01100, 0b01100, 0b00000),
    "+": (0b00000, 0b00100, 0b00100, 0b11111, 0b00100, 0b00100, 0b00000),
    " ": (0b00000, 0b00000, 0b00000, 0b00000, 0b00000, 0b00000, 0b00000),
    "?": (0b01110, 0b10001, 0b00010, 0b00100, 0b00100, 0b00000, 0b00100),
}


def _png_chunk(tag: bytes, data: bytes) -> bytes:
    crc = zlib.crc32(tag + data) & 0xFFFFFFFF
    return struct.pack("!I", len(data)) + tag + data + struct.pack("!I", crc)


def _write_rgba_png(path: Path, width: int, height: int, rgba: bytearray) -> None:
    """Encode an 8-bit RGBA pixel buffer to a PNG file using stdlib zlib + struct only."""
    row_stride = width * 4
    raw = bytearray()
    for y in range(height):
        raw.append(0)  # Filter type 0 (None)
        start = y * row_stride
        raw.extend(rgba[start : start + row_stride])
    ihdr = struct.pack("!IIBBBBB", width, height, 8, 6, 0, 0, 0)
    png_bytes = (
        b"\x89PNG\r\n\x1a\n"
        + _png_chunk(b"IHDR", ihdr)
        + _png_chunk(b"IDAT", zlib.compress(bytes(raw), level=6))
        + _png_chunk(b"IEND", b"")
    )
    path.write_bytes(png_bytes)


def _render_badge_png(label: str, path: Path, *, max_width: int) -> None:
    """Render a high-contrast dark translucent pill badge with crisp white bitmap text."""
    text = label.upper()
    scale = 4
    pad_x = 12
    pad_y = 8
    while scale > 1:
        text_w = len(text) * (5 * scale) + max(0, len(text) - 1) * scale
        if text_w + 2 * pad_x <= max_width:
            break
        scale -= 1
    if scale < 4:
        pad_x = max(6, pad_x // 2)
        pad_y = max(4, pad_y // 2)

    glyph_w = 5 * scale
    glyph_h = 7 * scale
    gap = scale
    text_w = len(text) * glyph_w + max(0, len(text) - 1) * gap
    width = max(16, text_w + 2 * pad_x)
    height = max(16, glyph_h + 2 * pad_y)

    rgba = bytearray(width * height * 4)
    bg = (11, 11, 14, 215)
    border = (232, 236, 244, 235)
    fg = (255, 255, 255, 255)
    border_px = 2

    def _set_px(px: int, py: int, color: tuple[int, int, int, int]) -> None:
        if 0 <= px < width and 0 <= py < height:
            off = (py * width + px) * 4
            rgba[off : off + 4] = bytes(color)

    # Fill dark translucent pill with 2px light border and softly clipped 2px corners
    for y in range(height):
        for x in range(width):
            in_corner = (
                (x < 2 and y < 2)
                or (x >= width - 2 and y < 2)
                or (x < 2 and y >= height - 2)
                or (x >= width - 2 and y >= height - 2)
            )
            if in_corner:
                continue
            is_edge = (
                x < border_px
                or x >= width - border_px
                or y < border_px
                or y >= height - border_px
            )
            _set_px(x, y, border if is_edge else bg)

    # Render each 5x7 glyph scaled cleanly
    cursor_x = pad_x
    for ch in text:
        glyph = _FONT_5X7.get(ch, _FONT_5X7["?"])
        for row_idx, bits in enumerate(glyph):
            for col_idx in range(5):
                if bits & (1 << (4 - col_idx)):
                    base_x = cursor_x + col_idx * scale
                    base_y = pad_y + row_idx * scale
                    for dy in range(scale):
                        for dx in range(scale):
                            _set_px(base_x + dx, base_y + dy, fg)
        cursor_x += glyph_w + gap

    _write_rgba_png(path, width, height, rgba)


def _default_lookbook_label(index: int) -> str:
    return chr(ord("A") + index) if index < 26 else f"V{index + 1}"


def build_lookbook(
    image_paths: list[Path],
    *,
    out_path: Path,
    labels: list[str] | None = None,
    cols: int | None = None,
    tile_width: int = 480,
) -> dict[str, Any]:
    """Stitch 1+ images into a labeled dark-slate A/B/C Lookbook or Stills Strip PNG."""
    if not image_paths:
        raise ValueError("at least one image path is required")
    if tile_width <= 0:
        raise ValueError("--tile-width must be a positive integer")
    if cols is not None and cols <= 0:
        raise ValueError("--cols must be a positive integer")

    if labels is None:
        resolved_labels = [_default_lookbook_label(idx) for idx in range(len(image_paths))]
    else:
        cleaned = [lbl.strip() for lbl in labels]
        if len(cleaned) != len(image_paths):
            raise ValueError(
                f"--labels count ({len(cleaned)}) must match image count ({len(image_paths)})"
            )
        if any(not lbl for lbl in cleaned):
            raise ValueError("--labels must not contain empty labels")
        if len(set(cleaned)) != len(cleaned):
            raise ValueError(f"--labels must not contain duplicate labels: {cleaned}")
        resolved_labels = cleaned

    ffmpeg, ffprobe = _ensure_ffmpeg_tools()

    first_dims: tuple[int, int] | None = None
    for img in image_paths:
        if not img.is_file():
            raise FileNotFoundError(f"image file not found: {img}")
        probe = _ffprobe_json(ffprobe, img)
        streams = probe.get("streams") or []
        vstream = next((s for s in streams if s.get("codec_type") == "video"), None)
        w = int(vstream["width"]) if vstream and vstream.get("width") else 0
        h = int(vstream["height"]) if vstream and vstream.get("height") else 0
        if vstream is None or w <= 0 or h <= 0:
            raise RuntimeError(f"unreadable image '{img}': no valid image stream found")
        if first_dims is None:
            first_dims = (w, h)

    assert first_dims is not None
    w0, h0 = first_dims
    tile_w = max(64, int(tile_width))
    tile_w += tile_w % 2
    raw_h = round(tile_w * (h0 / w0))
    tile_h = max(64, min(raw_h, tile_w * 2))
    tile_h += tile_h % 2

    effective_cols = min(len(image_paths), 3) if cols is None else cols
    rows = math.ceil(len(image_paths) / effective_cols)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    n_imgs = len(image_paths)

    with tempfile.TemporaryDirectory(prefix="qa_lookbook_") as tmp_dir:
        tmp = Path(tmp_dir)
        badge_paths: list[Path] = []
        max_badge_w = max(48, tile_w - 28)
        for idx, lbl in enumerate(resolved_labels):
            bpath = tmp / f"badge_{idx}.png"
            _render_badge_png(lbl, bpath, max_width=max_badge_w)
            badge_paths.append(bpath)

        input_args: list[str] = []
        for img in image_paths:
            input_args.extend(["-i", str(img)])
        for bpath in badge_paths:
            input_args.extend(["-i", str(bpath)])

        filter_parts: list[str] = []
        for idx in range(n_imgs):
            badge_in = n_imgs + idx
            filter_parts.append(
                f"[{idx}:v]scale={tile_w}:{tile_h}:force_original_aspect_ratio=decrease,"
                f"pad={tile_w}:{tile_h}:(ow-iw)/2:(oh-ih)/2:color=#141418,"
                f"setsar=1,format=rgba[base{idx}]"
            )
            filter_parts.append(
                f"[base{idx}][{badge_in}:v]overlay=14:14:format=auto,format=rgb24[v{idx}]"
            )

        tile_spec = f"tile={effective_cols}x{rows}:padding=12:margin=12:color=#0B0B0E"
        if n_imgs == 1:
            filter_complex = f"{';'.join(filter_parts)};[v0]{tile_spec}[out]"
        else:
            concat_inputs = "".join(f"[v{idx}]" for idx in range(n_imgs))
            filter_complex = (
                f"{';'.join(filter_parts)};"
                f"{concat_inputs}concat=n={n_imgs}:v=1:a=0[cat];"
                f"[cat]{tile_spec}[out]"
            )

        proc = subprocess.run(
            [
                ffmpeg,
                "-v",
                "error",
                "-y",
                *input_args,
                "-filter_complex",
                filter_complex,
                "-map",
                "[out]",
                "-frames:v",
                "1",
                str(out_path),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        if proc.returncode != 0 or not out_path.is_file():
            raise RuntimeError(
                f"failed to stitch lookbook PNG '{out_path}': {proc.stderr.strip()}"
            )

    out_probe = _ffprobe_json(ffprobe, out_path)
    out_v = next(
        (s for s in (out_probe.get("streams") or []) if s.get("codec_type") == "video"),
        None,
    )
    out_w = int(out_v["width"]) if out_v and out_v.get("width") else None
    out_h = int(out_v["height"]) if out_v and out_v.get("height") else None

    slots = [
        {"label": lbl, "index": idx, "file": str(img)}
        for idx, (lbl, img) in enumerate(zip(resolved_labels, image_paths))
    ]
    return {
        "ok": True,
        "command": "lookbook",
        "out": str(out_path),
        "cols": effective_cols,
        "rows": rows,
        "tile_width": tile_w,
        "tile_height": tile_h,
        "output_width": out_w,
        "output_height": out_h,
        "slots": slots,
        "warnings": [],
        "errors": [],
    }


def slice_grid(
    image_path: Path,
    *,
    out_dir: Path,
    rows: int = 3,
    cols: int = 3,
    trim: int = 0,
    prefix: str = "tile",
) -> dict[str, Any]:
    """Slice a multi-panel contact sheet (e.g. 3x3 nano_banana_2_shots) into standalone PNG tiles."""
    if not image_path.is_file():
        raise FileNotFoundError(f"grid sheet image not found: {image_path}")
    if rows < 1 or cols < 1:
        raise ValueError(f"rows and cols must be >= 1, got {rows}x{cols}")
    if trim < 0:
        raise ValueError(f"trim must be >= 0, got {trim}")
    clean_prefix = re.sub(r"[^A-Za-z0-9._-]+", "_", (prefix or "tile").strip()) or "tile"

    ffmpeg, ffprobe = _ensure_ffmpeg_tools()
    probe = _ffprobe_json(ffprobe, image_path)
    vstream = next(
        (s for s in (probe.get("streams") or []) if s.get("codec_type") == "video"),
        None,
    )
    if vstream is None or not vstream.get("width") or not vstream.get("height"):
        raise RuntimeError(f"could not determine dimensions of grid image: {image_path}")

    src_w = int(vstream["width"])
    src_h = int(vstream["height"])
    cell_w = src_w // cols
    cell_h = src_h // rows
    crop_w = cell_w - (2 * trim)
    crop_h = cell_h - (2 * trim)
    if crop_w <= 0 or crop_h <= 0:
        raise ValueError(
            f"trim={trim}px leaves non-positive tile size ({crop_w}x{crop_h}) for "
            f"{cols}x{rows} grid on {src_w}x{src_h} image"
        )

    out_dir.mkdir(parents=True, exist_ok=True)
    tiles: list[dict[str, Any]] = []
    for r in range(rows):
        for c in range(cols):
            x = (c * cell_w) + trim
            y = (r * cell_h) + trim
            tile_path = out_dir / f"{clean_prefix}_r{r}_c{c}.png"
            proc = subprocess.run(
                [
                    ffmpeg,
                    "-v",
                    "error",
                    "-y",
                    "-i",
                    str(image_path),
                    "-vf",
                    f"crop={crop_w}:{crop_h}:{x}:{y}",
                    "-frames:v",
                    "1",
                    str(tile_path),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            if proc.returncode != 0 or not tile_path.is_file():
                raise RuntimeError(
                    f"ffmpeg failed slicing tile r{r}_c{c} (exit {proc.returncode}): "
                    f"{proc.stderr.strip()}"
                )
            tiles.append(
                {
                    "row": r,
                    "col": c,
                    "file": str(tile_path),
                    "width": crop_w,
                    "height": crop_h,
                }
            )

    return {
        "ok": True,
        "command": "slice",
        "source": str(image_path),
        "out_dir": str(out_dir),
        "source_width": src_w,
        "source_height": src_h,
        "rows": rows,
        "cols": cols,
        "trim": trim,
        "tile_width": crop_w,
        "tile_height": crop_h,
        "tile_count": len(tiles),
        "tiles": tiles,
        "warnings": [],
        "errors": [],
    }


def _print_human(report: dict[str, Any]) -> None:
    state = "OK" if report["ok"] else "FAIL"
    cmd = report["command"]
    meta = report.get("metadata") or {}
    if cmd == "lookbook":
        print(
            f"[{state}] lookbook: {report['out']} "
            f"({report['cols']}x{report['rows']}, tile={report['tile_width']}x{report['tile_height']}, "
            f"output={report['output_width']}x{report['output_height']})"
        )
        for slot in report.get("slots") or []:
            print(f"  [{slot['label']}] {slot['file']}")
    elif cmd == "slice":
        print(
            f"[{state}] slice: {report['source']} -> {report['out_dir']} "
            f"({report['cols']}x{report['rows']}, trim={report['trim']}px, "
            f"tile={report['tile_width']}x{report['tile_height']}, count={report['tile_count']})"
        )
        for tile in report.get("tiles") or []:
            print(f"  [r{tile['row']}_c{tile['col']}] {tile['file']}")
    elif cmd in ("clip", "render"):
        loud = report.get("loudness") or {}
        qual = report.get("quality") or {}
        print(
            f"[{state}] {cmd}: {report['path']} "
            f"({meta.get('width')}x{meta.get('height')} @{meta.get('fps')}fps, "
            f"dur={meta.get('duration')}s, codec={meta.get('video_codec')}, "
            f"vbr={meta.get('video_bitrate_kbps')}kbps, hf={qual.get('hf_edge_energy')}, "
            f"audio={meta.get('has_audio')}, lufs={loud.get('integrated_lufs')})"
        )
        if report.get("sheet"):
            print(f"  Contact sheet: {report['sheet']}")
        if report.get("crops"):
            print(f"  1:1 crop strip: {report['crops']}")
        if report.get("verify_slices"):
            print(f"  Verify slices ({len(report['verify_slices'])}): {', '.join(report['verify_slices'])}")
        lsc = report.get("locked_still_check") or {}
        if lsc.get("enabled"):
            lsc_state = "PASS" if lsc.get("passed") else "FAIL"
            print(
                f"  Locked-still drift ({lsc_state}): max_tile_drift={lsc.get('max_tile_drift')} "
                f"(limit {lsc.get('threshold')}), mean_luma_shift={lsc.get('mean_luma_shift')}, "
                f"tail_drift={lsc.get('tail_drift')}"
            )
    elif cmd == "batch":
        base = report.get("baseline") or {}
        print(
            f"[{state}] batch: {report.get('clip_count')} clips "
            f"(baseline={base.get('resolution')} @{base.get('fps')}fps, "
            f"min_hf={base.get('min_hf_edge_energy')}, median_hf={base.get('median_hf_edge_energy')})"
        )
        for c in report.get("clips") or []:
            ratio_s = f" ({c['hf_ratio_to_baseline']}x)" if c.get("hf_ratio_to_baseline") is not None else ""
            print(
                f"  - {c['path']}: {c.get('width')}x{c.get('height')} @{c.get('fps')}fps, "
                f"vbr={c.get('video_bitrate_kbps')}kbps, hf={c.get('hf_edge_energy')}{ratio_s}"
            )
    else:
        loud = report.get("loudness") or {}
        print(
            f"[{state}] voice: {report['path']} "
            f"(speech_end={report.get('speech_end')}s, "
            f"allowed=[{report.get('min_allowed')}s, {report.get('max_allowed')}s], "
            f"lufs={loud.get('integrated_lufs')})"
        )
    for w in report.get("warnings") or []:
        print(f"  WARN [{w['code']}]: {w['message']}")
    for e in report.get("errors") or []:
        print(f"  ERROR [{e['code']}]: {e['message']}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Deterministic FFmpeg/ffprobe media QA, 3x2 contact-sheet, and Lookbook grid builder."
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # lookbook
    lb = sub.add_parser(
        "lookbook",
        help="Stitch 1+ images into a clean A/B/C Lookbook or Stills Strip PNG for Dailies.",
    )
    lb.add_argument("images", nargs="+", help="Ordered image paths to stitch into the grid.")
    lb.add_argument("--out", required=True, help="Output PNG path.")
    lb.add_argument(
        "--labels",
        default=None,
        help="Optional comma-separated labels for slots (default: A,B,C,...).",
    )
    lb.add_argument(
        "--cols",
        type=int,
        default=None,
        help="Columns in grid (default: min(image_count, 3)).",
    )
    lb.add_argument(
        "--tile-width",
        type=int,
        default=480,
        help="Uniform width of each tile in pixels (default: 480).",
    )
    lb.add_argument("--json", action="store_true", dest="as_json", help="Emit JSON report.")

    # clip
    cl = sub.add_parser("clip", help="Validate a single generated video clip.")
    cl.add_argument("video", help="Path to video file.")
    cl.add_argument("--sheet", default=None, help="Output path for 3x2 PNG contact sheet.")
    cl.add_argument(
        "--crops",
        default=None,
        help="Output path for unscaled 1:1 native-pixel 3-frame crop strip (mandatory for R5/upscale QC).",
    )
    cl.add_argument(
        "--crop-focus",
        choices=("thirds", "center", "left", "right"),
        default="thirds",
        help="Horizontal crop framing for --crops (default: thirds = left/center/right sweep).",
    )
    cl.add_argument(
        "--max-still", type=float, default=3.0, help="Max static frame duration in seconds (default: 3.0)."
    )
    cl.add_argument(
        "--max-frozen-tail",
        type=float,
        default=None,
        help="Max frozen tail duration in seconds before error (default: matches --max-still).",
    )
    cl.add_argument(
        "--black-min", type=float, default=0.5, help="Minimum black gap duration to flag in seconds (default: 0.5)."
    )
    cl.add_argument("--allow-silent", action="store_true", help="Allow missing or silent audio.")
    cl.add_argument("--strict", action="store_true", help="Treat still_stretch warnings as errors.")
    cl.add_argument(
        "--locked-still",
        action="store_true",
        help=(
            "Enable locked-tripod living-still drift check (ENG-08): suppress static-frame errors "
            "and fail if late 8x8 tile luminance drifts past --drift-threshold."
        ),
    )
    cl.add_argument(
        "--drift-threshold",
        type=float,
        default=LOCKED_STILL_DRIFT_THRESHOLD,
        help=(
            f"Max allowed 8x8 tile mean luminance delta (0-255) for --locked-still "
            f"(default: {LOCKED_STILL_DRIFT_THRESHOLD:g})."
        ),
    )
    cl.add_argument("--json", action="store_true", dest="as_json", help="Emit JSON report.")

    # voice
    vo = sub.add_parser("voice", help="Validate VO timing against target shot/spot window.")
    vo.add_argument("audio", help="Path to audio file.")
    vo.add_argument("--window", type=float, required=True, help="Target window duration in seconds.")
    vo.add_argument(
        "--min-margin-low",
        type=float,
        default=2.0,
        help="Minimum allowable undershoot below window in seconds (default: 2.0).",
    )
    vo.add_argument(
        "--min-margin-high",
        type=float,
        default=0.2,
        help="Minimum breathing margin before end of window in seconds (default: 0.2).",
    )
    vo.add_argument("--json", action="store_true", dest="as_json", help="Emit JSON report.")

    # render
    rn = sub.add_parser("render", help="Validate final assembled video render and loudness.")
    rn.add_argument("video", help="Path to assembled master video file.")
    rn.add_argument("--sheet", default=None, help="Output path for 3x2 PNG contact sheet.")
    rn.add_argument(
        "--crops",
        default=None,
        help="Output path for unscaled 1:1 native-pixel 3-frame crop strip.",
    )
    rn.add_argument(
        "--crop-focus",
        choices=("thirds", "center", "left", "right"),
        default="thirds",
        help="Horizontal crop framing for --crops (default: thirds = left/center/right sweep).",
    )
    rn.add_argument(
        "--verify-slices-dir",
        default=None,
        help="Optional output directory to stream-copy masters > --slice-seconds into part_XX.mp4 slices for fast reviewer-agent playback.",
    )
    rn.add_argument(
        "--slice-seconds",
        type=float,
        default=20.0,
        help="Max duration per verify slice in seconds when --verify-slices-dir is set (default: 20.0).",
    )
    rn.add_argument("--target-lufs", type=float, default=-14.0, help="Target integrated LUFS (default: -14.0).")
    rn.add_argument("--lufs-tolerance", type=float, default=1.0, help="Allowed +/- LUFS tolerance (default: 1.0).")
    rn.add_argument("--max-true-peak", type=float, default=-1.0, help="Strict max true peak dBTP ceiling (default: -1.0).")
    rn.add_argument(
        "--max-still", type=float, default=3.0, help="Max static frame duration in seconds (default: 3.0)."
    )
    rn.add_argument(
        "--max-frozen-tail",
        type=float,
        default=None,
        help="Max frozen tail duration in seconds before error (default: matches --max-still).",
    )
    rn.add_argument(
        "--black-min", type=float, default=0.5, help="Minimum black gap duration to flag in seconds (default: 0.5)."
    )
    rn.add_argument("--allow-silent", action="store_true", help="Allow missing or silent audio.")
    rn.add_argument(
        "--no-loudness-check",
        action="store_true",
        help="Skip integrated LUFS and true-peak range checks (e.g. for --no-loudnorm renders).",
    )
    rn.add_argument("--strict", action="store_true", help="Treat still_stretch warnings as errors.")
    rn.add_argument("--json", action="store_true", dest="as_json", help="Emit JSON report.")

    # slice
    sl = sub.add_parser(
        "slice",
        help="Slice a 2x2 or 3x3 multi-angle contact sheet into clean standalone PNG tiles.",
    )
    sl.add_argument("image", help="Path to grid contact sheet image (e.g. nano_banana_2_shots output).")
    sl.add_argument("--out-dir", required=True, help="Directory to write individual PNG tiles.")
    sl.add_argument("--rows", type=int, default=3, help="Grid rows (default: 3).")
    sl.add_argument("--cols", type=int, default=3, help="Grid columns (default: 3).")
    sl.add_argument(
        "--trim",
        type=int,
        default=0,
        help="Optional pixels to trim off each tile edge to strip thin panel divider lines (default: 0).",
    )
    sl.add_argument("--prefix", default="tile", help="Filename prefix for tiles (default: tile).")
    sl.add_argument("--json", action="store_true", dest="as_json", help="Emit JSON report.")

    # batch
    bt = sub.add_parser(
        "batch",
        help="Audit cross-shot resolution, FPS, bitrate, and HF-sharpness consistency across clips before assembly.",
    )
    bt.add_argument("videos", nargs="+", help="Ordered video clip paths in the edit.")
    bt.add_argument(
        "--max-hf-ratio",
        type=float,
        default=1.5,
        help="Max allowed hf_edge_energy ratio vs. clean mod-4 median before emitting a warning (default: 1.5).",
    )
    bt.add_argument(
        "--strict",
        action="store_true",
        help="Treat fps_mismatch warnings as hard errors (hf_sharpness_outlier stays a visual-inspection warning).",
    )
    bt.add_argument("--json", action="store_true", dest="as_json", help="Emit JSON report.")

    # pixel-diff
    pd = sub.add_parser(
        "pixel-diff",
        help="Verify untouched pass-through frames outside active VFX windows match the source plate.",
    )
    pd.add_argument("processed", help="Processed/composited video file.")
    pd.add_argument("--plate", required=True, help="Original source plate video file.")
    pd.add_argument(
        "--windows",
        default="",
        help="Optional comma-separated active effect windows in seconds (e.g. '2-7,12-17').",
    )
    pd.add_argument(
        "--tolerance",
        type=float,
        default=3.5,
        help="Max allowed mean absolute RGB pixel difference (0-255) on pass-through frames (default: 3.5).",
    )
    pd.add_argument("--json", action="store_true", dest="as_json", help="Emit JSON report.")

    # log-review
    lr = sub.add_parser(
        "log-review",
        help="Append a structured pre-Dailies Visual Critic review verdict to campaigns/<slug>/qc/review-log.jsonl.",
    )
    lr.add_argument("--campaign", required=True, help="Campaign directory.")
    lr.add_argument("--round", required=True, choices=VALID_REVIEW_ROUNDS, help="Production round.")
    lr.add_argument("--asset", required=True, help="Asset or batch identifier (e.g. s04.video, lookbook).")
    lr.add_argument(
        "--verdict",
        required=True,
        choices=VALID_REVIEW_VERDICTS,
        help="Visual Critic verdict.",
    )
    lr.add_argument(
        "--defect-class",
        choices=VALID_DEFECT_CLASSES,
        default=None,
        help="Defect class from docs/delegation.md#review-result (defaults to NONE when verdict=PASS).",
    )
    lr.add_argument("--version", type=int, default=1, help="Asset version integer >= 1 (default: 1).")
    lr.add_argument("--reopen-owner", default="none", help="Reopen owner (Worker(<id>), Root Producer, or none).")
    lr.add_argument("--summary", default="", help="Concise factual impact / findings note.")
    lr.add_argument("--qa-report", default=None, help="Path to qa_media.py JSON report (required for R4/R5 PASS).")
    lr.add_argument("--sheet", default=None, help="Path to inspected 3x2 contact sheet/grid (required for R4/R5 PASS).")
    lr.add_argument("--crops", default=None, help="Path to inspected 1:1 crop strip (required for R5 PASS).")
    lr.add_argument("--reviewer-id", default=None, help="Optional fresh reviewer-agent conversation/lane ID.")
    lr.add_argument("--json", action="store_true", dest="as_json", help="Emit JSON confirmation.")

    return parser


@contextlib.contextmanager
def _review_log_lock(qc_dir: Path) -> Iterator[None]:
    qc_dir.mkdir(parents=True, exist_ok=True)
    lock_path = qc_dir / ".review-log.lock"
    with lock_path.open("a+", encoding="utf-8") as fh:
        fcntl.flock(fh.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(fh.fileno(), fcntl.LOCK_UN)


def append_review_log(
    campaign_dir: Path,
    *,
    round_name: str,
    asset_id: str,
    verdict: str,
    defect_class: str | None = None,
    version: int = 1,
    reopen_owner: str = "none",
    summary: str = "",
    qa_report: str | None = None,
    sheet: str | None = None,
    crops: str | None = None,
    reviewer_id: str | None = None,
) -> dict[str, Any]:
    """Validate and atomically append a structured Visual Critic review event to qc/review-log.jsonl."""
    if not campaign_dir.is_dir():
        raise FileNotFoundError(f"campaign directory not found: {campaign_dir}")
    if round_name not in VALID_REVIEW_ROUNDS:
        raise ValueError(f"invalid round '{round_name}'")
    if verdict not in VALID_REVIEW_VERDICTS:
        raise ValueError(f"invalid verdict '{verdict}'")
    if not isinstance(version, int) or isinstance(version, bool) or version < 1:
        raise ValueError(f"--version must be an integer >= 1, got {version!r}")
    asset_clean = asset_id.strip()
    if not asset_clean:
        raise ValueError("--asset must be non-empty")

    # Fail-closed proof gate: R4/R5 PASS requires an existing qa_media.py report; R5 PASS also requires 1:1 crops.
    def _resolve_proof(raw_p: str | None) -> Path | None:
        if not raw_p or not raw_p.strip():
            return None
        p = Path(raw_p.strip())
        if p.is_file():
            return p
        if not p.is_absolute() and (campaign_dir / p).is_file():
            return campaign_dir / p
        return None

    if verdict == "PASS" and round_name in ("R4", "R4A", "R4B", "R5"):
        if _resolve_proof(qa_report) is None:
            raise ValueError(
                f"REVIEW_HANDOFF_INVALID: {round_name} PASS requires --qa-report pointing to an existing qa_media.py JSON file"
            )
        if _resolve_proof(sheet) is None:
            raise ValueError(
                f"REVIEW_HANDOFF_INVALID: {round_name} PASS requires --sheet pointing to an existing 3x2 contact sheet PNG"
            )
    if verdict == "PASS" and round_name == "R5":
        if _resolve_proof(crops) is None:
            raise ValueError(
                "REVIEW_HANDOFF_INVALID: R5 PASS requires --crops pointing to an existing 1:1 native crop strip PNG"
            )

    resolved_defect = defect_class
    if resolved_defect is None:
        if verdict == "PASS":
            resolved_defect = "NONE"
        elif verdict == "REVIEW_HANDOFF_INVALID":
            resolved_defect = "FOLLOW_UP"
        else:
            raise ValueError(
                f"--defect-class is required when --verdict is {verdict} "
                f"(choose one of {[c for c in VALID_DEFECT_CLASSES if c != 'NONE']})"
            )
    if resolved_defect not in VALID_DEFECT_CLASSES:
        raise ValueError(f"invalid defect class '{resolved_defect}'")
    if verdict in ("FAIL", "CONCERNS") and resolved_defect == "NONE":
        raise ValueError(f"--defect-class cannot be NONE when --verdict is {verdict}")

    qc_dir = campaign_dir / "qc"
    log_path = qc_dir / "review-log.jsonl"
    record: dict[str, Any] = {
        "ts": (
            datetime.datetime.now(datetime.UTC)
            .replace(microsecond=0)
            .isoformat()
            .replace("+00:00", "Z")
        ),
        "round": round_name,
        "asset_id": asset_clean,
        "version": version,
        "verdict": verdict,
        "defect_class": resolved_defect,
        "reopen_owner": (reopen_owner or "none").strip() or "none",
        "summary": summary.strip(),
        "qa_report": qa_report,
        "sheet": sheet,
        "crops": crops,
    }
    if reviewer_id and reviewer_id.strip():
        record["reviewer_id"] = reviewer_id.strip()

    with _review_log_lock(qc_dir):
        if log_path.is_file():
            for idx, line in enumerate(log_path.read_text(encoding="utf-8").splitlines(), start=1):
                if not line.strip():
                    continue
                try:
                    parsed = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise RuntimeError(f"corrupt review-log.jsonl at line {idx}: {exc}") from exc
                if not isinstance(parsed, dict):
                    raise RuntimeError(f"corrupt review-log.jsonl at line {idx}: expected JSON object")
        with log_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
            fh.flush()

    return {
        "ok": True,
        "command": "log-review",
        "log_path": str(log_path),
        "record": record,
    }


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "pixel-diff":
        windows: list[tuple[float, float]] = []
        raw_win = (args.windows or "").strip()
        try:
            if raw_win:
                for token in raw_win.split(","):
                    t = token.strip()
                    if not t:
                        continue
                    lo_s, sep, hi_s = t.partition("-")
                    if not sep:
                        raise ValueError(f"invalid window {t!r}; expected start-end seconds")
                    lo_f, hi_f = float(lo_s), float(hi_s)
                    if not (math.isfinite(lo_f) and math.isfinite(hi_f)) or hi_f < lo_f:
                        raise ValueError(f"invalid window bounds {t!r}")
                    windows.append((lo_f, hi_f))
            report = inspect_pixel_diff(
                Path(args.processed),
                Path(args.plate),
                active_windows=windows,
                tolerance=args.tolerance,
            )
        except (FileNotFoundError, ValueError, RuntimeError) as exc:
            if args.as_json:
                print(json.dumps({"ok": False, "error": str(exc)}, indent=2))
            else:
                print(f"ERROR: {exc}", file=sys.stderr)
            return 2

        if args.as_json:
            print(json.dumps(report, indent=2, ensure_ascii=False))
        else:
            _print_human(report)
        return 0 if report["ok"] else 1

    if args.command == "log-review":
        try:
            report = append_review_log(
                Path(args.campaign),
                round_name=args.round,
                asset_id=args.asset,
                verdict=args.verdict,
                defect_class=args.defect_class,
                version=args.version,
                reopen_owner=args.reopen_owner,
                summary=args.summary,
                qa_report=args.qa_report,
                sheet=args.sheet,
                crops=args.crops,
                reviewer_id=args.reviewer_id,
            )
        except (FileNotFoundError, ValueError, RuntimeError) as exc:
            if args.as_json:
                print(json.dumps({"ok": False, "error": str(exc)}, indent=2))
            else:
                print(f"ERROR: {exc}", file=sys.stderr)
            return 2

        if args.as_json:
            print(json.dumps(report, indent=2, ensure_ascii=False))
        else:
            rec = report["record"]
            print(
                f"[OK] logged review -> {report['log_path']} "
                f"({rec['round']} {rec['asset_id']} v{rec['version']}: "
                f"{rec['verdict']} / {rec['defect_class']})"
            )
        return 0

    if args.command == "lookbook":
        img_paths = [Path(p) for p in args.images]
        labels_list = (
            [lbl.strip() for lbl in args.labels.split(",")]
            if args.labels is not None
            else None
        )
        try:
            report = build_lookbook(
                img_paths,
                out_path=Path(args.out),
                labels=labels_list,
                cols=args.cols,
                tile_width=args.tile_width,
            )
        except (FileNotFoundError, ValueError, RuntimeError) as exc:
            if args.as_json:
                print(json.dumps({"ok": False, "error": str(exc)}, indent=2))
            else:
                print(f"ERROR: {exc}", file=sys.stderr)
            return 2

        if args.as_json:
            print(json.dumps(report, indent=2, ensure_ascii=False))
        else:
            _print_human(report)
        return 0 if report["ok"] else 1

    if args.command == "slice":
        try:
            report = slice_grid(
                Path(args.image),
                out_dir=Path(args.out_dir),
                rows=args.rows,
                cols=args.cols,
                trim=args.trim,
                prefix=args.prefix,
            )
        except (FileNotFoundError, ValueError, RuntimeError) as exc:
            if args.as_json:
                print(json.dumps({"ok": False, "error": str(exc)}, indent=2))
            else:
                print(f"ERROR: {exc}", file=sys.stderr)
            return 2

        if args.as_json:
            print(json.dumps(report, indent=2, ensure_ascii=False))
        else:
            _print_human(report)
        return 0 if report["ok"] else 1

    if args.command == "batch":
        try:
            report = inspect_batch(
                [Path(p) for p in args.videos],
                max_hf_ratio=args.max_hf_ratio,
                strict=args.strict,
            )
        except (FileNotFoundError, ValueError, RuntimeError) as exc:
            if args.as_json:
                print(json.dumps({"ok": False, "error": str(exc)}, indent=2))
            else:
                print(f"ERROR: {exc}", file=sys.stderr)
            return 2

        if args.as_json:
            print(json.dumps(report, indent=2, ensure_ascii=False))
        else:
            _print_human(report)
        return 0 if report["ok"] else 1

    target_path = Path(args.video if args.command in ("clip", "render") else args.audio)
    if not target_path.is_file():
        msg = f"media file not found: {target_path}"
        if args.as_json:
            print(json.dumps({"ok": False, "error": msg}, indent=2))
        else:
            print(f"ERROR: {msg}", file=sys.stderr)
        return 2

    try:
        if args.command == "clip":
            report = inspect_clip(
                target_path,
                sheet_path=Path(args.sheet) if args.sheet else None,
                crops_path=Path(args.crops) if args.crops else None,
                crop_focus=args.crop_focus,
                max_still=args.max_still,
                max_frozen_tail=args.max_frozen_tail,
                black_min=args.black_min,
                allow_silent=args.allow_silent,
                strict=args.strict,
                locked_still=args.locked_still,
                drift_threshold=args.drift_threshold,
            )
        elif args.command == "voice":
            if args.window <= 0:
                msg = "--window must be positive"
                if args.as_json:
                    print(json.dumps({"ok": False, "error": msg}, indent=2))
                else:
                    print(f"ERROR: {msg}", file=sys.stderr)
                return 2
            report = inspect_voice(
                target_path,
                window=args.window,
                min_margin_low=args.min_margin_low,
                min_margin_high=args.min_margin_high,
            )
        else:
            report = inspect_render(
                target_path,
                sheet_path=Path(args.sheet) if args.sheet else None,
                crops_path=Path(args.crops) if args.crops else None,
                crop_focus=args.crop_focus,
                verify_slices_dir=Path(args.verify_slices_dir) if args.verify_slices_dir else None,
                slice_seconds=args.slice_seconds,
                target_lufs=args.target_lufs,
                lufs_tolerance=args.lufs_tolerance,
                max_true_peak=args.max_true_peak,
                max_still=args.max_still,
                max_frozen_tail=args.max_frozen_tail,
                black_min=args.black_min,
                allow_silent=args.allow_silent,
                skip_loudness_check=args.no_loudness_check,
                strict=args.strict,
            )
    except (RuntimeError, ValueError) as exc:
        if args.as_json:
            print(json.dumps({"ok": False, "error": str(exc)}, indent=2))
        else:
            print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    if args.as_json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        _print_human(report)

    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())

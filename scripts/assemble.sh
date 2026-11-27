#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
QA_SCRIPT="${SCRIPT_DIR}/qa_media.py"
PYTHON_BIN="${PYTHON:-python3}"

OUT=""
CAMPAIGN=""
MANIFEST=""
CLIPS_ARG=""
ANIMATIC=0
STILLS_ARG=""
STEMS_DIR=""
MUSIC=""
MUSIC_VOL="0.14"
SFX_VOL="0.18"
VO=""
LUT=""
GRAIN=""
OVERLAY=""
BPM=""
DUCK_MUSIC=0
ENDCARD=""
NO_LOUDNORM=0
ALLOW_SILENT=0

usage() {
  cat <<'EOF'
Usage:
  bash scripts/assemble.sh --out <master.mp4> [options]

Options:
  --out <path>              Output assembled MP4 path (required)
  --campaign <dir>          Campaign directory for resolving manifest relative paths
  --manifest <path>         shotlist.json containing selected takes, optional edit specs, and audio tracks
  --clips <c1,c2,...>       Comma-separated ordered clip paths (alternative to --manifest)
  --animatic                Build a zero-video-credit Still Animatic from stills
  --stills <p1:d1,p2:d2>    Comma-separated still image:duration_s pairs (for --animatic)
  --stems-dir <dir>         Optional output directory for normalized clips, video_only.mp4, and WAV stems
  --music <file>            Optional background music file (looped/trimmed + 1s fade-out)
  --music-vol <float>       Music linear gain <= 0.35 (clamped <= 0.16 with --vo; default: 0.14)
  --sfx-vol <float>         Clip diegetic audio linear gain <= 0.20 (default: 0.18)
  --vo <file>               Optional voiceover track (always mixed at 1.0 per Level Law)
  --duck-music              Sidechain-duck background music gently whenever --vo is speaking
  --lut <file.cube>         Optional 3D LUT file (.cube/.3dl) applied across concatenated video for unified grade
  --grain <float>           Optional subtle shared temporal 35mm grain strength (1..20, e.g. 3-5)
  --overlay <file>          Optional alpha overlay (ProRes 4444/WebM/PNG) composited strictly AFTER --lut/--grain
  --endcard <file>          Optional closing brand card video/ProRes appended strictly AFTER --lut/--grain
  --bpm <float>             Optional music BPM for absolute beat-grid alignment diagnostics
  --no-loudnorm             Skip -14 LUFS / -1.5 dBTP loudness normalization pass
  --allow-silent            Explicitly allow a silent master in final qa_media.py render check
  -h, --help                Show this help message
EOF
}

die() {
  echo "ERROR: $*" >&2
  exit 2
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --out)
      [[ $# -ge 2 ]] || die "--out requires a value"
      OUT="$2"
      shift 2
      ;;
    --campaign)
      [[ $# -ge 2 ]] || die "--campaign requires a value"
      CAMPAIGN="$2"
      shift 2
      ;;
    --manifest)
      [[ $# -ge 2 ]] || die "--manifest requires a value"
      MANIFEST="$2"
      shift 2
      ;;
    --clips)
      [[ $# -ge 2 ]] || die "--clips requires a value"
      CLIPS_ARG="$2"
      shift 2
      ;;
    --animatic)
      ANIMATIC=1
      shift
      ;;
    --stills)
      [[ $# -ge 2 ]] || die "--stills requires a value"
      STILLS_ARG="$2"
      shift 2
      ;;
    --stems-dir)
      [[ $# -ge 2 ]] || die "--stems-dir requires a value"
      STEMS_DIR="$2"
      shift 2
      ;;
    --music)
      [[ $# -ge 2 ]] || die "--music requires a value"
      MUSIC="$2"
      shift 2
      ;;
    --music-vol)
      [[ $# -ge 2 ]] || die "--music-vol requires a value"
      MUSIC_VOL="$2"
      shift 2
      ;;
    --sfx-vol)
      [[ $# -ge 2 ]] || die "--sfx-vol requires a value"
      SFX_VOL="$2"
      shift 2
      ;;
    --vo)
      [[ $# -ge 2 ]] || die "--vo requires a value"
      VO="$2"
      shift 2
      ;;
    --lut)
      [[ $# -ge 2 ]] || die "--lut requires a value"
      LUT="$2"
      shift 2
      ;;
    --grain)
      [[ $# -ge 2 ]] || die "--grain requires a value"
      GRAIN="$2"
      shift 2
      ;;
    --overlay)
      [[ $# -ge 2 ]] || die "--overlay requires a value"
      OVERLAY="$2"
      shift 2
      ;;
    --bpm)
      [[ $# -ge 2 ]] || die "--bpm requires a value"
      BPM="$2"
      shift 2
      ;;
    --duck-music)
      DUCK_MUSIC=1
      shift
      ;;
    --endcard)
      [[ $# -ge 2 ]] || die "--endcard requires a value"
      ENDCARD="$2"
      shift 2
      ;;
    --no-loudnorm)
      NO_LOUDNORM=1
      shift
      ;;
    --allow-silent)
      ALLOW_SILENT=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      die "unknown argument: $1"
      ;;
  esac
done

[[ -n "$OUT" ]] || die "--out is required"
if [[ "$ANIMATIC" -eq 1 ]]; then
  if [[ -z "$STILLS_ARG" && -z "$MANIFEST" ]]; then
    die "--animatic requires either --stills or --manifest"
  fi
else
  if [[ -z "$CLIPS_ARG" && -z "$MANIFEST" ]]; then
    die "provide either --clips or --manifest"
  fi
fi

command -v ffmpeg >/dev/null 2>&1 || die "ffmpeg is required in PATH"
command -v ffprobe >/dev/null 2>&1 || die "ffprobe is required in PATH"
command -v "$PYTHON_BIN" >/dev/null 2>&1 || die "${PYTHON_BIN} is required in PATH"

if [[ -n "$LUT" ]]; then
  [[ -f "$LUT" ]] || die "--lut file not found: $LUT"
fi
if [[ -n "$OVERLAY" ]]; then
  [[ -f "$OVERLAY" ]] || die "--overlay file not found: $OVERLAY"
fi
if [[ -n "$BPM" ]]; then
  BPM="$("$PYTHON_BIN" - "$BPM" <<'PY'
import math, sys
try:
    val = float(sys.argv[1])
except ValueError:
    sys.exit(2)
if not math.isfinite(val) or val < 30.0 or val > 300.0:
    sys.exit(2)
print(f"{val:g}")
PY
  )" || die "--bpm must be a number in [30, 300], got: $BPM"
fi
if [[ -n "$GRAIN" ]]; then
  GRAIN="$("$PYTHON_BIN" - "$GRAIN" <<'PY'
import math, sys
try:
    val = float(sys.argv[1])
except ValueError:
    sys.exit(2)
if not math.isfinite(val) or val <= 0.0 or val > 20.0:
    sys.exit(2)
print(f"{val:g}")
PY
  )" || die "--grain must be a number in (0, 20], got: $GRAIN"
fi
if [[ -n "$OVERLAY" ]]; then
  [[ -f "$OVERLAY" ]] || die "--overlay file not found: $OVERLAY"
fi
if [[ -n "$ENDCARD" ]]; then
  [[ -f "$ENDCARD" ]] || die "--endcard file not found: $ENDCARD"
fi

WORKDIR=""
cleanup() {
  if [[ -n "$WORKDIR" && -d "$WORKDIR" ]]; then
    rm -rf "$WORKDIR"
  fi
}
trap cleanup EXIT
WORKDIR="$(mktemp -d "${TMPDIR:-/tmp}/hf_assemble.XXXXXX")"

# Auto-discover optional manifest audio tracks when CLI flags were not explicitly supplied
if [[ -n "$MANIFEST" ]]; then
  [[ -f "$MANIFEST" ]] || die "manifest file not found: $MANIFEST"
  AUDIO_BASE_DIR="$CAMPAIGN"
  if [[ -z "$AUDIO_BASE_DIR" ]]; then
    AUDIO_BASE_DIR="$(dirname "$MANIFEST")"
  fi
  MANIFEST_AUDIO_OUT="$("$PYTHON_BIN" - "$MANIFEST" "$AUDIO_BASE_DIR" "$MUSIC" "$VO" "$WORKDIR" <<'PY'
import json, math, pathlib, re, subprocess, sys

manifest_path = pathlib.Path(sys.argv[1])
base_dir = pathlib.Path(sys.argv[2])
cli_music = sys.argv[3]
cli_vo = sys.argv[4]
workdir = pathlib.Path(sys.argv[5])

data = json.loads(manifest_path.read_text(encoding="utf-8"))
audio = data.get("audio")
resolved_music = cli_music
resolved_vo = cli_vo

def resolve_rel(raw_path: str) -> pathlib.Path:
    p = pathlib.Path(raw_path)
    if p.is_absolute():
        return p
    if (base_dir / p).is_file():
        return base_dir / p
    return p

def parse_ts(token: str):
    t = token.strip().rstrip("sS").strip()
    if not t:
        return None
    if ":" in t:
        parts = t.split(":")
        if len(parts) not in (2, 3):
            return None
        try:
            nums = [float(x) for x in parts]
        except ValueError:
            return None
        if any(not math.isfinite(x) or x < 0 for x in nums):
            return None
        if len(nums) == 2:
            return nums[0] * 60.0 + nums[1]
        return nums[0] * 3600.0 + nums[1] * 60.0 + nums[2]
    try:
        val = float(t)
    except ValueError:
        return None
    return val if math.isfinite(val) and val >= 0 else None

def parse_window_start(raw):
    if not isinstance(raw, str):
        return None
    m = re.match(
        r"^\s*([0-9:.]+(?:\s*s)?)\s*[-–—]\s*([0-9:.]+(?:\s*s)?)\s*$",
        raw.strip(),
        re.IGNORECASE,
    )
    if not m:
        return None
    return parse_ts(m.group(1))

if isinstance(audio, dict):
    music_cfg = audio.get("music")
    if not resolved_music and isinstance(music_cfg, dict) and music_cfg.get("enabled") is True:
        sel = music_cfg.get("selected_file")
        if isinstance(sel, str) and sel.strip():
            resolved_music = str(resolve_rel(sel.strip()))

    vo_cfg = audio.get("voiceover")
    if not resolved_vo and isinstance(vo_cfg, dict) and vo_cfg.get("enabled") is True:
        sel_vo = vo_cfg.get("selected_file")
        if isinstance(sel_vo, str) and sel_vo.strip():
            resolved_vo = str(resolve_rel(sel_vo.strip()))
        else:
            tracks = vo_cfg.get("tracks")
            if isinstance(tracks, list) and tracks:
                parsed_tracks = []
                for tr in tracks:
                    if isinstance(tr, str) and tr.strip():
                        parsed_tracks.append((resolve_rel(tr.strip()), None, None, None))
                    elif isinstance(tr, dict):
                        fpath = tr.get("selected_file") or tr.get("file") or tr.get("path")
                        if isinstance(fpath, str) and fpath.strip():
                            start = tr.get("start_s")
                            if start is None:
                                start = tr.get("offset_s")
                            if start is None:
                                start = parse_window_start(tr.get("window_s"))
                            t_in = tr.get("trim_start_s")
                            t_out = tr.get("trim_end_s")
                            parsed_tracks.append((resolve_rel(fpath.strip()), start, t_in, t_out))
                if parsed_tracks:
                    for tp, _, _, _ in parsed_tracks:
                        if not tp.is_file():
                            print(f"ERROR: manifest voiceover track not found: {tp}", file=sys.stderr)
                            sys.exit(2)
                    has_trims = any((ti is not None or to is not None) for _, _, ti, to in parsed_tracks)
                    if len(parsed_tracks) == 1 and parsed_tracks[0][1] is None and not has_trims:
                        resolved_vo = str(parsed_tracks[0][0])
                    else:
                        combined_vo = workdir / "manifest_vo.wav"
                        has_offsets = any(st is not None for _, st, _, _ in parsed_tracks)
                        cmd = ["ffmpeg", "-v", "error", "-y"]
                        for tp, _, _, _ in parsed_tracks:
                            cmd.extend(["-i", str(tp)])

                        def _trim_prefix(t_in, t_out):
                            opts = []
                            if t_in is not None:
                                opts.append(f"start={float(t_in):.3f}")
                            if t_out is not None:
                                opts.append(f"end={float(t_out):.3f}")
                            return f"atrim={':'.join(opts)},asetpts=PTS-STARTPTS," if opts else ""

                        if has_offsets:
                            parts = []
                            labels = []
                            for idx, (_, st, t_in, t_out) in enumerate(parsed_tracks):
                                delay_ms = max(0, int(round(float(st or 0.0) * 1000.0)))
                                tpfx = _trim_prefix(t_in, t_out)
                                parts.append(
                                    f"[{idx}:a]{tpfx}aformat=sample_fmts=fltp:sample_rates=48000:channel_layouts=stereo,"
                                    f"adelay={delay_ms}|{delay_ms}[v{idx}]"
                                )
                                labels.append(f"[v{idx}]")
                            fc = ";".join(parts) + f";{''.join(labels)}amix=inputs={len(parsed_tracks)}:duration=longest:dropout_transition=0:normalize=0[vout]"
                        else:
                            parts = []
                            labels = []
                            for idx, (_, _, t_in, t_out) in enumerate(parsed_tracks):
                                tpfx = _trim_prefix(t_in, t_out)
                                parts.append(
                                    f"[{idx}:a]{tpfx}aformat=sample_fmts=fltp:sample_rates=48000:channel_layouts=stereo[v{idx}]"
                                )
                                labels.append(f"[v{idx}]")
                            fc = ";".join(parts) + f";{''.join(labels)}concat=n={len(parsed_tracks)}:v=0:a=1[vout]"
                        cmd.extend([
                            "-filter_complex", fc,
                            "-map", "[vout]",
                            "-c:a", "pcm_s16le", "-ar", "48000", "-ac", "2",
                            str(combined_vo),
                        ])
                        proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
                        if proc.returncode != 0:
                            print(f"ERROR: failed to build manifest VO stem: {proc.stderr.strip()}", file=sys.stderr)
                            sys.exit(2)
                        resolved_vo = str(combined_vo)

print(resolved_music)
print(resolved_vo)
PY
)"
  {
    IFS= read -r MUSIC || true
    IFS= read -r VO || true
  } <<< "$MANIFEST_AUDIO_OUT"
fi

# Enforce Level Law caps with finite checks:
# sfx_vol in [0.0, 0.20], music_vol in [0.0, 0.35], and clamp music_vol <= 0.16 when VO is active
VOL_CHECK="$("$PYTHON_BIN" - "$SFX_VOL" "$MUSIC_VOL" "$VO" <<'PY'
import math, sys
try:
    sfx = float(sys.argv[1])
    music = float(sys.argv[2])
except ValueError:
    print("ERROR: --sfx-vol and --music-vol must be valid numbers", file=sys.stderr)
    sys.exit(2)
has_vo = bool(sys.argv[3].strip())
if not math.isfinite(sfx) or not math.isfinite(music):
    print("ERROR: --sfx-vol and --music-vol must be finite numbers", file=sys.stderr)
    sys.exit(2)
if sfx < 0.0 or sfx > 0.20:
    print(f"ERROR: --sfx-vol ({sfx}) violates Level Law cap [0.0, 0.20]", file=sys.stderr)
    sys.exit(2)
if music < 0.0 or music > 0.35:
    print(f"ERROR: --music-vol ({music}) violates Level Law cap [0.0, 0.35]", file=sys.stderr)
    sys.exit(2)
if has_vo and music > 0.16:
    print(
        f"WARN: clamping --music-vol from {music} to 0.16 while voiceover is active (Level Law)",
        file=sys.stderr,
    )
    music = 0.16
print(f"{'1' if sfx > 0.0 else '0'} {music:.4f}")
PY
)"
read -r SFX_NONZERO MUSIC_VOL <<< "$VOL_CHECK"

if [[ -n "$MUSIC" && ! -f "$MUSIC" ]]; then
  die "music file not found: $MUSIC"
fi
if [[ -n "$VO" && ! -f "$VO" ]]; then
  die "vo file not found: $VO"
fi

NORM_CLIPS=()
HAS_CLIP_AUDIO=0
IDX=0

if [[ "$ANIMATIC" -eq 1 ]]; then
  STILL_FILES=()
  STILL_DURS=()
  MANIFEST_FPS="24"
  MANIFEST_ASPECT=""

  if [[ -n "$STILLS_ARG" ]]; then
    PARSED_STILLS="$("$PYTHON_BIN" - "$STILLS_ARG" <<'PY'
import math, sys
raw = sys.argv[1]
entries = [part.strip() for part in raw.split(",") if part.strip()]
if not entries:
    print("ERROR: --stills contains no entries", file=sys.stderr)
    sys.exit(2)
for entry in entries:
    if ":" in entry:
        path_part, dur_part = entry.rsplit(":", 1)
        path_part = path_part.strip()
        dur_part = dur_part.strip()
        try:
            dur = float(dur_part)
        except ValueError:
            print(f"ERROR: invalid duration in --stills entry '{entry}'", file=sys.stderr)
            sys.exit(2)
    else:
        path_part = entry
        dur = 5.0
    if not path_part or not math.isfinite(dur) or dur <= 0.0:
        print(f"ERROR: invalid --stills entry '{entry}' (expected <path>:<positive_seconds>)", file=sys.stderr)
        sys.exit(2)
    print(f"{path_part}\t{dur:.3f}")
PY
)"
    while IFS=$'\t' read -r spath sdur; do
      [[ -n "$spath" ]] || continue
      STILL_FILES+=("$spath")
      STILL_DURS+=("$sdur")
    done <<< "$PARSED_STILLS"
  else
    [[ -f "$MANIFEST" ]] || die "manifest file not found: $MANIFEST"
    BASE_DIR="$CAMPAIGN"
    if [[ -z "$BASE_DIR" ]]; then
      BASE_DIR="$(dirname "$MANIFEST")"
    fi
    MANIFEST_ANIMATIC_META="$("$PYTHON_BIN" - "$MANIFEST" <<'PY'
import json, pathlib, sys
data = json.loads(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"))
fps = data.get("fps_target")
if isinstance(fps, (int, float)) and not isinstance(fps, bool) and fps > 0:
    fps_str = str(int(fps)) if float(fps).is_integer() else str(fps)
else:
    fps_str = "24"
aspect = str(data.get("aspect_ratio") or "").strip()
print(f"{fps_str}\t{aspect}")
PY
)"
    IFS=$'\t' read -r MANIFEST_FPS MANIFEST_ASPECT <<< "$MANIFEST_ANIMATIC_META"
    PARSED_STILLS="$("$PYTHON_BIN" - "$MANIFEST" "$BASE_DIR" <<'PY'
import json, math, pathlib, sys
manifest_path = pathlib.Path(sys.argv[1])
base_dir = pathlib.Path(sys.argv[2])
data = json.loads(manifest_path.read_text(encoding="utf-8"))
shots = data.get("shots")
if not isinstance(shots, list) or not shots:
    print("ERROR: manifest contains no shots", file=sys.stderr)
    sys.exit(2)
for shot in shots:
    if not isinstance(shot, dict):
        continue
    still_obj = shot.get("still")
    if not isinstance(still_obj, dict):
        print(f"ERROR: shot '{shot.get('id')}' has no still object for --animatic", file=sys.stderr)
        sys.exit(2)
    take = still_obj.get("selected_take")
    if not take:
        print(f"ERROR: shot '{shot.get('id')}' has no still.selected_take", file=sys.stderr)
        sys.exit(2)
    dur = shot.get("duration_s", 5)
    try:
        dur_f = float(dur)
    except (TypeError, ValueError):
        print(f"ERROR: shot '{shot.get('id')}' has invalid duration_s: {dur!r}", file=sys.stderr)
        sys.exit(2)
    if not math.isfinite(dur_f) or dur_f <= 0.0:
        print(f"ERROR: shot '{shot.get('id')}' duration_s must be positive", file=sys.stderr)
        sys.exit(2)
    p = pathlib.Path(take)
    if p.is_absolute():
        resolved = p
    elif (base_dir / p).is_file():
        resolved = base_dir / p
    else:
        resolved = p
    print(f"{resolved}\t{dur_f:.3f}")
PY
)"
    while IFS=$'\t' read -r spath sdur; do
      [[ -n "$spath" ]] || continue
      STILL_FILES+=("$spath")
      STILL_DURS+=("$sdur")
    done <<< "$PARSED_STILLS"
  fi

  [[ "${#STILL_FILES[@]}" -gt 0 ]] || die "no stills resolved for --animatic"
  for still in "${STILL_FILES[@]}"; do
    [[ -f "$still" ]] || die "still file not found: $still"
  done

  # Resolve uniform even-dimension resolution (from still 1, fallback to manifest aspect_ratio)
  FIRST_STILL="${STILL_FILES[0]}"
  STILL_META="$("$PYTHON_BIN" - "$FIRST_STILL" "$MANIFEST_ASPECT" "$MANIFEST_FPS" <<'PY'
import json, subprocess, sys
still_path, aspect, fps = sys.argv[1], sys.argv[2], sys.argv[3]
aspect_map = {
    "16:9": (1280, 720),
    "9:16": (720, 1280),
    "1:1": (1080, 1080),
    "4:5": (864, 1080),
    "4:3": (960, 720),
}
w, h = None, None
proc = subprocess.run(
    ["ffprobe", "-v", "error", "-select_streams", "v:0",
     "-show_entries", "stream=width,height", "-of", "json", still_path],
    capture_output=True, text=True, check=False
)
if proc.returncode == 0:
    try:
        streams = json.loads(proc.stdout).get("streams") or []
        if streams and streams[0].get("width") and streams[0].get("height"):
            w = int(streams[0]["width"])
            h = int(streams[0]["height"])
    except (ValueError, KeyError, TypeError):
        w, h = None, None
if not w or not h:
    w, h = aspect_map.get(aspect, (1280, 720))
w = w + (w % 2)
h = h + (h % 2)
print(f"{w} {h} {fps or '24'}")
PY
)"
  read -r TARGET_W TARGET_H TARGET_FPS <<< "$STILL_META"

  STILL_COUNT="${#STILL_FILES[@]}"
  for ((si = 0; si < STILL_COUNT; si++)); do
    IDX=$((IDX + 1))
    still="${STILL_FILES[$si]}"
    sdur="${STILL_DURS[$si]}"
    CLIP_NAME="$(printf "clip_%02d.mp4" "$IDX")"
    OUT_CLIP="${WORKDIR}/${CLIP_NAME}"
    VF_NORM="scale=${TARGET_W}:${TARGET_H}:force_original_aspect_ratio=decrease:flags=lanczos,pad=${TARGET_W}:${TARGET_H}:(ow-iw)/2:(oh-ih)/2:black,setsar=1"

    ffmpeg -v error -y \
      -loop 1 -framerate "$TARGET_FPS" -t "$sdur" -i "$still" \
      -f lavfi -t "$sdur" -i "anullsrc=channel_layout=stereo:sample_rate=48000" \
      -map 0:v:0 -map 1:a:0 \
      -vf "$VF_NORM" \
      -r "$TARGET_FPS" \
      -c:v libx264 -crf 18 -pix_fmt yuv420p -g 30 \
      -c:a aac -b:a 192k -ar 48000 -ac 2 \
      -shortest \
      "$OUT_CLIP"
    NORM_CLIPS+=("$OUT_CLIP")
  done
else
  # Resolve ordered timeline entries + optional per-shot edit specs (Bash 3.2 compatible)
  ENTRY_KINDS=()
  ENTRY_PATHS=()
  ENTRY_DURS=()
  ENTRY_EDIT_JSONS=()
  if [[ -n "$CLIPS_ARG" ]]; then
    IFS=',' read -r -a RAW_CLIPS <<< "$CLIPS_ARG"
    for item in "${RAW_CLIPS[@]}"; do
      trimmed="$("$PYTHON_BIN" -c 'import sys; print(sys.argv[1].strip())' "$item")"
      if [[ -n "$trimmed" ]]; then
        ENTRY_KINDS+=("VIDEO")
        ENTRY_PATHS+=("$trimmed")
        ENTRY_DURS+=("")
        ENTRY_EDIT_JSONS+=("{}")
      fi
    done
  else
    [[ -f "$MANIFEST" ]] || die "manifest file not found: $MANIFEST"
    BASE_DIR="$CAMPAIGN"
    if [[ -z "$BASE_DIR" ]]; then
      BASE_DIR="$(dirname "$MANIFEST")"
    fi
    RESOLVED_ENTRIES="$("$PYTHON_BIN" - "$MANIFEST" "$BASE_DIR" <<'PY'
import json, math, pathlib, sys
manifest_path = pathlib.Path(sys.argv[1])
base_dir = pathlib.Path(sys.argv[2])
data = json.loads(manifest_path.read_text(encoding="utf-8"))
shots = data.get("shots")
if not isinstance(shots, list) or not shots:
    print("ERROR: manifest contains no shots", file=sys.stderr)
    sys.exit(2)

def resolve_rel(raw_path: str) -> pathlib.Path:
    p = pathlib.Path(raw_path)
    if p.is_absolute():
        return p
    if (base_dir / p).is_file():
        return base_dir / p
    return p

for shot in shots:
    if not isinstance(shot, dict):
        continue
    shot_id = shot.get("id")
    still_only = shot.get("still_only") is True
    vid = shot.get("video")
    still_obj = shot.get("still")

    use_still = still_only or (
        vid is None
        and isinstance(still_obj, dict)
        and bool(still_obj.get("selected_take"))
    )

    if use_still:
        if not isinstance(still_obj, dict) or not still_obj.get("selected_take"):
            print(
                f"ERROR: still_only shot '{shot_id}' has no still.selected_take",
                file=sys.stderr,
            )
            sys.exit(2)
        dur = shot.get("duration_s", 5)
        try:
            dur_f = float(dur)
        except (TypeError, ValueError):
            print(
                f"ERROR: shot '{shot_id}' has invalid duration_s: {dur!r}",
                file=sys.stderr,
            )
            sys.exit(2)
        if not math.isfinite(dur_f) or dur_f <= 0.0:
            print(
                f"ERROR: shot '{shot_id}' duration_s must be positive",
                file=sys.stderr,
            )
            sys.exit(2)
        resolved = resolve_rel(str(still_obj["selected_take"]))
        print(f"STILL\t{resolved}\t{dur_f:.4f}\t{{}}")
        continue

    if not isinstance(vid, dict):
        continue
    edit = shot.get("edit") if isinstance(shot.get("edit"), dict) else {}
    take = edit.get("source_clip") or vid.get("selected_take")
    if not take:
        print(f"ERROR: shot '{shot_id}' has no video.selected_take (or edit.source_clip)", file=sys.stderr)
        sys.exit(2)
    resolved = resolve_rel(str(take))
    spec = {
        "id": shot_id or "",
        "trim_in": edit.get("trim_in"),
        "trim_out": edit.get("trim_out"),
        "crop_4k_punchin": edit.get("crop_4k_punchin"),
        "grade": edit.get("grade") if isinstance(edit.get("grade"), dict) else None,
        "fade_out_black_s": edit.get("fade_out_black_s"),
    }
    print(f"VIDEO\t{resolved}\t0\t{json.dumps(spec, separators=(',', ':'))}")
PY
)"
    DEFAULT_EDIT="{}"
    while IFS=$'\t' read -r ekind epath edur edit_json; do
      [[ -n "$epath" ]] || continue
      ENTRY_KINDS+=("$ekind")
      ENTRY_PATHS+=("$epath")
      ENTRY_DURS+=("$edur")
      ENTRY_EDIT_JSONS+=("${edit_json:-$DEFAULT_EDIT}")
    done <<< "$RESOLVED_ENTRIES"
  fi

  ENTRY_COUNT="${#ENTRY_PATHS[@]}"
  [[ "$ENTRY_COUNT" -gt 0 ]] || die "no clips resolved for assembly"

  FIRST_VIDEO_CLIP=""
  for ((ei = 0; ei < ENTRY_COUNT; ei++)); do
    epath="${ENTRY_PATHS[$ei]}"
    ekind="${ENTRY_KINDS[$ei]}"
    if [[ "$ekind" == "STILL" ]]; then
      [[ -f "$epath" ]] || die "still file not found: $epath"
    else
      [[ -f "$epath" ]] || die "clip file not found: $epath"
      if [[ -z "$FIRST_VIDEO_CLIP" ]]; then
        FIRST_VIDEO_CLIP="$epath"
      fi
    fi
  done

  # Probe target resolution and FPS (prefer first video clip; fall back to still 1 + manifest fps_target/24)
  PROBE_SRC="$FIRST_VIDEO_CLIP"
  PROBE_IS_STILL="0"
  if [[ -z "$PROBE_SRC" ]]; then
    PROBE_SRC="${ENTRY_PATHS[0]}"
    PROBE_IS_STILL="1"
  fi
  PROBE_META="$("$PYTHON_BIN" - "$PROBE_SRC" "$MANIFEST" "$PROBE_IS_STILL" <<'PY'
import json, math, pathlib, subprocess, sys
src_path = sys.argv[1]
manifest_arg = sys.argv[2] if len(sys.argv) > 2 else ""
is_still = (len(sys.argv) > 3 and sys.argv[3] == "1")

aspect_map = {
    "16:9": (1280, 720),
    "9:16": (720, 1280),
    "1:1": (1080, 1080),
    "4:5": (864, 1080),
    "4:3": (960, 720),
}

manifest_fps = ""
manifest_aspect = ""
if manifest_arg:
    try:
        mdata = json.loads(pathlib.Path(manifest_arg).read_text(encoding="utf-8"))
        mfps = mdata.get("fps_target")
        if (
            isinstance(mfps, (int, float))
            and not isinstance(mfps, bool)
            and math.isfinite(float(mfps))
            and float(mfps) > 0
        ):
            manifest_fps = str(int(mfps)) if float(mfps).is_integer() else str(mfps)
        manifest_aspect = str(mdata.get("aspect_ratio") or "").strip()
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        manifest_fps = ""
        manifest_aspect = ""

proc = subprocess.run(
    ["ffprobe", "-v", "error", "-select_streams", "v:0",
     "-show_entries", "stream=width,height,avg_frame_rate,r_frame_rate",
     "-of", "json", src_path],
    capture_output=True, text=True, check=False
)
streams = []
if proc.returncode == 0:
    try:
        streams = json.loads(proc.stdout).get("streams") or []
    except (ValueError, TypeError):
        streams = []

w, h = None, None
st = streams[0] if streams else {}
if st.get("width") and st.get("height"):
    w = int(st["width"])
    h = int(st["height"])

if not w or not h:
    if is_still:
        w, h = aspect_map.get(manifest_aspect, (1280, 720))
    else:
        if proc.returncode != 0:
            print(f"ERROR: ffprobe failed on clip 1: {proc.stderr.strip()}", file=sys.stderr)
        else:
            print("ERROR: clip 1 has no video stream", file=sys.stderr)
        sys.exit(2)

w = w + (w % 2)
h = h + (h % 2)

def valid_rate(rate_str):
    if not rate_str or rate_str == "0/0":
        return False
    if "/" in rate_str:
        n_s, d_s = rate_str.split("/", 1)
        try:
            n, d = float(n_s), float(d_s)
            return d > 0 and (n / d) > 0
        except ValueError:
            return False
    try:
        return float(rate_str) > 0
    except ValueError:
        return False

if is_still:
    fps = manifest_fps if manifest_fps else "24"
else:
    avg_fps = st.get("avg_frame_rate") or ""
    r_fps = st.get("r_frame_rate") or ""
    fps = manifest_fps if manifest_fps else (avg_fps if valid_rate(avg_fps) else (r_fps if valid_rate(r_fps) else "24/1"))
print(f"{w} {h} {fps}")
PY
)"
  read -r TARGET_W TARGET_H TARGET_FPS <<< "$PROBE_META"

  DEFAULT_EDIT="{}"
  for ((ei = 0; ei < ENTRY_COUNT; ei++)); do
    IDX=$((IDX + 1))
    ekind="${ENTRY_KINDS[$ei]}"
    clip="${ENTRY_PATHS[$ei]}"
    edur="${ENTRY_DURS[$ei]}"
    edit_json="${ENTRY_EDIT_JSONS[$ei]:-$DEFAULT_EDIT}"
    CLIP_NAME="$(printf "clip_%02d.mp4" "$IDX")"
    OUT_CLIP="${WORKDIR}/${CLIP_NAME}"

    if [[ "$ekind" == "STILL" ]]; then
      VF_STILL="scale=${TARGET_W}:${TARGET_H}:force_original_aspect_ratio=decrease:flags=lanczos,pad=${TARGET_W}:${TARGET_H}:(ow-iw)/2:(oh-ih)/2:black,setsar=1"
      ffmpeg -v error -y \
        -loop 1 -framerate "$TARGET_FPS" -t "$edur" -i "$clip" \
        -f lavfi -t "$edur" -i "anullsrc=channel_layout=stereo:sample_rate=48000" \
        -map 0:v:0 -map 1:a:0 \
        -vf "$VF_STILL" \
        -r "$TARGET_FPS" \
        -c:v libx264 -crf 18 -pix_fmt yuv420p -g 30 \
        -c:a aac -b:a 192k -ar 48000 -ac 2 \
        -shortest \
        "$OUT_CLIP"
    else
      AUDIO_STREAM="$(ffprobe -v error -select_streams a -show_entries stream=index -of csv=p=0 "$clip" | head -n 1 || true)"

      CLIP_DIM_FPS="$(ffprobe -v error -select_streams v:0 -show_entries stream=width,height,avg_frame_rate -of csv=p=0 "$clip" | head -n 1 || true)"
      CLIP_DUR_RAW="$(ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 "$clip" | head -n 1 || true)"
      if [[ -n "$CLIP_DIM_FPS" ]]; then
        IFS=',' read -r cw ch cfps <<< "$CLIP_DIM_FPS"
        if [[ -n "$cw" && -n "$ch" ]] && [[ "$cw" != "$TARGET_W" || "$ch" != "$TARGET_H" ]]; then
          echo "WARN: clip '${clip}' dimensions (${cw}x${ch}) differ from target (${TARGET_W}x${TARGET_H}); lanczos scaling/padding applied" >&2
        fi
        if [[ -n "$cfps" && "$cfps" != "$TARGET_FPS" && "$cfps" != "${TARGET_FPS}/1" ]]; then
          echo "WARN: clip '${clip}' native FPS (${cfps}) differs from target (${TARGET_FPS}); check for pulldown judder" >&2
        fi
      fi

      # Build per-shot trim, optional 4K 2x punch-in crop, pre-LUT grade match, and fade-to-black filters
      EDIT_PARSED="$("$PYTHON_BIN" - "$edit_json" "$TARGET_W" "$TARGET_H" "${CLIP_DUR_RAW:-0}" <<'PY'
import json, math, re, sys
spec = json.loads(sys.argv[1] or "{}")
tw, th = int(sys.argv[2]), int(sys.argv[3])
src_dur = float(sys.argv[4] or 0.0)

trim_in = spec.get("trim_in")
trim_out = spec.get("trim_out")
ss_str = ""
dur_str = ""
eff_dur = src_dur

if trim_in is not None:
    ti = float(trim_in)
    if not math.isfinite(ti) or ti < 0.0:
        print(f"ERROR: invalid edit.trim_in {trim_in!r}", file=sys.stderr)
        sys.exit(2)
    ss_str = f"{ti:.3f}"
    eff_dur = max(0.0, src_dur - ti)
else:
    ti = 0.0

if trim_out is not None:
    to = float(trim_out)
    if not math.isfinite(to) or to <= ti:
        print(f"ERROR: invalid edit.trim_out {trim_out!r} (must be > trim_in={ti})", file=sys.stderr)
        sys.exit(2)
    dur_val = to - ti
    dur_str = f"{dur_val:.3f}"
    eff_dur = dur_val

vf_parts = []
crop_spec = spec.get("crop_4k_punchin")
if isinstance(crop_spec, str) and crop_spec.strip():
    cs = crop_spec.strip()
    if cs == "center_2x":
        vf_parts.append("crop=iw/2:ih/2:iw/4:ih/4")
    elif cs == "left_2x":
        vf_parts.append("crop=iw/2:ih/2:0:ih/4")
    elif cs == "right_2x":
        vf_parts.append("crop=iw/2:ih/2:iw/2:ih/4")
    elif re.match(r"^[0-9a-zA-Z_/*+-]+:[0-9a-zA-Z_/*+-]+:[0-9a-zA-Z_/*+-]+:[0-9a-zA-Z_/*+-]+$", cs):
        vf_parts.append(f"crop={cs}")
    else:
        print(f"ERROR: invalid edit.crop_4k_punchin {cs!r}", file=sys.stderr)
        sys.exit(2)

vf_parts.append(f"scale={tw}:{th}:force_original_aspect_ratio=decrease:flags=lanczos")
vf_parts.append(f"pad={tw}:{th}:(ow-iw)/2:(oh-ih)/2:black")
vf_parts.append("setsar=1")

grade = spec.get("grade")
if isinstance(grade, dict):
    eq_args = []
    for key in ("brightness", "contrast", "saturation", "gamma"):
        if key in grade and grade[key] is not None:
            v = float(grade[key])
            if not math.isfinite(v):
                print(f"ERROR: non-finite edit.grade.{key}", file=sys.stderr)
                sys.exit(2)
            eq_args.append(f"{key}={v:.4f}")
    if eq_args:
        vf_parts.append("eq=" + ":".join(eq_args))
    cb_args = []
    wb_r = grade.get("wb_r")
    wb_b = grade.get("wb_b")
    if wb_r is not None:
        v = float(wb_r)
        if not math.isfinite(v):
            sys.exit(2)
        cb_args.append(f"rm={v:.4f}:rs={v * 0.5:.4f}")
    if wb_b is not None:
        v = float(wb_b)
        if not math.isfinite(v):
            sys.exit(2)
        cb_args.append(f"bm={v:.4f}:bs={v * 0.5:.4f}")
    if cb_args:
        vf_parts.append("colorbalance=" + ":".join(cb_args))

fade_out = spec.get("fade_out_black_s")
if fade_out is not None:
    fo = float(fade_out)
    if not math.isfinite(fo) or fo <= 0.0 or fo > 2.0:
        print(f"ERROR: edit.fade_out_black_s must be in (0, 2.0], got {fade_out!r}", file=sys.stderr)
        sys.exit(2)
    if eff_dur > fo:
        st = max(0.0, eff_dur - fo)
        vf_parts.append(f"fade=t=out:st={st:.3f}:d={fo:.3f}")

print(ss_str)
print(dur_str)
print(",".join(vf_parts))
PY
)"
      {
        IFS= read -r TRIM_SS || true
        IFS= read -r TRIM_DUR || true
        IFS= read -r VF_NORM || true
      } <<< "$EDIT_PARSED"

      IN_ARGS=()
      TRIM_OUT_ARGS=()
      if [[ -n "$TRIM_SS" ]]; then
        IN_ARGS+=(-ss "$TRIM_SS")
      fi
      if [[ -n "$TRIM_DUR" ]]; then
        TRIM_OUT_ARGS+=(-t "$TRIM_DUR")
      fi

      if [[ -n "$AUDIO_STREAM" ]]; then
        HAS_CLIP_AUDIO=1
        ffmpeg -v error -y "${IN_ARGS[@]+"${IN_ARGS[@]}"}" -i "$clip" "${TRIM_OUT_ARGS[@]+"${TRIM_OUT_ARGS[@]}"}" \
          -vf "$VF_NORM" \
          -r "$TARGET_FPS" \
          -c:v libx264 -crf 18 -pix_fmt yuv420p -g 30 \
          -c:a aac -b:a 192k -ar 48000 -ac 2 \
          "$OUT_CLIP"
      else
        ffmpeg -v error -y "${IN_ARGS[@]+"${IN_ARGS[@]}"}" -i "$clip" \
          -f lavfi -i "anullsrc=channel_layout=stereo:sample_rate=48000" \
          -map 0:v:0 -map 1:a:0 \
          "${TRIM_OUT_ARGS[@]+"${TRIM_OUT_ARGS[@]}"}" \
          -vf "$VF_NORM" \
          -r "$TARGET_FPS" \
          -c:v libx264 -crf 18 -pix_fmt yuv420p -g 30 \
          -c:a aac -b:a 192k -ar 48000 -ac 2 \
          -shortest \
          "$OUT_CLIP"
      fi
    fi
    NORM_CLIPS+=("$OUT_CLIP")
  done
fi

# Concatenate normalized clips cleanly via filter_complex concat (zero cut-point freezes)
CONCAT_INPUTS=()
CONCAT_FILTER=""
CLIP_COUNT="${#NORM_CLIPS[@]}"
for ((i = 0; i < CLIP_COUNT; i++)); do
  CONCAT_INPUTS+=(-i "${NORM_CLIPS[$i]}")
  CONCAT_FILTER="${CONCAT_FILTER}[${i}:v:0][${i}:a:0]"
done
CONCAT_FILTER="${CONCAT_FILTER}concat=n=${CLIP_COUNT}:v=1:a=1[vcat][acat]"

FINISH_CHAIN=""
if [[ -n "$LUT" ]]; then
  LUT_BASE="$(basename "$LUT")"
  if [[ "$LUT_BASE" == *.* ]]; then
    LUT_EXT="${LUT_BASE##*.}"
  else
    LUT_EXT="cube"
  fi
  LUT_SAFE="${WORKDIR}/grade.${LUT_EXT}"
  cp "$LUT" "$LUT_SAFE"
  FINISH_CHAIN="lut3d=file='${LUT_SAFE}'"
fi
if [[ -n "$GRAIN" ]]; then
  GRAIN_FILTER="noise=c0s=${GRAIN}:c0f=t+u"
  if [[ -n "$FINISH_CHAIN" ]]; then
    FINISH_CHAIN="${FINISH_CHAIN},${GRAIN_FILTER}"
  else
    FINISH_CHAIN="${GRAIN_FILTER}"
  fi
fi

VIDEO_MAP="[vcat]"
if [[ -n "$FINISH_CHAIN" ]]; then
  CONCAT_FILTER="${CONCAT_FILTER};[vcat]${FINISH_CHAIN}[vfin]"
  VIDEO_MAP="[vfin]"
fi

VIDEO_ONLY="${WORKDIR}/video_only.mp4"
DIEGETIC_WAV="${WORKDIR}/diegetic.wav"

ffmpeg -v error -y \
  "${CONCAT_INPUTS[@]}" \
  -filter_complex "$CONCAT_FILTER" \
  -map "$VIDEO_MAP" -an -r "$TARGET_FPS" -c:v libx264 -crf 18 -pix_fmt yuv420p -g 30 "$VIDEO_ONLY" \
  -map "[acat]" -vn -c:a pcm_s16le -ar 48000 -ac 2 "$DIEGETIC_WAV"

# Composite optional post-LUT/post-grain alpha overlay (ProRes 4444 / WebM / PNG)
if [[ -n "$OVERLAY" ]]; then
  GRADED_DURATION="$(ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 "$VIDEO_ONLY")"
  OVERLAY_META="$("$PYTHON_BIN" - "$OVERLAY" <<'PY'
import json, subprocess, sys

ov_path = sys.argv[1]
proc = subprocess.run(
    ["ffprobe", "-v", "error", "-show_format", "-show_streams", "-of", "json", ov_path],
    capture_output=True, text=True, check=False,
)
if proc.returncode != 0:
    print(f"ERROR: ffprobe failed on --overlay '{ov_path}': {proc.stderr.strip()}", file=sys.stderr)
    sys.exit(2)
data = json.loads(proc.stdout)
streams = data.get("streams") or []
vstream = next((s for s in streams if s.get("codec_type") == "video"), None)
if vstream is None:
    print(f"ERROR: --overlay '{ov_path}' has no video/image stream", file=sys.stderr)
    sys.exit(2)
fmt_name = str((data.get("format") or {}).get("format_name") or "").lower()
codec = str(vstream.get("codec_name") or "").lower()
raw_dur = (data.get("format") or {}).get("duration") or vstream.get("duration")
raw_frames = vstream.get("nb_frames")
nb_frames = (
    int(raw_frames)
    if isinstance(raw_frames, str) and raw_frames.isdigit()
    else (raw_frames if isinstance(raw_frames, int) else None)
)

is_still = (
    codec in ("png", "tiff", "bmp", "mjpeg", "webp")
    and (nb_frames is None or nb_frames <= 1)
    and not raw_dur
) or any(
    tok in fmt_name
    for tok in ("png_pipe", "tiff_pipe", "bmp_pipe", "jpeg_pipe", "webp_pipe", "image2")
)

if is_still:
    # Only loop still overlays across full duration when the still has actual transparency (alpha < 255)
    alpha_proc = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", ov_path, "-frames:v", "1", "-vf", "scale=64:64", "-f", "rawvideo", "-pix_fmt", "rgba", "-"],
        capture_output=True, check=False,
    )
    if alpha_proc.returncode == 0 and len(alpha_proc.stdout) >= 4:
        if min(alpha_proc.stdout[3::4]) >= 255:
            is_still = False

decoder = ""
if codec in ("vp9", "vp8"):
    wanted = "libvpx-vp9" if codec == "vp9" else "libvpx"
    dec_proc = subprocess.run(
        ["ffmpeg", "-v", "error", "-decoders"],
        capture_output=True, text=True, check=False,
    )
    if dec_proc.returncode == 0 and wanted in dec_proc.stdout:
        decoder = wanted

print(f"{'1' if is_still else '0'} {decoder}")
PY
)"
  OVERLAY_IS_STILL="0"
  OVERLAY_DECODER=""
  read -r OVERLAY_IS_STILL OVERLAY_DECODER <<< "$OVERLAY_META"

  OVERLAY_IN_ARGS=()
  if [[ "$OVERLAY_IS_STILL" == "1" ]]; then
    OVERLAY_IN_ARGS=(-loop 1 -framerate "$TARGET_FPS" -t "$GRADED_DURATION" -i "$OVERLAY")
  elif [[ -n "$OVERLAY_DECODER" ]]; then
    OVERLAY_IN_ARGS=(-c:v "$OVERLAY_DECODER" -i "$OVERLAY")
  else
    OVERLAY_IN_ARGS=(-i "$OVERLAY")
  fi

  OVERLAY_VIDEO="${WORKDIR}/video_overlay.mp4"
  ffmpeg -v error -y \
    -i "$VIDEO_ONLY" \
    "${OVERLAY_IN_ARGS[@]}" \
    -filter_complex "[0:v]format=rgba[base];[1:v]scale=${TARGET_W}:${TARGET_H}:flags=lanczos,setsar=1,format=rgba[ov];[base][ov]overlay=0:0:shortest=0:eof_action=pass:format=rgb,format=yuv420p[vout]" \
    -map "[vout]" -an -r "$TARGET_FPS" -c:v libx264 -crf 18 -pix_fmt yuv420p -g 30 \
    "$OVERLAY_VIDEO"
  mv "$OVERLAY_VIDEO" "$VIDEO_ONLY"
fi

# Append optional post-LUT/post-grain closing brand endcard cleanly after graded timeline
if [[ -n "$ENDCARD" ]]; then
  ENDCARD_NORM="${WORKDIR}/endcard_norm.mp4"
  ENDCARD_AUDIO_STREAM="$(ffprobe -v error -select_streams a -show_entries stream=index -of csv=p=0 "$ENDCARD" | head -n 1 || true)"
  VF_ENDCARD="scale=${TARGET_W}:${TARGET_H}:force_original_aspect_ratio=decrease:flags=lanczos,pad=${TARGET_W}:${TARGET_H}:(ow-iw)/2:(oh-ih)/2:black,setsar=1"
  if [[ -n "$ENDCARD_AUDIO_STREAM" ]]; then
    HAS_CLIP_AUDIO=1
    ffmpeg -v error -y -i "$ENDCARD" \
      -vf "$VF_ENDCARD" \
      -r "$TARGET_FPS" \
      -c:v libx264 -crf 18 -pix_fmt yuv420p -g 30 \
      -c:a aac -b:a 192k -ar 48000 -ac 2 \
      "$ENDCARD_NORM"
  else
    ffmpeg -v error -y -i "$ENDCARD" \
      -f lavfi -i "anullsrc=channel_layout=stereo:sample_rate=48000" \
      -map 0:v:0 -map 1:a:0 \
      -vf "$VF_ENDCARD" \
      -r "$TARGET_FPS" \
      -c:v libx264 -crf 18 -pix_fmt yuv420p -g 30 \
      -c:a aac -b:a 192k -ar 48000 -ac 2 \
      -shortest \
      "$ENDCARD_NORM"
  fi

  APPENDED_VIDEO="${WORKDIR}/video_with_endcard.mp4"
  APPENDED_DIEGETIC="${WORKDIR}/diegetic_with_endcard.wav"
  ffmpeg -v error -y \
    -i "$VIDEO_ONLY" \
    -i "$DIEGETIC_WAV" \
    -i "$ENDCARD_NORM" \
    -filter_complex "[0:v:0][1:a:0][2:v:0][2:a:0]concat=n=2:v=1:a=1[vout][aout]" \
    -map "[vout]" -an -r "$TARGET_FPS" -c:v libx264 -crf 18 -pix_fmt yuv420p -g 30 "$APPENDED_VIDEO" \
    -map "[aout]" -vn -c:a pcm_s16le -ar 48000 -ac 2 "$APPENDED_DIEGETIC"
  mv "$APPENDED_VIDEO" "$VIDEO_ONLY"
  mv "$APPENDED_DIEGETIC" "$DIEGETIC_WAV"
fi

VIDEO_DURATION="$(ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 "$VIDEO_ONLY")"

if [[ -n "$BPM" ]]; then
  "$PYTHON_BIN" - "$BPM" "$VIDEO_DURATION" <<'PY' >&2
import sys
bpm = float(sys.argv[1])
dur = float(sys.argv[2])
beat_s = 60.0 / bpm
beats = dur / beat_s
nearest = round(beats)
drift_ms = abs(dur - nearest * beat_s) * 1000.0
if drift_ms > 80.0:
    print(f"WARN: total cut duration {dur:.3f}s is {drift_ms:.0f}ms off nearest beat at {bpm:g} BPM ({nearest} beats = {nearest * beat_s:.3f}s)")
PY
fi

# Prepare optional VO and music WAV stems
VO_WAV="${WORKDIR}/vo.wav"
MUSIC_WAV="${WORKDIR}/music.wav"

if [[ -n "$VO" ]]; then
  ffmpeg -v error -y -i "$VO" \
    -af "aformat=sample_fmts=fltp:sample_rates=48000:channel_layouts=stereo,apad,atrim=0:${VIDEO_DURATION}" \
    -c:a pcm_s16le -ar 48000 -ac 2 "$VO_WAV"
fi

if [[ -n "$MUSIC" ]]; then
  FADE_PARAMS="$("$PYTHON_BIN" - "$VIDEO_DURATION" <<'PY'
import sys
dur = float(sys.argv[1])
fade_dur = min(1.0, max(0.1, dur / 2.0))
fade_start = max(0.0, dur - fade_dur)
print(f"{fade_start:.3f} {fade_dur:.3f}")
PY
)"
  read -r FADE_START FADE_DUR <<< "$FADE_PARAMS"
  ffmpeg -v error -y -stream_loop -1 -i "$MUSIC" \
    -t "$VIDEO_DURATION" \
    -af "aformat=sample_fmts=fltp:sample_rates=48000:channel_layouts=stereo,afade=t=out:st=${FADE_START}:d=${FADE_DUR}" \
    -c:a pcm_s16le -ar 48000 -ac 2 "$MUSIC_WAV"
fi

# Mix stems according to Level Law (VO=1.0, music<=0.35 or <=0.16 w/ VO, sfx<=0.20, normalize=0)
RAW_MIX_WAV="${WORKDIR}/mix_raw.wav"
MIX_INPUTS=(-i "$DIEGETIC_WAV")
MIX_CHAIN="[0:a]volume=${SFX_VOL}[a0];"
MIX_LABELS="[a0]"
MIX_COUNT=1

if [[ -n "$VO" ]]; then
  MIX_INPUTS+=(-i "$VO_WAV")
  if [[ "$DUCK_MUSIC" -eq 1 && -n "$MUSIC" ]]; then
    MIX_CHAIN="${MIX_CHAIN}[${MIX_COUNT}:a]asplit=2[vo_main][vo_sc];[vo_main]volume=1.0[a${MIX_COUNT}];"
  else
    MIX_CHAIN="${MIX_CHAIN}[${MIX_COUNT}:a]volume=1.0[a${MIX_COUNT}];"
  fi
  MIX_LABELS="${MIX_LABELS}[a${MIX_COUNT}]"
  MIX_COUNT=$((MIX_COUNT + 1))
fi

if [[ -n "$MUSIC" ]]; then
  MIX_INPUTS+=(-i "$MUSIC_WAV")
  if [[ "$DUCK_MUSIC" -eq 1 && -n "$VO" ]]; then
    MIX_CHAIN="${MIX_CHAIN}[${MIX_COUNT}:a]volume=${MUSIC_VOL}[mus_pre];[mus_pre][vo_sc]sidechaincompress=threshold=0.02:ratio=4:attack=30:release=250:makeup=1[a${MIX_COUNT}];"
  else
    MIX_CHAIN="${MIX_CHAIN}[${MIX_COUNT}:a]volume=${MUSIC_VOL}[a${MIX_COUNT}];"
  fi
  MIX_LABELS="${MIX_LABELS}[a${MIX_COUNT}]"
  MIX_COUNT=$((MIX_COUNT + 1))
fi

if [[ "$MIX_COUNT" -eq 1 ]]; then
  ffmpeg -v error -y -i "$DIEGETIC_WAV" \
    -af "volume=${SFX_VOL},atrim=0:${VIDEO_DURATION}" \
    -c:a pcm_s16le -ar 48000 -ac 2 "$RAW_MIX_WAV"
else
  MIX_FILTER="${MIX_CHAIN}${MIX_LABELS}amix=inputs=${MIX_COUNT}:duration=first:dropout_transition=0:normalize=0,atrim=0:${VIDEO_DURATION}[amixout]"
  ffmpeg -v error -y "${MIX_INPUTS[@]}" \
    -filter_complex "$MIX_FILTER" \
    -map "[amixout]" \
    -c:a pcm_s16le -ar 48000 -ac 2 "$RAW_MIX_WAV"
fi

# Determine whether audible master audio is expected
MASTER_HAS_AUDIO=0
if [[ -n "$VO" || -n "$MUSIC" ]]; then
  MASTER_HAS_AUDIO=1
elif [[ "$HAS_CLIP_AUDIO" -eq 1 && "$SFX_NONZERO" -eq 1 ]]; then
  MASTER_HAS_AUDIO=1
fi

# Apply canonical loudness mastering (-14 LUFS, -1.5 dBTP ceiling, LRA 11) unless --no-loudnorm
FINAL_WAV="${WORKDIR}/mix_final.wav"
if [[ "$NO_LOUDNORM" -eq 1 || "$MASTER_HAS_AUDIO" -eq 0 ]]; then
  cp "$RAW_MIX_WAV" "$FINAL_WAV"
else
  LN_FILTER="$("$PYTHON_BIN" - "$RAW_MIX_WAV" <<'PY'
import json, math, re, subprocess, sys
proc = subprocess.run(
    ["ffmpeg", "-v", "info", "-i", sys.argv[1],
     "-af", "loudnorm=I=-14:TP=-1.5:LRA=11:print_format=json",
     "-f", "null", "-"],
    capture_output=True, text=True, check=False
)
matches = list(re.finditer(r"\{[^{}]*\"input_i\"[^{}]*\}", proc.stderr, re.DOTALL))
if not matches:
    print("loudnorm=I=-14:TP=-1.5:LRA=11")
    sys.exit(0)
data = json.loads(matches[-1].group(0))
try:
    mi = float(data["input_i"])
    mtp = float(data["input_tp"])
    mlra = float(data["input_lra"])
    mth = float(data["input_thresh"])
    off = float(data["target_offset"])
except (KeyError, ValueError, TypeError):
    print("loudnorm=I=-14:TP=-1.5:LRA=11")
    sys.exit(0)
if not all(math.isfinite(x) for x in (mi, mtp, mlra, mth, off)) or mi < -70.0:
    print("SILENT")
    sys.exit(0)
print(
    f"loudnorm=I=-14:TP=-1.5:LRA=11:measured_I={mi:.2f}:measured_TP={mtp:.2f}:"
    f"measured_LRA={mlra:.2f}:measured_thresh={mth:.2f}:offset={off:.2f}:linear=true"
)
PY
)"
  if [[ "$LN_FILTER" == "SILENT" ]]; then
    if [[ "$ALLOW_SILENT" -eq 1 ]]; then
      cp "$RAW_MIX_WAV" "$FINAL_WAV"
    else
      echo "ERROR: audio mix measured silent (< -70 LUFS) despite expected audio tracks (--vo/--music/clip audio)" >&2
      exit 1
    fi
  else
    ffmpeg -v error -y -i "$RAW_MIX_WAV" \
      -af "$LN_FILTER" \
      -c:a pcm_s16le -ar 48000 -ac 2 "$FINAL_WAV"
  fi
fi

# Mux final master MP4
mkdir -p "$(dirname "$OUT")"
ffmpeg -v error -y \
  -i "$VIDEO_ONLY" \
  -i "$FINAL_WAV" \
  -map 0:v:0 -map 1:a:0 \
  -c:v copy \
  -c:a aac -b:a 192k -ar 48000 -ac 2 \
  -movflags +faststart \
  -shortest \
  "$OUT"

# Export optional stems for DaVinci Resolve polish
if [[ -n "$STEMS_DIR" ]]; then
  mkdir -p "$STEMS_DIR"
  for norm_clip in "${NORM_CLIPS[@]}"; do
    cp "$norm_clip" "${STEMS_DIR}/$(basename "$norm_clip")"
  done
  cp "$VIDEO_ONLY" "${STEMS_DIR}/video_only.mp4"
  cp "$DIEGETIC_WAV" "${STEMS_DIR}/diegetic.wav"
  if [[ -n "$MUSIC" ]]; then
    cp "$MUSIC_WAV" "${STEMS_DIR}/music.wav"
  fi
  if [[ -n "$VO" ]]; then
    cp "$VO_WAV" "${STEMS_DIR}/vo.wav"
  fi
fi

# Final QA verification gate (no silent-master bypass unless explicit --allow-silent or audio-less animatic)
QA_ARGS=(render "$OUT" --json)
if [[ "$ANIMATIC" -eq 1 ]]; then
  QA_ARGS+=(--max-still 999)
fi
if [[ "$NO_LOUDNORM" -eq 1 ]]; then
  QA_ARGS+=(--no-loudness-check)
fi
if [[ "$ALLOW_SILENT" -eq 1 ]]; then
  QA_ARGS+=(--allow-silent)
elif [[ "$ANIMATIC" -eq 1 && -z "$VO" && -z "$MUSIC" ]]; then
  QA_ARGS+=(--allow-silent)
fi
"$PYTHON_BIN" "$QA_SCRIPT" "${QA_ARGS[@]}"

"""Integration tests for scripts/qa_media.py and scripts/assemble.sh using synthetic FFmpeg media."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
QA_SCRIPT = REPO_ROOT / "scripts" / "qa_media.py"
ASSEMBLE_SCRIPT = REPO_ROOT / "scripts" / "assemble.sh"

PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


def _ffmpeg(*args: str) -> None:
    proc = subprocess.run(
        ["ffmpeg", "-v", "error", "-y", *args],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg failed (rc={proc.returncode}): {proc.stderr}")


def _ffprobe_json(media_path: Path) -> dict:
    proc = subprocess.run(
        [
            "ffprobe",
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
        check=True,
    )
    return json.loads(proc.stdout)


@unittest.skipUnless(
    shutil.which("ffmpeg") and shutil.which("ffprobe"),
    "ffmpeg and ffprobe are required for media QA and assembly tests",
)
class TestQaAndAssemble(unittest.TestCase):
    def _run_qa(self, *args: str) -> tuple[int, dict, str]:
        proc = subprocess.run(
            [sys.executable, str(QA_SCRIPT), *args, "--json"],
            capture_output=True,
            text=True,
            check=False,
        )
        parsed = json.loads(proc.stdout) if proc.stdout.strip().startswith("{") else {}
        return proc.returncode, parsed, proc.stderr

    def test_good_clip_passes_and_writes_contact_sheet(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            clip = tmp / "good.mp4"
            sheet = tmp / "good_sheet.png"

            _ffmpeg(
                "-f", "lavfi", "-i", "testsrc2=size=320x180:rate=24:duration=4",
                "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=48000:duration=4",
                "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "ultrafast",
                "-c:a", "aac", "-b:a", "128k",
                str(clip),
            )

            rc, data, err = self._run_qa("clip", str(clip), "--sheet", str(sheet))
            self.assertEqual(rc, 0, msg=f"err={err}\ndata={data}")
            self.assertTrue(data["ok"])
            self.assertEqual(data["errors"], [])
            self.assertTrue(sheet.is_file())
            raw = sheet.read_bytes()
            self.assertGreater(len(raw), 100)
            self.assertTrue(raw.startswith(PNG_MAGIC))

    def test_black_gap_in_middle_fails_clip_qa(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            clip = tmp / "black_gap.mp4"

            _ffmpeg(
                "-f", "lavfi", "-i", "testsrc2=size=320x180:rate=24:duration=1.5",
                "-f", "lavfi", "-i", "color=c=black:s=320x180:r=24:d=1.0",
                "-f", "lavfi", "-i", "testsrc2=size=320x180:rate=24:duration=1.5",
                "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=48000:duration=4.0",
                "-filter_complex", "[0:v][1:v][2:v]concat=n=3:v=1:a=0[v]",
                "-map", "[v]", "-map", "3:a",
                "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "ultrafast",
                "-c:a", "aac", "-b:a", "128k",
                str(clip),
            )

            rc, data, err = self._run_qa("clip", str(clip))
            self.assertEqual(rc, 1, msg=f"Expected black_gap failure, err={err}\ndata={data}")
            self.assertFalse(data["ok"])
            codes = {e["code"] for e in data.get("errors", [])}
            self.assertIn("black_gap", codes, msg=data)

    def test_frozen_tail_fails_clip_qa(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            clip = tmp / "frozen_tail.mp4"

            # 2.0s motion + 3.2s frozen tail exceeds default 3.0s frozen-tail ceiling
            _ffmpeg(
                "-f", "lavfi", "-i", "testsrc2=size=320x180:rate=24:duration=2.0",
                "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=48000:duration=5.2",
                "-vf", "tpad=stop_mode=clone:stop_duration=3.2",
                "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "ultrafast",
                "-c:a", "aac", "-b:a", "128k",
                str(clip),
            )

            rc, data, err = self._run_qa("clip", str(clip))
            self.assertEqual(rc, 1, msg=f"Expected frozen_tail failure, err={err}\ndata={data}")
            self.assertFalse(data["ok"])
            codes = {e["code"] for e in data.get("errors", [])}
            self.assertIn("frozen_tail", codes, msg=data)

    def test_fully_static_clip_fails_clip_qa(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            clip = tmp / "fully_static.mp4"

            _ffmpeg(
                "-f", "lavfi", "-i", "color=c=0x446688:s=320x180:r=24:d=4.0",
                "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=48000:duration=4.0",
                "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "ultrafast",
                "-c:a", "aac", "-b:a", "128k",
                str(clip),
            )

            rc, data, err = self._run_qa("clip", str(clip))
            self.assertEqual(rc, 1, msg=f"Expected fully_static_clip failure, err={err}\ndata={data}")
            self.assertFalse(data["ok"])
            codes = {e["code"] for e in data.get("errors", [])}
            self.assertIn("fully_static_clip", codes, msg=data)

    def test_two_second_hold_passes_clip_qa(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            clip = tmp / "closing_hold_2s.mp4"

            # 3.0s motion + 2.0s deliberate closing button hold stays under default 3.0s ceiling
            _ffmpeg(
                "-f", "lavfi", "-i", "testsrc2=size=320x180:rate=24:duration=3.0",
                "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=48000:duration=5.0",
                "-vf", "tpad=stop_mode=clone:stop_duration=2.0",
                "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "ultrafast",
                "-c:a", "aac", "-b:a", "128k",
                str(clip),
            )

            rc, data, err = self._run_qa("clip", str(clip))
            self.assertEqual(rc, 0, msg=f"Expected 2.0s closing hold to pass, err={err}\ndata={data}")
            self.assertTrue(data["ok"])
            self.assertEqual(data["errors"], [])

    def test_voice_window_passes_for_4s_and_fails_for_4_95s(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            good_vo = tmp / "vo_4s.wav"
            long_vo = tmp / "vo_4_95s.wav"

            _ffmpeg(
                "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=48000:duration=4.0",
                str(good_vo),
            )
            _ffmpeg(
                "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=48000:duration=4.95",
                str(long_vo),
            )

            rc_ok, data_ok, err_ok = self._run_qa("voice", str(good_vo), "--window", "5")
            self.assertEqual(rc_ok, 0, msg=f"err={err_ok}\ndata={data_ok}")
            self.assertTrue(data_ok["ok"])

            rc_bad, data_bad, err_bad = self._run_qa("voice", str(long_vo), "--window", "5")
            self.assertEqual(rc_bad, 1, msg=f"err={err_bad}\ndata={data_bad}")
            self.assertFalse(data_bad["ok"])
            codes = {e["code"] for e in data_bad.get("errors", [])}
            self.assertIn("voice_too_long", codes, msg=data_bad)

    def test_assemble_end_to_end_and_render_qa(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            clip1 = tmp / "clip1.mp4"
            clip2 = tmp / "clip2.mp4"
            music = tmp / "music.wav"
            master = tmp / "exports" / "master.mp4"
            stems_dir = tmp / "exports" / "stems"
            sheet = tmp / "exports" / "master_sheet.png"

            _ffmpeg(
                "-f", "lavfi", "-i", "testsrc2=size=320x180:rate=24:duration=3",
                "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=48000:duration=3",
                "-af", "volume=-18dB",
                "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "ultrafast",
                "-c:a", "aac", "-b:a", "128k",
                str(clip1),
            )
            _ffmpeg(
                "-f", "lavfi", "-i", "testsrc2=size=320x180:rate=24:duration=3",
                "-f", "lavfi", "-i", "sine=frequency=523:sample_rate=48000:duration=3",
                "-af", "volume=-18dB",
                "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "ultrafast",
                "-c:a", "aac", "-b:a", "128k",
                str(clip2),
            )
            _ffmpeg(
                "-f", "lavfi", "-i", "sine=frequency=220:sample_rate=48000:duration=6",
                "-af", "volume=-14dB",
                str(music),
            )

            proc = subprocess.run(
                [
                    "bash",
                    str(ASSEMBLE_SCRIPT),
                    "--clips",
                    f"{clip1},{clip2}",
                    "--music",
                    str(music),
                    "--music-vol",
                    "0.14",
                    "--out",
                    str(master),
                    "--stems-dir",
                    str(stems_dir),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(
                proc.returncode,
                0,
                msg=f"assemble.sh failed:\nstdout={proc.stdout}\nstderr={proc.stderr}",
            )
            self.assertTrue(master.is_file(), "master.mp4 was not created")
            self.assertTrue(stems_dir.is_dir(), "stems directory was not created")
            stem_files = [p for p in stems_dir.iterdir() if p.is_file()]
            self.assertGreater(len(stem_files), 0, "stems directory is empty")

            probe = _ffprobe_json(master)
            streams = probe.get("streams") or []
            vstream = next((s for s in streams if s.get("codec_type") == "video"), None)
            astream = next((s for s in streams if s.get("codec_type") == "audio"), None)
            self.assertIsNotNone(vstream, msg=probe)
            self.assertIsNotNone(astream, msg=probe)
            self.assertEqual(vstream["codec_name"], "h264")
            self.assertEqual(astream["codec_name"], "aac")

            rc, data, err = self._run_qa("render", str(master), "--sheet", str(sheet))
            self.assertEqual(rc, 0, msg=f"render QA failed: err={err}\ndata={data}")
            self.assertTrue(data["ok"], msg=data)
            self.assertEqual(data["errors"], [])
            lufs = data["loudness"]["integrated_lufs"]
            self.assertIsNotNone(lufs)
            self.assertGreaterEqual(lufs, -16.0)
            self.assertLessEqual(lufs, -12.0)
            self.assertTrue(sheet.is_file())
            self.assertTrue(sheet.read_bytes().startswith(PNG_MAGIC))

    def test_assemble_manifest_autoloads_music_and_rejects_silent_audio(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            camp = tmp / "camp"
            shots_dir = camp / "media" / "shots"
            audio_dir = camp / "media" / "audio"
            shots_dir.mkdir(parents=True, exist_ok=True)
            audio_dir.mkdir(parents=True, exist_ok=True)

            clip1 = shots_dir / "s01.mp4"
            clip2 = shots_dir / "s02.mp4"
            music = audio_dir / "score.wav"
            silent_music = audio_dir / "silent_score.wav"

            # Video-only clips (-an) prove audible mix comes strictly from manifest music
            _ffmpeg(
                "-f", "lavfi", "-i", "testsrc2=size=320x180:rate=24:duration=3",
                "-an", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "ultrafast",
                str(clip1),
            )
            _ffmpeg(
                "-f", "lavfi", "-i", "testsrc2=size=320x180:rate=24:duration=3",
                "-an", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "ultrafast",
                str(clip2),
            )
            _ffmpeg(
                "-f", "lavfi", "-i", "sine=frequency=220:sample_rate=48000:duration=6",
                str(music),
            )
            _ffmpeg(
                "-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=48000:d=6",
                str(silent_music),
            )

            manifest = camp / "shotlist.json"
            manifest.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "campaign": "autoload-test",
                        "shots": [
                            {"id": "s01", "duration_s": 3, "video": {"selected_take": "media/shots/s01.mp4"}},
                            {"id": "s02", "duration_s": 3, "video": {"selected_take": "media/shots/s02.mp4"}},
                        ],
                        "audio": {
                            "music": {
                                "enabled": True,
                                "selected_file": "media/audio/score.wav",
                            },
                            "voiceover": {
                                "enabled": False,
                                "tracks": [],
                            },
                        },
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )

            master = camp / "media" / "exports" / "master.mp4"
            stems_dir = camp / "media" / "exports" / "stems"
            proc_ok = subprocess.run(
                [
                    "bash",
                    str(ASSEMBLE_SCRIPT),
                    "--campaign",
                    str(camp),
                    "--manifest",
                    str(manifest),
                    "--out",
                    str(master),
                    "--stems-dir",
                    str(stems_dir),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(
                proc_ok.returncode,
                0,
                msg=f"manifest autoload assemble failed:\nstdout={proc_ok.stdout}\nstderr={proc_ok.stderr}",
            )
            self.assertTrue(master.is_file())
            self.assertTrue((stems_dir / "music.wav").is_file(), "Expected autoloaded music.wav stem")

            rc_qa, qa_data, qa_err = self._run_qa("render", str(master))
            self.assertEqual(rc_qa, 0, msg=f"err={qa_err}\ndata={qa_data}")
            self.assertTrue(qa_data["ok"])
            self.assertIsNotNone(qa_data["loudness"]["integrated_lufs"])

            # Passing a completely silent --music track must fail loudly rather than injecting --allow-silent
            bad_master = camp / "media" / "exports" / "silent_fail.mp4"
            proc_bad = subprocess.run(
                [
                    "bash",
                    str(ASSEMBLE_SCRIPT),
                    "--clips",
                    f"{clip1},{clip2}",
                    "--music",
                    str(silent_music),
                    "--out",
                    str(bad_master),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertNotEqual(
                proc_bad.returncode,
                0,
                msg=f"Expected assemble.sh to fail loudly on silent --music track, got stdout={proc_bad.stdout}",
            )

    def test_assemble_animatic_from_stills_and_audio(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            still1 = tmp / "s01.png"
            still2 = tmp / "s02.png"
            music = tmp / "music.wav"
            animatic_silent = tmp / "exports" / "animatic_silent.mp4"
            animatic_music = tmp / "exports" / "animatic_music.mp4"

            _ffmpeg(
                "-f", "lavfi", "-i", "color=c=0x8B5A2B:s=321x181:d=1",
                "-frames:v", "1", str(still1),
            )
            _ffmpeg(
                "-f", "lavfi", "-i", "color=c=0x5C6773:s=320x180:d=1",
                "-frames:v", "1", str(still2),
            )
            _ffmpeg(
                "-f", "lavfi", "-i", "sine=frequency=220:sample_rate=48000:duration=4",
                "-af", "volume=-14dB", str(music),
            )

            proc_silent = subprocess.run(
                [
                    "bash",
                    str(ASSEMBLE_SCRIPT),
                    "--animatic",
                    "--stills",
                    f"{still1}:2,{still2}:2",
                    "--out",
                    str(animatic_silent),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(
                proc_silent.returncode,
                0,
                msg=f"silent animatic failed:\nstdout={proc_silent.stdout}\nstderr={proc_silent.stderr}",
            )
            self.assertTrue(animatic_silent.is_file())

            proc_music = subprocess.run(
                [
                    "bash",
                    str(ASSEMBLE_SCRIPT),
                    "--animatic",
                    "--stills",
                    f"{still1}:2,{still2}:2",
                    "--music",
                    str(music),
                    "--out",
                    str(animatic_music),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(
                proc_music.returncode,
                0,
                msg=f"music animatic failed:\nstdout={proc_music.stdout}\nstderr={proc_music.stderr}",
            )
            self.assertTrue(animatic_music.is_file())
            probe = _ffprobe_json(animatic_music)
            dur = float(probe["format"]["duration"])
            self.assertGreaterEqual(dur, 3.5)
            self.assertLessEqual(dur, 4.5)

    def test_assemble_manifest_vo_only_does_not_swap_into_music(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_str:
            camp = Path(tmp_str)
            shots_dir = camp / "media" / "shots"
            audio_dir = camp / "media" / "audio"
            stems_dir = camp / "media" / "exports" / "stems"
            shots_dir.mkdir(parents=True)
            audio_dir.mkdir(parents=True)

            clip1 = shots_dir / "s01-t01.mp4"
            vo_file = audio_dir / "vo_full.wav"
            master = camp / "media" / "exports" / "master_vo.mp4"

            _ffmpeg(
                "-f", "lavfi", "-i", "testsrc2=size=320x180:rate=24:duration=4",
                "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "ultrafast",
                str(clip1),
            )
            _ffmpeg(
                "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=48000:duration=4",
                "-af", "volume=-16dB", str(vo_file),
            )

            manifest = {
                "schema_version": 1,
                "campaign": "vo-only-manifest-test",
                "aspect_ratio": "16:9",
                "target_duration_s": 4,
                "fps_target": 24,
                "shots": [
                    {
                        "id": "s01",
                        "duration_s": 4,
                        "video": {"selected_take": "media/shots/s01-t01.mp4"},
                    }
                ],
                "audio": {
                    "music": {"enabled": False, "selected_file": None},
                    "voiceover": {"enabled": True, "selected_file": "media/audio/vo_full.wav"},
                },
            }
            manifest_path = camp / "shotlist.json"
            manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

            proc = subprocess.run(
                [
                    "bash",
                    str(ASSEMBLE_SCRIPT),
                    "--campaign",
                    str(camp),
                    "--manifest",
                    str(manifest_path),
                    "--out",
                    str(master),
                    "--stems-dir",
                    str(stems_dir),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(
                proc.returncode,
                0,
                msg=f"VO-only manifest assemble failed:\nstdout={proc.stdout}\nstderr={proc.stderr}",
            )
            self.assertTrue(master.is_file())
            self.assertTrue((stems_dir / "vo.wav").is_file(), "VO must be preserved in stems/vo.wav")
            self.assertFalse(
                (stems_dir / "music.wav").exists(),
                "VO-only manifest must NOT misassign VO into stems/music.wav",
            )

    def test_lookbook_grid_stitches_mixed_size_images_with_labels(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            img_a = tmp / "variant_a.png"
            img_b = tmp / "variant_b.png"
            img_c = tmp / "variant_c.png"
            lookbook_png = tmp / "lookbook.png"

            _ffmpeg(
                "-f", "lavfi", "-i", "color=c=0x8B5A2B:s=320x180:d=1",
                "-frames:v", "1", str(img_a),
            )
            _ffmpeg(
                "-f", "lavfi", "-i", "color=c=0x5C6773:s=400x300:d=1",
                "-frames:v", "1", str(img_b),
            )
            _ffmpeg(
                "-f", "lavfi", "-i", "color=c=0x2B2E31:s=256x256:d=1",
                "-frames:v", "1", str(img_c),
            )

            rc, data, err = self._run_qa(
                "lookbook",
                str(img_a),
                str(img_b),
                str(img_c),
                "--out",
                str(lookbook_png),
                "--labels",
                "A,B,C",
                "--cols",
                "3",
            )
            self.assertEqual(rc, 0, msg=f"lookbook failed: err={err}\ndata={data}")
            self.assertTrue(data["ok"], msg=data)
            self.assertTrue(lookbook_png.is_file(), "lookbook.png was not created")
            raw = lookbook_png.read_bytes()
            self.assertGreater(len(raw), 100)
            self.assertTrue(raw.startswith(PNG_MAGIC), "lookbook output is not a valid PNG")

            slots = data.get("slots")
            self.assertIsInstance(slots, list, msg=data)
            self.assertEqual(len(slots), 3, msg=data)
            labels = [s["label"] if isinstance(s, dict) else s for s in slots]
            self.assertEqual(labels, ["A", "B", "C"], msg=data)

    def test_lookbook_draws_distinct_visual_labels_and_rejects_bad_labels(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            img_a = tmp / "solid_a.png"
            img_b = tmp / "solid_b.png"
            img_c = tmp / "solid_c.png"
            lookbook_png = tmp / "lookbook_ab.png"

            # Identical solid-color inputs prove pixel differences come strictly from rendered labels
            for p in (img_a, img_b, img_c):
                _ffmpeg(
                    "-f", "lavfi", "-i", "color=c=0x8B5A2B:s=320x180:d=1",
                    "-frames:v", "1", str(p),
                )

            rc, data, err = self._run_qa(
                "lookbook",
                str(img_a),
                str(img_b),
                "--out",
                str(lookbook_png),
                "--labels",
                "A,B",
                "--cols",
                "2",
            )
            self.assertEqual(rc, 0, msg=f"lookbook A/B failed: err={err}\ndata={data}")
            self.assertTrue(data["ok"], msg=data)
            self.assertTrue(lookbook_png.is_file())
            self.assertTrue(lookbook_png.read_bytes().startswith(PNG_MAGIC))

            tile_w = int(data["tile_width"])
            tile_h = int(data["tile_height"])
            out_w = int(data["output_width"])
            out_h = int(data["output_height"])
            margin = (out_h - tile_h) // 2
            x0 = margin
            x1 = out_w - margin - tile_w
            crop_w = min(tile_w, 120)
            crop_h = min(tile_h, 80)

            def _crop_rgb(x: int, y: int) -> bytes:
                proc = subprocess.run(
                    [
                        "ffmpeg",
                        "-v",
                        "error",
                        "-i",
                        str(lookbook_png),
                        "-vf",
                        f"crop={crop_w}:{crop_h}:{x}:{y}",
                        "-f",
                        "rawvideo",
                        "-pix_fmt",
                        "rgb24",
                        "-",
                    ],
                    capture_output=True,
                    check=True,
                )
                return proc.stdout

            corner_a = _crop_rgb(x0, margin)
            corner_b = _crop_rgb(x1, margin)
            self.assertEqual(len(corner_a), crop_w * crop_h * 3)
            self.assertEqual(len(corner_b), crop_w * crop_h * 3)
            self.assertNotEqual(
                corner_a,
                corner_b,
                "Top-left corners of identical tiles labeled A vs B must render distinct pixels",
            )
            diff_pixels = sum(
                1
                for i in range(0, len(corner_a), 3)
                if corner_a[i : i + 3] != corner_b[i : i + 3]
            )
            self.assertGreater(
                diff_pixels,
                20,
                msg=f"Expected distinct visible glyph pixels between A and B, got {diff_pixels} diff px",
            )

            # Reject empty label entry ("A,,C")
            rc_empty, data_empty, _ = self._run_qa(
                "lookbook",
                str(img_a),
                str(img_b),
                str(img_c),
                "--out",
                str(tmp / "bad_empty.png"),
                "--labels",
                "A,,C",
                "--cols",
                "3",
            )
            self.assertNotEqual(rc_empty, 0, msg=f"Expected empty label rejection: {data_empty}")
            self.assertFalse(data_empty.get("ok", True))

            # Reject mismatched label count ("A,B" for 3 images)
            rc_len, data_len, _ = self._run_qa(
                "lookbook",
                str(img_a),
                str(img_b),
                str(img_c),
                "--out",
                str(tmp / "bad_len.png"),
                "--labels",
                "A,B",
                "--cols",
                "3",
            )
            self.assertNotEqual(rc_len, 0, msg=f"Expected mismatched label length rejection: {data_len}")
            self.assertFalse(data_len.get("ok", True))

            # Reject duplicate labels ("A,A" for 2 images)
            rc_dup, data_dup, _ = self._run_qa(
                "lookbook",
                str(img_a),
                str(img_b),
                "--out",
                str(tmp / "bad_dup.png"),
                "--labels",
                "A,A",
                "--cols",
                "2",
            )
            self.assertNotEqual(rc_dup, 0, msg=f"Expected duplicate label rejection: {data_dup}")
            self.assertFalse(data_dup.get("ok", True))

    def test_assemble_manifest_respects_fps_target_vo_window_s_and_no_loudnorm(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_str:
            camp = Path(tmp_str)
            shots_dir = camp / "media" / "shots"
            audio_dir = camp / "media" / "audio"
            stems_dir = camp / "media" / "exports" / "stems"
            shots_dir.mkdir(parents=True)
            audio_dir.mkdir(parents=True)

            # Input clip is 24fps while manifest requests fps_target: 30
            clip1 = shots_dir / "s01-24fps.mp4"
            vo_late = audio_dir / "vo_late.wav"
            master = camp / "media" / "exports" / "master_30fps.mp4"

            _ffmpeg(
                "-f", "lavfi", "-i", "testsrc2=size=320x180:rate=24:duration=4",
                "-an", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "ultrafast",
                str(clip1),
            )
            # Quiet -28dB 1.5s VO track placed at window_s "2.0-4.0" proves both window_s delay and --no-loudnorm
            _ffmpeg(
                "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=48000:duration=1.5",
                "-af", "volume=-28dB",
                str(vo_late),
            )

            manifest = {
                "schema_version": 1,
                "campaign": "fps-window-noloudnorm-test",
                "aspect_ratio": "16:9",
                "target_duration_s": 4,
                "fps_target": 30,
                "shots": [
                    {
                        "id": "s01",
                        "duration_s": 4,
                        "video": {"selected_take": "media/shots/s01-24fps.mp4"},
                    }
                ],
                "audio": {
                    "music": {"enabled": False, "selected_file": None},
                    "voiceover": {
                        "enabled": True,
                        "tracks": [
                            {
                                "id": "vo01",
                                "selected_file": "media/audio/vo_late.wav",
                                "window_s": "2.0-4.0",
                            }
                        ],
                    },
                },
            }
            manifest_path = camp / "shotlist.json"
            manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

            proc = subprocess.run(
                [
                    "bash",
                    str(ASSEMBLE_SCRIPT),
                    "--campaign",
                    str(camp),
                    "--manifest",
                    str(manifest_path),
                    "--out",
                    str(master),
                    "--stems-dir",
                    str(stems_dir),
                    "--no-loudnorm",
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(
                proc.returncode,
                0,
                msg=f"assemble.sh --no-loudnorm with fps_target=30 & window_s failed:\nstdout={proc.stdout}\nstderr={proc.stderr}",
            )
            self.assertTrue(master.is_file())
            self.assertTrue((stems_dir / "vo.wav").is_file())

            # Verify output video stream respected manifest fps_target=30
            probe = _ffprobe_json(master)
            vstream = next(
                (s for s in (probe.get("streams") or []) if s.get("codec_type") == "video"),
                None,
            )
            self.assertIsNotNone(vstream, msg=probe)
            rate_str = vstream.get("avg_frame_rate") or vstream.get("r_frame_rate") or "0/1"
            num_s, _, den_s = rate_str.partition("/")
            fps_val = float(num_s) / float(den_s or "1")
            self.assertAlmostEqual(fps_val, 30.0, delta=0.2, msg=f"Expected 30fps, got {rate_str}")

            # Verify vo.wav absorbed window_s start offset (2.0s delay + 1.5s clip => ~3.5s)
            vo_probe = _ffprobe_json(stems_dir / "vo.wav")
            vo_dur = float(vo_probe["format"]["duration"])
            self.assertGreaterEqual(
                vo_dur,
                3.3,
                msg=f"Expected window_s '2.0-4.0' delay on 1.5s VO (>=3.3s), got {vo_dur}s",
            )

    def test_clip_qa_crops_strip_and_upscale_quality_warnings(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            clip_bad = tmp / "upscaled_1918x1080.mp4"
            crops_png = tmp / "crops.png"

            # Synthetic 1918x1080 (non-multiple-of-4 rounding) low-bitrate HD clip
            _ffmpeg(
                "-f", "lavfi", "-i", "testsrc2=size=1918x1080:rate=24:duration=2",
                "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=48000:duration=2",
                "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "ultrafast",
                "-b:v", "400k", "-maxrate", "400k", "-bufsize", "400k",
                "-c:a", "aac", "-b:a", "128k",
                str(clip_bad),
            )

            rc, data, err = self._run_qa("clip", str(clip_bad), "--crops", str(crops_png))
            self.assertEqual(rc, 0, msg=f"err={err}\ndata={data}")
            self.assertTrue(data["ok"], msg=data)
            self.assertEqual(data["crops"], str(crops_png))
            self.assertTrue(crops_png.is_file(), "1:1 crop strip PNG was not created")
            self.assertTrue(crops_png.read_bytes().startswith(PNG_MAGIC))

            # Unscaled 3x1 strip of 560x560 crops => 1680x560
            cprobe = _ffprobe_json(crops_png)
            cv = next(s for s in cprobe["streams"] if s.get("codec_type") == "video")
            self.assertEqual((int(cv["width"]), int(cv["height"])), (1680, 560))

            self.assertIsNotNone(data["metadata"].get("video_bitrate_kbps"))
            self.assertIsNotNone(data["quality"].get("hf_edge_energy"))
            warn_codes = {w["code"] for w in data.get("warnings", [])}
            self.assertIn("non_standard_dimensions", warn_codes, msg=data)
            self.assertIn("low_video_bitrate", warn_codes, msg=data)

    def test_slice_grid_splits_3x3_sheet_with_trim(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            sheet = tmp / "angles_3x3.png"
            out_dir = tmp / "tiles"

            _ffmpeg(
                "-f", "lavfi", "-i", "testsrc2=size=900x540:duration=1",
                "-frames:v", "1",
                str(sheet),
            )

            rc, data, err = self._run_qa(
                "slice",
                str(sheet),
                "--out-dir",
                str(out_dir),
                "--rows",
                "3",
                "--cols",
                "3",
                "--trim",
                "4",
                "--prefix",
                "loc_room",
            )
            self.assertEqual(rc, 0, msg=f"err={err}\ndata={data}")
            self.assertTrue(data["ok"], msg=data)
            self.assertEqual(data["tile_count"], 9)
            self.assertEqual((data["tile_width"], data["tile_height"]), (292, 172))
            self.assertEqual(len(data["tiles"]), 9)

            first_tile = Path(data["tiles"][0]["file"])
            self.assertEqual(first_tile.name, "loc_room_r0_c0.png")
            self.assertTrue(first_tile.is_file())
            self.assertTrue(first_tile.read_bytes().startswith(PNG_MAGIC))
            tprobe = _ffprobe_json(first_tile)
            tv = next(s for s in tprobe["streams"] if s.get("codec_type") == "video")
            self.assertEqual((int(tv["width"]), int(tv["height"])), (292, 172))

    def test_batch_qa_detects_resolution_fps_and_hf_sharpness_outliers(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            clean_a = tmp / "clean_a.mp4"
            clean_b = tmp / "clean_b.mp4"
            outlier = tmp / "outlier.mp4"

            for out_path in (clean_a, clean_b):
                _ffmpeg(
                    "-f", "lavfi", "-i", "testsrc2=size=1280x720:rate=24:duration=2",
                    "-vf", "gblur=sigma=2.0",
                    "-c:v", "libx264", "-pix_fmt", "yuv420p",
                    str(out_path),
                )

            _ffmpeg(
                "-f", "lavfi", "-i", "testsrc2=size=1278x720:rate=30:duration=2",
                "-vf", "unsharp=5:5:2.0:5:5:0.0",
                "-c:v", "libx264", "-pix_fmt", "yuv420p",
                str(outlier),
            )

            rc_ok, data_ok, err_ok = self._run_qa(
                "batch", str(clean_a), str(clean_b), "--strict",
            )
            self.assertEqual(rc_ok, 0, msg=f"err={err_ok}\ndata={data_ok}")
            self.assertTrue(data_ok["ok"], msg=data_ok)
            self.assertEqual(data_ok["baseline"]["resolution"], "1280x720")
            self.assertEqual(data_ok["warnings"], [])
            self.assertEqual(data_ok["errors"], [])

            rc_bad, data_bad, err_bad = self._run_qa(
                "batch", str(clean_a), str(clean_b), str(outlier), "--strict",
            )
            self.assertEqual(rc_bad, 1, msg=f"err={err_bad}\ndata={data_bad}")
            self.assertFalse(data_bad["ok"], msg=data_bad)
            self.assertEqual(data_bad["baseline"]["resolution"], "1280x720")
            err_codes = {e["code"] for e in data_bad["errors"]}
            warn_codes = {w["code"] for w in data_bad["warnings"]}
            self.assertIn("non_standard_dimensions", err_codes, msg=data_bad)
            self.assertIn("resolution_mismatch", err_codes, msg=data_bad)
            self.assertIn("fps_mismatch", err_codes, msg=data_bad)
            self.assertIn("hf_sharpness_outlier", warn_codes, msg=data_bad)

    def test_assemble_finishing_lut_and_grain_flags(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            clip1 = tmp / "shot1.mp4"
            clip2 = tmp / "shot2.mp4"
            out_plain = tmp / "plain.mp4"
            out_graded = tmp / "graded.mp4"
            stems_dir = tmp / "stems"
            lut_file = tmp / "warm shift.cube"

            # Valid 2x2x2 3D LUT that shifts colors noticeably toward warm tint
            lut_file.write_text(
                "\n".join(
                    [
                        "TITLE \"WarmTest\"",
                        "LUT_3D_SIZE 2",
                        "0.15 0.05 0.00",
                        "1.00 0.15 0.00",
                        "0.15 0.90 0.00",
                        "1.00 0.95 0.05",
                        "0.10 0.05 0.70",
                        "0.95 0.15 0.75",
                        "0.15 0.85 0.70",
                        "1.00 0.95 0.80",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            for clip, freq in ((clip1, 440), (clip2, 520)):
                _ffmpeg(
                    "-f", "lavfi", "-i", "testsrc2=size=640x360:rate=24:duration=2",
                    "-f", "lavfi", "-i", f"sine=frequency={freq}:sample_rate=48000:duration=2",
                    "-c:v", "libx264", "-pix_fmt", "yuv420p",
                    "-c:a", "aac", "-b:a", "128k",
                    "-shortest",
                    str(clip),
                )

            proc_plain = subprocess.run(
                [
                    "bash", str(ASSEMBLE_SCRIPT),
                    "--clips", f"{clip1},{clip2}",
                    "--out", str(out_plain),
                ],
                capture_output=True, text=True, check=False,
            )
            self.assertEqual(
                proc_plain.returncode, 0,
                msg=f"plain assemble failed:\nstdout={proc_plain.stdout}\nstderr={proc_plain.stderr}",
            )

            proc_graded = subprocess.run(
                [
                    "bash", str(ASSEMBLE_SCRIPT),
                    "--clips", f"{clip1},{clip2}",
                    "--lut", str(lut_file),
                    "--grain", "4",
                    "--stems-dir", str(stems_dir),
                    "--out", str(out_graded),
                ],
                capture_output=True, text=True, check=False,
            )
            self.assertEqual(
                proc_graded.returncode, 0,
                msg=f"graded assemble failed:\nstdout={proc_graded.stdout}\nstderr={proc_graded.stderr}",
            )
            self.assertTrue(out_graded.is_file())
            self.assertTrue((stems_dir / "video_only.mp4").is_file())

            def _mid_frame_rgb(mp4: Path) -> bytes:
                p = subprocess.run(
                    [
                        "ffmpeg", "-v", "error", "-ss", "1.0", "-i", str(mp4),
                        "-frames:v", "1", "-f", "rawvideo", "-pix_fmt", "rgb24", "-",
                    ],
                    capture_output=True, check=True,
                )
                return p.stdout

            self.assertNotEqual(
                _mid_frame_rgb(out_plain),
                _mid_frame_rgb(out_graded),
                "Finishing --lut + --grain must visibly modify rendered frames",
            )

            # Invalid --lut path and out-of-range --grain must fail with exit code 2
            proc_bad_lut = subprocess.run(
                [
                    "bash", str(ASSEMBLE_SCRIPT),
                    "--clips", str(clip1),
                    "--lut", str(tmp / "missing.cube"),
                    "--out", str(tmp / "bad1.mp4"),
                ],
                capture_output=True, text=True, check=False,
            )
            self.assertEqual(proc_bad_lut.returncode, 2)

            proc_bad_grain = subprocess.run(
                [
                    "bash", str(ASSEMBLE_SCRIPT),
                    "--clips", str(clip1),
                    "--grain", "99",
                    "--out", str(tmp / "bad2.mp4"),
                ],
                capture_output=True, text=True, check=False,
            )
            self.assertEqual(proc_bad_grain.returncode, 2)

    def test_assemble_per_shot_edit_trim_punchin_grade_duck_overlay_and_pixel_diff(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            camp = tmp / "camp"
            shots_dir = camp / "media" / "shots"
            audio_dir = camp / "media" / "audio"
            shots_dir.mkdir(parents=True, exist_ok=True)
            audio_dir.mkdir(parents=True, exist_ok=True)

            # Generate a 4s moving source clip + VO + music + transparent PNG overlay
            src_clip = shots_dir / "long_take.mp4"
            _ffmpeg(
                "-f", "lavfi", "-i", "testsrc2=size=640x360:rate=24:duration=4",
                "-f", "lavfi", "-i", "sine=frequency=330:sample_rate=48000:duration=4",
                "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest",
                str(src_clip),
            )
            vo_wav = audio_dir / "vo.wav"
            mus_wav = audio_dir / "music.wav"
            _ffmpeg("-f", "lavfi", "-i", "sine=frequency=440:sample_rate=48000:duration=3", "-ac", "2", str(vo_wav))
            _ffmpeg("-f", "lavfi", "-i", "sine=frequency=220:sample_rate=48000:duration=4", "-ac", "2", str(mus_wav))
            overlay_png = tmp / "overlay.png"
            _ffmpeg(
                "-f", "lavfi", "-i", "color=c=white@0.4:s=640x360:d=1",
                "-frames:v", "1", "-pix_fmt", "rgba", str(overlay_png),
            )

            # Harvest two trimmed segments from the SAME source clip, one with 2x center crop + grade + fade-out
            manifest = {
                "schema_version": 1,
                "fps_target": 24,
                "shots": [
                    {
                        "id": "s01",
                        "video": {"selected_take": "media/shots/long_take.mp4"},
                        "edit": {"trim_in": 0.5, "trim_out": 2.0, "grade": {"brightness": -0.02, "saturation": 0.95}},
                    },
                    {
                        "id": "s02",
                        "video": {"selected_take": "media/shots/long_take.mp4"},
                        "edit": {"trim_in": 2.0, "trim_out": 3.5, "crop_4k_punchin": "center_2x", "fade_out_black_s": 0.3},
                    },
                ],
            }
            manifest_path = camp / "shotlist.json"
            manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
            out_mp4 = camp / "media" / "exports" / "master.mp4"

            proc = subprocess.run(
                [
                    "bash", str(ASSEMBLE_SCRIPT),
                    "--campaign", str(camp),
                    "--manifest", str(manifest_path),
                    "--vo", str(vo_wav),
                    "--music", str(mus_wav),
                    "--duck-music",
                    "--overlay", str(overlay_png),
                    "--bpm", "120",
                    "--out", str(out_mp4),
                ],
                capture_output=True, text=True, check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=f"assemble v2 failed:\nstdout={proc.stdout}\nstderr={proc.stderr}")
            rep = json.loads(proc.stdout)
            self.assertTrue(rep["ok"], msg=rep)
            # Trimmed 1.5s + 1.5s = ~3.0s (not 4.0 + 4.0 = 8.0s!)
            self.assertLess(rep["metadata"]["duration"], 3.6)
            self.assertGreater(rep["metadata"]["duration"], 2.4)

            # pixel-diff passes on identical plate and fails on darkened plate
            code_ok, data_ok, comb_ok = self._run_qa("pixel-diff", str(src_clip), "--plate", str(src_clip), "--windows", "1-2")
            self.assertEqual(code_ok, 0, msg=comb_ok)
            self.assertTrue(data_ok["ok"], msg=data_ok)

            dark_clip = tmp / "dark.mp4"
            _ffmpeg(
                "-i", str(src_clip),
                "-vf", "eq=brightness=-0.25", "-c:v", "libx264", "-crf", "18", "-an", str(dark_clip),
            )
            code_bad, data_bad, comb_bad = self._run_qa("pixel-diff", str(dark_clip), "--plate", str(src_clip), "--windows", "1-2")
            self.assertEqual(code_bad, 1, msg=comb_bad)
            self.assertFalse(data_bad["ok"], msg=data_bad)

            # qa_media.py render --verify-slices-dir slices a 3s render into <= 1.5s part_XX.mp4 chunks
            slices_dir = camp / "qc" / "verify_slices"
            rc_sl, sl_data, sl_err = self._run_qa(
                "render",
                str(out_mp4),
                "--verify-slices-dir",
                str(slices_dir),
                "--slice-seconds",
                "1.5",
            )
            self.assertEqual(rc_sl, 0, msg=f"err={sl_err}\ndata={sl_data}")
            self.assertIsInstance(sl_data.get("verify_slices"), list, msg=sl_data)
            self.assertGreaterEqual(len(sl_data["verify_slices"]), 2, msg=sl_data)
            for sp in sl_data["verify_slices"]:
                self.assertTrue(Path(sp).is_file(), f"missing verify slice: {sp}")

    def test_voice_cadence_pause_telemetry_and_vo_track_trim(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            camp = tmp / "camp"
            shots_dir = camp / "media" / "shots"
            audio_dir = camp / "media" / "audio"
            shots_dir.mkdir(parents=True)
            audio_dir.mkdir(parents=True)

            # Build a VO WAV with 0.4s leading silence + 1.0s tone + 0.6s internal silence + 1.0s tone
            vo_pauses = audio_dir / "vo_pauses.wav"
            _ffmpeg(
                "-f", "lavfi", "-i", "anullsrc=r=48000:cl=mono:d=0.4",
                "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=48000:duration=1.0",
                "-f", "lavfi", "-i", "anullsrc=r=48000:cl=mono:d=0.6",
                "-f", "lavfi", "-i", "sine=frequency=520:sample_rate=48000:duration=1.0",
                "-filter_complex", "[0:a][1:a][2:a][3:a]concat=n=4:v=0:a=1[a]",
                "-map", "[a]",
                str(vo_pauses),
            )
            rc_v, v_data, v_err = self._run_qa("voice", str(vo_pauses), "--window", "3.5")
            self.assertEqual(rc_v, 0, msg=f"err={v_err}\ndata={v_data}")
            self.assertGreaterEqual(v_data.get("speech_start", 0.0), 0.3)
            self.assertGreaterEqual(len(v_data.get("internal_pauses") or []), 1, msg=v_data)
            warn_codes = {w["code"] for w in (v_data.get("warnings") or [])}
            self.assertIn("leading_silence", warn_codes, msg=v_data)
            self.assertIn("long_internal_pause", warn_codes, msg=v_data)

            # Verify assemble.sh honors trim_start_s / trim_end_s on audio.voiceover.tracks[]
            clip1 = shots_dir / "s01.mp4"
            _ffmpeg(
                "-f", "lavfi", "-i", "testsrc2=size=320x180:rate=24:duration=3",
                "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "ultrafast",
                str(clip1),
            )
            manifest = {
                "schema_version": 1,
                "fps_target": 24,
                "shots": [{"id": "s01", "duration_s": 3, "video": {"selected_take": "media/shots/s01.mp4"}}],
                "audio": {
                    "music": {"enabled": False, "selected_file": None},
                    "voiceover": {
                        "enabled": True,
                        "tracks": [
                            {
                                "selected_file": "media/audio/vo_pauses.wav",
                                "start_s": 0.0,
                                "trim_start_s": 0.4,
                                "trim_end_s": 1.4,
                            }
                        ],
                    },
                },
            }
            manifest_path = camp / "shotlist.json"
            manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
            out_mp4 = camp / "media" / "exports" / "master_trim.mp4"
            stems_dir = camp / "media" / "exports" / "stems"
            proc = subprocess.run(
                [
                    "bash", str(ASSEMBLE_SCRIPT),
                    "--campaign", str(camp),
                    "--manifest", str(manifest_path),
                    "--out", str(out_mp4),
                    "--stems-dir", str(stems_dir),
                ],
                capture_output=True, text=True, check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=f"VO trim assemble failed:\nstdout={proc.stdout}\nstderr={proc.stderr}")
            # Trimmed VO stem should start speaking right at 0.0s with ~1.0s duration (leading 0.4s removed!)
            rc_t, t_data, t_err = self._run_qa("voice", str(stems_dir / "vo.wav"), "--window", "1.5")
            self.assertEqual(rc_t, 0, msg=f"err={t_err}\ndata={t_data}")
            self.assertLessEqual(t_data.get("speech_start", 1.0), 0.1, msg=t_data)
            self.assertLessEqual(t_data.get("speech_end", 9.0), 1.25, msg=t_data)


    def test_non_div4_dims_warning_on_clip_render_and_batch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            clean_clip = tmp / "clean_320x240.mp4"
            non_div4_clip = tmp / "odd_322x240.mp4"

            _ffmpeg(
                "-f", "lavfi", "-i", "testsrc2=size=320x240:rate=24:duration=3.5",
                "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=48000:duration=3.5",
                "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "ultrafast",
                "-c:a", "aac", "-b:a", "128k",
                str(clean_clip),
            )
            _ffmpeg(
                "-f", "lavfi", "-i", "testsrc2=size=322x240:rate=24:duration=3.5",
                "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=48000:duration=3.5",
                "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "ultrafast",
                "-c:a", "aac", "-b:a", "128k",
                str(non_div4_clip),
            )

            rc_ok, data_ok, err_ok = self._run_qa("clip", str(clean_clip))
            self.assertEqual(rc_ok, 0, msg=f"err={err_ok}\ndata={data_ok}")
            self.assertTrue(data_ok["ok"], msg=data_ok)
            self.assertNotIn(
                "non_div4_dims",
                {w["code"] for w in data_ok.get("warnings", [])},
                msg=data_ok,
            )

            rc_odd, data_odd, err_odd = self._run_qa("clip", str(non_div4_clip))
            self.assertEqual(rc_odd, 0, msg=f"err={err_odd}\ndata={data_odd}")
            self.assertTrue(data_odd["ok"], msg=data_odd)
            div4_warns = [w for w in data_odd.get("warnings", []) if w["code"] == "non_div4_dims"]
            self.assertEqual(len(div4_warns), 1, msg=data_odd)
            self.assertEqual((div4_warns[0]["width"], div4_warns[0]["height"]), (322, 240))
            self.assertIn("topaz_hyperion_2_5", div4_warns[0]["message"])
            self.assertIn("1918x1080", div4_warns[0]["message"])

            rc_rn, data_rn, err_rn = self._run_qa(
                "render", str(non_div4_clip), "--no-loudness-check"
            )
            self.assertEqual(rc_rn, 0, msg=f"err={err_rn}\ndata={data_rn}")
            self.assertTrue(data_rn["ok"], msg=data_rn)
            self.assertIn(
                "non_div4_dims",
                {w["code"] for w in data_rn.get("warnings", [])},
                msg=data_rn,
            )

            rc_bt, data_bt, err_bt = self._run_qa("batch", str(non_div4_clip))
            self.assertEqual(rc_bt, 0, msg=f"err={err_bt}\ndata={data_bt}")
            self.assertIn(
                "non_div4_dims",
                {w["code"] for w in data_bt.get("warnings", [])},
                msg=data_bt,
            )

    def test_locked_still_drift_detector_passes_clean_and_fails_drifting_tail(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            clean_still = tmp / "locked_clean.mp4"
            drifting_still = tmp / "locked_drift.mp4"

            # Clean locked living still: uniform matte stone plate + subtle 35mm grain only
            _ffmpeg(
                "-f", "lavfi", "-i", "color=c=0x88847C:s=320x180:r=24:d=4.0",
                "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=48000:duration=4.0",
                "-vf", "noise=c0s=2:c0f=t+u",
                "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "ultrafast",
                "-c:a", "aac", "-b:a", "128k",
                str(clean_still),
            )

            # Drifting locked still: first 2.6s clean, final third adds bright flare bar + shifts luminance
            _ffmpeg(
                "-f", "lavfi", "-i", "color=c=0x606060:s=320x180:r=24:d=2.6",
                "-f", "lavfi", "-i", "color=c=0x484848:s=320x180:r=24:d=1.4",
                "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=48000:duration=4.0",
                "-filter_complex",
                "[0:v]noise=c0s=2:c0f=t+u[v0];"
                "[1:v]drawbox=x=20:y=20:w=280:h=50:color=0xFFFFFF:t=fill,noise=c0s=2:c0f=t+u[v1];"
                "[v0][v1]concat=n=2:v=1:a=0[v]",
                "-map", "[v]", "-map", "2:a",
                "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "ultrafast",
                "-c:a", "aac", "-b:a", "128k",
                str(drifting_still),
            )

            # Without --locked-still, a clean locked still fails normal static-clip checks
            rc_default, data_default, _ = self._run_qa("clip", str(clean_still))
            self.assertEqual(rc_default, 1, msg=data_default)
            self.assertIn(
                "fully_static_clip",
                {e["code"] for e in data_default.get("errors", [])},
                msg=data_default,
            )

            # With --locked-still, clean living still suppresses static errors and passes drift check
            rc_ok, data_ok, err_ok = self._run_qa("clip", str(clean_still), "--locked-still")
            self.assertEqual(rc_ok, 0, msg=f"err={err_ok}\ndata={data_ok}")
            self.assertTrue(data_ok["ok"], msg=data_ok)
            self.assertEqual(data_ok["errors"], [], msg=data_ok)
            lsc_ok = data_ok.get("locked_still_check") or {}
            self.assertTrue(lsc_ok.get("enabled"), msg=data_ok)
            self.assertTrue(lsc_ok.get("passed"), msg=data_ok)
            self.assertLess(lsc_ok.get("max_tile_drift", 999.0), 5.0, msg=lsc_ok)
            self.assertLess(lsc_ok.get("tail_drift", 999.0), 5.0, msg=lsc_ok)
            self.assertLess(lsc_ok.get("mean_luma_shift", 999.0), 3.0, msg=lsc_ok)

            # Drifting final third must FAIL mechanically with locked_still_drift
            rc_bad, data_bad, err_bad = self._run_qa("clip", str(drifting_still), "--locked-still")
            self.assertEqual(rc_bad, 1, msg=f"Expected locked_still_drift failure, err={err_bad}\ndata={data_bad}")
            self.assertFalse(data_bad["ok"], msg=data_bad)
            err_codes = {e["code"] for e in data_bad.get("errors", [])}
            self.assertIn("locked_still_drift", err_codes, msg=data_bad)
            self.assertNotIn("fully_static_clip", err_codes, msg=data_bad)
            lsc_bad = data_bad.get("locked_still_check") or {}
            self.assertTrue(lsc_bad.get("enabled"), msg=data_bad)
            self.assertFalse(lsc_bad.get("passed"), msg=data_bad)
            self.assertGreater(lsc_bad.get("max_tile_drift", 0.0), 12.0, msg=lsc_bad)
            self.assertGreater(lsc_bad.get("tail_drift", 0.0), 12.0, msg=lsc_bad)

            # Invalid --drift-threshold fails cleanly with exit code 2
            rc_inv, _, _ = self._run_qa(
                "clip", str(clean_still), "--locked-still", "--drift-threshold", "0"
            )
            self.assertEqual(rc_inv, 2)

    def test_assemble_mixed_still_only_and_video_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_str:
            camp = Path(tmp_str)
            stills_dir = camp / "media" / "stills"
            shots_dir = camp / "media" / "shots"
            audio_dir = camp / "media" / "audio"
            stems_dir = camp / "media" / "exports" / "stems"
            stills_dir.mkdir(parents=True)
            shots_dir.mkdir(parents=True)
            audio_dir.mkdir(parents=True)

            still1 = stills_dir / "s01.png"
            clip2 = shots_dir / "s02.mp4"
            still3 = stills_dir / "s03.png"
            music = audio_dir / "score.wav"
            master = camp / "media" / "exports" / "mixed_master.mp4"

            # Shot 1 is a 640x360 still_only plate; Shot 2 is a 320x180@24fps video clip
            _ffmpeg(
                "-f", "lavfi", "-i", "color=c=0x8B5A2B:s=640x360:d=1",
                "-frames:v", "1", str(still1),
            )
            _ffmpeg(
                "-f", "lavfi", "-i", "testsrc2=size=320x180:rate=24:duration=3.0",
                "-an", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "ultrafast",
                str(clip2),
            )
            _ffmpeg(
                "-f", "lavfi", "-i", "color=c=0x2B4C7E:s=640x360:d=1",
                "-frames:v", "1", str(still3),
            )
            _ffmpeg(
                "-f", "lavfi", "-i", "sine=frequency=220:sample_rate=48000:duration=4.5",
                "-af", "volume=-14dB", str(music),
            )

            manifest = {
                "schema_version": 1,
                "campaign": "mixed-still-video-test",
                "aspect_ratio": "16:9",
                "target_duration_s": 4,
                "fps_target": 24,
                "shots": [
                    {
                        "id": "s01",
                        "duration_s": 0.5,
                        "still_only": True,
                        "still": {"selected_take": "media/stills/s01.png"},
                        "video": None,
                    },
                    {
                        "id": "s02",
                        "duration_s": 3.0,
                        "video": {"selected_take": "media/shots/s02.mp4"},
                    },
                    {
                        "id": "s03",
                        "duration_s": 0.5,
                        "still": {"selected_take": "media/stills/s03.png"},
                        "video": None,
                    },
                ],
                "audio": {
                    "music": {"enabled": True, "selected_file": "media/audio/score.wav"},
                    "voiceover": {"enabled": False, "tracks": []},
                },
            }
            manifest_path = camp / "shotlist.json"
            manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

            proc = subprocess.run(
                [
                    "bash", str(ASSEMBLE_SCRIPT),
                    "--campaign", str(camp),
                    "--manifest", str(manifest_path),
                    "--out", str(master),
                    "--stems-dir", str(stems_dir),
                ],
                capture_output=True, text=True, check=False,
            )
            self.assertEqual(
                proc.returncode,
                0,
                msg=f"mixed still+video assemble failed:\nstdout={proc.stdout}\nstderr={proc.stderr}",
            )
            self.assertTrue(master.is_file())
            for stem in ("clip_01.mp4", "clip_02.mp4", "clip_03.mp4", "video_only.mp4", "music.wav"):
                self.assertTrue((stems_dir / stem).is_file(), msg=f"Missing stem {stem}")

            probe = _ffprobe_json(master)
            vstream = next(s for s in probe["streams"] if s.get("codec_type") == "video")
            # Probing prefers first video clip (320x180) even though shot 1 is still_only (640x360)
            self.assertEqual((int(vstream["width"]), int(vstream["height"])), (320, 180))
            dur = float(probe["format"]["duration"])
            self.assertGreaterEqual(dur, 3.7)
            self.assertLessEqual(dur, 4.3)

            # Verify all-still manifest (no video clips) falls back cleanly to still 1 + fps_target
            all_still_manifest = camp / "all_still_shotlist.json"
            all_still_manifest.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "campaign": "all-still-test",
                        "aspect_ratio": "16:9",
                        "fps_target": 30,
                        "shots": [
                            {
                                "id": "s01",
                                "duration_s": 0.5,
                                "still_only": True,
                                "still": {"selected_take": "media/stills/s01.png"},
                            },
                            {
                                "id": "s02",
                                "duration_s": 0.5,
                                "still_only": True,
                                "still": {"selected_take": "media/stills/s03.png"},
                            },
                        ],
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )
            all_still_out = camp / "media" / "exports" / "all_still.mp4"
            proc_stills = subprocess.run(
                [
                    "bash", str(ASSEMBLE_SCRIPT),
                    "--campaign", str(camp),
                    "--manifest", str(all_still_manifest),
                    "--allow-silent",
                    "--out", str(all_still_out),
                ],
                capture_output=True, text=True, check=False,
            )
            self.assertEqual(
                proc_stills.returncode,
                0,
                msg=f"all-still manifest failed:\nstdout={proc_stills.stdout}\nstderr={proc_stills.stderr}",
            )
            st_probe = _ffprobe_json(all_still_out)
            st_v = next(s for s in st_probe["streams"] if s.get("codec_type") == "video")
            self.assertEqual((int(st_v["width"]), int(st_v["height"])), (640, 360))
            rate_s = st_v.get("avg_frame_rate") or "0/1"
            num_s, _, den_s = rate_s.partition("/")
            self.assertAlmostEqual(float(num_s) / float(den_s or "1"), 30.0, delta=0.5)

    def test_assemble_post_lut_overlay_and_endcard(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            clip1 = tmp / "main.mp4"
            lut_file = tmp / "invert.cube"
            ov_mov = tmp / "overlay_prores4444.mov"
            ov_png = tmp / "overlay_halfres.png"
            endcard = tmp / "endcard.mp4"
            out_mov = tmp / "master_mov_endcard.mp4"
            out_png = tmp / "master_png.mp4"

            # Exact 2x2x2 inverting LUT: (R,G,B) -> (1-R, 1-G, 1-B)
            lut_file.write_text(
                "\n".join(
                    [
                        'TITLE "InvertTest"',
                        "LUT_3D_SIZE 2",
                        "1.00 1.00 1.00",
                        "0.00 1.00 1.00",
                        "1.00 0.00 1.00",
                        "0.00 0.00 1.00",
                        "1.00 1.00 0.00",
                        "0.00 1.00 0.00",
                        "1.00 0.00 0.00",
                        "0.00 0.00 0.00",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            # Main 3s clip: moving testsrc2 with a solid dark-red patch at x=180..300, y=40..140
            _ffmpeg(
                "-f", "lavfi", "-i", "testsrc2=size=320x180:rate=24:duration=3.0",
                "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=48000:duration=3.0",
                "-vf", "drawbox=x=180:y=40:w=120:h=100:color=0xCC2020:t=fill",
                "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "ultrafast",
                "-c:a", "aac", "-b:a", "128k",
                str(clip1),
            )

            # Transparent ProRes 4444 overlay with pure green box at x=20..100, y=20..100
            ov_mov_src = (
                "color=c=black:s=320x180:r=24:d=3.0,format=rgba,"
                "geq=r='0':g='if(between(X,20,100)*between(Y,20,100),255,0)':"
                "b='0':a='if(between(X,20,100)*between(Y,20,100),255,0)'"
            )
            _ffmpeg(
                "-f", "lavfi", "-i", ov_mov_src,
                "-c:v", "prores_ks", "-profile:v", "4444", "-pix_fmt", "yuva444p10le",
                str(ov_mov),
            )

            # Half-res transparent PNG overlay (160x90 -> scaled to 320x180) with pure green box at x=10..50, y=10..50
            ov_png_src = (
                "color=c=black:s=160x90:d=1,format=rgba,"
                "geq=r='0':g='if(between(X,10,50)*between(Y,10,50),255,0)':"
                "b='0':a='if(between(X,10,50)*between(Y,10,50),255,0)'"
            )
            _ffmpeg(
                "-f", "lavfi", "-i", ov_png_src,
                "-frames:v", "1",
                str(ov_png),
            )

            # 2s video-only brand endcard in pure royal blue (20, 50, 235)
            _ffmpeg(
                "-f", "lavfi", "-i", "color=c=0x1432EB:s=320x180:r=24:d=2.0",
                "-an", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "ultrafast",
                str(endcard),
            )

            def _sample_rgb(mp4: Path, ts: float, x: int, y: int) -> tuple[int, int, int]:
                raw = subprocess.run(
                    [
                        "ffmpeg", "-v", "error", "-ss", f"{ts:.2f}", "-i", str(mp4),
                        "-frames:v", "1", "-f", "rawvideo", "-pix_fmt", "rgb24", "-",
                    ],
                    capture_output=True, check=True,
                ).stdout
                off = (y * 320 + x) * 3
                return raw[off], raw[off + 1], raw[off + 2]

            # Test 1: --lut + --grain + ProRes 4444 --overlay + --endcard
            proc_mov = subprocess.run(
                [
                    "bash", str(ASSEMBLE_SCRIPT),
                    "--clips", str(clip1),
                    "--lut", str(lut_file),
                    "--grain", "3",
                    "--overlay", str(ov_mov),
                    "--endcard", str(endcard),
                    "--out", str(out_mov),
                ],
                capture_output=True, text=True, check=False,
            )
            self.assertEqual(
                proc_mov.returncode,
                0,
                msg=f"post-LUT ProRes overlay + endcard failed:\nstdout={proc_mov.stdout}\nstderr={proc_mov.stderr}",
            )
            self.assertTrue(out_mov.is_file())
            probe_mov = _ffprobe_json(out_mov)
            dur_mov = float(probe_mov["format"]["duration"])
            self.assertGreaterEqual(dur_mov, 4.7)
            self.assertLessEqual(dur_mov, 5.3)

            # Overlay pixel (60, 60) at t=1.5s MUST stay pure green (untouched by inverting LUT)
            r_ov, g_ov, b_ov = _sample_rgb(out_mov, 1.5, 60, 60)
            self.assertLess(r_ov, 40, msg=f"Overlay green shifted by LUT: {(r_ov, g_ov, b_ov)}")
            self.assertGreater(g_ov, 210, msg=f"Overlay green shifted by LUT: {(r_ov, g_ov, b_ov)}")
            self.assertLess(b_ov, 40, msg=f"Overlay green shifted by LUT: {(r_ov, g_ov, b_ov)}")

            # Background red patch (240, 90) at t=1.5s MUST be inverted to cyan by LUT (alpha preserved!)
            r_bg, g_bg, b_bg = _sample_rgb(out_mov, 1.5, 240, 90)
            self.assertLess(r_bg, 95, msg=f"Background red patch not inverted by LUT: {(r_bg, g_bg, b_bg)}")
            self.assertGreater(g_bg, 170, msg=f"Background red patch not inverted by LUT: {(r_bg, g_bg, b_bg)}")
            self.assertGreater(b_bg, 170, msg=f"Background red patch not inverted by LUT: {(r_bg, g_bg, b_bg)}")

            # Endcard pixel (160, 90) at t=4.0s MUST stay pure royal blue (untouched by inverting LUT)
            r_ec, g_ec, b_ec = _sample_rgb(out_mov, 4.0, 160, 90)
            self.assertLess(r_ec, 60, msg=f"Endcard blue shifted by LUT: {(r_ec, g_ec, b_ec)}")
            self.assertLess(g_ec, 90, msg=f"Endcard blue shifted by LUT: {(r_ec, g_ec, b_ec)}")
            self.assertGreater(b_ec, 190, msg=f"Endcard blue shifted by LUT: {(r_ec, g_ec, b_ec)}")

            # Test 2: --lut + half-res PNG --overlay holds cleanly across full duration and scales to TARGET_W:TARGET_H
            proc_png = subprocess.run(
                [
                    "bash", str(ASSEMBLE_SCRIPT),
                    "--clips", str(clip1),
                    "--lut", str(lut_file),
                    "--overlay", str(ov_png),
                    "--out", str(out_png),
                ],
                capture_output=True, text=True, check=False,
            )
            self.assertEqual(
                proc_png.returncode,
                0,
                msg=f"post-LUT PNG overlay failed:\nstdout={proc_png.stdout}\nstderr={proc_png.stderr}",
            )
            r_p, g_p, b_p = _sample_rgb(out_png, 1.5, 60, 60)
            self.assertLess(r_p, 40, msg=f"PNG overlay green shifted/missing at t=1.5s: {(r_p, g_p, b_p)}")
            self.assertGreater(g_p, 210, msg=f"PNG overlay green shifted/missing at t=1.5s: {(r_p, g_p, b_p)}")
            self.assertLess(b_p, 40, msg=f"PNG overlay green shifted/missing at t=1.5s: {(r_p, g_p, b_p)}")

            # Missing --overlay / --endcard files fail with exit code 2
            proc_bad_ov = subprocess.run(
                [
                    "bash", str(ASSEMBLE_SCRIPT),
                    "--clips", str(clip1),
                    "--overlay", str(tmp / "missing.mov"),
                    "--out", str(tmp / "bad_ov.mp4"),
                ],
                capture_output=True, text=True, check=False,
            )
            self.assertEqual(proc_bad_ov.returncode, 2)

            proc_bad_ec = subprocess.run(
                [
                    "bash", str(ASSEMBLE_SCRIPT),
                    "--clips", str(clip1),
                    "--endcard", str(tmp / "missing.mp4"),
                    "--out", str(tmp / "bad_ec.mp4"),
                ],
                capture_output=True, text=True, check=False,
            )
            self.assertEqual(proc_bad_ec.returncode, 2)


if __name__ == "__main__":
    unittest.main()

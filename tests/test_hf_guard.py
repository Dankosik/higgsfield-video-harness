"""Unit and integration tests for scripts/hf_guard.py using a mock higgsfield CLI."""

from __future__ import annotations

import json
import os
import stat
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "scripts" / "hf_guard.py"


MOCK_HF_SCRIPT = textwrap.dedent(
    """\
    #!/usr/bin/env python3
    import json
    import os
    import sys
    from pathlib import Path

    args = sys.argv[1:]
    log_path = Path(os.environ["MOCK_HF_LOG"])
    with log_path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps({"argv": args}) + "\\n")

    cost = int(os.environ.get("MOCK_HF_COST", "15"))
    balance = int(os.environ.get("MOCK_HF_BALANCE", "500"))
    media_file = Path(os.environ["MOCK_HF_MEDIA"])
    counter_path = Path(os.environ["MOCK_HF_COUNTER"])
    list_path = Path(os.environ["MOCK_HF_LIST"])

    if args[:2] == ["account", "status"]:
        print(json.dumps({"balance": balance, "currency": "credits"}))
        sys.exit(0)

    if args[:2] == ["upload", "create"]:
        count = int(counter_path.read_text(encoding="utf-8").strip()) if counter_path.is_file() else 0
        count += 1
        counter_path.write_text(str(count), encoding="utf-8")
        upload_id = f"upl-mock-{count:03d}"
        print(json.dumps({"upload_id": upload_id, "url": f"https://cdn.example/uploads/{upload_id}"}))
        sys.exit(0)

    if args[:2] == ["workflow", "get"]:
        if args[2] == "kling3_0_motion_control":
            print(
                json.dumps(
                    {
                        "job_type": "kling3_0_motion_control",
                        "cost_params": [
                            {"name": "duration", "type": "number", "required": True},
                            {"name": "mode", "type": "string", "required": False},
                        ],
                        "params": [
                            {"name": "background_source", "type": "string"},
                            {"name": "image_references", "type": "array"},
                            {"name": "mode", "type": "string"},
                            {"name": "video_references", "type": "array"},
                        ],
                    }
                )
            )
            sys.exit(0)
        print(
            json.dumps(
                {
                    "job_type": args[2],
                    "cost_params": [
                        {"name": "duration", "type": "integer"},
                        {"name": "mode", "type": "string"},
                        {"name": "resolution", "type": "string"},
                        {"name": "video_references", "type": "array"},
                    ],
                    "params": [
                        {"name": "duration", "type": "integer"},
                        {"name": "mode", "type": "string"},
                        {"name": "resolution", "type": "string"},
                        {"name": "video_references", "type": "array"},
                        {"name": "aspect_ratio", "type": "string"},
                        {"name": "prompt", "type": "string"},
                        {"name": "start_image", "type": "object|null"},
                        {"name": "image_references", "type": "array"},
                    ],
                }
            )
        )
        sys.exit(0)

    if len(args) >= 2 and args[1] == "cost":
        if os.environ.get("MOCK_HF_STRICT_WF_COST") == "1" and args[:3] == ["generate", "cost", "workflow"]:
            bad = [a for a in args[4:] if a in ("--prompt", "--aspect_ratio", "--start_image", "--image_references")]
            if bad:
                print(f"Error: Unknown params: {', '.join(bad)}", file=sys.stderr)
                sys.exit(4)
        if os.environ.get("MOCK_HF_STRICT_PS_COST") == "1":
            if args[0] == "product-photoshoot":
                print("Error: unknown flag: --mode", file=sys.stderr)
                sys.exit(1)
            if args[0] == "generate":
                bad = [
                    a
                    for a in args
                    if a in ("--mode", "--count")
                    or a.startswith("--enhance-only")
                ]
                if bad:
                    print(f"Error: Unknown params: {', '.join(bad)}", file=sys.stderr)
                    sys.exit(1)
                if "--aspect_ratio" in args and "99:99" in args:
                    print("Error: invalid aspect_ratio 99:99", file=sys.stderr)
                    sys.exit(1)
        print(json.dumps({"estimated_credits": cost}))
        sys.exit(0)

    if args[:2] == ["generate", "list"]:
        if list_path.is_file():
            print(list_path.read_text(encoding="utf-8"))
        else:
            print(json.dumps({"jobs": []}))
        sys.exit(0)

    if args[:2] in (["generate", "get"], ["soul-id", "get"]):
        job_id = args[2]
        get_override = os.environ.get("MOCK_HF_GET_STATUS")
        if get_override == "in_progress":
            print(json.dumps({"job_id": job_id, "status": "in_progress"}))
            sys.exit(0)
        if get_override == "timeout":
            print(json.dumps({"job_id": job_id, "status": "timeout"}))
            sys.exit(0)
        media_file.write_bytes(f"MOCK-RESUMED-{job_id}".encode("utf-8"))
        print(
            json.dumps(
                {
                    "job_id": job_id,
                    "status": "completed",
                    "credits": cost,
                    "url": str(media_file),
                }
            )
        )
        sys.exit(0)

    if args[:2] in (["generate", "wait"], ["soul-id", "wait"]):
        job_id = args[2]
        wait_status = os.environ.get("MOCK_HF_WAIT_STATUS", "completed")
        if wait_status == "timeout":
            print(json.dumps({"job_id": job_id, "status": "timeout"}))
            sys.exit(int(os.environ.get("MOCK_HF_WAIT_RC", "0")))
        media_file.write_bytes(f"MOCK-RESUMED-{job_id}".encode("utf-8"))
        print(
            json.dumps(
                {
                    "job_id": job_id,
                    "status": wait_status,
                    "credits": cost,
                    "url": str(media_file),
                }
            )
        )
        sys.exit(0)

    if args[:2] in (
        ["generate", "create"],
        ["generate", "workflow"],
        ["product-photoshoot", "create"],
        ["soul-id", "create"],
    ):
        if os.environ.get("MOCK_HF_REJECT") == "1":
            print(json.dumps({"error": "HTTP 429 rate limited"}), file=sys.stderr)
            sys.exit(1)

        if os.environ.get("MOCK_HF_TIMEOUT_NO_JOB") == "1":
            print("Error: gateway request timed out after 120s", file=sys.stderr)
            sys.exit(1)

        count = int(counter_path.read_text(encoding="utf-8").strip()) if counter_path.is_file() else 0
        count += 1
        counter_path.write_text(str(count), encoding="utf-8")
        job_id = f"mock-job-{count:03d}"

        if os.environ.get("MOCK_HF_TIMEOUT_WITH_JOB") == "1":
            print(json.dumps({"job_id": job_id, "error": "request timed out while waiting"}))
            sys.exit(1)

        custom_url = os.environ.get("MOCK_HF_URL_OVERRIDE")
        if custom_url:
            out_url = custom_url
        else:
            media_file.write_bytes(f"MOCK-MEDIA-{job_id}".encode("utf-8"))
            out_url = str(media_file)

        status = os.environ.get("MOCK_HF_CREATE_STATUS", "completed")
        print(
            json.dumps(
                {
                    "job_id": job_id,
                    "status": status,
                    "credits": 0 if status in ("in_progress", "timeout") else cost,
                    "url": None if status in ("in_progress", "timeout") else out_url,
                }
            )
        )
        sys.exit(0)

    print(json.dumps({"error": f"unhandled mock command: {args}"}), file=sys.stderr)
    sys.exit(1)
    """
)


def _write_brief(
    campaign_dir: Path,
    *,
    status: str = "active",
    campaign_cap: int = 50,
    lookbook_variants: int = 3,
    max_retries: int = 1,
    auto_open_dailies: bool = True,
) -> None:
    campaign_dir.mkdir(parents=True, exist_ok=True)
    auto_open_str = "true" if auto_open_dailies else "false"
    (campaign_dir / "brief.md").write_text(
        f"# Brief: Mock Guard Campaign\n\n"
        f"status: {status}\n\n"
        "## Purpose & viewer effect\n\n"
        "Verify campaign cap, round cap, asset lock, and idempotent retry enforcement.\n\n"
        "## Subject & visual truth\n\n"
        "Matte ceramic mug on pale limestone table in daylight.\n\n"
        "## Format, audio & delivery\n\n"
        "5s 16:9 widescreen spot.\n\n"
        "## Constraints & boundaries\n\n"
        "- **Must not:** Exceed credit cap or double-charge timeouts.\n"
        "- **Budget & round policy:**\n"
        f"  - Campaign cap: {campaign_cap} credits\n"
        f"  - Lookbook variants: {lookbook_variants}\n"
        f"  - Max auto-retries/asset: {max_retries}\n"
        f"  - Auto-open dailies: {auto_open_str}\n"
        "- **Scope & non-goals:** Guardrail test campaign only.\n\n"
        "## Success signal\n\n"
        "Receipts reflect exact credit spend, round caps, and attempt limits.\n",
        encoding="utf-8",
    )


def _pick_num(payload: dict, keys: tuple[str, ...]) -> int | float | None:
    for key in keys:
        val = payload.get(key)
        if isinstance(val, (int, float)) and not isinstance(val, bool):
            return val
    return None


def _extract_status_campaign(
    data: dict,
) -> tuple[int | float | None, int | float | None, int | float | None]:
    """Return (spent, cap, remaining) from hf_guard.py status --json payload."""
    sub = data.get("campaign") if isinstance(data.get("campaign"), dict) else data
    spent = _pick_num(sub, ("total_spent", "spent", "campaign_spent"))
    if spent is None:
        spent = _pick_num(data, ("total_spent", "campaign_spent", "spent"))
    cap = _pick_num(sub, ("campaign_cap", "cap"))
    if cap is None:
        cap = _pick_num(data, ("campaign_cap", "cap"))
    remaining = _pick_num(sub, ("remaining_campaign", "campaign_remaining", "remaining"))
    if remaining is None:
        remaining = _pick_num(data, ("remaining_campaign", "campaign_remaining", "remaining"))
    return spent, cap, remaining


def _make_locked_shotlist(
    *,
    lookbook_status: str = "LOCKED",
    still_status: str = "LOCKED",
    still_version: int = 1,
    video_status: str = "LOCKED",
    music_status: str = "LOCKED",
    vo_status: str = "LOCKED",
    vo_track_status: str = "LOCKED",
) -> dict:
    return {
        "schema_version": 1,
        "campaign": "lock-guard-test",
        "aspect_ratio": "16:9",
        "target_duration_s": 5,
        "fps_target": 24,
        "references": [],
        "lookbook": [
            {
                "id": "lb_traveler_hand",
                "kind": "character",
                "model": "gpt_image_2_6",
                "prompt_file": "prompts/lb_traveler_v1.txt",
                "variants_requested": 3,
                "status": lookbook_status,
                "version": 1,
                "approved_variant": "B" if lookbook_status == "LOCKED" else None,
                "approved_upload_id": None,
                "estimated_credits": 30,
            }
        ],
        "shots": [
            {
                "id": "s01",
                "title": "Macro hero beat",
                "duration_s": 5,
                "still": {
                    "model": "gpt_image_2_6",
                    "prompt_file": "prompts/s01_still_v1.txt",
                    "references": [],
                    "status": still_status,
                    "version": still_version,
                    "estimated_credits": 10,
                    "selected_take": "media/stills/s01-v1.png",
                    "selected_job_id": "job-locked-001",
                },
                "video": {
                    "model": "cinematic_studio_video_4_0",
                    "is_workflow": True,
                    "mode": "omni_reference",
                    "prompt_file": "prompts/s01_video_v1.txt",
                    "start_image_from": "s01.still",
                    "end_image_from": None,
                    "image_references": [],
                    "draft_params": {"resolution": "480p", "duration": 5},
                    "final_params": {"resolution": "1080p", "duration": 5},
                    "status": video_status,
                    "version": 1,
                    "estimated_draft_credits": 15,
                    "estimated_final_credits": 80,
                    "selected_take": None,
                    "selected_job_id": None,
                },
            }
        ],
        "audio": {
            "music": {
                "enabled": True,
                "model": "elevenlabs_music_v2_5",
                "duration_s": 5,
                "prompt": "Sparse cello underscore.",
                "status": music_status,
                "version": 1,
                "estimated_credits": 10,
                "selected_file": None,
                "selected_job_id": None,
            },
            "voiceover": {
                "enabled": True,
                "model": "elevenlabs_tts_v2",
                "voice_id": "voice-01",
                "voice_type": "warm",
                "status": vo_status,
                "version": 1,
                "estimated_credits": 5,
                "tracks": [
                    {
                        "id": "vo01",
                        "shot_ids": ["s01"],
                        "start_s": 0.0,
                        "window_s": 4.0,
                        "script_file": "prompts/vo01_v1.txt",
                        "status": vo_track_status,
                        "version": 1,
                        "selected_file": None,
                        "selected_job_id": None,
                    }
                ],
            },
        },
    }


class TestHfGuard(unittest.TestCase):
    def _setup_env(self, tmp: Path) -> tuple[Path, dict[str, str], Path, Path]:
        mock_bin = tmp / "mock_higgsfield"
        mock_bin.write_text(MOCK_HF_SCRIPT, encoding="utf-8")
        mock_bin.chmod(mock_bin.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

        log_path = tmp / "mock_hf.log.jsonl"
        list_path = tmp / "mock_hf_list.json"
        counter_path = tmp / "mock_hf_counter.txt"
        media_path = tmp / "mock_source_media.bin"

        env = os.environ.copy()
        env["MOCK_HF_LOG"] = str(log_path)
        env["MOCK_HF_LIST"] = str(list_path)
        env["MOCK_HF_COUNTER"] = str(counter_path)
        env["MOCK_HF_MEDIA"] = str(media_path)
        env["MOCK_HF_COST"] = "15"
        env["MOCK_HF_BALANCE"] = "500"
        for key in (
            "MOCK_HF_REJECT",
            "MOCK_HF_URL_OVERRIDE",
            "MOCK_HF_CREATE_STATUS",
            "MOCK_HF_GET_STATUS",
            "MOCK_HF_WAIT_STATUS",
            "MOCK_HF_WAIT_RC",
            "MOCK_HF_TIMEOUT_NO_JOB",
            "MOCK_HF_TIMEOUT_WITH_JOB",
            "MOCK_HF_STRICT_PS_COST",
            "MOCK_HF_STRICT_WF_COST",
        ):
            env.pop(key, None)
        return mock_bin, env, log_path, list_path

    def _run_guard(
        self, args: list[str], env: dict[str, str]
    ) -> tuple[int, dict, str]:
        proc = subprocess.run(
            [sys.executable, str(SCRIPT), *args],
            capture_output=True,
            text=True,
            env=env,
            check=False,
        )
        parsed = json.loads(proc.stdout) if proc.stdout.strip().startswith("{") else {}
        return proc.returncode, parsed, proc.stderr

    def _read_mock_calls(self, log_path: Path) -> list[list[str]]:
        if not log_path.is_file():
            return []
        return [
            json.loads(line)["argv"]
            for line in log_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]

    def _read_receipts(self, camp: Path) -> list[dict]:
        path = camp / "receipts.jsonl"
        if not path.is_file():
            return []
        return [
            json.loads(line)
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]

    def test_preflight_succeeds_and_reports_exact_remaining_credits(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            camp = tmp / "camp"
            _write_brief(camp, campaign_cap=50, max_retries=2)
            mock_bin, env, _, _ = self._setup_env(tmp)
            env["MOCK_HF_COST"] = "15"

            rc, data, err = self._run_guard(
                [
                    "preflight",
                    "--campaign",
                    str(camp),
                    "--shot",
                    "s01",
                    "--kind",
                    "video",
                    "--round",
                    "R4",
                    "--round-cap",
                    "40",
                    "--model",
                    "cinematic_studio_video_4_0",
                    "--higgsfield-bin",
                    str(mock_bin),
                ],
                env,
            )
            self.assertEqual(rc, 0, msg=f"stderr={err}\ndata={data}")
            self.assertTrue(data["ok"])
            self.assertEqual(data["estimated_credits"], 15)
            self.assertEqual(data["total_spent"], 0, msg=data)
            self.assertEqual(data["campaign_cap"], 50, msg=data)
            self.assertEqual(data["remaining_campaign_after"], 35, msg=data)
            self.assertEqual(data["round_cap"], 40, msg=data)

    def test_missing_round_cap_rejected_on_preflight_and_run(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            camp = tmp / "camp"
            _write_brief(camp, campaign_cap=100, max_retries=2)
            mock_bin, env, log_path, _ = self._setup_env(tmp)

            for subcmd in ("preflight", "run"):
                rc, _, err = self._run_guard(
                    [
                        subcmd,
                        "--campaign",
                        str(camp),
                        "--shot",
                        "s01",
                        "--kind",
                        "video",
                        "--round",
                        "R4",
                        "--model",
                        "cinematic_studio_video_4_0",
                        "--higgsfield-bin",
                        str(mock_bin),
                    ],
                    env,
                )
                self.assertNotEqual(
                    rc,
                    0,
                    msg=f"Expected {subcmd} without --round-cap to fail via argparse",
                )
                self.assertIn("--round-cap", err, msg=f"stderr={err}")
            self.assertEqual(self._read_mock_calls(log_path), [])

    def test_preflight_and_run_refuse_budget_exceeded(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            camp = tmp / "camp"
            _write_brief(camp, campaign_cap=20, max_retries=2)
            mock_bin, env, log_path, _ = self._setup_env(tmp)
            env["MOCK_HF_COST"] = "25"

            base_args = [
                "--campaign",
                str(camp),
                "--shot",
                "s01",
                "--kind",
                "video",
                "--round",
                "R4",
                "--round-cap",
                "50",
                "--model",
                "cinematic_studio_video_4_0",
                "--higgsfield-bin",
                str(mock_bin),
            ]

            rc_pf, data_pf, _ = self._run_guard(["preflight", *base_args], env)
            self.assertEqual(rc_pf, 2, msg=data_pf)
            self.assertFalse(data_pf["ok"])
            self.assertEqual(data_pf["error_code"], "campaign_budget_exceeded")

            out_file = camp / "media" / "shots" / "s01.mp4"
            rc_run, data_run, _ = self._run_guard(
                ["run", *base_args, "--out", str(out_file)], env
            )
            self.assertEqual(rc_run, 2, msg=data_run)
            self.assertFalse(data_run["ok"])
            self.assertEqual(data_run["error_code"], "campaign_budget_exceeded")
            self.assertFalse(out_file.exists())
            create_calls = [
                c for c in self._read_mock_calls(log_path) if c[:2] == ["generate", "create"]
            ]
            self.assertEqual(create_calls, [])

    def test_run_writes_receipt_copies_output_and_enforces_retry_limit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            camp = tmp / "camp"
            # Max auto-retries/asset = 1 => at most 1 + 1 = 2 total attempts
            _write_brief(camp, campaign_cap=100, max_retries=1)
            mock_bin, env, log_path, _ = self._setup_env(tmp)
            env["MOCK_HF_COST"] = "15"

            prompt_file = camp / "prompt.txt"
            prompt_file.write_text("Sunlight across ceramic mug.", encoding="utf-8")

            out1 = camp / "media" / "shots" / "s01-take1.mp4"
            rc1, data1, err1 = self._run_guard(
                [
                    "run",
                    "--campaign",
                    str(camp),
                    "--shot",
                    "s01",
                    "--kind",
                    "video",
                    "--round",
                    "R4",
                    "--round-cap",
                    "100",
                    "--model",
                    "cinematic_studio_video_4_0",
                    "--prompt-file",
                    str(prompt_file),
                    "--out",
                    str(out1),
                    "--higgsfield-bin",
                    str(mock_bin),
                ],
                env,
            )
            self.assertEqual(rc1, 0, msg=f"err={err1}\ndata={data1}")
            self.assertTrue(data1["ok"])
            self.assertEqual(data1["attempt"], 0)
            self.assertTrue(out1.is_file())
            self.assertEqual(out1.read_bytes(), b"MOCK-MEDIA-mock-job-001")

            out2 = camp / "media" / "shots" / "s01-take2.mp4"
            rc2, data2, _ = self._run_guard(
                [
                    "run",
                    "--campaign",
                    str(camp),
                    "--shot",
                    "s01",
                    "--kind",
                    "video",
                    "--round",
                    "R4",
                    "--round-cap",
                    "100",
                    "--model",
                    "cinematic_studio_video_4_0",
                    "--prompt-file",
                    str(prompt_file),
                    "--out",
                    str(out2),
                    "--higgsfield-bin",
                    str(mock_bin),
                ],
                env,
            )
            self.assertEqual(rc2, 0, msg=data2)
            self.assertEqual(data2["attempt"], 1)
            self.assertTrue(out2.is_file())

            # Third attempt exceeds 1 + max_retries (= 2) and must exit 2
            out3 = camp / "media" / "shots" / "s01-take3.mp4"
            rc3, data3, _ = self._run_guard(
                [
                    "run",
                    "--campaign",
                    str(camp),
                    "--shot",
                    "s01",
                    "--kind",
                    "video",
                    "--round",
                    "R4",
                    "--round-cap",
                    "100",
                    "--model",
                    "cinematic_studio_video_4_0",
                    "--prompt-file",
                    str(prompt_file),
                    "--out",
                    str(out3),
                    "--higgsfield-bin",
                    str(mock_bin),
                ],
                env,
            )
            self.assertEqual(rc3, 2, msg=data3)
            self.assertFalse(data3["ok"])
            self.assertEqual(data3["error_code"], "retry_limit_exceeded")
            self.assertFalse(out3.exists())

            completed_receipts = [
                r for r in self._read_receipts(camp) if r.get("status") == "completed"
            ]
            self.assertEqual(len(completed_receipts), 2)
            self.assertEqual([r["attempt"] for r in completed_receipts], [0, 1])
            # NB1: receipts include round_cap, variant, and version
            for rec in completed_receipts:
                self.assertEqual(rec["round_cap"], 100, msg=rec)
                self.assertIn("variant", rec, msg=rec)
                self.assertEqual(rec["version"], 1, msg=rec)

            rc_st, st_data, _ = self._run_guard(
                ["status", "--campaign", str(camp), "--json"], env
            )
            self.assertEqual(rc_st, 0, msg=st_data)
            spent, cap, remaining = _extract_status_campaign(st_data)
            self.assertEqual(spent, 30, msg=st_data)
            self.assertEqual(cap, 100, msg=st_data)
            self.assertEqual(remaining, 70, msg=st_data)
            self.assertIn("active_reserved", st_data, msg=st_data)
            self.assertEqual(st_data["active_reserved"], 0, msg=st_data)

            create_calls = [
                c for c in self._read_mock_calls(log_path) if c[:2] == ["generate", "create"]
            ]
            self.assertEqual(len(create_calls), 2)

    def test_run_refuses_when_brief_is_draft(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            camp = tmp / "camp"
            _write_brief(camp, status="draft", campaign_cap=100, max_retries=2)
            mock_bin, env, log_path, _ = self._setup_env(tmp)

            rc, data, _ = self._run_guard(
                [
                    "run",
                    "--campaign",
                    str(camp),
                    "--shot",
                    "s01",
                    "--kind",
                    "still",
                    "--round",
                    "R3",
                    "--round-cap",
                    "50",
                    "--model",
                    "gpt_image_2_6",
                    "--higgsfield-bin",
                    str(mock_bin),
                ],
                env,
            )
            self.assertEqual(rc, 2, msg=data)
            self.assertFalse(data["ok"])
            self.assertEqual(data["error_code"], "brief_not_active")
            paid_calls = [
                c
                for c in self._read_mock_calls(log_path)
                if c[:2] in (["generate", "create"], ["generate", "workflow"], ["generate", "wait"])
            ]
            self.assertEqual(paid_calls, [])

    def test_duplicate_protection_resumes_in_flight_job_without_recreating(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            camp = tmp / "camp"
            _write_brief(camp, status="active", campaign_cap=100, max_retries=2)
            mock_bin, env, log_path, list_path = self._setup_env(tmp)
            env["MOCK_HF_COST"] = "15"
            env["MOCK_HF_GET_STATUS"] = "in_progress"

            prompt_file = camp / "s01_video.txt"
            prompt_file.write_text("Slow push-in across matte leather clasp.", encoding="utf-8")

            rc_dry, dry_data, _ = self._run_guard(
                [
                    "run",
                    "--campaign",
                    str(camp),
                    "--shot",
                    "s01",
                    "--kind",
                    "video",
                    "--round",
                    "R4",
                    "--round-cap",
                    "100",
                    "--model",
                    "cinematic_studio_video_4_0",
                    "--prompt-file",
                    str(prompt_file),
                    "--dry-run",
                    "--higgsfield-bin",
                    str(mock_bin),
                    "--",
                    "--resolution",
                    "480p",
                ],
                env,
            )
            self.assertEqual(rc_dry, 0, msg=dry_data)
            params_hash = dry_data["params_hash"]

            interrupted_job = "job-inflight-777"
            (camp / "receipts.jsonl").write_text(
                json.dumps(
                    {
                        "ts": "2026-11-19T20:00:00Z",
                        "reservation_id": "res-inflight-777",
                        "shot": "s01",
                        "kind": "video",
                        "round": "R4",
                        "round_cap": 100,
                        "variant": "",
                        "version": 1,
                        "model": "cinematic_studio_video_4_0",
                        "is_workflow": False,
                        "params_hash": params_hash,
                        "job_id": interrupted_job,
                        "status": "in_progress",
                        "estimated_credits": 15,
                        "actual_credits": None,
                        "credits": 15,
                        "url": None,
                        "out": None,
                        "attempt": 0,
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            list_path.write_text(
                json.dumps({"jobs": [{"job_id": interrupted_job, "status": "in_progress"}]}),
                encoding="utf-8",
            )
            log_path.write_text("", encoding="utf-8")

            out_file = camp / "media" / "shots" / "s01-resumed.mp4"
            rc, data, err = self._run_guard(
                [
                    "run",
                    "--campaign",
                    str(camp),
                    "--shot",
                    "s01",
                    "--kind",
                    "video",
                    "--round",
                    "R4",
                    "--round-cap",
                    "100",
                    "--model",
                    "cinematic_studio_video_4_0",
                    "--prompt-file",
                    str(prompt_file),
                    "--out",
                    str(out_file),
                    "--higgsfield-bin",
                    str(mock_bin),
                    "--",
                    "--resolution",
                    "480p",
                ],
                env,
            )
            self.assertEqual(rc, 0, msg=f"err={err}\ndata={data}")
            self.assertTrue(data["ok"])
            self.assertTrue(data["resumed"])
            self.assertEqual(data["job_id"], interrupted_job)
            self.assertTrue(out_file.is_file())
            self.assertEqual(out_file.read_bytes(), f"MOCK-RESUMED-{interrupted_job}".encode())

            calls = self._read_mock_calls(log_path)
            create_calls = [c for c in calls if c[:2] == ["generate", "create"]]
            wait_calls = [c for c in calls if c[:2] == ["generate", "wait"]]
            self.assertEqual(create_calls, [], msg=f"Unexpected duplicate create call: {calls}")
            self.assertEqual(len(wait_calls), 1, msg=f"Expected single wait call: {calls}")
            self.assertEqual(wait_calls[0][:3], ["generate", "wait", interrupted_job])
            self.assertIn("--json", wait_calls[0])

    def test_upload_records_upload_id_at_zero_credits(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            camp = tmp / "camp"
            _write_brief(camp, campaign_cap=50, max_retries=2)
            mock_bin, env, log_path, _ = self._setup_env(tmp)

            ref_img = camp / "media" / "references" / "bag_hero_front.jpg"
            ref_img.parent.mkdir(parents=True, exist_ok=True)
            ref_img.write_bytes(b"\xff\xd8\xffMOCKJPEG")

            rc, data, err = self._run_guard(
                [
                    "upload",
                    "--campaign",
                    str(camp),
                    "--file",
                    str(ref_img),
                    "--ref-id",
                    "ref_bag_front",
                    "--round",
                    "R2",
                    "--higgsfield-bin",
                    str(mock_bin),
                ],
                env,
            )
            self.assertEqual(rc, 0, msg=f"err={err}\ndata={data}")
            self.assertTrue(data["ok"])
            self.assertEqual(data["upload_id"], "upl-mock-001")

            receipts = self._read_receipts(camp)
            self.assertEqual(len(receipts), 1)
            self.assertEqual(receipts[0]["upload_id"], "upl-mock-001")
            self.assertEqual(receipts[0]["kind"], "upload")
            self.assertEqual(float(receipts[0]["credits"]), 0.0)

            rc_st, st_data, _ = self._run_guard(
                ["status", "--campaign", str(camp), "--json"], env
            )
            self.assertEqual(rc_st, 0, msg=st_data)
            spent, _, _ = _extract_status_campaign(st_data)
            self.assertEqual(spent, 0, msg=st_data)

            upload_calls = [
                c for c in self._read_mock_calls(log_path) if c[:2] == ["upload", "create"]
            ]
            self.assertEqual(len(upload_calls), 1)

    def test_upload_fails_closed_on_corrupt_receipts_before_remote_cli(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            camp = tmp / "camp"
            _write_brief(camp, campaign_cap=50, max_retries=2)
            mock_bin, env, log_path, _ = self._setup_env(tmp)

            ref_img = camp / "media" / "references" / "bag_hero_front.jpg"
            ref_img.parent.mkdir(parents=True, exist_ok=True)
            ref_img.write_bytes(b"\xff\xd8\xffMOCKJPEG")
            (camp / "receipts.jsonl").write_text("{corrupt-jsonl\n", encoding="utf-8")

            rc, data, _ = self._run_guard(
                [
                    "upload",
                    "--campaign",
                    str(camp),
                    "--file",
                    str(ref_img),
                    "--ref-id",
                    "ref_bag_front",
                    "--round",
                    "R2",
                    "--higgsfield-bin",
                    str(mock_bin),
                ],
                env,
            )
            self.assertEqual(rc, 2, msg=data)
            self.assertFalse(data.get("ok", True))
            self.assertEqual(data.get("error_code"), "corrupt_receipts")
            self.assertEqual(
                self._read_mock_calls(log_path),
                [],
                "Corrupt receipts.jsonl must fail closed BEFORE calling remote CLI upload",
            )

    def test_run_product_photoshoot_command_succeeds(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            camp = tmp / "camp"
            _write_brief(camp, campaign_cap=50, max_retries=2)
            mock_bin, env, log_path, _ = self._setup_env(tmp)
            env["MOCK_HF_COST"] = "10"

            out_img = camp / "media" / "stills" / "s01-shoot.png"
            rc, data, err = self._run_guard(
                [
                    "run",
                    "--campaign",
                    str(camp),
                    "--shot",
                    "s01",
                    "--kind",
                    "still",
                    "--round",
                    "R3",
                    "--round-cap",
                    "50",
                    "--command",
                    "product-photoshoot",
                    "--model",
                    "gpt_image_2",
                    "--out",
                    str(out_img),
                    "--higgsfield-bin",
                    str(mock_bin),
                    "--",
                    "--mode",
                    "lifestyle_scene",
                ],
                env,
            )
            self.assertEqual(rc, 0, msg=f"err={err}\ndata={data}")
            self.assertTrue(data["ok"])
            self.assertEqual(data["credits"], 10)
            self.assertTrue(out_img.is_file())

            calls = self._read_mock_calls(log_path)
            self.assertTrue(
                any(c[:2] == ["product-photoshoot", "create"] for c in calls),
                msg=f"Expected product-photoshoot create call, got: {calls}",
            )

    def test_product_photoshoot_cost_fallback_strips_command_only_flags(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            camp = tmp / "camp"
            _write_brief(camp, campaign_cap=50, max_retries=2)
            mock_bin, env, log_path, _ = self._setup_env(tmp)
            env["MOCK_HF_COST"] = "7"
            env["MOCK_HF_STRICT_PS_COST"] = "1"

            # Valid fallback: strips --no-color, --enhance-only=true, --mode, --count +2 (2x), ignores --workflow
            rc, data, err = self._run_guard(
                [
                    "preflight",
                    "--campaign",
                    str(camp),
                    "--shot",
                    "lb_hero",
                    "--kind",
                    "lookbook",
                    "--round",
                    "R2",
                    "--round-cap",
                    "35",
                    "--variant",
                    "A",
                    "--command",
                    "product-photoshoot",
                    "--model",
                    "gpt_image_2",
                    "--workflow",
                    "--higgsfield-bin",
                    str(mock_bin),
                    "--",
                    "--no-color",
                    "--enhance-only=true",
                    "--mode",
                    "lifestyle_scene",
                    "--count",
                    "+2",
                    "--image",
                    "00000000-0000-4000-8000-000000000001",
                    "--prompt",
                    "Matte saddle leather on pale limestone bench",
                ],
                env,
            )
            self.assertEqual(rc, 0, msg=f"err={err}\ndata={data}")
            self.assertTrue(data["ok"])
            self.assertEqual(data["estimated_credits"], 14, msg=data)
            calls = self._read_mock_calls(log_path)
            fb_calls = [c for c in calls if c[:3] == ["generate", "cost", "gpt_image_2"]]
            self.assertEqual(len(fb_calls), 1, msg=f"Expected non-workflow fallback call: {calls}")
            self.assertNotIn("--mode", fb_calls[0])
            self.assertNotIn("--count", fb_calls[0])
            self.assertNotIn("--enhance-only=true", fb_calls[0])
            self.assertNotIn("--no-color", fb_calls[0])
            self.assertIn("--prompt", fb_calls[0])

            # Real fallback failure must surface fallback stderr, not stale primary stderr
            rc_err, data_err, _ = self._run_guard(
                [
                    "preflight",
                    "--campaign",
                    str(camp),
                    "--shot",
                    "lb_hero",
                    "--kind",
                    "lookbook",
                    "--round",
                    "R2",
                    "--round-cap",
                    "35",
                    "--variant",
                    "A",
                    "--command",
                    "product-photoshoot",
                    "--model",
                    "gpt_image_2",
                    "--higgsfield-bin",
                    str(mock_bin),
                    "--",
                    "--mode",
                    "lifestyle_scene",
                    "--count=1",
                    "--aspect_ratio",
                    "99:99",
                    "--prompt",
                    "test",
                ],
                env,
            )
            self.assertEqual(rc_err, 1, msg=data_err)
            self.assertIn("invalid aspect_ratio 99:99", data_err.get("stderr", ""), msg=data_err)

            # Invalid --count variants (0, -2, abc, Unicode digit, missing value) must fail closed before CLI
            log_path.write_text("", encoding="utf-8")
            for bad_args in (
                ["--count", "0"],
                ["--count", "-2"],
                ["--count", "abc"],
                ["--count", "\u00b2"],
                ["--count=0"],
                ["--count"],
            ):
                rc_bad, data_bad, _ = self._run_guard(
                    [
                        "preflight",
                        "--campaign",
                        str(camp),
                        "--shot",
                        "lb_hero",
                        "--kind",
                        "lookbook",
                        "--round",
                        "R2",
                        "--round-cap",
                        "35",
                        "--variant",
                        "A",
                        "--command",
                        "product-photoshoot",
                        "--model",
                        "gpt_image_2",
                        "--higgsfield-bin",
                        str(mock_bin),
                        "--",
                        *bad_args,
                    ],
                    env,
                )
                self.assertEqual(rc_bad, 2, msg=f"Expected exit 2 for {bad_args}: {data_bad}")
                self.assertEqual(data_bad.get("error_code"), "invalid_count", msg=data_bad)
            self.assertEqual(self._read_mock_calls(log_path), [])

    def test_workflow_cost_fallback_filters_to_cost_params(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            camp = tmp / "camp"
            _write_brief(camp, campaign_cap=100, max_retries=2)
            mock_bin, env, log_path, _ = self._setup_env(tmp)
            env["MOCK_HF_COST"] = "15"
            env["MOCK_HF_STRICT_WF_COST"] = "1"

            rc, data, err = self._run_guard(
                [
                    "preflight",
                    "--campaign",
                    str(camp),
                    "--shot",
                    "s02",
                    "--kind",
                    "video",
                    "--round",
                    "R4A",
                    "--round-cap",
                    "20",
                    "--model",
                    "cinematic_studio_video_4_0",
                    "--workflow",
                    "--higgsfield-bin",
                    str(mock_bin),
                    "--",
                    "--no-color",
                    "--mode",
                    "omni_reference",
                    "--resolution",
                    "1080p",
                    "--duration",
                    "5",
                    "--aspect_ratio",
                    "16:9",
                    "--start_image",
                    "00000000-0000-4000-8000-000000000001",
                    "--prompt",
                    "Slow push-in across matte leather clasp.",
                ],
                env,
            )
            self.assertEqual(rc, 0, msg=f"err={err}\ndata={data}")
            self.assertTrue(data["ok"])
            self.assertEqual(data["estimated_credits"], 15, msg=data)
            calls = self._read_mock_calls(log_path)
            wf_cost_calls = [
                c for c in calls if c[:4] == ["generate", "cost", "workflow", "cinematic_studio_video_4_0"]
            ]
            self.assertEqual(len(wf_cost_calls), 1, msg=f"Expected single filtered cost call: {calls}")
            self.assertNotIn("--prompt", wf_cost_calls[0])
            self.assertNotIn("--start_image", wf_cost_calls[0])
            self.assertNotIn("--no-color", wf_cost_calls[0])
            self.assertIn("--mode", wf_cost_calls[0])
            self.assertIn("--resolution", wf_cost_calls[0])
            self.assertIn("1080p", wf_cost_calls[0])

    def test_workflow_run_strips_cost_only_params_like_motion_control_duration(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            camp = tmp / "camp"
            _write_brief(camp, campaign_cap=100, max_retries=2)
            mock_bin, env, log_path, _ = self._setup_env(tmp)
            env["MOCK_HF_COST"] = "15"
            out_file = camp / "media" / "shots" / "s04-motion-v1.mp4"

            rc, data, err = self._run_guard(
                [
                    "run",
                    "--campaign",
                    str(camp),
                    "--shot",
                    "s04",
                    "--kind",
                    "video",
                    "--round",
                    "R4B",
                    "--round-cap",
                    "25",
                    "--model",
                    "kling3_0_motion_control",
                    "--workflow",
                    "--out",
                    str(out_file),
                    "--higgsfield-bin",
                    str(mock_bin),
                    "--",
                    "--duration",
                    "5",
                    "--mode",
                    "pro",
                    "--background_source",
                    "input_image",
                    "--image_references",
                    "00000000-0000-4000-8000-000000000001",
                    "--video_references",
                    "00000000-0000-4000-8000-000000000002",
                ],
                env,
            )
            self.assertEqual(rc, 0, msg=f"err={err}\ndata={data}")
            self.assertTrue(data["ok"])
            calls = self._read_mock_calls(log_path)
            cost_calls = [
                c for c in calls if c[:4] == ["generate", "cost", "workflow", "kling3_0_motion_control"]
            ]
            exec_calls = [
                c for c in calls if c[:3] == ["generate", "workflow", "kling3_0_motion_control"]
            ]
            self.assertEqual(len(cost_calls), 1, msg=calls)
            self.assertEqual(len(exec_calls), 1, msg=calls)
            self.assertIn("--duration", cost_calls[0])
            self.assertIn("5", cost_calls[0])
            self.assertNotIn("--background_source", cost_calls[0])
            self.assertNotIn("--duration", exec_calls[0])
            self.assertIn("--background_source", exec_calls[0])
            self.assertIn("--image_references", exec_calls[0])
            self.assertIn("--video_references", exec_calls[0])

    def test_rejected_cli_failure_without_job_id_does_not_consume_budget_or_retries(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            camp = tmp / "camp"
            # Max auto-retries/asset = 0 => only 1 attempt allowed total
            _write_brief(camp, campaign_cap=20, max_retries=0)
            mock_bin, env, _, _ = self._setup_env(tmp)
            env["MOCK_HF_COST"] = "15"
            env["MOCK_HF_REJECT"] = "1"

            base_run = [
                "run",
                "--campaign",
                str(camp),
                "--shot",
                "s01",
                "--kind",
                "video",
                "--round",
                "R4",
                "--round-cap",
                "20",
                "--model",
                "cinematic_studio_video_4_0",
                "--higgsfield-bin",
                str(mock_bin),
            ]
            rc_fail, data_fail, _ = self._run_guard(base_run, env)
            self.assertEqual(rc_fail, 1, msg=data_fail)
            self.assertFalse(data_fail["ok"])
            self.assertEqual(data_fail["status"], "rejected")
            self.assertEqual(float(data_fail["credits"]), 0.0)

            rc_st, st_data, _ = self._run_guard(
                ["status", "--campaign", str(camp), "--json"], env
            )
            self.assertEqual(rc_st, 0, msg=st_data)
            spent, _, remaining = _extract_status_campaign(st_data)
            self.assertEqual(spent, 0, msg=st_data)
            self.assertEqual(remaining, 20, msg=st_data)

            # Clear rejection and verify retry + budget were NOT consumed
            env.pop("MOCK_HF_REJECT", None)
            out_file = camp / "media" / "shots" / "s01-ok.mp4"
            rc_ok, data_ok, err_ok = self._run_guard(
                [*base_run, "--out", str(out_file)], env
            )
            self.assertEqual(rc_ok, 0, msg=f"err={err_ok}\ndata={data_ok}")
            self.assertTrue(data_ok["ok"])
            self.assertEqual(data_ok["attempt"], 0)
            self.assertTrue(out_file.is_file())

    def test_download_failed_preserves_job_and_resumes_without_recreating(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            camp = tmp / "camp"
            _write_brief(camp, campaign_cap=50, max_retries=1)
            mock_bin, env, log_path, _ = self._setup_env(tmp)
            env["MOCK_HF_COST"] = "15"

            transient_src = tmp / "transient_download_source.mp4"
            env["MOCK_HF_URL_OVERRIDE"] = str(transient_src)

            out_file = camp / "media" / "shots" / "s01-dl.mp4"
            run_args = [
                "run",
                "--campaign",
                str(camp),
                "--shot",
                "s01",
                "--kind",
                "video",
                "--round",
                "R4",
                "--round-cap",
                "50",
                "--model",
                "cinematic_studio_video_4_0",
                "--out",
                str(out_file),
                "--higgsfield-bin",
                str(mock_bin),
            ]

            # First run: remote job completes (charging 15 cr) but local download source is missing
            rc1, data1, _ = self._run_guard(run_args, env)
            self.assertEqual(rc1, 1, msg=data1)
            self.assertFalse(data1["ok"])
            self.assertEqual(data1["status"], "download_failed")
            self.assertEqual(data1["error_code"], "download_failed")
            self.assertEqual(data1["job_id"], "mock-job-001")
            self.assertEqual(data1["actual_credits"], 15)
            self.assertFalse(out_file.exists())

            # Source becomes available; clear mock log and re-run to verify zero duplicate create calls
            transient_src.write_bytes(b"RECOVERED-VIDEO-BYTES")
            log_path.write_text("", encoding="utf-8")

            rc2, data2, err2 = self._run_guard(run_args, env)
            self.assertEqual(rc2, 0, msg=f"err={err2}\ndata={data2}")
            self.assertTrue(data2["ok"])
            self.assertEqual(data2["job_id"], "mock-job-001")
            self.assertTrue(out_file.is_file())
            self.assertEqual(out_file.read_bytes(), b"RECOVERED-VIDEO-BYTES")

            calls_after = self._read_mock_calls(log_path)
            create_calls = [c for c in calls_after if c[:2] == ["generate", "create"]]
            self.assertEqual(
                create_calls,
                [],
                msg=f"Unexpected recreate on download retry: {calls_after}",
            )

            rc_st, st_data, _ = self._run_guard(
                ["status", "--campaign", str(camp), "--json"], env
            )
            self.assertEqual(rc_st, 0, msg=st_data)
            spent, _, _ = _extract_status_campaign(st_data)
            self.assertEqual(spent, 15, msg=st_data)

    def test_unresolved_reserved_or_in_progress_receipt_blocks_concurrent_overspend(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            camp = tmp / "camp"
            _write_brief(camp, campaign_cap=25, max_retries=2)
            mock_bin, env, log_path, _ = self._setup_env(tmp)
            env["MOCK_HF_COST"] = "15"

            # Seed an unresolved active `reserved` receipt for s01 holding 15 credits
            (camp / "receipts.jsonl").write_text(
                json.dumps(
                    {
                        "ts": "2026-11-19T20:10:00Z",
                        "reservation_id": "res-active-s01",
                        "shot": "s01",
                        "kind": "video",
                        "round": "R4",
                        "round_cap": 25,
                        "variant": "",
                        "version": 1,
                        "model": "cinematic_studio_video_4_0",
                        "is_workflow": False,
                        "params_hash": "hash-s01-in-flight",
                        "job_id": "",
                        "status": "reserved",
                        "estimated_credits": 15,
                        "actual_credits": None,
                        "credits": 15,
                        "url": None,
                        "out": None,
                        "attempt": 0,
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            # Status surfaces active_reserved accurately (NB1)
            rc_st, st_data, _ = self._run_guard(
                ["status", "--campaign", str(camp), "--json"], env
            )
            self.assertEqual(rc_st, 0, msg=st_data)
            self.assertEqual(st_data["active_reserved"], 15, msg=st_data)

            # Concurrent call for s02 (15 cr) would push 15 + 15 = 30 > Campaign cap 25
            rc, data, _ = self._run_guard(
                [
                    "run",
                    "--campaign",
                    str(camp),
                    "--shot",
                    "s02",
                    "--kind",
                    "video",
                    "--round",
                    "R4",
                    "--round-cap",
                    "40",
                    "--model",
                    "cinematic_studio_video_4_0",
                    "--higgsfield-bin",
                    str(mock_bin),
                ],
                env,
            )
            self.assertEqual(rc, 2, msg=data)
            self.assertFalse(data["ok"])
            self.assertEqual(data["error_code"], "campaign_budget_exceeded")
            self.assertEqual(data["total_spent"], 15, msg=data)
            create_calls = [
                c for c in self._read_mock_calls(log_path) if c[:2] == ["generate", "create"]
            ]
            self.assertEqual(create_calls, [])

    def test_round_cap_blocks_before_campaign_cap(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            camp = tmp / "camp"
            _write_brief(camp, campaign_cap=400, max_retries=2)
            mock_bin, env, log_path, _ = self._setup_env(tmp)
            env["MOCK_HF_COST"] = "30"

            base_args = [
                "--campaign",
                str(camp),
                "--shot",
                "lb_traveler_hand",
                "--kind",
                "lookbook",
                "--round",
                "R2",
                "--round-cap",
                "25",
                "--variant",
                "A",
                "--model",
                "gpt_image_2_6",
                "--higgsfield-bin",
                str(mock_bin),
            ]

            rc_pf, data_pf, _ = self._run_guard(["preflight", *base_args], env)
            self.assertEqual(rc_pf, 2, msg=data_pf)
            self.assertFalse(data_pf["ok"])
            self.assertEqual(data_pf["error_code"], "round_budget_exceeded")

            out_img = camp / "media" / "lookbook" / "lb_traveler_hand-a.png"
            rc_run, data_run, _ = self._run_guard(
                ["run", *base_args, "--out", str(out_img)], env
            )
            self.assertEqual(rc_run, 2, msg=data_run)
            self.assertFalse(data_run["ok"])
            self.assertEqual(data_run["error_code"], "round_budget_exceeded")
            self.assertFalse(out_img.exists())
            create_calls = [
                c for c in self._read_mock_calls(log_path) if c[:2] == ["generate", "create"]
            ]
            self.assertEqual(create_calls, [])

    def test_locked_assets_refused_across_all_kinds_and_unlock_requires_shotlist_edit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            camp = tmp / "camp"
            _write_brief(camp, campaign_cap=200, max_retries=2)
            mock_bin, env, log_path, _ = self._setup_env(tmp)
            env["MOCK_HF_COST"] = "10"

            shotlist_path = camp / "shotlist.json"
            shotlist_path.write_text(
                json.dumps(_make_locked_shotlist(), indent=2),
                encoding="utf-8",
            )

            locked_cases = [
                ("lb_traveler_hand", "lookbook", "R2", ["--variant", "A"], "gpt_image_2_6"),
                ("s01", "still", "R3", [], "gpt_image_2_6"),
                ("s01", "video", "R4", [], "cinematic_studio_video_4_0"),
                ("music01", "audio", "R3", [], "elevenlabs_music_v2_5"),
                ("vo01", "audio", "R3", [], "elevenlabs_tts_v2"),
            ]
            for shot, kind, rnd, extra, model in locked_cases:
                base = [
                    "--campaign",
                    str(camp),
                    "--shot",
                    shot,
                    "--kind",
                    kind,
                    "--round",
                    rnd,
                    "--round-cap",
                    "100",
                    *extra,
                    "--model",
                    model,
                    "--higgsfield-bin",
                    str(mock_bin),
                ]
                for subcmd in ("preflight", "run"):
                    rc, data, _ = self._run_guard([subcmd, *base], env)
                    self.assertEqual(
                        rc,
                        2,
                        msg=f"Expected {subcmd} asset_locked for {kind}:{shot}, got {data}",
                    )
                    self.assertFalse(data["ok"])
                    self.assertEqual(
                        data["error_code"],
                        "asset_locked",
                        msg=f"Expected asset_locked for {subcmd} {kind}:{shot}, got {data}",
                    )

            # Removed CLI flag --force-unlock must be rejected by argparse
            rc_fu, _, err_fu = self._run_guard(
                [
                    "run",
                    "--campaign",
                    str(camp),
                    "--shot",
                    "s01",
                    "--kind",
                    "still",
                    "--round",
                    "R3",
                    "--round-cap",
                    "100",
                    "--model",
                    "gpt_image_2_6",
                    "--force-unlock",
                    "--higgsfield-bin",
                    str(mock_bin),
                ],
                env,
            )
            self.assertNotEqual(rc_fu, 0, msg="Removed --force-unlock flag must fail")
            self.assertIn("--force-unlock", err_fu)
            self.assertEqual(
                [c for c in self._read_mock_calls(log_path) if c[:2] == ["generate", "create"]],
                [],
            )

            # Unlock cleanly ONLY by Root Producer moving shotlist.json to ITERATING v2
            shotlist_path.write_text(
                json.dumps(
                    _make_locked_shotlist(still_status="ITERATING", still_version=2),
                    indent=2,
                ),
                encoding="utf-8",
            )
            out_v2 = camp / "media" / "stills" / "s01-v2.png"
            rc_ok, data_ok, err_ok = self._run_guard(
                [
                    "run",
                    "--campaign",
                    str(camp),
                    "--shot",
                    "s01",
                    "--kind",
                    "still",
                    "--round",
                    "R3",
                    "--round-cap",
                    "100",
                    "--version",
                    "2",
                    "--model",
                    "gpt_image_2_6",
                    "--out",
                    str(out_v2),
                    "--higgsfield-bin",
                    str(mock_bin),
                ],
                env,
            )
            self.assertEqual(rc_ok, 0, msg=f"Unlocked ITERATING v2 failed: err={err_ok}\ndata={data_ok}")
            self.assertTrue(data_ok["ok"])
            self.assertEqual(data_ok["version"], 2, msg=data_ok)
            self.assertTrue(out_v2.is_file())

    def test_corrupt_shotlist_fails_closed_on_preflight_and_run(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            camp = tmp / "camp"
            _write_brief(camp, campaign_cap=100, max_retries=2)
            mock_bin, env, log_path, _ = self._setup_env(tmp)
            (camp / "shotlist.json").write_text("{corrupt-shotlist-json", encoding="utf-8")

            for subcmd in ("preflight", "run"):
                rc, data, _ = self._run_guard(
                    [
                        subcmd,
                        "--campaign",
                        str(camp),
                        "--shot",
                        "s01",
                        "--kind",
                        "still",
                        "--round",
                        "R3",
                        "--round-cap",
                        "50",
                        "--model",
                        "gpt_image_2_6",
                        "--higgsfield-bin",
                        str(mock_bin),
                    ],
                    env,
                )
                self.assertEqual(rc, 2, msg=f"Expected corrupt_shotlist on {subcmd}: {data}")
                self.assertFalse(data["ok"])
                self.assertEqual(data["error_code"], "corrupt_shotlist")
            self.assertEqual(self._read_mock_calls(log_path), [])

    def test_subround_r4a_r4b_isolation_and_surgical_delta_cap(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            camp = tmp / "camp"
            _write_brief(camp, campaign_cap=200, max_retries=2)
            mock_bin, env, _, _ = self._setup_env(tmp)
            env["MOCK_HF_COST"] = "15"

            # R4A pilot spends 15 inside R4A cap 20
            rc_a, data_a, err_a = self._run_guard(
                [
                    "run",
                    "--campaign",
                    str(camp),
                    "--shot",
                    "s02",
                    "--kind",
                    "video",
                    "--round",
                    "R4A",
                    "--round-cap",
                    "20",
                    "--model",
                    "cinematic_studio_video_4_0",
                    "--out",
                    str(camp / "media" / "shots" / "s02-pilot.mp4"),
                    "--higgsfield-bin",
                    str(mock_bin),
                ],
                env,
            )
            self.assertEqual(rc_a, 0, msg=f"err={err_a}\ndata={data_a}")

            # R4B batch spends 15 + 15 = 30 inside R4B cap 30 (R4A's 15 does not collide!)
            for shot_id in ("s01", "s03"):
                rc_b, data_b, err_b = self._run_guard(
                    [
                        "run",
                        "--campaign",
                        str(camp),
                        "--shot",
                        shot_id,
                        "--kind",
                        "video",
                        "--round",
                        "R4B",
                        "--round-cap",
                        "30",
                        "--model",
                        "cinematic_studio_video_4_0",
                        "--out",
                        str(camp / "media" / "shots" / f"{shot_id}-draft.mp4"),
                        "--higgsfield-bin",
                        str(mock_bin),
                    ],
                    env,
                )
                self.assertEqual(rc_b, 0, msg=f"{shot_id} failed: err={err_b}\ndata={data_b}")

            # Surgical re-roll on s01 with unchanged R4B cap 30 must fail
            rc_block, data_block, _ = self._run_guard(
                [
                    "run",
                    "--campaign",
                    str(camp),
                    "--shot",
                    "s01",
                    "--kind",
                    "video",
                    "--round",
                    "R4B",
                    "--round-cap",
                    "30",
                    "--model",
                    "cinematic_studio_video_4_0",
                    "--higgsfield-bin",
                    str(mock_bin),
                ],
                env,
            )
            self.assertEqual(rc_block, 2, msg=data_block)
            self.assertEqual(data_block["error_code"], "round_budget_exceeded")

            # Passing cumulative round_spent (30) + surgical delta (15) = 45 succeeds
            rc_delta, data_delta, err_delta = self._run_guard(
                [
                    "run",
                    "--campaign",
                    str(camp),
                    "--shot",
                    "s01",
                    "--kind",
                    "video",
                    "--round",
                    "R4B",
                    "--round-cap",
                    "45",
                    "--model",
                    "cinematic_studio_video_4_0",
                    "--out",
                    str(camp / "media" / "shots" / "s01-reroll.mp4"),
                    "--higgsfield-bin",
                    str(mock_bin),
                ],
                env,
            )
            self.assertEqual(rc_delta, 0, msg=f"err={err_delta}\ndata={data_delta}")

            rc_st, st_data, _ = self._run_guard(
                ["status", "--campaign", str(camp), "--json"], env
            )
            self.assertEqual(rc_st, 0, msg=st_data)
            self.assertEqual(st_data["rounds"]["R4A"]["spent"], 15, msg=st_data)
            self.assertEqual(st_data["rounds"]["R4B"]["spent"], 45, msg=st_data)
            self.assertEqual(st_data["total_spent"], 60, msg=st_data)

    def test_lookbook_variants_independent_retry_budgets_and_limits(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            camp = tmp / "camp"
            # lookbook_variants=3, max_retries=0 => 1 attempt per distinct variant (A, B, C)
            _write_brief(camp, campaign_cap=400, lookbook_variants=3, max_retries=0)
            mock_bin, env, _, _ = self._setup_env(tmp)
            env["MOCK_HF_COST"] = "10"

            for variant in ("A", "B", "C"):
                out_v = camp / "media" / "lookbook" / f"lb_traveler_hand-{variant}.png"
                rc, data, err = self._run_guard(
                    [
                        "run",
                        "--campaign",
                        str(camp),
                        "--shot",
                        "lb_traveler_hand",
                        "--kind",
                        "lookbook",
                        "--round",
                        "R2",
                        "--round-cap",
                        "100",
                        "--variant",
                        variant,
                        "--model",
                        "gpt_image_2_6",
                        "--out",
                        str(out_v),
                        "--higgsfield-bin",
                        str(mock_bin),
                    ],
                    env,
                )
                self.assertEqual(rc, 0, msg=f"variant {variant} failed: err={err}\ndata={data}")
                self.assertEqual(data["attempt"], 0, msg=data)
                self.assertEqual(data["variant"], variant, msg=data)
                self.assertTrue(out_v.is_file())

            # Second attempt on variant A exceeds max_retries=0
            rc_retry, data_retry, _ = self._run_guard(
                [
                    "run",
                    "--campaign",
                    str(camp),
                    "--shot",
                    "lb_traveler_hand",
                    "--kind",
                    "lookbook",
                    "--round",
                    "R2",
                    "--round-cap",
                    "100",
                    "--variant",
                    "A",
                    "--model",
                    "gpt_image_2_6",
                    "--higgsfield-bin",
                    str(mock_bin),
                ],
                env,
            )
            self.assertEqual(rc_retry, 2, msg=data_retry)
            self.assertEqual(data_retry["error_code"], "retry_limit_exceeded")

            # 4th distinct variant D exceeds brief Lookbook variants: 3
            rc_lim, data_lim, _ = self._run_guard(
                [
                    "run",
                    "--campaign",
                    str(camp),
                    "--shot",
                    "lb_traveler_hand",
                    "--kind",
                    "lookbook",
                    "--round",
                    "R2",
                    "--round-cap",
                    "100",
                    "--variant",
                    "D",
                    "--model",
                    "gpt_image_2_6",
                    "--higgsfield-bin",
                    str(mock_bin),
                ],
                env,
            )
            self.assertEqual(rc_lim, 2, msg=data_lim)
            self.assertEqual(data_lim["error_code"], "variant_limit_exceeded")

            # --variant A on --kind still must fail with invalid_variant
            rc_inv, data_inv, _ = self._run_guard(
                [
                    "preflight",
                    "--campaign",
                    str(camp),
                    "--shot",
                    "s01",
                    "--kind",
                    "still",
                    "--round",
                    "R3",
                    "--round-cap",
                    "50",
                    "--variant",
                    "A",
                    "--model",
                    "gpt_image_2_6",
                    "--higgsfield-bin",
                    str(mock_bin),
                ],
                env,
            )
            self.assertEqual(rc_inv, 2, msg=data_inv)
            self.assertEqual(data_inv["error_code"], "invalid_variant")

    def test_version_bump_grants_fresh_retry_budget_and_mismatch_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            camp = tmp / "camp"
            _write_brief(camp, campaign_cap=200, max_retries=0)
            mock_bin, env, _, _ = self._setup_env(tmp)
            env["MOCK_HF_COST"] = "10"

            shotlist_path = camp / "shotlist.json"
            shotlist_path.write_text(
                json.dumps(
                    _make_locked_shotlist(still_status="ITERATING", still_version=1),
                    indent=2,
                ),
                encoding="utf-8",
            )

            # Attempt 1 at version 1 succeeds
            rc1, data1, err1 = self._run_guard(
                [
                    "run",
                    "--campaign",
                    str(camp),
                    "--shot",
                    "s01",
                    "--kind",
                    "still",
                    "--round",
                    "R3",
                    "--round-cap",
                    "50",
                    "--model",
                    "gpt_image_2_6",
                    "--out",
                    str(camp / "media" / "stills" / "s01-v1.png"),
                    "--higgsfield-bin",
                    str(mock_bin),
                ],
                env,
            )
            self.assertEqual(rc1, 0, msg=f"err={err1}\ndata={data1}")
            self.assertEqual(data1["version"], 1)

            # Passing --version 2 while shotlist.json is still version 1 fails with version_mismatch
            rc_mm, data_mm, _ = self._run_guard(
                [
                    "run",
                    "--campaign",
                    str(camp),
                    "--shot",
                    "s01",
                    "--kind",
                    "still",
                    "--round",
                    "R3",
                    "--round-cap",
                    "50",
                    "--version",
                    "2",
                    "--model",
                    "gpt_image_2_6",
                    "--higgsfield-bin",
                    str(mock_bin),
                ],
                env,
            )
            self.assertEqual(rc_mm, 2, msg=data_mm)
            self.assertEqual(data_mm["error_code"], "version_mismatch")

            # Bumping shotlist.json version to 2 grants fresh retry budget for --version 2
            shotlist_path.write_text(
                json.dumps(
                    _make_locked_shotlist(still_status="ITERATING", still_version=2),
                    indent=2,
                ),
                encoding="utf-8",
            )
            out_v2 = camp / "media" / "stills" / "s01-v2.png"
            rc2, data2, err2 = self._run_guard(
                [
                    "run",
                    "--campaign",
                    str(camp),
                    "--shot",
                    "s01",
                    "--kind",
                    "still",
                    "--round",
                    "R3",
                    "--round-cap",
                    "50",
                    "--version",
                    "2",
                    "--model",
                    "gpt_image_2_6",
                    "--out",
                    str(out_v2),
                    "--higgsfield-bin",
                    str(mock_bin),
                ],
                env,
            )
            self.assertEqual(rc2, 0, msg=f"err={err2}\ndata={data2}")
            self.assertEqual(data2["version"], 2)
            self.assertEqual(data2["attempt"], 0)
            self.assertTrue(out_v2.is_file())

    def test_timeout_with_job_id_keeps_in_progress_and_resumes_without_double_spend(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            camp = tmp / "camp"
            _write_brief(camp, campaign_cap=100, max_retries=2)
            mock_bin, env, log_path, _ = self._setup_env(tmp)
            env["MOCK_HF_COST"] = "15"

            # Case A: create/wait returns {"job_id": "mock-job-001", "status": "timeout"} (rc=0)
            env["MOCK_HF_CREATE_STATUS"] = "timeout"
            out_s01 = camp / "media" / "shots" / "s01-t1.mp4"
            s01_args = [
                "run",
                "--campaign",
                str(camp),
                "--shot",
                "s01",
                "--kind",
                "video",
                "--round",
                "R4",
                "--round-cap",
                "60",
                "--model",
                "cinematic_studio_video_4_0",
                "--out",
                str(out_s01),
                "--higgsfield-bin",
                str(mock_bin),
            ]
            rc1, data1, _ = self._run_guard(s01_args, env)
            self.assertNotEqual(rc1, 0, msg=data1)
            self.assertEqual(data1["status"], "in_progress", msg=data1)
            self.assertEqual(data1["credits"], 15, msg=data1)
            self.assertEqual(data1["job_id"], "mock-job-001", msg=data1)

            # Retry resumes via generate get/wait without creating a duplicate job
            env.pop("MOCK_HF_CREATE_STATUS", None)
            log_path.write_text("", encoding="utf-8")
            rc1_res, data1_res, err1_res = self._run_guard(s01_args, env)
            self.assertEqual(rc1_res, 0, msg=f"err={err1_res}\ndata={data1_res}")
            self.assertTrue(data1_res["resumed"])
            self.assertEqual(data1_res["job_id"], "mock-job-001")
            self.assertTrue(out_s01.is_file())
            calls1 = self._read_mock_calls(log_path)
            self.assertEqual(
                [c for c in calls1 if c[:2] == ["generate", "create"]],
                [],
                msg=f"Unexpected duplicate create on timeout resume: {calls1}",
            )

            # Case B: rc=1 with {"job_id": "mock-job-002", "error": "timed out"}
            env["MOCK_HF_TIMEOUT_WITH_JOB"] = "1"
            out_s02 = camp / "media" / "shots" / "s02-t2.mp4"
            s02_args = [
                "run",
                "--campaign",
                str(camp),
                "--shot",
                "s02",
                "--kind",
                "video",
                "--round",
                "R4",
                "--round-cap",
                "60",
                "--model",
                "cinematic_studio_video_4_0",
                "--out",
                str(out_s02),
                "--higgsfield-bin",
                str(mock_bin),
            ]
            rc2, data2, _ = self._run_guard(s02_args, env)
            self.assertNotEqual(rc2, 0, msg=data2)
            self.assertEqual(data2["status"], "in_progress", msg=data2)
            self.assertEqual(data2["credits"], 15, msg=data2)
            self.assertEqual(data2["job_id"], "mock-job-002", msg=data2)

            env.pop("MOCK_HF_TIMEOUT_WITH_JOB", None)
            log_path.write_text("", encoding="utf-8")
            rc2_res, data2_res, err2_res = self._run_guard(s02_args, env)
            self.assertEqual(rc2_res, 0, msg=f"err={err2_res}\ndata={data2_res}")
            self.assertTrue(data2_res["resumed"])
            self.assertEqual(data2_res["job_id"], "mock-job-002")
            self.assertTrue(out_s02.is_file())
            calls2 = self._read_mock_calls(log_path)
            self.assertEqual(
                [c for c in calls2 if c[:2] == ["generate", "create"]],
                [],
                msg=f"Unexpected duplicate create on rc=1 timeout resume: {calls2}",
            )

            rc_st, st_data, _ = self._run_guard(
                ["status", "--campaign", str(camp), "--json"], env
            )
            self.assertEqual(rc_st, 0, msg=st_data)
            self.assertEqual(st_data["total_spent"], 30, msg=st_data)

    def test_timeout_without_job_id_does_not_release_to_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            camp = tmp / "camp"
            _write_brief(camp, campaign_cap=50, max_retries=2)
            mock_bin, env, _, _ = self._setup_env(tmp)
            env["MOCK_HF_COST"] = "15"
            env["MOCK_HF_TIMEOUT_NO_JOB"] = "1"

            rc, data, _ = self._run_guard(
                [
                    "run",
                    "--campaign",
                    str(camp),
                    "--shot",
                    "s01",
                    "--kind",
                    "video",
                    "--round",
                    "R4",
                    "--round-cap",
                    "50",
                    "--model",
                    "cinematic_studio_video_4_0",
                    "--higgsfield-bin",
                    str(mock_bin),
                ],
                env,
            )
            self.assertNotEqual(rc, 0, msg=data)
            self.assertNotEqual(
                data.get("status"),
                "rejected",
                msg=f"Ambiguous timeout without job_id must NOT release to rejected: {data}",
            )
            self.assertEqual(data.get("credits"), 15, msg=data)

            rc_st, st_data, _ = self._run_guard(
                ["status", "--campaign", str(camp), "--json"], env
            )
            self.assertEqual(rc_st, 0, msg=st_data)
            self.assertEqual(st_data["total_spent"], 15, msg=st_data)
            self.assertEqual(st_data["active_reserved"], 15, msg=st_data)

    def test_soul_id_in_flight_job_resumes_via_soul_id_get_or_wait(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            camp = tmp / "camp"
            _write_brief(camp, campaign_cap=100, max_retries=2)
            mock_bin, env, log_path, _ = self._setup_env(tmp)
            env["MOCK_HF_COST"] = "20"
            env["MOCK_HF_GET_STATUS"] = "in_progress"

            base_soul = [
                "--campaign",
                str(camp),
                "--shot",
                "lb_actor",
                "--kind",
                "lookbook",
                "--round",
                "R2",
                "--round-cap",
                "100",
                "--variant",
                "A",
                "--command",
                "soul-id",
                "--model",
                "soul_id_v1",
                "--higgsfield-bin",
                str(mock_bin),
            ]
            rc_dry, dry_data, err_dry = self._run_guard(["run", *base_soul, "--dry-run"], env)
            self.assertEqual(rc_dry, 0, msg=f"err={err_dry}\ndata={dry_data}")
            params_hash = dry_data["params_hash"]

            soul_job = "soul-job-888"
            (camp / "receipts.jsonl").write_text(
                json.dumps(
                    {
                        "ts": "2026-11-19T21:00:00Z",
                        "reservation_id": "res-soul-888",
                        "shot": "lb_actor",
                        "kind": "lookbook",
                        "round": "R2",
                        "round_cap": 100,
                        "variant": "A",
                        "version": 1,
                        "command": "soul-id",
                        "model": "soul_id_v1",
                        "is_workflow": False,
                        "params_hash": params_hash,
                        "job_id": soul_job,
                        "status": "in_progress",
                        "estimated_credits": 20,
                        "actual_credits": None,
                        "credits": 20,
                        "url": None,
                        "out": None,
                        "attempt": 0,
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            log_path.write_text("", encoding="utf-8")

            out_file = camp / "media" / "lookbook" / "lb_actor-a.png"
            rc, data, err = self._run_guard(
                ["run", *base_soul, "--out", str(out_file)], env
            )
            self.assertEqual(rc, 0, msg=f"err={err}\ndata={data}")
            self.assertTrue(data["ok"])
            self.assertTrue(data["resumed"])
            self.assertEqual(data["job_id"], soul_job)
            self.assertTrue(out_file.is_file())
            self.assertEqual(out_file.read_bytes(), f"MOCK-RESUMED-{soul_job}".encode())

            calls = self._read_mock_calls(log_path)
            self.assertEqual(
                [c for c in calls if c[:2] == ["soul-id", "create"]],
                [],
                msg=f"Unexpected duplicate soul-id create: {calls}",
            )
            self.assertTrue(
                any(c[:3] in (["soul-id", "get", soul_job], ["soul-id", "wait", soul_job]) for c in calls),
                msg=f"Expected soul-id get/wait call, got: {calls}",
            )

    def test_preflight_blocks_local_paths_across_media_flags_and_variants(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            camp = tmp / "camp"
            _write_brief(camp, campaign_cap=100, max_retries=2)
            mock_bin, env, log_path, _ = self._setup_env(tmp)

            # Create an actual local file with NO media extension to test Path.exists() detection
            existing_no_ext = tmp / "opaque_local_blob"
            existing_no_ext.write_bytes(b"RAWBYTES")
            # Create an existing file inside repo/tmp with a comma in its name
            existing_comma = tmp / "frame_1,v2"
            existing_comma.write_bytes(b"RAWBYTES")

            blocked_cases: list[tuple[list[str], str]] = [
                (["--start_image", "./foo.png"], "--start_image"),
                (["--start-image", "../frame.webp"], "--start-image"),
                (["--start_image=./foo.png"], "--start_image"),
                (["--start-image=./foo.png"], "--start-image"),
                (["--end_image", "hero_end.jpeg"], "--end_image"),
                (["--image", "~/Pictures/shot.png"], "--image"),
                (["--image_references=media/ref.jpg"], "--image_references"),
                (
                    [
                        "--image-references",
                        "550e8400-e29b-41d4-a716-446655440000,media/ref.jpg",
                    ],
                    "--image-references",
                ),
                (["--video", "clip.mp4"], "--video"),
                (["--video_references", "/abs/path/driver.mov"], "--video_references"),
                (["--audio", "voice.wav"], "--audio"),
                (["--audio_references=tracks/score.mp3"], "--audio_references"),
                (["--character_images", '["./hero.png"]'], "--character_images"),
                (["--character_image", r"media\face.png"], "--character_image"),
                (["--location_image", "file:///tmp/loc.png"], "--location_image"),
                (["--input_images", "logo.svg"], "--input_images"),
                (["--input_video", "mesh.glb"], "--input_video"),
                (["--product_image", str(existing_no_ext)], "--product_image"),
                (["--ref_image", str(existing_comma)], "--ref_image"),
                (["--mask", "./matte.png"], "--mask"),
                (["--no-color", "--start_image", "./after_bool.png"], "--start_image"),
            ]

            for extra, expected_flag in blocked_cases:
                log_path.write_text("", encoding="utf-8")
                rc, data, err = self._run_guard(
                    [
                        "preflight",
                        "--campaign",
                        str(camp),
                        "--shot",
                        "s01",
                        "--kind",
                        "video",
                        "--round",
                        "R4",
                        "--round-cap",
                        "50",
                        "--model",
                        "seedance_2_5",
                        "--higgsfield-bin",
                        str(mock_bin),
                        "--",
                        *extra,
                    ],
                    env,
                )
                self.assertEqual(
                    rc,
                    2,
                    msg=f"Expected exit 2 for {extra}: err={err} data={data}",
                )
                self.assertFalse(data.get("ok", True), msg=data)
                self.assertEqual(
                    data.get("error_code"),
                    "local_path_in_cost_quote",
                    msg=f"Unexpected error_code for {extra}: {data}",
                )
                self.assertIn(expected_flag, data.get("offending_flags", []), msg=data)
                self.assertIn(expected_flag, data.get("message", ""), msg=data)
                self.assertIn("UUID", data.get("message", ""), msg=data)
                self.assertEqual(
                    self._read_mock_calls(log_path),
                    [],
                    msg=f"preflight must fail closed BEFORE calling CLI for {extra}",
                )

            # Bare relative filename without slash or extension that exists in CWD
            proc_cwd = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "preflight",
                    "--campaign",
                    str(camp),
                    "--shot",
                    "s01",
                    "--kind",
                    "video",
                    "--round",
                    "R4",
                    "--round-cap",
                    "50",
                    "--model",
                    "seedance_2_5",
                    "--higgsfield-bin",
                    str(mock_bin),
                    "--",
                    "--start_image",
                    existing_no_ext.name,
                ],
                cwd=str(tmp),
                capture_output=True,
                text=True,
                env=env,
                check=False,
            )
            cwd_data = json.loads(proc_cwd.stdout)
            self.assertEqual(proc_cwd.returncode, 2, msg=cwd_data)
            self.assertEqual(cwd_data.get("error_code"), "local_path_in_cost_quote", msg=cwd_data)
            self.assertEqual(self._read_mock_calls(log_path), [])

            # run --dry-run must also fail closed BEFORE calling generate cost
            log_path.write_text("", encoding="utf-8")
            rc_dry, dry_data, _ = self._run_guard(
                [
                    "run",
                    "--campaign",
                    str(camp),
                    "--shot",
                    "s01",
                    "--kind",
                    "video",
                    "--round",
                    "R4",
                    "--round-cap",
                    "50",
                    "--model",
                    "seedance_2_5",
                    "--dry-run",
                    "--higgsfield-bin",
                    str(mock_bin),
                    "--",
                    "--start_image",
                    "./foo.png",
                ],
                env,
            )
            self.assertEqual(rc_dry, 2, msg=dry_data)
            self.assertFalse(dry_data.get("ok", True))
            self.assertEqual(dry_data.get("error_code"), "local_path_in_cost_quote", msg=dry_data)
            cost_calls = [c for c in self._read_mock_calls(log_path) if "cost" in c]
            self.assertEqual(cost_calls, [], msg=f"run --dry-run leaked local path to cost: {cost_calls}")

    def test_preflight_allows_uuids_https_urls_and_non_media_prompt_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            camp = tmp / "camp"
            _write_brief(camp, campaign_cap=100, max_retries=2)
            mock_bin, env, log_path, _ = self._setup_env(tmp)
            env["MOCK_HF_COST"] = "12"

            rc, data, err = self._run_guard(
                [
                    "preflight",
                    "--campaign",
                    str(camp),
                    "--shot",
                    "s01",
                    "--kind",
                    "video",
                    "--round",
                    "R4",
                    "--round-cap",
                    "50",
                    "--model",
                    "seedance_2_5",
                    "--higgsfield-bin",
                    str(mock_bin),
                    "--",
                    "--mode",
                    "omni_reference",
                    "--duration",
                    "5",
                    "--start_image",
                    "550e8400-e29b-41d4-a716-446655440000",
                    "--end_image=https://cdn.higgsfield.ai/uploads/end_frame.png",
                    "--image_references",
                    "550e8400-e29b-41d4-a716-446655440000,https://cdn.example.com/ref.jpg?w=100,h=200",
                    "--character_images",
                    '["550e8400-e29b-41d4-a716-446655440000"]',
                    "--video_references",
                    "https://cdn.example.com/driver.mp4",
                    "--audio_references",
                    "http://cdn.example.com/vo.wav",
                    "--prompt",
                    "Match lighting from ./notes/ref.png shot at f/1.4",
                ],
                env,
            )
            self.assertEqual(rc, 0, msg=f"err={err}\ndata={data}")
            self.assertTrue(data["ok"])
            self.assertEqual(data["estimated_credits"], 12)
            cost_calls = [c for c in self._read_mock_calls(log_path) if c[:2] == ["generate", "cost"]]
            self.assertEqual(len(cost_calls), 1, msg=cost_calls)
            self.assertIn("550e8400-e29b-41d4-a716-446655440000", cost_calls[0])
            self.assertIn("--end_image=https://cdn.higgsfield.ai/uploads/end_frame.png", cost_calls[0])

    def test_run_with_local_path_strips_from_cost_quote_warns_and_preserves_exec(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            camp = tmp / "camp"
            _write_brief(camp, campaign_cap=100, max_retries=2)
            mock_bin, env, log_path, _ = self._setup_env(tmp)
            env["MOCK_HF_COST"] = "10"

            local_img = camp / "media" / "references" / "product.png"
            local_img.parent.mkdir(parents=True, exist_ok=True)
            local_img.write_bytes(b"\x89PNGMOCK")
            out_img = camp / "media" / "stills" / "s01-ps.png"

            rc, data, err = self._run_guard(
                [
                    "run",
                    "--campaign",
                    str(camp),
                    "--shot",
                    "s01",
                    "--kind",
                    "still",
                    "--round",
                    "R3",
                    "--round-cap",
                    "50",
                    "--command",
                    "product-photoshoot",
                    "--model",
                    "gpt_image_2",
                    "--out",
                    str(out_img),
                    "--higgsfield-bin",
                    str(mock_bin),
                    "--",
                    "--mode",
                    "lifestyle_scene",
                    "--image",
                    str(local_img),
                ],
                env,
            )
            self.assertEqual(rc, 0, msg=f"err={err}\ndata={data}")
            self.assertTrue(data["ok"])
            self.assertTrue(out_img.is_file())
            self.assertTrue(
                any("stripped local file path" in w and "--image" in w for w in data.get("warnings", [])),
                msg=f"Expected local-path strip warning, got: {data.get('warnings')}",
            )

            calls = self._read_mock_calls(log_path)
            cost_calls = [c for c in calls if len(c) >= 2 and c[1] == "cost"]
            create_calls = [c for c in calls if c[:2] == ["product-photoshoot", "create"]]
            self.assertEqual(len(cost_calls), 1, msg=calls)
            self.assertNotIn(str(local_img), cost_calls[0], msg=f"Local path leaked to cost: {cost_calls}")
            self.assertNotIn("--image", cost_calls[0], msg=f"Local-only flag leaked to cost: {cost_calls}")
            self.assertEqual(len(create_calls), 1, msg=calls)
            self.assertIn(str(local_img), create_calls[0], msg=f"Legitimate run exec lost --image: {create_calls}")

            # Mixed comma-separated UUID + local path: cost keeps UUID, strips local path
            log_path.write_text("", encoding="utf-8")
            out_gen = camp / "media" / "stills" / "s02-gen.png"
            rc2, data2, err2 = self._run_guard(
                [
                    "run",
                    "--campaign",
                    str(camp),
                    "--shot",
                    "s02",
                    "--kind",
                    "still",
                    "--round",
                    "R3",
                    "--round-cap",
                    "50",
                    "--model",
                    "gpt_image_2_6",
                    "--out",
                    str(out_gen),
                    "--higgsfield-bin",
                    str(mock_bin),
                    "--",
                    "--image_references",
                    f"550e8400-e29b-41d4-a716-446655440000,{local_img}",
                ],
                env,
            )
            self.assertEqual(rc2, 0, msg=f"err={err2}\ndata={data2}")
            calls2 = self._read_mock_calls(log_path)
            cost_calls2 = [c for c in calls2 if c[:2] == ["generate", "cost"]]
            self.assertEqual(len(cost_calls2), 1, msg=calls2)
            self.assertIn("550e8400-e29b-41d4-a716-446655440000", cost_calls2[0])
            self.assertNotIn(str(local_img), " ".join(cost_calls2[0]))

    def test_hidden_expensive_default_warnings_in_preflight_and_run(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            camp = tmp / "camp"
            _write_brief(camp, campaign_cap=500, max_retries=5)
            mock_bin, env, _, _ = self._setup_env(tmp)
            env["MOCK_HF_COST"] = "15"

            def _call(
                subcmd: str,
                shot: str,
                model: str,
                extra: list[str],
                *,
                workflow: bool = False,
            ) -> tuple[int, dict, str]:
                argv = [
                    subcmd,
                    "--campaign",
                    str(camp),
                    "--shot",
                    shot,
                    "--kind",
                    "video",
                    "--round",
                    "R4",
                    "--round-cap",
                    "500",
                    "--model",
                    model,
                    "--higgsfield-bin",
                    str(mock_bin),
                ]
                if workflow:
                    argv.append("--workflow")
                if extra:
                    argv.extend(["--", *extra])
                return self._run_guard(argv, env)

            # 1. kling4_0 and kling_4_0_flash without --duration -> warn 10s default; disappears with --duration 5
            for idx, kling_model in enumerate(("kling4_0", "kling_4_0_flash")):
                for subcmd in ("preflight", "run"):
                    rc, data, err = _call(subcmd, f"k_warn_{idx}_{subcmd}", kling_model, [])
                    self.assertEqual(rc, 0, msg=f"err={err}\ndata={data}")
                    self.assertTrue(data["ok"])
                    self.assertTrue(
                        any("10s" in w and "--duration" in w for w in data.get("warnings", [])),
                        msg=f"Expected 10s duration warning for {kling_model} {subcmd}: {data}",
                    )

                for dur_args in (["--duration", "5"], ["--duration=5"]):
                    rc_ok, data_ok, err_ok = _call(
                        "preflight", f"k_ok_{idx}", kling_model, dur_args
                    )
                    self.assertEqual(rc_ok, 0, msg=f"err={err_ok}\ndata={data_ok}")
                    self.assertEqual(data_ok.get("warnings"), [], msg=data_ok)

            # 2. cinematic_studio_video_3_5 without --duration and --prompt_language -> BOTH warnings fire
            for subcmd in ("preflight", "run"):
                rc, data, err = _call(
                    subcmd, f"cs35_both_{subcmd}", "cinematic_studio_video_3_5", [], workflow=True
                )
                self.assertEqual(rc, 0, msg=f"err={err}\ndata={data}")
                self.assertTrue(data["ok"])
                warns = data.get("warnings", [])
                self.assertTrue(
                    any("15s" in w and "--duration" in w for w in warns),
                    msg=f"Expected 15s warning for cs3.5 {subcmd}: {warns}",
                )
                self.assertTrue(
                    any("zh" in w and "--prompt_language" in w for w in warns),
                    msg=f"Expected zh prompt_language warning for cs3.5 {subcmd}: {warns}",
                )

            # Partial explicit flags on cs3.5: only missing one warns
            rc_d, data_d, _ = _call(
                "preflight", "cs35_dur_only", "cinematic_studio_video_3_5", ["--duration", "5"], workflow=True
            )
            self.assertEqual(rc_d, 0, msg=data_d)
            self.assertEqual(len(data_d["warnings"]), 1, msg=data_d["warnings"])
            self.assertIn("zh", data_d["warnings"][0])

            # Both explicit flags (underscore and hyphen variants) clear ALL warnings on preflight and run
            for idx, explicit in enumerate(
                (
                    ["--duration", "5", "--prompt_language", "en"],
                    ["--duration=5", "--prompt-language=en"],
                )
            ):
                for subcmd in ("preflight", "run"):
                    rc_c, data_c, err_c = _call(
                        subcmd,
                        f"cs35_clean_{idx}_{subcmd}",
                        "cinematic_studio_video_3_5",
                        explicit,
                        workflow=True,
                    )
                    self.assertEqual(rc_c, 0, msg=f"err={err_c}\ndata={data_c}")
                    self.assertEqual(data_c.get("warnings"), [], msg=data_c)

            # 3. cinematic_studio_3_0 without --prompt_language -> warns zh; clears with underscore/hyphen flag
            for subcmd in ("preflight", "run"):
                rc, data, err = _call(
                    subcmd, f"cs30_warn_{subcmd}", "cinematic_studio_3_0", [], workflow=True
                )
                self.assertEqual(rc, 0, msg=f"err={err}\ndata={data}")
                self.assertTrue(
                    any("zh" in w and "--prompt_language" in w for w in data.get("warnings", [])),
                    msg=data,
                )
            for lang_args in (["--prompt_language", "en"], ["--prompt-language", "en"]):
                rc_c, data_c, _ = _call(
                    "preflight", "cs30_clean", "cinematic_studio_3_0", lang_args, workflow=True
                )
                self.assertEqual(rc_c, 0, msg=data_c)
                self.assertEqual(data_c.get("warnings"), [], msg=data_c)

            # 4. marketing_studio_video without --duration -> warns 15s; clears with --duration 5
            for subcmd in ("preflight", "run"):
                rc, data, err = _call(
                    subcmd, f"msv_warn_{subcmd}", "marketing_studio_video", [], workflow=True
                )
                self.assertEqual(rc, 0, msg=f"err={err}\ndata={data}")
                self.assertTrue(
                    any("15s" in w and "--duration" in w for w in data.get("warnings", [])),
                    msg=data,
                )
            rc_msv_ok, data_msv_ok, _ = _call(
                "preflight", "msv_clean", "marketing_studio_video", ["--duration", "5"], workflow=True
            )
            self.assertEqual(rc_msv_ok, 0, msg=data_msv_ok)
            self.assertEqual(data_msv_ok.get("warnings"), [], msg=data_msv_ok)

            # 5. Full hf_mult_motion_control & hf_mult_replace_object warn about 10x cheaper _flash Lite;
            #    _flash variants emit zero warnings
            for full_model, flash_model in (
                ("hf_mult_motion_control", "hf_mult_motion_control_flash"),
                ("hf_mult_replace_object", "hf_mult_replace_object_flash"),
            ):
                for subcmd in ("preflight", "run"):
                    rc_f, data_f, err_f = _call(subcmd, f"{full_model}_{subcmd}", full_model, [])
                    self.assertEqual(rc_f, 0, msg=f"err={err_f}\ndata={data_f}")
                    self.assertTrue(data_f["ok"])
                    self.assertTrue(
                        any(flash_model in w and "10x cheaper" in w for w in data_f.get("warnings", [])),
                        msg=f"Expected _flash Lite warning for {full_model} {subcmd}: {data_f}",
                    )
                rc_fl, data_fl, err_fl = _call("preflight", f"{flash_model}_clean", flash_model, [])
                self.assertEqual(rc_fl, 0, msg=f"err={err_fl}\ndata={data_fl}")
                self.assertEqual(data_fl.get("warnings"), [], msg=data_fl)


if __name__ == "__main__":
    unittest.main()

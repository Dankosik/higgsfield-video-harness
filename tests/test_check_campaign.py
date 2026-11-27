"""Unit and CLI tests for scripts/check-campaign.py."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "scripts" / "check-campaign.py"
EXAMPLE_CAMPAIGN = REPO_ROOT / "campaigns" / "example-product-spot"
EXAMPLE_BRAND = REPO_ROOT / "brands" / "example-brand"


def _copy_campaign_fixture(tmp_root: Path) -> Path:
    """Copy example campaign and brand into an isolated repo-shaped temp directory."""
    (tmp_root / "AGENTS.md").write_text("# Test Fixture Root\n", encoding="utf-8")
    brand_dst = tmp_root / "brands" / "example-brand"
    brand_dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(EXAMPLE_BRAND, brand_dst)

    camp_dst = tmp_root / "campaigns" / "example-product-spot"
    camp_dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(EXAMPLE_CAMPAIGN, camp_dst)
    return camp_dst


def _extract_total_estimated(data: dict) -> int | float | None:
    budget = data.get("budget") or {}
    if not isinstance(budget, dict):
        return None
    for key in (
        "total_estimated",
        "planned_total",
        "total_planned_credits",
        "estimated_total",
        "total",
    ):
        val = budget.get(key)
        if isinstance(val, (int, float)) and not isinstance(val, bool):
            return val
    return None


class TestCheckCampaign(unittest.TestCase):
    def _run(self, target: Path) -> tuple[int, dict, str]:
        proc = subprocess.run(
            [sys.executable, str(SCRIPT), str(target), "--json"],
            capture_output=True,
            text=True,
            check=False,
        )
        combined = f"{proc.stdout}\n{proc.stderr}"
        parsed: dict = {}
        if proc.stdout.strip():
            try:
                parsed = json.loads(proc.stdout)
            except json.JSONDecodeError:
                parsed = {}
        return proc.returncode, parsed, combined

    def test_example_campaign_passes(self) -> None:
        code, data, combined = self._run(EXAMPLE_CAMPAIGN)
        self.assertEqual(code, 0, msg=f"Expected pass, got:\n{combined}")
        self.assertTrue(data["ok"], msg=data)
        self.assertEqual(data.get("errors", []), [])
        total = _extract_total_estimated(data)
        if total is not None:
            self.assertEqual(total, 355)

    def test_example_shotlist_lookbook_continuity_lock_and_test_take_check(self) -> None:
        shotlist = json.loads(
            (EXAMPLE_CAMPAIGN / "shotlist.json").read_text(encoding="utf-8")
        )
        lock = shotlist.get("continuity_lock")
        self.assertIsInstance(lock, dict)
        for key in ("product", "lighting_and_palette", "space_cast_axis"):
            self.assertIsInstance(lock.get(key), str)
            self.assertTrue(lock[key].strip(), msg=f"Empty continuity_lock.{key}")

        lookbook = shotlist.get("lookbook")
        self.assertIsInstance(lookbook, list)
        self.assertEqual(len(lookbook), 1)
        lb = lookbook[0]
        self.assertEqual(lb["id"], "lb_traveler_hand")
        self.assertEqual(lb["status"], "LOCKED")
        self.assertEqual(lb["approved_variant"], "B")
        self.assertIsNone(lb["approved_upload_id"])
        self.assertEqual(lb["estimated_credits"], 30)

        shots_by_id = {s["id"]: s for s in shotlist["shots"]}
        self.assertIsNone(shots_by_id["s01"]["test_take_check"])
        self.assertIsNone(shots_by_id["s03"]["test_take_check"])
        self.assertEqual(shots_by_id["s01"]["still"]["status"], "LOCKED")
        self.assertEqual(shots_by_id["s02"]["still"]["status"], "ITERATING")
        self.assertEqual(shots_by_id["s03"]["still"]["status"], "LOCKED")
        self.assertIn("selected_job_id", shotlist["audio"]["music"])
        self.assertIsNone(shotlist["audio"]["music"]["selected_job_id"])
        s02_check = shots_by_id["s02"]["test_take_check"]
        self.assertIsInstance(s02_check, dict)
        self.assertTrue(s02_check.get("risk", "").strip())
        self.assertTrue(s02_check.get("pass_check", "").strip())

    def test_detects_planned_spend_exceeding_campaign_cap(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            camp = _copy_campaign_fixture(Path(tmp))
            shotlist_path = camp / "shotlist.json"
            shotlist = json.loads(shotlist_path.read_text(encoding="utf-8"))
            # Push planned spend from 355 to 475 (> 400 Campaign cap in brief.md)
            shotlist["shots"][0]["video"]["estimated_final_credits"] = 200
            shotlist_path.write_text(json.dumps(shotlist, indent=2), encoding="utf-8")

            code, data, combined = self._run(camp)
            self.assertEqual(code, 1, msg=f"Expected Campaign cap failure:\n{combined}")
            self.assertFalse(data.get("ok", True))
            errors_text = " ".join(data.get("errors", [])) if data else combined
            self.assertTrue(
                any(tok in errors_text.lower() for tok in ("cap", "budget", "credit", "400")),
                msg=f"Expected budget cap diagnostic, got: {errors_text!r}",
            )

    def test_disabled_audio_does_not_count_toward_campaign_cap(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            camp = _copy_campaign_fixture(Path(tmp))
            shotlist_path = camp / "shotlist.json"
            shotlist = json.loads(shotlist_path.read_text(encoding="utf-8"))
            shotlist["audio"]["voiceover"]["enabled"] = False
            shotlist["audio"]["voiceover"]["estimated_credits"] = 999
            shotlist_path.write_text(json.dumps(shotlist, indent=2), encoding="utf-8")

            code, data, combined = self._run(camp)
            self.assertEqual(
                code,
                0,
                msg=f"Disabled audio should not count toward Campaign cap:\n{combined}",
            )
            self.assertTrue(data["ok"], msg=data)
            total = _extract_total_estimated(data)
            if total is not None:
                self.assertEqual(total, 355)

    def test_accepts_lookbook_ref_and_last_frame_anchors(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            camp = _copy_campaign_fixture(Path(tmp))
            shotlist_path = camp / "shotlist.json"
            shotlist = json.loads(shotlist_path.read_text(encoding="utf-8"))
            shotlist["shots"][0]["video"]["start_image_from"] = "ref_bag_front"
            shotlist["shots"][1]["video"]["start_image_from"] = "lb_traveler_hand"
            shotlist["shots"][1]["video"]["end_image_from"] = "s01.last_frame"
            shotlist_path.write_text(json.dumps(shotlist, indent=2), encoding="utf-8")

            code, data, combined = self._run(camp)
            self.assertEqual(
                code,
                0,
                msg=f"Expected pass for lb_traveler_hand, ref_*, and s01.last_frame:\n{combined}",
            )
            self.assertTrue(data["ok"], msg=data)

            # Unknown anchor must fail
            shotlist["shots"][0]["video"]["start_image_from"] = "ref_does_not_exist"
            shotlist_path.write_text(json.dumps(shotlist, indent=2), encoding="utf-8")
            code_bad, data_bad, combined_bad = self._run(camp)
            self.assertEqual(
                code_bad,
                1,
                msg=f"Expected failure for unknown anchor:\n{combined_bad}",
            )
            self.assertFalse(data_bad.get("ok", True))

    def test_rejects_malformed_continuity_lock_and_test_take_check(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            camp = _copy_campaign_fixture(Path(tmp))
            shotlist_path = camp / "shotlist.json"
            shotlist = json.loads(shotlist_path.read_text(encoding="utf-8"))
            shotlist["continuity_lock"] = {"product": "valid only"}
            shotlist["shots"][1]["test_take_check"] = {"risk": "TBD", "pass_check": ""}
            shotlist_path.write_text(json.dumps(shotlist, indent=2), encoding="utf-8")

            code, data, combined = self._run(camp)
            self.assertEqual(code, 1, msg=f"Expected continuity/test_take failure:\n{combined}")
            errors_text = " ".join(data.get("errors", [])) if data else combined
            self.assertIn("continuity_lock", errors_text)
            self.assertIn("test_take_check", errors_text)

    def test_rejects_invalid_asset_status(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            camp = _copy_campaign_fixture(Path(tmp))
            shotlist_path = camp / "shotlist.json"
            shotlist = json.loads(shotlist_path.read_text(encoding="utf-8"))
            shotlist["shots"][0]["still"]["status"] = "BOGUS"
            shotlist_path.write_text(json.dumps(shotlist, indent=2), encoding="utf-8")

            code, data, combined = self._run(camp)
            self.assertEqual(code, 1, msg=f"Expected invalid status failure:\n{combined}")
            self.assertFalse(data.get("ok", True))
            errors_text = " ".join(data.get("errors", [])) if data else combined
            self.assertTrue(
                any(tok in errors_text.lower() for tok in ("bogus", "status")),
                msg=f"Expected invalid status diagnostic, got: {errors_text!r}",
            )

    def test_rejects_locked_lookbook_missing_approved_variant(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            camp = _copy_campaign_fixture(Path(tmp))
            shotlist_path = camp / "shotlist.json"
            shotlist = json.loads(shotlist_path.read_text(encoding="utf-8"))
            shotlist["lookbook"][0]["status"] = "LOCKED"
            shotlist["lookbook"][0]["approved_variant"] = None
            shotlist_path.write_text(json.dumps(shotlist, indent=2), encoding="utf-8")

            code, data, combined = self._run(camp)
            self.assertEqual(
                code,
                1,
                msg=f"Expected failure when LOCKED lookbook misses approved_variant:\n{combined}",
            )
            self.assertFalse(data.get("ok", True))
            errors_text = " ".join(data.get("errors", [])) if data else combined
            self.assertTrue(
                any(
                    tok in errors_text.lower()
                    for tok in ("approved_variant", "locked", "lookbook")
                ),
                msg=f"Expected approved_variant diagnostic, got: {errors_text!r}",
            )

    def test_rejects_malformed_taste_log_duplicate_and_empty_entry(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            camp = _copy_campaign_fixture(Path(tmp))
            taste_path = camp / "taste-log.md"
            original = taste_path.read_text(encoding="utf-8")

            # Duplicate TL-01 entry
            taste_path.write_text(
                original
                + "\n### TL-01 (R2 — Duplicate Lookbook)\n\n"
                + "- **More of:** Cool morning daylight.\n",
                encoding="utf-8",
            )
            code_dup, data_dup, combined_dup = self._run(camp)
            self.assertEqual(
                code_dup,
                1,
                msg=f"Expected duplicate TL-01 failure:\n{combined_dup}",
            )
            self.assertFalse(data_dup.get("ok", True))
            err_dup = " ".join(data_dup.get("errors", [])) if data_dup else combined_dup
            self.assertTrue(
                any(tok in err_dup.lower() for tok in ("tl-01", "duplicate", "taste")),
                msg=f"Expected duplicate TL-01 diagnostic, got: {err_dup!r}",
            )

            # Empty TL-03 entry with no bullets
            taste_path.write_text(
                original + "\n### TL-03 (R4 — Draft Motion)\n\n",
                encoding="utf-8",
            )
            code_empty, data_empty, combined_empty = self._run(camp)
            self.assertEqual(
                code_empty,
                1,
                msg=f"Expected empty taste-log entry failure:\n{combined_empty}",
            )
            self.assertFalse(data_empty.get("ok", True))
            err_empty = (
                " ".join(data_empty.get("errors", [])) if data_empty else combined_empty
            )
            self.assertTrue(
                any(
                    tok in err_empty.lower()
                    for tok in ("tl-03", "empty", "bullet", "taste")
                ),
                msg=f"Expected empty taste-log diagnostic, got: {err_empty!r}",
            )

    def test_rejects_shots_duration_sum_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            camp = _copy_campaign_fixture(Path(tmp))
            shotlist_path = camp / "shotlist.json"
            shotlist = json.loads(shotlist_path.read_text(encoding="utf-8"))
            shotlist["target_duration_s"] = 30
            shotlist_path.write_text(json.dumps(shotlist, indent=2), encoding="utf-8")

            code, data, combined = self._run(camp)
            self.assertEqual(
                code,
                1,
                msg=f"Expected duration mismatch failure:\n{combined}",
            )
            self.assertFalse(data.get("ok", True))
            errors_text = " ".join(data.get("errors", [])) if data else combined
            self.assertTrue(
                any(tok in errors_text.lower() for tok in ("duration", "target_duration")),
                msg=f"Expected duration mismatch diagnostic, got: {errors_text!r}",
            )

    def test_rejects_cinematic_studio_video_4_0_non_workflow_or_i2v_mode(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            camp = _copy_campaign_fixture(Path(tmp))
            shotlist_path = camp / "shotlist.json"
            base = json.loads(shotlist_path.read_text(encoding="utf-8"))

            # Case 1: is_workflow: false on cinematic_studio_video_4_0
            bad_wf = json.loads(json.dumps(base))
            bad_wf["shots"][0]["video"]["is_workflow"] = False
            shotlist_path.write_text(json.dumps(bad_wf, indent=2), encoding="utf-8")
            code1, data1, comb1 = self._run(camp)
            self.assertEqual(code1, 1, msg=f"Expected is_workflow=false failure:\n{comb1}")
            self.assertFalse(data1.get("ok", True))
            err1 = " ".join(data1.get("errors", [])) if data1 else comb1
            self.assertTrue(
                any(tok in err1.lower() for tok in ("is_workflow", "workflow", "cinematic_studio_video_4_0")),
                msg=f"Expected workflow diagnostic, got: {err1!r}",
            )

            # Case 2: mode: "i2v" on cinematic_studio_video_4_0
            bad_mode = json.loads(json.dumps(base))
            bad_mode["shots"][0]["video"]["is_workflow"] = True
            bad_mode["shots"][0]["video"]["mode"] = "i2v"
            shotlist_path.write_text(json.dumps(bad_mode, indent=2), encoding="utf-8")
            code2, data2, comb2 = self._run(camp)
            self.assertEqual(code2, 1, msg=f"Expected mode=i2v failure:\n{comb2}")
            self.assertFalse(data2.get("ok", True))
            err2 = " ".join(data2.get("errors", [])) if data2 else comb2
            self.assertTrue(
                any(tok in err2.lower() for tok in ("omni_reference", "i2v", "mode", "cinematic_studio_video_4_0")),
                msg=f"Expected mode diagnostic, got: {err2!r}",
            )

    def test_rejects_missing_or_null_credit_estimates(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            camp = _copy_campaign_fixture(Path(tmp))
            shotlist_path = camp / "shotlist.json"
            base = json.loads(shotlist_path.read_text(encoding="utf-8"))

            mutations = [
                ("still.estimated_credits", lambda d: d["shots"][0]["still"].__setitem__("estimated_credits", None)),
                ("video.estimated_draft_credits", lambda d: d["shots"][0]["video"].pop("estimated_draft_credits")),
                ("video.estimated_final_credits", lambda d: d["shots"][0]["video"].__setitem__("estimated_final_credits", None)),
            ]
            for label, mutate in mutations:
                mutated = json.loads(json.dumps(base))
                mutate(mutated)
                shotlist_path.write_text(json.dumps(mutated, indent=2), encoding="utf-8")
                code, data, comb = self._run(camp)
                self.assertEqual(
                    code,
                    1,
                    msg=f"Expected missing/null {label} to fail (not default to 0):\n{comb}",
                )
                self.assertFalse(data.get("ok", True))
                err = " ".join(data.get("errors", [])) if data else comb
                self.assertTrue(
                    any(tok in err.lower() for tok in ("estimated", "credit", label.split(".")[-1])),
                    msg=f"Expected estimate diagnostic for {label}, got: {err!r}",
                )

    def test_rejects_enabled_audio_music_without_valid_status(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            camp = _copy_campaign_fixture(Path(tmp))
            shotlist_path = camp / "shotlist.json"
            base = json.loads(shotlist_path.read_text(encoding="utf-8"))

            # Missing status on enabled audio.music
            missing_st = json.loads(json.dumps(base))
            missing_st["audio"]["music"].pop("status", None)
            shotlist_path.write_text(json.dumps(missing_st, indent=2), encoding="utf-8")
            code1, data1, comb1 = self._run(camp)
            self.assertEqual(code1, 1, msg=f"Expected missing music.status failure:\n{comb1}")
            self.assertFalse(data1.get("ok", True))
            err1 = " ".join(data1.get("errors", [])) if data1 else comb1
            self.assertTrue(
                any(tok in err1.lower() for tok in ("status", "music", "audio")),
                msg=f"Expected audio.music status diagnostic, got: {err1!r}",
            )

            # Invalid status value on enabled audio.music
            bad_st = json.loads(json.dumps(base))
            bad_st["audio"]["music"]["status"] = "UNKNOWN"
            shotlist_path.write_text(json.dumps(bad_st, indent=2), encoding="utf-8")
            code2, data2, comb2 = self._run(camp)
            self.assertEqual(code2, 1, msg=f"Expected invalid music.status failure:\n{comb2}")
            self.assertFalse(data2.get("ok", True))
            err2 = " ".join(data2.get("errors", [])) if data2 else comb2
            self.assertTrue(
                any(tok in err2.lower() for tok in ("status", "unknown", "music")),
                msg=f"Expected invalid audio.music status diagnostic, got: {err2!r}",
            )

    def test_warns_on_missing_high_bitrate_and_480p_pixel_upscale(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            camp = _copy_campaign_fixture(Path(tmp))
            shotlist_path = camp / "shotlist.json"
            base = json.loads(shotlist_path.read_text(encoding="utf-8"))

            # Drop bitrate_mode from shot 0 (CS 4.0 1080p) and set shot 1 to 480p -> bytedance_video_upscale
            mut = json.loads(json.dumps(base))
            mut["shots"][0]["video"]["final_params"].pop("bitrate_mode", None)
            mut["shots"][1]["video"]["model"] = "bytedance_video_upscale"
            mut["shots"][1]["video"]["is_workflow"] = False
            mut["shots"][1]["video"]["draft_params"]["resolution"] = "480p"
            shotlist_path.write_text(json.dumps(mut, indent=2), encoding="utf-8")

            code, data, comb = self._run(camp)
            self.assertEqual(code, 0, msg=f"Warnings should not fail exit code:\n{comb}")
            self.assertTrue(data.get("ok"), msg=data)
            warns = " ".join(data.get("warnings", []))
            self.assertIn("bitrate_mode", warns, msg=data)
            self.assertIn("480p", warns, msg=data)

    def test_enforces_reference_budgets_cel_caps_and_photocopy_guard(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            camp = _copy_campaign_fixture(Path(tmp))
            shotlist_path = camp / "shotlist.json"
            base = json.loads(shotlist_path.read_text(encoding="utf-8"))

            # Add extra declared references so reference IDs resolve cleanly
            extra_refs = [
                {"id": f"ref_extra_{i}", "kind": "prop", "local_path": f"media/references/e{i}.png", "upload_id": None}
                for i in range(1, 11)
            ]
            base["references"].extend(extra_refs)
            extra_ids = [r["id"] for r in extra_refs]

            # Case 1: Optimal-budget warnings, wan3_0 start+refs warning, and .last_frame photocopy warning
            warn_mut = json.loads(json.dumps(base))
            warn_mut["shots"][0]["still"]["references"] = extra_ids[:7]  # > 6 optimal R3 budget
            warn_mut["shots"][0]["video"]["image_references"] = extra_ids[:5]  # + start_image = 6 > 5 optimal video budget
            warn_mut["shots"][1]["video"]["model"] = "wan3_0"
            warn_mut["shots"][1]["video"]["is_workflow"] = False
            warn_mut["shots"][1]["video"]["start_image_from"] = "s02.still"
            warn_mut["shots"][1]["video"]["image_references"] = ["ref_bag_front"]
            warn_mut["shots"][2]["video"]["start_image_from"] = "s02.last_frame"
            warn_mut["shots"][2]["video"]["image_references"] = []
            shotlist_path.write_text(json.dumps(warn_mut, indent=2), encoding="utf-8")

            code_w, data_w, comb_w = self._run(camp)
            self.assertEqual(code_w, 0, msg=f"Advisory spatial warnings must not fail exit code:\n{comb_w}")
            self.assertTrue(data_w.get("ok"), msg=data_w)
            warns_text = " ".join(data_w.get("warnings", []))
            self.assertIn("optimal R3 still budget", warns_text, msg=data_w)
            self.assertIn("optimal R4/R5 video budget", warns_text, msg=data_w)
            self.assertIn("wan3_0", warns_text, msg=data_w)
            self.assertIn("photocopy", warns_text, msg=data_w)

            # Case 2: Hard live CEL cap exceeded (flux_kontext > 4 stills, kling4_0 > 10 video images)
            err_mut = json.loads(json.dumps(base))
            err_mut["shots"][0]["still"]["model"] = "flux_kontext"
            err_mut["shots"][0]["still"]["references"] = extra_ids[:5]  # > 4 CEL cap
            err_mut["shots"][1]["video"]["model"] = "kling4_0"
            err_mut["shots"][1]["video"]["is_workflow"] = False
            err_mut["shots"][1]["video"]["start_image_from"] = "s02.still"
            err_mut["shots"][1]["video"]["image_references"] = extra_ids[:10]  # 10 + start = 11 > 10 CEL cap
            shotlist_path.write_text(json.dumps(err_mut, indent=2), encoding="utf-8")

            code_e, data_e, comb_e = self._run(camp)
            self.assertEqual(code_e, 1, msg=f"Hard CEL cap violations must fail:\n{comb_e}")
            self.assertFalse(data_e.get("ok", True))
            err_text = " ".join(data_e.get("errors", []))
            self.assertIn("flux_kontext", err_text, msg=data_e)
            self.assertIn("kling4_0", err_text, msg=data_e)

    def test_enforces_character_soul_motion_control_and_intone_cel_rules(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            camp = _copy_campaign_fixture(Path(tmp))
            shotlist_path = camp / "shotlist.json"
            base = json.loads(shotlist_path.read_text(encoding="utf-8"))
            base["references"].extend(
                [
                    {"id": "ref_driver_vid", "kind": "driving_video", "local_path": "media/references/act.mp4", "upload_id": None},
                    {"id": "ref_voice_line", "kind": "audio", "local_path": "media/audio/line.wav", "upload_id": None},
                ]
            )

            # Valid config: text2image_soul_v2 (1 ref), kling3_0_motion_control (workflow, 1 img + 1 vid), intone (1 char + 1 aud)
            ok_mut = json.loads(json.dumps(base))
            ok_mut["shots"][0]["still"]["model"] = "text2image_soul_v2"
            ok_mut["shots"][0]["still"]["references"] = ["lb_traveler_hand"]
            ok_mut["shots"][1]["video"]["model"] = "kling3_0_motion_control"
            ok_mut["shots"][1]["video"]["is_workflow"] = True
            ok_mut["shots"][1]["video"]["prompt_file"] = None
            ok_mut["shots"][1]["video"]["start_image_from"] = None
            ok_mut["shots"][1]["video"]["end_image_from"] = None
            ok_mut["shots"][1]["video"]["image_references"] = ["lb_traveler_hand"]
            ok_mut["shots"][1]["video"]["video_references"] = ["ref_driver_vid"]
            ok_mut["shots"][2]["video"]["model"] = "intone"
            ok_mut["shots"][2]["video"]["is_workflow"] = False
            ok_mut["shots"][2]["video"]["start_image_from"] = None
            ok_mut["shots"][2]["video"]["end_image_from"] = None
            ok_mut["shots"][2]["video"]["image_references"] = []
            ok_mut["shots"][2]["video"]["character_images"] = ["lb_traveler_hand"]
            ok_mut["shots"][2]["video"]["audio_references"] = ["ref_voice_line"]
            ok_mut["shots"][2]["video"]["final_params"]["bitrate_mode"] = "high"
            shotlist_path.write_text(json.dumps(ok_mut, indent=2), encoding="utf-8")

            code_ok, data_ok, comb_ok = self._run(camp)
            self.assertEqual(code_ok, 0, msg=f"Valid character/motion/intone config must pass:\n{comb_ok}")
            self.assertTrue(data_ok.get("ok"), msg=data_ok)

            # Invalid config: soul_v2 >1 ref + style_id, kling3_0_motion_control non-workflow & missing video & start_image, intone missing audio & conflicting refs
            bad_mut = json.loads(json.dumps(ok_mut))
            bad_mut["shots"][0]["still"]["references"] = ["lb_traveler_hand", "ref_bag_front"]
            bad_mut["shots"][0]["still"]["style_id"] = "style-uuid"
            bad_mut["shots"][1]["video"]["is_workflow"] = False
            bad_mut["shots"][1]["video"]["start_image_from"] = "s02.still"
            bad_mut["shots"][1]["video"]["video_references"] = []
            bad_mut["shots"][2]["video"]["image_references"] = ["lb_traveler_hand", "ref_bag_front"]
            bad_mut["shots"][2]["video"]["audio_references"] = []
            shotlist_path.write_text(json.dumps(bad_mut, indent=2), encoding="utf-8")

            code_bad, data_bad, comb_bad = self._run(camp)
            self.assertEqual(code_bad, 1, msg=f"Invalid character/motion/intone CEL config must fail:\n{comb_bad}")
            self.assertFalse(data_bad.get("ok", True))
            errs = " ".join(data_bad.get("errors", []))
            self.assertIn("text2image_soul_v2", errs, msg=data_bad)
            self.assertIn("style_id", errs, msg=data_bad)
            self.assertIn("kling3_0_motion_control", errs, msg=data_bad)
            self.assertIn("start_image/end_image", errs, msg=data_bad)
            self.assertIn("intone", errs, msg=data_bad)

    def test_enforces_camera_workflows_speedramp_and_end_image_cel_rules(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            camp = _copy_campaign_fixture(Path(tmp))
            shotlist_path = camp / "shotlist.json"
            base = json.loads(shotlist_path.read_text(encoding="utf-8"))
            base["references"].extend(
                [
                    {"id": "ref_sketch", "kind": "sketch", "local_path": "media/references/sketch.png", "upload_id": None},
                    {"id": "ref_master_vid", "kind": "video", "local_path": "media/references/master.mp4", "upload_id": None},
                ]
            )

            # Valid camera workflow configs: CS 3.5 (camera_style + prompt_language + duration), CS 3.0 (speedramp), reframe (1 video)
            ok_mut = json.loads(json.dumps(base))
            ok_mut["shots"][0]["video"]["model"] = "cinematic_studio_video_3_5"
            ok_mut["shots"][0]["video"]["is_workflow"] = True
            ok_mut["shots"][0]["video"]["draft_params"] = {
                "resolution": "720p",
                "duration": 5,
                "prompt_language": "en",
                "camera_style": "intimate_observer",
            }
            ok_mut["shots"][0]["video"]["final_params"] = {
                "resolution": "1080p",
                "duration": 5,
                "prompt_language": "en",
                "camera_style": "intimate_observer",
            }
            ok_mut["shots"][1]["video"]["model"] = "cinematic_studio_3_0"
            ok_mut["shots"][1]["video"]["is_workflow"] = True
            ok_mut["shots"][1]["video"]["draft_params"] = {
                "resolution": "720p",
                "duration": 5,
                "prompt_language": "en",
                "speedramp": "fast_to_slowmo",
            }
            ok_mut["shots"][1]["video"]["final_params"] = {
                "resolution": "1080p",
                "duration": 5,
                "prompt_language": "en",
                "speedramp": "fast_to_slowmo",
            }
            ok_mut["shots"][2]["video"]["model"] = "reframe"
            ok_mut["shots"][2]["video"]["is_workflow"] = True
            ok_mut["shots"][2]["video"]["start_image_from"] = None
            ok_mut["shots"][2]["video"]["end_image_from"] = None
            ok_mut["shots"][2]["video"]["image_references"] = []
            ok_mut["shots"][2]["video"]["video_references"] = ["ref_master_vid"]
            shotlist_path.write_text(json.dumps(ok_mut, indent=2), encoding="utf-8")

            code_ok, data_ok, comb_ok = self._run(camp)
            self.assertEqual(code_ok, 0, msg=f"Valid camera workflows must pass:\n{comb_ok}")
            self.assertTrue(data_ok.get("ok"), msg=data_ok)

            # Warnings when CS 3.5 omits prompt_language and duration (live CLI defaults zh / 15s)
            warn_mut = json.loads(json.dumps(ok_mut))
            warn_mut["shots"][0]["video"]["draft_params"] = {"camera_style": "silent_machine"}
            warn_mut["shots"][0]["video"]["final_params"] = {"camera_style": "silent_machine"}
            shotlist_path.write_text(json.dumps(warn_mut, indent=2), encoding="utf-8")
            code_w, data_w, comb_w = self._run(camp)
            self.assertEqual(code_w, 0, msg=f"Default-trap warnings must not fail exit code:\n{comb_w}")
            warns = " ".join(data_w.get("warnings", []))
            self.assertIn("prompt_language", warns, msg=data_w)
            self.assertIn("15s", warns, msg=data_w)

            # Hard CEL violations: CS 3.5 camera_style + style_prompt mutex, CS 3.0 invalid speedramp,
            # draw_to_video missing image + start_image, kling_4_0_flash with end_image, cinematic_studio_image > 4 refs
            bad_mut = json.loads(json.dumps(ok_mut))
            bad_mut["shots"][0]["still"]["model"] = "cinematic_studio_image"
            bad_mut["shots"][0]["still"]["references"] = [
                "lb_traveler_hand",
                "ref_bag_front",
                "ref_sketch",
                "ref_master_vid",
                "lb_traveler_hand",
            ]
            bad_mut["shots"][0]["video"]["draft_params"]["style_prompt"] = "conflicting style"
            bad_mut["shots"][1]["video"]["draft_params"]["speedramp"] = "custom"  # v2-only, invalid on 3_0
            bad_mut["shots"][2]["video"]["model"] = "draw_to_video"
            bad_mut["shots"][2]["video"]["is_workflow"] = False
            bad_mut["shots"][2]["video"]["image_references"] = []
            bad_mut["shots"][2]["video"]["start_image_from"] = "s03.still"
            shotlist_path.write_text(json.dumps(bad_mut, indent=2), encoding="utf-8")

            code_bad, data_bad, comb_bad = self._run(camp)
            self.assertEqual(code_bad, 1, msg=f"Invalid camera workflow CEL must fail:\n{comb_bad}")
            errs = " ".join(data_bad.get("errors", []))
            self.assertIn("cinematic_studio_image", errs, msg=data_bad)
            self.assertIn("style_prompt", errs, msg=data_bad)
            self.assertIn("speedramp", errs, msg=data_bad)
            self.assertIn("draw_to_video", errs, msg=data_bad)

            # kling_4_0_flash with end_image must fail
            flash_mut = json.loads(json.dumps(ok_mut))
            flash_mut["shots"][2]["video"]["model"] = "kling_4_0_flash"
            flash_mut["shots"][2]["video"]["is_workflow"] = False
            flash_mut["shots"][2]["video"]["start_image_from"] = "s03.still"
            flash_mut["shots"][2]["video"]["end_image_from"] = "s01.still"
            flash_mut["shots"][2]["video"]["video_references"] = []
            shotlist_path.write_text(json.dumps(flash_mut, indent=2), encoding="utf-8")

            code_f, data_f, comb_f = self._run(camp)
            self.assertEqual(code_f, 1, msg=f"kling_4_0_flash with end_image must fail:\n{comb_f}")
            self.assertIn("kling_4_0_flash", " ".join(data_f.get("errors", [])), msg=data_f)

    def test_narrative_lock_and_narrative_job_are_optional_but_validated_when_present(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            camp = _copy_campaign_fixture(Path(tmp))
            shotlist_path = camp / "shotlist.json"
            shotlist = json.loads(shotlist_path.read_text(encoding="utf-8"))

            # 1) Example fixture with narrative_lock & narrative_job passes
            self.assertIsInstance(shotlist.get("narrative_lock"), dict)
            for shot in shotlist["shots"]:
                self.assertIsInstance(shot.get("narrative_job"), dict)
            code_ok, data_ok, comb_ok = self._run(camp)
            self.assertEqual(code_ok, 0, msg=comb_ok)
            self.assertTrue(data_ok["ok"], msg=data_ok)

            # 2) Omitting narrative_lock and narrative_job remains backwards-compatible
            legacy = json.loads(json.dumps(shotlist))
            legacy.pop("narrative_lock", None)
            for shot in legacy["shots"]:
                shot.pop("narrative_job", None)
            shotlist_path.write_text(json.dumps(legacy, indent=2), encoding="utf-8")
            code_leg, data_leg, comb_leg = self._run(camp)
            self.assertEqual(code_leg, 0, msg=f"Legacy shotlist without narrative fields must pass:\n{comb_leg}")
            self.assertTrue(data_leg["ok"], msg=data_leg)

            # 3) Malformed narrative_lock and invalid shot narrative_job must fail
            bad = json.loads(json.dumps(shotlist))
            bad["narrative_lock"] = {"human_truth": "TBD"}
            bad["shots"][0]["narrative_job"] = {"beat_function": "filler", "delta": ""}
            shotlist_path.write_text(json.dumps(bad, indent=2), encoding="utf-8")
            code_bad, data_bad, comb_bad = self._run(camp)
            self.assertEqual(code_bad, 1, msg=f"Malformed narrative fields must fail:\n{comb_bad}")
            errs = " ".join(data_bad.get("errors", []))
            self.assertIn("narrative_lock", errs, msg=data_bad)
            self.assertIn("narrative_job", errs, msg=data_bad)
            self.assertIn("beat_function", errs, msg=data_bad)

    def test_validates_production_track_outfit_edit_prompt_timing_and_receipt_drift(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            camp = _copy_campaign_fixture(Path(tmp))
            shotlist_path = camp / "shotlist.json"
            data = json.loads(shotlist_path.read_text(encoding="utf-8"))

            # Valid production_track, sub_flows, lookbook outfit kind, and shot edit spec pass cleanly
            data["production_track"] = "scratch_cinema"
            data["sub_flows"] = ["remotion_overlays", "shorts_cutdown"]
            data["lookbook"].append(
                {
                    "id": "lb_traveler_coat",
                    "kind": "outfit",
                    "title": "Flat-lay matte charcoal wool overcoat",
                    "model": "seedream_v5_pro",
                    "prompt_file": "prompts/lb_traveler_v1.txt",
                    "variants_requested": 1,
                    "status": "LOCKED",
                    "version": 1,
                    "approved_variant": "A",
                    "approved_take": None,
                    "approved_upload_id": None,
                    "estimated_credits": 2.5,
                }
            )
            data["shots"][0]["edit"] = {
                "trim_in": 0.5,
                "trim_out": 4.0,
                "crop_4k_punchin": "center_2x",
                "grade": {"brightness": -0.02, "saturation": 0.96},
                "fade_out_black_s": 0.5,
            }
            shotlist_path.write_text(json.dumps(data, indent=2), encoding="utf-8")

            # Prompt timecodes exceeding shot duration_s=5s trigger advisory warning
            (camp / "prompts" / "s01_video_v1.txt").write_text(
                "0-4s: Slow dolly in.\n4-9s: Hand opens clasp.\nNO MUSIC. NO BACKGROUND SCORE. Native diegetic sound only.\n",
                encoding="utf-8",
            )
            # Receipt model mismatch triggers advisory reconciliation warning
            (camp / "receipts.jsonl").write_text(
                json.dumps({"shot": "s01", "kind": "video", "status": "completed", "model": "veo3_1"}) + "\n",
                encoding="utf-8",
            )
            code, res, comb = self._run(camp)
            self.assertEqual(code, 0, msg=comb)
            warns = " ".join(res.get("warnings", []))
            self.assertIn("prompt timecodes end at 9s", warns, msg=res)
            self.assertIn("differs from latest completed receipt model 'veo3_1'", warns, msg=res)

            # Invalid production_track, invalid sub_flows, invalid edit.trim_out <= trim_in, and invalid VO track trim fail
            data["production_track"] = "invalid_track"
            data["sub_flows"] = ["bogus_sub_flow"]
            data["shots"][0]["edit"]["trim_in"] = 4.0
            data["shots"][0]["edit"]["trim_out"] = 2.0
            data["audio"]["voiceover"]["tracks"] = [{"trim_start_s": 2.0, "trim_end_s": 1.0}]
            shotlist_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
            code_bad, res_bad, _ = self._run(camp)
            self.assertEqual(code_bad, 1, msg=res_bad)
            errs = " ".join(res_bad.get("errors", []))
            self.assertIn("production_track", errs, msg=res_bad)
            self.assertIn("sub_flows", errs, msg=res_bad)
            self.assertIn("trim_out", errs, msg=res_bad)
            self.assertIn("trim_end_s", errs, msg=res_bad)

            # kling3_0 bridging from .last_frame without canonical refs triggers photocopy-cascade warning,
            # and >8s single-shot I2V triggers long-clip drift warning; trim_out compares prompt against raw duration
            data2 = json.loads((camp / "shotlist.json").read_text(encoding="utf-8"))
            data2["production_track"] = "scratch_cinema"
            data2["sub_flows"] = []
            data2["shots"][0]["edit"] = {"trim_in": 0.0, "trim_out": 5.0}
            data2["shots"][0]["video"]["final_params"]["duration"] = 9
            data2["audio"]["voiceover"].pop("tracks", None)
            data2["shots"][2]["video"]["model"] = "kling3_0"
            data2["shots"][2]["video"]["is_workflow"] = False
            data2["shots"][2]["video"]["start_image_from"] = "s02.last_frame"
            data2["shots"][2]["video"]["image_references"] = []
            data2["shots"][2]["duration_s"] = 11
            data2["target_duration_s"] = 21
            shotlist_path.write_text(json.dumps(data2, indent=2), encoding="utf-8")
            code_k3, res_k3, comb_k3 = self._run(camp)
            self.assertEqual(code_k3, 0, msg=comb_k3)
            warns_k3 = " ".join(res_k3.get("warnings", []))
            self.assertIn("photocopy", warns_k3, msg=res_k3)
            self.assertIn("single-shot I2V duration (11s > 8s)", warns_k3, msg=res_k3)
            self.assertNotIn("prompt timecodes end at 9s", warns_k3, msg=res_k3)
    def test_enforces_kling4_0_and_kling_4_0_flash_live_cli_guards(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            camp = _copy_campaign_fixture(Path(tmp))
            shotlist_path = camp / "shotlist.json"
            base = json.loads(shotlist_path.read_text(encoding="utf-8"))

            # Clean pass: kling4_0 with explicit duration=5, kling_4_0_flash at 720p with duration=5,
            # and kling4_0 with duration_s=10 omitting duration (matches 10s CLI default)
            ok_mut = json.loads(json.dumps(base))
            ok_mut["target_duration_s"] = 20
            ok_mut["shots"][0]["duration_s"] = 5
            ok_mut["shots"][0]["video"]["model"] = "kling4_0"
            ok_mut["shots"][0]["video"]["is_workflow"] = False
            ok_mut["shots"][0]["video"]["draft_params"] = {"resolution": "720p", "duration": 5}
            ok_mut["shots"][0]["video"]["final_params"] = {"resolution": "1080p", "duration": 5}
            ok_mut["shots"][1]["duration_s"] = 5
            ok_mut["shots"][1]["video"]["model"] = "kling_4_0_flash"
            ok_mut["shots"][1]["video"]["is_workflow"] = False
            ok_mut["shots"][1]["video"]["end_image_from"] = None
            ok_mut["shots"][1]["video"]["draft_params"] = {"resolution": "720p", "duration": 5}
            ok_mut["shots"][1]["video"]["final_params"] = {"resolution": "720p", "duration": 5}
            ok_mut["shots"][2]["duration_s"] = 10
            ok_mut["shots"][2]["video"]["model"] = "kling4_0"
            ok_mut["shots"][2]["video"]["is_workflow"] = False
            ok_mut["shots"][2]["video"]["draft_params"] = {"resolution": "720p"}
            ok_mut["shots"][2]["video"]["final_params"] = {"resolution": "1080p"}
            shotlist_path.write_text(json.dumps(ok_mut, indent=2), encoding="utf-8")

            code_ok, data_ok, comb_ok = self._run(camp)
            self.assertEqual(code_ok, 0, msg=f"Valid kling4_0/flash config must pass:\n{comb_ok}")
            self.assertTrue(data_ok.get("ok"), msg=data_ok)
            warns_ok = " ".join(data_ok.get("warnings", []))
            self.assertNotIn("defaults duration", warns_ok, msg=data_ok)
            self.assertNotIn("kling_4_0_flash", warns_ok, msg=data_ok)

            # Warnings when duration is omitted on duration_s != 10
            warn_mut = json.loads(json.dumps(ok_mut))
            warn_mut["shots"][0]["video"]["draft_params"] = {"resolution": "720p"}
            warn_mut["shots"][0]["video"]["final_params"] = {"resolution": "1080p"}
            warn_mut["shots"][1]["video"]["draft_params"] = {"resolution": "720p"}
            warn_mut["shots"][1]["video"]["final_params"] = {"resolution": "720p"}
            shotlist_path.write_text(json.dumps(warn_mut, indent=2), encoding="utf-8")

            code_w, data_w, comb_w = self._run(camp)
            self.assertEqual(code_w, 0, msg=f"Missing duration warnings must not fail:\n{comb_w}")
            warns_w = " ".join(data_w.get("warnings", []))
            self.assertIn("kling4_0", warns_w, msg=data_w)
            self.assertIn("kling_4_0_flash", warns_w, msg=data_w)
            self.assertIn("10s", warns_w, msg=data_w)

            # Hard errors: kling4_0 multi_shots / multi_prompt, kling_4_0_flash non-720p resolution
            bad_mut = json.loads(json.dumps(ok_mut))
            bad_mut["shots"][0]["video"]["draft_params"]["multi_shots"] = True
            bad_mut["shots"][0]["video"]["final_params"]["multi_prompt"] = [{"prompt": "beat 1"}]
            bad_mut["shots"][1]["video"]["final_params"]["resolution"] = "1080p"
            bad_mut["shots"][1]["video"]["resolution"] = "480p"
            shotlist_path.write_text(json.dumps(bad_mut, indent=2), encoding="utf-8")

            code_b, data_b, comb_b = self._run(camp)
            self.assertEqual(code_b, 1, msg=f"Invalid kling4_0/flash params must fail:\n{comb_b}")
            errs_b = " ".join(data_b.get("errors", []))
            self.assertIn("multi_shots", errs_b, msg=data_b)
            self.assertIn("multi_prompt", errs_b, msg=data_b)
            self.assertIn("kling_4_0_flash", errs_b, msg=data_b)
            self.assertIn("720p", errs_b, msg=data_b)

    def test_enforces_cinematic_studio_video_4_0_live_cli_1_2_3_guards(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            camp = _copy_campaign_fixture(Path(tmp))
            shotlist_path = camp / "shotlist.json"
            base = json.loads(shotlist_path.read_text(encoding="utf-8"))

            # Clean pass: CS 4.0 with dict color_palette + light_custom only, and second shot with light_id="custom" only
            ok_mut = json.loads(json.dumps(base))
            for idx in (0, 1):
                ok_mut["shots"][idx]["video"]["model"] = "cinematic_studio_video_4_0"
                ok_mut["shots"][idx]["video"]["is_workflow"] = True
                ok_mut["shots"][idx]["video"]["mode"] = "omni_reference"
                ok_mut["shots"][idx]["video"]["draft_params"] = {"resolution": "720p", "duration": 5}
                ok_mut["shots"][idx]["video"]["final_params"] = {
                    "resolution": "1080p",
                    "bitrate_mode": "high",
                    "duration": 5,
                }
            ok_mut["shots"][0]["video"]["final_params"]["color_palette"] = {"primary": "#8B5A2B"}
            ok_mut["shots"][0]["video"]["final_params"]["light_custom"] = {"angle": 45}
            ok_mut["shots"][1]["video"]["final_params"]["color_palette"] = None
            ok_mut["shots"][1]["video"]["final_params"]["light_id"] = "custom"
            shotlist_path.write_text(json.dumps(ok_mut, indent=2), encoding="utf-8")

            code_ok, data_ok, comb_ok = self._run(camp)
            self.assertEqual(code_ok, 0, msg=f"Valid CS 4.0 config must pass:\n{comb_ok}")
            self.assertTrue(data_ok.get("ok"), msg=data_ok)

            # Fail 1: 4k resolution, draft/draft_job_id, string color_palette, non-"custom" light_id
            bad1 = json.loads(json.dumps(ok_mut))
            bad1["shots"][0]["video"]["final_params"]["resolution"] = "4k"
            bad1["shots"][0]["video"]["draft_params"]["draft"] = True
            bad1["shots"][0]["video"]["final_params"]["draft_job_id"] = "job-uuid-1"
            bad1["shots"][1]["video"]["draft_params"]["color_palette"] = "warm_nordic"
            bad1["shots"][1]["video"]["final_params"]["light_id"] = "preset_warm_01"
            shotlist_path.write_text(json.dumps(bad1, indent=2), encoding="utf-8")

            code_b1, data_b1, comb_b1 = self._run(camp)
            self.assertEqual(code_b1, 1, msg=f"Invalid CS 4.0 CLI 1.2.3 params must fail:\n{comb_b1}")
            errs_b1 = " ".join(data_b1.get("errors", []))
            self.assertIn("4k", errs_b1, msg=data_b1)
            self.assertIn("draft", errs_b1, msg=data_b1)
            self.assertIn("draft_job_id", errs_b1, msg=data_b1)
            self.assertIn("color_palette", errs_b1, msg=data_b1)
            self.assertIn("light_id", errs_b1, msg=data_b1)

            # Fail 2: simultaneous light_id + light_custom (both inline and inherited from video -> final_params)
            bad2 = json.loads(json.dumps(ok_mut))
            bad2["shots"][0]["video"]["final_params"]["light_id"] = "custom"
            bad2["shots"][1]["video"]["light_id"] = "custom"
            bad2["shots"][1]["video"]["final_params"].pop("light_id", None)
            bad2["shots"][1]["video"]["final_params"]["light_custom"] = {"angle": 30}
            shotlist_path.write_text(json.dumps(bad2, indent=2), encoding="utf-8")

            code_b2, data_b2, comb_b2 = self._run(camp)
            self.assertEqual(code_b2, 1, msg=f"Simultaneous light_id + light_custom must fail:\n{comb_b2}")
            errs_b2 = " ".join(data_b2.get("errors", []))
            self.assertIn("light_id", errs_b2, msg=data_b2)
            self.assertIn("light_custom", errs_b2, msg=data_b2)
            self.assertGreaterEqual(len(data_b2.get("errors", [])), 2, msg=data_b2)

    def test_enforces_draw_to_video_required_video_guard(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            camp = _copy_campaign_fixture(Path(tmp))
            shotlist_path = camp / "shotlist.json"
            base = json.loads(shotlist_path.read_text(encoding="utf-8"))
            base["references"].extend(
                [
                    {"id": "ref_sketch", "kind": "sketch", "local_path": "media/references/sketch.png", "upload_id": None},
                    {"id": "ref_src_vid", "kind": "video", "local_path": "media/references/src.mp4", "upload_id": None},
                    {"id": "ref_src_vid_2", "kind": "video", "local_path": "media/references/src2.mp4", "upload_id": None},
                ]
            )

            # Clean pass: shot 0 uses video_references=[1], shot 1 uses explicit video dict
            ok_mut = json.loads(json.dumps(base))
            for idx in (0, 1):
                ok_mut["shots"][idx]["video"]["model"] = "draw_to_video"
                ok_mut["shots"][idx]["video"]["is_workflow"] = True
                ok_mut["shots"][idx]["video"]["start_image_from"] = None
                ok_mut["shots"][idx]["video"]["end_image_from"] = None
                ok_mut["shots"][idx]["video"]["image_references"] = ["ref_sketch"]
            ok_mut["shots"][0]["video"]["video_references"] = ["ref_src_vid"]
            ok_mut["shots"][1]["video"]["video_references"] = []
            ok_mut["shots"][1]["video"]["video"] = {"id": "uploaded-video-uuid"}
            shotlist_path.write_text(json.dumps(ok_mut, indent=2), encoding="utf-8")

            code_ok, data_ok, comb_ok = self._run(camp)
            self.assertEqual(code_ok, 0, msg=f"Valid draw_to_video configs must pass:\n{comb_ok}")
            self.assertTrue(data_ok.get("ok"), msg=data_ok)

            # Fail: neither video nor video_references, and 2 video_references without video
            bad_mut = json.loads(json.dumps(ok_mut))
            bad_mut["shots"][0]["video"]["video_references"] = []
            bad_mut["shots"][1]["video"].pop("video", None)
            bad_mut["shots"][1]["video"]["video_references"] = ["ref_src_vid", "ref_src_vid_2"]
            shotlist_path.write_text(json.dumps(bad_mut, indent=2), encoding="utf-8")

            code_b, data_b, comb_b = self._run(camp)
            self.assertEqual(code_b, 1, msg=f"draw_to_video missing/extra video must fail:\n{comb_b}")
            errs_b = " ".join(data_b.get("errors", []))
            self.assertIn("draw_to_video", errs_b, msg=data_b)
            self.assertIn("video", errs_b, msg=data_b)
            self.assertGreaterEqual(len(data_b.get("errors", [])), 2, msg=data_b)

    def test_enforces_genjutsu_replace_object_flash_and_intone_duration_guards(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            camp = _copy_campaign_fixture(Path(tmp))
            shotlist_path = camp / "shotlist.json"
            base = json.loads(shotlist_path.read_text(encoding="utf-8"))
            base["references"].extend(
                [
                    {"id": "ref_driver_vid", "kind": "video", "local_path": "media/references/act.mp4", "upload_id": None},
                    {"id": "ref_voice_line", "kind": "audio", "local_path": "media/audio/line.wav", "upload_id": None},
                ]
            )

            # Clean pass: both _flash models at 1080p + intone at duration_s=8 (<= 8s boundary)
            ok_mut = json.loads(json.dumps(base))
            ok_mut["target_duration_s"] = 18
            ok_mut["shots"][0]["duration_s"] = 5
            ok_mut["shots"][0]["video"]["model"] = "hf_mult_replace_object_flash"
            ok_mut["shots"][0]["video"]["is_workflow"] = False
            ok_mut["shots"][0]["video"]["start_image_from"] = None
            ok_mut["shots"][0]["video"]["end_image_from"] = None
            ok_mut["shots"][0]["video"]["image_references"] = ["ref_bag_front"]
            ok_mut["shots"][0]["video"]["video_references"] = ["ref_driver_vid"]
            ok_mut["shots"][0]["video"]["draft_params"] = {"resolution": "1080p"}
            ok_mut["shots"][0]["video"]["final_params"] = {"resolution": "1080p"}

            ok_mut["shots"][1]["duration_s"] = 5
            ok_mut["shots"][1]["video"]["model"] = "hf_mult_motion_control_flash"
            ok_mut["shots"][1]["video"]["is_workflow"] = False
            ok_mut["shots"][1]["video"]["start_image_from"] = None
            ok_mut["shots"][1]["video"]["end_image_from"] = None
            ok_mut["shots"][1]["video"]["image_references"] = ["lb_traveler_hand"]
            ok_mut["shots"][1]["video"]["video_references"] = ["ref_driver_vid"]
            ok_mut["shots"][1]["video"]["draft_params"] = {"resolution": "1080p"}
            ok_mut["shots"][1]["video"]["final_params"] = {"resolution": "1080p"}

            ok_mut["shots"][2]["duration_s"] = 8
            ok_mut["shots"][2]["video"]["model"] = "intone"
            ok_mut["shots"][2]["video"]["is_workflow"] = False
            ok_mut["shots"][2]["video"]["start_image_from"] = None
            ok_mut["shots"][2]["video"]["end_image_from"] = None
            ok_mut["shots"][2]["video"]["image_references"] = []
            ok_mut["shots"][2]["video"]["character_images"] = ["lb_traveler_hand"]
            ok_mut["shots"][2]["video"]["audio_references"] = ["ref_voice_line"]
            ok_mut["shots"][2]["video"]["final_params"] = {"resolution": "1080p", "bitrate_mode": "high"}
            shotlist_path.write_text(json.dumps(ok_mut, indent=2), encoding="utf-8")

            code_ok, data_ok, comb_ok = self._run(camp)
            self.assertEqual(code_ok, 0, msg=f"Valid Genjutsu _flash + intone<=8s must pass:\n{comb_ok}")
            self.assertTrue(data_ok.get("ok"), msg=data_ok)
            warns_ok = " ".join(data_ok.get("warnings", []))
            self.assertNotIn("hf_mult_", warns_ok, msg=data_ok)
            self.assertNotIn("intone", warns_ok, msg=data_ok)

            # Warnings: full hf_mult_replace_object, full hf_mult_motion_control, intone duration_s > 8
            warn_mut = json.loads(json.dumps(ok_mut))
            warn_mut["target_duration_s"] = 19
            warn_mut["shots"][0]["video"]["model"] = "hf_mult_replace_object"
            warn_mut["shots"][1]["video"]["model"] = "hf_mult_motion_control"
            warn_mut["shots"][2]["duration_s"] = 9
            shotlist_path.write_text(json.dumps(warn_mut, indent=2), encoding="utf-8")

            code_w, data_w, comb_w = self._run(camp)
            self.assertEqual(code_w, 0, msg=f"Genjutsu/intone cost warnings must not fail:\n{comb_w}")
            warns_w = " ".join(data_w.get("warnings", []))
            self.assertIn("hf_mult_replace_object_flash", warns_w, msg=data_w)
            self.assertIn("hf_mult_motion_control_flash", warns_w, msg=data_w)
            self.assertIn("intone", warns_w, msg=data_w)
            self.assertIn("18 cr./s", warns_w, msg=data_w)

            # Hard errors: replace_object missing refs + start_image, _flash non-1080p resolutions
            bad_mut = json.loads(json.dumps(ok_mut))
            bad_mut["shots"][0]["video"]["model"] = "hf_mult_replace_object"
            bad_mut["shots"][0]["video"]["image_references"] = []
            bad_mut["shots"][0]["video"]["video_references"] = []
            bad_mut["shots"][0]["video"]["start_image_from"] = "s01.still"
            bad_mut["shots"][1]["video"]["draft_params"]["resolution"] = "720p"
            bad_mut["shots"][2]["video"]["model"] = "hf_mult_replace_object_flash"
            bad_mut["shots"][2]["video"]["image_references"] = ["ref_bag_front"]
            bad_mut["shots"][2]["video"]["video_references"] = ["ref_driver_vid"]
            bad_mut["shots"][2]["video"]["draft_params"] = {"resolution": "480p"}
            bad_mut["shots"][2]["video"]["final_params"] = {"resolution": "1080p"}
            shotlist_path.write_text(json.dumps(bad_mut, indent=2), encoding="utf-8")

            code_b, data_b, comb_b = self._run(camp)
            self.assertEqual(code_b, 1, msg=f"Invalid Genjutsu CEL / _flash res must fail:\n{comb_b}")
            errs_b = " ".join(data_b.get("errors", []))
            self.assertIn("hf_mult_replace_object", errs_b, msg=data_b)
            self.assertIn("start_image/end_image", errs_b, msg=data_b)
            self.assertIn("hf_mult_motion_control_flash", errs_b, msg=data_b)
            self.assertIn("hf_mult_replace_object_flash", errs_b, msg=data_b)
            self.assertIn("1080p-only", errs_b, msg=data_b)

    def test_enforces_minimax_h3_seedream_v5_pro_and_soul_cast_guards(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            camp = _copy_campaign_fixture(Path(tmp))
            shotlist_path = camp / "shotlist.json"
            base = json.loads(shotlist_path.read_text(encoding="utf-8"))

            # Clean pass: minimax_h3 with start_image only, minimax_h3 with refs only,
            # seedream_v5_pro at 2k, soul_cast explicitly 16:9 on a 9:16 campaign,
            # and cinematic_studio_soul_cast at 9:16
            ok_mut = json.loads(json.dumps(base))
            ok_mut["aspect_ratio"] = "9:16"
            ok_mut["shots"][0]["still"]["model"] = "seedream_v5_pro"
            ok_mut["shots"][0]["still"]["resolution"] = "2k"
            ok_mut["shots"][1]["still"]["model"] = "soul_cast"
            ok_mut["shots"][1]["still"]["aspect_ratio"] = "16:9"
            ok_mut["shots"][2]["still"]["model"] = "cinematic_studio_soul_cast"
            ok_mut["shots"][2]["still"]["aspect_ratio"] = "9:16"
            ok_mut["lookbook"][0]["model"] = "soul_cast"
            ok_mut["lookbook"][0]["params"] = {"aspect_ratio": "16:9"}

            ok_mut["shots"][0]["video"]["model"] = "minimax_h3"
            ok_mut["shots"][0]["video"]["is_workflow"] = False
            ok_mut["shots"][0]["video"]["start_image_from"] = "s01.still"
            ok_mut["shots"][0]["video"]["end_image_from"] = None
            ok_mut["shots"][0]["video"]["image_references"] = []

            ok_mut["shots"][1]["video"]["model"] = "minimax_h3"
            ok_mut["shots"][1]["video"]["is_workflow"] = False
            ok_mut["shots"][1]["video"]["start_image_from"] = None
            ok_mut["shots"][1]["video"]["end_image_from"] = None
            ok_mut["shots"][1]["video"]["image_references"] = ["ref_bag_front"]
            shotlist_path.write_text(json.dumps(ok_mut, indent=2), encoding="utf-8")

            code_ok, data_ok, comb_ok = self._run(camp)
            self.assertEqual(code_ok, 0, msg=f"Valid minimax/seedream/soul_cast must pass:\n{comb_ok}")
            self.assertTrue(data_ok.get("ok"), msg=data_ok)

            # Warning on minimax_h3_max
            warn_mut = json.loads(json.dumps(ok_mut))
            warn_mut["shots"][0]["video"]["model"] = "minimax_h3_max"
            shotlist_path.write_text(json.dumps(warn_mut, indent=2), encoding="utf-8")

            code_w, data_w, comb_w = self._run(camp)
            self.assertEqual(code_w, 0, msg=f"minimax_h3_max warning must not fail:\n{comb_w}")
            warns_w = " ".join(data_w.get("warnings", []))
            self.assertIn("minimax_h3_max", warns_w, msg=data_w)
            self.assertIn("minimax_h3", warns_w, msg=data_w)

            # Hard errors: minimax_h3 XOR, seedream_v5_pro 4k (direct + params),
            # soul_cast explicit non-16:9, and soul_cast inheriting campaign 9:16
            bad_mut = json.loads(json.dumps(ok_mut))
            bad_mut["shots"][0]["video"]["image_references"] = ["ref_bag_front"]  # + start_image XOR!
            bad_mut["shots"][0]["still"]["resolution"] = "4k"
            bad_mut["shots"][1]["still"]["aspect_ratio"] = "9:16"
            bad_mut["shots"][2]["still"]["model"] = "soul_cast"
            bad_mut["shots"][2]["still"].pop("aspect_ratio", None)  # inherits campaign 9:16!
            bad_mut["lookbook"][0]["model"] = "seedream_v5_pro"
            bad_mut["lookbook"][0]["params"] = {"resolution": "4k"}
            shotlist_path.write_text(json.dumps(bad_mut, indent=2), encoding="utf-8")

            code_b, data_b, comb_b = self._run(camp)
            self.assertEqual(code_b, 1, msg=f"Invalid minimax/seedream/soul_cast must fail:\n{comb_b}")
            errs_b = " ".join(data_b.get("errors", []))
            self.assertIn("minimax_h3", errs_b, msg=data_b)
            self.assertIn("seedream_v5_pro", errs_b, msg=data_b)
            self.assertIn("soul_cast", errs_b, msg=data_b)
            self.assertIn("16:9", errs_b, msg=data_b)
            self.assertGreaterEqual(len(data_b.get("errors", [])), 5, msg=data_b)

    def test_enforces_marketing_studio_workflow_guards(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            camp = _copy_campaign_fixture(Path(tmp))
            shotlist_path = camp / "shotlist.json"
            base = json.loads(shotlist_path.read_text(encoding="utf-8"))

            # Clean pass: v2 2d_motion with 1 input_images, v2 saas_motion 1080p (0 images),
            # marketing_studio_video with explicit duration=5
            ok_mut = json.loads(json.dumps(base))
            ok_mut["shots"][0]["video"]["model"] = "marketing_studio_v2_video"
            ok_mut["shots"][0]["video"]["is_workflow"] = True
            ok_mut["shots"][0]["video"]["type"] = "2d_motion"
            ok_mut["shots"][0]["video"]["input_images"] = ["ref_bag_front"]
            ok_mut["shots"][0]["video"]["image_references"] = []
            ok_mut["shots"][0]["video"]["draft_params"] = {"resolution": "720p"}
            ok_mut["shots"][0]["video"]["final_params"] = {"resolution": "1080p"}

            ok_mut["shots"][1]["video"]["model"] = "marketing_studio_v2_video"
            ok_mut["shots"][1]["video"]["is_workflow"] = True
            ok_mut["shots"][1]["video"]["type"] = "saas_motion"
            ok_mut["shots"][1]["video"]["image_references"] = []
            ok_mut["shots"][1]["video"]["draft_params"] = {"resolution": "1080p"}
            ok_mut["shots"][1]["video"]["final_params"] = {"resolution": "1080p"}

            ok_mut["shots"][2]["video"]["model"] = "marketing_studio_video"
            ok_mut["shots"][2]["video"]["is_workflow"] = True
            ok_mut["shots"][2]["video"]["draft_params"] = {"duration": 5}
            ok_mut["shots"][2]["video"]["final_params"] = {"duration": 5}
            shotlist_path.write_text(json.dumps(ok_mut, indent=2), encoding="utf-8")

            code_ok, data_ok, comb_ok = self._run(camp)
            self.assertEqual(code_ok, 0, msg=f"Valid marketing_studio workflows must pass:\n{comb_ok}")
            self.assertTrue(data_ok.get("ok"), msg=data_ok)
            warns_ok = " ".join(data_ok.get("warnings", []))
            self.assertNotIn("marketing_studio", warns_ok, msg=data_ok)

            # Clean pass: hypermotion using 1 image_references entry + marketing_studio_video omitting duration when duration_s == 15
            ok_15 = json.loads(json.dumps(ok_mut))
            ok_15["target_duration_s"] = 25
            ok_15["shots"][0]["video"]["type"] = "hypermotion"
            ok_15["shots"][0]["video"].pop("input_images", None)
            ok_15["shots"][0]["video"]["image_references"] = ["ref_bag_front"]
            ok_15["shots"][2]["duration_s"] = 15
            ok_15["shots"][2]["video"]["draft_params"] = {"resolution": "720p"}
            ok_15["shots"][2]["video"]["final_params"] = {"resolution": "1080p"}
            shotlist_path.write_text(json.dumps(ok_15, indent=2), encoding="utf-8")

            code_15, data_15, comb_15 = self._run(camp)
            self.assertEqual(code_15, 0, msg=f"15s marketing_studio_video + 1 image_references must pass:\n{comb_15}")
            self.assertNotIn("defaults duration", " ".join(data_15.get("warnings", [])), msg=data_15)

            # Warnings: saas_motion at 720p, and marketing_studio_video omitting duration on 5s shot
            warn_mut = json.loads(json.dumps(ok_mut))
            warn_mut["shots"][1]["video"]["draft_params"] = {"resolution": "720p"}
            warn_mut["shots"][2]["video"]["draft_params"] = {"resolution": "720p"}
            warn_mut["shots"][2]["video"]["final_params"] = {"resolution": "1080p"}
            shotlist_path.write_text(json.dumps(warn_mut, indent=2), encoding="utf-8")

            code_w, data_w, comb_w = self._run(camp)
            self.assertEqual(code_w, 0, msg=f"marketing_studio warnings must not fail:\n{comb_w}")
            warns_w = " ".join(data_w.get("warnings", []))
            self.assertIn("saas_motion", warns_w, msg=data_w)
            self.assertIn("31.1 cr.", warns_w, msg=data_w)
            self.assertIn("marketing_studio_video", warns_w, msg=data_w)
            self.assertIn("15s", warns_w, msg=data_w)

            # Hard errors: missing is_workflow, hypermotion with 0 imgs, mixed_media with 2 imgs
            bad_mut = json.loads(json.dumps(ok_mut))
            bad_mut["shots"][0]["video"]["is_workflow"] = False
            bad_mut["shots"][0]["video"]["type"] = "hypermotion"
            bad_mut["shots"][0]["video"]["input_images"] = []
            bad_mut["shots"][1]["video"]["type"] = None
            bad_mut["shots"][1]["video"]["final_params"]["type"] = "mixed_media"
            bad_mut["shots"][1]["video"]["image_references"] = ["ref_bag_front", "lb_traveler_hand"]
            bad_mut["shots"][2]["video"]["is_workflow"] = False
            shotlist_path.write_text(json.dumps(bad_mut, indent=2), encoding="utf-8")

            code_b, data_b, comb_b = self._run(camp)
            self.assertEqual(code_b, 1, msg=f"Invalid marketing_studio configs must fail:\n{comb_b}")
            errs_b = " ".join(data_b.get("errors", []))
            self.assertIn("is_workflow", errs_b, msg=data_b)
            self.assertIn("hypermotion", errs_b, msg=data_b)
            self.assertIn("mixed_media", errs_b, msg=data_b)
            self.assertIn("marketing_studio_video", errs_b, msg=data_b)

    def test_eng08_anti_caustic_living_still_prompt_lint(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            camp = _copy_campaign_fixture(Path(tmp))
            shotlist_path = camp / "shotlist.json"
            base = json.loads(shotlist_path.read_text(encoding="utf-8"))

            (camp / "prompts" / "drift_a.txt").write_text(
                "Locked-off tripod. Subtle breathing daylight and luminous caustic shimmer across stone.\n",
                encoding="utf-8",
            )
            (camp / "prompts" / "drift_b.txt").write_text(
                "Static camera. Gliding caustics and drifting light cast gentle moving shadows and gliding light.\n",
                encoding="utf-8",
            )
            (camp / "prompts" / "negated_clean.txt").write_text(
                "Locked-off tripod. Fixed stationary daylight. Zero breathing daylight, no drifting light, "
                "without caustic shimmer, forbid gliding caustics, zero moving shadows, forbids gliding light.\n",
                encoding="utf-8",
            )
            (camp / "prompts" / "mixed_neg_pos.txt").write_text(
                "Zero moving shadows on stone left, but subtle moving shadow slides across right wall.\n",
                encoding="utf-8",
            )

            # Case 1: Warns on seedance_2_5 and cinematic_studio_video_4_0 when start == end and non-negated drift phrase appears
            warn_mut = json.loads(json.dumps(base))
            warn_mut["shots"][0]["video"]["model"] = "seedance_2_5"
            warn_mut["shots"][0]["video"]["is_workflow"] = False
            warn_mut["shots"][0]["video"]["mode"] = "omni_reference"
            warn_mut["shots"][0]["video"]["start_image_from"] = "s01.still"
            warn_mut["shots"][0]["video"]["end_image_from"] = "s01.still"
            warn_mut["shots"][0]["video"]["prompt_file"] = "prompts/drift_a.txt"
            warn_mut["shots"][0]["video"]["draft_params"] = {"draft": True, "duration": 5}
            warn_mut["shots"][0]["video"]["final_params"] = {"resolution": "1080p", "bitrate_mode": "high", "duration": 5}

            warn_mut["shots"][1]["video"]["model"] = "cinematic_studio_video_4_0"
            warn_mut["shots"][1]["video"]["is_workflow"] = True
            warn_mut["shots"][1]["video"]["mode"] = "omni_reference"
            warn_mut["shots"][1]["video"]["start_image_from"] = "s02.still"
            warn_mut["shots"][1]["video"]["end_image_from"] = "s02.still"
            warn_mut["shots"][1]["video"]["prompt_file"] = "prompts/drift_b.txt"
            warn_mut["shots"][1]["video"]["draft_params"] = {"resolution": "720p", "duration": 5}
            warn_mut["shots"][1]["video"]["final_params"] = {"resolution": "1080p", "bitrate_mode": "high", "duration": 5}

            warn_mut["shots"][2]["video"]["model"] = "seedance_2_5"
            warn_mut["shots"][2]["video"]["is_workflow"] = False
            warn_mut["shots"][2]["video"]["mode"] = "omni_reference"
            warn_mut["shots"][2]["video"]["start_image_from"] = "s03.still"
            warn_mut["shots"][2]["video"]["end_image_from"] = "s03.still"
            warn_mut["shots"][2]["video"]["prompt_file"] = "prompts/mixed_neg_pos.txt"
            warn_mut["shots"][2]["video"]["draft_params"] = {"draft": True, "duration": 5}
            warn_mut["shots"][2]["video"]["final_params"] = {"resolution": "1080p", "bitrate_mode": "high", "duration": 5}
            shotlist_path.write_text(json.dumps(warn_mut, indent=2), encoding="utf-8")

            code_w, data_w, comb_w = self._run(camp)
            self.assertEqual(code_w, 0, msg=f"ENG-08 warnings must not fail:\n{comb_w}")
            eng08_warns = [w for w in data_w.get("warnings", []) if "ENG-08" in w]
            self.assertEqual(len(eng08_warns), 3, msg=f"Expected 3 ENG-08 warnings, got: {data_w.get('warnings')}")
            joined = " ".join(eng08_warns)
            self.assertIn("breathing daylight", joined)
            self.assertIn("caustic shimmer", joined)
            self.assertIn("gliding caustic", joined)
            self.assertIn("drifting light", joined)
            self.assertIn("moving shadow", joined)
            self.assertIn("gliding light", joined)

            # Case 2: Clean pass when all phrases are properly negated
            neg_mut = json.loads(json.dumps(warn_mut))
            for idx in (0, 1, 2):
                neg_mut["shots"][idx]["video"]["prompt_file"] = "prompts/negated_clean.txt"
            shotlist_path.write_text(json.dumps(neg_mut, indent=2), encoding="utf-8")

            code_n, data_n, comb_n = self._run(camp)
            self.assertEqual(code_n, 0, msg=f"Negated ENG-08 prompt must pass cleanly:\n{comb_n}")
            self.assertEqual(
                [w for w in data_n.get("warnings", []) if "ENG-08" in w],
                [],
                msg=f"Negated phrases must not trigger ENG-08 warning: {data_n.get('warnings')}",
            )

            # Case 3: No ENG-08 warning when start != end, end is null, or model is kling4_0
            skip_mut = json.loads(json.dumps(warn_mut))
            skip_mut["shots"][0]["video"]["end_image_from"] = "s02.still"  # start != end
            skip_mut["shots"][1]["video"]["end_image_from"] = None  # no end_image
            skip_mut["shots"][2]["video"]["model"] = "kling4_0"
            skip_mut["shots"][2]["video"]["prompt_file"] = "prompts/drift_a.txt"
            skip_mut["shots"][2]["video"]["draft_params"] = {"resolution": "720p", "duration": 5}
            shotlist_path.write_text(json.dumps(skip_mut, indent=2), encoding="utf-8")

            code_s, data_s, comb_s = self._run(camp)
            self.assertEqual(code_s, 0, msg=f"Non-living-still / other-model must pass:\n{comb_s}")
            self.assertEqual(
                [w for w in data_s.get("warnings", []) if "ENG-08" in w],
                [],
                msg=f"Unexpected ENG-08 warning: {data_s.get('warnings')}",
            )

    def test_supports_first_class_still_only_shots_and_preserves_video_requirement(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            camp = _copy_campaign_fixture(Path(tmp))
            shotlist_path = camp / "shotlist.json"
            base = json.loads(shotlist_path.read_text(encoding="utf-8"))

            # Clean pass: s01 still_only=true with video=null (0.4s), s02 still_only=true with video omitted (0.6s),
            # s03 normal video shot (5s) referencing s01.still
            ok_mut = json.loads(json.dumps(base))
            ok_mut["target_duration_s"] = 6
            ok_mut["lookbook"][0]["estimated_credits"] = 10
            ok_mut["audio"]["music"]["estimated_credits"] = 5

            ok_mut["shots"][0]["duration_s"] = 0.4
            ok_mut["shots"][0]["still_only"] = True
            ok_mut["shots"][0]["still"]["estimated_credits"] = 2
            ok_mut["shots"][0]["video"] = None

            ok_mut["shots"][1]["duration_s"] = 0.6
            ok_mut["shots"][1]["still_only"] = True
            ok_mut["shots"][1]["still"]["estimated_credits"] = 2
            ok_mut["shots"][1].pop("video", None)

            ok_mut["shots"][2]["duration_s"] = 5
            ok_mut["shots"][2]["still"]["estimated_credits"] = 2
            ok_mut["shots"][2]["video"]["model"] = "seedance_2_5"
            ok_mut["shots"][2]["video"]["is_workflow"] = False
            ok_mut["shots"][2]["video"]["mode"] = "omni_reference"
            ok_mut["shots"][2]["video"]["start_image_from"] = "s01.still"
            ok_mut["shots"][2]["video"]["end_image_from"] = None
            ok_mut["shots"][2]["video"]["estimated_draft_credits"] = 15
            ok_mut["shots"][2]["video"]["estimated_final_credits"] = 80
            ok_mut["shots"][2]["video"]["draft_params"] = {"draft": True, "duration": 5}
            ok_mut["shots"][2]["video"]["final_params"] = {"resolution": "1080p", "bitrate_mode": "high", "duration": 5}
            shotlist_path.write_text(json.dumps(ok_mut, indent=2), encoding="utf-8")

            code_ok, data_ok, comb_ok = self._run(camp)
            self.assertEqual(code_ok, 0, msg=f"Valid still_only shots must pass:\n{comb_ok}")
            self.assertTrue(data_ok.get("ok"), msg=data_ok)
            self.assertEqual(data_ok["budget"]["r4_draft_video"], 15, msg=data_ok)
            self.assertEqual(data_ok["budget"]["r5_final_video"], 80, msg=data_ok)
            self.assertEqual(data_ok["budget"]["r3_stills_audio"], 11, msg=data_ok)  # 2+2+2 stills + 5 music
            self.assertEqual(data_ok["budget"]["planned_total"], 116, msg=data_ok)  # 10+11+15+80

            # Fail 1: still_only=true with still=null must fail
            no_still = json.loads(json.dumps(ok_mut))
            no_still["shots"][0]["still"] = None
            no_still["shots"][2]["video"]["start_image_from"] = "s03.still"
            shotlist_path.write_text(json.dumps(no_still, indent=2), encoding="utf-8")

            code_ns, data_ns, comb_ns = self._run(camp)
            self.assertEqual(code_ns, 1, msg=f"still_only=true with null still must fail:\n{comb_ns}")
            self.assertIn("still_only", " ".join(data_ns.get("errors", [])), msg=data_ns)

            # Fail 2: still_only=false or omitted still requires non-null video dict with exact error
            no_vid = json.loads(json.dumps(ok_mut))
            no_vid["shots"][0]["still_only"] = False
            no_vid["shots"][1].pop("still_only", None)
            shotlist_path.write_text(json.dumps(no_vid, indent=2), encoding="utf-8")

            code_nv, data_nv, comb_nv = self._run(camp)
            self.assertEqual(code_nv, 1, msg=f"Missing video without still_only=true must fail:\n{comb_nv}")
            errs_nv = data_nv.get("errors", [])
            self.assertEqual(
                sum(1 for e in errs_nv if "missing or non-object 'video'" in e),
                2,
                msg=f"Expected exact missing/non-object video error on both shots, got: {errs_nv}",
            )

            # Fail 3: non-boolean still_only and .last_frame reference to still_only shot must fail
            bad_ref = json.loads(json.dumps(ok_mut))
            bad_ref["shots"][0]["still_only"] = "true"
            bad_ref["shots"][2]["video"]["start_image_from"] = "s02.last_frame"
            shotlist_path.write_text(json.dumps(bad_ref, indent=2), encoding="utf-8")

            code_br, data_br, comb_br = self._run(camp)
            self.assertEqual(code_br, 1, msg=f"Non-bool still_only and .last_frame to still_only must fail:\n{comb_br}")
            errs_br = " ".join(data_br.get("errors", []))
            self.assertIn("still_only", errs_br, msg=data_br)
            self.assertIn("no 'video' defined", errs_br, msg=data_br)


if __name__ == "__main__":
    unittest.main()

"""Unit and integration tests for 5-layer memory, Supersedes compiler, raw traces, retro harvest, and FTS5 search."""

from __future__ import annotations

import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = REPO_ROOT / "scripts"
EXAMPLE_CAMPAIGN = REPO_ROOT / "campaigns" / "example-product-spot"


def _make_fake_hf_bin(path: Path, *, cost: float = 10.0) -> Path:
    script = f"""#!/usr/bin/env python3
import json, sys
args = sys.argv[1:]
if "cost" in args:
    print(json.dumps({{"credits": {cost}}}))
    sys.exit(0)
print(json.dumps({{"status": "completed", "credits": {cost}}}))
"""
    path.write_text(script, encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IEXEC)
    return path


class TestMemoryAndRetro(unittest.TestCase):
    def _run_py(self, script_name: str, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(SCRIPTS_DIR / script_name), *args],
            capture_output=True,
            text=True,
            check=False,
        )

    def test_memory_compile_supersedes_full_category_and_scoped(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_str:
            camp = Path(tmp_str)
            taste_log = camp / "taste-log.md"
            taste_log.write_text(
                "# Taste Log: Test Spot\n\n"
                "Brand taste seed: brands/example-brand/taste.md\n\n"
                "### TL-01 (R2 — Dark Night)\n"
                "- **Approved / LOCKED:** Dark 00:40 midnight shadows.\n"
                "- **Never:** Bright daylight.\n\n"
                "### TL-02 (R3 — Upscale Rule)\n"
                "- **Approved / LOCKED:** Beat-locked 24fps edit.\n"
                "- **More of:** Upscaling 480p drafts via pixel upscaler.\n\n"
                "### TL-03 (R3 — Counter & Climax)\n"
                "- **Approved / LOCKED:** SKU counter 94 000 + tabletop gift climax.\n\n"
                "### TL-04 (R4 — Revisions)\n"
                "- **Supersedes:** TL-01, TL-02[More of], TL-03 (SKU counter)\n"
                "- **Approved / LOCKED:** Clean diffused morning daylight + native 1080p.\n"
                "- **Never:** Dark shadows or numeric counters.\n",
                encoding="utf-8",
            )

            proc = self._run_py("memory_compile.py", str(camp), "--json")
            self.assertEqual(proc.returncode, 0, msg=proc.stdout + proc.stderr)
            data = json.loads(proc.stdout)
            self.assertTrue(data["ok"])
            self.assertEqual(data["entry_count"], 4)
            self.assertEqual(data["active_entry_count"], 3)
            self.assertEqual(data["superseded_entry_count"], 1)

            active_text = (camp / "taste-active.md").read_text(encoding="utf-8")
            self.assertNotIn("Dark 00:40 midnight shadows", active_text)
            self.assertIn("Beat-locked 24fps edit", active_text)
            self.assertNotIn("Upscaling 480p drafts", active_text)
            self.assertIn("partially superseded by TL-04: SKU counter", active_text)
            self.assertIn("`TL-01` -> superseded by `TL-04`", active_text)
            self.assertIn("`TL-02[More of]` -> superseded by `TL-04`", active_text)

            # Fresh check passes
            chk_ok = self._run_py("memory_compile.py", str(camp), "--check", "--json")
            self.assertEqual(chk_ok.returncode, 0, msg=chk_ok.stdout + chk_ok.stderr)

            # Mutating taste-log.md without recompiling fails --check
            taste_log.write_text(
                taste_log.read_text(encoding="utf-8")
                + "\n### TL-05 (R5 — Final)\n- **Approved / LOCKED:** Master locked.\n",
                encoding="utf-8",
            )
            chk_stale = self._run_py("memory_compile.py", str(camp), "--check", "--json")
            self.assertEqual(chk_stale.returncode, 1, msg=chk_stale.stdout + chk_stale.stderr)
            self.assertIn("stale", chk_stale.stdout.lower())

    def test_memory_compile_rejects_unknown_self_and_forward_supersedes(self) -> None:
        bad_cases = [
            (
                "unknown",
                "### TL-01 (R2)\n- **Supersedes:** TL-99\n- **More of:** Crisp light.\n",
                "unknown entry 'TL-99'",
            ),
            (
                "self",
                "### TL-01 (R2)\n- **Supersedes:** TL-01\n- **More of:** Crisp light.\n",
                "cannot supersede itself",
            ),
            (
                "forward",
                "### TL-01 (R2)\n- **Supersedes:** TL-02\n- **More of:** Crisp light.\n\n"
                "### TL-02 (R3)\n- **More of:** Warm light.\n",
                "later entry 'TL-02'",
            ),
            (
                "bad_cat",
                "### TL-01 (R2)\n- **More of:** Crisp light.\n\n"
                "### TL-02 (R3)\n- **Supersedes:** TL-01[Bogus]\n- **More of:** Warm light.\n",
                "unknown category 'Bogus'",
            ),
        ]
        for label, body, expected_msg in bad_cases:
            with self.subTest(case=label), tempfile.TemporaryDirectory() as tmp_str:
                camp = Path(tmp_str)
                (camp / "taste-log.md").write_text(
                    "# Taste Log: Invalid Supersedes\n\n" + body,
                    encoding="utf-8",
                )
                proc = self._run_py("memory_compile.py", str(camp), "--json")
                self.assertEqual(proc.returncode, 1, msg=f"{label}: {proc.stdout}")
                self.assertIn(expected_msg, proc.stdout)

    def test_check_campaign_enforces_supersedes_and_taste_active_freshness(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_str:
            root = Path(tmp_str)
            (root / "AGENTS.md").write_text("# AGENTS.md\n", encoding="utf-8")
            shutil.copytree(REPO_ROOT / "brands" / "example-brand", root / "brands" / "example-brand")
            camp = root / "campaigns" / "camp"
            shutil.copytree(EXAMPLE_CAMPAIGN, camp)

            ok_proc = self._run_py("check-campaign.py", str(camp), "--json")
            self.assertEqual(ok_proc.returncode, 0, msg=ok_proc.stdout + ok_proc.stderr)
            self.assertTrue(json.loads(ok_proc.stdout)["taste_active_fresh"])

            # Append TL-03 without recompiling taste-active.md -> check-campaign must fail
            taste_log = camp / "taste-log.md"
            taste_log.write_text(
                taste_log.read_text(encoding="utf-8")
                + "\n### TL-03 (R4 — Update)\n- **Supersedes:** TL-01\n- **More of:** Sharp daylight.\n",
                encoding="utf-8",
            )
            stale_proc = self._run_py("check-campaign.py", str(camp), "--json")
            self.assertEqual(stale_proc.returncode, 1, msg=stale_proc.stdout + stale_proc.stderr)
            self.assertIn("stale snapshot", stale_proc.stdout)

            # Recompile -> passes cleanly
            comp = self._run_py("memory_compile.py", str(camp))
            self.assertEqual(comp.returncode, 0, msg=comp.stdout + comp.stderr)
            ok2 = self._run_py("check-campaign.py", str(camp), "--json")
            self.assertEqual(ok2.returncode, 0, msg=ok2.stdout + ok2.stderr)

    def test_check_memory_enforces_caps_staleness_ace_sim_and_review_logs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_str:
            root = Path(tmp_str)
            shutil.copytree(REPO_ROOT / "studio", root / "studio")
            shutil.copytree(REPO_ROOT / "brands" / "example-brand", root / "brands" / "example-brand")
            shutil.copytree(EXAMPLE_CAMPAIGN, root / "campaigns" / "example-product-spot")

            # Clean on reference date -> 0 errors, 0 warnings
            ok_proc = self._run_py("check-memory.py", str(root), "--as-of", "2026-11-21", "--json")
            self.assertEqual(ok_proc.returncode, 0, msg=ok_proc.stdout + ok_proc.stderr)
            ok_data = json.loads(ok_proc.stdout)
            self.assertTrue(ok_data["ok"])
            self.assertEqual(ok_data["warnings"], [])

            # 100 days later -> active engine rules trigger staleness warning, graduated_to_code does not
            stale_proc = self._run_py("check-memory.py", str(root), "--as-of", "2027-03-01", "--json")
            self.assertEqual(stale_proc.returncode, 0, msg=stale_proc.stdout + stale_proc.stderr)
            stale_data = json.loads(stale_proc.stdout)
            self.assertNotIn("ENG-01", stale_data["checked"]["stale_engine_ids"])
            self.assertIn("ENG-02", stale_data["checked"]["stale_engine_ids"])

            # Over-cap studio/director.md (> 60 lines) fails
            dir_path = root / "studio" / "director.md"
            orig_dir = dir_path.read_text(encoding="utf-8")
            dir_path.write_text(orig_dir + "\n" * 50 + "- Extra line\n", encoding="utf-8")
            cap_proc = self._run_py("check-memory.py", str(root), "--json")
            self.assertEqual(cap_proc.returncode, 1, msg=cap_proc.stdout)
            self.assertIn("must be <= 60 lines", cap_proc.stdout)
            dir_path.write_text(orig_dir, encoding="utf-8")

            # Corrupt qc/review-log.jsonl fails
            bad_rev = root / "campaigns" / "example-product-spot" / "qc" / "review-log.jsonl"
            bad_rev.parent.mkdir(parents=True, exist_ok=True)
            bad_rev.write_text("{broken-json\n", encoding="utf-8")
            rev_proc = self._run_py("check-memory.py", str(root), "--json")
            self.assertEqual(rev_proc.returncode, 1, msg=rev_proc.stdout)
            self.assertIn("malformed JSONL", rev_proc.stdout)

    def test_hf_guard_log_web_zero_credits_and_independent_from_paid_retries(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            camp = tmp / "camp"
            shutil.copytree(EXAMPLE_CAMPAIGN, camp)
            fake_hf = _make_fake_hf_bin(tmp / "fake_hf", cost=10.0)

            # Log 4 Web Unlimited attempts for unlocked s02.still (version 2 in example-product-spot)
            for idx in range(4):
                status = "failed" if idx == 0 else "completed"
                proc = self._run_py(
                    "hf_guard.py",
                    "log-web",
                    "--campaign",
                    str(camp),
                    "--shot",
                    "s02",
                    "--kind",
                    "still",
                    "--round",
                    "R3",
                    "--model",
                    "seedream_5_5",
                    "--status",
                    status,
                    "--prompt-file",
                    "prompts/s02_still_v1.txt",
                    "--ref",
                    "lb_traveler_hand",
                    "--note",
                    f"web take {idx}",
                )
                self.assertEqual(proc.returncode, 0, msg=proc.stdout + proc.stderr)
                out = json.loads(proc.stdout)
                self.assertTrue(out["ok"])
                self.assertEqual(out["credits"], 0)
                self.assertEqual(out["attempt"], idx)

            # Refuses LOCKED asset s01.still
            locked_proc = self._run_py(
                "hf_guard.py",
                "log-web",
                "--campaign",
                str(camp),
                "--shot",
                "s01",
                "--kind",
                "still",
                "--round",
                "R3",
                "--model",
                "seedream_5_5",
            )
            self.assertEqual(locked_proc.returncode, 2, msg=locked_proc.stdout)
            self.assertEqual(json.loads(locked_proc.stdout)["error_code"], "asset_locked")

            # Paid preflight on s02.still still succeeds (Web runs didn't burn max_retries=2 or credits)
            pf_proc = self._run_py(
                "hf_guard.py",
                "--higgsfield-bin",
                str(fake_hf),
                "preflight",
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
                "seedream_5_5",
            )
            self.assertEqual(pf_proc.returncode, 0, msg=pf_proc.stdout + pf_proc.stderr)
            pf = json.loads(pf_proc.stdout)
            self.assertTrue(pf["ok"])
            self.assertEqual(pf["attempts_used"], 0)
            self.assertEqual(pf["total_spent"], 0)

            # status reports web_unlimited_runs accurately
            st_proc = self._run_py("hf_guard.py", "status", "--campaign", str(camp), "--json")
            self.assertEqual(st_proc.returncode, 0, msg=st_proc.stdout + st_proc.stderr)
            st = json.loads(st_proc.stdout)
            self.assertEqual(st["total_spent"], 0)
            self.assertEqual(st["web_unlimited_runs"], 4)
            self.assertEqual(st["rounds"]["R3"]["web_unlimited_runs"], 4)

    def test_qa_media_log_review_appends_and_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_str:
            camp = Path(tmp_str)
            # PASS defaults defect_class to NONE
            p1 = self._run_py(
                "qa_media.py",
                "log-review",
                "--campaign",
                str(camp),
                "--round",
                "R3",
                "--asset",
                "s01.still",
                "--verdict",
                "PASS",
                "--summary",
                "Clean 2k lock",
                "--json",
            )
            self.assertEqual(p1.returncode, 0, msg=p1.stdout + p1.stderr)
            r1 = json.loads(p1.stdout)
            self.assertEqual(r1["record"]["defect_class"], "NONE")

            # FAIL without defect-class is rejected (exit 2)
            bad = self._run_py(
                "qa_media.py",
                "log-review",
                "--campaign",
                str(camp),
                "--round",
                "R4",
                "--asset",
                "s02.video",
                "--verdict",
                "FAIL",
                "--json",
            )
            self.assertEqual(bad.returncode, 2, msg=bad.stdout + bad.stderr)

            # FAIL with CONTINUITY_DEFECT succeeds
            p2 = self._run_py(
                "qa_media.py",
                "log-review",
                "--campaign",
                str(camp),
                "--round",
                "R4",
                "--asset",
                "s02.video",
                "--verdict",
                "FAIL",
                "--defect-class",
                "CONTINUITY_DEFECT",
                "--reopen-owner",
                "Worker(s02.video)",
                "--summary",
                "180-degree axis flip",
                "--json",
            )
            self.assertEqual(p2.returncode, 0, msg=p2.stdout + p2.stderr)

            # CONCERNS with NARRATIVE_DEFECT succeeds and validates under check-memory.py
            p_nar = self._run_py(
                "qa_media.py",
                "log-review",
                "--campaign",
                str(camp),
                "--round",
                "R3",
                "--asset",
                "animatic.mp4",
                "--verdict",
                "FAIL",
                "--defect-class",
                "NARRATIVE_DEFECT",
                "--reopen-owner",
                "Root Producer",
                "--summary",
                "Blind viewer read triggered Primary Misread Risk",
                "--json",
            )
            self.assertEqual(p_nar.returncode, 0, msg=p_nar.stdout + p_nar.stderr)
            self.assertEqual(json.loads(p_nar.stdout)["record"]["defect_class"], "NARRATIVE_DEFECT")

            lines = (camp / "qc" / "review-log.jsonl").read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(lines), 3)

            # R4 PASS without --qa-report is mechanically rejected (fail closed)
            r4_no_proof = self._run_py(
                "qa_media.py",
                "log-review",
                "--campaign",
                str(camp),
                "--round",
                "R4B",
                "--asset",
                "s02.video",
                "--verdict",
                "PASS",
                "--json",
            )
            self.assertEqual(r4_no_proof.returncode, 2, msg=r4_no_proof.stdout)
            self.assertIn("REVIEW_HANDOFF_INVALID", r4_no_proof.stdout)

            # R5 PASS with --qa-report but missing --sheet or --crops is rejected; with all + --reviewer-id succeeds
            qa_json = camp / "qc" / "s02_qa.json"
            qa_json.write_text('{"ok": true}\n', encoding="utf-8")
            sheet_png = camp / "qc" / "s02_sheet.png"
            sheet_png.write_bytes(b"\x89PNG\r\n\x1a\n")
            crops_png = camp / "qc" / "s02_crops.png"
            crops_png.write_bytes(b"\x89PNG\r\n\x1a\n")
            r4_no_sheet = self._run_py(
                "qa_media.py",
                "log-review",
                "--campaign",
                str(camp),
                "--round",
                "R4B",
                "--asset",
                "s02.video",
                "--verdict",
                "PASS",
                "--qa-report",
                str(qa_json),
                "--json",
            )
            self.assertEqual(r4_no_sheet.returncode, 2, msg=r4_no_sheet.stdout)
            self.assertIn("--sheet", r4_no_sheet.stdout)
            r5_no_crops = self._run_py(
                "qa_media.py",
                "log-review",
                "--campaign",
                str(camp),
                "--round",
                "R5",
                "--asset",
                "s02.video",
                "--verdict",
                "PASS",
                "--qa-report",
                str(qa_json),
                "--sheet",
                str(sheet_png),
                "--json",
            )
            self.assertEqual(r5_no_crops.returncode, 2, msg=r5_no_crops.stdout)
            r5_ok = self._run_py(
                "qa_media.py",
                "log-review",
                "--campaign",
                str(camp),
                "--round",
                "R5",
                "--asset",
                "s02.video",
                "--verdict",
                "PASS",
                "--qa-report",
                str(qa_json),
                "--sheet",
                str(sheet_png),
                "--crops",
                str(crops_png),
                "--reviewer-id",
                "rev-lane-1",
                "--json",
            )
            self.assertEqual(r5_ok.returncode, 0, msg=r5_ok.stdout + r5_ok.stderr)
            rec_ok = json.loads(r5_ok.stdout)["record"]
            self.assertEqual(rec_ok["reviewer_id"], "rev-lane-1")
            self.assertEqual(rec_ok["sheet"], str(sheet_png))

            # Corrupt review-log.jsonl fails closed
            with (camp / "qc" / "review-log.jsonl").open("a", encoding="utf-8") as fh:
                fh.write("{corrupt\n")
            p3 = self._run_py(
                "qa_media.py",
                "log-review",
                "--campaign",
                str(camp),
                "--round",
                "R5",
                "--asset",
                "s02.video",
                "--verdict",
                "PASS",
                "--json",
            )
            self.assertEqual(p3.returncode, 2, msg=p3.stdout + p3.stderr)

    def test_retro_harvest_aggregates_traces_and_memory_search_finds_hits(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_str:
            root = Path(tmp_str)
            shutil.copytree(REPO_ROOT / "studio", root / "studio")
            shutil.copytree(REPO_ROOT / "brands" / "example-brand", root / "brands" / "example-brand")
            camp = root / "campaigns" / "test-spot"
            shutil.copytree(EXAMPLE_CAMPAIGN, camp)

            # Add v2 prompt churn, Web Unlimited log, and review log
            (camp / "prompts" / "s02_still_v2.txt").write_text("Tighter sunlit brass clasp.\n", encoding="utf-8")
            self._run_py(
                "hf_guard.py",
                "log-web",
                "--campaign",
                str(camp),
                "--shot",
                "s02",
                "--kind",
                "still",
                "--round",
                "R3",
                "--model",
                "new_untracked_model_x",
                "--status",
                "ip_detected",
                "--note",
                "blocked brand word",
            )
            self._run_py(
                "qa_media.py",
                "log-review",
                "--campaign",
                str(camp),
                "--round",
                "R3",
                "--asset",
                "s02.still",
                "--verdict",
                "FAIL",
                "--defect-class",
                "VISUAL_DRIFT_DEFECT",
                "--summary",
                "Brass clasp drifted to chrome",
            )
            self._run_py(
                "qa_media.py",
                "log-review",
                "--campaign",
                str(camp),
                "--round",
                "R3",
                "--asset",
                "animatic.mp4",
                "--verdict",
                "FAIL",
                "--defect-class",
                "NARRATIVE_DEFECT",
                "--summary",
                "Hero object silhouette ambiguous on 0.1s read",
            )

            harv = self._run_py("retro_harvest.py", str(camp), "--json")
            self.assertEqual(harv.returncode, 0, msg=harv.stdout + harv.stderr)
            hdata = json.loads(harv.stdout)
            self.assertTrue(hdata["ok"])
            self.assertEqual(hdata["telemetry"]["web_unlimited_runs"], 1)
            self.assertEqual(len(hdata["telemetry"]["web_failures"]), 1)
            self.assertEqual(hdata["reviews"]["by_defect_class"]["VISUAL_DRIFT_DEFECT"], 1)
            self.assertEqual(hdata["reviews"]["by_defect_class"]["NARRATIVE_DEFECT"], 1)
            mem_ok = self._run_py("check-memory.py", str(root), "--as-of", "2026-11-21", "--json")
            self.assertEqual(mem_ok.returncode, 0, msg=mem_ok.stdout + mem_ok.stderr)
            self.assertIn("new_untracked_model_x", hdata["graduation_signals"]["models_not_in_engine_memory"])
            self.assertTrue(
                any(item["asset"] == "s02_still" for item in hdata["churn"]["multi_version_prompts"])
            )

            # FTS5 search finds both studio English rules and review-log finding
            s1 = self._run_py("memory_search.py", "Brass clasp chrome", "--root", str(root), "--json")
            self.assertEqual(s1.returncode, 0, msg=s1.stdout + s1.stderr)
            s1_data = json.loads(s1.stdout)
            self.assertGreaterEqual(s1_data["hit_count"], 1)
            self.assertTrue(any("review-log.jsonl" in h["path"] for h in s1_data["hits"]))

            # Punctuation-heavy query never crashes FTS5
            s2 = self._run_py("memory_search.py", "480p -> 1080p shimmer", "--root", str(root), "--json")
            self.assertEqual(s2.returncode, 0, msg=s2.stdout + s2.stderr)
            self.assertGreaterEqual(json.loads(s2.stdout)["hit_count"], 1)


if __name__ == "__main__":
    unittest.main()

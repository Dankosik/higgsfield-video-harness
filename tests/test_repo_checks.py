"""Repository-level checks: instructions, docs links, campaign scaffolding, and example campaign."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = REPO_ROOT / "scripts"
EXAMPLE_CAMPAIGN = REPO_ROOT / "campaigns" / "example-product-spot"
EXAMPLE_BRAND = REPO_ROOT / "brands" / "example-brand" / "brand.md"
EXAMPLE_BRAND_TASTE = REPO_ROOT / "brands" / "example-brand" / "taste.md"

FORBIDDEN_BINARY_EXTS = frozenset({".png", ".jpg", ".jpeg", ".mp4", ".mov", ".webm", ".wav", ".mp3"})
REQUIRED_NO_MUSIC_LINE = "NO MUSIC. NO BACKGROUND SCORE. Native diegetic sound only."


def _extract_campaign_cap(status_data: dict) -> int | float | None:
    sub = status_data.get("campaign") if isinstance(status_data.get("campaign"), dict) else status_data
    for key in ("cap", "campaign_cap"):
        val = sub.get(key)
        if isinstance(val, (int, float)) and not isinstance(val, bool):
            return val
    for key in ("campaign_cap", "cap"):
        val = status_data.get(key)
        if isinstance(val, (int, float)) and not isinstance(val, bool):
            return val
    return None


class TestRepoChecks(unittest.TestCase):
    def _run_py(self, script_name: str, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(SCRIPTS_DIR / script_name), *args],
            capture_output=True,
            text=True,
            check=False,
        )

    def test_check_instructions_passes(self) -> None:
        proc = self._run_py("check-instructions.py", str(REPO_ROOT))
        self.assertEqual(
            proc.returncode,
            0,
            msg=f"check-instructions.py failed:\nstdout={proc.stdout}\nstderr={proc.stderr}",
        )
        self.assertIn("roles=4", proc.stdout)
        self.assertIn("skills=18", proc.stdout)

    def test_minimalist_docs_layout_and_thirteen_skills_exist(self) -> None:
        expected_skills = (
            "idea-refine",
            "grilling",
            "studio-retro",
            "ad-references",
            "ad-concepts",
            "ad-script",
            "ad-storyboard",
            "video-narrative",
            "higgsfield-cli",
            "video-direction",
            "video-consistency",
            "video-qa",
            "video-assembly",
            "video-v2v-rewrite",
            "video-previz-vfx",
            "performance-ads",
            "hybrid-motion-graphics",
            "youtube-clipping",
        )
        skills_root = REPO_ROOT / ".agents" / "skills"
        for name in expected_skills:
            skill_md = skills_root / name / "SKILL.md"
            self.assertTrue(skill_md.is_file(), msg=f"Missing skill: {skill_md}")

        for studio_doc in ("director.md", "engine-memory.md", "evolution-log.md"):
            sp = REPO_ROOT / "studio" / studio_doc
            self.assertTrue(sp.is_file(), msg=f"Missing studio memory file: {sp}")

        for doc in (
            "flows.md",
            "workflow.md",
            "delegation.md",
            "grilling.md",
            "writing-for-agents.md",
            "ad-craft-glossary.md",
        ):
            doc_path = REPO_ROOT / "docs" / doc
            self.assertTrue(doc_path.is_file(), msg=f"Missing minimalist doc: {doc_path}")
            self.assertGreater(len(doc_path.read_text(encoding="utf-8").strip()), 100)

        self.assertFalse(
            (REPO_ROOT / "docs" / "video-workflow").exists(),
            "Superseded multi-file docs/video-workflow/ tree must remain removed",
        )
        self.assertFalse(
            (REPO_ROOT / ".agents" / "roles" / "adjudicator-agent.toml").exists(),
            "Redundant adjudicator-agent.toml role must remain removed",
        )

    def test_check_docs_passes(self) -> None:
        proc = self._run_py("check-docs.py", str(REPO_ROOT))
        self.assertEqual(
            proc.returncode,
            0,
            msg=f"check-docs.py failed:\nstdout={proc.stdout}\nstderr={proc.stderr}",
        )

    def test_check_memory_passes(self) -> None:
        proc = self._run_py("check-memory.py", str(REPO_ROOT))
        self.assertEqual(
            proc.returncode,
            0,
            msg=f"check-memory.py failed:\nstdout={proc.stdout}\nstderr={proc.stderr}",
        )

    def test_campaign_init_scaffolds_structure_and_guards_duplicates(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            proc = self._run_py(
                "campaign_init.py",
                "--slug",
                "nordic-launch",
                "--brand",
                "example-brand",
                "--root",
                str(tmp),
            )
            self.assertEqual(
                proc.returncode,
                0,
                msg=f"campaign_init.py failed:\nstdout={proc.stdout}\nstderr={proc.stderr}",
            )

            created_dirs = list((tmp / "campaigns").glob("*-nordic-launch"))
            self.assertEqual(len(created_dirs), 1, msg=f"Unexpected dirs: {created_dirs}")
            camp_dir = created_dirs[0]

            for rel in (
                "prompts",
                "qc",
                "media/references",
                "media/lookbook",
                "media/lookbook/characters",
                "media/lookbook/locations",
                "media/lookbook/props",
                "media/stills",
                "media/shots",
                "media/audio",
                "media/exports",
            ):
                self.assertTrue((camp_dir / rel).is_dir(), msg=f"Missing scaffold subdir: {rel}")

            self.assertFalse((camp_dir / "tasks").exists(), "Feedback-Loop Studio must not scaffold tasks/")
            self.assertFalse((camp_dir / "tasks.md").exists(), "Feedback-Loop Studio must not scaffold tasks.md")
            self.assertFalse((camp_dir / "intent.md").exists(), "Feedback-Loop Studio scaffolds brief.md, not intent.md")

            brief_path = camp_dir / "brief.md"
            self.assertTrue(brief_path.is_file(), "Missing scaffolded brief.md")
            brief_text = brief_path.read_text(encoding="utf-8")
            self.assertIn("status: draft", brief_text)
            self.assertIn("brands/example-brand/brand.md", brief_text)
            self.assertIn("State shift (Before -> After):", brief_text)
            self.assertIn("Primary misread risk:", brief_text)

            taste_log_path = camp_dir / "taste-log.md"
            self.assertTrue(taste_log_path.is_file(), "Missing scaffolded taste-log.md")
            taste_text = taste_log_path.read_text(encoding="utf-8")
            self.assertIn("# Taste Log:", taste_text)

            taste_active_path = camp_dir / "taste-active.md"
            self.assertTrue(taste_active_path.is_file(), "Missing scaffolded taste-active.md")
            self.assertIn("# Active Taste Snapshot:", taste_active_path.read_text(encoding="utf-8"))

            # Second invocation with identical slug/day must refuse overwrite
            dup_proc = self._run_py(
                "campaign_init.py",
                "--slug",
                "nordic-launch",
                "--root",
                str(tmp),
            )
            self.assertNotEqual(dup_proc.returncode, 0)

            # Invalid slug must return exit 2
            bad_proc = self._run_py(
                "campaign_init.py",
                "--slug",
                "../escape",
                "--root",
                str(tmp),
            )
            self.assertEqual(bad_proc.returncode, 2)

    def test_example_product_spot_end_to_end(self) -> None:
        self.assertTrue(EXAMPLE_BRAND.is_file(), "Missing brands/example-brand/brand.md")
        self.assertTrue(EXAMPLE_BRAND_TASTE.is_file(), "Missing brands/example-brand/taste.md")

        for rel in (
            "brief.md",
            "taste-log.md",
            "taste-active.md",
            "script.md",
            "storyboard.md",
            "style-bible.md",
            "shotlist.json",
            "prompts/lb_traveler_v1.txt",
            "prompts/s01_still_v1.txt",
            "prompts/s01_video_v1.txt",
            "prompts/s02_still_v1.txt",
            "prompts/s02_video_v1.txt",
            "prompts/s03_still_v1.txt",
            "prompts/s03_video_v1.txt",
        ):
            self.assertTrue(
                (EXAMPLE_CAMPAIGN / rel).is_file(),
                msg=f"Missing example campaign file: {rel}",
            )

        # Ensure legacy ledger/intent files do not exist in Feedback-Loop Studio campaign
        for legacy in ("tasks.md", "tasks", "intent.md", "treatment.md"):
            self.assertFalse(
                (EXAMPLE_CAMPAIGN / legacy).exists(),
                msg=f"Unexpected legacy path in example campaign: {legacy}",
            )

        # Verify lookbook, photoreal still model, workflow/model schema, and per-asset statuses in shotlist.json
        shotlist = json.loads((EXAMPLE_CAMPAIGN / "shotlist.json").read_text(encoding="utf-8"))
        self.assertIsInstance(shotlist.get("lookbook"), list)
        self.assertGreaterEqual(len(shotlist["lookbook"]), 1)
        for lb in shotlist["lookbook"]:
            self.assertEqual(lb["model"], "seedream_5_5", msg="Lookbook must use seedream_5_5 (not gpt_image_2_6)")
        for shot in shotlist["shots"]:
            self.assertEqual(
                shot["still"]["model"],
                "seedream_5_5",
                msg=f"{shot['id']} still must use seedream_5_5 (not gpt_image_2_6)",
            )
            video = shot["video"]
            self.assertEqual(video["mode"], "omni_reference", msg=f"{shot['id']} must use omni_reference")
            if video["model"] == "cinematic_studio_video_4_0":
                self.assertTrue(video["is_workflow"], msg=f"{shot['id']} CS 4.0 must set is_workflow: true")
                self.assertNotEqual(
                    video["draft_params"].get("resolution"),
                    "480p",
                    msg=f"{shot['id']} CS 4.0 must not dead-end in a 480p draft",
                )
            else:
                self.assertEqual(video["model"], "seedance_2_5", msg=f"{shot['id']} expected seedance_2_5")
                self.assertFalse(video["is_workflow"], msg=f"{shot['id']} seedance_2_5 must set is_workflow: false")
                self.assertTrue(
                    video["draft_params"].get("draft"),
                    msg=f"{shot['id']} seedance_2_5 draft_params must enable latent draft: true",
                )
            self.assertEqual(video["final_params"].get("resolution"), "1080p")
            self.assertEqual(video["final_params"].get("bitrate_mode"), "high")
            self.assertIn(shot["still"]["status"], ("DRAFT", "IN_REVIEW", "ITERATING", "LOCKED"))
            self.assertIn(video["status"], ("DRAFT", "IN_REVIEW", "ITERATING", "LOCKED"))

        style_text = (EXAMPLE_CAMPAIGN / "style-bible.md").read_text(encoding="utf-8")
        self.assertIn("status: active", style_text)
        self.assertIn("## Negative Constraints & Anti-IP Phrasing", style_text)

        taste_text = (EXAMPLE_CAMPAIGN / "taste-log.md").read_text(encoding="utf-8")
        for token in (
            "# Taste Log:",
            "Brand taste seed: brands/example-brand/taste.md",
            "### TL-01",
            "### TL-02",
        ):
            self.assertIn(token, taste_text, msg=f"Missing '{token}' in taste-log.md")

        # Verify canonical three-column script and continuity-locked storyboard sections
        script_text = (EXAMPLE_CAMPAIGN / "script.md").read_text(encoding="utf-8")
        for token in (
            "## Narrative Lock",
            "| Time | Video | Audio |",
            "## Read-aloud budget",
            "## Mute test",
            "Verdict: PASS",
            "[PAUSE ",
        ):
            self.assertIn(token, script_text, msg=f"Missing '{token}' in script.md")

        storyboard_text = (EXAMPLE_CAMPAIGN / "storyboard.md").read_text(encoding="utf-8")
        for token in (
            "## Narrative Lock",
            "## Continuity Lock",
            "### S01 |",
            "### S02 |",
            "### S03 |",
            "**Narrative job:**",
            "**Test-take check:**",
            "## Cut-by-cut continuity audit",
        ):
            self.assertIn(token, storyboard_text, msg=f"Missing '{token}' in storyboard.md")

        # Every video prompt must enforce native diegetic sound only
        for shot_id in ("s01", "s02", "s03"):
            lines = [
                ln.strip()
                for ln in (EXAMPLE_CAMPAIGN / "prompts" / f"{shot_id}_video_v1.txt")
                .read_text(encoding="utf-8")
                .splitlines()
                if ln.strip()
            ]
            self.assertEqual(
                lines[-1],
                REQUIRED_NO_MUSIC_LINE,
                msg=f"{shot_id}_video_v1.txt must end with diegetic-only directive",
            )

        # Zero committed binary media files in reference campaign
        binaries = [
            p
            for p in EXAMPLE_CAMPAIGN.rglob("*")
            if p.is_file() and p.suffix.lower() in FORBIDDEN_BINARY_EXTS
        ]
        self.assertEqual(binaries, [], msg=f"Unexpected binary files in example campaign: {binaries}")

        # Verify zero technical/CLI implementation jargon leaked into Director-facing brief.md
        brief_text = (EXAMPLE_CAMPAIGN / "brief.md").read_text(encoding="utf-8")
        for forbidden in (
            "H.264/AAC",
            "music_vol:",
            "-22 dBFS",
            "atempo",
            "scripts/hf_guard.py",
            "--round-cap",
            "scripts/qa_media.py",
            "85mm",
            "50mm",
            "35mm",
        ):
            self.assertNotIn(
                forbidden,
                brief_text,
                msg=f"Director-facing brief.md must not expose technical jargon {forbidden!r}",
            )

        # Validators & budget status pass cleanly
        brief_proc = self._run_py("check-brief.py", str(EXAMPLE_CAMPAIGN), "--json")
        self.assertEqual(brief_proc.returncode, 0, msg=brief_proc.stdout + brief_proc.stderr)
        self.assertTrue(json.loads(brief_proc.stdout)["ok"])

        campaign_proc = self._run_py("check-campaign.py", str(EXAMPLE_CAMPAIGN), "--json")
        self.assertEqual(campaign_proc.returncode, 0, msg=campaign_proc.stdout + campaign_proc.stderr)
        self.assertTrue(json.loads(campaign_proc.stdout)["ok"])

        status_proc = self._run_py(
            "hf_guard.py", "status", "--campaign", str(EXAMPLE_CAMPAIGN), "--json"
        )
        self.assertEqual(status_proc.returncode, 0, msg=status_proc.stdout + status_proc.stderr)
        st = json.loads(status_proc.stdout)
        self.assertTrue(st["ok"])
        self.assertEqual(_extract_campaign_cap(st), 400, msg=st)

    def test_check_instructions_catches_broken_role_output_schema_anchor(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_str:
            tmp_root = Path(tmp_str)
            shutil.copy2(REPO_ROOT / "AGENTS.md", tmp_root / "AGENTS.md")
            for sub in (".agents", ".codex", "docs"):
                shutil.copytree(REPO_ROOT / sub, tmp_root / sub)

            ok_proc = self._run_py("check-instructions.py", str(tmp_root))
            self.assertEqual(
                ok_proc.returncode,
                0,
                msg=f"Clean repo copy should pass check-instructions.py:\n{ok_proc.stdout}\n{ok_proc.stderr}",
            )

            role_toml = tmp_root / ".agents" / "roles" / "reviewer-agent.toml"
            original = role_toml.read_text(encoding="utf-8")
            mutated = original.replace(
                'output_schema = "docs/delegation.md#review-result"',
                'output_schema = "docs/delegation.md#nonexistent-anchor-fragment"',
                1,
            )
            self.assertNotEqual(original, mutated, "Expected to mutate reviewer-agent.toml output_schema")
            role_toml.write_text(mutated, encoding="utf-8")

            bad_proc = self._run_py("check-instructions.py", str(tmp_root))
            combined = f"{bad_proc.stdout}\n{bad_proc.stderr}"
            self.assertEqual(
                bad_proc.returncode,
                1,
                msg=f"Expected check-instructions.py to reject broken output_schema #anchor:\n{combined}",
            )
            self.assertTrue(
                any(
                    tok in combined.lower()
                    for tok in ("nonexistent-anchor-fragment", "anchor", "output_schema")
                ),
                msg=f"Expected anchor diagnostic, got:\n{combined}",
            )

    def test_check_instructions_enforces_layering_description_budget_and_orphan_refs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_str:
            tmp_root = Path(tmp_str)
            shutil.copy2(REPO_ROOT / "AGENTS.md", tmp_root / "AGENTS.md")
            for sub in (".agents", ".codex", "docs"):
                shutil.copytree(REPO_ROOT / sub, tmp_root / sub)

            # 1. Deep link in AGENTS.md bypassing owning SKILL.md must fail
            agents_path = tmp_root / "AGENTS.md"
            orig_agents = agents_path.read_text(encoding="utf-8")
            agents_path.write_text(
                orig_agents
                + "\n- Bypass -> [Camera](.agents/skills/video-direction/references/camera-control.md)\n",
                encoding="utf-8",
            )
            proc1 = self._run_py("check-instructions.py", str(tmp_root))
            self.assertEqual(proc1.returncode, 1, msg=proc1.stdout + proc1.stderr)
            self.assertIn("bypasses owning", proc1.stdout + proc1.stderr)
            agents_path.write_text(orig_agents, encoding="utf-8")

            # 2. Bloated always-loaded SKILL.md description (> 320 chars) must fail
            vc_skill = tmp_root / ".agents" / "skills" / "video-consistency" / "SKILL.md"
            orig_vc = vc_skill.read_text(encoding="utf-8")
            bloated_desc = "X" * 340
            vc_skill.write_text(
                orig_vc.replace(
                    'description: "Cross-shot',
                    f'description: "{bloated_desc} Cross-shot',
                    1,
                ),
                encoding="utf-8",
            )
            proc2 = self._run_py("check-instructions.py", str(tmp_root))
            self.assertEqual(proc2.returncode, 1, msg=proc2.stdout + proc2.stderr)
            self.assertIn("320 chars", proc2.stdout + proc2.stderr)
            vc_skill.write_text(orig_vc, encoding="utf-8")

            # 3. Unlinked orphan file under references/ must fail
            orphan = tmp_root / ".agents" / "skills" / "video-consistency" / "references" / "orphan.md"
            orphan.write_text("# Orphan\n", encoding="utf-8")
            proc3 = self._run_py("check-instructions.py", str(tmp_root))
            self.assertEqual(proc3.returncode, 1, msg=proc3.stdout + proc3.stderr)
            self.assertIn("orphan reference doc", proc3.stdout + proc3.stderr)


if __name__ == "__main__":
    unittest.main()

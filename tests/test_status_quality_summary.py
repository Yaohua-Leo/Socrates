from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from socrates.artifacts import generate_atomic_note_draft, generate_exercise_drafts
from socrates.context import load_project
from socrates.kb import build_reference_kb
from socrates.notes import export_reviewed_notes_to_obsidian, review_atomic_note
from socrates.project import ProjectSpec, create_project
from socrates.state import LearningStatePatch, update_learning_state
from socrates.tutoring import run_scripted_tutoring_session


REPO_ROOT = Path(__file__).resolve().parents[1]


class StatusQualitySummaryTests(unittest.TestCase):
    def test_status_cli_json_summarizes_empty_project_without_writes(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = create_project(ProjectSpec(topic="Group Theory", path=Path(temp_dir) / "p"))
            project_files_before = _project_file_snapshot(project)

            status = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "socrates",
                    "status",
                    "--project",
                    str(project),
                    "--json",
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(status.returncode, 0, status.stderr)
            self.assertNotIn("Project:", status.stdout)
            payload = json.loads(status.stdout)
            self.assertEqual(payload["schema_version"], 1)
            self.assertEqual(payload["quality_boundary"], "deterministic_project_status")
            self.assertEqual(payload["project"], "Group Theory")
            self.assertEqual(payload["root"], str(project))
            self.assertEqual(payload["current_phase"], "planning_complete")
            self.assertEqual(payload["counts"]["imported_sources"], 0)
            self.assertEqual(payload["counts"]["pending_draft_notes"], 0)
            self.assertEqual(payload["counts"]["learning_reports"], 0)
            self.assertEqual(
                payload["reference_kb"],
                {"status": "not_applicable", "object_count": 0},
            )
            self.assertEqual(
                payload["report_history"],
                {"status": "not_run", "snapshots": 0, "latest": "none"},
            )
            self.assertEqual(
                payload["study_brief"],
                {
                    "status": "not_run",
                    "recorded_next_action": "none",
                    "current_next_action": "none",
                },
            )
            self.assertEqual(
                payload["queue"],
                {
                    "workflow_actions": 0,
                    "quality_checks_to_fix": 0,
                    "action_summary": {
                        "completion": "clear",
                        "open_actions": 0,
                        "blockers": 0,
                        "can_continue_learning": 0,
                        "needs_human_review": 0,
                        "next_action": "none",
                    },
                },
            )
            self.assertEqual(payload["quality"]["ingestion"], {"status": "not_run"})
            self.assertEqual(payload["quality"]["note"], {"status": "not_run"})
            self.assertEqual(payload["quality"]["exercise"], {"status": "not_run"})
            self.assertEqual(payload["quality"]["exercise_validation"], {"status": "not_run"})
            self.assertEqual(payload["quality"]["tutoring"], {"status": "not_run"})
            self.assertEqual(payload["quality"]["tool_verification"], {"status": "not_run"})
            self.assertEqual(payload["session_score"], {"status": "not_run"})
            self.assertEqual(payload["session_closeout"], {"status": "not_run"})
            self.assertEqual(payload["multi_session_regression"], {"status": "not_run"})
            self.assertEqual(payload["next_session_plan"], {"status": "not_created"})
            self.assertEqual(payload["benchmark"], {"status": "not_run"})
            self.assertEqual(payload["misconceptions"], {"active": 0, "resolved": 0})
            self.assertEqual(_project_file_snapshot(project), project_files_before)

    def test_status_cli_json_reports_invalid_manifests_conservatively(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = create_project(ProjectSpec(topic="Group Theory", path=Path(temp_dir) / "p"))
            evals = project / "08_evals"
            (evals / "ingestion_quality_manifest.json").write_text(
                "{not valid json\n",
                encoding="utf-8",
                newline="\n",
            )
            (evals / "note_quality_manifest.json").write_text(
                json.dumps({"schema_version": 1, "checked": 2, "passed": 2, "failed": 1})
                + "\n",
                encoding="utf-8",
                newline="\n",
            )
            (evals / "exercise_quality_manifest.json").write_text(
                "[]\n",
                encoding="utf-8",
                newline="\n",
            )
            (evals / "tool_verification_quality_manifest.json").write_text(
                json.dumps({"schema_version": 1, "status": "pass", "checked": "1"})
                + "\n",
                encoding="utf-8",
                newline="\n",
            )
            (evals / "session_score_manifest.json").write_text(
                "{not valid json\n",
                encoding="utf-8",
                newline="\n",
            )
            (evals / "session_closeout_manifest.json").write_text(
                "{not valid json\n",
                encoding="utf-8",
                newline="\n",
            )
            (evals / "multi_session_regression_manifest.json").write_text(
                "{not valid json\n",
                encoding="utf-8",
                newline="\n",
            )

            status = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "socrates",
                    "status",
                    "--project",
                    str(project),
                    "--json",
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(status.returncode, 0, status.stderr)
            payload = json.loads(status.stdout)
            self.assertEqual(payload["quality"]["ingestion"], {"status": "invalid"})
            self.assertEqual(payload["quality"]["note"], {"status": "invalid"})
            self.assertEqual(payload["quality"]["exercise"], {"status": "invalid"})
            self.assertEqual(payload["quality"]["tutoring"], {"status": "not_run"})
            self.assertEqual(payload["quality"]["tool_verification"], {"status": "invalid"})
            self.assertEqual(payload["session_score"], {"status": "invalid"})
            self.assertEqual(payload["session_closeout"], {"status": "invalid"})
            self.assertEqual(payload["multi_session_regression"], {"status": "invalid"})

    def test_status_cli_summarizes_report_history(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = create_project(ProjectSpec(topic="Group Theory", path=Path(temp_dir) / "p"))

            first = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "socrates",
                    "report",
                    "weekly",
                    "--project",
                    str(project),
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(first.returncode, 0, first.stderr)

            update_learning_state(
                load_project(project),
                LearningStatePatch(concept_mastery={"quotient_group": 0.42}),
            )
            second = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "socrates",
                    "report",
                    "weekly",
                    "--project",
                    str(project),
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(second.returncode, 0, second.stderr)

            status = subprocess.run(
                [sys.executable, "-m", "socrates", "status", "--project", str(project)],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(status.returncode, 0, status.stderr)
            self.assertIn("Report history: current", status.stdout)
            self.assertIn("Report history snapshots: 2", status.stdout)
            self.assertIn("Latest report history: #2 weekly attention", status.stdout)

    def test_status_cli_summarizes_artifact_quality_manifests(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = create_project(ProjectSpec(topic="Group Theory", path=Path(temp_dir) / "p"))
            curated = project / "01_references" / "curated" / "normal_subgroups.curated.md"
            curated.write_text(
                "# Group Theory\n"
                "## Source Metadata\n"
                "- source_id: normality_notes\n"
                "- title: Normality Notes\n"
                "- role: lecture_notes\n"
                "## Normal Subgroups\n"
                "### Definition: Normal Subgroup\n"
                "A normal subgroup is stable under conjugation.\n"
                "Depends: subgroup, conjugation\n",
                encoding="utf-8",
                newline="\n",
            )
            build_reference_kb(project)
            generate_atomic_note_draft(
                project,
                concept="Normal Subgroup",
                note_type="definition",
                body=(
                    "A normal subgroup is stable under conjugation.\n\n"
                    "## Review Questions\n\n"
                    "- How is normality different from commutativity?\n"
                ),
                source_id="normality_notes",
            )
            generate_exercise_drafts(
                project,
                concept="Normal Subgroup",
                source_id="normality_notes",
                prerequisites=["subgroup", "conjugation"],
                count=5,
            )
            script = Path(temp_dir) / "session.script"
            script.write_text(
                "topic: Normal Subgroup\n"
                "goal: Distinguish normality from commutativity.\n"
                "question: What must be checked for normality?\n"
                "hint: Use conjugation invariance.\n"
                "hint: Compare gNg^-1=N with elementwise commutativity.\n"
                "attempt: I should check gNg^-1 = N.\n",
                encoding="utf-8",
                newline="\n",
            )
            run_scripted_tutoring_session(project, script, session_id="session_0001")

            for command in (
                ["kb", "check", "--project", str(project)],
                ["note", "check", "--project", str(project)],
                ["exercise", "check", "--project", str(project)],
                ["session", "check", "--project", str(project), "--session-id", "session_0001"],
            ):
                result = subprocess.run(
                    [sys.executable, "-m", "socrates", *command],
                    cwd=REPO_ROOT,
                    text=True,
                    capture_output=True,
                    check=False,
                )
                self.assertEqual(result.returncode, 0, result.stderr)

            status = subprocess.run(
                [sys.executable, "-m", "socrates", "status", "--project", str(project)],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(status.returncode, 0, status.stderr)
            self.assertIn("Ingestion quality check: pass (1/1 passed, 0 failed)", status.stdout)
            self.assertIn("Note quality check: pass (1/1 passed, 0 failed)", status.stdout)
            self.assertIn("Exercise quality check: pass (5/5 passed, 0 failed)", status.stdout)
            self.assertIn("Tutoring quality check: pass (1/1 passed, 0 failed)", status.stdout)

    def test_status_cli_counts_quality_checks_to_fix(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = create_project(ProjectSpec(topic="Group Theory", path=Path(temp_dir) / "p"))
            (project / "08_evals" / "note_quality_manifest.json").write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "checked": 1,
                        "passed": 0,
                        "failed": 1,
                        "notes": [
                            {
                                "id": "normal_subgroup",
                                "path": "04_atomic_notes/drafts/normal_subgroup.md",
                                "quality_status": "fail",
                                "issues": ["missing section Review Questions"],
                            }
                        ],
                    },
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
                newline="\n",
            )

            status = subprocess.run(
                [sys.executable, "-m", "socrates", "status", "--project", str(project)],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(status.returncode, 0, status.stderr)
            self.assertIn("Note quality check: fail (0/1 passed, 1 failed)", status.stdout)
            self.assertIn("Quality checks to fix: 1", status.stdout)

    def test_status_cli_reports_invalid_quality_manifests_conservatively(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = create_project(ProjectSpec(topic="Group Theory", path=Path(temp_dir) / "p"))
            evals = project / "08_evals"
            (evals / "ingestion_quality_manifest.json").write_text(
                "{not valid json\n",
                encoding="utf-8",
                newline="\n",
            )
            (evals / "note_quality_manifest.json").write_text(
                json.dumps({"schema_version": 1, "checked": 2, "passed": 2, "failed": 1})
                + "\n",
                encoding="utf-8",
                newline="\n",
            )
            (evals / "exercise_quality_manifest.json").write_text(
                "[]\n",
                encoding="utf-8",
                newline="\n",
            )
            (evals / "tool_verification_quality_manifest.json").write_text(
                json.dumps({"schema_version": 1, "status": "pass", "checked": "1"})
                + "\n",
                encoding="utf-8",
                newline="\n",
            )
            (evals / "session_score_manifest.json").write_text(
                "{not valid json\n",
                encoding="utf-8",
                newline="\n",
            )
            (evals / "session_closeout_manifest.json").write_text(
                "{not valid json\n",
                encoding="utf-8",
                newline="\n",
            )
            (evals / "multi_session_regression_manifest.json").write_text(
                "{not valid json\n",
                encoding="utf-8",
                newline="\n",
            )

            status = subprocess.run(
                [sys.executable, "-m", "socrates", "status", "--project", str(project)],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(status.returncode, 0, status.stderr)
            self.assertIn("Ingestion quality check: invalid", status.stdout)
            self.assertIn("Note quality check: invalid", status.stdout)
            self.assertIn("Exercise quality check: invalid", status.stdout)
            self.assertIn("Tutoring quality check: not run", status.stdout)
            self.assertIn("Tool verification check: invalid", status.stdout)
            self.assertIn("Session score: invalid", status.stdout)
            self.assertIn("Session closeout: invalid", status.stdout)
            self.assertIn("Session closeout sessions: invalid", status.stdout)
            self.assertIn("Session closeout score: invalid", status.stdout)
            self.assertIn("Multi-session regression: invalid", status.stdout)
            self.assertIn("Multi-session regression checks: invalid", status.stdout)
            self.assertIn("Multi-session regression issues: invalid", status.stdout)

    def test_status_cli_counts_reviewed_notes_pending_obsidian_export(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = create_project(ProjectSpec(topic="Group Theory", path=Path(temp_dir) / "p"))
            generate_atomic_note_draft(
                project,
                concept="Normal Subgroup",
                note_type="definition",
                body=(
                    "A normal subgroup is stable under conjugation; compare [[Subgroup]].\n\n"
                    "## Review Questions\n\n"
                    "- What condition distinguishes normality from centrality?\n"
                ),
                source_id="df",
            )
            review_atomic_note(project, "normal_subgroup")

            status = subprocess.run(
                [sys.executable, "-m", "socrates", "status", "--project", str(project)],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(status.returncode, 0, status.stderr)
            self.assertIn("Reviewed notes: 1", status.stdout)
            self.assertIn("Obsidian exports: 0", status.stdout)
            self.assertIn("Obsidian exports to run: 1", status.stdout)

    def test_status_cli_rejects_malformed_reference_kb_index_state(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = create_project(ProjectSpec(topic="Group Theory", path=Path(temp_dir) / "p"))
            curated = project / "01_references" / "curated" / "normality.curated.md"
            curated.write_text(
                "### Definition: Normal Subgroup\n"
                "A normal subgroup is stable under conjugation.\n"
                "Depends: subgroup, conjugation\n",
                encoding="utf-8",
                newline="\n",
            )
            index_path = project / "06_kb" / "chunks" / "reference_index.json"
            index_path.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "objects": ["not an object"],
                        "chunks": [],
                    },
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
                newline="\n",
            )

            status = subprocess.run(
                [sys.executable, "-m", "socrates", "status", "--project", str(project)],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(status.returncode, 0, status.stderr)
            self.assertIn("Curated references: 1", status.stdout)
            self.assertIn("KB objects: 0", status.stdout)
            self.assertIn("Reference KB status: invalid", status.stdout)
            self.assertIn("Current phase: references_curated", status.stdout)
            self.assertNotIn("Current phase: reference_kb_ready", status.stdout)

    def test_status_cli_rejects_reference_index_non_curated_provenance(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = create_project(ProjectSpec(topic="Group Theory", path=Path(temp_dir) / "p"))
            curated = project / "01_references" / "curated" / "normality.curated.md"
            curated.write_text(
                "### Definition: Normal Subgroup\n"
                "A normal subgroup is stable under conjugation.\n"
                "Depends: subgroup, conjugation\n",
                encoding="utf-8",
                newline="\n",
            )
            build_reference_kb(project)
            index_path = project / "06_kb" / "chunks" / "reference_index.json"
            index = json.loads(index_path.read_text(encoding="utf-8"))
            index["objects"][0]["source"]["path"] = "README.md"
            index["chunks"][0]["metadata"]["source"]["path"] = "README.md"
            index["chunks"][0]["metadata"]["source_path"] = "README.md"
            index_path.write_text(
                json.dumps(index, indent=2) + "\n",
                encoding="utf-8",
                newline="\n",
            )

            status = subprocess.run(
                [sys.executable, "-m", "socrates", "status", "--project", str(project)],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(status.returncode, 0, status.stderr)
            self.assertIn("Curated references: 1", status.stdout)
            self.assertIn("KB objects: 0", status.stdout)
            self.assertIn("Reference KB status: invalid", status.stdout)
            self.assertIn("Current phase: references_curated", status.stdout)
            self.assertNotIn("Current phase: reference_kb_ready", status.stdout)

    def test_status_cli_rejects_reference_index_out_of_range_source_lines(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = create_project(ProjectSpec(topic="Group Theory", path=Path(temp_dir) / "p"))
            curated = project / "01_references" / "curated" / "normality.curated.md"
            curated.write_text(
                "### Definition: Normal Subgroup\n"
                "A normal subgroup is stable under conjugation.\n"
                "Depends: subgroup, conjugation\n",
                encoding="utf-8",
                newline="\n",
            )
            build_reference_kb(project)
            index_path = project / "06_kb" / "chunks" / "reference_index.json"
            index = json.loads(index_path.read_text(encoding="utf-8"))
            index["objects"][0]["source"]["line"] = 99
            index["chunks"][0]["metadata"]["source"]["line"] = 99
            index["chunks"][0]["metadata"]["source_line"] = 99
            index_path.write_text(
                json.dumps(index, indent=2) + "\n",
                encoding="utf-8",
                newline="\n",
            )

            status = subprocess.run(
                [sys.executable, "-m", "socrates", "status", "--project", str(project)],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(status.returncode, 0, status.stderr)
            self.assertIn("Curated references: 1", status.stdout)
            self.assertIn("KB objects: 0", status.stdout)
            self.assertIn("Reference KB status: invalid", status.stdout)
            self.assertIn("Current phase: references_curated", status.stdout)
            self.assertNotIn("Current phase: reference_kb_ready", status.stdout)

    def test_status_cli_rejects_reference_index_mismatched_chunk_provenance(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = create_project(ProjectSpec(topic="Group Theory", path=Path(temp_dir) / "p"))
            curated = project / "01_references" / "curated" / "normality.curated.md"
            curated.write_text(
                "### Definition: Normal Subgroup\n"
                "A normal subgroup is stable under conjugation.\n"
                "Depends: subgroup, conjugation\n",
                encoding="utf-8",
                newline="\n",
            )
            alternate = project / "01_references" / "curated" / "quotients.curated.md"
            alternate.write_text(
                "# Quotient Groups\n",
                encoding="utf-8",
                newline="\n",
            )
            build_reference_kb(project)
            index_path = project / "06_kb" / "chunks" / "reference_index.json"
            index = json.loads(index_path.read_text(encoding="utf-8"))
            index["chunks"][0]["metadata"]["source"]["path"] = (
                "01_references/curated/quotients.curated.md"
            )
            index["chunks"][0]["metadata"]["source"]["line"] = 1
            index["chunks"][0]["metadata"]["source_path"] = (
                "01_references/curated/quotients.curated.md"
            )
            index["chunks"][0]["metadata"]["source_line"] = 1
            index_path.write_text(
                json.dumps(index, indent=2) + "\n",
                encoding="utf-8",
                newline="\n",
            )

            status = subprocess.run(
                [sys.executable, "-m", "socrates", "status", "--project", str(project)],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(status.returncode, 0, status.stderr)
            self.assertIn("Curated references: 2", status.stdout)
            self.assertIn("KB objects: 0", status.stdout)
            self.assertIn("Reference KB status: invalid", status.stdout)
            self.assertIn("Current phase: references_curated", status.stdout)
            self.assertNotIn("Current phase: reference_kb_ready", status.stdout)

    def test_status_cli_rejects_reference_index_fabricated_object_statement(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = create_project(ProjectSpec(topic="Group Theory", path=Path(temp_dir) / "p"))
            curated = project / "01_references" / "curated" / "normality.curated.md"
            curated.write_text(
                "### Definition: Normal Subgroup\n"
                "A normal subgroup is stable under conjugation.\n"
                "Depends: subgroup, conjugation\n",
                encoding="utf-8",
                newline="\n",
            )
            build_reference_kb(project)
            index_path = project / "06_kb" / "chunks" / "reference_index.json"
            index = json.loads(index_path.read_text(encoding="utf-8"))
            index["objects"][0]["statement"] = "Every subgroup is normal."
            index["chunks"][0]["text"] = "Every subgroup is normal."
            index_path.write_text(
                json.dumps(index, indent=2) + "\n",
                encoding="utf-8",
                newline="\n",
            )

            status = subprocess.run(
                [sys.executable, "-m", "socrates", "status", "--project", str(project)],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(status.returncode, 0, status.stderr)
            self.assertIn("Curated references: 1", status.stdout)
            self.assertIn("KB objects: 0", status.stdout)
            self.assertIn("Reference KB status: invalid", status.stdout)
            self.assertIn("Current phase: references_curated", status.stdout)
            self.assertNotIn("Current phase: reference_kb_ready", status.stdout)

    def test_status_cli_rejects_reference_index_fabricated_chunk_text(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = create_project(ProjectSpec(topic="Group Theory", path=Path(temp_dir) / "p"))
            curated = project / "01_references" / "curated" / "normality.curated.md"
            curated.write_text(
                "### Definition: Normal Subgroup\n"
                "A normal subgroup is stable under conjugation.\n"
                "Depends: subgroup, conjugation\n",
                encoding="utf-8",
                newline="\n",
            )
            build_reference_kb(project)
            index_path = project / "06_kb" / "chunks" / "reference_index.json"
            index = json.loads(index_path.read_text(encoding="utf-8"))
            index["chunks"][0]["text"] = "Every subgroup is normal."
            index_path.write_text(
                json.dumps(index, indent=2) + "\n",
                encoding="utf-8",
                newline="\n",
            )

            status = subprocess.run(
                [sys.executable, "-m", "socrates", "status", "--project", str(project)],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(status.returncode, 0, status.stderr)
            self.assertIn("Curated references: 1", status.stdout)
            self.assertIn("KB objects: 0", status.stdout)
            self.assertIn("Reference KB status: invalid", status.stdout)
            self.assertIn("Current phase: references_curated", status.stdout)
            self.assertNotIn("Current phase: reference_kb_ready", status.stdout)

    def test_status_cli_rejects_reference_index_statement_from_later_object(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = create_project(ProjectSpec(topic="Group Theory", path=Path(temp_dir) / "p"))
            curated = project / "01_references" / "curated" / "normality.curated.md"
            curated.write_text(
                "### Definition: Normal Subgroup\n"
                "A normal subgroup is stable under conjugation.\n"
                "Depends: subgroup, conjugation\n\n"
                "### Theorem: Kernels are Normal\n"
                "The kernel of a homomorphism is a normal subgroup.\n"
                "Depends: kernel, homomorphism\n",
                encoding="utf-8",
                newline="\n",
            )
            build_reference_kb(project)
            index_path = project / "06_kb" / "chunks" / "reference_index.json"
            index = json.loads(index_path.read_text(encoding="utf-8"))
            later_statement = "The kernel of a homomorphism is a normal subgroup."
            index["objects"][0]["statement"] = later_statement
            index["chunks"][0]["text"] = later_statement
            index_path.write_text(
                json.dumps(index, indent=2) + "\n",
                encoding="utf-8",
                newline="\n",
            )

            status = subprocess.run(
                [sys.executable, "-m", "socrates", "status", "--project", str(project)],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(status.returncode, 0, status.stderr)
            self.assertIn("Curated references: 1", status.stdout)
            self.assertIn("KB objects: 0", status.stdout)
            self.assertIn("Reference KB status: invalid", status.stdout)
            self.assertIn("Current phase: references_curated", status.stdout)
            self.assertNotIn("Current phase: reference_kb_ready", status.stdout)

    def test_status_cli_requires_reference_kb_derived_indexes(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = create_project(ProjectSpec(topic="Group Theory", path=Path(temp_dir) / "p"))
            curated = project / "01_references" / "curated" / "normality.curated.md"
            curated.write_text(
                "### Definition: Normal Subgroup\n"
                "A normal subgroup is stable under conjugation.\n"
                "Depends: subgroup, conjugation\n",
                encoding="utf-8",
                newline="\n",
            )
            build_reference_kb(project)
            (project / "06_kb" / "chapter_index.json").unlink()

            status = subprocess.run(
                [sys.executable, "-m", "socrates", "status", "--project", str(project)],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(status.returncode, 0, status.stderr)
            self.assertIn("Curated references: 1", status.stdout)
            self.assertIn("KB objects: 0", status.stdout)
            self.assertIn("Reference KB status: missing", status.stdout)
            self.assertIn("Current phase: references_curated", status.stdout)
            self.assertNotIn("Current phase: reference_kb_ready", status.stdout)

    def test_status_cli_rejects_malformed_reference_kb_derived_index_rows(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = create_project(ProjectSpec(topic="Group Theory", path=Path(temp_dir) / "p"))
            curated = project / "01_references" / "curated" / "normality.curated.md"
            curated.write_text(
                "### Definition: Normal Subgroup\n"
                "A normal subgroup is stable under conjugation.\n"
                "Depends: subgroup, conjugation\n",
                encoding="utf-8",
                newline="\n",
            )
            build_reference_kb(project)
            (project / "06_kb" / "concept_graph.json").write_text(
                json.dumps(
                    {
                        "nodes": ["not an object"],
                        "edges": [],
                    },
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
                newline="\n",
            )

            status = subprocess.run(
                [sys.executable, "-m", "socrates", "status", "--project", str(project)],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(status.returncode, 0, status.stderr)
            self.assertIn("Curated references: 1", status.stdout)
            self.assertIn("KB objects: 0", status.stdout)
            self.assertIn("Reference KB status: invalid", status.stdout)
            self.assertIn("Current phase: references_curated", status.stdout)
            self.assertNotIn("Current phase: reference_kb_ready", status.stdout)

    def test_status_cli_rejects_reference_kb_graph_missing_required_fields(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = create_project(ProjectSpec(topic="Group Theory", path=Path(temp_dir) / "p"))
            curated = project / "01_references" / "curated" / "normality.curated.md"
            curated.write_text(
                "### Definition: Normal Subgroup\n"
                "A normal subgroup is stable under conjugation.\n"
                "Depends: subgroup, conjugation\n",
                encoding="utf-8",
                newline="\n",
            )
            build_reference_kb(project)
            graph_path = project / "06_kb" / "concept_graph.json"
            graph = json.loads(graph_path.read_text(encoding="utf-8"))
            graph["nodes"][0].pop("label")
            graph_path.write_text(
                json.dumps(graph, indent=2) + "\n",
                encoding="utf-8",
                newline="\n",
            )

            status = subprocess.run(
                [sys.executable, "-m", "socrates", "status", "--project", str(project)],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(status.returncode, 0, status.stderr)
            self.assertIn("Curated references: 1", status.stdout)
            self.assertIn("KB objects: 0", status.stdout)
            self.assertIn("Reference KB status: invalid", status.stdout)
            self.assertIn("Current phase: references_curated", status.stdout)
            self.assertNotIn("Current phase: reference_kb_ready", status.stdout)

    def test_status_cli_rejects_dependency_graph_non_prerequisite_edges(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = create_project(ProjectSpec(topic="Group Theory", path=Path(temp_dir) / "p"))
            curated = project / "01_references" / "curated" / "normality.curated.md"
            curated.write_text(
                "### Definition: Normal Subgroup\n"
                "A normal subgroup is stable under conjugation.\n"
                "Depends: subgroup, conjugation\n",
                encoding="utf-8",
                newline="\n",
            )
            build_reference_kb(project)
            graph_path = project / "06_kb" / "dependency_graph.json"
            graph = json.loads(graph_path.read_text(encoding="utf-8"))
            graph["edges"][0]["relationship"] = "example_of"
            graph_path.write_text(
                json.dumps(graph, indent=2) + "\n",
                encoding="utf-8",
                newline="\n",
            )

            status = subprocess.run(
                [sys.executable, "-m", "socrates", "status", "--project", str(project)],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(status.returncode, 0, status.stderr)
            self.assertIn("Curated references: 1", status.stdout)
            self.assertIn("KB objects: 0", status.stdout)
            self.assertIn("Reference KB status: invalid", status.stdout)
            self.assertIn("Current phase: references_curated", status.stdout)
            self.assertNotIn("Current phase: reference_kb_ready", status.stdout)

    def test_status_cli_rejects_malformed_reference_kb_nested_artifact_rows(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = create_project(ProjectSpec(topic="Group Theory", path=Path(temp_dir) / "p"))
            curated = project / "01_references" / "curated" / "normality.curated.md"
            curated.write_text(
                "# Chapter 3: Quotient Groups\n"
                "## Section 3.1 Normal Subgroups\n"
                "### Definition: Normal Subgroup\n"
                "A normal subgroup is stable under conjugation.\n"
                "Depends: subgroup, conjugation\n",
                encoding="utf-8",
                newline="\n",
            )
            build_reference_kb(project)
            (project / "06_kb" / "chapter_index.json").write_text(
                json.dumps(
                    {
                        "schema_version": 2,
                        "chapters": [
                            {
                                "title": "Chapter 3: Quotient Groups",
                                "sections": ["not an object"],
                            }
                        ],
                    },
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
                newline="\n",
            )

            status = subprocess.run(
                [sys.executable, "-m", "socrates", "status", "--project", str(project)],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(status.returncode, 0, status.stderr)
            self.assertIn("Curated references: 1", status.stdout)
            self.assertIn("KB objects: 0", status.stdout)
            self.assertIn("Reference KB status: invalid", status.stdout)
            self.assertIn("Current phase: references_curated", status.stdout)
            self.assertNotIn("Current phase: reference_kb_ready", status.stdout)

    def test_status_cli_rejects_reference_kb_chapter_index_missing_required_fields(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = create_project(ProjectSpec(topic="Group Theory", path=Path(temp_dir) / "p"))
            curated = project / "01_references" / "curated" / "normality.curated.md"
            curated.write_text(
                "# Chapter 3: Quotient Groups\n"
                "## Section 3.1 Normal Subgroups\n"
                "### Definition: Normal Subgroup\n"
                "A normal subgroup is stable under conjugation.\n"
                "Depends: subgroup, conjugation\n",
                encoding="utf-8",
                newline="\n",
            )
            build_reference_kb(project)
            chapter_index_path = project / "06_kb" / "chapter_index.json"
            chapter_index = json.loads(chapter_index_path.read_text(encoding="utf-8"))
            del chapter_index["chapters"][0]["sections"][0]["source_path"]
            chapter_index_path.write_text(
                json.dumps(chapter_index, indent=2) + "\n",
                encoding="utf-8",
                newline="\n",
            )

            status = subprocess.run(
                [sys.executable, "-m", "socrates", "status", "--project", str(project)],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(status.returncode, 0, status.stderr)
            self.assertIn("Curated references: 1", status.stdout)
            self.assertIn("KB objects: 0", status.stdout)
            self.assertIn("Reference KB status: invalid", status.stdout)
            self.assertIn("Current phase: references_curated", status.stdout)
            self.assertNotIn("Current phase: reference_kb_ready", status.stdout)

    def test_status_cli_rejects_reference_kb_chapter_index_missing_source_paths(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = create_project(ProjectSpec(topic="Group Theory", path=Path(temp_dir) / "p"))
            curated = project / "01_references" / "curated" / "normality.curated.md"
            curated.write_text(
                "# Chapter 3: Quotient Groups\n"
                "## Section 3.1 Normal Subgroups\n"
                "### Definition: Normal Subgroup\n"
                "A normal subgroup is stable under conjugation.\n"
                "Depends: subgroup, conjugation\n",
                encoding="utf-8",
                newline="\n",
            )
            build_reference_kb(project)
            chapter_index_path = project / "06_kb" / "chapter_index.json"
            chapter_index = json.loads(chapter_index_path.read_text(encoding="utf-8"))
            section = chapter_index["chapters"][0]["sections"][0]
            section["source_path"] = "01_references/curated/missing.curated.md"
            section["objects"][0]["source_path"] = "01_references/curated/missing.curated.md"
            chapter_index_path.write_text(
                json.dumps(chapter_index, indent=2) + "\n",
                encoding="utf-8",
                newline="\n",
            )

            status = subprocess.run(
                [sys.executable, "-m", "socrates", "status", "--project", str(project)],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(status.returncode, 0, status.stderr)
            self.assertIn("Curated references: 1", status.stdout)
            self.assertIn("KB objects: 0", status.stdout)
            self.assertIn("Reference KB status: invalid", status.stdout)
            self.assertIn("Current phase: references_curated", status.stdout)
            self.assertNotIn("Current phase: reference_kb_ready", status.stdout)

    def test_status_cli_rejects_reference_kb_chapter_index_non_curated_source_paths(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = create_project(ProjectSpec(topic="Group Theory", path=Path(temp_dir) / "p"))
            curated = project / "01_references" / "curated" / "normality.curated.md"
            curated.write_text(
                "# Chapter 3: Quotient Groups\n"
                "## Section 3.1 Normal Subgroups\n"
                "### Definition: Normal Subgroup\n"
                "A normal subgroup is stable under conjugation.\n"
                "Depends: subgroup, conjugation\n",
                encoding="utf-8",
                newline="\n",
            )
            build_reference_kb(project)
            chapter_index_path = project / "06_kb" / "chapter_index.json"
            chapter_index = json.loads(chapter_index_path.read_text(encoding="utf-8"))
            section = chapter_index["chapters"][0]["sections"][0]
            section["source_path"] = "README.md"
            section["objects"][0]["source_path"] = "README.md"
            chapter_index_path.write_text(
                json.dumps(chapter_index, indent=2) + "\n",
                encoding="utf-8",
                newline="\n",
            )

            status = subprocess.run(
                [sys.executable, "-m", "socrates", "status", "--project", str(project)],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(status.returncode, 0, status.stderr)
            self.assertIn("Curated references: 1", status.stdout)
            self.assertIn("KB objects: 0", status.stdout)
            self.assertIn("Reference KB status: invalid", status.stdout)
            self.assertIn("Current phase: references_curated", status.stdout)
            self.assertNotIn("Current phase: reference_kb_ready", status.stdout)

    def test_status_cli_rejects_reference_kb_theorem_index_non_curated_provenance(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = create_project(ProjectSpec(topic="Group Theory", path=Path(temp_dir) / "p"))
            curated = project / "01_references" / "curated" / "normality.curated.md"
            curated.write_text(
                "# Chapter 3: Quotient Groups\n"
                "## Section 3.1 Normal Subgroups\n"
                "### Theorem: Kernels are Normal\n"
                "The kernel of a homomorphism is a normal subgroup.\n"
                "Depends: kernel, homomorphism\n",
                encoding="utf-8",
                newline="\n",
            )
            build_reference_kb(project)
            theorem_index_path = project / "06_kb" / "theorem_index.json"
            theorem_index = json.loads(theorem_index_path.read_text(encoding="utf-8"))
            theorem_index["theorems"][0]["source"]["path"] = "README.md"
            theorem_index_path.write_text(
                json.dumps(theorem_index, indent=2) + "\n",
                encoding="utf-8",
                newline="\n",
            )

            status = subprocess.run(
                [sys.executable, "-m", "socrates", "status", "--project", str(project)],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(status.returncode, 0, status.stderr)
            self.assertIn("Curated references: 1", status.stdout)
            self.assertIn("KB objects: 0", status.stdout)
            self.assertIn("Reference KB status: invalid", status.stdout)
            self.assertIn("Current phase: references_curated", status.stdout)
            self.assertNotIn("Current phase: reference_kb_ready", status.stdout)

    def test_status_cli_rejects_reference_kb_exercise_index_fabricated_statement(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = create_project(ProjectSpec(topic="Group Theory", path=Path(temp_dir) / "p"))
            curated = project / "01_references" / "curated" / "normality.curated.md"
            curated.write_text(
                "# Chapter 3: Quotient Groups\n"
                "## Section 3.1 Normal Subgroups\n"
                "### Exercise: Prove Kernel Normality\n"
                "Prove that the kernel of a homomorphism is normal.\n"
                "Depends: kernel, normal subgroup\n",
                encoding="utf-8",
                newline="\n",
            )
            build_reference_kb(project)
            exercise_index_path = project / "06_kb" / "exercise_index.json"
            exercise_index = json.loads(exercise_index_path.read_text(encoding="utf-8"))
            exercise_index["exercises"][0]["statement"] = "Prove that every subgroup is normal."
            exercise_index_path.write_text(
                json.dumps(exercise_index, indent=2) + "\n",
                encoding="utf-8",
                newline="\n",
            )

            status = subprocess.run(
                [sys.executable, "-m", "socrates", "status", "--project", str(project)],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(status.returncode, 0, status.stderr)
            self.assertIn("Curated references: 1", status.stdout)
            self.assertIn("KB objects: 0", status.stdout)
            self.assertIn("Reference KB status: invalid", status.stdout)
            self.assertIn("Current phase: references_curated", status.stdout)
            self.assertNotIn("Current phase: reference_kb_ready", status.stdout)

    def test_status_phase_prefers_obsidian_export_pending_over_exported(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = create_project(ProjectSpec(topic="Group Theory", path=Path(temp_dir) / "p"))
            generate_atomic_note_draft(
                project,
                concept="Normal Subgroup",
                note_type="definition",
                body=(
                    "A normal subgroup is stable under conjugation; compare [[Subgroup]].\n\n"
                    "## Review Questions\n\n"
                    "- What condition distinguishes normality from centrality?\n"
                ),
                source_id="df",
            )
            review_atomic_note(project, "normal_subgroup")
            export_reviewed_notes_to_obsidian(project)
            generate_atomic_note_draft(
                project,
                concept="Quotient Group",
                note_type="definition",
                body=(
                    "A quotient group packages cosets of a [[Normal Subgroup]].\n\n"
                    "## Review Questions\n\n"
                    "- Why is normality needed for multiplication of cosets?\n"
                ),
                source_id="df",
            )
            review_atomic_note(project, "quotient_group")

            status = subprocess.run(
                [sys.executable, "-m", "socrates", "status", "--project", str(project)],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(status.returncode, 0, status.stderr)
            self.assertIn("Obsidian exports: 1", status.stdout)
            self.assertIn("Obsidian exports to run: 1", status.stdout)
            self.assertIn("Current phase: obsidian_export_pending", status.stdout)

    def test_status_phase_prefers_obsidian_export_pending_over_existing_reports(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = create_project(ProjectSpec(topic="Group Theory", path=Path(temp_dir) / "p"))
            generate_atomic_note_draft(
                project,
                concept="Normal Subgroup",
                note_type="definition",
                body=(
                    "A normal subgroup is stable under conjugation; compare [[Subgroup]].\n\n"
                    "## Review Questions\n\n"
                    "- What condition distinguishes normality from centrality?\n"
                ),
                source_id="df",
            )
            review_atomic_note(project, "normal_subgroup")
            export_reviewed_notes_to_obsidian(project)
            report = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "socrates",
                    "report",
                    "project-summary",
                    "--project",
                    str(project),
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            generate_atomic_note_draft(
                project,
                concept="Quotient Group",
                note_type="definition",
                body=(
                    "A quotient group packages cosets of a [[Normal Subgroup]].\n\n"
                    "## Review Questions\n\n"
                    "- Why is normality needed for multiplication of cosets?\n"
                ),
                source_id="df",
            )
            review_atomic_note(project, "quotient_group")

            status = subprocess.run(
                [sys.executable, "-m", "socrates", "status", "--project", str(project)],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(report.returncode, 0, report.stderr)
            self.assertEqual(status.returncode, 0, status.stderr)
            self.assertIn("Learning reports: 1", status.stdout)
            self.assertIn("Obsidian exports to run: 1", status.stdout)
            self.assertIn("Current phase: obsidian_export_pending", status.stdout)


def _project_file_snapshot(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


if __name__ == "__main__":
    unittest.main()

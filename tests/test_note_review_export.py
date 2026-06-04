from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from socrates.artifacts import generate_atomic_note_draft
from socrates.context import load_project
from socrates.kb import build_reference_kb
from socrates.notes import export_reviewed_notes_to_obsidian, review_atomic_note
from socrates.project import ProjectSpec, create_project
from socrates.state import LearningStatePatch, MistakeRecord, update_learning_state


REPO_ROOT = Path(__file__).resolve().parents[1]


class NoteReviewExportTests(unittest.TestCase):
    def test_review_atomic_note_promotes_draft_without_deleting_original(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = create_project(ProjectSpec(topic="Group Theory", path=Path(temp_dir) / "p"))
            generate_atomic_note_draft(
                project,
                concept="Normal Subgroup",
                note_type="definition",
                body=(
                    "A normal subgroup is stable under conjugation. See [[Subgroup]].\n\n"
                    "## Review Questions\n\n"
                    "- How is normality different from commutativity?\n"
                ),
                source_id="df",
                source_title="Dummit and Foote",
            )

            reviewed = review_atomic_note(project, "normal_subgroup")

            draft = project / "04_atomic_notes" / "drafts" / "normal_subgroup.md"
            self.assertTrue(draft.exists())
            self.assertEqual(reviewed, project / "04_atomic_notes" / "definitions" / "normal_subgroup.md")
            text = reviewed.read_text(encoding="utf-8")
            self.assertIn('status: "reviewed"', text)
            self.assertIn("reviewed_by_user: true", text)
            self.assertIn("[[Subgroup]]", text)

    def test_status_excludes_reviewed_notes_from_pending_drafts(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = create_project(ProjectSpec(topic="Group Theory", path=Path(temp_dir) / "p"))
            generate_atomic_note_draft(
                project,
                concept="Normal Subgroup",
                note_type="definition",
                body=(
                    "A normal subgroup is stable under conjugation; compare [[Subgroup]].\n\n"
                    "## Review Questions\n\n"
                    "- How is normality different from commutativity?\n"
                ),
                source_id="df",
            )
            review_atomic_note(project, "normal_subgroup")

            result = subprocess.run(
                [sys.executable, "-m", "socrates", "status", "--project", str(project)],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("Pending draft notes: 0", result.stdout)
            self.assertIn("Reviewed notes: 1", result.stdout)

    def test_note_draft_misconceptions_cli_creates_reviewable_obsidian_note(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = create_project(ProjectSpec(topic="Group Theory", path=Path(temp_dir) / "p"))
            context = load_project(project)
            update_learning_state(
                context,
                LearningStatePatch(
                    mistakes=[
                        MistakeRecord(
                            session_id="session-001",
                            concept="normal_subgroup",
                            misconception_id="normal_equals_central",
                            user_answer="Normal means central.",
                            analysis="Confuses normality with centrality.",
                            repair_suggestion="Compare gNg^-1 = N with gn = ng.",
                            follow_up_exercises=["Find a non-central normal subgroup."],
                        )
                    ],
                ),
            )

            draft_result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "socrates",
                    "note",
                    "draft-misconceptions",
                    "--project",
                    str(project),
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(draft_result.returncode, 0, draft_result.stderr)
            self.assertIn("Drafted 1 misconception note", draft_result.stdout)
            draft = project / "04_atomic_notes" / "drafts" / "normal_equals_central.md"
            self.assertTrue(draft.exists())
            draft_text = draft.read_text(encoding="utf-8")
            self.assertIn('type: "misconception"', draft_text)
            self.assertIn('source_id: "learning_state"', draft_text)
            self.assertIn("[[Normal Subgroup]]", draft_text)
            self.assertIn("Compare gNg^-1 = N with gn = ng.", draft_text)

            review_result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "socrates",
                    "note",
                    "review",
                    "--project",
                    str(project),
                    "--note",
                    "normal_equals_central",
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            export_result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "socrates",
                    "note",
                    "export-obsidian",
                    "--project",
                    str(project),
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            reviewed = project / "04_atomic_notes" / "misconceptions" / "normal_equals_central.md"
            self.assertEqual(review_result.returncode, 0, review_result.stderr)
            self.assertTrue(reviewed.exists())
            self.assertEqual(export_result.returncode, 0, export_result.stderr)
            manifest = json.loads(
                (project / "07_exports" / "obsidian" / "export_manifest.json").read_text(
                    encoding="utf-8"
                )
            )
            exported_note = manifest["exported_notes"][0]
            self.assertEqual(exported_note["note_id"], "normal_equals_central")
            self.assertEqual(exported_note["type"], "misconception")
            self.assertEqual(exported_note["concept"], "normal_equals_central")

    def test_note_draft_misconceptions_cli_does_not_overwrite_existing_drafts(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = create_project(ProjectSpec(topic="Group Theory", path=Path(temp_dir) / "p"))
            context = load_project(project)
            update_learning_state(
                context,
                LearningStatePatch(
                    mistakes=[
                        MistakeRecord(
                            session_id="session-001",
                            concept="normal_subgroup",
                            misconception_id="normal_equals_central",
                            user_answer="Normal means central.",
                            analysis="Confuses normality with centrality.",
                            repair_suggestion="Compare gNg^-1 = N with gn = ng.",
                        )
                    ],
                ),
            )
            first_result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "socrates",
                    "note",
                    "draft-misconceptions",
                    "--project",
                    str(project),
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            draft = project / "04_atomic_notes" / "drafts" / "normal_equals_central.md"
            draft.write_text(
                draft.read_text(encoding="utf-8").rstrip()
                + "\n\nReviewer note: keep this manual edit.\n",
                encoding="utf-8",
                newline="\n",
            )

            second_result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "socrates",
                    "note",
                    "draft-misconceptions",
                    "--project",
                    str(project),
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(first_result.returncode, 0, first_result.stderr)
            self.assertIn("Drafted 1 misconception note", first_result.stdout)
            self.assertEqual(second_result.returncode, 0, second_result.stderr)
            self.assertIn("Drafted 0 misconception notes", second_result.stdout)
            self.assertIn(
                "Reviewer note: keep this manual edit.",
                draft.read_text(encoding="utf-8"),
            )

    def test_review_atomic_note_rejects_failed_quality_gate(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = create_project(ProjectSpec(topic="Group Theory", path=Path(temp_dir) / "p"))
            draft = project / "04_atomic_notes" / "drafts" / "bad_note.md"
            draft.write_text(
                "---\n"
                "status: draft\n"
                "review_status: needs_review\n"
                "reviewed_by_user: false\n"
                "type: definition\n"
                "concept: Bad Note\n"
                "source_id: df\n"
                "tags:\n"
                "  - bad-note\n"
                "related:\n"
                "  []\n"
                "---\n\n"
                "# Bad Note\n\n"
                "This draft is missing review questions.\n",
                encoding="utf-8",
                newline="\n",
            )

            with self.assertRaisesRegex(ValueError, "failed quality gate"):
                review_atomic_note(project, "bad_note")

            reviewed = project / "04_atomic_notes" / "definitions" / "bad_note.md"
            self.assertFalse(reviewed.exists())

    def test_export_reviewed_notes_to_obsidian_copies_only_reviewed_notes(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = create_project(ProjectSpec(topic="Group Theory", path=Path(temp_dir) / "p"))
            curated = project / "01_references" / "curated" / "normal_subgroups.curated.md"
            curated.write_text(
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
                    "A normal subgroup is stable under conjugation; compare [[Subgroup]].\n\n"
                    "## Review Questions\n\n"
                    "- What conjugation condition must be checked?\n"
                ),
                source_id="df",
                source_title="Dummit and Foote",
                source_location="Section 3.1",
            )
            review_atomic_note(project, "normal_subgroup")

            exported = export_reviewed_notes_to_obsidian(project)

            self.assertEqual(exported, [project / "07_exports" / "obsidian" / "normal_subgroup.md"])
            export_text = exported[0].read_text(encoding="utf-8")
            self.assertIn('status: "reviewed"', export_text)
            self.assertIn("reviewed_by_user: true", export_text)
            self.assertIn("# Normal Subgroup", export_text)
            export_index = project / "07_exports" / "obsidian" / "_socrates_index.md"
            self.assertTrue(export_index.exists())
            export_index_text = export_index.read_text(encoding="utf-8")
            self.assertIn("# Socrates Obsidian Export", export_index_text)
            self.assertIn("## Definition", export_index_text)
            self.assertIn("- [[normal_subgroup|Normal Subgroup]]", export_index_text)
            self.assertIn("  - Source: Dummit and Foote, Section 3.1", export_index_text)
            self.assertIn(
                "  - Tags: #definition #normal-subgroup #subgroup #conjugation",
                export_index_text,
            )
            self.assertIn("  - Related: [[Subgroup]], [[Conjugation]]", export_index_text)
            manifest = json.loads(
                (project / "07_exports" / "obsidian" / "export_manifest.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(manifest["version"], 3)
            self.assertEqual(
                manifest["exported_notes"],
                [
                    {
                        "note_id": "normal_subgroup",
                        "concept": "Normal Subgroup",
                        "type": "definition",
                        "topic": "group_theory",
                        "created_by": "socrates",
                        "path": "normal_subgroup.md",
                        "review_status": "approved",
                        "source_id": "df",
                        "source_title": "Dummit and Foote",
                        "source_location": "Section 3.1",
                        "tags": ["definition", "normal-subgroup", "subgroup", "conjugation"],
                        "related": ["[[Subgroup]]", "[[Conjugation]]"],
                        "backlinks": [],
                    }
                ],
            )

    def test_export_reviewed_notes_to_obsidian_adds_backlink_section(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = create_project(ProjectSpec(topic="Group Theory", path=Path(temp_dir) / "p"))
            curated = project / "01_references" / "curated" / "quotients.curated.md"
            curated.write_text(
                "### Definition: Normal Subgroup\n"
                "A normal subgroup is stable under conjugation.\n"
                "Depends: subgroup\n\n"
                "### Definition: Quotient Group\n"
                "A quotient group uses cosets of a normal subgroup.\n"
                "Depends: normal_subgroup\n",
                encoding="utf-8",
                newline="\n",
            )
            build_reference_kb(project)
            generate_atomic_note_draft(
                project,
                concept="Normal Subgroup",
                note_type="definition",
                body=(
                    "A normal subgroup is stable under conjugation; compare [[Subgroup]].\n\n"
                    "## Review Questions\n\n"
                    "- What conjugation condition must be checked?\n"
                ),
                source_id="df",
            )
            generate_atomic_note_draft(
                project,
                concept="Quotient Group",
                note_type="definition",
                body=(
                    "A quotient group packages cosets of a [[Normal Subgroup]].\n\n"
                    "## Review Questions\n\n"
                    "- Why is normality required for multiplication of cosets?\n"
                ),
                source_id="df",
            )
            review_atomic_note(project, "normal_subgroup")
            review_atomic_note(project, "quotient_group")

            export_reviewed_notes_to_obsidian(project)

            normal_note = project / "07_exports" / "obsidian" / "normal_subgroup.md"
            quotient_note = project / "07_exports" / "obsidian" / "quotient_group.md"
            normal_text = normal_note.read_text(encoding="utf-8")
            quotient_text = quotient_note.read_text(encoding="utf-8")
            self.assertIn("## Socrates Backlinks", normal_text)
            self.assertIn("- [[quotient_group|Quotient Group]]", normal_text)
            self.assertNotIn("## Socrates Backlinks", quotient_text)
            manifest = json.loads(
                (project / "07_exports" / "obsidian" / "export_manifest.json").read_text(
                    encoding="utf-8"
                )
            )
            notes_by_id = {item["note_id"]: item for item in manifest["exported_notes"]}
            self.assertEqual(manifest["version"], 3)
            self.assertEqual(
                notes_by_id["normal_subgroup"]["backlinks"],
                [
                    {
                        "note_id": "quotient_group",
                        "concept": "Quotient Group",
                        "path": "quotient_group.md",
                    }
                ],
            )
            self.assertEqual(notes_by_id["quotient_group"]["backlinks"], [])

    def test_export_reviewed_notes_to_obsidian_uses_body_wikilinks_for_backlinks(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = create_project(ProjectSpec(topic="Group Theory", path=Path(temp_dir) / "p"))
            definitions = project / "04_atomic_notes" / "definitions"
            normal_note = definitions / "normal_subgroup.md"
            quotient_note = definitions / "quotient_group.md"
            normal_note.write_text(
                "---\n"
                "status: reviewed\n"
                "review_status: approved\n"
                "reviewed_by_user: true\n"
                "type: definition\n"
                "topic: group_theory\n"
                "concept: Normal Subgroup\n"
                "created_by: socrates\n"
                "source_id: df\n"
                "tags:\n"
                "  - normal-subgroup\n"
                "related: [[Subgroup]]\n"
                "---\n\n"
                "# Normal Subgroup\n\n"
                "A normal subgroup is stable under conjugation.\n\n"
                "## Key Examples\n\n"
                "- A3 in S3.\n\n"
                "## Non-Examples\n\n"
                "- A transposition subgroup in S3.\n\n"
                "## Common Mistakes\n\n"
                "- Confusing normal with central.\n\n"
                "## Review Questions\n\n"
                "- What conjugation condition must be checked?\n",
                encoding="utf-8",
                newline="\n",
            )
            quotient_note.write_text(
                "---\n"
                "status: reviewed\n"
                "review_status: approved\n"
                "reviewed_by_user: true\n"
                "type: definition\n"
                "topic: group_theory\n"
                "concept: Quotient Group\n"
                "created_by: socrates\n"
                "source_id: df\n"
                "tags:\n"
                "  - quotient-group\n"
                "related: [[Subgroup]]\n"
                "---\n\n"
                "# Quotient Group\n\n"
                "A quotient group is built from cosets of a [[Normal Subgroup]].\n\n"
                "## Key Examples\n\n"
                "- Z / nZ.\n\n"
                "## Non-Examples\n\n"
                "- Cosets of a non-normal subgroup do not form a group.\n\n"
                "## Common Mistakes\n\n"
                "- Forgetting well-defined multiplication.\n\n"
                "## Review Questions\n\n"
                "- Why is normality required?\n",
                encoding="utf-8",
                newline="\n",
            )

            export_reviewed_notes_to_obsidian(project)

            exported_normal = project / "07_exports" / "obsidian" / "normal_subgroup.md"
            normal_text = exported_normal.read_text(encoding="utf-8")
            manifest = json.loads(
                (project / "07_exports" / "obsidian" / "export_manifest.json").read_text(
                    encoding="utf-8"
                )
            )
            notes_by_id = {item["note_id"]: item for item in manifest["exported_notes"]}
            self.assertIn("## Socrates Backlinks", normal_text)
            self.assertIn("- [[quotient_group|Quotient Group]]", normal_text)
            self.assertEqual(
                notes_by_id["normal_subgroup"]["backlinks"],
                [
                    {
                        "note_id": "quotient_group",
                        "concept": "Quotient Group",
                        "path": "quotient_group.md",
                    }
                ],
            )

    def test_export_reviewed_notes_to_obsidian_prunes_stale_manifest_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = create_project(ProjectSpec(topic="Group Theory", path=Path(temp_dir) / "p"))
            generate_atomic_note_draft(
                project,
                concept="Normal Subgroup",
                note_type="definition",
                body=(
                    "A normal subgroup is stable under conjugation; compare [[Subgroup]].\n\n"
                    "## Review Questions\n\n"
                    "- What conjugation condition must be checked?\n"
                ),
                source_id="df",
            )
            generate_atomic_note_draft(
                project,
                concept="Quotient Group",
                note_type="definition",
                body=(
                    "A quotient group packages cosets of a [[Normal Subgroup]].\n\n"
                    "## Review Questions\n\n"
                    "- Why is normality required for multiplication of cosets?\n"
                ),
                source_id="df",
            )
            normal_reviewed = review_atomic_note(project, "normal_subgroup")
            quotient_reviewed = review_atomic_note(project, "quotient_group")
            export_reviewed_notes_to_obsidian(project)
            obsidian_dir = project / "07_exports" / "obsidian"
            manual_note = obsidian_dir / "manual_note.md"
            manual_note.write_text(
                "# Manual Note\n\nThis file was not written by Socrates.\n",
                encoding="utf-8",
                newline="\n",
            )

            quotient_reviewed.unlink()
            exported = export_reviewed_notes_to_obsidian(project)

            self.assertEqual(exported, [obsidian_dir / "normal_subgroup.md"])
            self.assertTrue(normal_reviewed.exists())
            self.assertTrue(manual_note.exists())
            self.assertTrue((obsidian_dir / "normal_subgroup.md").exists())
            self.assertFalse((obsidian_dir / "quotient_group.md").exists())
            manifest = json.loads((obsidian_dir / "export_manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(
                [note["note_id"] for note in manifest["exported_notes"]],
                ["normal_subgroup"],
            )
            export_index_text = (obsidian_dir / "_socrates_index.md").read_text(encoding="utf-8")
            self.assertIn("- [[normal_subgroup|Normal Subgroup]]", export_index_text)
            self.assertNotIn("quotient_group", export_index_text)

    def test_export_reviewed_notes_to_obsidian_refreshes_empty_export_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = create_project(ProjectSpec(topic="Group Theory", path=Path(temp_dir) / "p"))
            generate_atomic_note_draft(
                project,
                concept="Normal Subgroup",
                note_type="definition",
                body=(
                    "A normal subgroup is stable under conjugation; compare [[Subgroup]].\n\n"
                    "## Review Questions\n\n"
                    "- What conjugation condition must be checked?\n"
                ),
                source_id="df",
            )
            reviewed = review_atomic_note(project, "normal_subgroup")
            export_reviewed_notes_to_obsidian(project)
            obsidian_dir = project / "07_exports" / "obsidian"

            reviewed.unlink()
            exported = export_reviewed_notes_to_obsidian(project)

            self.assertEqual(exported, [])
            self.assertFalse((obsidian_dir / "normal_subgroup.md").exists())
            manifest = json.loads((obsidian_dir / "export_manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["version"], 3)
            self.assertEqual(manifest["exported_notes"], [])
            export_index_text = (obsidian_dir / "_socrates_index.md").read_text(encoding="utf-8")
            self.assertIn("# Socrates Obsidian Export", export_index_text)
            self.assertIn("No reviewed notes exported.", export_index_text)

    def test_status_cli_counts_obsidian_manifest_backlinks(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = create_project(ProjectSpec(topic="Group Theory", path=Path(temp_dir) / "p"))
            curated = project / "01_references" / "curated" / "normality.curated.md"
            curated.write_text(
                "### Definition: Normal Subgroup\n"
                "A normal subgroup is stable under conjugation.\n"
                "Depends: subgroup\n\n"
                "### Definition: Quotient Group\n"
                "A quotient group uses cosets of a normal subgroup.\n"
                "Depends: normal_subgroup\n",
                encoding="utf-8",
                newline="\n",
            )
            build_reference_kb(project)
            generate_atomic_note_draft(
                project,
                concept="Normal Subgroup",
                note_type="definition",
                body=(
                    "A normal subgroup is stable under conjugation; compare [[Subgroup]].\n\n"
                    "## Review Questions\n\n"
                    "- What conjugation condition must be checked?\n"
                ),
                source_id="df",
            )
            generate_atomic_note_draft(
                project,
                concept="Quotient Group",
                note_type="definition",
                body=(
                    "A quotient group packages cosets of a normal subgroup.\n\n"
                    "## Review Questions\n\n"
                    "- Why is normality required for multiplication of cosets?\n"
                ),
                source_id="df",
            )
            review_atomic_note(project, "normal_subgroup")
            review_atomic_note(project, "quotient_group")
            export_reviewed_notes_to_obsidian(project)

            result = subprocess.run(
                [sys.executable, "-m", "socrates", "status", "--project", str(project)],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("Obsidian exports: 2", result.stdout)
            self.assertIn("Obsidian backlinks: 1", result.stdout)

    def test_note_list_cli_shows_pending_reviewed_and_exported_notes(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = create_project(ProjectSpec(topic="Group Theory", path=Path(temp_dir) / "p"))
            generate_atomic_note_draft(
                project,
                concept="Normal Subgroup",
                note_type="definition",
                body=(
                    "A normal subgroup is stable under conjugation; compare [[Subgroup]].\n\n"
                    "## Review Questions\n\n"
                    "- What conjugation condition must be checked?\n"
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
                    "A quotient group packages cosets using a [[Normal Subgroup]].\n\n"
                    "## Review Questions\n\n"
                    "- Why must the subgroup be normal?\n"
                ),
                source_id="df",
            )
            review_atomic_note(project, "quotient_group")
            generate_atomic_note_draft(
                project,
                concept="Group Action",
                note_type="example",
                body=(
                    "A group action sends each group element to a permutation.\n\n"
                    "## Review Questions\n\n"
                    "- What compatibility law must be checked?\n"
                ),
                source_id="df",
            )

            all_notes = subprocess.run(
                [sys.executable, "-m", "socrates", "note", "list", "--project", str(project)],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            pending_notes = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "socrates",
                    "note",
                    "list",
                    "--project",
                    str(project),
                    "--status",
                    "pending",
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            exported_notes = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "socrates",
                    "note",
                    "list",
                    "--project",
                    str(project),
                    "--status",
                    "exported",
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(all_notes.returncode, 0, all_notes.stderr)
            self.assertIn("# Atomic Notes", all_notes.stdout)
            pending = "- group_action | pending | example | Group Action | 04_atomic_notes/drafts/group_action.md"
            reviewed = (
                "- quotient_group | reviewed | definition | Quotient Group | "
                "04_atomic_notes/definitions/quotient_group.md"
            )
            exported = (
                "- normal_subgroup | exported | definition | Normal Subgroup | "
                "04_atomic_notes/definitions/normal_subgroup.md"
            )
            self.assertIn(pending, all_notes.stdout)
            self.assertIn(reviewed, all_notes.stdout)
            self.assertIn(exported, all_notes.stdout)
            self.assertLess(all_notes.stdout.index(pending), all_notes.stdout.index(reviewed))
            self.assertLess(all_notes.stdout.index(reviewed), all_notes.stdout.index(exported))

            self.assertEqual(pending_notes.returncode, 0, pending_notes.stderr)
            self.assertIn(pending, pending_notes.stdout)
            self.assertNotIn("quotient_group", pending_notes.stdout)
            self.assertNotIn("normal_subgroup", pending_notes.stdout)

            self.assertEqual(exported_notes.returncode, 0, exported_notes.stderr)
            self.assertIn(exported, exported_notes.stdout)
            self.assertNotIn("group_action", exported_notes.stdout)
            self.assertNotIn("quotient_group", exported_notes.stdout)

    def test_note_list_cli_falls_back_when_obsidian_manifest_is_corrupt(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = create_project(ProjectSpec(topic="Group Theory", path=Path(temp_dir) / "p"))
            generate_atomic_note_draft(
                project,
                concept="Normal Subgroup",
                note_type="definition",
                body=(
                    "A normal subgroup is stable under conjugation; compare [[Subgroup]].\n\n"
                    "## Review Questions\n\n"
                    "- What conjugation condition must be checked?\n"
                ),
                source_id="df",
            )
            review_atomic_note(project, "normal_subgroup")
            export_reviewed_notes_to_obsidian(project)
            (project / "07_exports" / "obsidian" / "export_manifest.json").write_text(
                "{not valid json\n",
                encoding="utf-8",
                newline="\n",
            )

            exported_notes = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "socrates",
                    "note",
                    "list",
                    "--project",
                    str(project),
                    "--status",
                    "exported",
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(exported_notes.returncode, 0, exported_notes.stderr)
            self.assertIn(
                "- normal_subgroup | exported | definition | Normal Subgroup | "
                "04_atomic_notes/definitions/normal_subgroup.md",
                exported_notes.stdout,
            )

    def test_status_cli_falls_back_when_obsidian_manifest_is_corrupt(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = create_project(ProjectSpec(topic="Group Theory", path=Path(temp_dir) / "p"))
            generate_atomic_note_draft(
                project,
                concept="Normal Subgroup",
                note_type="definition",
                body=(
                    "A normal subgroup is stable under conjugation; compare [[Subgroup]].\n\n"
                    "## Review Questions\n\n"
                    "- What conjugation condition must be checked?\n"
                ),
                source_id="df",
            )
            review_atomic_note(project, "normal_subgroup")
            export_reviewed_notes_to_obsidian(project)
            (project / "07_exports" / "obsidian" / "export_manifest.json").write_text(
                "{not valid json\n",
                encoding="utf-8",
                newline="\n",
            )

            result = subprocess.run(
                [sys.executable, "-m", "socrates", "status", "--project", str(project)],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("Obsidian exports: 1", result.stdout)
            self.assertIn("Obsidian backlinks: 0", result.stdout)

    def test_export_reviewed_notes_rejects_failed_quality_gate(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = create_project(ProjectSpec(topic="Group Theory", path=Path(temp_dir) / "p"))
            reviewed = project / "04_atomic_notes" / "definitions" / "legacy_bad_note.md"
            reviewed.write_text(
                "---\n"
                "status: reviewed\n"
                "review_status: approved\n"
                "reviewed_by_user: true\n"
                "type: definition\n"
                "concept: Legacy Bad Note\n"
                "source_id: df\n"
                "tags:\n"
                "  - legacy-bad-note\n"
                "related:\n"
                "  []\n"
                "---\n\n"
                "# Legacy Bad Note\n\n"
                "This legacy reviewed note is missing review questions.\n",
                encoding="utf-8",
                newline="\n",
            )

            with self.assertRaisesRegex(ValueError, "failed quality gate"):
                export_reviewed_notes_to_obsidian(project)

            exported = project / "07_exports" / "obsidian" / "legacy_bad_note.md"
            self.assertFalse(exported.exists())
            report = project / "08_evals" / "note_quality_eval.md"
            self.assertIn("definitions/legacy_bad_note.md: fail", report.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()

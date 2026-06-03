from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from socrates.artifacts import generate_atomic_note_draft
from socrates.kb import build_reference_kb
from socrates.project import ProjectSpec, create_project


REPO_ROOT = Path(__file__).resolve().parents[1]


class NoteQualityTests(unittest.TestCase):
    def test_note_quality_requires_nonempty_title_heading(self) -> None:
        from socrates.quality import atomic_note_quality_issues

        with tempfile.TemporaryDirectory() as temp_dir:
            project = create_project(ProjectSpec(topic="Group Theory", path=Path(temp_dir) / "p"))
            note = project / "04_atomic_notes" / "drafts" / "empty_title.md"
            note.write_text(
                "---\n"
                "status: draft\n"
                "review_status: needs_review\n"
                "reviewed_by_user: false\n"
                "type: definition\n"
                "concept: Normal Subgroup\n"
                "source_id: df\n"
                "tags:\n"
                "  - normal-subgroup\n"
                "related:\n"
                "  - \"[[Subgroup]]\"\n"
                "---\n\n"
                "# \n\n"
                "A normal subgroup is stable under conjugation.\n\n"
                "## Key Examples\n\n"
                "- Kernels of homomorphisms.\n\n"
                "## Non-Examples\n\n"
                "- A non-normal subgroup of S3.\n\n"
                "## Common Mistakes\n\n"
                "- Confusing normality with centrality.\n\n"
                "## Review Questions\n\n"
                "- How is normality different from commutativity?\n",
                encoding="utf-8",
                newline="\n",
            )

            issues = atomic_note_quality_issues(note, project)

            self.assertIn("missing title heading", issues)

    def test_note_quality_requires_example_non_example_and_mistake_sections(self) -> None:
        from socrates.quality import atomic_note_quality_issues

        with tempfile.TemporaryDirectory() as temp_dir:
            project = create_project(ProjectSpec(topic="Group Theory", path=Path(temp_dir) / "p"))
            note = project / "04_atomic_notes" / "drafts" / "thin_note.md"
            note.write_text(
                "---\n"
                "status: draft\n"
                "review_status: needs_review\n"
                "reviewed_by_user: false\n"
                "type: definition\n"
                "concept: Normal Subgroup\n"
                "source_id: df\n"
                "tags:\n"
                "  - normal-subgroup\n"
                "related:\n"
                "  []\n"
                "---\n\n"
                "# Normal Subgroup\n\n"
                "A normal subgroup is stable under conjugation.\n\n"
                "## Review Questions\n\n"
                "- How is normality different from centrality?\n",
                encoding="utf-8",
                newline="\n",
            )

            issues = atomic_note_quality_issues(note, project)

            self.assertIn("missing section Key Examples", issues)
            self.assertIn("missing section Non-Examples", issues)
            self.assertIn("missing section Common Mistakes", issues)

    def test_note_quality_requires_at_least_one_review_question(self) -> None:
        from socrates.quality import atomic_note_quality_issues

        with tempfile.TemporaryDirectory() as temp_dir:
            project = create_project(ProjectSpec(topic="Group Theory", path=Path(temp_dir) / "p"))
            note = project / "04_atomic_notes" / "drafts" / "empty_review.md"
            note.write_text(
                "---\n"
                "status: draft\n"
                "review_status: needs_review\n"
                "reviewed_by_user: false\n"
                "type: definition\n"
                "concept: Normal Subgroup\n"
                "source_id: df\n"
                "tags:\n"
                "  - normal-subgroup\n"
                "related:\n"
                "  - subgroup\n"
                "---\n\n"
                "# Normal Subgroup\n\n"
                "A normal subgroup is stable under conjugation.\n\n"
                "## Key Examples\n\n"
                "- Kernels of homomorphisms.\n\n"
                "## Non-Examples\n\n"
                "- A non-normal subgroup of S3.\n\n"
                "## Common Mistakes\n\n"
                "- Confusing normality with centrality.\n\n"
                "## Review Questions\n\n",
                encoding="utf-8",
                newline="\n",
            )

            issues = atomic_note_quality_issues(note, project)

            self.assertIn("missing review questions", issues)

    def test_note_quality_requires_related_concept_links(self) -> None:
        from socrates.quality import atomic_note_quality_issues

        with tempfile.TemporaryDirectory() as temp_dir:
            project = create_project(ProjectSpec(topic="Group Theory", path=Path(temp_dir) / "p"))
            note = project / "04_atomic_notes" / "drafts" / "isolated_note.md"
            note.write_text(
                "---\n"
                "status: draft\n"
                "review_status: needs_review\n"
                "reviewed_by_user: false\n"
                "type: definition\n"
                "concept: Normal Subgroup\n"
                "source_id: df\n"
                "tags:\n"
                "  - normal-subgroup\n"
                "related:\n"
                "  []\n"
                "---\n\n"
                "# Normal Subgroup\n\n"
                "A normal subgroup is stable under conjugation.\n\n"
                "## Key Examples\n\n"
                "- Kernels of homomorphisms.\n\n"
                "## Non-Examples\n\n"
                "- A non-normal subgroup of S3.\n\n"
                "## Common Mistakes\n\n"
                "- Confusing normality with centrality.\n\n"
                "## Review Questions\n\n"
                "- How is normality different from commutativity?\n\n"
                "## Related Concepts\n\n",
                encoding="utf-8",
                newline="\n",
            )

            issues = atomic_note_quality_issues(note, project)

            self.assertIn("missing related concept links", issues)

    def test_note_quality_requires_nonempty_tags(self) -> None:
        from socrates.quality import atomic_note_quality_issues

        with tempfile.TemporaryDirectory() as temp_dir:
            project = create_project(ProjectSpec(topic="Group Theory", path=Path(temp_dir) / "p"))
            note = project / "04_atomic_notes" / "drafts" / "untagged_note.md"
            note.write_text(
                "---\n"
                "status: draft\n"
                "review_status: needs_review\n"
                "reviewed_by_user: false\n"
                "type: definition\n"
                "concept: Normal Subgroup\n"
                "source_id: df\n"
                "tags:\n"
                "related:\n"
                "  - \"[[Subgroup]]\"\n"
                "---\n\n"
                "# Normal Subgroup\n\n"
                "A normal subgroup is stable under conjugation.\n\n"
                "## Key Examples\n\n"
                "- Kernels of homomorphisms.\n\n"
                "## Non-Examples\n\n"
                "- A non-normal subgroup of S3.\n\n"
                "## Common Mistakes\n\n"
                "- Confusing normality with centrality.\n\n"
                "## Review Questions\n\n"
                "- How is normality different from commutativity?\n",
                encoding="utf-8",
                newline="\n",
            )

            issues = atomic_note_quality_issues(note, project)

            self.assertIn("missing tags", issues)

    def test_note_quality_requires_related_wikilinks(self) -> None:
        from socrates.quality import atomic_note_quality_issues

        with tempfile.TemporaryDirectory() as temp_dir:
            project = create_project(ProjectSpec(topic="Group Theory", path=Path(temp_dir) / "p"))
            note = project / "04_atomic_notes" / "drafts" / "plain_related_note.md"
            note.write_text(
                "---\n"
                "status: draft\n"
                "review_status: needs_review\n"
                "reviewed_by_user: false\n"
                "type: definition\n"
                "concept: Normal Subgroup\n"
                "source_id: df\n"
                "tags:\n"
                "  - normal-subgroup\n"
                "related:\n"
                "  - subgroup\n"
                "---\n\n"
                "# Normal Subgroup\n\n"
                "A normal subgroup is stable under conjugation.\n\n"
                "## Key Examples\n\n"
                "- Kernels of homomorphisms.\n\n"
                "## Non-Examples\n\n"
                "- A non-normal subgroup of S3.\n\n"
                "## Common Mistakes\n\n"
                "- Confusing normality with centrality.\n\n"
                "## Review Questions\n\n"
                "- How is normality different from commutativity?\n",
                encoding="utf-8",
                newline="\n",
            )

            issues = atomic_note_quality_issues(note, project)

            self.assertIn("missing related concept links", issues)

    def test_note_quality_requires_nonempty_source_id(self) -> None:
        from socrates.quality import atomic_note_quality_issues

        with tempfile.TemporaryDirectory() as temp_dir:
            project = create_project(ProjectSpec(topic="Group Theory", path=Path(temp_dir) / "p"))
            note = project / "04_atomic_notes" / "drafts" / "missing_source_note.md"
            note.write_text(
                "---\n"
                "status: draft\n"
                "review_status: needs_review\n"
                "reviewed_by_user: false\n"
                "type: definition\n"
                "concept: Normal Subgroup\n"
                "source_id:\n"
                "tags:\n"
                "  - normal-subgroup\n"
                "related:\n"
                "  - \"[[Subgroup]]\"\n"
                "---\n\n"
                "# Normal Subgroup\n\n"
                "A normal subgroup is stable under conjugation.\n\n"
                "## Key Examples\n\n"
                "- Kernels of homomorphisms.\n\n"
                "## Non-Examples\n\n"
                "- A non-normal subgroup of S3.\n\n"
                "## Common Mistakes\n\n"
                "- Confusing normality with centrality.\n\n"
                "## Review Questions\n\n"
                "- How is normality different from commutativity?\n",
                encoding="utf-8",
                newline="\n",
            )

            issues = atomic_note_quality_issues(note, project)

            self.assertIn("missing source id", issues)

    def test_note_quality_requires_nonempty_concept(self) -> None:
        from socrates.quality import atomic_note_quality_issues

        with tempfile.TemporaryDirectory() as temp_dir:
            project = create_project(ProjectSpec(topic="Group Theory", path=Path(temp_dir) / "p"))
            note = project / "04_atomic_notes" / "drafts" / "missing_concept_note.md"
            note.write_text(
                "---\n"
                "status: draft\n"
                "review_status: needs_review\n"
                "reviewed_by_user: false\n"
                "type: definition\n"
                "concept:\n"
                "source_id: df\n"
                "tags:\n"
                "  - normal-subgroup\n"
                "related:\n"
                "  - \"[[Subgroup]]\"\n"
                "---\n\n"
                "# Normal Subgroup\n\n"
                "A normal subgroup is stable under conjugation.\n\n"
                "## Key Examples\n\n"
                "- Kernels of homomorphisms.\n\n"
                "## Non-Examples\n\n"
                "- A non-normal subgroup of S3.\n\n"
                "## Common Mistakes\n\n"
                "- Confusing normality with centrality.\n\n"
                "## Review Questions\n\n"
                "- How is normality different from commutativity?\n",
                encoding="utf-8",
                newline="\n",
            )

            issues = atomic_note_quality_issues(note, project)

            self.assertIn("missing concept", issues)

    def test_note_quality_requires_boolean_reviewed_by_user(self) -> None:
        from socrates.quality import atomic_note_quality_issues

        with tempfile.TemporaryDirectory() as temp_dir:
            project = create_project(ProjectSpec(topic="Group Theory", path=Path(temp_dir) / "p"))
            note = project / "04_atomic_notes" / "drafts" / "invalid_review_flag.md"
            note.write_text(
                "---\n"
                "status: draft\n"
                "review_status: needs_review\n"
                "reviewed_by_user: maybe\n"
                "type: definition\n"
                "concept: Normal Subgroup\n"
                "source_id: df\n"
                "tags:\n"
                "  - normal-subgroup\n"
                "related:\n"
                "  - \"[[Subgroup]]\"\n"
                "---\n\n"
                "# Normal Subgroup\n\n"
                "A normal subgroup is stable under conjugation.\n\n"
                "## Key Examples\n\n"
                "- Kernels of homomorphisms.\n\n"
                "## Non-Examples\n\n"
                "- A non-normal subgroup of S3.\n\n"
                "## Common Mistakes\n\n"
                "- Confusing normality with centrality.\n\n"
                "## Review Questions\n\n"
                "- How is normality different from commutativity?\n",
                encoding="utf-8",
                newline="\n",
            )

            issues = atomic_note_quality_issues(note, project)

            self.assertIn("invalid reviewed_by_user", issues)

    def test_note_quality_rejects_invalid_status(self) -> None:
        from socrates.quality import atomic_note_quality_issues

        with tempfile.TemporaryDirectory() as temp_dir:
            project = create_project(ProjectSpec(topic="Group Theory", path=Path(temp_dir) / "p"))
            note = project / "04_atomic_notes" / "drafts" / "invalid_status.md"
            note.write_text(
                "---\n"
                "status: archived\n"
                "review_status: needs_review\n"
                "reviewed_by_user: false\n"
                "type: definition\n"
                "concept: Normal Subgroup\n"
                "source_id: df\n"
                "tags:\n"
                "  - normal-subgroup\n"
                "related:\n"
                "  - \"[[Subgroup]]\"\n"
                "---\n\n"
                "# Normal Subgroup\n\n"
                "A normal subgroup is stable under conjugation.\n\n"
                "## Key Examples\n\n"
                "- Kernels of homomorphisms.\n\n"
                "## Non-Examples\n\n"
                "- A non-normal subgroup of S3.\n\n"
                "## Common Mistakes\n\n"
                "- Confusing normality with centrality.\n\n"
                "## Review Questions\n\n"
                "- How is normality different from commutativity?\n",
                encoding="utf-8",
                newline="\n",
            )

            issues = atomic_note_quality_issues(note, project)

            self.assertIn("invalid status", issues)

    def test_note_quality_rejects_invalid_review_status(self) -> None:
        from socrates.quality import atomic_note_quality_issues

        with tempfile.TemporaryDirectory() as temp_dir:
            project = create_project(ProjectSpec(topic="Group Theory", path=Path(temp_dir) / "p"))
            note = project / "04_atomic_notes" / "drafts" / "invalid_review_status.md"
            note.write_text(
                "---\n"
                "status: draft\n"
                "review_status: waiting\n"
                "reviewed_by_user: false\n"
                "type: definition\n"
                "concept: Normal Subgroup\n"
                "source_id: df\n"
                "tags:\n"
                "  - normal-subgroup\n"
                "related:\n"
                "  - \"[[Subgroup]]\"\n"
                "---\n\n"
                "# Normal Subgroup\n\n"
                "A normal subgroup is stable under conjugation.\n\n"
                "## Key Examples\n\n"
                "- Kernels of homomorphisms.\n\n"
                "## Non-Examples\n\n"
                "- A non-normal subgroup of S3.\n\n"
                "## Common Mistakes\n\n"
                "- Confusing normality with centrality.\n\n"
                "## Review Questions\n\n"
                "- How is normality different from commutativity?\n",
                encoding="utf-8",
                newline="\n",
            )

            issues = atomic_note_quality_issues(note, project)

            self.assertIn("invalid review_status", issues)

    def test_note_quality_rejects_invalid_note_type(self) -> None:
        from socrates.quality import atomic_note_quality_issues

        with tempfile.TemporaryDirectory() as temp_dir:
            project = create_project(ProjectSpec(topic="Group Theory", path=Path(temp_dir) / "p"))
            note = project / "04_atomic_notes" / "drafts" / "invalid_type.md"
            note.write_text(
                "---\n"
                "status: draft\n"
                "review_status: needs_review\n"
                "reviewed_by_user: false\n"
                "type: summary\n"
                "concept: Normal Subgroup\n"
                "source_id: df\n"
                "tags:\n"
                "  - normal-subgroup\n"
                "related:\n"
                "  - \"[[Subgroup]]\"\n"
                "---\n\n"
                "# Normal Subgroup\n\n"
                "A normal subgroup is stable under conjugation.\n\n"
                "## Key Examples\n\n"
                "- Kernels of homomorphisms.\n\n"
                "## Non-Examples\n\n"
                "- A non-normal subgroup of S3.\n\n"
                "## Common Mistakes\n\n"
                "- Confusing normality with centrality.\n\n"
                "## Review Questions\n\n"
                "- How is normality different from commutativity?\n",
                encoding="utf-8",
                newline="\n",
            )

            issues = atomic_note_quality_issues(note, project)

            self.assertIn("invalid type", issues)

    def test_note_check_cli_writes_quality_report_for_atomic_notes(self) -> None:
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
                    "A normal subgroup is stable under conjugation.\n\n"
                    "## Review Questions\n\n"
                    "- How is normality different from commutativity?\n"
                ),
                source_id="df-1",
            )

            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "socrates",
                    "note",
                    "check",
                    "--project",
                    str(project),
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("Checked 1 atomic note: 1 passed, 0 failed", result.stdout)
            self.assertIn("Note quality manifest:", result.stdout)
            report = project / "08_evals" / "note_quality_eval.md"
            report_text = report.read_text(encoding="utf-8")
            self.assertIn("# Note Quality Eval", report_text)
            self.assertIn("## Summary", report_text)
            self.assertIn("- Notes checked: 1", report_text)
            self.assertIn("- Passed: 1", report_text)
            self.assertIn("- Failed: 0", report_text)
            self.assertIn("drafts/normal_subgroup.md: pass", report_text)
            manifest = json.loads(
                (project / "08_evals" / "note_quality_manifest.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(manifest["schema_version"], 1)
            self.assertEqual(manifest["checked"], 1)
            self.assertEqual(manifest["passed"], 1)
            self.assertEqual(manifest["failed"], 0)
            self.assertEqual(manifest["notes"][0]["id"], "normal_subgroup")
            self.assertEqual(
                manifest["notes"][0]["path"],
                "04_atomic_notes/drafts/normal_subgroup.md",
            )
            self.assertEqual(manifest["notes"][0]["quality_status"], "pass")
            self.assertEqual(
                manifest["notes"][0]["frontmatter"]["concept"],
                "Normal Subgroup",
            )
            self.assertEqual(
                manifest["notes"][0]["frontmatter"]["reviewed_by_user"],
                False,
            )
            self.assertIn(
                "normal-subgroup",
                manifest["notes"][0]["frontmatter"]["tags"],
            )
            self.assertEqual(manifest["notes"][0]["sections"]["review_question_count"], 1)
            self.assertEqual(manifest["notes"][0]["sections"]["has_reference_context"], True)


if __name__ == "__main__":
    unittest.main()

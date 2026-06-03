from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from socrates.kb import build_reference_kb, search_reference_kb
from socrates.project import ProjectSpec, create_project


class ReferenceKbTests(unittest.TestCase):
    def test_build_reference_kb_extracts_objects_and_graph_from_curated_markdown(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = create_project(ProjectSpec(topic="Group Theory", path=Path(temp_dir) / "p"))
            curated = project / "01_references" / "curated" / "normal_subgroups.curated.md"
            curated.write_text(
                "\n".join(
                    [
                        "# Chapter 3: Quotient Groups",
                        "## Section 3.1 Normal Subgroups",
                        "### Definition: Normal Subgroup",
                        "A subgroup N of G is normal if gNg^{-1}=N for every g in G.",
                        "Depends: subgroup, conjugation",
                        "### Theorem: Kernels are Normal",
                        "The kernel of a group homomorphism is a normal subgroup.",
                        "Depends: group homomorphism, kernel, normal subgroup",
                        "",
                    ]
                ),
                encoding="utf-8",
            )

            result = build_reference_kb(project)

            self.assertEqual(result.object_count, 2)
            self.assertEqual(result.chunk_count, 2)
            self.assertEqual(result.index_path, project / "06_kb" / "chunks" / "reference_index.json")

            index = json.loads(result.index_path.read_text(encoding="utf-8"))
            self.assertEqual([item["type"] for item in index["objects"]], ["definition", "theorem"])
            self.assertEqual(index["objects"][0]["title"], "Normal Subgroup")
            self.assertEqual(
                index["objects"][0]["source"]["path"],
                "01_references/curated/normal_subgroups.curated.md",
            )
            self.assertIn("conjugation", index["objects"][0]["dependencies"])

            concept_graph = json.loads((project / "06_kb" / "concept_graph.json").read_text(encoding="utf-8"))
            self.assertIn({"id": "normal_subgroup", "label": "Normal Subgroup", "type": "definition"}, concept_graph["nodes"])
            self.assertIn(
                {"source": "normal_subgroup", "target": "conjugation", "relationship": "prerequisite"},
                concept_graph["edges"],
            )

    def test_search_reference_kb_returns_source_grounded_matches(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = create_project(ProjectSpec(topic="Group Theory", path=Path(temp_dir) / "p"))
            curated = project / "01_references" / "curated" / "kernels.curated.md"
            curated.write_text(
                "### Theorem: Kernel Normality\n"
                "The kernel of a homomorphism is normal by conjugation.\n"
                "Depends: kernel, conjugation\n",
                encoding="utf-8",
            )
            build_reference_kb(project)

            matches = search_reference_kb(project, "conjugation")

            self.assertEqual(len(matches), 1)
            self.assertEqual(matches[0]["title"], "Kernel Normality")
            self.assertEqual(matches[0]["type"], "theorem")
            self.assertIn("kernels.curated.md", matches[0]["source"]["path"])

    def test_build_reference_kb_writes_theorem_and_exercise_indexes(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = create_project(ProjectSpec(topic="Group Theory", path=Path(temp_dir) / "p"))
            curated = project / "01_references" / "curated" / "normality.curated.md"
            curated.write_text(
                "# Group Theory\n"
                "## Normality\n"
                "### Theorem: Kernel Normality\n"
                "The kernel of a group homomorphism is normal.\n"
                "Depends: group_homomorphism, kernel\n\n"
                "### Exercise: Prove Kernel Normality\n"
                "Prove that the kernel of a homomorphism is normal.\n"
                "Depends: kernel, normal_subgroup\n",
                encoding="utf-8",
            )

            build_reference_kb(project)

            theorem_index = json.loads(
                (project / "06_kb" / "theorem_index.json").read_text(encoding="utf-8")
            )
            exercise_index = json.loads(
                (project / "06_kb" / "exercise_index.json").read_text(encoding="utf-8")
            )
            self.assertEqual(theorem_index["theorems"][0]["title"], "Kernel Normality")
            self.assertEqual(
                theorem_index["theorems"][0]["source"]["path"],
                "01_references/curated/normality.curated.md",
            )
            self.assertEqual(exercise_index["exercises"][0]["title"], "Prove Kernel Normality")
            self.assertIn("normal_subgroup", exercise_index["exercises"][0]["dependencies"])

    def test_build_reference_kb_writes_chapter_section_index(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = create_project(ProjectSpec(topic="Group Theory", path=Path(temp_dir) / "p"))
            curated = project / "01_references" / "curated" / "normality.curated.md"
            curated.write_text(
                "# Chapter 3: Quotient Groups\n"
                "## Section 3.1 Normal Subgroups\n"
                "### Definition: Normal Subgroup\n"
                "A normal subgroup is stable under conjugation.\n"
                "Depends: subgroup, conjugation\n\n"
                "### Theorem: Kernel Normality\n"
                "The kernel of a group homomorphism is normal.\n"
                "Depends: kernel, normal subgroup\n\n"
                "## Section 3.2 Quotient Groups\n"
                "### Definition: Quotient Group\n"
                "The quotient group G/N is formed from cosets of a normal subgroup.\n"
                "Depends: normal subgroup, coset\n",
                encoding="utf-8",
            )

            build_reference_kb(project)

            chapter_index = json.loads(
                (project / "06_kb" / "chapter_index.json").read_text(encoding="utf-8")
            )
            self.assertEqual(chapter_index["schema_version"], 1)
            self.assertEqual(chapter_index["chapters"][0]["title"], "Chapter 3: Quotient Groups")
            self.assertEqual(
                chapter_index["chapters"][0]["sections"][0],
                {
                    "title": "Section 3.1 Normal Subgroups",
                    "source_path": "01_references/curated/normality.curated.md",
                    "objects": [
                        {
                            "id": "normal_subgroup",
                            "type": "definition",
                            "title": "Normal Subgroup",
                        },
                        {
                            "id": "kernel_normality",
                            "type": "theorem",
                            "title": "Kernel Normality",
                        },
                    ],
                },
            )
            self.assertEqual(
                chapter_index["chapters"][0]["sections"][1]["objects"][0]["id"],
                "quotient_group",
            )


if __name__ == "__main__":
    unittest.main()

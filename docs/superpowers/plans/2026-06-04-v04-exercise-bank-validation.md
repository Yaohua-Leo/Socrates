# Socrates v0.4 Exercise Bank and Validation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make generated Socrates exercises reliable enough to manage as a reviewable exercise bank with structured schema validation, solution/rubric checks, counterexample-search evidence, and bank-level status.

**Architecture:** Preserve the v0.3 local-first, stdlib-only baseline and keep LLM output proposal-only. Add a structured exercise-schema layer that parses existing Markdown drafts instead of replacing them, then build validation and bank manifests on top of the same generated files. Exercise approval remains human-gated; v0.4 validation decides whether an exercise is bank-ready, not whether it is mathematically proven.

**Tech Stack:** Python 3.11+, stdlib only, `unittest`, `argparse`, existing Socrates Markdown artifacts, existing Reference KB counterexample search, existing tool-verification manifests, no new runtime dependencies.

---

## Current Baseline and Execution Contract

- Start from the current v0.3-alpha branch state. At plan-writing time the working branch is `codex/v02-closure`, ahead of `origin/codex/v02-closure` by one commit.
- Treat commit `69b61ad072731f009623c960fa1fdebcd82a9f7b` (`Keep LLM assistance as reviewable local drafts`) as the v0.3-alpha baseline.
- Preserve the no-runtime-dependency policy in `pyproject.toml`.
- Do not read, print, stage, or commit `D:\Socrates\.env`.
- Default deterministic gates must remain offline:
  - `powershell -ExecutionPolicy Bypass -File scripts\check.ps1`
  - `bash scripts/check.sh`
- Live DeepSeek tests remain unrelated to v0.4 and stay opt-in.
- This plan is about v0.4 exercise-bank reliability. It does not add autonomous LLM tutoring, OCR/PDF conversion, LLM judging, vector retrieval, UI, or new external math-tool dependencies.

## Safety Rules for v0.4

- Generated exercises remain draft material until a human approval step marks them approved.
- Validation reports are conservative evidence, not formal mathematical proof.
- Counterexample-search results from the Reference KB are advisory. A match means "review this exercise carefully"; no match does not prove correctness.
- Tool-verification evidence may strengthen a validation record only when a matching, current persisted tool-verification record exists.
- `exercise bank build` must include only approved exercises with passing v0.4 validation.
- Existing `exercise grade` remains the only command that mutates learner mastery from an attempt.
- Existing LLM suggestion drafts must not be applied automatically by any v0.4 command.

## File Structure

- Create `socrates/exercise_schema.py`: parse generated exercise Markdown into structured dataclasses and validate frontmatter, sections, hints, solution steps, rubric totals, concepts, and common mistakes.
- Create `socrates/exercise_validation.py`: run one-exercise and project-wide validation, write `08_evals/exercise_validation/` reports, and maintain `08_evals/exercise_validation_manifest.json`.
- Create `socrates/exercise_bank.py`: build and read `05_exercises/exercise_bank_manifest.json` from approved, passing validation records.
- Modify `socrates/artifacts.py`: add schema-version metadata and reusable template helpers while preserving the existing generated Markdown sections.
- Modify `socrates/exercises.py`: expose validation and bank summaries through exercise listing metadata without treating feedback drafts as attempts.
- Modify `socrates/quality.py`: reuse v0.4 validation inside exercise quality checks and benchmark gates without duplicating parsing logic.
- Modify `socrates/cli.py`: add `exercise validate`, `exercise bank build`, and `exercise bank status` commands.
- Modify `docs/README.md`, `README.md`, `docs/development_log.md`, and `docs/development_roadmap.md` after implementation verification.
- Create tests:
  - `tests/test_exercise_schema.py`
  - `tests/test_exercise_validation.py`
  - `tests/test_exercise_bank.py`
  - `tests/test_v04_exercise_flow.py`
- Update tests:
  - `tests/test_exercise_quality.py`
  - `tests/test_status_quality_summary.py`
  - `tests/test_benchmark.py`
  - `tests/test_lifecycle_audit.py`

## Task 1: Exercise Schema Parser and Validator

**Files:**
- Create: `socrates/exercise_schema.py`
- Test: `tests/test_exercise_schema.py`

- [ ] **Step 1: Write schema parser tests**

Create `tests/test_exercise_schema.py`:

```python
from pathlib import Path
import tempfile
import unittest

from socrates.artifacts import generate_exercise_drafts
from socrates.exercise_schema import parse_exercise_markdown, validate_exercise_spec
from socrates.project import ProjectSpec, create_project


class ExerciseSchemaTests(unittest.TestCase):
    def test_generated_exercise_parses_to_structured_spec(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = create_project(
                ProjectSpec(topic="Group Theory", path=Path(temp_dir) / "p")
            )
            draft = generate_exercise_drafts(
                project,
                concept="Normal Subgroup",
                source_id="df-1",
                prerequisites=["subgroup", "conjugation"],
                count=5,
            )[0]
            exercise_path = project / draft.path

            spec = parse_exercise_markdown(exercise_path)

            self.assertEqual(spec.exercise_id, "normal_subgroup_01")
            self.assertEqual(spec.status, "draft")
            self.assertEqual(spec.review_status, "needs_review")
            self.assertEqual(spec.exercise_type, "generated_exercise")
            self.assertEqual(spec.concept, "Normal Subgroup")
            self.assertEqual(spec.difficulty, 1)
            self.assertEqual(spec.rubric.total_points, 10)
            self.assertEqual(sum(item.points for item in spec.rubric.items), 10)
            self.assertGreaterEqual(len(spec.hints), 3)
            self.assertGreaterEqual(len(spec.solution_steps), 3)
            self.assertEqual(validate_exercise_spec(spec), [])

    def test_validator_reports_non_progressive_hints_and_bad_rubric_sum(self) -> None:
        text = (
            "---\n"
            "status: draft\n"
            "review_status: needs_review\n"
            "type: generated_exercise\n"
            "concept: Normal Subgroup\n"
            "source_id: df-1\n"
            "difficulty: 2\n"
            "---\n\n"
            "# Bad Exercise\n\n"
            "## Statement\n\nProve something about normal subgroups.\n\n"
            "## Target Training Point\n\nUse the definition explicitly.\n\n"
            "## Concepts\n\n- Normal Subgroup\n\n"
            "## Prerequisites\n\n- subgroup\n\n"
            "## Hints\n\n"
            "- Hint 2 (structure): Start in the middle.\n"
            "- Hint 2 (structure): Repeat the same level.\n\n"
            "## Solution Outline\n\n"
            "- Step 1: State the definition.\n"
            "- Step 2: Apply it.\n"
            "- Step 3: Conclude.\n\n"
            "## Rubric\n\n"
            "- Total: 10 pts\n"
            "- Definition setup: 3 pts\n"
            "- Correct verification: 3 pts\n"
            "- Complete conclusion: 3 pts\n\n"
            "## Common Mistakes\n\n- Skipping one condition.\n"
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "bad.md"
            path.write_text(text, encoding="utf-8", newline="\n")

            spec = parse_exercise_markdown(path)
            issues = validate_exercise_spec(spec)

            self.assertIn("non-progressive hint ladder", issues)
            self.assertIn("rubric point values do not sum to total", issues)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run failing schema tests**

Run:

```powershell
python -m unittest tests.test_exercise_schema
```

Expected before implementation: fail because `socrates.exercise_schema` does not exist.

- [ ] **Step 3: Implement schema dataclasses**

Create `socrates/exercise_schema.py` with these public dataclasses and constants:

```python
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re

from .contracts import EXERCISE_ALLOWED_REVIEW_STATUSES, EXERCISE_ALLOWED_STATUSES, EXERCISE_ALLOWED_TYPES


@dataclass(frozen=True)
class HintStep:
    level: int
    label: str
    text: str


@dataclass(frozen=True)
class SolutionStep:
    number: int
    text: str


@dataclass(frozen=True)
class RubricItem:
    label: str
    points: int


@dataclass(frozen=True)
class RubricSpec:
    total_points: int
    items: tuple[RubricItem, ...]


@dataclass(frozen=True)
class ExerciseSpec:
    exercise_id: str
    path: str
    status: str
    review_status: str
    exercise_type: str
    concept: str
    source_id: str
    difficulty: int
    statement: str
    review_prompt: str
    target_training_point: str
    concepts: tuple[str, ...]
    prerequisites: tuple[str, ...]
    hints: tuple[HintStep, ...]
    solution_steps: tuple[SolutionStep, ...]
    rubric: RubricSpec
    common_mistakes: tuple[str, ...]
    frontmatter: dict[str, str]
```

- [ ] **Step 4: Implement Markdown parsing**

Add parser helpers to `socrates/exercise_schema.py`:

```python
FRONTMATTER_RE = re.compile(r"\A---\n(?P<body>.*?)\n---\n", re.DOTALL)
HINT_RE = re.compile(r"^- Hint (?P<level>\d+) \((?P<label>[^)]+)\): (?P<text>.+)$")
STEP_RE = re.compile(r"^- Step (?P<number>\d+): (?P<text>.+)$")
RUBRIC_TOTAL_RE = re.compile(r"^- Total: (?P<points>\d+) pts$")
RUBRIC_ITEM_RE = re.compile(r"^- (?P<label>[^:]+): (?P<points>\d+) pts$")


def parse_exercise_markdown(path: Path | str) -> ExerciseSpec:
    exercise_path = Path(path)
    text = exercise_path.read_text(encoding="utf-8")
    frontmatter = _frontmatter(text)
    body = _body_without_frontmatter(text)
    return ExerciseSpec(
        exercise_id=exercise_path.stem,
        path=exercise_path.as_posix(),
        status=frontmatter.get("status", ""),
        review_status=frontmatter.get("review_status", ""),
        exercise_type=frontmatter.get("type", ""),
        concept=frontmatter.get("concept", ""),
        source_id=frontmatter.get("source_id", ""),
        difficulty=_int_value(frontmatter.get("difficulty", "")),
        statement=_section_text(body, "## Statement"),
        review_prompt=_section_text(body, "## Review Prompt"),
        target_training_point=_section_text(body, "## Target Training Point"),
        concepts=tuple(_bullet_values(_section_text(body, "## Concepts"))),
        prerequisites=tuple(_bullet_values(_section_text(body, "## Prerequisites"))),
        hints=tuple(_hint_steps(_section_text(body, "## Hints"))),
        solution_steps=tuple(_solution_steps(_section_text(body, "## Solution Outline"))),
        rubric=_rubric_spec(_section_text(body, "## Rubric")),
        common_mistakes=tuple(_bullet_values(_section_text(body, "## Common Mistakes"))),
        frontmatter=frontmatter,
    )
```

Implement `_frontmatter`, `_body_without_frontmatter`, `_section_text`, `_bullet_values`, `_hint_steps`, `_solution_steps`, `_rubric_spec`, and `_int_value` in the same file. Keep parsing conservative: missing values become empty strings, empty tuples, or zero-point rubric fields instead of raising. Validation decides pass/fail.

- [ ] **Step 5: Implement schema validation**

Add:

```python
def validate_exercise_spec(spec: ExerciseSpec) -> list[str]:
    issues: list[str] = []
    if spec.status not in EXERCISE_ALLOWED_STATUSES:
        issues.append("invalid exercise status")
    if spec.review_status not in EXERCISE_ALLOWED_REVIEW_STATUSES:
        issues.append("invalid exercise review_status")
    if spec.exercise_type not in EXERCISE_ALLOWED_TYPES:
        issues.append("invalid exercise type")
    if not spec.concept:
        issues.append("missing concept")
    if not 1 <= spec.difficulty <= 5:
        issues.append("invalid difficulty")
    if not spec.statement and not spec.review_prompt:
        issues.append("missing statement or review prompt")
    if not spec.target_training_point:
        issues.append("missing target training point")
    if not spec.concepts:
        issues.append("missing concept tags")
    if not spec.prerequisites:
        issues.append("missing prerequisites")
    if len(spec.hints) < 3:
        issues.append("missing hint ladder")
    elif [hint.level for hint in spec.hints] != sorted({hint.level for hint in spec.hints}):
        issues.append("non-progressive hint ladder")
    if len(spec.solution_steps) < 3:
        issues.append("missing structured solution steps")
    if spec.rubric.total_points <= 0 or not spec.rubric.items:
        issues.append("missing rubric point values")
    elif sum(item.points for item in spec.rubric.items) != spec.rubric.total_points:
        issues.append("rubric point values do not sum to total")
    if not spec.common_mistakes:
        issues.append("missing common mistakes")
    return issues
```

- [ ] **Step 6: Run schema tests and diff check**

Run:

```powershell
python -m unittest tests.test_exercise_schema
git diff --check
```

Expected: tests pass and no whitespace errors.

- [ ] **Step 7: Commit Task 1**

Use a Lore-style commit message:

```text
Parse generated exercises through a structured schema

Constraint: Preserve existing Markdown exercise artifacts and avoid new runtime dependencies.
Confidence: high
Scope-risk: narrow
Tested: python -m unittest tests.test_exercise_schema
```

## Task 2: Schema-Aware Exercise Generation

**Files:**
- Modify: `socrates/artifacts.py`
- Modify: `socrates/contracts.py`
- Test: `tests/test_exercise_schema.py`
- Test: `tests/test_exercise_quality.py`

- [ ] **Step 1: Add generation regression tests**

Extend `tests/test_exercise_schema.py`:

```python
    def test_generated_exercises_include_schema_version_and_template_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = create_project(
                ProjectSpec(topic="Group Theory", path=Path(temp_dir) / "p")
            )
            drafts = generate_exercise_drafts(
                project,
                concept="Normal Subgroup",
                source_id="df-1",
                prerequisites=["subgroup", "conjugation"],
                count=5,
            )

            first_text = (project / drafts[0].path).read_text(encoding="utf-8")

            self.assertIn("schema_version: 1", first_text)
            self.assertIn("template: definition_application", first_text)
            self.assertIn("solution_schema_version: 1", first_text)
            self.assertIn("rubric_schema_version: 1", first_text)
```

- [ ] **Step 2: Run failing generation tests**

Run:

```powershell
python -m unittest tests.test_exercise_schema
```

Expected before implementation: fail because the generated frontmatter does not include the new v0.4 schema metadata.

- [ ] **Step 3: Add exercise schema metadata constants**

In `socrates/contracts.py`, add:

```python
EXERCISE_SCHEMA_VERSION = 1
SOLUTION_SCHEMA_VERSION = 1
RUBRIC_SCHEMA_VERSION = 1
EXERCISE_ALLOWED_TEMPLATES = frozenset(
    {
        "definition_application",
        "example_nonexample",
        "proof_outline",
        "counterexample_probe",
        "mixed_review",
    }
)
```

- [ ] **Step 4: Add metadata to generated exercises**

In `socrates/artifacts.py`, import the constants:

```python
from .contracts import (
    EXERCISE_SCHEMA_VERSION,
    RUBRIC_SCHEMA_VERSION,
    SOLUTION_SCHEMA_VERSION,
)
```

In `_exercise_text()`, add these frontmatter keys:

```python
"schema_version": EXERCISE_SCHEMA_VERSION,
"template": "definition_application",
"solution_schema_version": SOLUTION_SCHEMA_VERSION,
"rubric_schema_version": RUBRIC_SCHEMA_VERSION,
```

In `_targeted_review_exercise_text()`, add:

```python
"schema_version": EXERCISE_SCHEMA_VERSION,
"template": "example_nonexample",
"solution_schema_version": SOLUTION_SCHEMA_VERSION,
"rubric_schema_version": RUBRIC_SCHEMA_VERSION,
```

- [ ] **Step 5: Extend schema parser for metadata**

In `ExerciseSpec`, add:

```python
schema_version: int
template: str
solution_schema_version: int
rubric_schema_version: int
```

Populate those fields in `parse_exercise_markdown()` from frontmatter:

```python
schema_version=_int_value(frontmatter.get("schema_version", "")),
template=frontmatter.get("template", ""),
solution_schema_version=_int_value(frontmatter.get("solution_schema_version", "")),
rubric_schema_version=_int_value(frontmatter.get("rubric_schema_version", "")),
```

In `validate_exercise_spec()`, add:

```python
if spec.schema_version != 1:
    issues.append("invalid exercise schema_version")
if spec.solution_schema_version != 1:
    issues.append("invalid solution schema_version")
if spec.rubric_schema_version != 1:
    issues.append("invalid rubric schema_version")
if spec.template not in EXERCISE_ALLOWED_TEMPLATES:
    issues.append("invalid exercise template")
```

- [ ] **Step 6: Run generation and existing exercise-quality tests**

Run:

```powershell
python -m unittest tests.test_exercise_schema tests.test_exercise_quality
git diff --check
```

Expected: tests pass; existing generated exercise IDs and lifecycle statuses remain unchanged.

- [ ] **Step 7: Commit Task 2**

Use a Lore-style commit message:

```text
Stamp generated exercises with stable v04 schema metadata

Constraint: Existing Markdown sections and exercise IDs stay compatible with v0.1-v0.3 tests.
Rejected: Replace Markdown artifacts with JSON-only exercises | breaks review and Obsidian-friendly workflows.
Confidence: high
Scope-risk: narrow
Tested: python -m unittest tests.test_exercise_schema tests.test_exercise_quality
```

## Task 3: Per-Exercise Validation Reports

**Files:**
- Create: `socrates/exercise_validation.py`
- Modify: `socrates/quality.py`
- Test: `tests/test_exercise_validation.py`

- [ ] **Step 1: Write validation tests**

Create `tests/test_exercise_validation.py`:

```python
from pathlib import Path
import json
import tempfile
import unittest

from socrates.artifacts import generate_exercise_drafts
from socrates.exercise_validation import validate_exercise, validate_project_exercises
from socrates.project import ProjectSpec, create_project


class ExerciseValidationTests(unittest.TestCase):
    def test_validate_one_exercise_writes_report_and_json(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = create_project(
                ProjectSpec(topic="Group Theory", path=Path(temp_dir) / "p")
            )
            draft = generate_exercise_drafts(
                project,
                concept="Normal Subgroup",
                source_id="df-1",
                prerequisites=["subgroup", "conjugation"],
                count=5,
            )[0]

            result = validate_exercise(project, draft.id)

            self.assertEqual(result.exercise_id, draft.id)
            self.assertEqual(result.status, "pass")
            self.assertTrue(result.report_path.exists())
            self.assertTrue(result.artifact_path.exists())
            artifact = json.loads(result.artifact_path.read_text(encoding="utf-8"))
            self.assertEqual(artifact["schema_version"], 1)
            self.assertEqual(artifact["exercise_id"], draft.id)
            self.assertEqual(artifact["status"], "pass")
            self.assertEqual(artifact["schema"]["status"], "pass")
            self.assertEqual(artifact["counterexample_search"]["status"], "not_run")

    def test_project_validation_manifest_records_failures(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = create_project(
                ProjectSpec(topic="Group Theory", path=Path(temp_dir) / "p")
            )
            draft = generate_exercise_drafts(
                project,
                concept="Normal Subgroup",
                source_id="df-1",
                prerequisites=["subgroup", "conjugation"],
                count=5,
            )[0]
            exercise_path = project / draft.path
            exercise_path.write_text(
                exercise_path.read_text(encoding="utf-8").replace(
                    "- Complete conclusion: 3 pts",
                    "- Complete conclusion: 2 pts",
                    1,
                ),
                encoding="utf-8",
                newline="\n",
            )

            result = validate_project_exercises(project)

            self.assertEqual(result.checked, 5)
            self.assertEqual(result.failed, 1)
            manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
            failed = [item for item in manifest["records"] if item["status"] == "fail"]
            self.assertEqual(failed[0]["exercise_id"], draft.id)
            self.assertIn("rubric point values do not sum to total", failed[0]["issues"])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run failing validation tests**

Run:

```powershell
python -m unittest tests.test_exercise_validation
```

Expected before implementation: fail because `socrates.exercise_validation` does not exist.

- [ ] **Step 3: Implement validation result dataclasses**

Create `socrates/exercise_validation.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path

from .context import load_project, write_json, write_text
from .exercise_schema import parse_exercise_markdown, validate_exercise_spec
from .kb import find_counterexamples


VALIDATION_DIR = Path("08_evals") / "exercise_validation"
VALIDATION_MANIFEST = Path("08_evals") / "exercise_validation_manifest.json"


@dataclass(frozen=True)
class ExerciseValidationResult:
    exercise_id: str
    status: str
    issues: tuple[str, ...]
    report_path: Path
    artifact_path: Path


@dataclass(frozen=True)
class ProjectExerciseValidationResult:
    checked: int
    passed: int
    failed: int
    report_path: Path
    manifest_path: Path
```

- [ ] **Step 4: Implement one-exercise validation**

Add:

```python
def validate_exercise(project_path: Path | str, exercise_id: str) -> ExerciseValidationResult:
    context = load_project(project_path)
    exercise_path = context.generated_exercises_dir / f"{exercise_id}.md"
    if not exercise_path.exists():
        raise FileNotFoundError(f"Generated exercise does not exist: {exercise_path}")
    spec = parse_exercise_markdown(exercise_path)
    schema_issues = validate_exercise_spec(spec)
    counterexample = _counterexample_summary(context.root, spec.concept)
    issues = list(schema_issues)
    status = "fail" if issues else "pass"
    artifact_path = context.root / VALIDATION_DIR / f"{exercise_id}.json"
    report_path = context.root / VALIDATION_DIR / f"{exercise_id}.md"
    payload = {
        "schema_version": 1,
        "exercise_id": exercise_id,
        "path": exercise_path.relative_to(context.root).as_posix(),
        "status": status,
        "issues": issues,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "schema": {
            "status": "fail" if schema_issues else "pass",
            "issues": schema_issues,
            "concept": spec.concept,
            "difficulty": spec.difficulty,
            "template": spec.template,
            "rubric_total_points": spec.rubric.total_points,
        },
        "counterexample_search": counterexample,
    }
    write_json(artifact_path, payload)
    write_text(report_path, _validation_report(payload))
    return ExerciseValidationResult(
        exercise_id=exercise_id,
        status=status,
        issues=tuple(issues),
        report_path=report_path,
        artifact_path=artifact_path,
    )
```

Implement `_counterexample_summary()` so missing Reference KB returns `{"status": "not_run", "reason": "reference KB index missing", "match_count": 0, "matches": []}`. When KB is readable, call `find_counterexamples(project_root, concept, limit=3)` and store `status: "searched"`, `match_count`, and compact match entries.

- [ ] **Step 5: Implement project validation manifest**

Add:

```python
def validate_project_exercises(project_path: Path | str) -> ProjectExerciseValidationResult:
    context = load_project(project_path)
    exercise_ids = sorted(path.stem for path in context.generated_exercises_dir.glob("*.md"))
    results = [validate_exercise(context.root, exercise_id) for exercise_id in exercise_ids]
    manifest_path = context.root / VALIDATION_MANIFEST
    report_path = context.evals_dir / "exercise_validation_eval.md"
    records = [
        {
            "exercise_id": result.exercise_id,
            "status": result.status,
            "issues": list(result.issues),
            "artifact_path": result.artifact_path.relative_to(context.root).as_posix(),
            "report_path": result.report_path.relative_to(context.root).as_posix(),
        }
        for result in results
    ]
    manifest = {
        "schema_version": 1,
        "checked": len(results),
        "passed": sum(1 for result in results if result.status == "pass"),
        "failed": sum(1 for result in results if result.status == "fail"),
        "records": records,
    }
    write_json(manifest_path, manifest)
    write_text(report_path, _project_validation_report(manifest))
    return ProjectExerciseValidationResult(
        checked=manifest["checked"],
        passed=manifest["passed"],
        failed=manifest["failed"],
        report_path=report_path,
        manifest_path=manifest_path,
    )
```

- [ ] **Step 6: Run validation tests**

Run:

```powershell
python -m unittest tests.test_exercise_validation
git diff --check
```

Expected: tests pass and validation reports are written under `08_evals/exercise_validation/`.

- [ ] **Step 7: Commit Task 3**

Use a Lore-style commit message:

```text
Record exercise validation as reviewable evidence

Constraint: Validation is advisory and does not approve or grade exercises.
Rejected: Make counterexample-search failures block all exercises | absence of KB evidence is not mathematical evidence.
Confidence: high
Scope-risk: moderate
Tested: python -m unittest tests.test_exercise_validation
```

## Task 4: CLI Validation Commands

**Files:**
- Modify: `socrates/cli.py`
- Test: `tests/test_exercise_validation.py`

- [ ] **Step 1: Write CLI validation tests**

Extend `tests/test_exercise_validation.py`:

```python
import subprocess
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]


    def test_exercise_validate_cli_validates_one_or_all_exercises(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = create_project(
                ProjectSpec(topic="Group Theory", path=Path(temp_dir) / "p")
            )
            generate_exercise_drafts(
                project,
                concept="Normal Subgroup",
                source_id="df-1",
                prerequisites=["subgroup", "conjugation"],
                count=5,
            )

            one = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "socrates",
                    "exercise",
                    "validate",
                    "--project",
                    str(project),
                    "--exercise",
                    "normal_subgroup_01",
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            all_result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "socrates",
                    "exercise",
                    "validate",
                    "--project",
                    str(project),
                    "--all",
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(one.returncode, 0, one.stderr)
            self.assertIn("Validated exercise normal_subgroup_01: pass", one.stdout)
            self.assertEqual(all_result.returncode, 0, all_result.stderr)
            self.assertIn("Validated 5 exercise drafts: 5 passed, 0 failed", all_result.stdout)
            self.assertTrue((project / "08_evals" / "exercise_validation_manifest.json").exists())
```

- [ ] **Step 2: Run failing CLI tests**

Run:

```powershell
python -m unittest tests.test_exercise_validation
```

Expected before implementation: fail because `exercise validate` is not registered.

- [ ] **Step 3: Register CLI arguments**

In `socrates/cli.py`, import:

```python
from .exercise_validation import validate_exercise, validate_project_exercises
```

In `build_parser()` after `exercise_check_parser`, add:

```python
    exercise_validate_parser = exercise_subparsers.add_parser(
        "validate",
        help="Run v0.4 schema and evidence validation for generated exercise drafts.",
    )
    exercise_validate_parser.add_argument("--project", required=True, help="Socrates project directory.")
    exercise_validate_group = exercise_validate_parser.add_mutually_exclusive_group(required=True)
    exercise_validate_group.add_argument("--exercise", help="Generated exercise id, without .md.")
    exercise_validate_group.add_argument("--all", action="store_true", help="Validate all generated exercise drafts.")
    exercise_validate_parser.set_defaults(func=_handle_exercise_validate)
```

- [ ] **Step 4: Implement CLI handler**

Add near the other exercise handlers:

```python
def _handle_exercise_validate(args: argparse.Namespace) -> int:
    try:
        if args.all:
            result = validate_project_exercises(args.project)
            print(
                f"Validated {result.checked} exercise drafts: "
                f"{result.passed} passed, {result.failed} failed"
            )
            print(f"Exercise validation report: {result.report_path}")
            print(f"Exercise validation manifest: {result.manifest_path}")
            return 0
        result = validate_exercise(args.project, args.exercise)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(f"Validated exercise {result.exercise_id}: {result.status}")
    print(f"Exercise validation report: {result.report_path}")
    print(f"Exercise validation artifact: {result.artifact_path}")
    return 0
```

- [ ] **Step 5: Run CLI validation tests and diff check**

Run:

```powershell
python -m unittest tests.test_exercise_validation
git diff --check
```

Expected: tests pass.

- [ ] **Step 6: Commit Task 4**

Use a Lore-style commit message:

```text
Expose exercise validation through the CLI

Constraint: Validation commands write evidence but do not approve, grade, or mutate learning state.
Confidence: high
Scope-risk: narrow
Tested: python -m unittest tests.test_exercise_validation
```

## Task 5: Exercise Bank Manifest

**Files:**
- Create: `socrates/exercise_bank.py`
- Modify: `socrates/cli.py`
- Test: `tests/test_exercise_bank.py`

- [ ] **Step 1: Write exercise bank tests**

Create `tests/test_exercise_bank.py`:

```python
from pathlib import Path
import json
import subprocess
import sys
import tempfile
import unittest

from socrates.artifacts import generate_exercise_drafts
from socrates.exercise_bank import build_exercise_bank, read_exercise_bank
from socrates.exercise_validation import validate_project_exercises
from socrates.exercises import approve_exercise_draft
from socrates.project import ProjectSpec, create_project


REPO_ROOT = Path(__file__).resolve().parents[1]


class ExerciseBankTests(unittest.TestCase):
    def test_bank_includes_only_approved_passing_validation_records(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = create_project(
                ProjectSpec(topic="Group Theory", path=Path(temp_dir) / "p")
            )
            generate_exercise_drafts(
                project,
                concept="Normal Subgroup",
                source_id="df-1",
                prerequisites=["subgroup", "conjugation"],
                count=5,
            )
            approve_exercise_draft(project, "normal_subgroup_01")
            approve_exercise_draft(project, "normal_subgroup_02")
            validate_project_exercises(project)

            result = build_exercise_bank(project)

            self.assertEqual(result.total_exercises, 2)
            manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(manifest["schema_version"], 1)
            self.assertEqual([item["exercise_id"] for item in manifest["records"]], [
                "normal_subgroup_01",
                "normal_subgroup_02",
            ])
            summaries = read_exercise_bank(project)
            self.assertEqual([item.exercise_id for item in summaries], [
                "normal_subgroup_01",
                "normal_subgroup_02",
            ])

    def test_exercise_bank_cli_builds_and_prints_status(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = create_project(
                ProjectSpec(topic="Group Theory", path=Path(temp_dir) / "p")
            )
            generate_exercise_drafts(
                project,
                concept="Normal Subgroup",
                source_id="df-1",
                prerequisites=["subgroup", "conjugation"],
                count=5,
            )
            approve_exercise_draft(project, "normal_subgroup_01")
            validate_project_exercises(project)

            build = subprocess.run(
                [sys.executable, "-m", "socrates", "exercise", "bank", "build", "--project", str(project)],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            status = subprocess.run(
                [sys.executable, "-m", "socrates", "exercise", "bank", "status", "--project", str(project)],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(build.returncode, 0, build.stderr)
            self.assertIn("Exercise bank entries: 1", build.stdout)
            self.assertEqual(status.returncode, 0, status.stderr)
            self.assertIn("# Exercise Bank", status.stdout)
            self.assertIn("- normal_subgroup_01 | Normal Subgroup | difficulty 1", status.stdout)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run failing bank tests**

Run:

```powershell
python -m unittest tests.test_exercise_bank
```

Expected before implementation: fail because `socrates.exercise_bank` does not exist.

- [ ] **Step 3: Implement bank dataclasses and builder**

Create `socrates/exercise_bank.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path

from .context import load_project, write_json
from .exercise_schema import parse_exercise_markdown
from .exercises import list_exercises


BANK_MANIFEST = Path("05_exercises") / "exercise_bank_manifest.json"
VALIDATION_MANIFEST = Path("08_evals") / "exercise_validation_manifest.json"


@dataclass(frozen=True)
class ExerciseBankBuildResult:
    total_exercises: int
    manifest_path: Path


@dataclass(frozen=True)
class ExerciseBankSummary:
    exercise_id: str
    concept: str
    difficulty: int
    path: str
    validation_status: str
```

Implement:

```python
def build_exercise_bank(project_path: Path | str) -> ExerciseBankBuildResult:
    context = load_project(project_path)
    validation_by_id = _validation_by_id(context.root)
    approved = [
        summary
        for summary in list_exercises(context.root, status="approved")
        if validation_by_id.get(summary.exercise_id, {}).get("status") == "pass"
    ]
    records = []
    for summary in approved:
        spec = parse_exercise_markdown(context.root / summary.path)
        records.append(
            {
                "exercise_id": summary.exercise_id,
                "concept": spec.concept,
                "difficulty": spec.difficulty,
                "type": spec.exercise_type,
                "path": summary.path,
                "validation_status": "pass",
                "validation_artifact": validation_by_id[summary.exercise_id]["artifact_path"],
            }
        )
    manifest_path = context.root / BANK_MANIFEST
    write_json(
        manifest_path,
        {
            "schema_version": 1,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "total_exercises": len(records),
            "records": records,
        },
    )
    return ExerciseBankBuildResult(total_exercises=len(records), manifest_path=manifest_path)
```

Implement `read_exercise_bank(project_path)` and `_validation_by_id(project_root)`. If the bank manifest is absent, `read_exercise_bank()` returns an empty list. If the manifest JSON is corrupt or has invalid schema, raise `ValueError("invalid exercise_bank_manifest.json")`.

- [ ] **Step 4: Register `exercise bank` CLI commands**

In `socrates/cli.py`, import:

```python
from .exercise_bank import build_exercise_bank, read_exercise_bank
```

In `build_parser()` after `exercise_validate_parser`, add:

```python
    exercise_bank_parser = exercise_subparsers.add_parser(
        "bank",
        help="Build or inspect the approved exercise bank.",
    )
    exercise_bank_subparsers = exercise_bank_parser.add_subparsers(
        dest="exercise_bank_command",
        required=True,
    )
    exercise_bank_build_parser = exercise_bank_subparsers.add_parser(
        "build",
        help="Build the bank manifest from approved, passing validation exercises.",
    )
    exercise_bank_build_parser.add_argument("--project", required=True, help="Socrates project directory.")
    exercise_bank_build_parser.set_defaults(func=_handle_exercise_bank_build)
    exercise_bank_status_parser = exercise_bank_subparsers.add_parser(
        "status",
        help="Show the current exercise bank manifest.",
    )
    exercise_bank_status_parser.add_argument("--project", required=True, help="Socrates project directory.")
    exercise_bank_status_parser.set_defaults(func=_handle_exercise_bank_status)
```

Add handlers:

```python
def _handle_exercise_bank_build(args: argparse.Namespace) -> int:
    try:
        result = build_exercise_bank(args.project)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(f"Exercise bank entries: {result.total_exercises}")
    print(f"Exercise bank manifest: {result.manifest_path}")
    return 0


def _handle_exercise_bank_status(args: argparse.Namespace) -> int:
    try:
        summaries = read_exercise_bank(args.project)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print("# Exercise Bank")
    print("")
    if not summaries:
        print("- none")
        return 0
    for item in summaries:
        print(
            f"- {item.exercise_id} | {item.concept} | "
            f"difficulty {item.difficulty} | {item.path}"
        )
    return 0
```

- [ ] **Step 5: Run bank tests**

Run:

```powershell
python -m unittest tests.test_exercise_bank
git diff --check
```

Expected: tests pass.

- [ ] **Step 6: Commit Task 5**

Use a Lore-style commit message:

```text
Promote only approved validated exercises into the bank

Constraint: Bank membership is a review/readiness surface, not learner grading state.
Confidence: high
Scope-risk: moderate
Tested: python -m unittest tests.test_exercise_bank
```

## Task 6: Quality, Status, Benchmark, and Lifecycle Integration

**Files:**
- Modify: `socrates/quality.py`
- Modify: `socrates/cli.py`
- Test: `tests/test_exercise_quality.py`
- Test: `tests/test_status_quality_summary.py`
- Test: `tests/test_benchmark.py`
- Test: `tests/test_lifecycle_audit.py`

- [ ] **Step 1: Update exercise quality tests for v0.4 validation status**

Add to `tests/test_exercise_quality.py`:

```python
    def test_exercise_check_manifest_includes_v04_validation_status(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = create_project(
                ProjectSpec(topic="Group Theory", path=Path(temp_dir) / "p")
            )
            generate_exercise_drafts(
                project,
                concept="Normal Subgroup",
                source_id="df-1",
                prerequisites=["subgroup", "conjugation"],
                count=5,
            )

            result = subprocess.run(
                [sys.executable, "-m", "socrates", "exercise", "check", "--project", str(project)],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            manifest = json.loads(
                (project / "08_evals" / "exercise_quality_manifest.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(manifest["schema_version"], 1)
            first = manifest["exercises"][0]
            self.assertEqual(first["validation"]["status"], "pass")
            self.assertEqual(first["validation"]["schema_status"], "pass")
            self.assertIn("artifact_path", first["validation"])
```

- [ ] **Step 2: Run failing quality integration test**

Run:

```powershell
python -m unittest tests.test_exercise_quality
```

Expected before implementation: fail because `exercise_quality_manifest.json` has no `validation` block.

- [ ] **Step 3: Reuse validation in quality checks**

In `socrates/quality.py`, import:

```python
from .exercise_validation import validate_exercise
```

In `check_generated_exercise_quality()`, compute validation rows:

```python
validation_rows = [
    validate_exercise(context.root, path.stem)
    for path in exercise_paths
]
```

Pass `validation_rows` into `_exercise_quality_manifest()`, then add a `validation` field in `_exercise_manifest_entry()`:

```python
"validation": {
    "status": validation_row.status,
    "schema_status": "pass" if not validation_row.issues else "fail",
    "issues": list(validation_row.issues),
    "artifact_path": validation_row.artifact_path.relative_to(project_root).as_posix(),
    "report_path": validation_row.report_path.relative_to(project_root).as_posix(),
},
```

Keep the existing string-based quality issues in place for one release. The v0.4 schema parser becomes the source of new structured evidence, while old tests remain protected.

- [ ] **Step 4: Add status lines for exercise validation and bank**

In `socrates/cli.py`, add helpers:

```python
def _read_exercise_validation_status(project_root: Path) -> dict[str, object] | None:
    manifest_path = project_root / "08_evals" / "exercise_validation_manifest.json"
    if not manifest_path.exists():
        return None
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"status": "invalid"}
    if not isinstance(manifest, dict) or manifest.get("schema_version") != 1:
        return {"status": "invalid"}
    checked = manifest.get("checked")
    passed = manifest.get("passed")
    failed = manifest.get("failed")
    if not all(isinstance(value, int) for value in (checked, passed, failed)):
        return {"status": "invalid"}
    return {
        "status": "pass" if failed == 0 and checked > 0 else "fail" if failed else "empty",
        "checked": checked,
        "passed": passed,
        "failed": failed,
    }
```

Print in `_handle_status()`:

```python
print(f"Exercise validation: {_quality_manifest_status_text(exercise_validation_status)}")
print(f"Exercise bank entries: {_count_exercise_bank_entries(context.root)}")
```

- [ ] **Step 5: Update benchmark gate count**

Update `run_project_benchmark()` so `Exercise validation` is a fifth gate:

```python
validation = validate_project_exercises(context.root)
gates = {
    "Ingestion": ingestion.failed == 0 and ingestion.checked > 0,
    "Note quality": note.failed == 0 and note.checked > 0,
    "Exercise quality": exercise.failed == 0 and exercise.checked > 0,
    "Exercise validation": validation.failed == 0 and validation.checked > 0,
    "Tutoring quality": tutoring.status == "pass",
}
```

Add the validation gate entry to `_benchmark_manifest()` with `report_path=validation.report_path` and `manifest_path=validation.manifest_path`.

- [ ] **Step 6: Update lifecycle audit**

In `audit_project_lifecycle()`, add checks:

```python
"Exercise validation": _has_clean_exercise_validation_manifest(context.root),
"Exercise bank": _has_exercise_bank_entries(context.root),
```

`_has_clean_exercise_validation_manifest()` should require schema version 1, `checked > 0`, `passed == checked`, and `failed == 0`.

`_has_exercise_bank_entries()` should require `05_exercises/exercise_bank_manifest.json`, schema version 1, and at least one record whose artifact path exists.

- [ ] **Step 7: Run integration tests**

Run:

```powershell
python -m unittest tests.test_exercise_quality tests.test_status_quality_summary tests.test_benchmark tests.test_lifecycle_audit
git diff --check
```

Expected: tests pass after updating expected benchmark gate counts from `4/4` to `5/5` where appropriate.

- [ ] **Step 8: Commit Task 6**

Use a Lore-style commit message:

```text
Make v04 exercise validation visible in quality gates

Constraint: Existing exercise quality output remains compatible while validation becomes structured evidence.
Confidence: medium
Scope-risk: moderate
Tested: python -m unittest tests.test_exercise_quality tests.test_status_quality_summary tests.test_benchmark tests.test_lifecycle_audit
```

## Task 7: v0.4 End-to-End Regression

**Files:**
- Create: `tests/test_v04_exercise_flow.py`

- [ ] **Step 1: Write v0.4 flow test**

Create `tests/test_v04_exercise_flow.py`:

```python
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from socrates.artifacts import generate_atomic_note_draft, generate_exercise_drafts
from socrates.exercises import approve_exercise_draft
from socrates.kb import build_reference_kb
from socrates.project import ProjectSpec, create_project
from socrates.tutoring import run_scripted_tutoring_session


REPO_ROOT = Path(__file__).resolve().parents[1]


class V04ExerciseFlowTests(unittest.TestCase):
    def test_v04_exercise_validation_bank_and_benchmark_flow(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            project = create_project(ProjectSpec(topic="Group Theory", path=root / "p"))
            curated = project / "01_references" / "curated" / "normal_subgroups.curated.md"
            curated.write_text(
                "# Group Theory\n"
                "## Source Metadata\n"
                "- source_id: df-1\n"
                "- title: Normal Subgroups\n"
                "- role: lecture_notes\n"
                "### Definition: Normal Subgroup\n"
                "A normal subgroup is stable under conjugation.\n"
                "Depends: subgroup, conjugation\n\n"
                "### Counterexample: Non-normal Subgroup\n"
                "A subgroup can fail to be stable under conjugation.\n"
                "Counterexample to: normal_subgroup\n",
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
                    "- What condition distinguishes normality from centrality?\n"
                ),
                source_id="df-1",
            )
            generate_exercise_drafts(
                project,
                concept="Normal Subgroup",
                source_id="df-1",
                prerequisites=["subgroup", "conjugation"],
                count=5,
            )
            approve_exercise_draft(project, "normal_subgroup_01")
            script = root / "session.script"
            script.write_text(
                "topic: Normal Subgroup\n"
                "goal: Understand normality.\n"
                "question: What does normality require?\n"
                "hint: Check conjugation invariance.\n"
                "hint: Compare gNg^-1=N with elementwise commutativity.\n"
                "attempt: It requires gNg^-1=N.\n"
                "next: Prove kernels are normal.\n",
                encoding="utf-8",
                newline="\n",
            )
            run_scripted_tutoring_session(project, script, session_id="session_0001")

            validate = subprocess.run(
                [sys.executable, "-m", "socrates", "exercise", "validate", "--project", str(project), "--all"],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            bank = subprocess.run(
                [sys.executable, "-m", "socrates", "exercise", "bank", "build", "--project", str(project)],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            benchmark = subprocess.run(
                [sys.executable, "-m", "socrates", "benchmark", "run", "--project", str(project), "--session-id", "session_0001"],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(validate.returncode, 0, validate.stderr)
            self.assertIn("Validated 5 exercise drafts: 5 passed, 0 failed", validate.stdout)
            self.assertEqual(bank.returncode, 0, bank.stderr)
            self.assertIn("Exercise bank entries: 1", bank.stdout)
            self.assertEqual(benchmark.returncode, 0, benchmark.stderr)
            self.assertIn("Benchmark passed 5/5 gates", benchmark.stdout)
            self.assertTrue((project / "05_exercises" / "exercise_bank_manifest.json").exists())
            self.assertTrue((project / "08_evals" / "exercise_validation_manifest.json").exists())


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run failing v0.4 flow test**

Run:

```powershell
python -m unittest tests.test_v04_exercise_flow
```

Expected before completing Tasks 1-6: fail at missing commands or benchmark gate count.

- [ ] **Step 3: Fix integration mismatches found by the flow**

Use the failure output to correct only v0.4 integration issues. Do not weaken the assertions. Common fixes are import order, CLI handler registration, benchmark expected gates, and validation manifest paths.

- [ ] **Step 4: Run v0.4 targeted tests**

Run:

```powershell
python -m unittest tests.test_exercise_schema tests.test_exercise_validation tests.test_exercise_bank tests.test_v04_exercise_flow
git diff --check
```

Expected: all v0.4 tests pass and no whitespace errors.

- [ ] **Step 5: Commit Task 7**

Use a Lore-style commit message:

```text
Protect the v04 exercise-bank flow end to end

Constraint: End-to-end v0.4 readiness requires validation, bank build, and benchmark evidence.
Confidence: high
Scope-risk: narrow
Tested: python -m unittest tests.test_exercise_schema tests.test_exercise_validation tests.test_exercise_bank tests.test_v04_exercise_flow
```

## Task 8: Documentation and Closure Notes

**Files:**
- Modify: `README.md`
- Modify: `docs/README.md`
- Modify: `docs/development_log.md`
- Modify: `docs/development_roadmap.md`

- [ ] **Step 1: Update README v0.4 capability boundary**

Add to `README.md` under current capabilities:

```text
- v0.4-alpha exercise-bank validation: structured exercise schema checks,
  per-exercise validation reports, approved exercise-bank manifest, and
  benchmark visibility for exercise validation.
```

Add to boundaries:

```text
- v0.4 validation is conservative evidence, not formal mathematical proof.
  Counterexample search is advisory and depends on the current Reference KB.
```

- [ ] **Step 2: Update docs index**

In `docs/README.md`, add:

```markdown
- `superpowers/plans/2026-06-04-v04-exercise-bank-validation.md`: executable
  v0.4 plan for structured exercise validation and bank readiness.
```

- [ ] **Step 3: Update development log**

Append:

```markdown
## v0.4 Exercise bank and validation alpha

- Added structured validation for generated exercise Markdown without replacing the reviewable Markdown artifact.
- Added per-exercise validation reports and `exercise_validation_manifest.json`.
- Added an approved exercise-bank manifest that includes only human-approved exercises with passing validation.
- Added benchmark/lifecycle/status visibility for exercise validation and exercise-bank readiness.
- Preserved the boundary: validation evidence does not grade learner attempts and does not prove mathematical correctness.
```

- [ ] **Step 4: Update roadmap**

Under v0.4, mark the alpha scope complete only after Tasks 1-7 pass:

```markdown
当前状态（2026-06-04）：

- 已完成 v0.4-alpha exercise bank validation：exercise schema、solution outline schema、hint ladder、rubric sum checks、per-exercise validation artifacts、exercise bank manifest。
- Counterexample search is integrated as advisory Reference KB evidence; no-match is not treated as proof.
- Formal math verification and LLM judge remain future work.
```

- [ ] **Step 5: Run documentation and full deterministic gates**

Run:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\check.ps1
bash scripts/check.sh
git diff --check
```

Expected: all tests pass; no whitespace errors; no `.env` content appears in tracked docs.

- [ ] **Step 6: Final commit**

Use a Lore-style commit message:

```text
Document the v04 exercise-bank validation boundary

Constraint: Documentation must not imply validation is formal mathematical proof.
Confidence: high
Scope-risk: narrow
Tested: powershell -ExecutionPolicy Bypass -File scripts\check.ps1
Tested: bash scripts/check.sh
```

## Final Verification Checklist

- [ ] `python -m unittest tests.test_exercise_schema` passes.
- [ ] `python -m unittest tests.test_exercise_validation` passes.
- [ ] `python -m unittest tests.test_exercise_bank` passes.
- [ ] `python -m unittest tests.test_v04_exercise_flow` passes.
- [ ] `python -m unittest tests.test_exercise_quality tests.test_status_quality_summary tests.test_benchmark tests.test_lifecycle_audit` passes.
- [ ] `python -m unittest discover -s tests` passes.
- [ ] `python -m compileall socrates` passes.
- [ ] `git diff --check` passes.
- [ ] `powershell -ExecutionPolicy Bypass -File scripts\check.ps1` passes.
- [ ] `bash scripts/check.sh` passes.
- [ ] `python -m socrates exercise validate --project <project> --all` writes `08_evals/exercise_validation_manifest.json`.
- [ ] `python -m socrates exercise bank build --project <project>` writes `05_exercises/exercise_bank_manifest.json`.
- [ ] `python -m socrates benchmark run --project <project> --session-id session_0001` reports 5 gates after v0.4 integration.
- [ ] `.env` remains ignored and unstaged.

## Definition of Done

v0.4-alpha is complete when Socrates can:

1. Parse generated exercise Markdown into a stable structured schema.
2. Validate exercise frontmatter, sections, hint ladder, solution outline, rubric totals, prerequisites, concept tags, and common mistakes.
3. Persist per-exercise validation reports and a project validation manifest.
4. Build an exercise-bank manifest containing only human-approved exercises with passing validation.
5. Show validation and exercise-bank readiness in CLI status, lifecycle audit, and benchmark output.
6. Preserve the v0.3 LLM trust boundary and offline deterministic gates.

## Out of Scope for This Plan

- Formal proof checking for generated exercises.
- LLM judge scoring.
- Autonomous exercise generation from live LLM calls.
- OCR/PDF ingestion backend.
- Vector embeddings or semantic retrieval.
- UI, TUI, web app, or Obsidian plugin.
- New third-party runtime dependencies.

## Self-Review

- Spec coverage: roadmap v0.4 items map to Tasks 1-7. Exercise schema and solution schema are covered by `exercise_schema.py`; hint ladder and rubric checks are covered by schema validation; exercise quality checker and counterexample search evidence are covered by validation and quality integration; bank readiness is covered by `exercise_bank.py`.
- Placeholder scan: every code-changing step names concrete files, functions, tests, and commands; no unresolved placeholder markers remain.
- Type consistency: public names are consistent across tasks: `ExerciseSpec`, `validate_exercise_spec`, `validate_exercise`, `validate_project_exercises`, `build_exercise_bank`, and `read_exercise_bank`.

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-06-04-v04-exercise-bank-validation.md`.

Recommended execution mode: Subagent-Driven. Dispatch one fresh subagent per task, review after each task, and run the task-local test command before moving on.

Alternative execution mode: Inline Execution. Use `superpowers:executing-plans`, complete tasks in order, and stop at each commit boundary for verification.

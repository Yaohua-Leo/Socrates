"""Deterministic temporary-project lifecycle canary for Socrates."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import shutil
import tempfile

from .artifacts import (
    generate_atomic_note_draft,
    generate_exercise_drafts,
    generate_misconception_note_drafts,
)
from .context import load_project
from .dashboard import build_study_dashboard_payload
from .exercise_bank import build_exercise_bank
from .exercises import (
    approve_exercise_draft,
    grade_exercise_attempt,
    list_exercises,
    record_exercise_attempt,
)
from .kb import build_reference_kb, reference_kb_status
from .notes import export_reviewed_notes_to_obsidian, list_atomic_notes, review_atomic_note
from .multi_session import run_multi_session_regression
from .obsidian import obsidian_export_count
from .planning import create_learning_plan
from .project import ProjectSpec, create_project
from .quality import audit_project_lifecycle, run_project_benchmark
from .reports import generate_monthly_report, generate_weekly_report
from .resume import build_project_resume_payload
from .state import (
    LearningStatePatch,
    MistakeRecord,
    build_review_schedule,
    update_learning_state,
)
from .study_brief import generate_study_brief
from .tool_verification import generate_lean_statement_skeleton
from .tutoring import list_tutoring_sessions, run_scripted_tutoring_session
from .workflow import close_tutoring_session


CANARY_QUALITY_BOUNDARY = "deterministic_mvp_lifecycle_canary"
CANARY_SCENARIO = "normal_subgroup_mvp"


class CanaryArtifactError(ValueError):
    """Raised when the requested canary artifact bundle cannot be written."""


@dataclass(frozen=True)
class MvpLifecycleCanaryResult:
    """Structured result for the MVP lifecycle canary."""

    status: str
    lifecycle: dict[str, int]
    artifacts: dict[str, int]
    returning_learner: dict[str, object]
    checks: tuple[dict[str, str], ...]
    temporary_project_cleaned: bool
    artifact_bundle: dict[str, object]

    def to_payload(self) -> dict[str, object]:
        """Return the JSON-serializable canary payload."""

        return {
            "schema_version": 1,
            "quality_boundary": CANARY_QUALITY_BOUNDARY,
            "scenario": CANARY_SCENARIO,
            "status": self.status,
            "lifecycle": self.lifecycle,
            "artifacts": self.artifacts,
            "returning_learner": self.returning_learner,
            "checks": list(self.checks),
            "temporary_project": {
                "cleaned": self.temporary_project_cleaned,
            },
            "artifact_bundle": self.artifact_bundle,
        }


def run_mvp_lifecycle_canary(artifact_dir: Path | None = None) -> MvpLifecycleCanaryResult:
    """Run the deterministic MVP scenario in a temporary project."""

    artifact_bundle: dict[str, object] = {"written": False}
    with tempfile.TemporaryDirectory(prefix="socrates-canary-") as temp_dir:
        root = Path(temp_dir)
        project = _build_canary_project(root)
        audit = audit_project_lifecycle(project)
        lifecycle = {
            "passed_checks": audit.passed_checks,
            "total_checks": audit.total_checks,
        }
        status = "pass" if audit.passed_checks == audit.total_checks else "fail"
        generate_study_brief(project)
        artifacts = _artifact_counts(project)
        returning_learner = _returning_learner_evidence(project)
        checks = _read_audit_checks(audit.report_path)
        if artifact_dir is not None:
            artifact_bundle = _copy_artifact_bundle(artifact_dir, project)
    result = MvpLifecycleCanaryResult(
        status=status,
        lifecycle=lifecycle,
        artifacts=artifacts,
        returning_learner=returning_learner,
        checks=checks,
        temporary_project_cleaned=not root.exists(),
        artifact_bundle=artifact_bundle,
    )
    if artifact_dir is not None:
        _write_artifact_report(result)
    return result


def format_mvp_lifecycle_canary(result: MvpLifecycleCanaryResult) -> str:
    """Render a human-facing canary summary."""

    artifacts = result.artifacts
    lines = [
        f"MVP lifecycle canary: {result.status}",
        f"Scenario: {CANARY_SCENARIO}",
        (
            "Lifecycle audit: "
            f"{result.lifecycle['passed_checks']}/{result.lifecycle['total_checks']}"
        ),
        (
            "Artifacts: "
            f"kb={artifacts['kb_objects']}, "
            f"notes={artifacts['reviewed_notes']}, "
            f"exercises={artifacts['generated_exercises']}, "
            f"briefs={artifacts['study_briefs']}, "
            f"reports={artifacts['learning_reports']}"
        ),
        (
            "Returning learner: "
            f"resume={result.returning_learner['resume_state']}, "
            f"brief={result.returning_learner['study_brief']}"
        ),
        "Temporary project: cleaned",
    ]
    if result.artifact_bundle.get("written"):
        lines.append(f"Artifact bundle: {result.artifact_bundle['root']}")
    return "\n".join(lines)


def _build_canary_project(root: Path) -> Path:
    project = create_project(
        ProjectSpec(
            topic="Group Theory",
            path=root / "group_theory",
            goal="Prepare for quotient groups.",
        )
    )
    _write_curated_reference(project)
    build_reference_kb(project)
    create_learning_plan(project)
    _run_sessions(root, project)
    _write_notes(project)
    _write_exercises(root, project)
    _write_learning_state(project)
    generate_lean_statement_skeleton(project, object_id="normal_subgroup")
    generate_weekly_report(project)
    generate_monthly_report(project)
    close_tutoring_session(
        project,
        session_id="session_0001",
        next_session_id="session_0002",
    )
    run_multi_session_regression(project)
    run_project_benchmark(project, session_id="session_0001")
    build_exercise_bank(project)
    return project


def _write_curated_reference(project: Path) -> None:
    curated = project / "01_references" / "curated" / "normal_subgroups.curated.md"
    curated.write_text(
        "# Group Theory\n"
        "## Source Metadata\n"
        "- source_id: df-1\n"
        "- title: Normality Notes\n"
        "- role: lecture_notes\n"
        "## Normal Subgroups\n"
        "### Definition: Normal Subgroup\n"
        "A normal subgroup is stable under conjugation.\n"
        "Depends: subgroup, conjugation\n",
        encoding="utf-8",
        newline="\n",
    )


def _run_sessions(root: Path, project: Path) -> None:
    script_1 = root / "session_0001.script"
    script_1.write_text(
        "topic: Normal Subgroup\n"
        "question: What must you check to prove normality?\n"
        "hint: Track conjugation invariance.\n"
        "hint: Compare normality with centrality.\n"
        "attempt: Show gNg^-1=N.\n"
        "next: Prove kernels are normal.\n",
        encoding="utf-8",
        newline="\n",
    )
    run_scripted_tutoring_session(project, script_1, session_id="session_0001")

    script_2 = root / "session_0002.script"
    script_2.write_text(
        "topic: Kernel Normality\n"
        "question: Why is a kernel normal?\n"
        "hint: Use the homomorphism property.\n"
        "hint: Compute phi(gkg^-1).\n"
        "attempt: phi(gkg^-1)=e, so gkg^-1 is in the kernel.\n"
        "next: Compare quotient groups with cosets.\n",
        encoding="utf-8",
        newline="\n",
    )
    run_scripted_tutoring_session(project, script_2, session_id="session_0002")


def _write_notes(project: Path) -> None:
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
    review_atomic_note(project, "normal_subgroup")
    export_reviewed_notes_to_obsidian(project)


def _write_exercises(root: Path, project: Path) -> None:
    generate_exercise_drafts(
        project,
        concept="Normal Subgroup",
        source_id="df-1",
        prerequisites=["subgroup", "conjugation"],
        count=5,
    )
    answer = root / "answer.md"
    feedback = root / "feedback.md"
    answer.write_text("Use conjugation invariance.\n", encoding="utf-8", newline="\n")
    feedback.write_text("Good core idea.\n", encoding="utf-8", newline="\n")
    approve_exercise_draft(project, "normal_subgroup_01")
    record_exercise_attempt(project, "normal_subgroup_01", answer)
    grade_exercise_attempt(project, "normal_subgroup_01_attempt_001", 0.8, feedback)


def _write_learning_state(project: Path) -> None:
    context = load_project(project)
    update_learning_state(
        context,
        LearningStatePatch(
            concept_mastery={"quotient_group": 0.42},
            mistakes=[
                MistakeRecord(
                    session_id="session_0001",
                    concept="normal_subgroup",
                    misconception_id="normal_equals_central",
                    user_answer="Normal means central.",
                    analysis="Confuses normality with centrality.",
                    repair_suggestion="Compare gNg^-1 = N with gn = ng.",
                )
            ],
        ),
    )
    build_review_schedule(context)
    generate_misconception_note_drafts(project)
    review_atomic_note(project, "normal_equals_central")
    export_reviewed_notes_to_obsidian(project)


def _artifact_counts(project: Path) -> dict[str, int]:
    kb_status = reference_kb_status(project)
    notes = list_atomic_notes(project)
    return {
        "curated_references": _markdown_count(project / "01_references" / "curated"),
        "kb_objects": kb_status.object_count,
        "tutoring_sessions": len(list_tutoring_sessions(project)),
        "reviewed_notes": sum(1 for note in notes if note.status in {"reviewed", "exported"}),
        "obsidian_exports": obsidian_export_count(project),
        "generated_exercises": len(list_exercises(project)),
        "attempted_exercises": _markdown_count(project / "05_exercises" / "attempted"),
        "graded_exercises": _markdown_count(project / "05_exercises" / "graded"),
        "learning_reports": _markdown_count(project / "07_exports" / "reports"),
        "study_briefs": _markdown_count(project / "07_exports" / "briefs"),
        "study_brief_manifests": _json_count(project / "07_exports" / "briefs"),
    }


def _returning_learner_evidence(project: Path) -> dict[str, object]:
    dashboard = build_study_dashboard_payload(project)
    resume = build_project_resume_payload(project)
    snapshot = dashboard["snapshot"] if isinstance(dashboard["snapshot"], dict) else {}
    return {
        "study_brief": resume["study_brief"],
        "dashboard_study_brief": snapshot.get("study_brief", "invalid"),
        "resume_state": resume["resume_state"],
        "recommended_command": resume["recommended_command"],
        "current_next_action": resume["current_next_action"],
        "study_brief_path": resume["study_brief_path"],
    }


def _read_audit_checks(report_path: Path) -> tuple[dict[str, str], ...]:
    checks: list[dict[str, str]] = []
    if not report_path.exists():
        return tuple(checks)
    for raw_line in report_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line.startswith("- ") or ": " not in line:
            continue
        name, status = line.removeprefix("- ").split(": ", 1)
        checks.append({"name": name, "status": status})
    return tuple(checks)


def _markdown_count(path: Path) -> int:
    if not path.exists():
        return 0
    return len(list(path.glob("*.md")))


def _json_count(path: Path) -> int:
    if not path.exists():
        return 0
    return len(list(path.glob("*.json")))


def _copy_artifact_bundle(artifact_dir: Path, project: Path) -> dict[str, object]:
    root = artifact_dir
    if root.exists() and any(root.iterdir()):
        raise CanaryArtifactError(f"artifact directory is not empty: {root}")
    root.mkdir(parents=True, exist_ok=True)
    project_path = root / "project"
    shutil.copytree(project, project_path)
    return {
        "written": True,
        "root": str(root),
        "project_path": str(project_path),
        "report_path": str(root / "canary_report.json"),
    }


def _write_artifact_report(result: MvpLifecycleCanaryResult) -> None:
    report_path = Path(str(result.artifact_bundle["report_path"]))
    report_path.write_text(
        json.dumps(result.to_payload(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )

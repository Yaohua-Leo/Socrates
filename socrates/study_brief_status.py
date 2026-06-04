"""Status reader for generated Socrates study briefs."""

from __future__ import annotations

from dataclasses import dataclass
from json import JSONDecodeError
from pathlib import Path

from .context import load_project, read_json
from .learning_queue import QueueItem, collect_learning_queue, priority_queue_items


STUDY_BRIEF_RELATIVE_PATH = Path("07_exports") / "briefs" / "study_brief.md"
STUDY_BRIEF_MANIFEST_RELATIVE_PATH = (
    Path("07_exports") / "briefs" / "study_brief_manifest.json"
)
STUDY_BRIEF_QUALITY_BOUNDARY = "deterministic_study_brief"


@dataclass(frozen=True)
class StudyBriefStatus:
    """Freshness summary for one generated study-start brief."""

    status: str
    path: str
    recorded_next_action: str
    current_next_action: str


def summarize_study_brief(project_path: Path | str) -> StudyBriefStatus:
    """Compare the brief's recorded next action with the current queue action."""

    context = load_project(project_path)
    brief_path = context.root / STUDY_BRIEF_RELATIVE_PATH
    manifest_path = context.root / STUDY_BRIEF_MANIFEST_RELATIVE_PATH
    relative_path = STUDY_BRIEF_RELATIVE_PATH.as_posix()
    current_next_action = _current_next_action(context.root)
    if manifest_path.exists():
        return _manifest_status(
            manifest_path=manifest_path,
            brief_path=brief_path,
            current_next_action=current_next_action,
            relative_path=relative_path,
        )
    if not brief_path.exists():
        return StudyBriefStatus(
            status="not_run",
            path=relative_path,
            recorded_next_action="none",
            current_next_action=current_next_action,
        )
    try:
        text = brief_path.read_text(encoding="utf-8")
    except OSError:
        return StudyBriefStatus(
            status="invalid",
            path=relative_path,
            recorded_next_action="invalid",
            current_next_action=current_next_action,
        )
    recorded_next_action = _recorded_next_action(text)
    if recorded_next_action is None:
        return StudyBriefStatus(
            status="invalid",
            path=relative_path,
            recorded_next_action="invalid",
            current_next_action=current_next_action,
        )
    status = "current" if recorded_next_action == current_next_action else "stale"
    return StudyBriefStatus(
        status=status,
        path=relative_path,
        recorded_next_action=recorded_next_action,
        current_next_action=current_next_action,
    )


def _manifest_status(
    *,
    manifest_path: Path,
    brief_path: Path,
    current_next_action: str,
    relative_path: str,
) -> StudyBriefStatus:
    if not brief_path.exists():
        return _invalid_status(relative_path=relative_path, current_next_action=current_next_action)
    try:
        manifest = read_json(manifest_path)
    except (OSError, JSONDecodeError):
        return _invalid_status(relative_path=relative_path, current_next_action=current_next_action)
    if not isinstance(manifest, dict):
        return _invalid_status(relative_path=relative_path, current_next_action=current_next_action)
    recorded_next_action = manifest.get("recorded_next_action")
    if (
        manifest.get("schema_version") != 1
        or manifest.get("quality_boundary") != STUDY_BRIEF_QUALITY_BOUNDARY
        or manifest.get("status") != "generated"
        or manifest.get("brief_path") != STUDY_BRIEF_RELATIVE_PATH.as_posix()
        or not isinstance(recorded_next_action, str)
        or not isinstance(manifest.get("action_type"), str)
    ):
        return _invalid_status(relative_path=relative_path, current_next_action=current_next_action)
    status = "current" if recorded_next_action == current_next_action else "stale"
    return StudyBriefStatus(
        status=status,
        path=relative_path,
        recorded_next_action=recorded_next_action,
        current_next_action=current_next_action,
    )


def _invalid_status(*, relative_path: str, current_next_action: str) -> StudyBriefStatus:
    return StudyBriefStatus(
        status="invalid",
        path=relative_path,
        recorded_next_action="invalid",
        current_next_action=current_next_action,
    )


def _current_next_action(project_path: Path) -> str:
    actions = priority_queue_items(collect_learning_queue(project_path))
    if not actions:
        return "none"
    return _action_line(actions[0])


def _action_line(item: QueueItem) -> str:
    line = f"{item.item_id} | {item.path}"
    if item.detail:
        line += f" | {item.detail}"
    return line


def _recorded_next_action(text: str) -> str | None:
    prefix = "- Next action: "
    for line in text.splitlines():
        if line.startswith(prefix):
            return line.removeprefix(prefix)
    return None

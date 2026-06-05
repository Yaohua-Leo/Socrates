"""Read-only product readiness audit for the Socrates v1.0 goal."""

from __future__ import annotations


PRODUCT_READINESS_QUALITY_BOUNDARY = "deterministic_product_readiness_audit"
PRODUCT_GOAL = "v1.0_math_learning_agent"
CURRENT_VERSION = "v0.59-alpha"


def build_product_readiness_payload() -> dict[str, object]:
    """Build the deterministic product capability/gap payload."""

    capabilities = _capabilities()
    return {
        "schema_version": 1,
        "quality_boundary": PRODUCT_READINESS_QUALITY_BOUNDARY,
        "product_goal": PRODUCT_GOAL,
        "current_version": CURRENT_VERSION,
        "overall_status": "not_v1_ready",
        "summary": _summary(capabilities),
        "capabilities": capabilities,
        "decision_points": _decision_points(),
    }


def format_product_readiness(payload: dict[str, object] | None = None) -> str:
    """Render the product readiness audit as compact Markdown."""

    record = payload if payload is not None else build_product_readiness_payload()
    summary = record["summary"] if isinstance(record["summary"], dict) else {}
    capabilities = record["capabilities"] if isinstance(record["capabilities"], list) else []
    decision_points = (
        record["decision_points"] if isinstance(record["decision_points"], list) else []
    )
    lines = [
        "# Product Readiness Audit",
        "",
        "## Snapshot",
        "",
        f"- Current version: {record['current_version']}",
        f"- Product goal: {record['product_goal']}",
        f"- Overall status: {record['overall_status']}",
        f"- Capabilities: {summary.get('capability_count', 0)}",
        f"- Implemented: {summary.get('implemented', 0)}",
        f"- Partial: {summary.get('partial', 0)}",
        f"- Missing: {summary.get('missing', 0)}",
        f"- Decision required: {summary.get('decision_required', 0)}",
        "",
        "## Capability Map",
        "",
        *_capability_lines(capabilities),
        "",
        "## Decision Points",
        "",
        *_decision_point_lines(decision_points),
        "",
        "## Boundary",
        "",
        (
            "This audit is a deterministic repo-level capability map. It does "
            "not inspect or mutate a learner project, run OCR, call an LLM, "
            "generate reports, validate real learner outcomes, or prove v1.0 "
            "completion."
        ),
        "",
    ]
    return "\n".join(lines)


def _summary(capabilities: list[dict[str, object]]) -> dict[str, int]:
    statuses = [str(item["status"]) for item in capabilities]
    return {
        "capability_count": len(capabilities),
        "implemented": statuses.count("implemented"),
        "partial": statuses.count("partial"),
        "missing": statuses.count("missing"),
        "decision_required": len(_decision_points()),
    }


def _capabilities() -> list[dict[str, object]]:
    return [
        {
            "id": "project_initialization",
            "final_goal": "Create a durable independent learning project from topic, path, and goal.",
            "status": "implemented",
            "evidence": [
                "python -m socrates init",
                "ProjectSpec/create_project",
                "standard project directory and metadata files",
            ],
            "gaps": [],
        },
        {
            "id": "reference_discovery_management",
            "final_goal": "Help establish and manage reference lists across local, online, and scholarly sources.",
            "status": "partial",
            "evidence": [
                "python -m socrates import",
                "python -m socrates sources list",
                "source_registry.yaml",
            ],
            "gaps": [
                "topic-based textbook, web/arXiv discovery is not implemented",
                "online reference ranking and source recommendation are not implemented",
            ],
        },
        {
            "id": "literature_cleaning_structuring",
            "final_goal": "Convert, clean, curate, and structure mathematical references into trustworthy KB evidence.",
            "status": "partial",
            "evidence": [
                "python -m socrates sources attach-conversion",
                "python -m socrates curate",
                "python -m socrates kb build",
                "Reference KB provenance checks",
            ],
            "gaps": [
                "built-in OCR/PDF backend is not implemented",
                "MinerU/Mathpix/PDF parser integration is not implemented",
                "formula and cross-reference extraction remain bounded by curated Markdown input",
            ],
        },
        {
            "id": "learning_plan_design",
            "final_goal": "Design long-term and short-term learning plans with session goals and dependencies.",
            "status": "partial",
            "evidence": [
                "python -m socrates plan",
                "python -m socrates session plan-next",
                "dependency graph evidence from Reference KB",
            ],
            "gaps": [
                "interactive plan negotiation is not implemented",
                "provider-assisted plan critique remains review-only and limited",
            ],
        },
        {
            "id": "guided_teaching",
            "final_goal": "Run Socratic tutoring with diagnosis, hints, feedback, and follow-up.",
            "status": "partial",
            "evidence": [
                "python -m socrates teach --script",
                "session transcripts and summaries",
                "review-only LLM next-question drafts",
            ],
            "gaps": [
                "autonomous LLM tutoring loop is not implemented",
                "live adaptive diagnosis remains outside deterministic default gates",
            ],
        },
        {
            "id": "personal_kb_capture",
            "final_goal": "Capture reviewed atomic notes into a durable personal mathematics knowledge base.",
            "status": "partial",
            "evidence": [
                "python -m socrates note review",
                "python -m socrates note export-obsidian",
                "Obsidian export manifests and stale-export cleanup",
            ],
            "gaps": [
                "user-facing review UX is CLI-only",
                "cross-project personal KB browsing is limited",
            ],
        },
        {
            "id": "exercise_generation",
            "final_goal": "Generate exercises from current content, misconceptions, and review needs.",
            "status": "partial",
            "evidence": [
                "python -m socrates review exercises",
                "python -m socrates exercise validate",
                "python -m socrates exercise bank build",
            ],
            "gaps": [
                "exercise correctness still requires review evidence and human approval",
                "adaptive generation from live learner interaction is incomplete",
            ],
        },
        {
            "id": "learning_state_modeling",
            "final_goal": "Maintain long-term mastery, proof-skill, review, and progress state.",
            "status": "partial",
            "evidence": [
                "learning_state.json",
                "python -m socrates review mastery --json",
                "python -m socrates review due --json",
                "risk/focus/trend report summaries",
            ],
            "gaps": [
                "state updates are deterministic artifacts, not validated learner-outcome models",
                "long-term human usage calibration is not complete",
            ],
        },
        {
            "id": "misconception_bank",
            "final_goal": "Track misconceptions, repair suggestions, and resolved misconception history.",
            "status": "partial",
            "evidence": [
                "mistake_bank.md",
                "python -m socrates review misconceptions --json",
                "python -m socrates review resolve --dry-run --json",
            ],
            "gaps": [
                "misconception diagnosis is not fully autonomous",
                "repair effectiveness is not validated from real learner outcomes",
            ],
        },
        {
            "id": "verification_evaluation",
            "final_goal": "Evaluate reference ingestion, notes, exercises, tutoring, and generated artifacts.",
            "status": "partial",
            "evidence": [
                "python -m socrates lifecycle audit",
                "python -m socrates lifecycle canary --json",
                "python -m socrates benchmark run",
                "quality manifests and review-only LLM judge drafts",
            ],
            "gaps": [
                "trusted LLM judge is not implemented",
                "formal proof correctness is not guaranteed",
                "real long-term learner validation remains incomplete",
            ],
        },
    ]


def _decision_points() -> list[dict[str, object]]:
    return [
        {
            "id": "next_major_product_lane",
            "reason": (
                "The remaining v1.0 gaps branch into different product surfaces "
                "with different cost and risk profiles."
            ),
            "options": [
                "ocr_pdf_backend",
                "autonomous_llm_tutoring",
                "ui_plugin_surface",
                "real_long_term_validation",
            ],
        }
    ]


def _capability_lines(capabilities: list[object]) -> list[str]:
    if not capabilities:
        return ["- none"]
    lines: list[str] = []
    for item in capabilities:
        record = item if isinstance(item, dict) else {}
        gaps = record.get("gaps", [])
        gap_count = len(gaps) if isinstance(gaps, list) else 0
        lines.append(f"- {record.get('id', '')} | {record.get('status', '')} | gaps={gap_count}")
    return lines


def _decision_point_lines(decision_points: list[object]) -> list[str]:
    if not decision_points:
        return ["- none"]
    lines: list[str] = []
    for item in decision_points:
        record = item if isinstance(item, dict) else {}
        options = record.get("options", [])
        option_text = ", ".join(str(option) for option in options) if isinstance(options, list) else ""
        lines.append(f"- {record.get('id', '')}: {option_text}")
    return lines

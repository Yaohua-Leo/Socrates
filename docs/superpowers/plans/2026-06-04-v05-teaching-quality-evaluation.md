# v05 Teaching Quality Evaluation Implementation Plan
> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship the v0.5 roadmap item: a project can evaluate its own teaching behavior with persisted rubrics and a session score report.

**Architecture:** Reuse existing deterministic quality checks for ingestion, notes, exercises, exercise validation, and tutoring sessions. Add a session-level scoring layer that composes those persisted manifests into one report and manifest without mutating learning state or promoting advisory checks into mathematical proof.

**Tech Stack:** Python standard library, existing Socrates CLI, unittest, Markdown/JSON artifacts under `08_evals/`.

---

## Scope

- Add a first-class session score report for one tutoring session.
- Expose it through `socrates session score --project ... --session-id ...`.
- Include session scoring in `status`, project summary snapshots, and lifecycle audit.
- Keep all checks deterministic and dependency-free.
- Preserve the boundary: these are heuristic/advisory quality gates, not formal verification or automatic approval.

## Data Contract

Write:

- `08_evals/session_score_report.md`
- `08_evals/session_score_manifest.json`

Manifest shape:

```json
{
  "schema_version": 1,
  "session_id": "session_0001",
  "score": 100,
  "passed_gates": 5,
  "total_gates": 5,
  "status": "pass",
  "gates": [
    {
      "name": "Tutoring quality",
      "passed": true,
      "score": 100,
      "checked": 1,
      "failed": 0,
      "report_path": "08_evals/tutoring_eval.md",
      "manifest_path": "08_evals/tutoring_quality_manifest.json"
    }
  ]
}
```

## Tasks

- [ ] Add tests for `session score` writing report and manifest from a complete learning fixture.
- [ ] Add tests for conservative status text when no session score report exists or its manifest is invalid.
- [ ] Add lifecycle audit expectations for a required, fresh, passing session score report.
- [ ] Implement session score composition in a focused module.
- [ ] Wire CLI parser and handlers.
- [ ] Add status/project-summary/lifecycle integration.
- [ ] Update README, docs index, roadmap, and development log for v0.5.
- [ ] Update `D:\llmwiki` with the reusable v05 decision.
- [ ] Run targeted tests, full unittest discovery, compileall, and repository check scripts.
- [ ] Commit with Lore protocol.

## Validation Commands

```powershell
python -m unittest tests.test_session_score
python -m unittest tests.test_tutoring_quality tests.test_status_quality_summary tests.test_reports tests.test_lifecycle_audit tests.test_benchmark
python -m unittest discover -s tests
python -m compileall socrates
git diff --check
powershell -ExecutionPolicy Bypass -File scripts\check.ps1
bash scripts/check.sh
```

## Stop Condition

v05 is complete when a complete learning fixture can run `socrates session score`, the generated manifest/report are reflected in status/project summary/lifecycle audit, the full test suite passes, docs and `llmwiki` record the quality-boundary decision, and a Lore commit is created.

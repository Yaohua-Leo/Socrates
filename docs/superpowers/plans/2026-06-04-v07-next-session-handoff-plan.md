# v0.7 Next Session Handoff Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a deterministic next-session handoff planner that turns due reviews, prior session artifacts, queue state, and Reference KB context into a reviewable plan for the next teaching session.

**Architecture:** Extend `socrates.planning` with `create_next_session_plan(...)`, keeping it deterministic and offline. Surface it through `socrates session plan-next`, plus status/report/docs visibility, without making it a new lifecycle pass/fail gate yet.

**Tech Stack:** Python stdlib, existing Socrates file contracts, `unittest`, CLI subprocess tests.

---

## File Structure

- Modify: `socrates/planning.py` - next-session handoff data collection, Markdown rendering, manifest writing.
- Modify: `socrates/cli.py` - add `session plan-next` parser/handler and status manifest summary.
- Modify: `socrates/reports.py` - include the latest handoff snapshot in project summary and freshness inputs.
- Modify: `tests/test_learning_plan.py` - unit and CLI tests for next-session handoff behavior.
- Modify: `tests/test_status_quality_summary.py` or `tests/test_reports.py` - focused visibility regression tests.
- Modify: `README.md`, `docs/README.md`, `docs/development_roadmap.md`, `docs/development_log.md` - v0.7 capability and boundary.

## Task 1: Lock Next-Session Handoff Behavior

**Files:**
- Modify: `tests/test_learning_plan.py`

- [ ] **Step 1: Add a unit test for a populated handoff plan**

Create a project fixture with:

```python
project = create_project(ProjectSpec(topic="Normal Subgroup", path=Path(temp_dir) / "p"))
curated = project / "01_references" / "curated" / "normal_subgroups.curated.md"
curated.write_text(
    "# Group Theory\n"
    "## Normal Subgroups\n"
    "### Definition 3.1: Normal Subgroup\n"
    "A subgroup N of G is normal when it is stable under conjugation.\n"
    "Depends: subgroup, conjugation\n",
    encoding="utf-8",
    newline="\n",
)
build_reference_kb(project)
run_scripted_tutoring_session(project, script, session_id="session_0001")
update_learning_state(
    load_project(project),
    LearningStatePatch(
        concept_mastery={"normal_subgroup": 0.42},
        mistakes=[
            MistakeRecord(
                session_id="session_0001",
                concept="normal_subgroup",
                misconception_id="normal_equals_central",
                user_answer="Normal means central.",
                analysis="Confuses normality with centrality.",
                repair_suggestion="Compare gNg^-1=N with gn=ng.",
            )
        ],
    ),
)
build_review_schedule(load_project(project), as_of=date(2026, 6, 4))
```

Assert:

```python
result = create_next_session_plan(project, session_id="session_0002", as_of=date(2026, 6, 4))
self.assertEqual(result.session_id, "session_0002")
self.assertTrue((project / "02_learning_plan" / "session_0002_plan.md").exists())
self.assertTrue((project / "02_learning_plan" / "next_session_plan_manifest.json").exists())
self.assertIn("## Previous Session Handoff", plan_text)
self.assertIn("## Due Reviews", plan_text)
self.assertIn("normal_subgroup", plan_text)
self.assertIn("repair: Compare gNg^-1=N with gn=ng.", plan_text)
self.assertIn("Definition 3.1: Normal Subgroup", plan_text)
self.assertEqual(manifest["quality_boundary"], "deterministic_handoff_plan")
self.assertEqual(manifest["due_reviews"], 1)
```

- [ ] **Step 2: Add a corrupt-state regression**

Write invalid JSON to `00_meta/learning_state.json`, call `create_next_session_plan(...)`, and assert `ValueError` contains:

```text
invalid learning_state.json; repair the JSON before creating next-session plans
```

Also assert `session_0002_plan.md` is not created.

- [ ] **Step 3: Add a CLI smoke test**

Run:

```powershell
python -m socrates session plan-next --project <project> --session-id session_0002 --as-of 2026-06-04
```

Assert stdout includes:

```text
Created next-session plan session_0002
Next-session manifest:
```

## Task 2: Implement Deterministic Handoff Writer

**Files:**
- Modify: `socrates/planning.py`

- [ ] **Step 1: Add result dataclass and public function**

Implement:

```python
@dataclass(frozen=True)
class NextSessionPlanResult:
    session_id: str
    plan_path: Path
    manifest_path: Path
    due_reviews: int
    previous_session_id: str | None


def create_next_session_plan(
    project_path: Path | str,
    *,
    session_id: str,
    as_of: date | None = None,
) -> NextSessionPlanResult:
    ...
```

- [ ] **Step 2: Read schedule and previous session conservatively**

Use `ensure_learning_state_readable(..., action="creating next-session plans")`.

Read `review_schedule` from `learning_state.json` and split into:

```python
due_reviews = valid scheduled_for <= as_of
future_reviews = valid scheduled_for > as_of
invalid_reviews = malformed scheduled_for rows
```

Read the latest previous session directory from `03_sessions/`, excluding the target `session_id`, and include `summary.md`, `next_actions.md`, and `detected_misconceptions.md` when present.

- [ ] **Step 3: Include existing queue and Reference KB context**

Reuse:

```python
queue = collect_learning_queue(context.root)
kb_status = reference_kb_status(context.root)
reference_context = _read_reference_context(context.root, query_concept)
```

Choose `query_concept` from the first due review concept, falling back to the project topic.

- [ ] **Step 4: Write Markdown plus manifest**

Write `02_learning_plan/<session_id>_plan.md` with sections:

```markdown
# Session <id> Plan

## Objective
...
## Previous Session Handoff
...
## Due Reviews
...
## Action Queue Snapshot
...
## Reference Context
...
## Suggested Teaching Moves
...
## Boundary
...
```

Write `02_learning_plan/next_session_plan_manifest.json` with:

```json
{
  "schema_version": 1,
  "session_id": "session_0002",
  "status": "ready",
  "quality_boundary": "deterministic_handoff_plan",
  "as_of": "2026-06-04",
  "plan_path": "02_learning_plan/session_0002_plan.md",
  "previous_session_id": "session_0001",
  "due_reviews": 1,
  "future_reviews": 0,
  "invalid_review_items": 0,
  "reference_kb_status": "ready",
  "action_queue": {
    "notes_to_review": 0,
    "obsidian_exports_to_run": 0,
    "misconception_notes_to_draft": 1,
    "scheduled_reviews": 1,
    "exercise_drafts_to_approve": 0,
    "exercises_to_attempt": 0,
    "attempts_to_grade": 0,
    "quality_checks_to_fix": 0,
    "tool_verifications_to_fix": 0
  }
}
```

Append a project-log entry: `Created next-session handoff plan <session_id>.`

## Task 3: Surface Through CLI, Status, And Reports

**Files:**
- Modify: `socrates/cli.py`
- Modify: `socrates/reports.py`
- Test: `tests/test_status_quality_summary.py` or `tests/test_reports.py`

- [ ] **Step 1: Add `session plan-next`**

Add parser under the existing `session` command:

```python
session_plan_next_parser = session_subparsers.add_parser(
    "plan-next",
    help="Create a deterministic handoff plan for the next tutoring session.",
)
session_plan_next_parser.add_argument("--project", required=True)
session_plan_next_parser.add_argument("--session-id", required=True)
session_plan_next_parser.add_argument("--as-of", default=None)
session_plan_next_parser.set_defaults(func=_handle_session_plan_next)
```

Parse `--as-of` with `_parse_iso_date`, call `create_next_session_plan`, print plan and manifest paths, and return `1` with clean stderr when `ValueError` is raised.

- [ ] **Step 2: Add status lines**

Read `02_learning_plan/next_session_plan_manifest.json` with conservative invalid handling. Print:

```text
Next session plan: session_0002
Next session due reviews: 1
Next session handoff: ready
```

For missing manifest:

```text
Next session plan: not created
Next session due reviews: none
Next session handoff: not run
```

- [ ] **Step 3: Add report snapshot**

Project summary should include:

```markdown
## Next Session Handoff Snapshot

- Session: session_0002
- Status: ready
- Due reviews: 1
- Previous session: session_0001
- Manifest: 02_learning_plan/next_session_plan_manifest.json
```

Also include the manifest in project-summary freshness inputs.

## Task 4: Documentation And Verification

**Files:**
- Modify: `README.md`
- Modify: `docs/README.md`
- Modify: `docs/development_roadmap.md`
- Modify: `docs/development_log.md`

- [ ] **Step 1: Update docs**

Record v0.7-alpha as a deterministic next-session handoff layer:

- It consumes persisted state and queue artifacts.
- It does not run autonomous tutoring.
- It does not trust LLM output.
- It does not mutate learner mastery.
- It produces a reviewable plan/manifest for the next session.

- [ ] **Step 2: Run targeted verification**

Run:

```powershell
python -m unittest tests.test_learning_plan tests.test_reports tests.test_status_quality_summary
```

- [ ] **Step 3: Run full verification**

Run:

```powershell
python -m unittest discover -s tests
python -m compileall socrates
git diff --check
powershell -ExecutionPolicy Bypass -File scripts\check.ps1
bash scripts/check.sh
```

- [ ] **Step 4: Commit with Lore protocol**

Commit the Socrates repo changes with a Lore-style message recording:

- Constraint: no new dependencies; deterministic offline handoff only.
- Rejected: autonomous LLM next-session execution in v0.7.
- Tested: targeted tests, full unittest, compileall, diff check, PowerShell check, bash check.

## Self-Review

- Spec coverage: The plan advances the final product goal by making multi-session continuity actionable while preserving existing review and trust boundaries.
- Placeholder scan: No TBD/TODO placeholders are present.
- Type consistency: The function name, manifest fields, CLI command, and report/status labels are consistent across tasks.

# v09 Session Closeout Workflow Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a deterministic session closeout command that turns the common post-session sequence into one repeatable product workflow.

**Architecture:** Compose existing trusted surfaces instead of adding new intelligence. A new workflow module runs deterministic session scoring, creates the next-session handoff plan, regenerates the project summary after those artifacts exist, then writes a closeout manifest summarizing readiness and paths. The command succeeds when artifacts are written even if deterministic gates say the session needs attention.

**Tech Stack:** Python stdlib, existing Socrates project artifact layout, `unittest`, existing `session_score`, `planning`, and `reports` modules.

---

## File Structure

- Create `socrates/workflow.py`: deterministic session closeout API and manifest writer.
- Create `tests/test_session_closeout.py`: TDD coverage for API artifacts, CLI behavior, and failed-score closeout handling.
- Modify `socrates/cli.py`: add `session closeout`.
- Modify `README.md`: advance baseline to v0.9-alpha and document the closeout command.
- Modify `docs/README.md`: add the v0.9 plan to the implementation-plan index.
- Modify `docs/development_roadmap.md`: add v0.9 current-state notes and v0.10 direction.
- Modify `docs/development_log.md`: append v0.9 evidence after verification.

## Task 1: Failing Tests For Deterministic Closeout

**Files:**
- Create: `tests/test_session_closeout.py`
- Later create: `socrates/workflow.py`

- [ ] **Step 1: Write the passing-session API test**

Build a temporary project with curated reference KB, one reviewed-quality note draft, generated exercises, and a complete scripted session. Call:

```python
result = close_tutoring_session(
    project,
    session_id="session_0001",
    next_session_id="session_0002",
    as_of=date(2026, 6, 4),
)
```

Assert:

```python
self.assertEqual(result.status, "ready")
self.assertEqual(result.session_score, 100)
self.assertTrue(result.session_score_report_path.exists())
self.assertTrue(result.next_session_plan_path.exists())
self.assertTrue(result.project_summary_path.exists())
self.assertTrue(result.manifest_path.exists())
```

Manifest assertions:

```python
self.assertEqual(manifest["quality_boundary"], "deterministic_session_closeout")
self.assertEqual(manifest["session_id"], "session_0001")
self.assertEqual(manifest["next_session_id"], "session_0002")
self.assertEqual(manifest["status"], "ready")
self.assertEqual(manifest["session_score_status"], "pass")
self.assertEqual(manifest["session_score"], 100)
self.assertEqual(manifest["project_summary_path"], "07_exports/reports/project_summary.md")
```

Project summary assertions:

```python
self.assertIn("## Session Score Snapshot", summary_text)
self.assertIn("## Next Session Handoff Snapshot", summary_text)
```

- [ ] **Step 2: Write the failed-score CLI test**

Create a minimal project and session that lacks the reference/note/exercise quality inputs needed for a passing score. Run:

```powershell
python -m socrates session closeout --project <project> --session-id session_0001 --next-session-id session_0002 --as-of 2026-06-04
```

Assert the command returns `0`, prints `Session closeout: needs_attention`, writes `08_evals/session_closeout_manifest.json`, and records `status: needs_attention` with `session_score_status: fail`.

- [ ] **Step 3: Run red tests**

Run:

```powershell
python -m unittest tests.test_session_closeout
```

Expected: fail because `socrates.workflow` or `close_tutoring_session` does not exist.

## Task 2: Implement The Closeout API

**Files:**
- Create: `socrates/workflow.py`
- Test: `tests/test_session_closeout.py`

- [ ] **Step 1: Add result dataclass**

Implement:

```python
@dataclass(frozen=True)
class SessionCloseoutResult:
    session_id: str
    next_session_id: str
    status: str
    session_score: int
    session_score_status: str
    session_score_report_path: Path
    session_score_manifest_path: Path
    next_session_plan_path: Path
    next_session_plan_manifest_path: Path
    project_summary_path: Path
    manifest_path: Path
```

- [ ] **Step 2: Add public function**

Implement:

```python
def close_tutoring_session(
    project_path: Path | str,
    *,
    session_id: str,
    next_session_id: str,
    as_of: date | None = None,
) -> SessionCloseoutResult:
```

Call these existing deterministic functions in order:

```python
score = score_teaching_session(context.root, session_id=session_id)
handoff = create_next_session_plan(context.root, session_id=next_session_id, as_of=as_of)
summary_path = generate_project_summary(context.root)
```

Set closeout status to `ready` when `score.status == "pass"`, otherwise `needs_attention`.

- [ ] **Step 3: Write closeout manifest**

Write `08_evals/session_closeout_manifest.json`:

```json
{
  "schema_version": 1,
  "session_id": "session_0001",
  "next_session_id": "session_0002",
  "status": "ready",
  "quality_boundary": "deterministic_session_closeout",
  "session_score_status": "pass",
  "session_score": 100,
  "session_score_manifest_path": "08_evals/session_score_manifest.json",
  "next_session_plan_manifest_path": "02_learning_plan/next_session_plan_manifest.json",
  "project_summary_path": "07_exports/reports/project_summary.md"
}
```

Append a project-log entry after the manifest is written.

- [ ] **Step 4: Run green API tests**

Run:

```powershell
python -m unittest tests.test_session_closeout
```

Expected: pass after CLI wiring is added in Task 3.

## Task 3: Add CLI Wiring

**Files:**
- Modify: `socrates/cli.py`

- [ ] **Step 1: Import the workflow**

Add:

```python
from .workflow import close_tutoring_session
```

- [ ] **Step 2: Add parser command**

Under existing `session` subcommands:

```python
session_closeout_parser = session_subparsers.add_parser(
    "closeout",
    help="Run deterministic post-session score, next-plan, and summary closeout.",
)
session_closeout_parser.add_argument("--project", required=True, help="Socrates project directory.")
session_closeout_parser.add_argument("--session-id", required=True, help="Completed tutoring session id.")
session_closeout_parser.add_argument("--next-session-id", required=True, help="Next tutoring session id.")
session_closeout_parser.add_argument("--as-of", default=None, help="ISO date for due-review cutoff; defaults to today.")
session_closeout_parser.set_defaults(func=_handle_session_closeout)
```

- [ ] **Step 3: Add handler**

Implement:

```python
def _handle_session_closeout(args: argparse.Namespace) -> int:
    try:
        as_of = date.fromisoformat(args.as_of) if args.as_of else None
        result = close_tutoring_session(
            args.project,
            session_id=args.session_id,
            next_session_id=args.next_session_id,
            as_of=as_of,
        )
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(f"Session closeout: {result.status}")
    print(f"Session score: {result.session_score}/100 ({result.session_score_status})")
    print(f"Next-session plan: {result.next_session_plan_path}")
    print(f"Project summary: {result.project_summary_path}")
    print(f"Closeout manifest: {result.manifest_path}")
    return 0
```

- [ ] **Step 4: Run CLI help check**

Run:

```powershell
python -m socrates session --help
```

Expected: output includes `closeout`.

## Task 4: Documentation And Verification

**Files:**
- Modify: `README.md`
- Modify: `docs/README.md`
- Modify: `docs/development_roadmap.md`
- Modify: `docs/development_log.md`

- [ ] **Step 1: Update docs**

Document `session closeout` as the recommended deterministic post-session command. State that it composes existing gates and does not override failed scores.

- [ ] **Step 2: Run focused tests**

```powershell
python -m unittest tests.test_session_closeout tests.test_session_score tests.test_learning_plan tests.test_reports
```

- [ ] **Step 3: Run full gates**

```powershell
python -m unittest discover -s tests
python -m compileall socrates
git diff --check
powershell -ExecutionPolicy Bypass -File scripts\check.ps1
bash scripts/check.sh
```

- [ ] **Step 4: Commit and update llmwiki**

Commit with Lore protocol and `Co-authored-by: OmX <omx@oh-my-codex.dev>`. Update [[socrates]] in llmwiki to v0.9-alpha with the reusable decision: closeout is a deterministic workflow composition, not a new scoring authority.

## Self-Review

- Spec coverage: The plan covers API, CLI, success and failed-score behavior, docs, verification, commit, and llmwiki.
- Placeholder scan: No TODO/TBD placeholders or unspecified validation remain.
- Type consistency: The public API, CLI command, manifest path, and `deterministic_session_closeout` boundary are used consistently.

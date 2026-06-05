# v0.58 Returning Learner Canary Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:test-driven-development before implementation. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend the deterministic MVP lifecycle canary so it proves a learner can return after the generated workflow and resume through existing study brief, dashboard, and resume surfaces.

**Architecture:** Keep the canary deterministic/offline and reuse the existing reader-owned surfaces. The canary should generate the study brief inside the temporary project, then record structured returning-learner evidence from the dashboard and resume payloads. Do not introduce a new UI, LLM path, or separate parser.

**Tech Stack:** Python dataclass payloads, existing `study_brief`, `dashboard`, and `resume` modules, `unittest`, JSON output, optional artifact bundle copy.

---

## File Map

- Modify `tests/test_lifecycle_canary.py`: add RED coverage for returning-learner continuity in JSON output and copied artifact bundles.
- Modify `socrates/lifecycle_canary.py`: generate the canary study brief, count brief artifacts, and expose dashboard/resume continuity evidence.
- Modify docs after GREEN: `README.md`, `docs/README.md`, `docs/development_log.md`, `docs/development_roadmap.md`.
- Modify this plan as checklist state changes.
- Update llmwiki after the repo commit: `D:\llmwiki\wiki\projects\socrates.md`, `D:\llmwiki\wiki\index.md`, `D:\llmwiki\wiki\log.md`.

## Acceptance Criteria

- `python -m socrates lifecycle canary --json` exits 0 and includes a `returning_learner` object.
- The payload reports `study_brief: current`, `dashboard_study_brief: current`, `resume_state: ready`, and `recommended_command: none`.
- Artifact counts include at least one generated study brief.
- `python -m socrates lifecycle canary --artifacts <dir> --json` copies the study brief and manifest into the inspectable project bundle and writes the same continuity evidence into `canary_report.json`.
- The command remains deterministic/offline and still does not accept or mutate a user project.

---

### Task 1: RED Returning Learner Tests

**Files:**
- Modify: `tests/test_lifecycle_canary.py`

- [x] **Step 1: Add failing JSON continuity assertions**

Assert the canary JSON includes structured returning-learner evidence from the generated study brief, dashboard, and resume payloads.

- [x] **Step 2: Add failing artifact bundle assertions**

Assert the copied canary project contains `07_exports/briefs/study_brief.md`, `07_exports/briefs/study_brief_manifest.json`, and the report JSON records ready resume evidence.

- [x] **Step 3: Run RED**

Run:

```powershell
python -m unittest tests.test_lifecycle_canary
```

Result: failed as expected because `study_briefs` canary evidence and copied study brief artifacts are not exposed yet.

---

### Task 2: Implement Returning Learner Evidence

**Files:**
- Modify: `socrates/lifecycle_canary.py`

- [x] **Step 1: Generate the study brief inside the canary project**

Reuse `generate_study_brief(project)` after the deterministic project evidence exists.

- [x] **Step 2: Reuse dashboard and resume readers**

Build the returning-learner payload from `build_study_dashboard_payload(project)` and `build_project_resume_payload(project)`.

- [x] **Step 3: Count generated brief artifacts**

Extend artifact counts with generated study brief and manifest counts.

- [x] **Step 4: Run GREEN**

Run:

```powershell
python -m unittest tests.test_lifecycle_canary
```

Result: `python -m unittest tests.test_lifecycle_canary` passed with 4 tests OK.

---

### Task 3: Docs, Verification, Commit, and Wiki

**Files:**
- Modify `README.md`
- Modify `docs/README.md`
- Modify `docs/development_log.md`
- Modify `docs/development_roadmap.md`
- Modify `docs/superpowers/plans/2026-06-05-v58-returning-learner-canary.md`
- Update llmwiki after the repo commit: `D:\llmwiki\wiki\projects\socrates.md`, `D:\llmwiki\wiki\index.md`, `D:\llmwiki\wiki\log.md`

- [x] **Step 1: Document v0.58**

Document the canary as returning-learner continuity evidence, not a human outcome validation or new UI surface.

- [x] **Step 2: Run verification**

Run:

```powershell
python -m unittest tests.test_lifecycle_canary
python -m unittest tests.test_lifecycle_canary tests.test_lifecycle_audit tests.test_v02_cli_flow tests.test_v04_exercise_flow tests.test_status_quality_summary
python -m unittest discover -s tests
python -m compileall socrates
git diff --check
powershell -ExecutionPolicy Bypass -File scripts\check.ps1
bash scripts/check.sh
```

Result: all verification commands passed. Full unittest discovery and both check scripts reported 477 tests OK with 1 skipped; Bash emitted the existing WSL localhost/NAT notice and Git CRLF warning for `scripts/check.ps1`.

- [x] **Step 3: Commit and publish to the existing draft PR**

Commit the v0.58 repo changes with a why-first Lore message and `Co-authored-by: OmX <omx@oh-my-codex.dev>`, then push to `codex/v02-closure` so draft PR `https://github.com/Yaohua-Leo/Socrates/pull/5` includes returning-learner continuity evidence.

- [x] **Step 4: Update llmwiki**

Update the Socrates wiki page, wiki index, and wiki log with the v0.58 commit id, verification evidence, returning-learner canary boundary, and the reusable lesson that product canaries should cover both artifact generation and the operator/learner re-entry surfaces that consume those artifacts.

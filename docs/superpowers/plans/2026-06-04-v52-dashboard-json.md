# v0.52 Dashboard JSON Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:test-driven-development before implementation. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `dashboard --json` so wrappers, UI prototypes, plugins, and automation can consume the read-only operator dashboard without parsing Markdown.

**Architecture:** Factor the existing dashboard evidence into a structured read-only payload and render Markdown from that payload. JSON mode must call the same deterministic readers as Markdown mode and must not run repairs, generate reports, refresh briefs, call an LLM, score learning, tutor, predict, approve artifacts, or mutate project state.

**Tech Stack:** Python argparse, existing dashboard/queue/report readers, `json`, `unittest`, deterministic temporary project fixtures.

---

## File Map

- Modify `tests/test_dashboard.py`: add RED coverage for `dashboard --json`, empty-project payload shape, priority-action payload rows, and no-write behavior.
- Modify `socrates/dashboard.py`: add `build_study_dashboard_payload(...)` and render Markdown from that payload.
- Modify `socrates/cli.py`: add `--json` to `dashboard` and print deterministic JSON.
- Modify docs after GREEN: `README.md`, `docs/README.md`, `docs/development_log.md`, `docs/development_roadmap.md`.
- Modify this plan as checklist state changes.
- Update llmwiki after the repo commit: `D:\llmwiki\wiki\projects\socrates.md`, `D:\llmwiki\wiki\index.md`, `D:\llmwiki\wiki\log.md`.

## Acceptance Criteria

- `python -m socrates dashboard --project <project> --json` exits 0 and emits valid deterministic JSON.
- The payload includes `schema_version: 1`, `quality_boundary: deterministic_study_dashboard`, `project`, `root`, `snapshot`, `action_summary`, `top_priority_actions`, and `report_health`.
- `snapshot` includes workflow actions, closeout/regression/report-history state, study-brief freshness rows, and report health counts.
- `action_summary` exposes completion, open-action, blocker, continue-learning, human-review, and next-action fields without parsing Markdown.
- `top_priority_actions` and `report_health` are structured rows with stable ids/status/path fields.
- Markdown dashboard output remains stable.
- JSON mode is read-only and does not write project logs, reports, briefs, learning state, or queue artifacts.

---

### Task 1: RED Dashboard JSON Tests

**Files:**
- Modify: `tests/test_dashboard.py`

- [x] **Step 1: Add failing empty-project JSON test**

Run `dashboard --json`, assert payload metadata, snapshot fields, action summary, report health rows, no Markdown header, and no project-log write.

- [x] **Step 2: Add failing priority-action JSON test**

Create a draft note, run `dashboard --json`, assert action summary and first top-priority action row match Markdown dashboard evidence.

- [x] **Step 3: Run RED**

Run:

```powershell
python -m unittest tests.test_dashboard
```

Expected: fail because `dashboard --json` is not registered yet.

---

### Task 2: Add Dashboard JSON Payload

**Files:**
- Modify: `socrates/dashboard.py`
- Modify: `socrates/cli.py`

- [x] **Step 1: Register `--json`**

Add `--json` to the dashboard parser and route JSON output through the dashboard payload.

- [x] **Step 2: Build structured payload**

Create `build_study_dashboard_payload(...)` with snapshot, action summary, top-priority actions, and report-health rows from the same deterministic readers as Markdown.

- [x] **Step 3: Render Markdown from payload**

Keep Markdown output stable by formatting from the structured payload instead of maintaining a separate evidence path.

- [x] **Step 4: Preserve read-only boundary**

Ensure JSON mode reads only and does not write project artifacts.

- [x] **Step 5: Run GREEN**

Run:

```powershell
python -m unittest tests.test_dashboard
```

Expected: tests OK.

---

### Task 3: Docs, Verification, Commit, and Wiki

**Files:**
- Modify `README.md`
- Modify `docs/README.md`
- Modify `docs/development_log.md`
- Modify `docs/development_roadmap.md`
- Modify `docs/superpowers/plans/2026-06-04-v52-dashboard-json.md`
- Update llmwiki after the repo commit: `D:\llmwiki\wiki\projects\socrates.md`, `D:\llmwiki\wiki\index.md`, `D:\llmwiki\wiki\log.md`

- [x] **Step 1: Document v0.52**

Document `dashboard --json` as a read-only structured operator dashboard payload, not a writer or readiness gate.

- [x] **Step 2: Run verification**

Run:

```powershell
python -m unittest tests.test_dashboard
python -m unittest tests.test_dashboard tests.test_study_brief tests.test_status_quality_summary tests.test_learning_queue tests.test_reports
python -m unittest discover -s tests
python -m compileall socrates
git diff --check
powershell -ExecutionPolicy Bypass -File scripts\check.ps1
bash scripts/check.sh
```

- [ ] **Step 3: Commit with Lore protocol**

Commit the v0.52 repo changes with a why-first Lore message and `Co-authored-by: OmX <omx@oh-my-codex.dev>`.

- [ ] **Step 4: Update llmwiki**

Update the Socrates wiki page, wiki index, and wiki log with the v0.52 commit id, verification evidence, dashboard JSON boundary, and the reusable lesson that wrapper-facing dashboards should expose structured evidence rows rather than forcing Markdown parsing.

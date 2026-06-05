# v0.51 Review Resolve Dry-Run Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:test-driven-development before implementation. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `review resolve --dry-run` so operators, wrappers, UI prototypes, and plugins can preview misconception resolver effects before mutating learning state or appending the mistake bank.

**Architecture:** Reuse the v0.50 resolver row capture helper. Dry-run mode reads matching active misconception rows with the same action scope as the writer, emits prose or deterministic JSON, and returns before calling `resolve_active_misconceptions_for_concept(...)`. The command remains a preview of the existing resolver writer, not a ledger, note generator, tutor, score, report refresh, LLM call, or new learning-state truth source.

**Tech Stack:** Python argparse, existing misconception row serialization, `json`, `unittest`, deterministic temporary project fixtures.

---

## File Map

- Modify `tests/test_state_eval.py`: add RED coverage for `review resolve --dry-run`, JSON preview payloads, no-match preview payloads, no-write guarantees, and corrupt JSON compatibility.
- Modify `socrates/cli.py`: add `--dry-run` to `review resolve`, emit deterministic preview prose/JSON, and keep writer/prose behavior unchanged.
- Modify docs after GREEN: `README.md`, `docs/README.md`, `docs/development_log.md`, `docs/development_roadmap.md`.
- Modify this plan as checklist state changes.
- Update llmwiki after the repo commit: `D:\llmwiki\wiki\projects\socrates.md`, `D:\llmwiki\wiki\index.md`, `D:\llmwiki\wiki\log.md`.

## Acceptance Criteria

- `python -m socrates review resolve --project <project> --concept normal_subgroup --dry-run` exits 0, previews matching active misconceptions, and does not rewrite `learning_state.json` or append `mistake_bank.md`.
- `--dry-run --json` emits `schema_version: 1`, `quality_boundary: deterministic_misconception_resolver_preview`, `project`, `concept`, `dry_run: true`, `resolved_count`, and `resolved_misconceptions`.
- Each preview row includes `misconception_id`, `concept`, `previous_status`, `status`, `count`, `last_session_id`, `analysis`, `repair_suggestion`, and `follow_up_exercises`.
- No-match dry-run JSON returns `resolved_count: 0` and an empty `resolved_misconceptions` list without writing.
- Corrupt `learning_state.json` handling remains clean and non-traceback, including in dry-run mode.
- Existing `review resolve` and `review resolve --json` writer behavior remains unchanged.

---

### Task 1: RED Review Resolve Dry-Run Tests

**Files:**
- Modify: `tests/test_state_eval.py`

- [x] **Step 1: Add failing prose dry-run no-write test**

Create a project with active misconceptions, run `review resolve --concept normal_subgroup --dry-run`, assert preview prose and assert learning-state plus mistake-bank bytes are unchanged.

- [x] **Step 2: Add failing JSON dry-run no-write test**

Run `review resolve --concept normal_subgroup --dry-run --json`, assert preview metadata, row shape, and no writes.

- [x] **Step 3: Add failing JSON no-match dry-run test**

Run `review resolve --concept rings --dry-run --json`, assert `resolved_count: 0`, no resolved rows, and no writes.

- [x] **Step 4: Add failing corrupt-state dry-run compatibility test**

Run `review resolve --dry-run --json` with invalid `learning_state.json`, assert exit 1, no stdout, clean stderr, and no mistake-bank append.

- [x] **Step 5: Run RED**

Run:

```powershell
python -m unittest tests.test_state_eval
```

Expected: fail because `review resolve --dry-run` is not registered yet.

---

### Task 2: Add Resolver Dry-Run Preview

**Files:**
- Modify: `socrates/cli.py`

- [x] **Step 1: Register `--dry-run`**

Add `--dry-run` to the `review resolve` parser. Keep existing `--project`, `--concept`, and `--json` behavior.

- [x] **Step 2: Reuse resolver row capture**

In dry-run mode, collect matching active misconception rows and return before calling the resolver writer.

- [x] **Step 3: Serialize preview result**

Emit `quality_boundary: deterministic_misconception_resolver_preview`, `dry_run: true`, resolved count, and preview rows when `--json` is present.

- [x] **Step 4: Render prose preview**

Emit stable prose with a preview header and row summaries when `--json` is absent.

- [x] **Step 5: Preserve writer behavior**

Keep current writer prose and writer JSON output unchanged when `--dry-run` is absent, while preserving clean corrupt JSON failures.

- [x] **Step 6: Run GREEN**

Run:

```powershell
python -m unittest tests.test_state_eval
```

Expected: tests OK.

---

### Task 3: Docs, Verification, Commit, and Wiki

**Files:**
- Modify `README.md`
- Modify `docs/README.md`
- Modify `docs/development_log.md`
- Modify `docs/development_roadmap.md`
- Modify `docs/superpowers/plans/2026-06-04-v51-review-resolve-dry-run.md`
- Update llmwiki after the repo commit: `D:\llmwiki\wiki\projects\socrates.md`, `D:\llmwiki\wiki\index.md`, `D:\llmwiki\wiki\log.md`

- [x] **Step 1: Document v0.51**

Document `review resolve --dry-run` as a no-write misconception resolver preview, not a writer or read-only ledger.

- [x] **Step 2: Run verification**

Run:

```powershell
python -m unittest tests.test_state_eval
python -m unittest tests.test_state_eval tests.test_status_quality_summary tests.test_learning_queue tests.test_reports
python -m unittest discover -s tests
python -m compileall socrates
git diff --check
powershell -ExecutionPolicy Bypass -File scripts\check.ps1
bash scripts/check.sh
```

- [x] **Step 3: Commit with Lore protocol**

Commit the v0.51 repo changes with a why-first Lore message and `Co-authored-by: OmX <omx@oh-my-codex.dev>`.

- [x] **Step 4: Update llmwiki**

Update the Socrates wiki page, wiki index, and wiki log with the v0.51 commit id, verification evidence, resolver dry-run preview boundary, and the reusable lesson that resolver previews should share the writer's row selection while proving no resolver side effects occurred.

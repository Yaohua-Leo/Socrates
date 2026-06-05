# v0.50 Review Resolve JSON Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:test-driven-development before implementation. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `review resolve --json` so wrappers, UI prototypes, and plugins can consume misconception resolver writer results without parsing prose.

**Architecture:** Keep existing `review resolve` writer semantics. JSON mode still calls `resolve_active_misconceptions_for_concept(...)`, updates matching active misconceptions to `resolved`, and appends the mistake-bank resolution entry. The CLI captures matching active misconception rows before the writer runs, then serializes those rows as the writer-result payload. The command remains a writer, not a dry-run, read-only ledger, note generator, tutor, report refresh, or LLM call.

**Tech Stack:** Python argparse, existing learning-state/misconception records, `json`, `unittest`, deterministic temporary project fixtures.

---

## File Map

- Modify `tests/test_state_eval.py`: add RED coverage for `review resolve --json`, writer side effects, returned resolved rows, no-match payloads, and corrupt JSON compatibility.
- Modify `socrates/cli.py`: add `--json` to `review resolve`, emit deterministic writer-result JSON, and keep prose mode unchanged.
- Modify docs after GREEN: `README.md`, `docs/README.md`, `docs/development_log.md`, `docs/development_roadmap.md`.
- Modify this plan as checklist state changes.
- Update llmwiki after the repo commit: `D:\llmwiki\wiki\projects\socrates.md`, `D:\llmwiki\wiki\index.md`, `D:\llmwiki\wiki\log.md`.

## Acceptance Criteria

- `python -m socrates review resolve --project <project> --concept normal_subgroup --json` exits 0, resolves the same matching active misconceptions as prose mode, appends the same mistake-bank resolution entry, and emits valid deterministic JSON.
- The JSON payload includes `schema_version: 1`, `quality_boundary: deterministic_misconception_resolver`, `project`, `concept`, `resolved_count`, and `resolved_misconceptions`.
- Each resolved row includes `misconception_id`, `concept`, `previous_status`, `status`, `count`, `last_session_id`, `analysis`, `repair_suggestion`, and `follow_up_exercises`.
- No-match JSON mode returns `resolved_count: 0` and an empty `resolved_misconceptions` list without writing.
- Corrupt `learning_state.json` handling remains clean and non-traceback, including in JSON mode.
- The command boundary remains explicit: JSON output describes the existing resolver writer result; it is not a dry-run, read-only ledger, note generator, tutor, report refresh, LLM call, plan approval, or learning-state scoring.

---

### Task 1: RED Review Resolve JSON Tests

**Files:**
- Modify: `tests/test_state_eval.py`

- [x] **Step 1: Add failing JSON writer-result test**

Create a project with two active misconceptions, run `review resolve --concept normal_subgroup --json`, assert payload metadata and one resolved row, and assert learning state plus mistake bank side effects.

- [x] **Step 2: Add failing JSON no-match test**

Run `review resolve --concept rings --json`, assert `resolved_count: 0`, no resolved rows, and no learning-state or mistake-bank writes.

- [x] **Step 3: Add failing corrupt-state JSON compatibility test**

Run `review resolve --json` with invalid `learning_state.json`, assert exit 1, no stdout, clean stderr, and no mistake-bank append.

- [x] **Step 4: Run RED**

Run:

```powershell
python -m unittest tests.test_state_eval
```

Expected: fail because `review resolve --json` is not registered yet.

---

### Task 2: Add Writer-Result JSON

**Files:**
- Modify: `socrates/cli.py`

- [x] **Step 1: Register `--json`**

Add `--json` to the `review resolve` parser. Keep existing `--project` and `--concept` behavior.

- [x] **Step 2: Capture resolver rows**

Before the writer runs, collect matching active misconception rows for the requested concept using the same concept matching policy as the writer.

- [x] **Step 3: Serialize writer result**

After `resolve_active_misconceptions_for_concept(...)` returns, emit `quality_boundary: deterministic_misconception_resolver` with project path, concept, resolved count, and resolved rows when `args.json` is true.

- [x] **Step 4: Preserve prose behavior**

Keep current prose output unchanged when `--json` is absent, while keeping corrupt JSON failures clean.

- [x] **Step 5: Run GREEN**

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
- Modify `docs/superpowers/plans/2026-06-04-v50-review-resolve-json.md`
- Update llmwiki after the repo commit: `D:\llmwiki\wiki\projects\socrates.md`, `D:\llmwiki\wiki\index.md`, `D:\llmwiki\wiki\log.md`

- [x] **Step 1: Document v0.50**

Document `review resolve --json` as a structured misconception resolver writer-result payload, not a dry-run or read-only ledger.

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

Commit the v0.50 repo changes with a why-first Lore message and `Co-authored-by: OmX <omx@oh-my-codex.dev>`.

- [x] **Step 4: Update llmwiki**

Update the Socrates wiki page, wiki index, and wiki log with the v0.50 commit id, verification evidence, resolver writer-result JSON boundary, and the reusable lesson that resolver JSON payloads should capture affected rows before mutation while serializing the post-action status.

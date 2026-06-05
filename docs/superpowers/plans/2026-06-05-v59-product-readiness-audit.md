# v0.59 Product Readiness Audit Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:test-driven-development before implementation. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a read-only product readiness audit that maps the final Socrates v1.0 development goal to the current implemented evidence and remaining gaps.

**Architecture:** Keep this repo-level and deterministic. The audit is a static current-state capability map derived from `docs/final_development_goal.md` and current implemented surfaces. It must not inspect or mutate a learner project, run OCR, call an LLM, generate reports, or claim real learner validation.

**Tech Stack:** Python payload formatter, argparse `product readiness` subcommand, `unittest`, JSON output.

---

## File Map

- Add `tests/test_product_readiness.py`: RED coverage for JSON and prose audit output.
- Add `socrates/product_readiness.py`: structured product readiness payload and Markdown formatter.
- Modify `socrates/cli.py`: register `product readiness` and `--json`.
- Modify docs after GREEN: `README.md`, `docs/README.md`, `docs/development_log.md`, `docs/development_roadmap.md`.
- Modify this plan as checklist state changes.
- Update llmwiki after the repo commit: `D:\llmwiki\wiki\projects\socrates.md`, `D:\llmwiki\wiki\index.md`, `D:\llmwiki\wiki\log.md`.

## Acceptance Criteria

- `python -m socrates product readiness` exits 0 and renders `# Product Readiness Audit`.
- `python -m socrates product readiness --json` exits 0 and emits `quality_boundary: deterministic_product_readiness_audit`.
- JSON includes the ten final-goal capability areas, their statuses, evidence, and gaps.
- JSON reports `overall_status: not_v1_ready` and a decision point for the next major product lane.
- The command is read-only and does not require a project path.

---

### Task 1: RED Product Readiness Tests

**Files:**
- Add: `tests/test_product_readiness.py`

- [x] **Step 1: Add failing JSON contract test**

Assert the JSON payload has the expected quality boundary, ten capability rows, a non-ready status, and a next-major-lane decision point.

- [x] **Step 2: Add failing prose contract test**

Assert the prose output renders the audit heading, current version, not-ready status, capability rows, and decision point.

- [x] **Step 3: Run RED**

Run:

```powershell
python -m unittest tests.test_product_readiness
```

Result: failed as expected because `product` is not a registered top-level command yet.

---

### Task 2: Implement Read-Only Audit

**Files:**
- Add: `socrates/product_readiness.py`
- Modify: `socrates/cli.py`

- [x] **Step 1: Add structured payload**

Define the deterministic v1.0 capability map with evidence, gaps, and decision points.

- [x] **Step 2: Add formatter**

Render a compact Markdown audit from the same payload.

- [x] **Step 3: Register CLI**

Add `python -m socrates product readiness [--json]`.

- [x] **Step 4: Run GREEN**

Run:

```powershell
python -m unittest tests.test_product_readiness
```

Result: `python -m unittest tests.test_product_readiness` passed with 2 tests OK.

---

### Task 3: Docs, Verification, Commit, and Wiki

**Files:**
- Modify `README.md`
- Modify `docs/README.md`
- Modify `docs/development_log.md`
- Modify `docs/development_roadmap.md`
- Modify `docs/superpowers/plans/2026-06-05-v59-product-readiness-audit.md`
- Update llmwiki after the repo commit: `D:\llmwiki\wiki\projects\socrates.md`, `D:\llmwiki\wiki\index.md`, `D:\llmwiki\wiki\log.md`

- [x] **Step 1: Document v0.59**

Document the audit as a read-only capability/gap map, not a v1.0 completion proof.

- [x] **Step 2: Run verification**

Run:

```powershell
python -m unittest tests.test_product_readiness
python -m unittest tests.test_product_readiness tests.test_lifecycle_canary tests.test_status_quality_summary
python -m unittest discover -s tests
python -m compileall socrates
git diff --check
powershell -ExecutionPolicy Bypass -File scripts\check.ps1
bash scripts/check.sh
```

Result: all verification commands passed. Full unittest discovery and both check scripts reported 479 tests OK with 1 skipped; Bash emitted the existing WSL localhost/NAT notice and Git CRLF warning for `scripts/check.ps1`.

- [ ] **Step 3: Commit and publish to the existing draft PR**

Commit the v0.59 repo changes with a why-first Lore message and `Co-authored-by: OmX <omx@oh-my-codex.dev>`, then push to `codex/v02-closure` so draft PR `https://github.com/Yaohua-Leo/Socrates/pull/5` includes product readiness audit evidence.

- [ ] **Step 4: Update llmwiki**

Update the Socrates wiki page, wiki index, and wiki log with the v0.59 commit id, verification evidence, audit boundary, and the reusable lesson that long product goals need explicit capability-gap maps before irreversible branch choices.

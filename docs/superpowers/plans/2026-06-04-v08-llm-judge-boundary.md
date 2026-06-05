# v08 LLM Judge Boundary Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a review-only LLM session-judge draft surface without turning LLM output into a score, readiness gate, grade, or learning-state mutation.

**Architecture:** Keep the deterministic quality system authoritative. A new focused module reads existing session artifacts plus any deterministic session score, asks the configured LLM for structured observations, writes a draft Markdown artifact, and records it in `08_evals/llm_suggestions_manifest.json`. CLI wiring exposes the draft generator while status and lifecycle keep treating LLM artifacts as conservative suggestions only.

**Tech Stack:** Python stdlib, existing Socrates project artifact layout, `unittest`, existing provider-neutral `socrates.llm` contracts, existing `socrates.llm_artifacts` manifest helpers.

---

## File Structure

- Create `socrates/llm_judge.py`: review-only session judge draft API, JSON parsing, prompt construction, and artifact writing.
- Create `tests/test_llm_judge.py`: TDD coverage for draft output, manifest record, and trusted-state immutability.
- Modify `socrates/cli.py`: import the new API, add `session judge-suggest`, and print a concise artifact path on success.
- Modify `README.md`: advance baseline to v0.8-alpha and describe the new boundary.
- Modify `docs/README.md`: add the v0.8 plan to the implementation-plan index.
- Modify `docs/development_roadmap.md`: add v0.8 current-state notes and forward v0.9 direction.
- Modify `docs/development_log.md`: append v0.8 implementation evidence after verification.

## Task 1: Failing Tests For Draft-Only Judge Output

**Files:**
- Create: `tests/test_llm_judge.py`
- Later create: `socrates/llm_judge.py`

- [ ] **Step 1: Write the failing API test**

Create `tests/test_llm_judge.py` with a test that builds a temporary project, runs a scripted session, writes a deterministic session score, snapshots `transcript.md`, `learning_state.json`, and `session_score_manifest.json`, then calls:

```python
artifact = suggest_session_judge_with_llm(project, "session_0001", client=client)
```

Use `FakeLlmClient` with JSON keys:

```json
{
  "summary": "The session is usable but needs human review.",
  "rubric_findings": ["The tutor asked a follow-up question before stating a solution."],
  "risks": ["The misconception may be under-specified."],
  "recommended_human_checks": ["Confirm normality versus commutativity was addressed."],
  "confidence": "medium"
}
```

Assertions:

```python
self.assertTrue(artifact.exists())
self.assertIn("status: draft", text)
self.assertIn("quality_boundary: review_only_llm_judge_draft", text)
self.assertIn("# LLM Session Judge Draft", text)
self.assertEqual(transcript_before, transcript_path.read_text(encoding="utf-8"))
self.assertEqual(learning_state_before, learning_state_path.read_text(encoding="utf-8"))
self.assertEqual(score_manifest_before, score_manifest_path.read_text(encoding="utf-8"))
self.assertEqual("session_quality_judge", records[0].suggestion_type)
self.assertIn("03_sessions/session_0001/transcript.md", manifest_text)
self.assertIn("08_evals/session_score_manifest.json", manifest_text)
```

- [ ] **Step 2: Write the failing validation test**

Add a second test with a fake response missing `recommended_human_checks`. Assert `suggest_session_judge_with_llm` raises `ValueError` and does not create `03_sessions/session_0001/llm_session_judge.md`.

- [ ] **Step 3: Run red tests**

Run:

```powershell
python -m unittest tests.test_llm_judge
```

Expected: fail because `socrates.llm_judge` does not exist or `suggest_session_judge_with_llm` is undefined.

## Task 2: Implement The Review-Only Judge API

**Files:**
- Create: `socrates/llm_judge.py`
- Test: `tests/test_llm_judge.py`

- [ ] **Step 1: Create the module and public function**

Implement:

```python
def suggest_session_judge_with_llm(
    project_path: Path | str,
    session_id: str,
    *,
    client: LlmClient,
) -> Path:
```

Read required session files from `03_sessions/<session_id>/`: `transcript.md`, `summary.md`, `tutor_notes.md`, `detected_misconceptions.md`, and `next_actions.md`. If `08_evals/session_score_manifest.json` exists, include it as context and source path. Do not call `score_teaching_session` or write any deterministic score output.

- [ ] **Step 2: Parse strict JSON output**

Require keys:

```python
("summary", "rubric_findings", "risks", "recommended_human_checks", "confidence")
```

Normalize `rubric_findings`, `risks`, and `recommended_human_checks` as non-empty string lists. Normalize `confidence` to one of `low`, `medium`, or `high`; reject empty fields with `ValueError`.

- [ ] **Step 3: Write the draft artifact**

Write `03_sessions/<session_id>/llm_session_judge.md` with frontmatter:

```yaml
status: draft
created_by: socrates_llm
provider: <provider>
model: <model>
session_id: <session_id>
quality_boundary: review_only_llm_judge_draft
```

Body sections:

```markdown
# LLM Session Judge Draft

## Boundary

This draft is for human review only. It is not a deterministic score, grade, readiness gate, proof, or learning-state update.

## Summary
...
```

- [ ] **Step 4: Record the manifest suggestion**

Call `record_llm_suggestion` with `suggestion_type="session_quality_judge"`, source paths for the five session files, and the score manifest only when present. Set the prompt hash from the concatenated prompt inputs.

- [ ] **Step 5: Run green API tests**

Run:

```powershell
python -m unittest tests.test_llm_judge
```

Expected: pass.

## Task 3: Add CLI Wiring

**Files:**
- Modify: `socrates/cli.py`
- Test: `tests/test_llm_judge.py`

- [ ] **Step 1: Import the new function**

Add:

```python
from .llm_judge import suggest_session_judge_with_llm
```

- [ ] **Step 2: Add parser command**

Under the existing `session` subcommands, add:

```python
session_judge_suggest_parser = session_subparsers.add_parser(
    "judge-suggest",
    help="Ask the configured LLM for a review-only session judge draft.",
)
session_judge_suggest_parser.add_argument("--project", required=True, help="Socrates project directory.")
session_judge_suggest_parser.add_argument("--session-id", required=True, help="Tutoring session id.")
session_judge_suggest_parser.set_defaults(func=_handle_session_judge_suggest)
```

- [ ] **Step 3: Add handler**

Implement `_handle_session_judge_suggest` next to `_handle_session_suggest_next`:

```python
def _handle_session_judge_suggest(args: argparse.Namespace) -> int:
    config = load_llm_config(Path.cwd())
    client = DeepSeekClient(config)
    try:
        artifact = suggest_session_judge_with_llm(args.project, args.session_id, client=client)
    except (OSError, ValueError, LlmProviderError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(f"Wrote LLM session-judge draft: {artifact}")
    return 0
```

- [ ] **Step 4: Run CLI help check**

Run:

```powershell
python -m socrates session --help
```

Expected: output includes `judge-suggest`.

## Task 4: Documentation And Roadmap

**Files:**
- Modify: `README.md`
- Modify: `docs/README.md`
- Modify: `docs/development_roadmap.md`
- Modify: `docs/development_log.md`

- [ ] **Step 1: Update README**

Advance the baseline to `v0.8-alpha` and state that `session judge-suggest` writes review-only LLM judge drafts. Explicitly say deterministic gates and session scores remain authoritative.

- [ ] **Step 2: Update docs index**

Add `2026-06-04-v08-llm-judge-boundary.md` to the implementation-plan list.

- [ ] **Step 3: Update roadmap**

Add a v0.8 section that records completed review-bounded LLM judge drafts and a v0.9 next direction that should remain deterministic unless explicitly widened.

- [ ] **Step 4: Update development log after verification**

Append the v0.8 commit-ready evidence: focused tests, full unittest discovery, compileall, diff check, Windows check, and WSL check.

## Task 5: Final Verification, Commit, And Wiki

**Files:**
- Verify all changed files.
- Modify after commit: `D:\llmwiki\wiki\projects\socrates.md`, `D:\llmwiki\wiki\index.md`, `D:\llmwiki\wiki\log.md`

- [ ] **Step 1: Run focused tests**

```powershell
python -m unittest tests.test_llm_judge tests.test_llm_tutoring_suggestions tests.test_llm_provider_contract
```

- [ ] **Step 2: Run full gates**

```powershell
python -m unittest discover -s tests
python -m compileall socrates
git diff --check
powershell -ExecutionPolicy Bypass -File scripts\check.ps1
bash scripts/check.sh
```

- [ ] **Step 3: Commit with Lore protocol**

Commit once all verification passes. Include `Co-authored-by: OmX <omx@oh-my-codex.dev>`.

- [ ] **Step 4: Update llmwiki**

Update the Socrates project page to `v0.8-alpha`, preserving the reusable decision: LLM judge drafts are review-only artifacts, not trusted grades, deterministic scores, or readiness gates. Refresh the wiki index and append the wiki log.

## Self-Review

- Spec coverage: The plan covers a review-only LLM judge API, CLI command, tests for immutability and manifest records, docs, verification, commit, and llmwiki update.
- Placeholder scan: No `TBD`, open-ended TODO, or unspecified test step remains.
- Type consistency: The public API is `suggest_session_judge_with_llm(project_path, session_id, *, client) -> Path`; tests, CLI, and docs use the same command and suggestion type.

# Socrates

Socrates is a local-first Python CLI for project-based mathematics learning.
It creates a durable learning-project directory and coordinates reference
ingestion, curated reference knowledge-base indexing, deterministic tutoring
sessions, atomic note review, Obsidian export, exercises, learning-state
artifacts, reports, and quality checks.

The current codebase is a v0.34-alpha prototype. Its strongest surfaces are the
deterministic CLI, file contracts, provenance checks, Reference KB indexing,
external conversion handoff for PDF/OCR workflows, Obsidian note workflow,
exercise validation and bank manifests, deterministic session score reports,
next-session handoff planning, deterministic session closeout workflow with
status/lifecycle visibility, deterministic multi-session regression with
long-term report-surface refresh, commands-output command-summarized filterable readiness-counted
machine-readable and Markdown read-only multi-project resume indexes,
machine-readable read-only project resume state, read-only project resume
cards, read-only study dashboards, generated
study-start briefs with a read-only manifest-backed freshness command,
workflow action queue visibility, priority action queue navigation, priority
action snapshots in reports, recommended focus report summaries, action summary
queue/report summaries, repair path queue/report summaries, risk summary report
snapshots, risk trend report summaries, report-history audit visibility, and an
opt-in LLM provider layer for
reviewable draft suggestions, including
review-only session judge drafts. It is not yet a full AI tutor: autonomous LLM
tutoring, OCR/PDF extraction backends, trusted LLM judges, and product UI layers
remain future work.

## Quick Start

Create a project:

```powershell
python -m socrates init --topic "Group Theory" --path ".\projects\group_theory" --goal "Prepare for representation theory."
```

Import and curate a local Markdown or text reference:

```powershell
python -m socrates import --project ".\projects\group_theory" ".\normal_subgroups.md" --role lecture_notes --title "Normal Subgroup Notes"
python -m socrates curate --project ".\projects\group_theory" --source-id normal_subgroup_notes
```

For a PDF or OCR workflow, attach an externally converted Markdown file before
curation:

```powershell
python -m socrates sources attach-conversion --project ".\projects\group_theory" --source-id abstract_algebra --markdown ".\abstract_algebra.converted.md"
```

Build and query the Reference KB:

```powershell
python -m socrates kb build --project ".\projects\group_theory"
python -m socrates kb search --project ".\projects\group_theory" --query "conjugation"
python -m socrates kb chapters --project ".\projects\group_theory"
python -m socrates kb relationships --project ".\projects\group_theory"
```

Run the deterministic learning loop and inspect status:

```powershell
python -m socrates plan --project ".\projects\group_theory"
python -m socrates teach --project ".\projects\group_theory" --session-id session_0001 --script ".\session.script"
python -m socrates note review --project ".\projects\group_theory" --note normal_subgroup
python -m socrates note export-obsidian --project ".\projects\group_theory"
python -m socrates exercise validate --project ".\projects\group_theory" --all
python -m socrates exercise bank build --project ".\projects\group_theory"
python -m socrates session score --project ".\projects\group_theory" --session-id session_0001
python -m socrates session plan-next --project ".\projects\group_theory" --session-id session_0002
python -m socrates session closeout --project ".\projects\group_theory" --session-id session_0001 --next-session-id session_0002
python -m socrates lifecycle regression --project ".\projects\group_theory"
python -m socrates queue --project ".\projects\group_theory" --section summary
python -m socrates queue --project ".\projects\group_theory" --section repairs
python -m socrates queue --project ".\projects\group_theory" --section priority
python -m socrates queue --project ".\projects\group_theory" --section workflow
python -m socrates report weekly --project ".\projects\group_theory"
python -m socrates report monthly --project ".\projects\group_theory"
python -m socrates report project-summary --project ".\projects\group_theory"
python -m socrates session judge-suggest --project ".\projects\group_theory" --session-id session_0001
python -m socrates dashboard --project ".\projects\group_theory"
python -m socrates resume --project ".\projects\group_theory"
python -m socrates resume --project ".\projects\group_theory" --json
python -m socrates projects resume --root ".\projects"
python -m socrates projects resume --root ".\projects" --json
python -m socrates projects resume --root ".\projects" --state refresh_brief
python -m socrates projects resume --root ".\projects" --state refresh_brief --commands
python -m socrates brief generate --project ".\projects\group_theory"
python -m socrates brief status --project ".\projects\group_theory"
python -m socrates status --project ".\projects\group_theory"
python -m socrates lifecycle audit --project ".\projects\group_theory"
```

Inspect local LLM configuration or run an explicit DeepSeek smoke test:

```powershell
python -m socrates llm config --root .
python -m socrates llm smoke --root . --prompt "Return exactly: socrates-ok"
```

## Current Capabilities

- Project initialization with stable metadata, reference, plan, session, note,
  exercise, KB, export, and eval directories.
- Local reference import, conversion-pending handling for unsupported PDFs, and
  patch-only curation correction proposals.
- External Markdown conversion handoff for PDF/OCR workflows, preserving raw
  reference bytes while creating a review-gated curated draft.
- Reference KB extraction from curated Markdown into object, chunk, chapter,
  theorem, exercise, concept graph, and dependency graph artifacts.
- Reader fail-fast behavior for malformed generated KB artifacts, with rebuild
  hints instead of raw JSON errors.
- Deterministic scripted tutoring sessions that write transcripts, summaries,
  tutor notes, misconception records, and draft notes.
- Atomic note review, Obsidian export, manifest generation, backlink handling,
  stale export cleanup, and lifecycle audit integration.
- Exercise drafting, attempts, grading, review scheduling, learning-state
  updates, reports, tool-verification records, and checklist quality gates.
- v0.4 exercise schema parsing, per-exercise validation reports, project
  validation manifests, and an approved exercise-bank manifest.
- v0.5 deterministic session score reports that compose ingestion, note,
  exercise, exercise validation, and tutoring quality gates into a persisted
  teaching-quality score.
- v0.7 deterministic next-session handoff plans that combine due reviews,
  previous session artifacts, queue counts, and Reference KB context into a
  reviewable plan/manifest for the next session.
- v0.9 deterministic session closeout workflow that runs session scoring,
  next-session handoff planning, and project-summary refresh in one repeatable
  post-session command.
- v0.10 status and lifecycle visibility for session closeout manifests, with
  missing, corrupt, or `needs_attention` closeouts treated conservatively.
- v0.11 deterministic multi-session regression reports that verify a ready
  closeout carries into visible next-session artifacts, status, and lifecycle
  readiness.
- v0.12 workflow action queue visibility for deterministic follow-up commands,
  currently including missing or invalid multi-session regression after a ready
  closeout.
- v0.13 priority action queue navigation that folds workflow, quality,
  verification, export, note, review, exercise, and grading actions into one
  deterministic operator-facing next-action view.
- v0.14 priority action snapshots in weekly, monthly, and project-summary
  reports, with report staleness tracking workflow/regression manifests that
  can change the next-action view.
- v0.15 recommended focus summaries in weekly, monthly, and project-summary
  reports, combining the first priority action, weakest concept, next review,
  and active misconception from existing deterministic evidence.
- v0.16 action summary rows in queue and learning reports, classifying open
  work into blocker, continue-learning, and human-review counts with the same
  deterministic next action used by the priority queue.
- v0.17 repair path rows in queue and learning reports, showing blocker-only
  workflow, quality-check, and tool-verification actions without mixing in
  ordinary study or review work.
- v0.18 risk summary rows in weekly, monthly, and project-summary reports,
  showing deterministic current-state pressure from blockers, reviews,
  human-review backlog, weak concepts, and active misconceptions.
- v0.19 trend summary rows in weekly, monthly, and project-summary reports,
  comparing current risk metrics against the previous same-type snapshot stored
  in `07_exports/reports/risk_history.json`.
- v0.20 report-history audit rows in `status` and project-summary reports,
  exposing risk-history health, snapshot count, and latest snapshot without
  requiring users to inspect raw JSON.
- v0.21 long-term multi-session regression refreshes project-summary output
  after the regression manifest is written, verifies long-term report sections
  and report-history artifacts, and leaves status/report views aligned after a
  realistic closeout -> regression cycle.
- v0.22 read-only study dashboards summarize existing status, queue, report,
  report-history, closeout, and regression evidence into one operator-facing
  Markdown view.
- v0.23 generated study-start briefs write `07_exports/briefs/study_brief.md`
  from existing dashboard and queue evidence so the next action can be saved
  before starting a learning session.
- v0.24 study brief status rows in `dashboard` and `status` show whether the
  brief's recorded next action is current, stale, missing, or invalid compared
  with the current priority queue first action.
- v0.25 generated study-start briefs also write
  `07_exports/briefs/study_brief_manifest.json`; status readers prefer this
  structured manifest and use Markdown parsing only as a legacy fallback.
- v0.26 `brief status` reports the manifest-backed brief freshness fields
  without writing artifacts; `brief generate` is the explicit write command,
  while legacy `brief --project <project>` remains supported.
- v0.27 `resume` renders a compact read-only returning-learner card that says
  whether the saved study brief is ready or should be regenerated before
  continuing.
- v0.28 `resume --json` emits the same read-only resume state as structured
  JSON with `quality_boundary: deterministic_project_resume` for future UI or
  plugin wrappers.
- v0.29 `projects resume --root <root>` renders a read-only resume index
  across a SocratesProjects root, reusing each project's deterministic resume
  payload so collection navigation does not duplicate status logic or write
  child-project artifacts.
- v0.30 `projects resume --root <root> --json` emits the same collection
  readiness state as structured JSON with
  `quality_boundary: deterministic_project_resume_index` for future UI or
  plugin wrappers.
- v0.31 collection resume outputs include ready and refresh-brief counts so a
  project root can be scanned without reading every row.
- v0.32 `projects resume --state all|ready|refresh_brief` filters collection
  resume output after building the same structured rows, for both Markdown and
  JSON.
- v0.33 collection resume outputs include a derived recommended-command summary
  so filtered project-root views show which child-project commands should be run
  next without executing them.
- v0.34 `projects resume --commands` prints only the derived child-project
  command lines for the active state filter, with `--json` and `--commands`
  kept mutually exclusive.
- Opt-in DeepSeek-backed draft suggestions for reference correction patches,
  tutoring next questions, exercise feedback proposals, and review-only session
  judge observations, tracked through an LLM suggestion manifest.

## Boundaries

- No runtime third-party dependencies are required.
- Bundled PDF/OCR conversion is intentionally not implemented yet; unsupported
  PDFs produce conversion-pending artifacts until the user attaches an external
  Markdown conversion.
- External conversions are review-gated drafts. They do not bypass curation,
  Reference KB provenance checks, or user review.
- v0.3 adds an opt-in LLM provider layer for draft suggestions only. The default
  CLI workflow remains deterministic and offline; live DeepSeek calls require
  local `.env` configuration and are not part of the default check gate.
- LLM output never directly overwrites curated references, reviewed notes,
  graded attempts, or learning-state truth.
- LLM session judge drafts are review-only observations. They are not trusted
  grades, deterministic session scores, readiness gates, formal teaching
  evaluations, proofs, or learning-state updates.
- Exercise validation and counterexample search are advisory review evidence.
  Passing validation does not prove mathematical correctness or approve a draft.
- Session scores and benchmark gates are deterministic checklist summaries, not
  an LLM judge or a formal teaching-quality proof.
- Next-session handoff plans are deterministic planning artifacts. They do not
  run autonomous tutoring, grade the learner, call an LLM judge, or mutate
  learning-state truth.
- Session closeout is a deterministic workflow composition. It does not override
  failed session score gates; failed scores produce a `needs_attention`
  closeout manifest for human follow-up, and lifecycle audit treats that as not
  ready.
- Multi-session regression is deterministic artifact evidence. It checks the
  persisted closeout, completed/next session artifacts, handoff manifest,
  project summary visibility, long-term report sections, and report-history
  artifact health; it is not an LLM judge, mathematical proof, prediction,
  grade, autonomous tutor, or learning-state truth source.
- Workflow action queue entries are operational prompts. They do not create a
  new readiness gate, mutate project state, or replace lifecycle/regression
  checks.
- Priority queue entries are a virtual rendering of existing queue items. They
  do not create new artifacts, readiness gates, scores, or project mutations.
- Report priority snapshots reuse the same queue evidence. They do not create a
  new report score, readiness gate, artifact writer, or learning-state truth.
- Recommended focus rows are deterministic report summaries. They do not run
  tutoring, plan a session, score learning quality, or mutate learning state.
- Action summary rows are deterministic queue/report summaries. They do not
  create a new readiness gate, score, planner, tutor, or learning-state truth.
- Repair path rows are deterministic blocker summaries. They do not run repair
  commands, fix artifacts, create a readiness gate, or mutate project state.
- Risk summary rows are deterministic current-state report snapshots over
  existing queue and learning-state evidence. They are not historical analytics,
  prediction, scoring, grading, tutoring, planning, readiness gates, or
  learning-state mutation.
- Trend summary rows are deterministic comparisons over bounded report risk
  snapshots. They are not predictions, learning-quality scores, grades,
  tutoring decisions, plans, readiness gates, or learning-state mutation.
- Report-history audit rows are deterministic visibility over existing trend
  artifacts. They are not new readiness gates, scores, predictions, planners,
  tutors, or learning-state truth.
- Study dashboards are read-only compositions over existing deterministic
  evidence. They do not create new truth, run repairs, generate reports, call an
  LLM, approve artifacts, score learning, tutor, predict, or mutate project
  state.
- Study-start briefs are deterministic export artifacts. Aside from writing the
  brief and a project-log entry, they do not run repairs, refresh reports, call
  an LLM, approve artifacts, score learning, tutor, predict, or mutate
  learning-state truth.
- Study brief status is a next-action freshness check. It compares the brief's
  recorded next action with the current priority queue first action; it is not
  a full report freshness system, readiness gate, score, tutor, or project
  mutation.
- Study brief manifests are deterministic metadata for the brief artifact only.
  A malformed manifest is reported conservatively as invalid; manifest status is
  not mathematical validation, report freshness, tutoring, scoring, or approval.
- `brief status` is a read-only inspection command over that status reader. It
  does not generate briefs, append project-log entries, refresh reports, call an
  LLM, repair artifacts, score learning, tutor, or mutate learning-state truth.
- `resume` is a read-only returning-learner view. It can recommend
  `brief generate` when the saved brief is missing, stale, or invalid, but it
  does not run that command or mutate project state.
- `resume --json` is the same read-only state as machine-readable output. It is
  not a new writer, score, project-readiness gate, or learning-state truth.
- `projects resume` is a read-only collection view over per-project resume
  payloads. It does not generate briefs, refresh reports, run repairs, call an
  LLM, score learning, or mutate any child project.
- `projects resume --json` is the same read-only collection state as
  machine-readable output. It is not a scanner, generator, writer, score,
  project-readiness gate, or child-project state mutation.
- Collection resume readiness counts are read-only scan aids derived from
  `resume_state` rows. They are not scores, readiness gates, predictions, or
  project-state mutations.
- `projects resume --state` filters existing collection rows. It is not a
  scanner, score, readiness gate, report generator, writer, or child-project
  state mutation.
- Collection resume recommended-command summaries are derived from returned
  rows. They are not command execution, batch automation, scanners, scores,
  readiness gates, report generation, LLM calls, or child-project mutations.
- `projects resume --commands` is an output/copy mode over those derived command
  rows. It is not command execution, batch automation, a generator, scanner,
  score, readiness gate, report generator, LLM call, or child-project mutation.
- Checklist quality gates are conservative heuristics, not formal mathematical
  verification.
- Lean/Sage/GAP/SymPy integrations depend on the corresponding external tools
  being installed.

## Development

Run the local checks on Windows:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/check.ps1
```

Run the equivalent checks from a POSIX shell:

```bash
bash scripts/check.sh
```

Both scripts run the unittest suite, compile the `socrates` package, and check
for whitespace errors with `git diff --check`.

The long-term development target, phased roadmap, and current development log
are stored in `docs/`.

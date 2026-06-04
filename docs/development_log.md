# Socrates 开发日志

更新时间：2026-06-04

当前分支：`codex/v02-closure`

## 当前阶段

Socrates 已从最初的 Python CLI skeleton 推进到可运行的本地数学学习 CLI 原型。v0.1/v0.2 的确定性学习闭环、Reference KB 与 Obsidian 笔记沉淀已经落地；当前实现已推进到 v0.39-alpha 的 targeted limit-controlled dry-run-previewable structured batch-refreshable commands-output command-summarized filterable readiness-counted multi-project resume index 层。

当前分支相对早期主线已有大量功能提交。最近一组工作从 Reference KB reader gate 和 v0.3 LLM draft 边界继续推进到 v0.39 projects refresh-briefs project-id targeting：生成 artifact 不能只存在，还必须结构有效、来源可追溯，并且直接读取型 CLI 不能绕过 readiness/validation 门禁；长期使用时的下一步操作、阻塞项、可继续学习项、人工审核项、修复路径、当前风险压力、同类型报告之间的风险变化、report history artifact 健康状态、regression manifest 写入后的报告/status 一致性、可读的一屏 operator dashboard、可保存的学习启动 brief、旧 brief 是否仍对应当前 first next action、新 brief 的结构化 manifest、只读检查 brief freshness 的命令、返回学习项目时的只读 resume card、给未来 UI/plugin 读取的 resume JSON、跨项目根目录的返回学习 ready/refresh 导航、给未来 UI/plugin 读取的 collection-level JSON、project root 的 ready/refresh_brief 分布、按 resume state 筛选项目根目录视图、从 filtered rows 派生出的推荐命令摘要、只输出推荐命令行的 copy mode、只对 refresh_brief 子项目写 brief 的 collection writer、该 writer 的 structured JSON result、该 writer 的 no-write dry-run preview、该 writer 的 bounded execution limit，以及该 writer 的 target-by-project-id filter 都必须清楚可见。

## v0.2 收口基线

本轮收口目标是把 `feature/v0.2-reference-kb-obsidian` 固化为可信的 v0.2 基线，而不是立即进入智能层大改。

当前核对结果：

- 当前分支：`feature/v0.2-reference-kb-obsidian`。
- 远端同步：本地 `HEAD` 与 `origin/feature/v0.2-reference-kb-obsidian` 为 `0 ahead / 0 behind`。
- 工作树：收口开始前干净。
- 基线门禁：`powershell -ExecutionPolicy Bypass -File scripts\check.ps1` 通过，327 tests OK。
- 新增跨平台门禁入口：`scripts/check.sh` 与 PowerShell 脚本执行同一组检查。

## 已完成能力

### v0.1 最小学习闭环

- 项目初始化：创建标准学习项目目录、元数据、初始状态文件。
- 本地参考资料导入：支持 Markdown/TXT/PDF 等本地文件进入 reference registry。
- 参考资料转换与 curated markdown：支持转换 pending、curation patch、curated reference 管理。
- 学习计划生成：从主题、目标、reference registry 与 Reference KB 生成长期、短期和 session plan。
- 引导式教学 session：支持 deterministic script 驱动的 Socratic session，并输出 transcript、summary 与 misconceptions。
- 原子笔记草稿：生成 Obsidian-compatible draft note，默认进入 review 流程。
- 练习生成：生成 exercise draft、hint、solution outline、rubric、concept tags。
- 学习状态与错因：维护 `learning_state.json`、mistake bank、misconception records。
- 状态与报告：`socrates status` 汇总当前阶段、待办、质量检查、导出情况。

### v0.2 Reference KB

- 从 curated Markdown 抽取 definition/theorem/proposition/lemma/corollary/example/counterexample/proof/exercise/remark/notation 等对象。
- 写入 `06_kb/chunks/reference_index.json`、`concept_graph.json`、`dependency_graph.json`、`chapter_index.json`、`theorem_index.json`、`exercise_index.json`。
- 支持 KB 检索、对象列表、章节索引、关系列表、counterexample 查询。
- Reference KB stale/missing/invalid 状态已接入 `status`、plan、notes、exercises、tool verification、lifecycle audit 等路径。
- provenance 校验已覆盖：
  - 主 reference index 的 object/chunk source path、line、source text。
  - chunk metadata 与 object provenance 的一致性。
  - chapter index nested section/object source path。
  - theorem/exercise derived indexes 的 object source 与 statement。
  - concept/dependency graph 的 node/edge schema 和 relationship 约束。
- 直接 reader 已开始复用 status validator，避免 `kb chapters` / `kb relationships` 绕过 readiness gate。

### v0.2 Obsidian 笔记流

- draft note 默认不污染正式知识库。
- reviewed note 可导出到 `07_exports/obsidian/`。
- 导出 manifest、backlink section、wikilink backlink resolution 已有测试覆盖。
- stale Socrates-generated export 会被清理，同时避免误删用户手写 Markdown。
- `status` 与 lifecycle audit 会识别 reviewed notes pending Obsidian export。

### 质量门禁

- 当前全量门禁：`powershell -ExecutionPolicy Bypass -File scripts\check.ps1`
- 最近一次结果：402 tests OK，1 skipped。
- 最近收口提交：
  - `f49a0c2 Fail fast on invalid chapter index reads`
  - `1d61f90 Fail fast on invalid concept graph reads`
  - `359e9f4 Reject malformed reference KB graph artifacts`
  - `1c9e53b Validate derived KB object provenance`

## v0.3 LLM provider alpha

- Added local `.env` based LLM provider configuration with redacted status output.
- Added DeepSeek provider adapter using `DEEPSEEK_MODEL=deepseek-v4-pro`.
- Added LLM suggestion artifacts for reference correction patches, tutoring next questions, and exercise feedback drafts.
- Preserved the safety boundary: LLM output is reviewed draft material and does not directly mutate curated references, reviewed notes, graded attempts, or learning state.
- Default gates remain offline; live DeepSeek smoke is opt-in.

## v0.4 Exercise bank and validation alpha

- Added `socrates/exercise_schema.py` to parse generated exercise Markdown into structured schema objects and validate status, review status, exercise type, concept, difficulty, hints, solution steps, rubric totals, prerequisites, and common mistakes.
- Added `socrates/exercise_validation.py` and `python -m socrates exercise validate` to write per-exercise JSON/Markdown reports under `08_evals/exercise_validation/` plus `08_evals/exercise_validation_manifest.json`.
- Added `socrates/exercise_bank.py` and `python -m socrates exercise bank build/status`; the bank manifest includes only human-approved exercises with passing validation evidence.
- Exercise quality manifests now include v0.4 validation evidence while preserving the older checklist pass/fail behavior for compatibility.
- Benchmark now has five gates: ingestion, note quality, exercise quality, exercise validation, and tutoring quality.
- Lifecycle audit now checks exercise validation and exercise bank readiness separately.
- Safety boundary: validation, rubric checks, and Reference KB counterexample search are advisory evidence only; they do not prove correctness, approve drafts, or mutate learner mastery.
- Verification evidence:
  - `python -m unittest tests.test_exercise_schema tests.test_exercise_validation tests.test_exercise_bank tests.test_v04_exercise_flow` passed.
  - `python -m unittest tests.test_exercise_quality tests.test_status_quality_summary tests.test_benchmark tests.test_lifecycle_audit` passed.
  - `python -m unittest discover -s tests` passed with 356 tests OK and 1 skipped.
  - `python -m compileall socrates` passed.
  - `git diff --check` passed.
  - `powershell -ExecutionPolicy Bypass -File scripts\check.ps1` passed with 356 tests OK and 1 skipped.
  - `bash scripts/check.sh` passed with 356 tests OK and 1 skipped; WSL emitted a localhost/line-ending warning, but the script exit code was 0.

## v0.5 Teaching quality evaluation alpha

- Added `socrates/session_score.py` and `python -m socrates session score` to write `08_evals/session_score_report.md` plus `08_evals/session_score_manifest.json`.
- Session scoring composes the existing deterministic gates: ingestion, note quality, exercise quality, exercise validation, and tutoring quality.
- `status` now reports session score, gates, and failed gates from the persisted manifest with conservative invalid/not-run handling.
- Project summary reports now include a Session Score Snapshot and become stale when the session score manifest changes.
- Lifecycle audit now requires both a fresh session score report and a valid passing session score manifest before claiming a complete learning loop.
- Safety boundary: v0.5 session scores are deterministic checklist summaries. They are not LLM judge outputs, formal proof of mathematical correctness, or automatic learner-state/trust mutation.
- Verification evidence:
  - `python -m unittest tests.test_session_score` passed.
  - `python -m unittest tests.test_status_quality_summary` passed.
  - `python -m unittest tests.test_reports` passed.
  - `python -m unittest tests.test_lifecycle_audit` passed.
  - `python -m unittest tests.test_benchmark tests.test_tutoring_quality` passed.
  - `python -m unittest discover -s tests` passed with 359 tests OK and 1 skipped.
  - `python -m compileall socrates` passed.
  - `git diff --check` passed.
  - `powershell -ExecutionPolicy Bypass -File scripts\check.ps1` passed with 359 tests OK and 1 skipped.
  - `bash scripts/check.sh` passed with 359 tests OK and 1 skipped; WSL emitted a localhost/line-ending warning, but the script exit code was 0.

## v0.6 External conversion handoff alpha

- Added `attach_converted_markdown` and `python -m socrates sources attach-conversion` for explicit external Markdown conversion handoff.
- A PDF or other imported source can move from `conversion_pending` to `curated_draft` when the user provides a converted Markdown file.
- The raw imported source file is preserved; Socrates writes a project-local converted Markdown artifact and curated draft instead of mutating raw references.
- Converted artifacts record the raw source path, external conversion source, and `external_markdown_handoff` policy.
- Safety boundary: v0.6 does not bundle OCR/PDF extraction or trust external conversions automatically. The attached conversion remains a review-gated curated draft and must pass Reference KB/quality gates before downstream trust.
- Verification evidence:
  - `python -m unittest tests.test_reference_import` passed.
  - `python -m unittest discover -s tests` passed with 361 tests OK and 1 skipped.
  - `python -m compileall socrates` passed.
  - `git diff --check` passed.
  - `powershell -ExecutionPolicy Bypass -File scripts\check.ps1` passed with 361 tests OK and 1 skipped.
  - `bash scripts/check.sh` passed with 361 tests OK and 1 skipped; WSL emitted a localhost/line-ending warning, but the script exit code was 0.

## v0.7 Next-session handoff alpha

- Added `create_next_session_plan` and `python -m socrates session plan-next` to write deterministic next-session handoff plans.
- The handoff plan combines due review items, previous session summary/next actions/misconceptions, action queue counts, Reference KB context, and a suggested teaching-move checklist.
- Added `02_learning_plan/next_session_plan_manifest.json` with `quality_boundary: deterministic_handoff_plan`, due/future/invalid review counts, Reference KB status, and action queue counts.
- `status` now reports next session plan id, due reviews, and handoff status from the manifest.
- Project summary reports now include a Next Session Handoff Snapshot and become stale when the handoff manifest changes.
- Safety boundary: v0.7 does not run autonomous tutoring, grade the learner, call an LLM judge, or mutate learning-state truth. It is a deterministic pre-session planning artifact.
- Verification evidence:
  - `python -m unittest tests.test_learning_plan tests.test_reports tests.test_status_quality_summary` passed with 64 tests OK after adding project-summary freshness coverage.
  - `python -m unittest discover -s tests` passed with 366 tests OK and 1 skipped.
  - `python -m compileall socrates` passed.
  - `git diff --check` passed.
  - `powershell -ExecutionPolicy Bypass -File scripts\check.ps1` passed with 366 tests OK and 1 skipped.
  - `bash scripts/check.sh` passed with 366 tests OK and 1 skipped; WSL emitted a localhost/line-ending warning, but the script exit code was 0.

## v0.8 LLM judge boundary alpha

- Added `socrates/llm_judge.py` and `python -m socrates session judge-suggest` for review-only LLM session judge drafts.
- Drafts are written to `03_sessions/<session_id>/llm_session_judge.md` with `quality_boundary: review_only_llm_judge_draft`.
- `08_evals/llm_suggestions_manifest.json` records the draft as `session_quality_judge` with source paths and prompt hash.
- Tests cover strict JSON validation and verify the LLM judge draft does not mutate the transcript, learning state, or deterministic session score manifest.
- Safety boundary: v0.8 LLM judge drafts are observations for human review. They are not trusted grades, deterministic scores, readiness gates, proofs, formal teaching evaluations, or learning-state updates.
- Verification evidence:
  - `python -m unittest tests.test_llm_judge` passed.
  - `python -m unittest tests.test_llm_judge tests.test_llm_tutoring_suggestions tests.test_llm_provider_contract` passed with 6 tests OK.
  - `python -m unittest discover -s tests` passed with 369 tests OK and 1 skipped.
  - `python -m compileall socrates` passed.
  - `git diff --check` passed.
  - `powershell -ExecutionPolicy Bypass -File scripts\check.ps1` passed with 369 tests OK and 1 skipped.
  - `bash scripts/check.sh` passed with 369 tests OK and 1 skipped; WSL emitted a localhost/line-ending warning, but the script exit code was 0.

## v0.9 Session closeout workflow alpha

- Added `socrates/workflow.py` and `python -m socrates session closeout` for deterministic post-session closeout.
- Closeout composes existing trusted surfaces: session score, next-session handoff plan, and project summary refresh.
- `08_evals/session_closeout_manifest.json` records `quality_boundary: deterministic_session_closeout`, current/next session ids, score status, score value, and generated artifact paths.
- Failed deterministic score gates do not stop artifact generation; they produce `status: needs_attention` so the next review step is explicit.
- Safety boundary: v0.9 closeout is a workflow composition, not a new score, LLM judge, automatic pass, proof, or learning-state truth mutation.
- Verification evidence:
  - `python -m unittest tests.test_session_closeout` passed.
  - `python -m unittest tests.test_session_closeout tests.test_session_score tests.test_learning_plan tests.test_reports` passed with 45 tests OK.
  - `python -m unittest discover -s tests` passed with 371 tests OK and 1 skipped.
  - `python -m compileall socrates` passed.
  - `git diff --check` passed.
  - `powershell -ExecutionPolicy Bypass -File scripts\check.ps1` passed with 371 tests OK and 1 skipped.
  - `bash scripts/check.sh` passed with 371 tests OK and 1 skipped; WSL emitted a localhost/line-ending warning, but the script exit code was 0.

## v0.10 Closeout status and lifecycle visibility alpha

- Added `socrates/workflow_manifest.py` as a neutral reader for `08_evals/session_closeout_manifest.json`.
- `status` now reports session closeout state, current/next session ids, and the closeout score snapshot.
- Lifecycle audit now includes `Session closeout manifest` and only passes it for valid `ready` closeouts.
- Missing, corrupt, malformed, or `needs_attention` closeout manifests remain conservative lifecycle failures.
- Safety boundary: v0.10 does not make closeout a new scoring authority. It only makes workflow evidence visible and readiness-gated.
- Verification evidence:
  - `python -m unittest tests.test_session_closeout tests.test_status_quality_summary tests.test_lifecycle_audit` passed with 42 tests OK.
  - `python -m unittest discover -s tests` passed with 372 tests OK and 1 skipped.
  - `python -m compileall socrates` passed.
  - `git diff --check` passed.
  - `powershell -ExecutionPolicy Bypass -File scripts\check.ps1` passed with 372 tests OK and 1 skipped.
  - `bash scripts/check.sh` passed with 372 tests OK and 1 skipped; WSL emitted a localhost/line-ending warning, but the script exit code was 0.

## v0.11 Multi-session regression alpha

- Added `socrates/multi_session.py` and `python -m socrates lifecycle regression` for deterministic product-loop regression across a completed session and its next session.
- The command writes `08_evals/multi_session_regression.md` plus `08_evals/multi_session_regression_manifest.json`.
- Regression checks the ready closeout manifest, completed session artifacts, next session artifacts, next-session handoff manifest, and project summary refresh.
- `status` now reports multi-session regression status, passed checks, and issue summary with conservative invalid/not-run handling.
- Lifecycle audit now includes `Multi-session regression` and only passes it for valid `status: pass` regression manifests.
- Safety boundary: v0.11 multi-session regression is deterministic artifact evidence for product-loop continuity. It is not an LLM judge, mathematical proof, grade, new score, or learning-state truth source.
- Verification evidence:
  - `python -m unittest tests.test_multi_session_regression tests.test_status_quality_summary tests.test_lifecycle_audit` passed with 42 tests OK.
  - `python -m unittest discover -s tests` passed with 375 tests OK and 1 skipped.
  - `python -m compileall socrates` passed.
  - `git diff --check` passed.
  - `powershell -ExecutionPolicy Bypass -File scripts\check.ps1` passed with 375 tests OK and 1 skipped.
  - `bash scripts/check.sh` passed with 375 tests OK and 1 skipped; WSL emitted a localhost/line-ending warning and a line-ending warning for `scripts/check.ps1`, but the script exit code was 0.

## v0.12 Workflow action queue alpha

- Extended `socrates.learning_queue` with a `workflow` queue section for deterministic follow-up commands.
- `queue --section workflow` now lists a missing multi-session regression action after a ready closeout and an invalid regression rerun action for corrupt manifests.
- `status` now reports `Workflow actions: <count>` alongside other queue/action counts.
- Safety boundary: v0.12 workflow action queue entries are operational UX only. They do not create a new readiness gate, mutate project state, or replace lifecycle/regression checks.
- Verification evidence:
  - `python -m unittest tests.test_learning_queue` passed with 18 tests OK.
  - `python -m unittest tests.test_learning_queue tests.test_status_quality_summary tests.test_multi_session_regression` passed with 44 tests OK.
  - `python -m unittest discover -s tests` passed with 377 tests OK and 1 skipped.
  - `python -m compileall socrates` passed.
  - `git diff --check` passed.
  - `powershell -ExecutionPolicy Bypass -File scripts\check.ps1` passed with 377 tests OK and 1 skipped.
  - `bash scripts/check.sh` passed with 377 tests OK and 1 skipped; WSL emitted localhost and `scripts/check.ps1` line-ending warnings, but the script exit code was 0.

## v0.13 Priority action queue alpha

- Extended `socrates.learning_queue` with a virtual `priority` queue section.
- `queue --section priority` now renders existing queue items in deterministic operator order: workflow, quality checks, tool verifications, Obsidian exports, notes, misconceptions, reviews, exercise drafts, exercises, and attempts.
- Priority rows prefix item ids with their source section, for example `workflow:multi_session_regression`, so cross-section actions remain unambiguous.
- Empty projects render `## Priority Actions` with `- none`.
- Safety boundary: v0.13 priority actions are a rendering of existing queue evidence only. They do not create new artifacts, readiness gates, scores, or project-state mutations.
- Verification evidence:
  - `python -m unittest tests.test_learning_queue` passed with 20 tests OK.
  - `python -m unittest tests.test_learning_queue tests.test_status_quality_summary tests.test_multi_session_regression` passed with 46 tests OK.
  - `python -m unittest discover -s tests` passed with 379 tests OK and 1 skipped.
  - `python -m compileall socrates` passed.
  - `git diff --check` passed.
  - `powershell -ExecutionPolicy Bypass -File scripts\check.ps1` passed with 379 tests OK and 1 skipped.
  - `bash scripts/check.sh` passed with 379 tests OK and 1 skipped; WSL emitted localhost text and a `scripts/check.ps1` line-ending warning, but the script exit code was 0.

## v0.14 Report priority action snapshot alpha

- Weekly, monthly, and project-summary reports now include a `## Priority Actions` section.
- Report priority rows reuse the same deterministic priority ordering and source-section item ids as `queue --section priority`.
- Report stale detection now includes closeout, multi-session regression, artifact-quality, and tool-verification quality manifests so priority snapshots do not remain marked generated after workflow evidence changes.
- Safety boundary: v0.14 report priority snapshots are report UX over existing queue evidence. They are not new readiness gates, report scores, artifact writers, or learning-state truth.
- Verification evidence:
  - `python -m unittest tests.test_reports` passed with 32 tests OK.
  - `python -m unittest tests.test_reports tests.test_learning_queue` passed with 52 tests OK.
  - `python -m unittest tests.test_reports tests.test_learning_queue tests.test_session_closeout` passed with 55 tests OK after fixing closeout summary refresh ordering.
  - `python -m unittest discover -s tests` passed with 382 tests OK and 1 skipped.
  - `python -m compileall socrates` passed.
  - `git diff --check` passed.
  - `powershell -ExecutionPolicy Bypass -File scripts\check.ps1` passed with 382 tests OK and 1 skipped.
  - `bash scripts/check.sh` passed with 382 tests OK and 1 skipped; WSL emitted localhost text and a `scripts/check.ps1` line-ending warning, but the script exit code was 0.

## v0.15 Report recommended focus alpha

- Weekly, monthly, and project-summary reports now include a `## Recommended Focus` section.
- Recommended Focus summarizes the first priority action, weakest concept, next scheduled review, and first active misconception from existing deterministic evidence.
- Empty projects and missing evidence render stable fallback rows instead of inventing recommendations.
- Safety boundary: v0.15 recommended focus rows are report summaries only. They do not run tutoring, plan a session, score learning quality, create a readiness gate, or mutate learning state.
- Verification evidence:
  - `python -m unittest tests.test_reports` passed with 35 tests OK.
  - `python -m unittest tests.test_reports tests.test_learning_queue` passed with 55 tests OK.
  - `python -m unittest discover -s tests` passed with 385 tests OK and 1 skipped.
  - `python -m compileall socrates` passed.
  - `git diff --check` passed.
  - `powershell -ExecutionPolicy Bypass -File scripts\check.ps1` passed with 385 tests OK and 1 skipped.
  - `bash scripts/check.sh` passed with 385 tests OK and 1 skipped; WSL emitted localhost text and a `scripts/check.ps1` line-ending warning, but the script exit code was 0.

## v0.16 Action summary alpha

- `queue --section summary` now renders `## Action Summary`; default queue output shows the same summary before `## Priority Actions`.
- Weekly, monthly, and project-summary reports now include a `## Action Summary` section after `## Recommended Focus`.
- Action Summary classifies existing queue buckets into open actions, blockers, can-continue-learning actions, human-review actions, and the first priority next action.
- Safety boundary: v0.16 action summary rows are queue/report summaries only. They do not create a readiness gate, score, planner, tutor, or learning-state mutation.
- Verification evidence:
  - `python -m unittest tests.test_learning_queue` passed with 23 tests OK.
  - `python -m unittest tests.test_reports` passed with 37 tests OK.
  - `python -m unittest tests.test_learning_queue tests.test_reports` passed with 60 tests OK.
  - `python -m unittest discover -s tests` passed with 390 tests OK and 1 skipped.
  - `python -m compileall socrates` passed.
  - `git diff --check` passed.
  - `powershell -ExecutionPolicy Bypass -File scripts\check.ps1` passed with 390 tests OK and 1 skipped.
  - `bash scripts/check.sh` passed with 390 tests OK and 1 skipped; WSL emitted localhost text and a `scripts/check.ps1` line-ending warning, but the script exit code was 0.

## v0.17 Repair paths alpha

- `queue --section repairs` now renders `## Repair Paths`; default queue output shows repair paths after action summary and before priority actions.
- Weekly, monthly, and project-summary reports now include a `## Repair Paths` section after `## Action Summary`.
- Repair Paths summarize blocker-only queue buckets: workflow actions, artifact quality checks, and tool-verification fixes.
- Test fixture stabilization: report tests now pin review scheduling to `2026-06-04` instead of depending on the machine date.
- Safety boundary: v0.17 repair path rows are queue/report summaries only. They do not run repair commands, fix artifacts, create a readiness gate, score, planner, or learning-state mutation.
- Verification evidence:
  - `python -m unittest tests.test_reports.ReportTests.test_monthly_report_includes_recommended_focus` passed after pinning the report fixture date.
  - `python -m unittest tests.test_learning_queue` passed with 25 tests OK.
  - `python -m unittest tests.test_reports` passed with 39 tests OK.
  - `python -m unittest tests.test_learning_queue tests.test_reports` passed with 64 tests OK.
  - `python -m unittest discover -s tests` passed with 394 tests OK and 1 skipped.
  - `python -m compileall socrates` passed.
  - `git diff --check` passed.
  - `powershell -ExecutionPolicy Bypass -File scripts\check.ps1` passed with 394 tests OK and 1 skipped.
  - `bash scripts/check.sh` passed with 394 tests OK and 1 skipped; WSL emitted localhost text and a `scripts/check.ps1` line-ending warning, but the script exit code was 0.

## v0.18 Risk summary alpha

- Weekly, monthly, and project-summary reports now include a `## Risk Summary` section after `## Repair Paths`.
- Risk Summary derives a current-state risk level from blocker pressure, review pressure, human-review backlog, weak concepts, and active misconception pressure.
- Empty projects and missing evidence render stable 0-count fallback rows.
- Safety boundary: v0.18 risk summary rows are deterministic report snapshots over existing queue and learning-state evidence. They are not historical analytics, prediction, scoring, grading, tutoring, planning, readiness gates, or learning-state mutation.

Verification evidence:
  - `python -m unittest tests.test_reports` passed with 41 tests OK after the RED run failed on the missing `## Risk Summary` section.
  - `python -m unittest discover -s tests` passed with 396 tests OK and 1 skipped.
  - `python -m compileall socrates` passed.
  - `git diff --check` passed.
  - `powershell -ExecutionPolicy Bypass -File scripts\check.ps1` passed with 396 tests OK and 1 skipped.
  - `bash scripts/check.sh` passed with 396 tests OK and 1 skipped; WSL emitted localhost text and a `scripts/check.ps1` line-ending warning, but the script exit code was 0.

## v0.19 Risk trend summary alpha

- Weekly, monthly, and project-summary reports now include a `## Trend Summary` section after `## Risk Summary`.
- Report generation writes bounded risk snapshots to `07_exports/reports/risk_history.json` after the report is rendered.
- Trend Summary compares the current risk metrics with the previous snapshot of the same report type and shows signed deltas for blocker, review, human-review, weak-concept, and active-misconception pressure.
- Safety boundary: v0.19 trend summary rows are deterministic comparisons over bounded report snapshots. They are not prediction, scoring, grading, tutoring, planning, readiness gates, or learning-state mutation.

Verification evidence:
  - `python -m unittest tests.test_reports` passed with 43 tests OK after the RED run failed on the missing `## Trend Summary` section.
  - `python -m unittest discover -s tests` passed with 398 tests OK and 1 skipped.
  - `python -m compileall socrates` passed.
  - `git diff --check` passed.
  - `powershell -ExecutionPolicy Bypass -File scripts\check.ps1` passed with 398 tests OK and 1 skipped.
  - `bash scripts/check.sh` passed with 398 tests OK and 1 skipped; WSL emitted localhost text and a `scripts/check.ps1` line-ending warning, but the script exit code was 0.

## v0.20 Report history audit alpha

- `status` now reports report-history health, snapshot count, and latest snapshot.
- Project-summary reports now include a `## Report History Snapshot` section after `## Trend Summary`.
- The public report-history summary reader lives in `socrates.reports`, so CLI code does not parse `risk_history.json` directly.
- Safety boundary: v0.20 report-history audit rows expose existing trend artifacts only. They are not new readiness gates, scores, predictions, planners, tutors, or learning-state truth.

Verification evidence:
  - `python -m unittest tests.test_status_quality_summary tests.test_reports` passed with 68 tests OK after the RED run failed on missing report-history audit rows.
  - `python -m unittest discover -s tests` passed with 400 tests OK and 1 skipped.
  - `python -m compileall socrates` passed.
  - `git diff --check` passed.
  - `powershell -ExecutionPolicy Bypass -File scripts\check.ps1` passed with 400 tests OK and 1 skipped.
  - `bash scripts/check.sh` passed with 400 tests OK and 1 skipped; WSL emitted localhost text and a `scripts/check.ps1` line-ending warning, but the script exit code was 0.

## v0.21 Long-term multi-session regression alpha

- `python -m socrates lifecycle regression` now writes a preliminary regression manifest, refreshes project-summary output, then writes the final regression report/manifest.
- The final regression now checks seven items: ready closeout, completed session artifacts, next session artifacts, next-session handoff, project summary refresh, long-term project-summary sections, and report-history artifact health.
- The regression manifest records `project_summary_path`, and the CLI prints `Project summary: <path>` alongside the regression report and manifest paths.
- A passing realistic closeout -> regression fixture now leaves `status` with `Workflow actions: 0`, `Multi-session regression checks: 7/7`, and current report-history evidence.
- Safety boundary: v0.21 long-term regression is deterministic product-loop evidence. It refreshes and audits report/status surfaces, but it is not autonomous tutoring, scoring, prediction, proof, a readiness shortcut, or learning-state truth.

Verification evidence:
  - `python -m unittest tests.test_multi_session_regression` passed with 3 tests OK after the RED run failed on the old 5-check regression output.
  - `python -m unittest tests.test_multi_session_regression tests.test_reports tests.test_status_quality_summary tests.test_learning_queue tests.test_session_closeout tests.test_lifecycle_audit` passed with 115 tests OK.
  - `python -m unittest discover -s tests` passed with 400 tests OK and 1 skipped.
  - `python -m compileall socrates` passed.
  - `git diff --check` passed.
  - `powershell -ExecutionPolicy Bypass -File scripts\check.ps1` passed with 400 tests OK and 1 skipped.
  - `bash scripts/check.sh` passed with 400 tests OK and 1 skipped; WSL emitted localhost text and a `scripts/check.ps1` line-ending warning, but the script exit code was 0.

## v0.22 Study dashboard alpha

- Added `socrates/dashboard.py` and `python -m socrates dashboard --project <project>` for a compact read-only operator dashboard.
- The dashboard composes existing deterministic evidence: queue action summary, top priority actions, report health, report-history status, session closeout status, and multi-session regression status.
- Empty projects render stable `clear` and `none` fallback rows; projects with draft notes surface the same first priority action as the priority queue.
- Safety boundary: v0.22 dashboard output is read-only composition. It does not create truth, run repairs, generate reports, call LLMs, approve artifacts, score learning, tutor, predict, or mutate project state.

Verification evidence:
  - `python -m unittest tests.test_dashboard` passed with 2 tests OK after the RED run failed because `dashboard` was not a known command.
  - `python -m unittest tests.test_dashboard tests.test_status_quality_summary tests.test_learning_queue tests.test_reports` passed with 95 tests OK.
  - `python -m unittest discover -s tests` passed with 402 tests OK and 1 skipped.
  - `python -m compileall socrates` passed.
  - `git diff --check` passed.
  - `powershell -ExecutionPolicy Bypass -File scripts\check.ps1` passed with 402 tests OK and 1 skipped.
  - `bash scripts/check.sh` passed with 402 tests OK and 1 skipped; WSL emitted localhost text and a `scripts/check.ps1` line-ending warning, but the script exit code was 0.

## v0.23 Study brief alpha

- Added `socrates/study_brief.py` and `python -m socrates brief --project <project>` for a deterministic startup brief.
- The brief writes `07_exports/briefs/study_brief.md` and appends a project-log entry.
- The `## Start Here` section surfaces the same first priority action as the queue/dashboard and classifies it as blocker, continue-learning, human-review, or none.
- The `## Dashboard Evidence` section embeds demoted dashboard Markdown so the artifact preserves snapshot, action summary, top priority actions, and report health.
- Safety boundary: v0.23 study briefs are generated export artifacts. Aside from writing the brief artifact and project-log entry, they do not run repairs, refresh reports, call LLMs, approve artifacts, score learning, tutor, predict, or mutate learning-state truth.

Verification evidence:
  - `python -m unittest tests.test_study_brief` passed with 2 tests OK after the RED run failed because `brief` was not a known command.
  - `python -m unittest tests.test_study_brief tests.test_dashboard tests.test_learning_queue tests.test_reports` passed with 73 tests OK.
  - `python -m unittest discover -s tests` passed with 404 tests OK and 1 skipped.
  - `python -m compileall socrates` passed.
  - `git diff --check` passed.
  - `powershell -ExecutionPolicy Bypass -File scripts\check.ps1` passed with 404 tests OK and 1 skipped.
  - `bash scripts/check.sh` passed with 404 tests OK and 1 skipped; WSL emitted localhost text and a `scripts/check.ps1` line-ending warning, but the script exit code was 0.

## v0.24 Study brief status alpha

- Added `socrates/study_brief_status.py` as a dependency-light reader for `07_exports/briefs/study_brief.md`.
- Dashboard snapshot now shows study brief status, the recorded next action, and the current next action.
- `status` CLI now shows the same three rows near report-history output.
- A generated brief is `current` when its recorded next action equals the current priority queue first action; it is `stale` when that first action changes.
- Safety boundary: v0.24 study brief status is a next-action freshness check only. It is not full report freshness, a readiness gate, score, tutor, planner, report parser, dashboard parser, LLM call, or project-state mutation.

Verification evidence:
  - `python -m unittest tests.test_study_brief` passed with 5 tests OK after the RED run failed on missing dashboard/status rows.
  - `python -m unittest tests.test_study_brief tests.test_dashboard tests.test_status_quality_summary` passed with 31 tests OK after wiring dashboard/status.
  - `python -m unittest tests.test_study_brief tests.test_dashboard tests.test_status_quality_summary tests.test_learning_queue` passed with 56 tests OK.
  - `python -m unittest discover -s tests` passed with 407 tests OK and 1 skipped.
  - `python -m compileall socrates` passed.
  - `git diff --check` passed.
  - `powershell -ExecutionPolicy Bypass -File scripts\check.ps1` passed with 407 tests OK and 1 skipped.
  - `bash scripts/check.sh` passed with 407 tests OK and 1 skipped; WSL emitted localhost text and a `scripts/check.ps1` line-ending warning, but the script exit code was 0.

## v0.25 Study brief manifest alpha

- `python -m socrates brief --project <project>` now writes `07_exports/briefs/study_brief_manifest.json` beside the Markdown brief.
- The manifest records schema version, deterministic boundary, generated status, brief path, recorded next action, and action type.
- `socrates.study_brief_status` now prefers the manifest for newly generated briefs and treats malformed manifests conservatively as `invalid`.
- Legacy Markdown fallback remains only when a brief exists without a manifest.
- Safety boundary: v0.25 manifests are deterministic metadata for the brief artifact only. They are not mathematical validation, report freshness, approval, score, tutor, planner, LLM call, or project-state mutation.

Verification evidence:
  - `python -m unittest tests.test_study_brief` passed with 8 tests OK after the RED run failed because the manifest was missing and corrupt manifests were ignored.
  - `python -m unittest tests.test_study_brief tests.test_dashboard tests.test_status_quality_summary` passed with 33 tests OK after implementation.
  - `python -m unittest tests.test_study_brief tests.test_dashboard tests.test_status_quality_summary tests.test_learning_queue` passed with 59 tests OK.
  - `python -m unittest discover -s tests` passed with 410 tests OK and 1 skipped.
  - `python -m compileall socrates` passed.
  - `git diff --check` passed.
  - `powershell -ExecutionPolicy Bypass -File scripts\check.ps1` passed with 410 tests OK and 1 skipped.
  - `bash scripts/check.sh` passed with 410 tests OK and 1 skipped; WSL emitted localhost text and a `scripts/check.ps1` line-ending warning, but the script exit code was 0.

## v0.26 Study brief status command alpha

- Added `python -m socrates brief status --project <project>` for read-only study brief freshness inspection.
- Added `python -m socrates brief generate --project <project>` as the explicit write command for `study_brief.md` and `study_brief_manifest.json`.
- Preserved legacy `python -m socrates brief --project <project>` generation compatibility.
- `brief status` prints the study brief status, brief path, recorded next action, and current next action without creating brief artifacts or appending `Generated study brief.` to the project log.
- Safety boundary: v0.26 brief status is a read-only CLI view over existing manifest-backed freshness evidence. It is not a generator, report refresh, repair runner, LLM call, score, tutor, planner, approval, readiness gate, or learning-state mutation.

Verification evidence:
  - `python -m unittest tests.test_study_brief` failed during RED because `brief status` and `brief generate` were not registered commands.
  - `python -m unittest tests.test_study_brief tests.test_dashboard tests.test_status_quality_summary` passed with 37 tests OK after implementation.
  - `python -m unittest tests.test_study_brief tests.test_dashboard tests.test_status_quality_summary tests.test_learning_queue` passed with 62 tests OK.
  - `python -m unittest discover -s tests` passed with 413 tests OK and 1 skipped.
  - `python -m compileall socrates` passed.
  - `git diff --check` passed.
  - `powershell -ExecutionPolicy Bypass -File scripts\check.ps1` passed with 413 tests OK and 1 skipped.
  - `bash scripts/check.sh` passed with 413 tests OK and 1 skipped; WSL emitted localhost text and a `scripts/check.ps1` line-ending warning, but the script exit code was 0.

## v0.27 Project resume command alpha

- Added `socrates/resume.py` and `python -m socrates resume --project <project>` for a compact returning-learner card.
- The resume output reports project title, root, resume state, study brief status/path, current next action, and a recommended command.
- A current saved brief yields `Resume state: ready` and `Recommended command: none`.
- Missing, stale, or invalid brief status yields `Resume state: refresh_brief` and recommends `python -m socrates brief generate --project "<project>"`.
- Safety boundary: v0.27 resume is a read-only view over existing deterministic evidence. It can recommend brief generation, but it does not generate briefs, refresh reports, run repairs, call an LLM, approve artifacts, score learning, tutor, predict, or mutate project state.

Verification evidence:
  - `python -m unittest tests.test_resume` failed during RED because `resume` was not a known command.
  - `python -m unittest tests.test_resume tests.test_study_brief tests.test_dashboard tests.test_status_quality_summary` passed with 40 tests OK after implementation.
  - `python -m unittest tests.test_resume tests.test_study_brief tests.test_dashboard tests.test_status_quality_summary tests.test_learning_queue` passed with 65 tests OK.
  - `python -m unittest discover -s tests` passed with 416 tests OK and 1 skipped.
  - `python -m compileall socrates` passed.
  - `git diff --check` passed.
  - `powershell -ExecutionPolicy Bypass -File scripts\check.ps1` passed with 416 tests OK and 1 skipped.
  - `bash scripts/check.sh` passed with 416 tests OK and 1 skipped; WSL emitted localhost text and a `scripts/check.ps1` line-ending warning, but the script exit code was 0.

## v0.28 Resume JSON alpha

- Added `socrates.resume.build_project_resume_payload(project_path)` as the single structured source for resume state.
- `python -m socrates resume --project <project> --json` now emits deterministic JSON with `schema_version: 1` and `quality_boundary: deterministic_project_resume`.
- Markdown resume output is rendered from the same payload so wrapper-facing JSON and human-facing Markdown stay aligned.
- JSON includes project title, root, resume state, study brief status/path, current next action, and recommended command.
- Safety boundary: v0.28 resume JSON is machine-readable read-only state for wrappers. It is not a writer, report refresh, repair runner, LLM call, score, tutor, planner, approval, readiness gate, or learning-state mutation.

Verification evidence:
  - `python -m unittest tests.test_resume` failed during RED because `resume --json` was not registered.
  - `python -m unittest tests.test_resume tests.test_study_brief tests.test_dashboard tests.test_status_quality_summary` passed with 42 tests OK after implementation.
  - `python -m unittest tests.test_resume tests.test_study_brief tests.test_dashboard tests.test_status_quality_summary tests.test_learning_queue` passed with 67 tests OK.
  - `python -m unittest discover -s tests` passed with 418 tests OK and 1 skipped.
  - `python -m compileall socrates` passed.
  - `git diff --check` passed.
  - `powershell -ExecutionPolicy Bypass -File scripts\check.ps1` passed with 418 tests OK and 1 skipped.
  - `bash scripts/check.sh` passed with 418 tests OK and 1 skipped; WSL emitted localhost text and a `scripts/check.ps1` line-ending warning, but the script exit code was 0.

## v0.29 Multi-project resume index alpha

- Added `socrates/project_resume.py` and `python -m socrates projects resume --root <root>` for collection-level returning-learner navigation.
- The output reports root, project count, and one row per project with project id, title, resume state, study brief status, current next action, and recommended command.
- Rows reuse `socrates.resume.build_project_resume_payload(project_path)` so the collection view shares the same read-only state contract as `resume --json`.
- Projects with current saved briefs show `ready`, `current`, and `none`; missing/stale/invalid briefs show `refresh_brief` and recommend `brief generate`.
- Safety boundary: v0.29 projects resume is a read-only collection view over existing deterministic per-project evidence. It does not generate briefs, refresh reports, run repairs, call an LLM, approve artifacts, score learning, tutor, predict, or mutate child-project state.

Verification evidence:
  - `python -m unittest tests.test_project_index` failed during RED because `projects resume` was not a registered subcommand.
  - `python -m unittest tests.test_project_index` passed with 7 tests OK after implementation.
  - `python -m unittest tests.test_project_index tests.test_resume tests.test_study_brief` passed with 23 tests OK.
  - `python -m unittest tests.test_project_index tests.test_resume tests.test_study_brief tests.test_dashboard tests.test_status_quality_summary tests.test_learning_queue` passed with 74 tests OK.
  - `python -m unittest discover -s tests` passed with 419 tests OK and 1 skipped.
  - `python -m compileall socrates` passed.
  - `git diff --check` passed.
  - `powershell -ExecutionPolicy Bypass -File scripts\check.ps1` passed with 419 tests OK and 1 skipped.
  - `bash scripts/check.sh` passed with 419 tests OK and 1 skipped; WSL emitted localhost text and a `scripts/check.ps1` line-ending warning, but the script exit code was 0.

## v0.30 Multi-project resume JSON alpha

- Added `socrates.project_resume.build_project_resume_index_payload(root_path)` as the structured source for collection resume state.
- `python -m socrates projects resume --root <root> --json` now emits deterministic JSON with `schema_version: 1` and `quality_boundary: deterministic_project_resume_index`.
- Markdown `projects resume` output is rendered from the same payload so wrapper-facing JSON and human-facing Markdown stay aligned.
- JSON includes root, project count, and one entry per project with id, title, path, resume state, study brief status/path, current next action, and recommended command.
- Safety boundary: v0.30 projects resume JSON is machine-readable read-only collection state for wrappers. It is not a scanner, generator, report refresh, repair runner, LLM call, score, tutor, planner, approval, readiness gate, or child-project mutation.

Verification evidence:
  - `python -m unittest tests.test_project_index` failed during RED because `projects resume --json` was not registered.
  - `python -m unittest tests.test_project_index tests.test_resume tests.test_study_brief` passed with 24 tests OK after implementation.
  - `python -m unittest tests.test_project_index tests.test_resume tests.test_study_brief tests.test_dashboard tests.test_status_quality_summary tests.test_learning_queue` passed with 75 tests OK.
  - `python -m unittest discover -s tests` passed with 420 tests OK and 1 skipped.
  - `python -m compileall socrates` passed.
  - `git diff --check` passed.
  - `powershell -ExecutionPolicy Bypass -File scripts\check.ps1` passed with 420 tests OK and 1 skipped.
  - `bash scripts/check.sh` passed with 420 tests OK and 1 skipped; WSL emitted localhost text and a `scripts/check.ps1` line-ending warning, but the script exit code was 0.

## v0.31 Multi-project resume summary alpha

- Added aggregate readiness counts to `socrates.project_resume.build_project_resume_index_payload(root_path)`.
- `python -m socrates projects resume --root <root>` now includes `Ready` and `Refresh brief` rows in the snapshot.
- `python -m socrates projects resume --root <root> --json` now includes `ready_count` and `refresh_brief_count`.
- Counts are derived from existing per-project `resume_state` rows, so project entries and read-only behavior stay unchanged.
- Safety boundary: v0.31 resume counts are collection scan aids. They are not scores, predictions, readiness gates, scanners, report generators, LLM calls, or child-project mutations.

Verification evidence:
  - `python -m unittest tests.test_project_index` failed during RED because Markdown summary rows and JSON count fields were absent.
  - `python -m unittest tests.test_project_index tests.test_resume tests.test_study_brief` passed with 24 tests OK after implementation.
  - `python -m unittest tests.test_project_index tests.test_resume tests.test_study_brief tests.test_dashboard tests.test_status_quality_summary tests.test_learning_queue` passed with 75 tests OK.
  - `python -m unittest discover -s tests` passed with 420 tests OK and 1 skipped.
  - `python -m compileall socrates` passed.
  - `git diff --check` passed.
  - `powershell -ExecutionPolicy Bypass -File scripts\check.ps1` passed with 420 tests OK and 1 skipped.
  - `bash scripts/check.sh` passed with 420 tests OK and 1 skipped; WSL emitted localhost text and a `scripts/check.ps1` line-ending warning, but the script exit code was 0.

## v0.32 Multi-project resume state filter alpha

- Added `--state {all,ready,refresh_brief}` to `python -m socrates projects resume`.
- `socrates.project_resume.build_project_resume_index_payload(root_path, state_filter=...)` now records `state_filter` and filters project rows before summary counts are computed.
- Markdown output renders the active state filter in the snapshot.
- JSON output includes `state_filter`, filtered project rows, and counts derived from those returned rows.
- Safety boundary: v0.32 resume state filters are read-only collection navigation aids. They are not scores, predictions, readiness gates, scanners, report generators, LLM calls, or child-project mutations.

Verification evidence:
  - `python -m unittest tests.test_project_index` failed during RED because `projects resume --state` was not registered.
  - `python -m unittest tests.test_project_index tests.test_resume tests.test_study_brief` passed with 26 tests OK after implementation.
  - `python -m unittest tests.test_project_index tests.test_resume tests.test_study_brief tests.test_dashboard tests.test_status_quality_summary tests.test_learning_queue` passed with 77 tests OK.
  - `python -m unittest discover -s tests` passed with 422 tests OK and 1 skipped.
  - `python -m compileall socrates` passed.
  - `git diff --check` passed.
  - `powershell -ExecutionPolicy Bypass -File scripts\check.ps1` passed with 422 tests OK and 1 skipped.
  - `bash scripts/check.sh` passed with 422 tests OK and 1 skipped; WSL emitted localhost text and a `scripts/check.ps1` line-ending warning, but the script exit code was 0.

## v0.33 Multi-project resume command summary alpha

- Added `recommended_command_count` and `recommended_commands` to `socrates.project_resume.build_project_resume_index_payload(root_path, state_filter=...)`.
- Recommended-command rows are derived after state filtering, so `--state ready` reports zero commands and `--state refresh_brief` reports only commands for returned refresh-needed projects.
- Markdown `projects resume` output now renders `Recommended commands` in the snapshot plus a `## Recommended Commands` section.
- JSON output includes structured command rows with `project_id`, `project_title`, `resume_state`, and `command`.
- Safety boundary: v0.33 command summaries are read-only collection navigation aids. They do not execute commands, batch automation, generate briefs, refresh reports, scan child state beyond existing resume rows, call an LLM, score learning, or mutate child projects.

Verification evidence:
  - `python -m unittest tests.test_project_index` failed during RED because command-summary payload fields and Markdown rows did not exist.
  - `python -m unittest tests.test_project_index tests.test_resume tests.test_study_brief` passed with 28 tests OK after implementation.
  - `python -m unittest tests.test_project_index tests.test_resume tests.test_study_brief tests.test_dashboard tests.test_status_quality_summary tests.test_learning_queue` passed with 79 tests OK.
  - `python -m unittest discover -s tests` passed with 424 tests OK and 1 skipped.
  - `python -m compileall socrates` passed.
  - `git diff --check` passed.
  - `powershell -ExecutionPolicy Bypass -File scripts\check.ps1` passed with 424 tests OK and 1 skipped.
  - `bash scripts/check.sh` passed with 424 tests OK and 1 skipped; WSL emitted localhost text and a `scripts/check.ps1` line-ending warning, but the script exit code was 0.

## v0.34 Multi-project resume commands output alpha

- Added `socrates.project_resume.format_project_resume_commands(root_path, state_filter=...)` to render only derived recommended child-project command lines.
- Added `--commands` to `python -m socrates projects resume`; it is mutually exclusive with `--json`.
- `projects resume --state refresh_brief --commands` prints only command lines for returned refresh-needed projects.
- `projects resume --state ready --commands` exits 0 with empty stdout when no returned project has a recommended command.
- Safety boundary: v0.34 commands-only output is a read-only copy/output mode. It does not execute commands, batch automation, generate briefs, refresh reports, scan child state beyond existing resume rows, call an LLM, score learning, or mutate child projects.

Verification evidence:
  - `python -m unittest tests.test_project_index` failed during RED because `--commands` was not registered.
  - `python -m unittest tests.test_project_index tests.test_resume tests.test_study_brief` passed with 31 tests OK after implementation.
  - `python -m unittest tests.test_project_index tests.test_resume tests.test_study_brief tests.test_dashboard tests.test_status_quality_summary tests.test_learning_queue` passed with 82 tests OK.
  - `python -m unittest discover -s tests` passed with 427 tests OK and 1 skipped.
  - `python -m compileall socrates` passed.
  - `git diff --check` passed.
  - `powershell -ExecutionPolicy Bypass -File scripts\check.ps1` passed with 427 tests OK and 1 skipped.
  - `bash scripts/check.sh` passed with 427 tests OK and 1 skipped; WSL emitted localhost text and a `scripts/check.ps1` line-ending warning, but the script exit code was 0.

## v0.35 Multi-project brief refresh alpha

- Added `socrates/project_brief_refresh.py` with `refresh_project_briefs_payload(root_path)` and `format_project_brief_refresh(root_path)`.
- Added `python -m socrates projects refresh-briefs --root <root>` as the first explicit collection writer over the resume workflow.
- The command uses existing per-project resume state to select only `refresh_brief` child projects, then calls the existing `generate_study_brief` writer for those selected children.
- Ready projects are skipped and do not receive an extra `Generated study brief.` project-log entry.
- Safety boundary: v0.35 refresh-briefs may write study brief artifacts and project-log entries only for selected `refresh_brief` child projects. It does not write the root index, refresh ready projects, refresh reports, run repairs, call an LLM, approve artifacts, score learning, tutor, predict, or mutate learning-state truth.

Verification evidence:
  - `python -m unittest tests.test_project_index` failed during RED because `projects refresh-briefs` was not registered.
  - `python -m unittest tests.test_project_index tests.test_resume tests.test_study_brief` passed with 33 tests OK after implementation.
  - `python -m unittest tests.test_project_index tests.test_resume tests.test_study_brief tests.test_dashboard tests.test_status_quality_summary tests.test_learning_queue` passed with 84 tests OK.
  - `python -m unittest discover -s tests` passed with 429 tests OK and 1 skipped.
  - `python -m compileall socrates` passed.
  - `git diff --check` passed.
  - `powershell -ExecutionPolicy Bypass -File scripts\check.ps1` passed with 429 tests OK and 1 skipped.
  - `bash scripts/check.sh` passed with 429 tests OK and 1 skipped; WSL emitted localhost text and a `scripts/check.ps1` line-ending warning, but the script exit code was 0.

## v0.36 Multi-project brief refresh JSON alpha

- Added `--json` to `python -m socrates projects refresh-briefs`.
- JSON output reuses `refresh_project_briefs_payload(root_path)`, so Markdown and JSON writer outputs share the same selection and side-effect semantics.
- The payload records `schema_version: 1`, `quality_boundary: deterministic_project_brief_refresh`, root, refreshed/skipped counts, refreshed rows, and skipped rows.
- Safety boundary: v0.36 JSON changes output format only. It is not a dry-run, read-only command, new selection policy, scanner, report refresh, repair runner, LLM call, score, tutor, approval, readiness gate, or learning-state truth mutation.

Verification evidence:
  - `python -m unittest tests.test_project_index` failed during RED because `projects refresh-briefs --json` was not registered.
  - `python -m unittest tests.test_project_index tests.test_resume tests.test_study_brief` passed with 34 tests OK after implementation.
  - `python -m unittest tests.test_project_index tests.test_resume tests.test_study_brief tests.test_dashboard tests.test_status_quality_summary tests.test_learning_queue` passed with 85 tests OK.
  - `python -m unittest discover -s tests` passed with 430 tests OK and 1 skipped.
  - `python -m compileall socrates` passed.
  - `git diff --check` passed.
  - `powershell -ExecutionPolicy Bypass -File scripts\check.ps1` passed with 430 tests OK and 1 skipped.
  - `bash scripts/check.sh` passed with 430 tests OK and 1 skipped; WSL emitted localhost text and a `scripts/check.ps1` line-ending warning, but the script exit code was 0.

## v0.37 Multi-project brief refresh dry-run alpha

- Added `--dry-run` to `python -m socrates projects refresh-briefs`.
- Markdown and JSON dry-run output reuse `refresh_project_briefs_payload(root_path, dry_run=True)`, so preview mode shares writer selection without calling `generate_study_brief`.
- The refresh payload now records `mode`, `dry_run`, `selected_count`, and `selected` rows while preserving `refreshed_count`, `skipped_count`, `refreshed`, and `skipped`.
- Dry-run output reports selected `refresh_brief` child projects and skipped ready projects, with `refreshed_count: 0` and empty `refreshed` rows.
- Safety boundary: v0.37 dry-run changes write behavior only. It is not a read-only resume command, new selector, scanner, report refresh, repair runner, LLM call, score, tutor, approval, readiness gate, or learning-state truth mutation.

Verification evidence:
  - `python -m unittest tests.test_project_index` failed during RED because `projects refresh-briefs --dry-run` was not registered.
  - `python -m unittest tests.test_project_index tests.test_resume tests.test_study_brief` passed with 36 tests OK after implementation.
  - `python -m unittest tests.test_project_index tests.test_resume tests.test_study_brief tests.test_dashboard tests.test_status_quality_summary tests.test_learning_queue` passed with 87 tests OK.
  - `python -m unittest discover -s tests` passed with 432 tests OK and 1 skipped.
  - `python -m compileall socrates` passed.
  - `git diff --check` passed.
  - `powershell -ExecutionPolicy Bypass -File scripts\check.ps1` passed with 432 tests OK and 1 skipped.
  - `bash scripts/check.sh` passed with 432 tests OK and 1 skipped; WSL emitted localhost text and a `scripts/check.ps1` line-ending warning, but the script exit code was 0.

## v0.38 Multi-project brief refresh limit alpha

- Added `--limit N` to `python -m socrates projects refresh-briefs`.
- Limited writer output reuses `refresh_project_briefs_payload(root_path, limit=N)`, so batch-size control shares the same deterministic project ordering and resume-state selection as no-limit mode.
- The refresh payload now records `limit`, `deferred_count`, and `deferred` rows while preserving selected/refreshed/skipped rows.
- Over-limit `refresh_brief` child projects are reported as deferred with `reason: limit_reached`; ready child projects remain skipped with `reason: resume_state_ready`.
- Safety boundary: v0.38 limit changes batch size only. It is not a new selector, queue, scanner, report refresh, repair runner, LLM call, score, tutor, approval, readiness gate, or learning-state truth mutation.

Verification evidence:
  - `python -m unittest tests.test_project_index` failed during RED because `projects refresh-briefs --limit` was not registered.
  - `python -m unittest tests.test_project_index tests.test_resume tests.test_study_brief` passed with 39 tests OK after implementation.
  - `python -m unittest tests.test_project_index tests.test_resume tests.test_study_brief tests.test_dashboard tests.test_status_quality_summary tests.test_learning_queue` passed with 90 tests OK.
  - `python -m unittest discover -s tests` passed with 435 tests OK and 1 skipped.
  - `python -m compileall socrates` passed.
  - `git diff --check` passed.
  - `powershell -ExecutionPolicy Bypass -File scripts\check.ps1` passed with 435 tests OK and 1 skipped.
  - `bash scripts/check.sh` passed with 435 tests OK and 1 skipped; WSL emitted localhost text and a `scripts/check.ps1` line-ending warning, but the script exit code was 0.

## v0.39 Multi-project brief refresh project-id alpha

- Added repeatable `--project-id <id>` to `python -m socrates projects refresh-briefs`.
- Targeted writer output reuses `refresh_project_briefs_payload(root_path, project_ids=[...])`, so Markdown, JSON, dry-run, and limit modes share one selection contract.
- The refresh payload now records `project_ids`, `excluded_count`, and `excluded` rows while preserving selected/refreshed/deferred/skipped rows.
- Nonmatching child projects are reported as excluded with `reason: project_id_filter`; matching ready child projects remain skipped with `reason: resume_state_ready`.
- Unknown project ids fail before writes with exit code 2 and `unknown project id: <id>`.
- Safety boundary: v0.39 project-id filtering changes target selection only. It is not a new readiness rule, scanner, queue, report refresh, repair runner, LLM call, score, tutor, approval, hidden discovery mode, or learning-state truth mutation.

Verification evidence:
  - `python -m unittest tests.test_project_index` failed during RED because `projects refresh-briefs --project-id` was not registered.
  - `python -m unittest tests.test_project_index tests.test_resume tests.test_study_brief` passed with 41 tests OK after implementation.
  - `python -m unittest tests.test_project_index tests.test_resume tests.test_study_brief tests.test_dashboard tests.test_status_quality_summary tests.test_learning_queue` passed with 92 tests OK.
  - `python -m unittest discover -s tests` passed with 437 tests OK and 1 skipped.
  - `python -m compileall socrates` passed.
  - `git diff --check` passed.
  - `powershell -ExecutionPolicy Bypass -File scripts\check.ps1` passed with 437 tests OK and 1 skipped.
  - `bash scripts/check.sh` passed with 437 tests OK and 1 skipped; WSL emitted localhost text and a `scripts/check.ps1` line-ending warning, but the script exit code was 0.

## 当前未完成事项

### 集成状态

- 当前工作在 `codex/v02-closure`，尚未合并回集成分支或 `main`。
- 旧的 v0.1 多 worktree 仍存在，包括 core contracts、reference import、learning plan、tutoring session、notes/exercises、state/eval 与 integration worktree。
- 集成审计结论：
  - `feature/v0.2-reference-kb-obsidian` 与 `origin/feature/v0.2-reference-kb-obsidian` 同步，`0 ahead / 0 behind`。
  - `main` 是当前 v0.2 分支的祖先；当前 v0.2 分支相对 `main` 为 `312 ahead / 0 behind`。
  - `integration/v0.1` 也是当前 v0.2 分支的祖先；当前 v0.2 分支相对 `integration/v0.1` 为 `313 ahead / 0 behind`。
  - 本地 `main` 相对 `integration/v0.1` 为 `1 ahead / 0 behind`。
  - 当前远端没有可见的 `origin/main` ref。
- 推荐合并路径：先把 v0.2 feature 分支提升到 integration 线，再决定是否快进本地 `main`。不要绕过 integration gate 直接把 v0.2 当作最终主线发布。

### v0.2 收尾

- 对所有直接读取 generated artifact 的 CLI/readers 做一次覆盖审计，确保它们都不会绕过 readiness/status gate。
- 对 Obsidian 导出做一次端到端回归：draft -> review -> export -> manifest -> backlink -> lifecycle audit。
- 更新 README，使其不再描述为 Phase 0 skeleton，而是反映当前 CLI 原型能力。
- 梳理 docs 中 v0.2 已完成和未完成条目，减少路线图与实现状态之间的偏差。

### Generated artifact reader 审计

当前 v0.2 的高风险 generated reader 主要分为四类：

- Reference KB reader：`kb list/search/counterexamples/chapters/relationships` 通过 `read_reference_index`、`read_reference_chapter_index`、`read_reference_concept_graph` 等 fail-fast reader 读取生成物；测试覆盖 missing、invalid JSON、invalid schema 和 rebuild hint。
- Obsidian reader：`note list`、`note export-obsidian`、`status`、`lifecycle audit` 通过 note/export manifest 与文件扫描组合工作；已有 corrupt manifest fallback、stale export cleanup、pending export lifecycle tests。
- Quality/report reader：`status`、`queue`、`benchmark status`、`lifecycle audit` 对 quality manifests、reports、benchmark manifest 做 schema/mtime/cleanliness 检查，坏 manifest 不应被误报为通过。
- Tool-verification reader：`tool list/check`、`queue`、`lifecycle audit` 检查 tool-verification manifest 与 quality manifest schema、record 字段、source manifest fingerprint 和 stale KB 状态。

收口结论：Reference KB reader 的 readiness gate 最成熟；Obsidian、quality/report 与 tool-verification reader 已有 fail-fast 或 conservative-fail 行为，后续如新增 reader，应优先复用现有 reader/helper，而不是在 CLI handler 中直接 `json.loads` 生成物。

### 距离最终目标的差距

相对 `docs/final_development_goal.md` 的最终目标，当前系统已经具备核心 CLI 骨架和学习闭环，但还不是稳定长期使用产品。

需要明确的是：当前实现仍是确定性 CLI 原型。v0.4 已提高题目验证和题库索引可靠性，v0.5 已增加教学 session score，v0.6 已增加外部 Markdown 转换交接，v0.7 已增加下一节课确定性交接计划，v0.8 已增加 review-only LLM session judge draft，v0.9 已增加 deterministic session closeout workflow，v0.10 已把 closeout 纳入 status 与 lifecycle readiness，v0.11 已增加 deterministic multi-session regression，v0.12 已增加 workflow action queue visibility，v0.13 已增加 priority action queue navigation，v0.14 已增加 report priority action snapshots，v0.15 已增加 recommended focus report summaries，v0.16 已增加 action summary queue/report summaries，v0.17 已增加 repair path queue/report summaries，v0.18 已增加 current-state risk summary report snapshots，v0.19 已增加 bounded risk trend report snapshots，v0.20 已增加 report-history audit visibility，v0.21 已增加 long-term multi-session regression refresh，v0.22 已增加 read-only study dashboard，v0.23 已增加 generated study-start brief，v0.24 已增加 study brief next-action freshness visibility，v0.25 已增加 manifest-backed study brief freshness，v0.26 已增加 read-only brief status command，v0.27 已增加 read-only project resume command，v0.28 已增加 read-only resume JSON，v0.29 已增加 read-only multi-project resume index，v0.30 已增加 read-only multi-project resume JSON，v0.31 已增加 collection resume readiness counts，v0.32 已增加 collection resume state filtering，v0.33 已增加 collection resume recommended-command summaries，v0.34 已增加 collection resume commands-only output，v0.35 已增加 collection refresh-briefs writer，v0.36 已增加 refresh-briefs JSON output，v0.37 已增加 refresh-briefs dry-run preview，v0.38 已增加 refresh-briefs limit control，v0.39 已增加 refresh-briefs project-id targeting，但这些能力不等同于数学正确性证明、trusted LLM judge、内置 OCR/PDF backend、prediction/scoring 或自动教学执行。全自动 LLM tutoring、UI/插件层和真实长期使用体验仍属于后续工作。

粗略估计：

- v0.1：基本完成。
- v0.2：大部分完成，剩余重点是集成清理、文档同步、端到端稳定性。
- v0.3-v0.5：已有实现基础，但仍需扩展为可靠的长期学习状态、复习调度、题目质量与教学质量评测闭环。
- v1.0：仍缺少完整产品体验、多 session 长期学习稳定性、可靠自动组题、阶段性学习报告打磨、UI/插件层和更多真实使用场景回归。

按能力完成度估算，当前约完成最终目标的 60%-70%。剩余 30%-40% 的主要风险不在单个函数，而在长期工作流的稳定性、集成一致性、用户体验和真实数学学习质量。

## 下一步建议

1. 完成并保持 v0.2 收口门禁：README/docs 同步、Group Theory 端到端回归、reader gate 审计、`check.ps1`/`check.sh` 通过。
2. 将 `feature/v0.2-reference-kb-obsidian` 作为 v0.2 集成候选，优先合并到 integration 分支，再决定是否提升到 `main`。
3. 合并前保留 v0.1 worktree 分支作为历史审计对象，不再从这些旧分支继续开发新功能。
4. v0.3 再处理错因、学习状态、复习调度产品化清理，以及 LLM/OCR/provider 抽象设计。

## 注意事项

- 本轮没有启动 OMX team mode；如果后续使用 team mode，子 agent 应按 Leo 的要求分配 `gpt-5.5-xhigh`。
- 本轮按用户要求持续同步 `D:\llmwiki`；没有修改 Codex/OMX 配置、Skill Governance、AGENTS 或 routing 文件。

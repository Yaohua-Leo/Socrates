# v0.60 Real-Use Validation Runbook

**Purpose:** Pause feature development and validate the current v0.59-alpha
Socrates prototype against one real learner workflow before choosing the v0.61
build lane.

**Decision:** Use the v0.59 `real_long_term_validation` lane. This run is not
an OCR/PDF backend build, not autonomous LLM tutoring, not a UI/plugin sprint,
and not a claim that Socrates is product-complete.

**Owner:** Leo runs this as the learner/operator. The next development step
waits for Leo's feedback.

**Expected duration:** 45-90 minutes for one small source and one scripted
session.

---

## Validation Boundary

- Use one real math topic that Leo actually wants to study.
- Prefer one small Markdown or TXT source. PDF is allowed only after external
  conversion to Markdown because Socrates still has no bundled OCR/PDF backend.
- Run against a disposable validation project, not an important existing
  learning project.
- Record exact command output when a command fails or feels confusing.
- Do not treat passing deterministic gates as mathematical correctness proof.
- Stop after one validation cycle and return feedback before v0.61 planning.

## What This Run Should Prove

- A real source can move through import, curation, KB build, plan, and one
  deterministic tutoring session without hidden development-only assumptions.
- The current status, dashboard, queue, brief, and resume surfaces agree about
  the next action.
- The manual parts are visible: source preparation, `source-id` discovery,
  script writing, note review, exercise review, and interpreting failures.
- The next major build lane can be chosen from observed friction rather than
  from feature preference alone.

## Setup

Run from `D:\Socrates`:

```powershell
git status --short --branch
python -m socrates product readiness
```

Choose a validation root outside the repo:

```powershell
$root = "D:\SocratesValidation"
$project = "$root\group_theory"
$source = "$root\normal_subgroups.md"
$script = "$root\session_0001.script"
$script2 = "$root\session_0002.script"
$answer = "$root\normal_subgroup_01_answer.md"
$feedback = "$root\normal_subgroup_01_feedback.md"
New-Item -ItemType Directory -Force $root
```

If you use your own real source, keep the variables but point `$source` at that
file. If you want a tiny smoke source before using real notes, create this file:

```powershell
@"
# Normal Subgroups

## Definition: Normal Subgroup
A subgroup N of G is normal if gNg^-1 = N for every g in G.

## Kernel Example
The kernel of a group homomorphism is normal because conjugation stays in the
kernel under the homomorphism.

Depends: subgroup, conjugation, group_homomorphism
"@ | Set-Content -Encoding UTF8 $source
```

## Pass 1: Core Learning Flow

Create the project:

```powershell
python -m socrates init --topic "Group Theory" --path $project --goal "Understand normal subgroups well enough to use quotient groups."
```

Import the source:

```powershell
python -m socrates import --project $project $source --role lecture_notes --title "Normal Subgroup Notes"
python -m socrates sources list --project $project
```

Copy the emitted `source_id`. For the sample title above it should be
`normal_subgroup_notes`; if your title differs, replace `<source_id>` below.

```powershell
python -m socrates curate --project $project --source-id <source_id>
python -m socrates kb build --project $project
python -m socrates kb search --project $project --query "conjugation"
python -m socrates kb chapters --project $project
python -m socrates plan --project $project
```

Create a deterministic tutoring script. Use real learner answers, including
one uncertainty or misconception if possible:

```powershell
@"
topic: Normal Subgroup
goal: Distinguish normality from commutativity and prepare for kernels.
question: What must you check to prove that a subgroup is normal?
hint: Use conjugation rather than elementwise commutativity.
hint: Compare gNg^-1 = N with gn = ng.
attempt: I think normal means every element commutes with every other element.
misconception: normal_equals_central
next: Prove that the kernel of a homomorphism is a normal subgroup.
"@ | Set-Content -Encoding UTF8 $script
```

Run the session and inspect the first re-entry surfaces:

```powershell
python -m socrates teach --project $project --session-id session_0001 --script $script
python -m socrates status --project $project
python -m socrates status --project $project --json
python -m socrates dashboard --project $project
python -m socrates dashboard --project $project --json
python -m socrates queue --project $project --section priority
python -m socrates queue --project $project --json
python -m socrates brief generate --project $project
python -m socrates brief status --project $project
python -m socrates brief status --project $project --json
python -m socrates resume --project $project
python -m socrates resume --project $project --json
```

## Pass 2: Review And Closeout Flow

This pass is optional if Pass 1 already hit a blocker. If Pass 1 worked, run it
to expose the manual review and lifecycle friction.

List and review the note:

```powershell
python -m socrates note list --project $project
python -m socrates note review --project $project --note normal_subgroup
python -m socrates note export-obsidian --project $project
```

List, validate, approve, attempt, and grade one exercise:

```powershell
python -m socrates exercise list --project $project --status all
python -m socrates exercise validate --project $project --all
python -m socrates exercise approve --project $project --exercise normal_subgroup_01
@"
I would prove kernel normality by taking k in ker(phi) and computing
phi(gkg^-1) = phi(g)phi(k)phi(g)^-1 = phi(g)ephi(g)^-1 = e.
"@ | Set-Content -Encoding UTF8 $answer
@"
Good use of conjugation and the homomorphism property. Check subgroup closure
separately when writing the full proof.
"@ | Set-Content -Encoding UTF8 $feedback
python -m socrates exercise attempt --project $project --exercise normal_subgroup_01 --answer $answer
python -m socrates exercise grade --project $project --attempt normal_subgroup_01_attempt_001 --score 0.8 --feedback $feedback --misconception normal_equals_central --analysis "Still needs contrast between normality and centrality." --repair-suggestion "Write one counterexample where normal does not imply central."
python -m socrates exercise bank build --project $project
python -m socrates exercise bank status --project $project
```

Run review and closeout surfaces:

```powershell
python -m socrates review schedule --project $project --as-of 2026-06-05 --json
python -m socrates review due --project $project --as-of 2026-06-05 --json
python -m socrates review mastery --project $project --json
python -m socrates review misconceptions --project $project --json
python -m socrates session score --project $project --session-id session_0001
python -m socrates session plan-next --project $project --session-id session_0002
@"
topic: Kernel Normality
goal: Apply normal subgroup criteria to kernels.
question: Why is the kernel of a homomorphism normal?
hint: Compute phi(gkg^-1).
hint: Use that phi(k) is the identity.
attempt: phi(gkg^-1)=phi(g)phi(k)phi(g)^-1=e, so gkg^-1 is in the kernel.
next: Compare quotient groups with cosets.
"@ | Set-Content -Encoding UTF8 $script2
python -m socrates teach --project $project --session-id session_0002 --script $script2
python -m socrates session closeout --project $project --session-id session_0001 --next-session-id session_0002
python -m socrates lifecycle regression --project $project
python -m socrates benchmark run --project $project --session-id session_0001
python -m socrates report weekly --project $project
python -m socrates report monthly --project $project
python -m socrates report project-summary --project $project
python -m socrates lifecycle audit --project $project
```

Finish by rechecking the user-facing surfaces:

```powershell
python -m socrates status --project $project
python -m socrates dashboard --project $project
python -m socrates queue --project $project --section priority
python -m socrates brief generate --project $project
python -m socrates resume --project $project
```

## If Something Fails

Stop that branch of the run and keep the first failure. Record:

- Exact command.
- Exit code if visible.
- Full stdout/stderr.
- What you expected.
- What happened instead.
- Whether the project directory now looks partially mutated.
- Whether the next recovery command was obvious from `status`, `dashboard`,
  `queue`, or `resume`.

Do not retry more than twice unless the failure is a typo. Repeated friction is
useful validation data.

## Artifact Checklist

Keep these artifacts until the next development session:

- `$project` directory.
- `$source` and any externally converted Markdown source.
- `$script`.
- `03_sessions/session_0001/transcript.md`.
- `03_sessions/session_0001/summary.md`.
- `03_sessions/session_0001/detected_misconceptions.md`.
- `04_atomic_notes/` draft/reviewed/export artifacts.
- `05_exercises/` generated, attempted, graded, and bank artifacts.
- `07_exports/briefs/study_brief.md`.
- `07_exports/reports/` weekly, monthly, and project-summary reports.
- `08_evals/` score, validation, closeout, regression, benchmark, and lifecycle
  artifacts.
- Captured `status --json`, `dashboard --json`, `queue --json`,
  `brief status --json`, and `resume --json` output.
- Any screenshots or copied terminal output for confusing moments.

## Feedback Template

Return feedback in this shape:

```markdown
## v0.60 real-use feedback

### Topic and source
- Topic:
- Source type: Markdown / TXT / externally converted PDF / other
- Source size:
- Project path:

### Commands completed
- Last completed command:
- First failed command, if any:

### Friction
- Most manual/awkward step:
- Least clear command or argument:
- Did `sources list` make the source id obvious?
- Did the deterministic script format feel natural enough for validation?
- Did `status`, `dashboard`, `queue`, `brief`, and `resume` agree?

### Output value
- Useful outputs:
- Useless or noisy outputs:
- Missing explanation or recovery hint:
- Any artifact that was hard to find:

### Learning quality
- Did the session transcript reflect the actual learning issue?
- Did misconceptions/mistake-bank entries help?
- Did generated exercises look usable?
- Did the next-session plan make sense?

### Desired next lane
- OCR/PDF backend:
- UI/plugin surface:
- Autonomous LLM tutoring:
- Real-use validation round 2:
- Other:

### Top 3 changes before v0.61
1.
2.
3.
```

## Pause Contract

After this runbook lands, development pauses. The next Socrates development
step should not implement OCR/PDF, autonomous tutoring, UI/plugin work, or new
workflow features until Leo returns feedback from this validation run or
explicitly changes the pause.

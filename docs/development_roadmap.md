# 各阶段开发计划

## 总体路线

苏格拉底项目采用渐进式开发路线。

开发重点不是一开始构建完整系统，而是先跑通最小学习闭环：

资料导入
  ↓
学习计划
  ↓
引导式教学
  ↓
原子笔记
  ↓
自动练习
  ↓
错因记录
  ↓
学习状态更新

每一阶段都应有明确的可交付成果和可评测标准。

Phase 0：项目骨架与基本规范
目标

建立苏格拉底项目的基础工程结构、配置规范和数据存储规范。

这一阶段不追求智能化，只追求项目能够稳定初始化、落盘和管理状态。

核心任务
1. 设计项目目录结构

实现命令：

Bash
socrates init --topic "Group Theory" --path "./group_theory"

生成目录：

group_theory/
  project.yaml
  README.md

  00_meta/
    goals.md
    user_profile.md
    project_log.md
    decisions.md
    progress.json
    learning_state.json

  01_references/
    source_registry.yaml
    raw/
    converted/
    curated/
    citations.bib

  02_learning_plan/
    long_term_plan.md
    short_term_plan.md
    chapter_sequence.yaml
    checkpoints.yaml

  03_sessions/

  04_atomic_notes/
    drafts/
    definitions/
    theorems/
    examples/
    counterexamples/
    techniques/
    exercises/

  05_exercises/
    generated/
    attempted/
    solutions/
    graded/
    mistake_bank.md

  06_kb/
    concept_graph.json
    dependency_graph.json
    embeddings/
    chunks/
    retrieval_index/

  07_exports/
    obsidian/
    latex_notes/
    pdf/

  08_evals/
    ingestion_eval.md
    tutoring_eval.md
    exercise_eval.md
    note_quality_eval.md
2. 设计 project.yaml

示例：

YAML
project:
  id: group_theory
  title: Group Theory
  created_at: 2026-06-03
  status: active

user_goal:
  description: 系统学习群论，为后续学习表示论和同调代数做准备
  target_level: advanced_undergraduate
  preferred_style: proof_oriented
  output_format:
    - obsidian_notes
    - exercises
    - summaries

references:
  main_reference: null
  source_registry: 01_references/source_registry.yaml

learning:
  current_phase: initialization
  current_topic: null
  current_session: null

policies:
  answer_policy: socratic
  note_policy: draft_first
  verification_policy: conservative
3. 设计统一日志格式

每个项目需要维护：

00_meta/project_log.md

记录：

项目创建时间

导入了哪些资料

用户做过哪些决策

生成了哪些学习计划

进行了哪些教学 session

生成了哪些笔记与练习

可交付成果

socrates init 命令可用

可以生成标准项目目录

可以生成 project.yaml

可以生成空的 learning state

可以记录项目日志

验收标准

用户输入 topic 和 path 后，可以创建一个完整学习项目

所有路径、配置和状态文件结构稳定

后续模块可以依赖该结构读写文件

Phase 1：Reference 导入与资料注册
目标

支持用户把本地资料导入学习项目，并建立统一的 reference registry。

此阶段先不追求复杂网络搜索，优先支持本地资料导入。

核心任务
1. 支持本地文件导入

支持格式：

PDF

Markdown

LaTeX

TXT

EPUB，可后置

DOCX，可后置

命令示例：

Bash
socrates import ./dummit_foote.pdf --role main_textbook
2. 维护 source_registry.yaml

示例：

YAML
sources:
  - id: dummit_foote
    type: book
    title: Abstract Algebra
    author:
      - David S. Dummit
      - Richard M. Foote
    role: main_textbook
    priority: 1
    status: raw_imported
    local_path: 01_references/raw/books/dummit_foote.pdf
    processed_paths:
      markdown: null
      curated: null
    notes: 用户指定为主教材
3. 支持资料角色标注

资料角色包括：

main_textbook
secondary_reference
lecture_notes
exercise_source
survey
paper
online_reference
advanced_reference
可交付成果

本地文件导入功能

source_registry.yaml 自动更新

reference 文件按类型存放

项目日志记录导入行为

验收标准

用户可以导入一本主教材

系统能记录该资料的路径、角色和状态

后续清洗模块可以根据 source id 找到原始文件

Phase 2：文献转换与清洗
目标

将导入的 reference 转换为可检索、可引用、可教学使用的 Markdown 或结构化数据。

该阶段核心原则是：

LLM 只能提出修正，不应直接覆盖原始转换结果。

核心任务
1. PDF / Markdown / LaTeX 转换

优先支持：

PDF text extraction
Markdown passthrough
LaTeX section extraction

后续接入：

MinerU
Mathpix
OCR
2. 建立 raw / converted / curated 三层结构
01_references/
  raw/
    books/
      dummit_foote.pdf

  converted/
    markdown/
      dummit_foote_ch01.ocr.md
      dummit_foote_ch02.ocr.md

  curated/
    dummit_foote_ch01.curated.md
    dummit_foote_ch02.curated.md
3. 生成清洗质量报告

输出：

08_evals/ingestion_eval.md

报告内容包括：

提取了多少章节

提取了多少公式

是否存在疑似 OCR 错误

是否存在断裂段落

是否存在公式残缺

是否存在定理编号异常

是否需要用户人工审核

4. LLM 校对采用 patch-only 模式

不要让 LLM 直接改写整个文档。

建议输出：

01_references/converted/patches/dummit_foote_ch01.patch.md

patch 内容格式：

Markdown
## Patch 001

### Location

Chapter 1, Section 1.2, paragraph 4

### Original

`Let G he a group...`

### Proposed Correction

`Let G be a group...`

### Reason

OCR likely misread "be" as "he".

### Risk Level

low
可交付成果

可以将一份 PDF 转为 Markdown

可以分章节保存转换结果

可以生成清洗质量报告

可以生成 LLM correction patch

可以生成 curated markdown 草稿

验收标准

系统不会覆盖原始资料

系统可以区分 raw、converted、curated

用户可以检查和接受修正

后续 RAG 模块只使用 curated 或明确标记为 safe 的资料

Phase 3：Reference KB 与结构化抽取
目标

从 curated reference 中抽取数学知识单元，构建 reference knowledge base。

核心任务
1. 抽取数学对象

抽取对象包括：

chapter
section
definition
theorem
proposition
lemma
corollary
example
counterexample
proof
exercise
remark
notation
2. 生成结构化 JSON

示例：

JSON
{
  "id": "normal_subgroup_def",
  "type": "definition",
  "title": "Normal Subgroup",
  "statement": "A subgroup N of G is normal if ...",
  "source": {
    "source_id": "dummit_foote",
    "chapter": "3",
    "section": "3.1",
    "page": 82
  },
  "dependencies": [
    "subgroup",
    "conjugation"
  ]
}
3. 构建初步概念图

输出：

06_kb/concept_graph.json
06_kb/dependency_graph.json

概念关系包括：

prerequisite
example_of
counterexample_to
used_in_proof_of
generalizes
special_case_of
equivalent_to
4. 建立检索索引

将 curated reference 切分为 chunk，并建立 retrieval index。

chunk metadata 应包含：

source id

chapter

section

object type

object id

page

title

dependency tags

可交付成果

definition / theorem / exercise 抽取器

reference chunk index

concept graph 初版

theorem index

exercise index

验收标准

可以检索某个概念的定义、定理、例子和习题

每条知识都有 provenance

教学模块可以调用 reference KB 获取上下文

Phase 4：学习计划设计模块
目标

根据用户目标、主参考资料和概念依赖图，生成长期与短期学习计划。

核心任务
1. 与用户交互确定目标

系统应询问或读取：

学习主题

学习目的

目标水平

每周投入时间

主参考书

是否偏证明

是否偏计算

是否需要生成 Obsidian 笔记

是否需要题库

是否有 deadline

2. 生成长期计划

输出：

02_learning_plan/long_term_plan.md

内容包括：

总目标

学习周期

主线参考书

阶段划分

每阶段主题

每阶段产出

检查点

3. 生成短期计划

输出：

02_learning_plan/short_term_plan.md

内容包括：

最近一周学习任务

当前章节

前置知识

本周目标

配套练习

复习任务

4. 生成 session plan

输出：

02_learning_plan/session_0001_plan.md

内容包括：

本次学习目标

需要回顾的前置知识

诊断问题

教学顺序

预计生成的笔记

预计生成的练习

可交付成果

long-term planner

weekly planner

session planner

plan negotiation prompt

checkpoint schema

验收标准

可以根据一本主教材生成章节学习路线

可以根据用户目标调整路线

可以生成下一次教学 session 的明确目标

计划文件可以落盘并被后续模块读取

Phase 5：引导式教学 MVP
目标

实现第一版苏格拉底式教学 session。

系统围绕一个小节或一个知识点进行教学，并将全过程落盘。

核心任务
1. 实现教学状态机

每次教学 session 包含：

start
  ↓
state objective
  ↓
recall prerequisites
  ↓
ask diagnostic question
  ↓
evaluate user response
  ↓
teach minimal concept
  ↓
ask guided question
  ↓
give hint if needed
  ↓
summarize
  ↓
generate notes
  ↓
generate exercises
  ↓
update memory
  ↓
end
2. 实现 hint ladder

提示等级：

YAML
hint_levels:
  0: ask_clarifying_question
  1: point_to_relevant_definition
  2: suggest_relevant_example
  3: suggest_relevant_lemma
  4: give_proof_skeleton
  5: fill_one_local_step
  6: give_full_solution

默认策略：

YAML
default:
  give_full_solution_immediately: false
  require_user_attempt_before_solution: true
  prefer_questions_over_exposition: true
3. 记录教学 session

每次 session 生成：

03_sessions/session_0001/
  transcript.md
  tutor_notes.md
  detected_misconceptions.md
  summary.md
  next_actions.md
4. 检测用户误区

初版误区类型：

missing_definition
notation_confusion
false_equivalence
invalid_generalization
proof_gap
circular_reasoning
example_confusion
quantifier_error
可交付成果

可运行 tutoring session

session transcript 自动落盘

可以给出分级提示

可以生成 session summary

可以记录用户错因

验收标准

系统不会一开始直接给完整答案

系统能够根据用户回答调整提示级别

每次教学后有明确 summary 和 next actions

用户错因可以写入 mistake bank

Phase 6：原子笔记生成与 Obsidian 导出
目标

将每次学习 session 中涉及的知识点转化为可复习、可链接、可审核的原子笔记。

核心任务
1. 设计笔记模板

笔记类型：

definition
theorem
example
counterexample
technique
proof_pattern
exercise
misconception
2. 生成 draft note

所有自动生成笔记先进入：

04_atomic_notes/drafts/

默认状态：

YAML
status: draft
reviewed_by_user: false
3. 笔记 frontmatter schema

示例：

YAML
---
type: definition
topic: group_theory
concept: normal_subgroup
status: draft
created_by: socrates
reviewed_by_user: false
source:
  - source_id: dummit_foote
    chapter: 3
    section: 1
tags:
  - algebra
  - group-theory
  - normal-subgroup
related:
  - subgroup
  - quotient_group
  - group_homomorphism
---
4. Obsidian 兼容

支持：

Markdown 文件

YAML frontmatter

双链 [[Normal Subgroup]]

tags

backlinks

文件夹分类

review status

可交付成果

笔记模板系统

自动生成 draft atomic notes

用户审核机制

Obsidian export 目录

backlinks 自动生成

验收标准

学完一个知识点后可以生成一份结构良好的原子笔记

笔记不会直接污染正式知识库

用户审核后可以导出到 Obsidian

笔记保留来源和相关概念链接

Phase 7：自动组题与答案生成
目标

根据当前学习内容、参考资料和用户错因，自动生成练习题、提示、解答和评分标准。

核心任务
1. 生成练习题

题目类型：

definition_check
example_construction
counterexample_construction
calculation
proof
debug_proof
concept_comparison
mixed_review
2. 生成题目结构

示例：

YAML
exercise:
  id: ex_normal_subgroup_001
  type: proof
  difficulty: 2
  concepts:
    - normal_subgroup
    - kernel
    - homomorphism
  prerequisites:
    - subgroup
    - group_homomorphism
  statement: >
    Let φ: G → H be a group homomorphism.
    Prove that ker φ is a normal subgroup of G.
  hints:
    - Recall the definition of the kernel.
    - To prove normality, compute φ(gkg^{-1}).
    - Use φ(k)=e_H.
  solution:
    outline:
      - Show ker φ is a subgroup of G.
      - Let g ∈ G and k ∈ ker φ.
      - Compute φ(gkg^{-1}).
      - Conclude gkg^{-1} ∈ ker φ.
  rubric:
    total: 10
    points:
      subgroup_check: 3
      conjugation_argument: 5
      conclusion: 2
  common_mistakes:
    - Forgetting to prove subgroup property.
    - Confusing normality with commutativity.
3. 练习来源

题目可以来自：

reference KB

主教材习题

教材习题变式

用户错因反向生成

用户薄弱概念

系统自生成

4. 题目验证

每道题进入正式题库前必须经过验证：

generate exercise
  ↓
generate solution
  ↓
check consistency
  ↓
try counterexample search
  ↓
assign difficulty
  ↓
save as draft
  ↓
optional user approval
可交付成果

exercise generator

solution generator

hint generator

rubric generator

exercise draft bank

exercise quality checker

验收标准

系统可以为一个知识点生成至少 5 道题

每道题包含 hint、solution 和 rubric

题目有 concept tags 和 difficulty

题目不会未经检查直接进入正式题库

Phase 8：学习状态与错因库
目标

建立用户长期学习状态模型，并根据用户表现动态调整后续教学、练习和复习。

核心任务
1. 维护 learning state

文件：

00_meta/learning_state.json

示例：

JSON
{
  "concept_mastery": {
    "subgroup": 0.85,
    "normal_subgroup": 0.64,
    "quotient_group": 0.41
  },
  "proof_skills": {
    "unfold_definition": 0.82,
    "construct_counterexample": 0.35,
    "use_universal_property": 0.48
  },
  "misconceptions": {
    "normal_equals_central": {
      "count": 3,
      "status": "active"
    }
  }
}
2. 维护 mistake bank

文件：

05_exercises/mistake_bank.md

记录：

错误发生在哪次 session

涉及哪个概念

用户原始回答

错因分析

修复建议

后续练习

是否复发

3. 动态调整学习计划

根据学习状态调整：

下一次 session 内容

复习题

题目难度

是否需要回退到前置概念

是否需要生成额外例子或反例

可交付成果

learning state updater

misconception detector

mistake bank writer

review scheduler 初版

plan adjustment logic

验收标准

用户做错题后，系统能记录错因

同一错因重复出现时，系统能识别复发

后续练习能针对薄弱点生成

学习计划可以根据用户状态调整

Phase 9：验证层与评测系统
目标

为系统输出增加质量控制，尤其是数学正确性、笔记质量、题目质量和教学质量。

核心任务
1. OCR / 清洗质量评测

评测对象：

公式是否残缺

定理编号是否正确

段落是否断裂

证明是否完整

章节层级是否正确

2. 原子笔记质量评测

检查项：

是否有明确定义

是否保留来源

是否有例子

是否有反例或非例

是否有相关链接

是否有常见误区

是否适合复习

是否存在数学错误

3. 练习质量评测

检查项：

题目是否成立

解答是否正确

难度是否合理

是否匹配目标概念

hint 是否逐级递进

rubric 是否可操作

是否有潜在反例

4. 教学质量评测

检查项：

是否过早给出完整答案

是否提出诊断问题

是否识别用户误区

是否给出最小必要提示

是否让用户参与推理

是否生成有效总结

是否更新学习状态

可交付成果

ingestion eval

note quality eval

exercise quality eval

tutoring quality eval

LLM judge rubric

eval reports

验收标准

每类核心输出都有质量报告

失败输出不会直接进入正式知识库

可以对不同版本 agent 的教学质量进行比较

系统具备最初的 benchmark 能力

当前实现状态（2026-06-04，v0.5-alpha）

- 已有 ingestion、note quality、exercise quality、exercise validation 和 tutoring quality 的确定性质量报告。
- 新增 `session score` 报告，将上述五个 gate 组合为单次教学 session 的 0-100 分报告和 manifest。
- `status`、project summary 和 lifecycle audit 已能读取 session score manifest，并对缺失、损坏或未通过的 score 保守失败。
- LLM judge rubric 仍未接入；当前 v0.5 是 deterministic checklist baseline，不是形式化教学质量证明。

Phase 10：高级数学工具集成
目标

增强系统在高等数学场景下的可靠性，尤其是代数、计算、证明结构和例子验证。

核心任务
1. 集成计算工具

优先考虑：

SageMath
GAP
SymPy

用途：

验证代数例子

检查群、环、模相关计算

构造反例

验证有限结构

生成计算型练习

2. 集成 Lean 辅助验证

初期目标不是全自动证明，而是：

生成 Lean statement skeleton

检查定理陈述是否类型合理

为部分基础命题提供形式化版本

建立 theorem dependency mapping

3. 数学工具调用记录

所有工具调用结果应落盘：

08_evals/tool_verification/

记录：

输入

工具

输出

是否通过

失败原因

对应题目或笔记

可交付成果

SageMath / GAP 工具接口

Lean statement generator

counterexample search helper

tool verification report

验收标准

系统可以用计算工具验证部分代数例子

自动组题模块可以调用工具检查简单命题

工具结果可追踪、可复现

Phase 11：用户体验与交互界面
目标

改善用户与系统交互方式，使项目长期使用更自然。

核心任务
1. CLI 交互

命令示例：

Bash
socrates init
socrates import
socrates plan
socrates teach
socrates note
socrates exercise
socrates review
socrates status
2. TUI / Web UI

后续可增加：

项目列表

当前学习进度

最近 session

待审核笔记

待完成练习

错因统计

概念图展示

Obsidian 导出按钮

3. Obsidian 插件

长期可以开发 Obsidian 插件，实现：

从 Obsidian 中发起学习 session

审核 Socrates 生成的笔记

查看概念图

做复习题

同步错因库

查看学习状态

可交付成果

CLI MVP

项目状态查看

待审核笔记列表

待完成练习列表

Obsidian export workflow

验收标准

用户可以通过 CLI 完成完整学习流程

用户可以方便地查看项目状态

用户可以审核笔记并导出到 Obsidian

Phase 12：完整闭环与产品化
目标

将苏格拉底从开发原型推进到可长期使用的本地数学学习系统。

核心任务
1. 打通完整闭环

完整流程：

init project
  ↓
import references
  ↓
clean references
  ↓
build reference KB
  ↓
generate learning plan
  ↓
run tutoring session
  ↓
generate atomic notes
  ↓
generate exercises
  ↓
grade user attempts
  ↓
update learning state
  ↓
schedule review
  ↓
export to Obsidian
2. 多项目管理

支持多个学习项目：

SocratesProjects/
  group_theory/
  homological_algebra/
  representation_theory/
  algebraic_geometry/

支持跨项目知识引用：

group_theory.normal_subgroup
  → representation_theory.group_representation
  → homological_algebra.derived_functor
3. 可复盘学习报告

定期生成：

weekly_report.md
monthly_report.md
project_summary.md

报告内容：

学了哪些概念

完成了哪些练习

生成了哪些笔记

出现了哪些错因

哪些知识点掌握较弱

下阶段建议学习什么

可交付成果

完整学习闭环

多项目管理

周报 / 月报

复习调度

Obsidian 集成

初步 benchmark suite

验收标准

一个数学主题可以从初始化持续学习到阶段性总结

所有重要产物都能落盘

系统可以根据用户表现调整后续学习

用户最终获得可复习的个人数学知识库

版本划分建议
v0.1：最小闭环原型

目标：

输入主题和资料
  ↓
初始化项目
  ↓
生成学习计划
  ↓
完成一次教学 session
  ↓
生成原子笔记
  ↓
生成练习

必须完成：

project init

local reference import

basic markdown extraction

learning plan generation

guided tutoring MVP

draft atomic note generation

basic exercise generation

session transcript

v0.2：Reference KB 与 Obsidian 笔记

目标：

资料可检索，笔记可沉淀

必须完成：

source registry

curated markdown

definition / theorem extraction

reference retrieval

Obsidian-compatible atomic notes

note review workflow

当前状态（2026-06-04）：

- v0.2 大部分已经在 `feature/v0.2-reference-kb-obsidian` 落地。
- Reference KB 已支持 curated Markdown 对象抽取、章节/定理/习题派生索引、concept/dependency graph、检索、counterexample/relationship 查询和 provenance 校验。
- Obsidian 笔记流已支持 draft -> review -> export -> manifest/backlink/lifecycle audit。
- 收尾重点不是新增智能能力，而是文档同步、端到端回归、generated artifact reader gate 审计和集成分支决策。
- PDF/OCR 后端、LLM tutor/provider、LLM judge 和自动数学内容生成仍不属于 v0.2 完成范围。

v0.3：错因与学习状态

目标：

系统开始记住用户哪里不会，并接入受控的智能建议层

必须完成：

learning_state.json

mistake bank

misconception detection

exercise targeting

review scheduling 初版

当前状态（2026-06-04）：

- 已完成 v0.3-alpha LLM provider 层：本地 `.env` 配置、redacted config 输出、stdlib-only DeepSeek adapter，默认模型为 `deepseek-v4-pro`。
- 已完成三类 reviewable LLM draft artifact：reference correction patch proposal、tutoring next-question draft、exercise feedback draft。
- 已完成 `08_evals/llm_suggestions_manifest.json` 与 `status` / lifecycle audit 可见性；损坏的 LLM manifest 会保守 fail，draft 存在本身不作为 readiness failure。
- 默认门禁保持离线确定性；live DeepSeek smoke 需要显式运行，不进入默认 check gate。
- OCR/PDF 后端、LLM judge、全自动 LLM tutoring、provider selection UI 仍后置到 v0.4+ / v0.5+。

v0.4：题库与验证

目标：

生成题目变得更可靠

必须完成：

exercise schema

solution schema

hint ladder

rubric

exercise quality checker

counterexample search 初版

当前状态（2026-06-04）：

- 已完成 v0.4-alpha exercise schema parser 与 validator；生成题目带 `schema_version: "v0.4"`，并保留原有 Markdown sections。
- 已完成 `exercise validate --all/--exercise`，会写入 `08_evals/exercise_validation/` 单题报告和 `08_evals/exercise_validation_manifest.json`。
- 已完成 `exercise bank build/status`，只把人工 approved 且 validation pass 的题目写入 `05_exercises/exercise_bank_manifest.json`。
- Exercise quality manifest、status、benchmark 与 lifecycle audit 已接入 v0.4 validation/bank 可见性；benchmark 现在是 5 个 gate。
- Counterexample search 与 validation 仍是 review evidence，不是形式化证明、自动审批或自动评分。

v0.5：教学质量评测

目标：

系统可以评测自己的教学行为

必须完成：

tutoring eval rubric

note quality eval

exercise quality eval

ingestion eval

session score report

v0.6：外部转换交接

目标：

在不引入内置 OCR/PDF 依赖的前提下，支持用户把外部工具生成的 Markdown 转换结果接入 Socrates。

必须完成：

attach external Markdown conversion

preserve raw source bytes

update source registry from conversion_pending to curated_draft

create review-gated curated reference

record conversion provenance

当前状态（2026-06-04）：

- `sources attach-conversion` 已支持为已导入 source 附加外部 Markdown 转换文件。
- PDF 可从 `conversion_pending` 进入 `curated_draft`，但 raw PDF 文件不会被修改。
- 转换产物记录 raw source path、external conversion source 和 `external_markdown_handoff` policy。
- 这不是内置 OCR/PDF backend；外部转换结果仍需 curated draft review 与 Reference KB provenance gate。

v0.7：下一节课交接计划

目标：

把长期学习状态、复习计划、上一次 session 产物、action queue 与 Reference KB context 汇总成下一节课的确定性 handoff plan。

必须完成：

next-session handoff plan

previous session summary / next_actions ingestion

due review selection

action queue snapshot

Reference KB context snapshot

handoff manifest

当前状态（2026-06-04）：

- `session plan-next` 已能生成 `02_learning_plan/<session_id>_plan.md`。
- `02_learning_plan/next_session_plan_manifest.json` 记录 session id、due review 数量、previous session、Reference KB 状态、action queue 计数与 deterministic handoff boundary。
- `status` 会显示 next session plan、due reviews 与 handoff 状态。
- Project summary report 会包含 Next Session Handoff Snapshot，并在 handoff manifest 变化后标记 stale。
- 这不是 autonomous tutoring、LLM judge、自动评分或 learning-state truth mutation；它只是下一节课前的确定性计划交接。

v0.8：LLM judge 边界

目标：

在不把 LLM 输出提升为可信评分、readiness gate 或 learning-state truth 的前提下，增加可人工审阅的 session judge draft。

必须完成：

review-only session judge draft

strict JSON response contract

LLM suggestion manifest record

no mutation of transcript / session score / learning_state

CLI surface for explicit opt-in use

当前状态（2026-06-04）：

- `session judge-suggest` 已支持调用已配置 LLM，为一个 tutoring session 写入 `03_sessions/<session_id>/llm_session_judge.md`。
- draft frontmatter 固定记录 `status: draft` 与 `quality_boundary: review_only_llm_judge_draft`。
- `08_evals/llm_suggestions_manifest.json` 会记录 `session_quality_judge` suggestion、source paths 与 prompt hash。
- v0.8 测试覆盖 transcript、learning_state 与 deterministic session score manifest 不被 LLM judge draft 修改。
- 这不是 trusted LLM judge、自动评分、readiness gate、数学证明、教学质量证明或 learning-state truth mutation。

v0.9：session closeout 工作流

目标：

把教学 session 结束后的常见步骤合并成一个确定性产品工作流：score 当前 session，生成下一节课 handoff plan，并刷新 project summary。

必须完成：

session closeout command

score current session

create next-session plan

refresh project summary

write closeout manifest

failed scores remain visible as needs_attention

当前状态（2026-06-04）：

- `session closeout` 已支持一次性运行 session score、next-session handoff plan 与 project summary refresh。
- `08_evals/session_closeout_manifest.json` 记录 `quality_boundary: deterministic_session_closeout`、当前 session、下一 session、score status、score value 与关键 artifact paths。
- closeout status 只有在 deterministic session score pass 时才是 `ready`；score fail 时命令仍写出 artifacts，但 manifest 标记 `needs_attention`。
- 这不是新的评分权威、LLM judge、自动通过 gate 或 learning-state truth mutation；它只是把既有确定性步骤组合成更稳定的 post-session workflow。

v0.10：closeout status / lifecycle 可见性

目标：

让 v0.9 的 session closeout manifest 进入 `status` 与 lifecycle audit，避免新的 workflow evidence 游离在产品 readiness 检查之外。

必须完成：

closeout manifest reader

status closeout snapshot

lifecycle closeout manifest check

corrupt/malformed closeout conservative failure

needs_attention remains lifecycle failure

当前状态（2026-06-04）：

- `status` 已显示 closeout 状态、当前/下一 session，以及 closeout 内记录的 deterministic session score。
- lifecycle audit 已增加 `Session closeout manifest` 检查。
- 只有 valid 且 `status: ready` 的 closeout manifest 才通过 lifecycle；missing、corrupt、malformed 或 `needs_attention` 均保守 fail。
- 这不是新的评分权威；它只是让 workflow evidence 进入可见性与 readiness gate。

v0.11：真实多 session 回归与产品闭环打磨

建议目标：

用一个真实小型数学主题跑通多 session 回归，优先修补长期使用时的 CLI 体验、artifact consistency 与报告可读性。除非显式扩展边界，否则继续保持 deterministic gates authoritative，LLM 只作为 review-only draft provider。

必须完成：

multi-session regression command

persist regression report / manifest

status multi-session regression snapshot

lifecycle multi-session regression check

missing/corrupt/malformed regression conservative failure

当前状态（2026-06-04）：

- `lifecycle regression` 已能写入 `08_evals/multi_session_regression.md` 与 `08_evals/multi_session_regression_manifest.json`。
- 回归检查 ready closeout、已完成 session artifacts、下一 session artifacts、next-session handoff manifest 和 project summary refresh。
- `status` 已显示 multi-session regression 的状态、通过检查数和 issue 摘要。
- lifecycle audit 已增加 `Multi-session regression` 检查，只接受 valid 且 `status: pass` 的 regression manifest。
- 这不是新的教学评分、LLM judge、数学证明、自动通过或 learning-state truth；它只是长期产品闭环的确定性 artifact 回归证据。

v0.12：workflow action queue 与长期使用体验打磨

建议目标：

在已经可见的多 session 回归基础上，继续打磨长期学习时的 CLI 导航、报告可读性、待办队列和阶段性复盘体验。除非显式扩展边界，否则继续优先修补真实使用路径中的 artifact consistency，而不是引入新的智能后端。

必须完成：

workflow queue section

status workflow action count

missing regression follow-up action

invalid regression rerun action

当前状态（2026-06-04）：

- `queue --section workflow` 已显示 deterministic workflow follow-up actions。
- 当 ready closeout 存在但 multi-session regression 尚未运行时，queue 提示运行 `socrates lifecycle regression --project <project>`。
- 当 multi-session regression manifest 损坏时，queue 提示重新运行 lifecycle regression。
- `status` 已显示 `Workflow actions: <count>`，让用户无需打开完整 queue 就能看到 workflow blocker 数量。
- 这不是新的 readiness gate，也不会修改项目状态；它只是把已有 deterministic gate 的下一步命令变得可见。

v0.13：长期报告与待办优先级打磨

建议目标：

继续把 workflow、quality、review、exercise 和 report 相关待办转成更明确的优先级/阶段化输出，减少长期项目中 status 信息过多但下一步不清楚的问题。

必须完成：

priority queue section

deterministic cross-section ordering

stable section-prefixed item ids

empty priority view behavior

当前状态（2026-06-04）：

- `queue --section priority` 已显示跨 section 的确定性优先级视图。
- priority view 按 workflow、quality checks、tool verifications、Obsidian exports、notes、misconceptions、reviews、exercise drafts、exercises、attempts 的顺序汇总既有 queue items。
- priority item id 使用 `<section>:<item>`，避免不同 section 的同名 artifact 在操作视图中混淆。
- 这不是新的 readiness gate、score、artifact writer 或 state mutation；它只是已有 queue 信息的 operator-facing 排序视图。

v0.14：阶段性学习报告与复盘体验打磨

建议目标：

在 priority queue 之后，继续打磨 weekly/monthly/project summary 的真实长期使用路径，让用户更容易从多 session artifact 中看到阶段性进展、薄弱点、复习建议和下一步学习重点。

必须完成：

priority action snapshots in weekly report

priority action snapshots in monthly report

priority action snapshots in project summary

report staleness tracks priority workflow/regression inputs

当前状态（2026-06-04）：

- weekly、monthly 与 project summary report 已包含 `## Priority Actions` snapshot。
- report priority rows 复用 `queue --section priority` 的 deterministic ordering 与 `<section>:<item>` item id。
- weekly/monthly/project-summary stale detection 已纳入 closeout、multi-session regression、artifact quality 与 tool-verification quality manifests，避免 report 中的 next-action snapshot 变旧却仍显示 generated。
- 这不是新的 readiness gate、report score、artifact writer 或 learning-state truth；它只是把已有 queue evidence 放进长期复盘报告。

v0.15：报告行动建议与阶段复盘结构打磨

建议目标：

继续把 priority actions、weak concepts、misconceptions、reviews 和 exercise progress 组合成更清晰的阶段复盘结构，让报告从 artifact inventory 进一步接近可执行学习建议。

必须完成：

recommended focus section in weekly report

recommended focus section in monthly report

recommended focus section in project summary

deterministic fallback rows when no evidence exists

当前状态（2026-06-04）：

- weekly、monthly 与 project summary report 已包含 `## Recommended Focus` section。
- Recommended Focus 汇总 first priority action、weakest concept、next scheduled review 与 first active misconception。
- 空项目或缺失 evidence 会输出 `none` / `none recorded` / `none scheduled` fallback，不会制造伪建议。
- 这不是 tutor、planner、session score、readiness gate 或 learning-state mutation；它只是把已有 deterministic evidence 压缩成报告中的下一步摘要。

v0.16：报告与行动队列的完成度/阻塞摘要

建议目标：

继续把 priority/focus/report evidence 压缩成更清晰的 completion/blocker summary，帮助长期项目区分“下一步操作”“阻塞项”“可继续学习项”和“需要人工审核项”。

必须完成：

action summary section in queue all view

selectable queue summary section

action summary section in weekly/monthly/project summary reports

deterministic fallback rows when no open actions exist

当前状态（2026-06-04）：

- `queue --section summary` 已显示 `## Action Summary`，并且默认 queue all view 会先显示该摘要。
- weekly、monthly 与 project summary report 已包含 `## Action Summary` section。
- Action Summary 统计 open actions、blockers、can continue learning、needs human review，并复用 priority queue 的 first next action。
- 这不是新的 readiness gate、score、planner、tutor 或 learning-state mutation；它只是把已有 queue buckets 压缩成可读的完成度/阻塞摘要。

v0.17：报告阻塞项的修复路径与阶段趋势

建议目标：

在 action summary 之后继续打磨 blocker repair path 和阶段趋势，让长期报告更清楚地区分“马上修复哪个命令”“哪些学习项可以继续”和“哪些状态正在积累风险”。

v1.0：可长期使用的数学学习系统

目标：

用户可以稳定地用苏格拉底学习一个完整数学主题

必须完成：

完整项目生命周期

多 session 学习

可靠 reference KB

稳定 Obsidian 导出

错因库

自动组题

学习状态追踪

阶段性学习报告

优先级排序
必须优先做

项目初始化

目录与配置规范

本地 reference 导入

学习计划生成

引导式教学 session

原子笔记草稿

session 记录

简单练习生成

learning state 初版

暂缓做

全网资料搜索

多 Agent 自治协作

完整 Obsidian 插件

Lean 全自动证明

复杂 OCR 流水线

多用户系统

Web UI

高级 spaced repetition

复杂 benchmark

当前最推荐的开发顺序
1. socrates init
2. project.yaml schema
3. source_registry.yaml schema
4. local reference import
5. simple markdown/PDF extraction
6. chapter/section index
7. learning plan generation
8. session state machine
9. session transcript落盘
10. atomic note draft generation
11. exercise generation
12. mistake bank
13. learning_state update
14. Obsidian export
15. eval reports
最小可用产品标准

苏格拉底 v0.1 完成时，应该能完成下面这个场景：

用户输入：
  我想学习群论，项目放在 ./projects/group_theory，
  目标是为后续学习表示论做准备。

系统：
  1. 初始化 group_theory 项目。
  2. 创建标准目录。
  3. 记录用户目标。
  4. 导入一本群论教材或讲义。
  5. 为前几章生成学习计划。
  6. 开启第一节教学 session。
  7. 通过问题引导用户理解 subgroup / normal subgroup。
  8. 记录用户回答和错因。
  9. 生成 Normal Subgroup 原子笔记草稿。
  10. 生成 5 道配套练习。
  11. 更新 learning_state.json。
  12. 给出下一次学习建议。

只要这个流程跑通，苏格拉底项目就有了稳定的核心。

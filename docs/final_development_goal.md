# 最终开发目标

## 项目名称

**苏格拉底 Socrates**

## 项目定位

苏格拉底是一个面向数学学习的项目式学习 Agent。它不是一个单纯的数学解题器，也不是一个普通的问答机器人，而是一个围绕长期学习项目运行的数学学习系统。

用户输入想要学习的数学主题与项目存放位置后，系统会初始化一个独立学习项目，并在该项目目录中持续完成资料整理、学习计划设计、引导式教学、原子笔记生成、练习组题、错因分析与复习规划。

项目的核心目标是：

> 帮助用户以项目式方式系统学习数学知识，并在学习过程中沉淀出可靠、可复习、可扩展的个人数学知识库。

---

## 核心理念

### 1. 项目式学习

每一个学习主题都被视为一个长期项目，而不是一次性对话。

例如：

- 群论学习项目
- 同调代数学习项目
- 表示论学习项目
- 代数几何学习项目
- 实分析学习项目

每个项目都有独立的目录结构、参考文献、学习计划、学习记录、原子笔记、题库和用户掌握状态。

---

### 2. 苏格拉底式教学

系统默认不直接给出完整答案，而是通过提问、诊断、提示和反馈帮助用户自己完成理解与推理。

核心教学策略包括：

- 先诊断用户已有知识
- 再给出最小必要提示
- 鼓励用户自己补全关键步骤
- 对错误进行错因分析
- 针对薄弱点生成后续练习
- 将学习成果沉淀为用户自己的笔记

系统应该尽量避免：

- 直接代替用户完成证明
- 无差别输出大段讲义
- 在没有诊断的情况下给出完整答案
- 生成未经校验的知识条目或题目

---

### 3. 知识库沉淀

苏格拉底的长期价值不只是“教会一次”，而是帮助用户持续积累个人数学知识库。

每学完一个知识点，系统会自动生成一份原子笔记草稿，交由用户审核修改后落盘到知识库中，并兼容 Obsidian 复习。

原子笔记类型包括：

- 定义笔记 Definition Note
- 定理笔记 Theorem Note
- 例子笔记 Example Note
- 反例笔记 Counterexample Note
- 技巧笔记 Technique Note
- 证明模板 Proof Pattern Note
- 习题笔记 Exercise Note
- 错因笔记 Misconception Note

---

### 4. Reference KB 与 Personal KB 分离

系统应严格区分外部参考知识库和用户个人知识库。

- Reference KB：来源于教材、论文、讲义、网页、OCR 清洗结果等外部材料。
- Personal KB：来源于用户学习后的理解、总结、错因、原子笔记和复习材料。

外部资料不能直接污染用户的最终笔记。

正确流程是：

raw reference
  ↓
converted reference
  ↓
curated reference
  ↓
teaching session
  ↓
draft atomic note
  ↓
user review
  ↓
personal knowledge base
最终系统能力
1. 项目初始化能力

用户输入学习主题和项目存放路径后，系统可以自动创建完整学习项目。

输入示例：

topic: Homological Algebra
path: ~/SocratesProjects/homological_algebra
goal: 为学习导出范畴和三角范畴做准备
main_reference: Weibel, An Introduction to Homological Algebra

系统自动生成：

homological_algebra/
  project.yaml
  README.md
  00_meta/
  01_references/
  02_learning_plan/
  03_sessions/
  04_atomic_notes/
  05_exercises/
  06_kb/
  07_exports/
  08_evals/
2. 参考资料发现与管理能力

系统可以根据用户输入的学习主题，帮助用户建立参考资料列表。

资料来源包括：

用户本地 PDF

用户本地 Markdown / LaTeX 文件

教材

讲义

论文

Survey

在线资料

arXiv

Wikipedia / nLab / Stacks Project 等开放资料

系统应维护统一的 source_registry.yaml，记录每份资料的来源、角色、优先级和处理状态。

资料角色包括：

main_textbook

secondary_reference

lecture_notes

exercise_source

survey

advanced_reference

online_reference

3. 文献清洗与结构化能力

系统可以调用 OCR、PDF parser、MinerU、Mathpix 等工具，将参考资料转化为 Markdown、LaTeX 或结构化 JSON。

清洗后的内容需要经过校验与修正，不能直接进入最终知识库。

系统需要识别并抽取：

章节结构

定义

定理

命题

引理

推论

例子

反例

证明

习题

图表

公式

交叉引用

页码与出处

4. 学习计划设计能力

系统可以与用户交互，制定长期与短期学习计划。

学习计划包括：

长期学习目标

主参考路径

每周学习安排

每次学习 session 的目标

概念依赖图

章节检查点

复习节点

阶段性测试

计划可以基于：

某本主教材

某份讲义

某个研究目标

某门课程 syllabus

用户自定义目标

5. 引导式教学能力

系统可以按照学习计划逐章节进行教学。

每次教学 session 应包括：

明确本次学习目标

回顾前置知识

提出诊断问题

进行最小必要讲解

引导用户补全定义、例子或证明步骤

检测用户误区

给出分级提示

总结本次学习内容

生成原子笔记草稿

生成配套练习

更新用户学习状态

6. 用户知识库沉淀能力

系统在每次学习后自动生成原子笔记草稿。

每份笔记应包含：

YAML frontmatter

标题

类型

所属主题

来源

定义或定理陈述

直观解释

例子

反例

证明思路

常见误区

相关概念链接

复习问题

用户审核状态

笔记默认进入 draft 状态，用户审核后再进入正式 Obsidian vault。

7. 自动组题能力

系统可以根据当前学习内容和用户错因自动生成练习。

每道题应包含：

题目陈述

类型

难度

涉及概念

前置知识

分级提示

标准解答

评分 rubric

常见错误

目标训练点

题目类型包括：

定义辨析题

例子构造题

反例构造题

计算题

证明题

改错题

概念关系题

综合题

8. 用户学习状态建模能力

系统需要长期维护用户学习状态。

包括：

概念掌握度

证明技能掌握度

典型错因

已完成练习

未掌握知识点

复习计划

学习偏好

常用符号习惯

示例：

JSON
{
  "concept_mastery": {
    "normal_subgroup": 0.82,
    "quotient_group": 0.61,
    "group_action": 0.48
  },
  "proof_skills": {
    "unfold_definition": 0.86,
    "construct_counterexample": 0.42,
    "diagram_chasing": 0.31
  },
  "misconceptions": {
    "normal_equals_central": 3,
    "confuse_orbit_and_stabilizer": 2
  }
}
9. 错因库能力

系统应持续积累用户个人错因库。

每个错因应包含：

错因 ID

涉及概念

错误表现

诊断问题

修复策略

对应练习

出现次数

是否已修复

错因库不仅用于记录错误，也用于生成针对性复习和练习。

10. 验证与评测能力

数学学习 Agent 必须具备验证层，避免生成错误知识。

验证对象包括：

OCR 清洗结果

定义和定理抽取结果

原子笔记

自动生成题目

标准解答

教学过程

用户答案评估

学习计划合理性

可使用的验证方式包括：

LLM judge + rubric

Lean statement skeleton

SageMath / GAP / SymPy 计算验证

counterexample search

checklist-based evaluation

用户人工审核

最终项目形态

苏格拉底最终应成为一个本地优先、可扩展、可复盘的数学学习 Agent 系统。

它的理想使用方式是：

用户想系统学习一个数学主题
  ↓
初始化一个学习项目
  ↓
导入或搜索参考资料
  ↓
清洗并整理成 reference KB
  ↓
生成学习计划
  ↓
逐章节进行苏格拉底式教学
  ↓
每次学习后沉淀原子笔记
  ↓
自动生成练习与复习任务
  ↓
记录用户错因和掌握状态
  ↓
长期形成个人数学知识库

最终目标不是让系统替用户学习数学，而是：

让系统成为用户长期学习数学、整理数学、复习数学和训练证明能力的项目管理者、引导教师、笔记助手与练习生成器。

---

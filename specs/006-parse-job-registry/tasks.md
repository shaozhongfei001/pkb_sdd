# Tasks: Parse Job Registry（006）

> **Spec**：`specs/006-parse-job-registry`  
> **分支**：`feature/006-parse-job-registry`  
> **Plan**：`plan.md`（Tech Lead Plan 已落地）  
> **Dev 必读**：本文件 → `plan.md` → `spec.md` → `acceptance.md` → `test_cases.md`

---

## 流水线阶段总览

| 阶段 | 角色 | 说明 | 状态 |
|------|------|------|------|
| **P1** | TL | Plan 五件套 | [x] |
| **P2** | DB | Plan Review | [ ] |
| **P3** | Dev | 只读实现方案（不写代码） | [ ] |
| **P4** | TL | Review & Approval | [ ] |
| **P5** | Dev | Implementation（白名单内） | [ ] |
| **P6** | DB | Implementation Review | [ ] |
| **P7** | QA | E2E 验收 A001–A015 | [ ] |
| **P8** | HO | Handoff 文档 | [ ] |
| **P9** | TL | Final Review / merge 决策 | [ ] |

**门禁**：P2 未 PASS → 不得 P5；P6 未 PASS → 不得 P7；P7 未 PASS → 不得 P8/P9。

---

## Dev 文件白名单（P5 起生效 — P4 TL 批准）

**允许新增**：

```text
sql/migrations/006_parse_registry_v1.sql
sql/migrations/006_parse_registry_v1_down.sql          # 可选；测试回滚
backend/app/models/parse_registry.py
backend/app/models/document.py                         # 若尚无 KbDocument
backend/app/services/parse_registry.py
backend/app/core/parse_registry_mapping.py             # 可选
backend/tests/test_parse_registry.py
```

**允许修改**：

```text
backend/app/cli/main.py                                # 006 CLI 命令
specs/006-parse-job-registry/tasks.md                  # 勾选
```

**只读 import（禁止修改文件内容）**：

```text
backend/app/core/parsed_paths.py
backend/app/core/vault_paths.py
backend/app/core/config.py
backend/app/models/file.py
```

**禁止修改**：

```text
backend/app/services/markitdown_parser.py
backend/app/adapters/markitdown_adapter.py
backend/app/services/inventory_scanner.py
backend/app/services/file_content_vault.py
backend/app/services/duplicate_governance.py
backend/app/services/parser_router.py
sql/001_init_schema_v1_1.sql
config/**
docs/**
.cursor/**
raw_vault/**（真实产物）
parsed/**（真实产物）
curated/**、quarantine/**、data/**
specs/001-*/** … specs/005-*/**
specs/006-parse-job-registry/plan.md
```

---

## 全局硬约束（P5 Dev Tasks 均适用）

1. 006 是 **parse registry / ingest / 查询**，不是 parser。
2. **不**调用 MarkItDown / MinerU / OCR；**不**读 `original.bin` 做解析。
3. **不**修改 `markitdown_parser.py` 或 005 行为。
4. **不**默认全库 reconcile；reconcile 须显式 filter + limit。
5. **不** delete/move/overwrite raw_vault 或 parsed。
6. migration **additive only**；**不**改 init SQL。
7. **不写** init SQL `kb_parse_job`（per-content queue 保留）。
8. **不写** curated / 向量 / 项目卡 / Streamlit。
9. 单条 ingest 失败 **continue**；dry-run **不写 DB**。
10. **TL 实现决策**：Dev 必读 `plan.md` **附录 A**（Q1–Q15）。

---

## P1 — TL Plan

### T001 编写 spec.md

- [x] 用户故事、目标、非目标、数据流
- [x] 与 005 / init SQL 边界
- [x] `kb_parse_run` 命名说明

### T002 编写 plan.md（§1–§29 + 附录 A）

- [x] 背景、schema 草案、ORM、CLI、幂等、reconcile、事务
- [x] Dev 白名单、DB/QA 关注点、STOP 条件

### T003 编写 tasks.md / acceptance.md / test_cases.md

- [x] 流水线九阶段
- [x] A001–A015 验收项
- [x] test cases 全覆盖

### T004 Plan 完成 STOP

- [x] STOP → **P2 DB Plan Review**

---

## P2 — DB & Data Plan Review

### T005 DB Agent 审查 Plan（只读）

- [ ] 已读 `plan.md` §9–§11、§25
- [ ] 确认 migration additive；无破坏性 ALTER 001–005 表
- [ ] 确认 `kb_parse_run` vs init `kb_parse_job` 共存策略
- [ ] 确认 UNIQUE / FK / parse_status 枚举 / kb_document bridge
- [ ] 确认 reconcile opt-in 与事务策略可审查
- [ ] 输出结论：**PASS** / **PASS_WITH_NOTES** / **BLOCKED**

**BLOCKED** → STOP → TL 修补 Plan  
**PASS** → STOP → P3 Dev 只读方案

---

## P3 — Dev Agent 只读实现方案

### T006 Dev 阅读与方案输出（不写代码）

- [ ] 已读 `tasks.md`、`plan.md` 附录 A、`spec.md`
- [ ] 已读 005 manifest/report 结构、`parsed_paths.py`
- [ ] 已读 init SQL `kb_document`、`kb_file_content.parse_status`
- [ ] 输出：类/方法清单、migration 执行方式、测试策略、风险项
- [ ] 书面确认：不修改 `markitdown_parser.py`

### T007 Dev 确认 DB 边界

- [ ] 书面确认：006 写 `kb_parse_run/result/artifact` + parse_status + kb_document
- [ ] 书面确认：006 **不写** init `kb_parse_job`

**完成后 STOP → P4 TL 批准**

---

## P4 — TL Review & Approval

### T008 P4 TL 裁决（DB Review 后填写）

| # | 裁决 | 说明 |
|---|------|------|
| R1 | 表名 | `kb_parse_run` / `kb_parse_result` / `kb_parsed_artifact` |
| R2 | migration 文件 | `006_parse_registry_v1.sql` |
| R3 | 005 衔接 | `register-parse-report` only |
| R4 | parser_profile | `markitdown_default_v1` |
| R5 | reconcile | opt-in + limit ≤ 100 |

### T008b TL 书面批准 Dev Implementation

- [ ] DB Plan Review = **PASS** 或 **PASS_WITH_NOTES**（无阻断）
- [ ] Dev 只读方案已审
- [ ] **结论：APPROVED_FOR_P5** 或 **NEEDS_PLAN_REPAIR**

**STOP → P5 Dev**

---

## P5 — Dev Implementation

### T009 编写 migration

- [ ] 新增 `sql/migrations/006_parse_registry_v1.sql`
- [ ] CREATE TABLE 三表；IF NOT EXISTS
- [ ] 可选 down migration（测试）

### T010 实现 ORM models

- [ ] `parse_registry.py`：KbParseRun、KbParseResult、KbParsedArtifact
- [ ] `document.py`：KbDocument（若需要）
- [ ] 字段与 migration 一致

### T011 实现 ParseRegistryService

- [ ] `register_from_report()`：读 report + manifest → upsert
- [ ] `reconcile_parsed_artifacts()`：opt-in scan
- [ ] 查询 helpers：list/show jobs、results、artifacts
- [ ] retry_of_result_id 逻辑
- [ ] kb_document bridge + parse_status UPDATE
- [ ] dry-run 路径
- [ ] 单条失败 continue

### T012 实现 CLI

- [ ] `register-parse-report`
- [ ] `list-parse-jobs`、`show-parse-job`
- [ ] `list-parse-results`、`list-parsed-artifacts`
- [ ] `reconcile-parsed-artifacts`（filter 护栏）
- [ ] `ensure_readonly()` 入口

### T013 实现 pytest

- [ ] `test_parse_registry.py`（≥25 functions）
- [ ] 覆盖 `test_cases.md` 全部 TC
- [ ] migration upgrade + idempotency
- [ ] 005 回归：`test_markitdown_parser.py` pass

### T014 Dev 自检 STOP

- [ ] 改动文件均在白名单内
- [ ] 未改 `markitdown_parser.py`
- [ ] `tasks.md` P5 项勾选
- [ ] 输出：文件清单、migrate/pytest/CLI 命令
- [ ] STOP → **P6 DB Implementation Review**

---

## P6 — DB & Data Implementation Review

### T015 DB Agent 审查 Dev diff

- [ ] migration 与 ORM 一致
- [ ] 幂等 UNIQUE 正确
- [ ] 无写 init `kb_parse_job`
- [ ] parse_status / kb_document bridge 正确
- [ ] 结论：**PASS** / **PASS_WITH_NOTES** / **BLOCKED**

---

## P7 — E2E QA

### T016 QA 执行验收

- [ ] 对照 `test_cases.md` 与 `acceptance.md` A001–A015
- [ ] 必查四项 + 006 专项
- [ ] 输出验收表 + 证据
- [ ] STOP → P8 Handoff

---

## P8 — Handoff

### T017 HO 撰写交接文档

- [ ] `docs/handoff-phase1-006-parse-job-registry.md`
- [ ] 含 migrate 命令、CLI 用法、A001–A015

---

## P9 — TL Final Review

### T018 TL Final Review

- [ ] 范围符合 Plan / Spec
- [ ] DB/QA 均 PASS
- [ ] 005 未回退
- [ ] 可 merge main / 008 入口条件

---

## 任务进度总览

| Task | 阶段 | 说明 | 状态 |
|------|------|------|------|
| T001–T004 | P1 | TL Plan | [x] |
| T005 | P2 | DB Plan Review | [ ] |
| T006–T007 | P3 | Dev 只读方案 | [ ] |
| T008 | P4 | TL Approval | [ ] |
| T009–T014 | P5 | Dev Implementation | [ ] |
| T015 | P6 | DB Implementation Review | [ ] |
| T016 | P7 | E2E QA | [ ] |
| T017 | P8 | Handoff | [ ] |
| T018 | P9 | TL Final Review | [ ] |

---

**Tasks 结束** — 当前 STOP 点：**P2 DB Plan Review**。

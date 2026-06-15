# Tasks: Parse Job Registry（006）

> **Spec**：`specs/006-parse-job-registry`  
> **分支**：`feature/006-parse-job-registry`  
> **Plan**：`plan.md`（P4 Plan Repair 已落地）  
> **Dev 必读**：本文件 → `plan.md` → `spec.md` → `acceptance.md` → `test_cases.md`

---

## 流水线阶段总览

| 阶段 | 角色 | 说明 | 状态 |
|------|------|------|------|
| **P1** | TL | Plan 五件套 | [x] |
| **P2** | DB | Plan Review | [x] PASS_WITH_NOTES |
| **P3** | Dev | 只读实现方案（不写代码） | [x] |
| **P4** | TL | Review & Approval + Plan Repair | [x] APPROVED_FOR_P5 |
| **P5** | Dev | Implementation（白名单内） | [x] |
| **P6** | DB | Implementation Review | [x] PASS_WITH_NOTES |
| **P7** | QA | E2E 验收 A001–A019 | [x] PASS_WITH_NOTES |
| **P8** | HO | Handoff 文档 | [x] |
| **P9** | TL | Final Review / merge 决策 | [ ] |

**门禁**：P2 未 PASS → 不得 P5；P4 未 APPROVED_FOR_P5 → 不得 P5；P6 未 PASS → 不得 P7。

---

## P4 TL 裁决摘要（2026-06-15）

| ID | 裁决 | Plan 引用 |
|----|------|-----------|
| **M1 / Q16** | artifact UNIQUE = `uk_artifact_scope(run_uid, content_uid, artifact_type, parser_name, parser_adapter_version)` | plan §8、§9.3 |
| **M2 / Q17** | 006 registry `--dry-run` 零 DB 写；禁止 `DRY_RUN_COMPLETED` | plan §6、§14、Q17 |
| **M3 / Q18** | `report.dry_run=true` → exit 1 + `INVALID_DRY_RUN_REPORT` | plan §12.1、§20、Q18 |
| **M4 / Q19** | `document_uid = content_uid`；禁止 sha256 备选 | plan §9.5、Q19 |
| **S1 / Q20** | `run_uid = parse_run_{UTC:%Y%m%dT%H%M%SZ}_{uuid4.hex[:8]}` | plan §5.1、Q20 |
| **S4 / Q21** | SKIPPED 无 manifest 时零 artifact 行 | plan §8、§12.3、Q21 |

**P4 结论**：**APPROVED_FOR_P5**（Plan Repair 完成；建议 DB 对 §9 schema 变更做 **Plan Re-Review** 确认 M1）。

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
9. 单条 ingest 失败 **continue**；006 registry **`--dry-run` 零 DB 写**。
10. **拒绝** 005 `dry_run=true` report（`INVALID_DRY_RUN_REPORT`）。
11. **artifact UNIQUE** 使用 `uk_artifact_scope`（含 `run_uid`）。
12. **`document_uid = content_uid`**；SKIPPED 无 manifest 时 **零** artifact 行。
13. **TL 实现决策**：Dev 必读 `plan.md` **附录 A**（Q1–Q21）。

---

## P1 — TL Plan

### T001–T004

- [x] 五件套完成 → P2

---

## P2 — DB & Data Plan Review

### T005 DB Agent 审查 Plan（只读）

- [x] migration additive；`kb_parse_run` vs init `kb_parse_job` 共存
- [x] 结论：**PASS_WITH_NOTES**（M1 artifact UNIQUE 待 P4 修复 → 已在 P4 落地）

---

## P3 — Dev 只读实现方案

### T006–T007

- [x] Dev 只读方案完成
- [x] 确认：006 不写 init `kb_parse_job`；不改 `markitdown_parser.py`

---

## P4 — TL Review & Approval + Plan Repair

### T008 P4 TL 裁决

| # | 裁决 | 状态 |
|---|------|------|
| R1 | 表名：`kb_parse_run` / `kb_parse_result` / `kb_parsed_artifact` | [x] |
| R2 | migration：`006_parse_registry_v1.sql` | [x] |
| R3 | 005 衔接：`register-parse-report` only | [x] |
| R4 | M1 `uk_artifact_scope` | [x] |
| R5 | M2 dry-run 零 DB 写 | [x] |
| R6 | M3 拒绝 005 dry-run report | [x] |
| R7 | M4 `document_uid = content_uid` | [x] |
| R8 | S1 run_uid 公式 | [x] |
| R9 | S4 SKIPPED 零 artifact | [x] |

### T008b TL 书面批准 Dev Implementation

- [x] P2 PASS_WITH_NOTES；P3 完成；Plan Repair M1–M4/S1/S4 已写入 plan.md
- [x] **结论：APPROVED_FOR_P5**

**STOP → P5 Dev**（建议 DB 对 §9 `uk_artifact_scope` 做 **Plan Re-Review** 后 Dev 开工）

---

## P5 — Dev Implementation

### T009 编写 migration

- [x] `006_parse_registry_v1.sql` 含 `uk_artifact_scope`（§9.3）
- [x] `run_uid` 列 VARCHAR(64)；artifact `run_uid NOT NULL`

### T010 实现 ORM models

- [x] 与 migration 一致；含 `uk_artifact_scope` 映射

### T011 实现 ParseRegistryService

- [x] `register_from_report()`：拒绝 `dry_run=true` report
- [x] 006 `--dry-run`：零 DB 写
- [x] `document_uid = content_uid`
- [x] SKIPPED 无 manifest：仅 result，零 artifact
- [x] `run_uid` 按 §5.1 生成

### T012 实现 CLI

- [x] 全部 006 命令 + 护栏

### T013 实现 pytest

- [x] 覆盖 M1–M4 / S4 test cases（TC015–TC019 等）

### T014 Dev 自检 STOP

- [x] STOP → P6

---

## P6 — DB Implementation Review

### T015 DB Agent 审查实现

- [x] ORM 与 migration 主结构一致；`uk_artifact_scope` 含 `run_uid`
- [x] 无阻断 schema / FK 问题；不写 `kb_parse_job`
- [x] 结论：**PASS_WITH_NOTES**（migration 手动执行；reconcile 无 dedup；共享库并行风险 — 非阻断）

**STOP → P7**

---

## P7 — E2E QA

### T016 QA 验收 A001–A019

- [x] 006 专项 36 passed；全量 120 passed
- [x] M1–M4 / S1 / S4 测试证据齐全
- [x] 不解析、不改 raw_vault/parsed、不接 MinerU/OCR
- [x] 结论：**PASS_WITH_NOTES**（无阻断项）

**STOP → P8**

---

## P8 — Handoff

### T017 Handoff 文档

- [x] `docs/handoff-phase1-006-parse-job-registry.md` 已撰写
- [x] tasks.md P6–P8 勾选

**STOP → P9**

---

## P9 — TL Final Review

### T018 TL merge 决策

- [ ] 阅读 handoff + plan + tasks（P1–P8 全部 `[x]`）
- [ ] 文件白名单 / migration 安全 / M1–M4 / 测试结果复核
- [ ] merge main 裁决

---

## 任务进度总览

| Task | 阶段 | 状态 |
|------|------|------|
| T001–T004 | P1 | [x] |
| T005 | P2 | [x] PASS_WITH_NOTES |
| T006–T007 | P3 | [x] |
| T008–T008b | P4 | [x] APPROVED_FOR_P5 |
| T009–T014 | P5 | [x] |
| T015 | P6 | [x] PASS_WITH_NOTES |
| T016 | P7 | [x] PASS_WITH_NOTES |
| T017 | P8 | [x] |
| T018 | P9 | [ ] |

---

**Tasks 结束** — 当前 STOP 点：**P9 Tech Lead Final Review** → merge main → 007/008 Spec Plan。

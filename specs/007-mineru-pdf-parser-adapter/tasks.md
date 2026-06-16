# Tasks: MinerU PDF Parser Adapter（007）

> **Spec**：`specs/007-mineru-pdf-parser-adapter`  
> **分支**：`feature/007-mineru-pdf-parser-adapter`  
> **Plan**：`plan.md`（P1 TL Plan）  
> **Dev 必读**：本文件 → `plan.md` → `spec.md` → `acceptance.md` → `test_cases.md`

---

## 流水线阶段总览

| 阶段 | 角色 | 说明 | 状态 |
|------|------|------|------|
| **P1** | TL | Plan（五件套） | [x] |
| **P2** | DB | Plan Review（§15 DB 关注点） | [ ] |
| **P3** | Dev | 只读实现方案（不写代码） | [ ] |
| **P4** | TL | Review & Approval + 文件白名单 | [ ] |
| **P5** | Dev | Implementation（白名单内） | [ ] |
| **P6** | DB | Implementation Review | [ ] |
| **P7** | QA | E2E 验收 A001–A020 | [ ] |
| **P8** | HO | Handoff 文档 | [ ] |
| **P9** | TL | Final Review / merge 决策 | [ ] |

**门禁**：P2 未 PASS → 不得 P5；P6 未 PASS → 不得 P7；P7 未 PASS → 不得 P8/P9。

---

## P1 — Tech Lead Plan

### T001 阅读前置材料

- [x] `docs/handoff-phase1-005-markitdown-parser.md`
- [x] `docs/handoff-phase1-006-parse-job-registry.md`
- [x] `specs/005-markitdown-parser/*`（spec / plan / tasks / acceptance / test_cases）
- [x] `specs/006-parse-job-registry/*`
- [x] `backend/app/core/vault_paths.py`
- [x] `backend/app/core/parsed_paths.py`
- [x] `backend/app/services/parser_router.py`
- [x] `backend/app/services/markitdown_parser.py`
- [x] `backend/app/services/parse_registry.py`
- [x] `backend/app/cli/main.py`
- [x] `backend/tests/test_markitdown_parser.py`
- [x] `backend/tests/test_parse_job_registry.py`

### T002 撰写 007 五件套

- [x] `spec.md` — 背景、目标、非目标、I/O 契约
- [x] `plan.md` — adapter / service / CLI / registry / 路径 / 安全 / DB Review
- [x] `tasks.md` — 本文件
- [x] `acceptance.md` — A001–A020
- [x] `test_cases.md` — TC001+

### T003 P1 范围确认

- [x] 仅 PDF / MinerU adapter；不扩 OCR / IMAGE / curated / vector
- [x] 不修改 001–006 封闭 service；不修改 006 schema
- [x] 复用 002 vault paths + 005 parsed paths
- [x] 可选 `--register` 经 006 registry service

**STOP → P2 DB & Data Plan Review**

---

## P2 — DB & Data Plan Review

### T004 审查 SQL / ORM 影响

- [ ] 确认 007 **无** migration / 无 init SQL 修改
- [ ] 确认 `--register` 仅使用既有 `kb_parse_run` / `kb_parse_result` / `kb_parsed_artifact`
- [ ] 裁决 **DB-Q5**：`assets/` 的 artifact 索引策略（`PARSED_ASSETS` vs metadata only）
- [ ] 裁决 **DB-Q6**：`kb_document` `parser_profile=mineru_default_v1` 薄改 `parse_registry.py` 是否批准
- [ ] 确认 dry-run 零 DB 写（007 + registry M2）
- [ ] 确认 parse result status 映射（含 TIMEOUT / PARTIAL）
- [ ] 结论：**PASS** / **PASS_WITH_NOTES** / **BLOCKED**

**STOP → P3（PASS）或回 TL 修订 Plan（BLOCKED）**

---

## P3 — Dev 只读方案

### T005 实现方案文档（不写代码）

- [ ] `MinerUAdapter` 接口与 subprocess 调用草图
- [ ] `MinerUPdfParserService` 流程对齐 005（候选 / limit / 幂等 / force）
- [ ] assets 归一化与 temp 清理策略
- [ ] `--register` 与 `register_parse_report` 衔接
- [ ] pytest mock 策略
- [ ] 风险与未决项清单

### T006 白名单草案

- [ ] 提交 P4 审查的精确文件列表（见 plan §17）

**STOP → P4**

---

## P4 — TL Review & Approval

### T007 Plan / 白名单 Gate

- [ ] 阅读 P2 DB 结论并合入 plan（若需修订）
- [ ] 批准 Dev 文件白名单
- [ ] 关闭附录 A Q1–Q6
- [ ] 结论：**APPROVED_FOR_P5** / **REVISE**

**STOP → P5（APPROVED）**

---

## P5 — Dev Implementation

### T008 新增 MinerUAdapter

- [ ] `backend/app/adapters/mineru_adapter.py`
- [ ] `PARSER_NAME` / `PARSER_ADAPTER_VERSION` / `AdapterResult` / `MinerUAdapterError`
- [ ] `check_availability()` + `convert()` + 错误分类 + timeout

### T009 新增 MinerUPdfParserService

- [ ] `backend/app/services/mineru_pdf_parser.py`
- [ ] 候选查询、PDF in-scope 过滤、limit / 幂等 / force
- [ ] vault / parsed 路径经 002 / 005 helpers
- [ ] 写三文件 + 可选 `assets/`
- [ ] `parse_mineru_pdf_report_{UTC}.json`

### T010 CLI `parse-mineru-pdf`

- [ ] `backend/app/cli/main.py` 新增命令与护栏
- [ ] `--dry-run` / `--force` / `--timeout` / `--register` / `--no-register`
- [ ] 非 dry-run MinerU 预检

### T011 可选 Registry 衔接

- [ ] `--register` 调用 `ParseRegistryService.register_parse_report()`
- [ ] 若 P2 批准：薄改 `parse_registry.py`（mineru profile / assets metadata）
- [ ] dry-run 不 register

### T012 pytest

- [ ] `backend/tests/test_mineru_pdf_parser.py`（≥30 functions）
- [ ] 默认 mock adapter；覆盖 test_cases.md

### T013 回归

- [ ] `pytest -q` 全量通过（001–006 无破坏）

**STOP → P6**

---

## P6 — DB Implementation Review

### T014 Schema / 写路径审查

- [ ] grep 无未授权 SQL / migration
- [ ] `--no-register`（默认）无 DB 写
- [ ] `--register` 仅经 `ParseRegistryService`
- [ ] dry-run 零 DB 写
- [ ] 结论：**PASS** / **PASS_WITH_NOTES** / **BLOCKED**

**STOP → P7**

---

## P7 — E2E QA

### T015 验收 A001–A020

- [ ] 007 专项 pytest 通过
- [ ] 005 / 006 回归通过
- [ ] dry-run / force / timeout / dependency missing 实测
- [ ] 结论：**PASS** / **PASS_WITH_NOTES** / **BLOCKED**

**STOP → P8**

---

## P8 — Handoff

### T016 Handoff 文档

- [ ] `docs/handoff-phase1-007-mineru-pdf-parser-adapter.md`
- [ ] tasks.md P6–P8 勾选

**STOP → P9**

---

## P9 — TL Final Review

### T017 merge 决策

- [ ] 阅读 handoff + plan + tasks（P1–P8 全部 `[x]`）
- [ ] 白名单 / 测试 / scope 复核
- [ ] merge main 裁决

---

## Dev 文件白名单（P4 批准后生效 — 草案）

**允许新增**：

```text
backend/app/adapters/mineru_adapter.py
backend/app/services/mineru_pdf_parser.py
backend/tests/test_mineru_pdf_parser.py
```

**允许修改（P4 最终确认）**：

```text
backend/app/cli/main.py
backend/app/services/parse_registry.py          # 仅 P2 批准的 mineru 薄扩展
specs/007-mineru-pdf-parser-adapter/tasks.md
```

**只读 import（禁止改内容）**：

```text
backend/app/core/parsed_paths.py
backend/app/core/vault_paths.py
backend/app/core/parser_routing.py
```

**禁止修改**：

```text
backend/app/services/markitdown_parser.py
backend/app/adapters/markitdown_adapter.py
backend/app/services/inventory_scanner.py
backend/app/services/file_content_vault.py
backend/app/services/parser_router.py
backend/app/services/duplicate_governance.py
sql/**
config/**
docs/**（P8 除外）
raw_vault/**
parsed/**（测试 temp 除外）
specs/001-006/**
```

---

## 任务进度总览

| Task | 阶段 | 状态 |
|------|------|------|
| T001–T003 | P1 | [x] |
| T004 | P2 | [ ] |
| T005–T006 | P3 | [ ] |
| T007 | P4 | [ ] |
| T008–T013 | P5 | [ ] |
| T014 | P6 | [ ] |
| T015 | P7 | [ ] |
| T016 | P8 | [ ] |
| T017 | P9 | [ ] |

---

**Tasks 结束** — 当前 STOP 点：**P2 DB & Data Plan Review**。

# Tasks: MarkItDown 普通文档解析（005）

> **Spec**：`specs/005-markitdown-parser`  
> **分支**：`feature/005-markitdown-parser-adapter`  
> **Plan**：`plan.md`（Tech Lead Plan Repair 已落地）  
> **Dev 必读**：本文件 → `plan.md` → `spec.md` → `acceptance.md` → `test_cases.md`

---

## 流水线阶段总览

| 阶段 | 角色 | 说明 | 状态 |
|------|------|------|------|
| **P1** | TL | Plan Repair（五件套） | [x] |
| **P2** | DB | Plan Re-Review | PASS_WITH_NOTES |
| **P3** | Dev | 只读实现方案（不写代码） | [x] |
| **P4** | TL | Review & Approval | [x] |
| **P5** | Dev | Implementation（白名单内） | [ ] |
| **P6** | DB | Implementation Review | [ ] |
| **P7** | QA | E2E 验收 A001–A017 | [ ] |
| **P8** | HO | Handoff 文档 | [ ] |
| **P9** | TL | Final Review / merge 决策 | [ ] |

**门禁**：P2 未 PASS → 不得 P5；P6 未 PASS → 不得 P7；P7 未 PASS → 不得 P8/P9。

---

## Dev 文件白名单（P5 起生效 — P4 TL 批准）

**允许修改**：

```text
backend/app/core/parsed_paths.py                    # 新增
backend/app/adapters/markitdown_adapter.py          # 新增
backend/app/services/markitdown_parser.py             # 新增（含 _resolve_vault_dir / _resolve_original_bin）
backend/app/cli/main.py                               # 新增 parse-markitdown
backend/tests/test_markitdown_parser.py               # 新增
specs/005-markitdown-parser/tasks.md                  # 勾选
```

**P5 默认禁止修改**：

```text
backend/requirements.txt                              # 除非 TL 重新批准依赖策略
```

**只读 import（禁止修改文件内容）**：

```text
backend/app/core/parser_routing.py
backend/app/core/vault_paths.py                       # P4：禁止修改
backend/app/core/config.py
```

**禁止修改**：

```text
backend/app/services/inventory_scanner.py
backend/app/services/file_content_vault.py   # P4：禁止修改
backend/app/services/duplicate_governance.py
backend/app/services/parser_router.py
backend/app/core/vault_paths.py              # P4：禁止修改；005 只读 import
backend/app/core/parser_routing.py           # 禁止改；仅 import
backend/requirements.txt                     # P5 默认禁止
backend/app/models/file.py
backend/app/models/vault.py
backend/app/models/duplicate.py
sql/**
config/**
docs/**
.cursor/**
raw_vault/**（真实产物）
parsed/**（真实产物）
curated/**
quarantine/**
data/**
specs/001-*/**
specs/002-*/**
specs/003-*/**
specs/004-*/**
specs/005-markitdown-parser/plan.md
specs/其他编号/**
```

---

## 全局硬约束（P5 Dev Tasks 均适用）

1. 005 是 MarkItDown-family **adapter MVP**，不是通用 parser 框架。
2. 只解析 **DOCX / PPTX / XLSX / TEXT_OR_MARKDOWN**。
3. 跳过 **PDF_DIGITAL / PDF_SCANNED_OR_IMAGE / IMAGE / UNKNOWN / UNSUPPORTED**。
4. 只读读入 **raw_vault/.../original.bin**（**002 两档**；经 `build_vault_dir` + `build_vault_artifact_paths`）。
5. 可写 **parsed/** 三文件 + **parse_markitdown_report_*.json**。
6. **不写 DB**：禁止 `kb_parse_job`、`kb_document`、`parse_status` 及任何 INSERT/UPDATE/DELETE。
7. **不改 SQL schema**。
8. 不接 MinerU、不做 OCR。
9. 不写 `curated/`、向量库、embedding、项目卡、Streamlit。
10. 不移动/删除/重命名原始文件；不删/覆盖/移动 raw_vault。
11. CLI 必须有 **--sha256 / --content-uid / --limit** 护栏；`limit ≤ 100`。
12. 单条失败 **continue**；FAILED 写 manifest、不写 parsed_text；`--dry-run` 不调用 MarkItDown。
13. **禁止**硬编码 raw_vault 三档路径；**禁止**修改 `vault_paths.py` / `file_content_vault.py`。
14. **`--limit`** 仅计 in-scope parse；out-of-scope skip 不计入。
15. **TL 实现决策**：Dev 必读 `plan.md` **附录 A**（Q1–Q17）。

---

## P1 — TL Plan Repair

### T001 重写 spec.md

- [x] 用户故事、目标、非目标、数据流
- [x] 明确：vault → parsed text；**无 DB 持久化**
- [x] 明确 route_type 四值覆盖与排除项

### T002 重写 plan.md（§1–§28 + 附录 A）

- [x] 001–004 基线、004 关系、输入/输出、adapter 分层
- [x] parsed 路径、manifest/metadata/text 约定
- [x] parse report、CLI、护栏、幂等、错误隔离
- [x] **§19 硬性：不写 DB、不改 schema**
- [x] Dev 白名单、测试、DB/QA 关注点、STOP 条件

### T003 重写 tasks.md / acceptance.md / test_cases.md

- [x] 流水线九阶段
- [x] A001–A017 验收项
- [x] 详细 test cases（含 no DB write）

### T004 Plan Repair 完成 STOP

- [x] 消除所有 DB 写入歧义表述
- [x] STOP → **P2 DB Plan Re-Review**

---

## P2 — DB & Data Plan Re-Review

### T005 DB Agent 审查 Plan（只读）

- [x] 已读 `plan.md` §19、§25
- [x] 确认无「写入 DB parse result / parse_status / kb_parse_job / kb_document」表述
- [x] 确认 schema 变更仅出现在非目标 / 后续 Spec
- [x] 确认批处理护栏、幂等、错误隔离可审查
- [x] 输出结论：**PASS_WITH_NOTES**

**BLOCKED** → STOP → TL 修补 Plan  
**PASS** → STOP → P3 Dev 只读方案

---

## P3 — Dev Agent 只读实现方案

### T006 Dev 阅读与方案输出（不写代码）

- [x] 已读 `tasks.md`、`plan.md` 附录 A、`spec.md`
- [x] 已读 001–004 相关 service / `parser_routing.py` / `vault_paths.py`
- [x] 已检查 `backend/requirements.txt` 中 markitdown 依赖
- [x] 输出：拟建类/方法清单、测试策略、风险项（**不修改任何文件**）
- [x] 识别 raw_vault 两档 vs spec 三档冲突 → 提交 P4 TL 裁决

### T007 Dev 确认 DB 边界

- [x] 书面确认：005 实现 **零** MySQL 写操作
- [x] 若方案含 ORM model 写库 → 删除该部分，STOP → TL

**完成后 STOP → P4 TL 批准**

---

## P4 — TL Review & Approval

### T008 P4 TL 裁决记录（2026-06-15）

| # | 裁决 | 说明 |
|---|------|------|
| R1 | raw_vault **两档** | 以 002 `vault_paths.py` 为唯一权威：`by_hash/{sha256[0:2]}/{sha256}/` |
| R2 | 禁止三档 raw_vault | 005 不得硬编码 `{sha256[2:4]}/` 于 raw_vault |
| R3 | 必须复用 helpers | `build_vault_dir()` + `build_vault_artifact_paths().original_bin` |
| R4 | service 私有方法 | 允许 `_resolve_vault_dir` / `_resolve_original_bin`（内部调用 002 helpers） |
| R5 | 禁止改 vault_paths | P5 不得修改 `vault_paths.py` |
| R6 | 禁止改 file_content_vault | P5 不得修改 `file_content_vault.py` |
| R7 | 禁止 raw_vault 迁移 | — |
| R8 | parsed **三档** | `parsed/by_hash/{sha256[0:2]}/{sha256[2:4]}/{sha256}/` 维持不变 |
| R9 | FAILED 产物 | 写 `parse_manifest.json`（FAILED+error）；不写 `parsed_text.md` |
| R10 | `--limit` | 仅 in-scope parse；out-of-scope skip 不计入 |
| R11 | `--dry-run` | 不调用 MarkItDown；仍做路由/路径/幂等/report |
| R12 | 测试 | 默认 mock adapter；真实 markitdown 仅 txt/md fixture |
| R13 | report 计数 | `total_candidates`=SQL 行数；增 `in_scope_candidates` |
| R14 | requirements | P5 默认不改；缺失则 STOP → TL |

### T008b TL 书面批准 Dev Implementation

- [x] DB Plan Re-Review = **PASS_WITH_NOTES**
- [x] Dev 只读方案已审；raw_vault 路径冲突已裁决
- [x] 五件套已同步 P4 裁决（vault 两档 / parsed 三档）
- [x] 白名单与附录 A Q1–Q17 已更新
- [x] **结论：APPROVED_FOR_P5**
- [x] 授权进入 **P5 Dev Implementation**

**STOP → P5 Dev**

## P5 — Dev Implementation

### T009 实现 parsed_paths 模块

- [x] 新增 `backend/app/core/parsed_paths.py`
- [x] `build_parsed_content_dir()` 符合 plan §8
- [x] `build_parsed_artifact_paths()` 返回三文件路径

### T010 实现 MarkItDownAdapter

- [x] 新增 `backend/app/adapters/markitdown_adapter.py`
- [x] CLI **不** import markitdown
- [x] `parser_adapter_version = "005_mvp_v1"`
- [x] `convert()` 返回 text + metadata + warnings

### T011 实现 MarkItDownParserService

- [x] 新增 `backend/app/services/markitdown_parser.py`
- [x] MySQL **只读**查询 + `match_route_type()` 筛选
- [x] `_resolve_vault_dir` / `_resolve_original_bin` 内部调用 `build_vault_dir` + `build_vault_artifact_paths`
- [x] **禁止**硬编码 raw_vault 三档路径
- [x] 只读 open `original.bin`；写 parsed 三文件（FAILED 仅 manifest）+ 幂等 skip
- [x] 写 `parse_markitdown_report_*.json`（含 `in_scope_candidates`）
- [x] **禁止**任何 session.add/commit/update/delete 业务表

### T012 实现 CLI parse-markitdown

- [x] 修改 `backend/app/cli/main.py`
- [x] 选项：`--config`、`--sha256`、`--content-uid`、`--limit`、`--dry-run`
- [x] 护栏：三者至少其一；limit ≤ 100
- [x] `ensure_readonly()` 在入口

### T013 实现 pytest

- [x] 新增 `backend/tests/test_markitdown_parser.py`（≥20 functions）
- [x] **默认 mock** `MarkItDownAdapter.convert`；真实 markitdown 仅 txt/md（可选）
- [x] 覆盖 `test_cases.md` 全部 TC（含 vault 路径 TC038–TC040）
- [x] 含 no-DB-write、raw_vault/original 不变、vault_paths 未改断言

### T014 Dev 自检 STOP

- [x] 改动文件均在白名单内
- [x] `tasks.md` P5 项勾选
- [x] 输出：文件清单、pytest/CLI 命令、遗留问题
- [x] STOP → **P6 DB Implementation Review**（Dev 不自我验收）

---

## P6 — DB & Data Implementation Review

### T015 DB Agent 审查 Dev diff

- [ ] 无 SQL / migration 变更
- [ ] 无 ORM 写库、无 parse_status 更新
- [ ] 无 kb_parse_job / kb_document 引用写路径
- [ ] 结论：**PASS** / **需修改**

---

## P7 — E2E QA

### T016 QA 执行验收

- [ ] 对照 `test_cases.md` 与 `acceptance.md` A001–A017
- [ ] 必查四项：原始文件、raw_vault、幂等、异常 continue
- [ ] 输出验收表 + 证据
- [ ] STOP → P8 Handoff（通过）或交还 Dev（不通过）

---

## P8 — Handoff

### T017 HO 撰写交接文档

- [ ] `docs/handoff-phase1-005-markitdown-parser.md`
- [ ] 含分支、commit、文件清单、测试结果、A001–A017
- [ ] 明确：005 无 DB 写；parse registry 入口条件给 006

---

## P9 — TL Final Review

### T018 TL Final Review

- [ ] 范围符合 Plan / Spec
- [ ] DB/QA 均 PASS
- [ ] 可 merge main / 006 入口条件

---

## 任务进度总览

| Task | 阶段 | 说明 | 状态 |
|------|------|------|------|
| T001 | P1 | spec.md | [x] |
| T002 | P1 | plan.md | [x] |
| T003 | P1 | acceptance + test_cases + tasks | [x] |
| T004 | P1 | Plan Repair STOP | [x] |
| T005 | P2 | DB Plan Re-Review | [x] PASS_WITH_NOTES |
| T006 | P3 | Dev 只读方案 | [x] |
| T007 | P3 | Dev DB 边界确认 | [x] |
| T008 | P4 | TL Review & Approval | [x] APPROVED_FOR_P5 |
| T009–T014 | P5 | Dev Implementation | [x] |
| T015 | P6 | DB Implementation Review | [ ] |
| T016 | P7 | E2E QA | [ ] |
| T017 | P8 | Handoff | [ ] |
| T018 | P9 | TL Final Review | [ ] |

---

**Tasks 结束** — 当前 STOP 点：**P6 DB Implementation Review**（P5 Dev 已完成，等待 DB 审查）。

# Tasks: 解析路由（004）

> **Spec**：`specs/004-parser-router`
> **分支**：`feature/004-parser-router`
> **Plan**：`plan.md`（Tech Lead 步骤 ① 已落地）
> **Dev 必读**：本文件 → `plan.md` → `spec.md` → `acceptance.md` → `test_cases.md`

---

## Dev 文件白名单（全局）

**允许修改**：

```text
backend/app/services/parser_router.py          # 新增
backend/app/core/parser_routing.py             # 新增（RouteType + routing rules）
backend/app/cli/main.py                        # 新增 route-parsers
backend/tests/test_parser_router.py            # 新增
specs/004-parser-router/tasks.md               # 勾选
```

**禁止修改**：

```text
backend/app/services/inventory_scanner.py
backend/app/services/file_content_vault.py
backend/app/services/duplicate_governance.py
backend/app/models/file.py
backend/app/models/vault.py
backend/app/models/duplicate.py
sql/**
config/**
docs/**
.cursor/**
raw_vault/**（真实产物）
specs/004-parser-router/plan.md
specs/其他编号/**
```

---

## 全局硬约束（T001–T013 均适用）

1. 不处理源代码知识库。
2. 不移动、不删除、不重命名原始文件。
3. 不自动删除重复文件。
4. 不删除 raw_vault 文件。
5. 不接 MinerU。
6. 不接 MarkItDown。
7. 不执行真实解析。
8. 不写 `parsed/`。
9. 不写 `curated/`。
10. 不做 Streamlit。
11. 不做向量库。
12. 不做项目卡蒸馏。
13. 不新增第三方依赖。
14. 不读取 `original.bin` 做路由判断。
15. 不做 OCR / 文本抽取。
16. 不修改 SQL schema。
17. 不持久化 route decision 到数据库（MVP）。
18. **TL 实现决策**：实现前必读 `plan.md` **§23**（Q1–Q7）；报告 hint 字段名 **`future_parser_hint`**（§6.5）。

---

## T001 阅读 001/002/003 模型、服务、CLI、测试与 handoff

### 目标

理解 001–003 已提供的 ORM、批处理模式、CLI、pytest fixture 与 handoff 入口条件，为 004 Parser Router 实现做准备。

### 允许修改范围

- 无（阅读 only）
- 可在本 task 勾选 `[x]`（Dev 完成后）

### 禁止事项

- 不改任何 `backend/**` 代码
- 不改 SQL / config / docs

### 验收标准

- [ ] 已读 `docs/handoff-phase1-003-duplicate-governance.md`
- [ ] 已读 `backend/app/models/file.py`、`vault.py`、`duplicate.py`
- [ ] 已读 `inventory_scanner.py`、`file_content_vault.py`、`duplicate_governance.py`（只读，不改）
- [ ] 已读 `cli/main.py` 中 `scan`、`copy-to-vault`、`govern-duplicates`
- [ ] 已读 `test_inventory_scanner.py`、`test_file_content_vault.py`、`test_duplicate_governance.py`
- [ ] 已读 `tests/fixtures/中文路径/银行项目/`
- [ ] 已读 `plan.md` 全文

---

## T002 确认 004 不执行解析、不接 MinerU/MarkItDown、不写 parsed/curated

### 目标

书面确认 004 MVP 边界：仅路由决策 + JSON 报告；无解析执行、无第三方 parser、无 parsed/curated 写入。

### 允许修改范围

- 无代码；本 task 勾选

### 禁止事项

- **禁止** import / 调用 MinerU、MarkItDown 或任何外部解析 CLI
- **禁止** 写入 `parsed/`、`curated/`、`quarantine/`
- **禁止** OCR、文本抽取、chunking

### 验收标准

- [ ] 已对照 `plan.md` §3、§7、§19
- [ ] 已确认 `build-parse-queue`、`parse` 保持 placeholder（plan §5.3）
- [ ] 已确认 Parser Router 输出为 route decision + `future_parser_hint`，不是 parsed content
- [ ] 已确认 `future_parser_hint` 仅为后续 005/006 提示；004 不 import/调用/subprocess/网络访问任何解析器（plan §6.5）

---

## T003 确认 004 schema 策略：不改 SQL schema

### 目标

确认 004 MVP 不修改 SQL、不新增 route 表、不 migration、不持久化 route decision 到 DB。

### 允许修改范围

- 无代码；本 task 勾选

### 禁止事项

- **禁止**修改 `sql/001_init_schema_v1_1.sql`
- **禁止**新增 `sql/migrations/**`
- **禁止** upsert `kb_parse_job`、update `kb_file_content.parse_status`
- 若实现发现必须写 DB → **STOP → TL**

### 验收标准

- [ ] 已对照 `plan.md` §14 全文
- [ ] 书面确认：004 MVP 无 schema 变更、无 DB 写
- [ ] 已确认仅输出 `parser_route_report_{UTC}.json`

---

## T004 实现 route_type 枚举和 routing rule

### 目标

新增 `RouteType` 枚举与 `match_route_type()` 规则引擎；规则仅基于 §9 所列元数据，不读 bin。

### 允许修改范围

- `backend/app/core/parser_routing.py`（新增）

### 禁止事项

- 不读 `original.bin` 或 vault sidecar 内容
- 不改 `config/parser_rules.yaml`
- 不对 `.pdf` 赋 `PDF_SCANNED_OR_IMAGE`（plan §23 Q3）
- 不调用外部解析器

### 验收标准

- [ ] `RouteType` 含：DOCX、PPTX、XLSX、PDF_DIGITAL、PDF_SCANNED_OR_IMAGE、IMAGE、TEXT_OR_MARKDOWN、UNKNOWN、UNSUPPORTED
- [ ] `future_parser_hint` 仅取：`MARKITDOWN_FAMILY` | `MINERU_FAMILY` | `DIRECT_TEXT` | `NONE`（plan §6.4–§6.5）
- [ ] 规则表与 `plan.md` §9.2 一致；hint 映射与 §6.4 一致
- [ ] 同 ext/mime 输入 → 稳定输出（单元可测）
- [ ] `ext_from_path` / fallback 逻辑可测

---

## T005 实现 Parser Router service

### 目标

新增 `ParserRouterService` 与 `ParserRouteResult`，实现批处理入口 `route_parsers()`：只读 MySQL → 调用 routing rule → 汇总 decisions/errors。

### 允许修改范围

- `backend/app/services/parser_router.py`（新增）
- `backend/app/core/parser_routing.py`（若 T004 需微调）

### 禁止事项

- 不改 001/002/003 service
- 不写 MySQL
- 不 touch 原始文件 / raw_vault 磁盘
- 单条失败必须 continue

### 验收标准

- [ ] Service 可实例化并连接 MySQL
- [ ] 候选条件：`vault_status=COPIED`、`status=CONTENT_REGISTERED`、`sha256 IS NOT NULL`
- [ ] 返回 `ParserRouteResult` 汇总结构
- [ ] 调用 `ensure_readonly()` 由 CLI 或 service 入口保证
- [ ] 单 content 失败记入 `errors`，不中断批处理

---

## T006 实现 parser_route_report.json

### 目标

写入 `reports_root/parser_route_report_{UTC}.json`，结构符合 `plan.md` §11。

### 允许修改范围

- `backend/app/services/parser_router.py`

### 禁止事项

- 不写 parsed / curated / quarantine / raw_vault
- 报告不得包含可执行解析 shell 作为默认行为
- 不覆盖旧报告（新 timestamp 文件）

### 验收标准

- [ ] JSON 含 `report_type`、`summary`、`decisions[]`、`errors[]`
- [ ] 每条 decision 含 content_uid、sha256、vault_path、file_ext、route_type、decision、reason、`future_parser_hint`（§6.5 四值之一）
- [ ] 报告字段名使用 `future_parser_hint`，**不得**使用 `suggested_parser`
- [ ] UTC 文件名格式与 001/003 对齐
- [ ] `routing_rules_version` 或等价 metadata 可追踪（可选常量）

---

## T007 实现 CLI 命令

### 目标

在 `cli/main.py` 新增 **`route-parsers`**，支持 `--config`、`--sha256`、`--content-uid`、`--limit`。

### 允许修改范围

- `backend/app/cli/main.py`

### 禁止事项

- 不修改 `scan`、`copy-to-vault`、`govern-duplicates` 行为
- 不把 MVP 逻辑塞进 `build-parse-queue` / `parse` placeholder
- 不实现 `--dry-run`（plan §23 Q1 周边）

### 验收标准

- [ ] `python -m app.cli.main route-parsers` 可运行
- [ ] Rich 输出 Candidates / Routed / Errors 等（plan §5.2）
- [ ] 打印 `Parser route report:` 路径
- [ ] `ensure_readonly()` 在入口调用

---

## T008 实现 pytest 单元测试

### 目标

新增 `test_parser_router.py`，覆盖 route_type 规则、UNKNOWN/UNSUPPORTED、中文路径、单条错误 continue。

### 允许修改范围

- `backend/tests/test_parser_router.py`（新增）

### 禁止事项

- 不要求外部网络
- 不修改用户真实原始目录
- 业务 service 不得 DELETE 原始数据

### 验收标准

- [ ] 覆盖 `plan.md` §20.1 所列用例（≥10 functions）
- [ ] `.txt` fixture → `TEXT_OR_MARKDOWN`，`future_parser_hint=DIRECT_TEXT`
- [ ] `.doc` → `UNSUPPORTED`；缺 ext → `UNKNOWN`
- [ ] `pytest -q tests/test_parser_router.py` 通过

---

## T009 实现 CLI E2E 测试

### 目标

pytest 集成用例验证 scan → copy-to-vault → route-parsers 全链路。

### 允许修改范围

- `backend/tests/test_parser_router.py`

### 禁止事项

- 不要求外部网络
- vault / reports 必须在 `tmp_path` 或测试隔离配置

### 验收标准

- [ ] `test_route_project_fixtures_integration`（或等价）通过
- [ ] CLI E2E：Routed ≥ 1、Errors = 0
- [ ] `parser_route_report_*.json` 存在于测试 reports_root

---

## T010 验证原始文件保护

### 目标

测试 route 前后原始 fixture 文件 mtime / 内容 hash 不变。

### 允许修改范围

- `backend/tests/test_parser_router.py`

### 禁止事项

- 不 delete/rename fixture 源文件
- 仅 pytest helper / teardown 可清理测试行（plan §23 Q6）

### 验收标准

- [ ] `test_original_files_unchanged` 通过
- [ ] 与 001/002/003 测试断言风格一致

---

## T011 验证 raw_vault 保护

### 目标

route 前后 `original.bin` 及 vault 目录 listing 不变；service 不读 bin 做路由。

### 允许修改范围

- `backend/tests/test_parser_router.py`

### 禁止事项

- 测试中 vault 必须在 `tmp_path`
- 不 open `original.bin` 做 magic-byte 路由

### 验收标准

- [ ] `test_raw_vault_unchanged` 通过
- [ ] bin sha256 与 route 前一致

---

## T012 验证幂等性

### 目标

连续两次 `route-parsers`（或两次 service 调用）对同 content 产生稳定 route decision。

### 允许修改范围

- `backend/tests/test_parser_router.py`

### 验收标准

- [ ] `test_route_idempotent` 通过
- [ ] 两次 decisions 中 route_type、rule_name、reason 一致
- [ ] 无 MySQL 写操作（无重复主记录）

---

## T013 验收与 Handoff

### 目标

Dev 完成后 STOP；由 **DB Agent** 审查；**E2E QA** 执行 A001–A012；**Handoff** 写交接文档。

### Handoff 文档（HO 撰写，Dev 不写）

```text
docs/handoff-phase1-004-parser-router.md
```

### 允许修改范围

- Dev：`specs/004-parser-router/tasks.md` 勾选 T001–T012
- QA / HO / DB：按角色权限

### 禁止事项

- Dev **不得**自我宣布验收通过
- Dev **不得**写 `docs/handoff-*.md`
- Dev **不得** merge main

### 验收标准

- [ ] Dev 已输出：修改文件清单、pytest 命令、CLI 命令、遗留问题
- [ ] 全链路：`pytest -q tests/test_inventory_scanner.py tests/test_file_content_vault.py tests/test_duplicate_governance.py tests/test_parser_router.py` 通过
- [ ] STOP → **DB Agent** → **E2E QA** → **Handoff Agent** → **TL Final Review**

---

## 任务进度总览

| Task | 说明 | 状态 |
|------|------|------|
| T001 | 阅读 001/002/003 | [ ] |
| T002 | 确认不解析/不接 parser | [ ] |
| T003 | 确认 schema 策略 | [ ] |
| T004 | route_type + routing rule | [ ] |
| T005 | Parser Router service | [ ] |
| T006 | parser_route_report | [ ] |
| T007 | CLI route-parsers | [ ] |
| T008 | pytest 单元 | [ ] |
| T009 | CLI E2E | [ ] |
| T010 | 原始文件保护 | [ ] |
| T011 | raw_vault 保护 | [ ] |
| T012 | 幂等性 | [ ] |
| T013 | 验收与 Handoff | [ ] |

---

**Tasks 结束** — Dev Agent 从 T001 开始，严格在白名单内实现。

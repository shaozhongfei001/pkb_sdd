# 阶段交接文档：Phase 1 — 004-parser-router（解析路由决策）

> **项目**：个人历史项目文档知识库 `pkb_sdd`  
> **版本基线**：V1.1-SDD  
> **交接日期**：2026-06-15  
> **项目路径**：`/home/szf/dev/pyws/pkb_sdd`  
> **编写角色**：Handoff Agent（`HO`）  
> **当前 Spec**：`specs/004-parser-router`  
> **前置文档**：`docs/handoff-phase1-003-duplicate-governance.md`

---

## 1. Executive Summary

**004-parser-router** MVP 已完成实现、DB Implementation Review 与 E2E QA 验收，当前处于 **Handoff → Tech Lead Final Review** 阶段。

**Phase 1 文件治理底座进度**：

```text
001-file-inventory       ✅ 已完成
002-file-content-vault   ✅ 已完成
003-duplicate-governance ✅ 已完成并 merge main
004-parser-router        ✅ 实现 + DB/QA PASS_WITH_NOTES（待 TL Final Review / merge main）
005/006 解析执行         ⬜ 未开始
```

**本 Spec 交付物**：

- 轻量级 **Parser Router**：纯规则、纯 MySQL 元数据、**无解析执行**
- 基于 `file_ext` / `mime_type` / instance fallback 产出 `route_type` + `future_parser_hint`
- JSON 报告：`parser_route_report_{UTC}.json`（**唯一**磁盘产物）
- CLI：`route-parsers`
- pytest：004 新增 19 个用例；全链路回归 **42 passed**

**审查结论**：

| 角色 | 结论 |
|------|------|
| DB & Data Agent（Implementation Review） | `PASS_WITH_NOTES`，无阻断项，不要求 Dev 修复 |
| E2E QA Agent | `PASS_WITH_NOTES`，无阻断项，不要求 Dev 修复 |

**004 MVP 未修改 SQL schema**；不读取 `original.bin`；不调用 MinerU / MarkItDown；不写 `parsed/` / `curated/` / `quarantine/`。

---

## 2. 当前分支与 commit 记录

| 项 | 值 |
|----|-----|
| **当前分支** | `feature/004-parser-router` |
| **是否已 merge main** | 否（待 TL Final Review） |
| **工作区状态** | 干净（Handoff 提交前） |

**004 相关 commits（按时间顺序）**：

```text
531318e spec(004): add parser router plan
ee71fe7 spec(004): align parser router supporting docs
0797621 feat(004): implement parser router
```

**分支 HEAD（实现）**：`0797621 feat(004): implement parser router`

---

## 3. 004 目标回顾

004 在 **原始文件只读、raw_vault 只读引用** 前提下，对每个 **已入 vault 的唯一内容** 生成 **未来应使用哪类解析器** 的路由决策，供 005-markitdown-parser、006-mineru-parser 后续消费。**004 不执行真实解析。**

1. 建立轻量级 Parser Router：纯规则、纯元数据、无解析执行
2. 基于 `kb_file_content` 与 `kb_raw_vault_object` 元数据生成 route decision
3. 路由对象是 content / vault object；原始路径仅作 fallback 扩展名参考
4. 输出 `parser_route_report_{UTC}.json` 到 `reports_root`
5. 提供 Typer CLI **`route-parsers`**
6. 保持幂等；单 content 失败不中断批处理

**Parser Router 只做「路由决策」，不做「解析执行」。**

**Parser Router 的输出是 route decision，不是 parsed content。**

**数据流**：

```text
001 scan → 002 copy-to-vault → 003 govern-duplicates（可选）→ 004 route-parsers
  kb_file_content（vault_status=COPIED）
    + kb_raw_vault_object（只读引用 vault_path）
    → route decision（内存 / JSON 报告）
    → reports_root/parser_route_report_{UTC}.json
```

---

## 4. 004 非目标与禁止事项

| 非目标 / 禁止 | 说明 |
|---------------|------|
| 真实解析 / OCR / 文本抽取 | 属于 005/006/007 |
| 调用 MinerU / MarkItDown | 属于 005/006 |
| 写入 `parsed/` | 属于 005/006 |
| 写入 `curated/` | 属于 010+ |
| 写入 `quarantine/` | 不属于 004 |
| 向量库 / embedding | 属于 011+ |
| Streamlit / 前端 | 属于 012+ |
| 项目卡蒸馏 | 属于 010+ |
| 源代码知识库分析 | 全局禁止 |
| 读取 `original.bin` 内容 | 004 禁止（含 magic-byte、OCR） |
| 打开 raw_vault sidecar JSON 内容 | 仅允许从 DB 列拷贝路径字符串 |
| 持久化 route decision 到 MySQL | 004 MVP 不做 |
| upsert `kb_parse_job` / 更新 `parse_status` | 004 MVP 不做 |
| SQL schema 变更 / 新增 route 表 | 004 MVP 无 migration |
| 修改 `inventory_scanner.py` / `file_content_vault.py` / `duplicate_governance.py` | 001–003 已封闭 |
| `--dry-run` | Plan §23 Q2：MVP 不实现 |

---

## 5. 本次实现文件清单

| 操作 | 文件 | 说明 |
|------|------|------|
| **新增** | `backend/app/core/parser_routing.py` | `RouteType`、`FutureParserHint`、`match_route_type()`、规则常量 |
| **新增** | `backend/app/services/parser_router.py` | `ParserRouterService`、`ParserRouteDecision`、`ParserRouteResult`、报告输出 |
| **修改** | `backend/app/cli/main.py` | 新增 `route-parsers` 命令 |
| **新增** | `backend/tests/test_parser_router.py` | 19 个 pytest 用例 |
| **修改** | `specs/004-parser-router/tasks.md` | T001–T012 勾选；T013 Handoff 完成 |

**未修改（封闭）**：

- `backend/app/services/inventory_scanner.py`
- `backend/app/services/file_content_vault.py`
- `backend/app/services/duplicate_governance.py`
- `backend/app/models/file.py`、`vault.py`、`duplicate.py`
- `sql/**`（无 migration）

---

## 6. 核心能力说明

### 6.1 候选 content 选取

默认条件（只读 MySQL）：

```text
kb_file_content.sha256 IS NOT NULL
AND kb_file_content.status = 'CONTENT_REGISTERED'
AND kb_file_content.vault_status = 'COPIED'
```

可选 CLI 过滤：`--sha256`、`--content-uid`、`--limit`。

### 6.2 路由决策流程

1. 查询候选 `kb_file_content`
2. 只读 join `kb_raw_vault_object` 补全 `vault_path` / `vault_uid`
3. 若 `file_ext` 为空，从 master instance 或首个 DISCOVERED instance 的 `file_name` / `source_path` fallback 扩展名
4. 调用 `match_route_type()` → `ParserRouteDecision`
5. 单条异常 → `errors[]`；continue
6. 全部完成后写 `parser_route_report_{UTC}.json`

### 6.3 批处理汇总

| 字段 | 含义 |
|------|------|
| `candidates` | 候选 content 数 |
| `routed` | `decision=ROUTE` 数 |
| `skipped` | MVP 恒为 0（见 NOTE-1） |
| `unknown` | `decision=UNKNOWN` 数 |
| `unsupported` | `decision=UNSUPPORTED` 数 |
| `errors` | 单条失败列表 |

### 6.4 与 005/006 边界

004 产出 `route_type` + `future_parser_hint` + JSON 报告；**不在 004 写 `parsed/`、不调用第三方解析器**。`build-parse-queue`、`parse` 保持 placeholder。

---

## 7. Parser Router 路由规则说明

规则内嵌于 `backend/app/core/parser_routing.py`（`ROUTING_RULES_VERSION = "004_mvp_v1"`）。

**主依据**：`kb_file_content.file_ext`（小写、含点）  
**辅助**：`kb_file_content.mime_type`（tie-break / 冲突检测）  
**Fallback**：`file_ext` 为空时从 instance 路径提取扩展名

### 7.1 路由规则摘要

| 匹配条件（`file_ext`） | `route_type` | `future_parser_hint` | `rule_name` |
|------------------------|--------------|----------------------|-------------|
| `.docx` | DOCX | MARKITDOWN_FAMILY | ext_docx |
| `.pptx` | PPTX | MARKITDOWN_FAMILY | ext_pptx |
| `.xlsx` | XLSX | MARKITDOWN_FAMILY | ext_xlsx |
| `.pdf` | PDF_DIGITAL | MINERU_FAMILY | ext_pdf_digital |
| 图片 ext（`.png` `.jpg` `.jpeg` `.tiff` `.bmp` `.gif` `.webp` 等） | IMAGE | MINERU_FAMILY | ext_image |
| `.txt` `.md` `.markdown` `.csv` | TEXT_OR_MARKDOWN | DIRECT_TEXT | ext_text |
| `.html` `.htm` `.xml` `.json` | TEXT_OR_MARKDOWN | DIRECT_TEXT | ext_markup_json |
| legacy office（`.doc` `.ppt` `.xls`） | UNSUPPORTED | NONE | ext_legacy_office |
| 其他 ODF/RTF（`.rtf` `.odt` `.ods` `.odp`） | UNSUPPORTED | NONE | ext_other_office |
| 扩展名缺失且 fallback 失败 | UNKNOWN | NONE | ext_missing |
| 在 001 白名单内但无规则 | UNKNOWN | NONE | ext_unknown |
| 未识别扩展名 | UNKNOWN | NONE | ext_unrecognized |
| `.pdf` + `mime_type` 以 `image/` 开头 | UNKNOWN | NONE | ext_mime_conflict |

**特殊说明**：

- `PDF_SCANNED_OR_IMAGE` 枚举已保留，**004 MVP 不自动赋值**（不读 PDF 内容判断扫描件）
- 所有 `.pdf`（无 mime 冲突）→ `PDF_DIGITAL`
- 规则确定性：同 metadata → 同 `route_type` / `rule_name` / `reason`

---

## 8. future_parser_hint 说明

**命名**：统一使用 **`future_parser_hint`**，**不得**使用 `suggested_parser`（易被误解为 004 正在调用解析器）。

**允许取值**：

| 值 | 含义 |
|----|------|
| `MARKITDOWN_FAMILY` | 后续 005 类 MarkItDown 路线（Office/HTML 等） |
| `MINERU_FAMILY` | 后续 006 类 MinerU 路线（PDF/图片等） |
| `DIRECT_TEXT` | 后续轻量文本路线（TXT/MD/CSV 等） |
| `NONE` | 无后续解析提示（UNKNOWN / UNSUPPORTED） |

**硬性约束**：

```text
future_parser_hint 仅是后续 005/006 的路由提示，
不代表 004 import、调用、subprocess、网络访问或执行任何解析器。
```

- 004 **不得**因 hint 值而加载 MinerU / MarkItDown 模块或 CLI
- hint 仅为 JSON 报告中的 **静态标签**，由 routing rule 映射产生
- 005/006 自行决定是否消费该 hint

---

## 9. CLI 使用方式

### 9.1 命令

```bash
cd /home/szf/dev/pyws/pkb_sdd/backend
source .venv/bin/activate

python -m app.cli.main route-parsers [--config PATH] [--sha256 HEX] [--content-uid UID] [--limit N]
```

### 9.2 选项

| 选项 | 说明 |
|------|------|
| `--config PATH` | 默认 `config/app.yaml` |
| `--sha256 HEX` | 仅处理指定内容 sha256 |
| `--content-uid UID` | 同 `--sha256`（001 中 `content_uid = sha256`） |
| `--limit N` | 最多处理 N 个候选 content |

### 9.3 全链路 E2E（fixtures）

```bash
python -m app.cli.main scan --path backend/tests/fixtures
python -m app.cli.main copy-to-vault
python -m app.cli.main route-parsers
```

**预期 Rich 汇总**：

```text
Candidates: N
Routed: N
Skipped: 0
Unknown: N
Unsupported: N
Errors: N
Parser route report: {reports_root}/parser_route_report_{UTC}.json
```

### 9.4 保留命令

- `scan`、`copy-to-vault`、`govern-duplicates` 行为不变
- `build-parse-queue`、`parse` 仍为 placeholder

---

## 10. 数据库与 schema 结论

**004 MVP 未修改 SQL schema。**

- **未新增 ORM**
- **未新增 migration**
- **未新增 route 表**
- **未持久化 route decision 到数据库**
- **未写 `kb_parse_job`**
- **未更新 `kb_file_content.parse_status`**

| 表 | 004 操作 |
|----|----------|
| `kb_file_content` | **只读**（`parse_status` 仅透传到报告） |
| `kb_raw_vault_object` | **只读** |
| `kb_file_instance` | **只读**（ext fallback） |
| `kb_parse_job` | **不读写** |
| `kb_document` | **不读写** |

MySQL **无任何写操作** → 无重复主记录风险。

---

## 11. 报告输出说明

报告目录：`{storage.reports_root}/`（来自 `config/app.yaml`）

| 文件 | 说明 |
|------|------|
| `parser_route_report_{UTC}.json` | **004 MVP 唯一磁盘产物** |

**JSON 结构要点**：

- `report_type`: `parser_route_report`
- `routing_rules_version`: `004_mvp_v1`
- `summary`: candidates / routed / skipped / unknown / unsupported / errors
- `decisions[]`: 每条含 content_uid、sha256、vault_path、file_ext、mime_type、route_type、decision、rule_name、reason、**future_parser_hint**、parse_status
- `errors[]`: sha256 + message

**规则**：

- UTC 时间戳格式与 001/003 对齐（`%Y%m%dT%H%M%SZ`）
- 每次运行 **新 timestamp 文件**，不覆盖旧报告
- 不写入 `parsed/`、`curated/`、`quarantine/`、`raw_vault/`

---

## 12. 测试与验收结果

### 12.1 pytest 命令

```bash
cd /home/szf/dev/pyws/pkb_sdd/backend
source .venv/bin/activate

# 004 专项
pytest -q tests/test_parser_router.py

# 全链路回归（001 + 002 + 003 + 004）
pytest -q tests/test_inventory_scanner.py tests/test_file_content_vault.py tests/test_duplicate_governance.py tests/test_parser_router.py
```

### 12.2 测试结果

```text
42 passed in 6.66s
```

| 模块 | 用例数 |
|------|--------|
| `test_inventory_scanner.py` | 7 |
| `test_file_content_vault.py` | 7 |
| `test_duplicate_governance.py` | 9 |
| `test_parser_router.py` | 19 |

### 12.3 004 关键用例

| 类别 | 用例 |
|------|------|
| 纯规则单测 | `test_match_route_*`（txt/pdf/image/office/legacy/unknown/mime 冲突） |
| 集成 | `test_route_project_fixtures_integration` |
| CLI 过滤 | `test_route_sha256_filter`、`test_route_content_uid_filter`、`test_route_limit` |
| 边界 | `test_route_sha256_not_copied_empty_candidates` |
| 幂等 | `test_route_idempotent` |
| 异常 | `test_route_single_error_continues` |
| 保护 | `test_original_files_unchanged`、`test_raw_vault_unchanged`、`test_no_parsed_curated_quarantine_writes` |
| CLI smoke | `test_cli_route_parsers_help` |

### 12.4 Acceptance A001–A012

| 编号 | 标准 | 结论 |
|------|------|------|
| **A001** 范围符合 | 只做路由决策，不执行解析 | ✅ PASS |
| **A002** 原始文件保护 | 不 delete/move/rename/overwrite | ✅ PASS |
| **A003** raw_vault 保护 | 不 delete/overwrite/move vault | ✅ PASS |
| **A004** 不写 parsed/curated | 磁盘无 parsed/curated/quarantine 新增 | ✅ PASS |
| **A005** 不接 MinerU/MarkItDown | 无 import/subprocess；`future_parser_hint` 为静态标签 | ✅ PASS |
| **A006** 不做 OCR/不读 bin | 不读 original.bin 内容 | ✅ PASS |
| **A007** 不做向量库/项目卡蒸馏 | 无 embedding/curated | ✅ PASS |
| **A008** 幂等性 | 同 metadata 稳定 route decision | ✅ PASS |
| **A009** 异常可恢复 | 单 content 失败不中断 | ✅ PASS |
| **A010** 报告可追溯 | JSON 字段齐全含 `future_parser_hint` | ✅ PASS |
| **A011** SQL schema 边界 | 无 migration、无 ORM 写库 | ✅ PASS |
| **A012** 测试通过 | pytest + CLI E2E | ✅ PASS（42 passed） |

---

## 13. DB & Data Agent Implementation Review 结论

**结论**：`PASS_WITH_NOTES`，无阻断项，不要求 Dev 修复。

审查范围：ORM/service 无 DB 写操作、与 init SQL 无 schema 漂移、无 upsert `kb_parse_job`、无 update `parse_status`、无 route 表、候选查询条件与 Plan §4.1 一致。

---

## 14. E2E QA Agent Review 结论

**结论**：`PASS_WITH_NOTES`，无阻断项，不要求 Dev 修复。

审查范围：pytest 全链路、CLI E2E（scan → copy-to-vault → route-parsers）、Acceptance A001–A012、原始文件只读、raw_vault 不变、无 parsed/curated 写入、无 MinerU/MarkItDown 调用。

---

## 15. 已知 notes / 非阻断事项

以下 notes **不要求 Dev 修复**，可作为后续增强或文档备忘：

| ID | 说明 |
|----|------|
| **NOTE-1** | `skipped` 计数恒为 0，符合 Plan §23 Q5 的 MVP 简化 |
| **NOTE-2** | `.html/.htm/.xml/.json` 规则已实现，但可后续补独立单测 |
| **NOTE-3** | `--sha256` 指向不存在 sha256 的行为为 `candidates=0`、exit 0，可后续补 CLI 专项测试 |
| **NOTE-4** | 报告使用 `future_parser_hint`，未使用 `suggested_parser` |

---

## 16. 原始文件保护结论

- 004 **不 open 原始文件进行 write**；不调用 `shutil.move` / `unlink` / `rename`
- 仅通过 MySQL **只读** `source_path` / `file_name`（fallback ext）；**不读文件内容**
- CLI 入口通过 `ensure_readonly()` 保证 `original_files_readonly: true`
- `test_original_files_unchanged` 验证 route 前后 stat + content hash 不变

**安全结论**：

```text
不删除、不移动、不重命名原始文件。
```

---

## 17. raw_vault 保护结论

- 004 **只读** `kb_file_content.vault_path`、`kb_raw_vault_object`；报告引用路径字符串
- **不** create / delete / overwrite `raw_vault/**` 下任何文件
- **不**读取 `original.bin` 做 magic-byte 或 OCR
- **不** open raw_vault sidecar JSON 内容
- `test_raw_vault_unchanged` 验证 `original.bin` hash 与目录 listing 在 route 前后不变

**安全结论**：

```text
不删除、不覆盖、不移动 raw_vault 文件。
不读取 original.bin。
不 open raw_vault sidecar JSON。
```

---

## 18. parsed / curated / quarantine 保护结论

- 004 **唯一**磁盘产物为 `{reports_root}/parser_route_report_{UTC}.json`
- **不**写入 `parsed/`、`curated/`、`quarantine/`
- `test_no_parsed_curated_quarantine_writes` 验证 route 前后三目录 listing 不变

**安全结论**：

```text
不写 parsed / curated / quarantine。
不调用 MinerU / MarkItDown。
不执行真实解析。
不做 OCR / 文本抽取。
```

---

## 19. 幂等性结论

| 场景 | 行为 |
|------|------|
| 重复执行 `route-parsers` | 同 content metadata → 同 `route_type` / `rule_name` / `reason` |
| `skipped` 计数 | MVP 恒为 0（NOTE-1） |
| 报告文件 | 每次运行新 timestamp 文件，不覆盖 |
| MySQL | **无写操作** → 无重复主记录风险 |
| 规则版本 | 报告含 `routing_rules_version: "004_mvp_v1"` |

`test_route_idempotent` 验证：两次 decisions 中 route_type、rule_name、reason 一致。

---

## 20. 当前未提交 / 不应提交内容

| 类别 | 说明 |
|------|------|
| **工作区** | Handoff 编写前：干净 |
| **`config/app.yaml`** | 本地配置，含 MySQL 密码，**勿提交** |
| **`.env`** | 若有，勿提交 |
| **`backend/.venv/`** | 本地 Python 环境，勿提交 |
| **`raw_vault/**`** | 002 真实产物，勿提交 |
| **`reports/**`** | 本地运行报告，通常勿提交 |
| **`parsed/**`、`curated/**`、`quarantine/**`** | 004 不应写入；若本地存在亦勿误提交 |
| **pytest 临时数据** | `tmp_path` 与测试 DB 行由 helper 清理 |

Handoff 文档本身待 commit：

```text
docs/handoff-phase1-004-parser-router.md
specs/004-parser-router/tasks.md  （T013 勾选）
```

---

## 21. 下一阶段入口条件

**004 merge main 前（TL Final Review checklist）**：

- [ ] TL 阅读本 handoff、`plan.md`、`tasks.md`（T001–T013 全部 `[x]`）
- [ ] 确认 DB Implementation Review `PASS_WITH_NOTES` 无阻断项
- [ ] 确认 E2E QA `PASS_WITH_NOTES` 无阻断项
- [ ] 复核全链路 pytest：`42 passed`
- [ ] 确认未修改 SQL schema、未 touch 001–003 封闭 service
- [ ] 确认无 MinerU/MarkItDown 调用、无 parsed 写入
- [ ] 确认分支 `feature/004-parser-router` commits 完整（plan + docs + feat + handoff）
- [ ] merge 到 `main` 后记录 merge commit

**进入 005/006 Spec 前**：

- [ ] 004 已 merge `main`
- [ ] 新 feature 分支基于 `main` HEAD 创建（如 `feature/005-markitdown-parser`）
- [ ] TL 完成下一 Spec 的 `plan.md` / `tasks.md` 与 Dev 白名单
- [ ] 已读最新 `docs/handoff-phase1-004-parser-router.md`
- [ ] 005/006 可消费 `parser_route_report_*.json` 中的 `route_type` 与 `future_parser_hint`

---

## 22. 下一阶段禁止事项

继承 `docs/agent_collaboration_standard.md` §9 全局硬约束；**004 完成后仍禁止在 004 分支「顺便实现」**：

```text
真实解析
MinerU 调用
MarkItDown 调用
parsed 写入
curated 写入
Streamlit
向量库
项目卡蒸馏
源代码知识库
```

**005/006 才允许**：在各自 Spec 授权范围内调用对应解析器并写 `parsed/`。

额外提醒：

- 不自动删除重复文件
- 不删除 raw_vault 文件
- 不修改 SQL schema（除非目标 Spec 授权 + migration）
- 不修改 001–003 封闭 service（除非 TL 明确解封）

---

## 23. 给新 ChatGPT / Cursor 会话的接手提示

### 23.1 会话启动模板

```text
当前角色：<TL|DEV|DB|QA|HO>
当前 Spec：specs/004-parser-router（或 005/006）
当前分支：feature/004-parser-router（或 main，若已 merge）
当前步骤：⑥ TL Final Review / 或 005 Plan
TL 批准的文件白名单：（DEV 必填）
禁止修改：001–003 封闭 service、sql/**、raw_vault 真实产物、原始用户文件
```

### 23.2 必读文档（按顺序）

1. `docs/handoff-phase1-004-parser-router.md`（本文）
2. `docs/agent_collaboration_standard.md`
3. `specs/004-parser-router/plan.md`（含 §23 TL 决策）
4. 若进入 005/006：对应 Spec 五件套 + 最新 handoff

### 23.3 快速命令

```bash
cd /home/szf/dev/pyws/pkb_sdd/backend
source .venv/bin/activate

# 全链路回归
pytest -q tests/test_inventory_scanner.py tests/test_file_content_vault.py tests/test_duplicate_governance.py tests/test_parser_router.py

# CLI 全链路
python -m app.cli.main scan --path backend/tests/fixtures
python -m app.cli.main copy-to-vault
python -m app.cli.main route-parsers
```

### 23.4 交接确认清单

- [ ] 已读本文 Executive Summary 与 commit 记录
- [ ] 已知 004 实现文件清单与 CLI 用法
- [ ] 已知 schema 未变更、无 DB 写、无 migration
- [ ] 已知 `future_parser_hint` 仅为静态标签，不代表 004 调用解析器
- [ ] 已知 DB/QA 均为 `PASS_WITH_NOTES`，notes 非阻断
- [ ] 已知 NOTE-1–NOTE-4 非阻断备忘
- [ ] 已知下一阶段禁止事项（真实解析 / MinerU / MarkItDown / parsed 等须在 005/006）
- [ ] 未在 handoff 阶段修改业务代码

---

**文档结束** — STOP → Tech Lead Final Review → merge main → 005/006 Spec Plan。

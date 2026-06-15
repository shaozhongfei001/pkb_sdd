# 阶段交接文档：Phase 1 — 005-markitdown-parser（MarkItDown 普通文档解析）

> **项目**：个人历史项目文档知识库 `pkb_sdd`  
> **版本基线**：V1.1-SDD  
> **交接日期**：2026-06-15  
> **项目路径**：`/home/szf/dev/pyws/pkb_sdd`  
> **编写角色**：Handoff Agent（`HO`）  
> **当前 Spec**：`specs/005-markitdown-parser`  
> **前置文档**：`docs/handoff-phase1-004-parser-router.md`

---

## 1. 005 基本信息

| 项 | 值 |
|----|-----|
| **Spec 名称** | `005-markitdown-parser` — MarkItDown-family 轻量文档解析 |
| **当前分支** | `feature/005-markitdown-parser-adapter` |
| **当前阶段** | **P8 Handoff**（P5 Dev / P6 DB / P7 QA 已完成；待 P9 TL Final Review） |
| **是否已 merge main** | 否 |

**005 相关 commits（按时间顺序）**：

```text
0137914 spec(005): expand markitdown parser plan
57fe409 spec(005): align vault path decision
36aaf80 feat(005): implement markitdown parser
```

**关键实现 commit**：`36aaf80831e7544bd05384928d89472a617ce247` — `feat(005): implement markitdown parser`

**审查结论**：

| 角色 | 阶段 | 结论 |
|------|------|------|
| Tech Lead | P4 TL Gate | `APPROVED_FOR_P5` |
| Dev | P5 Implementation | 已完成 |
| DB & Data Agent | P6 Implementation Review | `PASS_WITH_NOTES`，无阻断项 |
| E2E QA Agent | P7 E2E 验收 | `PASS_WITH_NOTES`，无阻断项 |

**测试结果（Handoff 复核）**：

```bash
cd /home/szf/dev/pyws/pkb_sdd/backend
source .venv/bin/activate

# 005 专项
pytest -q tests/test_markitdown_parser.py
# 41 passed in ~6.5s

# 全链路回归（001 + 002 + 003 + 004 + 005）
pytest -q tests/test_inventory_scanner.py tests/test_file_content_vault.py \
  tests/test_duplicate_governance.py tests/test_parser_router.py \
  tests/test_markitdown_parser.py
# 83 passed in ~13s
```

| 模块 | 用例数 |
|------|--------|
| `test_inventory_scanner.py` | 7 |
| `test_file_content_vault.py` | 7 |
| `test_duplicate_governance.py` | 9 |
| `test_parser_router.py` | 19 |
| `test_markitdown_parser.py` | 41 |
| **合计** | **83** |

---

## 2. 005 目标摘要

005 是 Phase 1 **首个允许**调用 MarkItDown-family 解析器、读取 `raw_vault/original.bin`、写入 `parsed/` 的 Spec。

**核心目标**：

1. **MarkItDown-family 轻量文档解析**：对 Office / 文本 / markup 类文档执行 Markdown 转换。
2. **从 raw_vault/original.bin 生成 parsed 产物**：只读 vault 副本，不读用户原始路径。
3. **不写 DB**：MySQL 仅 SELECT；无 INSERT / UPDATE / DELETE。
4. **不改 SQL schema**：无 migration、无 init SQL 修改。

**Phase 1 进度**：

```text
001-file-inventory       ✅ 已完成
002-file-content-vault   ✅ 已完成
003-duplicate-governance ✅ 已完成
004-parser-router        ✅ 已完成
005-markitdown-parser    ✅ 实现 + DB/QA PASS_WITH_NOTES（待 TL Final Review / merge main）
006-mineru-parser        ⬜ 未开始
```

**数据流**：

```text
001 scan → 002 copy-to-vault → 003 govern-duplicates（可选）→ 004 route-parsers（可选）
  → 005 parse-markitdown
    MySQL 只读（kb_file_content + kb_raw_vault_object [+ kb_file_instance fallback]）
    → match_route_type() 筛选 DOCX|PPTX|XLSX|TEXT_OR_MARKDOWN
    → 只读 open raw_vault/.../original.bin
    → MarkItDownAdapter.convert()
    → parsed/by_hash/.../parsed_text.md + parsed_metadata.json + parse_manifest.json
    → reports_root/parse_markitdown_report_{UTC}.json
```

---

## 3. 005 实现范围

| `route_type` | 005 行为 | 典型扩展名 |
|--------------|----------|------------|
| **DOCX** | 解析 | `.docx` |
| **PPTX** | 解析 | `.pptx` |
| **XLSX** | 解析 | `.xlsx` |
| **TEXT_OR_MARKDOWN** | 解析 | `.txt` `.md` `.csv` `.html` `.htm` `.xml` `.json` |

**交付物**：

- `MarkItDownAdapter` — 第三方 markitdown 薄包装
- `MarkItDownParserService` — 批处理编排、幂等、报告
- `parsed_paths.py` — parsed 三档路径 resolver
- CLI `parse-markitdown` — 含批处理护栏与 `--dry-run`
- `parse_markitdown_report_{UTC}.json` — 批处理报告
- pytest：005 新增 **41** 个用例（≥20 要求已满足）

---

## 4. 005 明确不覆盖

| 非目标 | 说明 | 归属 |
|--------|------|------|
| **PDF_DIGITAL** | 跳过 | 006-mineru-parser |
| **PDF_SCANNED_OR_IMAGE** | 跳过 | 006-mineru-parser |
| **IMAGE** | 跳过 | 006-mineru-parser |
| **UNKNOWN** | 跳过 | — |
| **UNSUPPORTED** | 跳过 | — |
| **MinerU** | 不 import / 不调用 | 006 |
| **OCR** | 不做 | 006 |
| **curated/** | 不写 | 010+ |
| **vector DB / embedding** | 不做 | 011+ |
| **project card distillation** | 不做 | 010+ |
| **Streamlit / 前端** | 不做 | 012+ |
| **kb_parse_job / kb_document / parse_status** | 不写 DB | 006-parse-job-registry（建议） |
| **SQL schema 变更** | 禁止 | 须单独 Spec + migration |
| **`--force-reparse`** | MVP 不实现 | — |

---

## 5. 新增或修改文件清单

| 操作 | 文件 | 说明 |
|------|------|------|
| **新增** | `backend/app/core/parsed_paths.py` | `build_parsed_content_dir()`、`build_parsed_artifact_paths()` — parsed 三档路径 |
| **新增** | `backend/app/adapters/markitdown_adapter.py` | `MarkItDownAdapter`、`AdapterResult`、错误分类常量 |
| **新增** | `backend/app/services/markitdown_parser.py` | `MarkItDownParserService`、报告/幂等/批处理编排 |
| **修改** | `backend/app/cli/main.py` | 新增 `parse-markitdown` 命令与护栏 |
| **新增** | `backend/tests/test_markitdown_parser.py` | 41 个 pytest 用例 |
| **修改** | `specs/005-markitdown-parser/tasks.md` | P5–P8 阶段勾选 |

**未修改（封闭 / 只读 import）**：

- `backend/app/core/vault_paths.py` — 只读 import `build_vault_dir` / `build_vault_artifact_paths`
- `backend/app/core/parser_routing.py` — 只读 import `match_route_type` / `RouteType`
- `backend/app/services/inventory_scanner.py`
- `backend/app/services/file_content_vault.py`
- `backend/app/services/duplicate_governance.py`
- `backend/app/services/parser_router.py`
- `backend/requirements.txt` — P5 未修改（markitdown 依赖已存在）
- `sql/**` — 无 migration

---

## 6. 核心设计说明

### 6.1 parsed path resolver（`parsed_paths.py`）

```text
{parsed_root}/by_hash/{sha256[0:2]}/{sha256[2:4]}/{sha256}/
  parsed_text.md
  parsed_metadata.json
  parse_manifest.json
```

- `build_parsed_content_dir(parsed_root, sha256)` — 三档 prefix（`[0:2]` + `[2:4]` + 完整 sha256）
- `build_parsed_artifact_paths(parsed_dir)` — 返回三文件路径 TypedDict
- **不**复用 `build_vault_dir()`（raw_vault 与 parsed 规则独立）

### 6.2 MarkItDownAdapter（`markitdown_adapter.py`）

分层边界：

```text
CLI (main.py)           — 不 import markitdown
  → MarkItDownParserService
    → MarkItDownAdapter   — 唯一 import markitdown 的层
      → third-party markitdown API
```

- `parser_name = "markitdown"`
- `parser_adapter_version = "005_mvp_v1"`
- `convert(input_path, route_type) → AdapterResult(text, metadata, warnings)`
- `check_import()` — CLI 非 dry-run 入口预检
- 运行时错误启发式分类：`CORRUPTED_DOCUMENT` / `PASSWORD_PROTECTED` / `PARSER_RUNTIME_ERROR`

### 6.3 MarkItDownParserService（`markitdown_parser.py`）

**候选查询**（MySQL 只读）：

```text
sha256 IS NOT NULL
AND status = 'CONTENT_REGISTERED'
AND vault_status = 'COPIED'
```

**处理流程**：

1. `_load_candidates()` — SELECT `kb_file_content`
2. 每条 content：join vault object、ext fallback → `match_route_type()`
3. out-of-scope → `status=SKIPPED`（不计入 `--limit`）
4. in-scope + 幂等 SUCCESS manifest → skip（`skip_reason=idempotent_success_manifest`）
5. in-scope + limit 达上限 → skip（`skip_reason=parse_limit_reached`）
6. dry-run → `dry_run_action=would_parse` / `would_skip`；不调用 adapter
7. 成功 → 写三文件；EMPTY 时 `status=EMPTY`
8. 失败 → 仅写 `parse_manifest.json`（`status=FAILED` + `error`）
9. 全部完成后写 `parse_markitdown_report_{UTC}.json`

**vault 路径解析**：

- `_resolve_vault_dir()` — 优先 DB `vault_path`，fallback `build_vault_dir(raw_vault_root, sha256)`
- `original_bin` — 始终经 `build_vault_artifact_paths(vault_dir)["original_bin"]`

### 6.4 parse-markitdown CLI（`main.py`）

- 入口 `ensure_readonly()`（service 构造时调用）
- 非 dry-run 时预检 `MarkItDownAdapter.check_import()`
- Rich 汇总：Candidates / In-scope / Parsed / Skipped / Failed / Empty / Dry run / Errors / report path
- `build-parse-queue`、`parse` 保持 placeholder

### 6.5 report JSON（`parse_markitdown_report_{UTC}.json`）

| 字段 | 说明 |
|------|------|
| `report_type` | `parse_markitdown_report` |
| `parser_adapter_version` | `005_mvp_v1` |
| `dry_run` | bool |
| `filters` | sha256 / content_uid / limit |
| `summary.total_candidates` | SQL 候选行数（route 过滤前） |
| `summary.in_scope_candidates` | route 过滤后 in-scope 数 |
| `summary.parsed_count` | SUCCESS |
| `summary.skipped_count` | SKIPPED（含 out-of-scope + 幂等 + limit） |
| `summary.failed_count` | FAILED |
| `summary.empty_count` | EMPTY |
| `items[]` | 每条含 content_uid、sha256、route_type、status、parsed_dir、skip_reason、**dry_run_action** |
| `errors[]` | FAILED 详情（content_uid、sha256、code、message） |

### 6.6 manifest / metadata / parsed_text 产物

**parse_manifest.json**（必填字段）：

- `content_uid`、`sha256`、`route_type`、`parser_name`、`parser_adapter_version`
- `source_vault_path`、`parsed_text_path`、`parsed_metadata_path`
- `generated_at`、`status`（SUCCESS / SKIPPED / FAILED / EMPTY）
- `content_size_bytes`、`input_metadata`（file_ext、mime_type、rule_name、vault_uid）
- SUCCESS/EMPTY：`output_size_bytes`、`output_hash`
- FAILED：`error.code` + `error.message`；**不写** parsed_text.md / parsed_metadata.json

**parsed_metadata.json**（SUCCESS/EMPTY 时）：

- `parser_name`、`parser_adapter_version`、`route_type`、`source_vault_path`
- `converted_at`、`library_version`、`warnings`、`extra`

**parsed_text.md**：

- UTF-8 Markdown / plain text
- EMPTY 时仍写文件（0 字节或空白）

---

## 7. 路径规则

### 7.1 raw_vault — 002 两档（权威）

```text
{raw_vault_root}/by_hash/{sha256[0:2].lower()}/{sha256}/original.bin
```

**必须**复用 002 helpers：

```python
vault_dir = build_vault_dir(config.storage.raw_vault_root, sha256)
original_bin = build_vault_artifact_paths(vault_dir)["original_bin"]
```

- service 内 `_resolve_vault_dir()` / `_resolve_original_bin()` 内部调用上述 helpers
- **禁止** raw_vault 三档 `{sha256[2:4]}/`
- **禁止**修改 `vault_paths.py` / `file_content_vault.py`

### 7.2 parsed — 005 三档（独立约定）

```text
{parsed_root}/by_hash/{sha256[0:2]}/{sha256[2:4]}/{sha256}/
```

- 由 `parsed_paths.py` 构建
- **不得**与 raw_vault 两档规则混用
- MVP **不使用** `parser_profile` 子目录；版本信息写入 manifest 字段

---

## 8. CLI 使用方式

### 8.1 命令

```bash
cd /home/szf/dev/pyws/pkb_sdd/backend
source .venv/bin/activate

python -m app.cli.main parse-markitdown [OPTIONS]
```

### 8.2 常用示例

```bash
# 批处理（最多 N 次 in-scope parse）
python -m app.cli.main parse-markitdown --limit N

# 单 content
python -m app.cli.main parse-markitdown --sha256 HEX
python -m app.cli.main parse-markitdown --content-uid UID

# 预览（不写 parsed、不调用 MarkItDown）
python -m app.cli.main parse-markitdown --limit N --dry-run
```

### 8.3 选项

| 选项 | 说明 |
|------|------|
| `--config PATH` | 默认 `config/app.yaml` |
| `--sha256 HEX` | 仅处理指定内容 |
| `--content-uid UID` | 同 `--sha256`（001 中 content_uid = sha256） |
| `--limit N` | 最多 N 次 **in-scope parse**；out-of-scope skip **不计入** |
| `--dry-run` | 不调用 MarkItDown；不写 parsed；仍写 report |

### 8.4 参数护栏

| 规则 | 行为 |
|------|------|
| 无 `--sha256` / `--content-uid` / `--limit` | **exit 1**，提示必须至少提供一个 |
| `--limit < 1` | exit 1 |
| `--limit > 100` | exit 1（`PARSE_MARKITDOWN_MAX_LIMIT = 100`） |
| `--limit` 语义 | 仅 in-scope parse 动作；PDF/IMAGE/UNKNOWN/UNSUPPORTED skip 不占额度 |
| limit 达上限 | 后续 in-scope item `skip_reason=parse_limit_reached` |

### 8.5 全链路 E2E（fixtures）

```bash
python -m app.cli.main scan --path backend/tests/fixtures
python -m app.cli.main copy-to-vault
python -m app.cli.main parse-markitdown --limit 10
```

**预期 Rich 汇总**：

```text
Candidates: N
In-scope candidates: N
Parsed: N
Skipped: N
Failed: N
Empty: N
Dry run: False
Errors: N
Parse markitdown report: {reports_root}/parse_markitdown_report_{UTC}.json
```

---

## 9. 幂等与错误处理

| 场景 | 行为 |
|------|------|
| **SUCCESS manifest skip** | `parse_manifest.json` 存在且 `status=SUCCESS` 且 `parser_adapter_version=005_mvp_v1` → skip，不覆盖三文件 |
| **FAILED / EMPTY / missing manifest 可重试** | 无 SUCCESS manifest → 允许重新 parse（覆盖 FAILED manifest） |
| **FAILED 产物** | 仅写 `parse_manifest.json`（FAILED + error）；**不写** parsed_text.md / parsed_metadata.json |
| **dry-run** | 不调用 MarkItDownAdapter.convert；不写 parsed；report 标注 `dry_run_action` |
| **单文件失败 continue** | 该条 FAILED + `errors[]`；批处理继续 |
| **全局 import 失败** | CLI exit 1；不 partially write parsed |
| **errors[] 语义** | 仅 FAILED 条目；含 content_uid、sha256、code、message |
| **items[] 语义** | 全部候选（SUCCESS / SKIPPED / FAILED / EMPTY）；SKIPPED 含 out-of-scope、幂等、limit |

**错误码**：

| code | 场景 |
|------|------|
| `MISSING_ORIGINAL_BIN` | vault bin 不存在 |
| `PARSER_IMPORT_ERROR` | markitdown import 失败 |
| `PARSER_RUNTIME_ERROR` | 未分类运行时错误 |
| `CORRUPTED_DOCUMENT` | 启发式：损坏文档 |
| `PASSWORD_PROTECTED` | 启发式：密码保护 |

---

## 10. DB / schema 边界

**005 MVP 未修改 SQL schema。**

| 表 | 005 操作 |
|----|----------|
| `kb_file_content` | **只读** SELECT |
| `kb_raw_vault_object` | **只读** SELECT |
| `kb_file_instance` | **只读** SELECT（ext fallback） |
| `kb_parse_job` | **不读写** |
| `kb_document` | **不读写** |

**硬性禁止**：

- 无 INSERT / UPDATE / DELETE
- 无 `session.add` / `commit` / `flush` / `delete`
- 不写 `kb_parse_job`
- 不写 `kb_document`
- 不更新 `parse_status`
- 无新增 migration
- 无新增 ORM model

**审查证据**：P6 grep + `test_no_db_write`；service 源码无写库路径。

---

## 11. P6 PASS_WITH_NOTES 摘要

**结论**：`PASS_WITH_NOTES`，无阻断项，不要求 Dev 修复。

| ID | Note | 说明 |
|----|------|------|
| **DB-NOTE-1** | Office 集成默认 mock | pytest 默认 mock `MarkItDownAdapter.convert`；不强制真实 docx/pptx/xlsx E2E |
| **DB-NOTE-2** | dry-run `would_parse` 使用 `dry_run_action` 字段 | item 级 `dry_run_action=would_parse` / `would_skip` 区分 dry-run 意图，而非复用 `status` |
| **DB-NOTE-3** | limit 达上限后 `parse_limit_reached` | in-scope 但超出 `--limit` 的条目 `skip_reason=parse_limit_reached` |
| **DB-NOTE-4** | corrupted/password 分类为启发式 | adapter 基于异常 message 正则匹配，非 Office 专用 API 判定 |

**审查范围确认**：

- 无 SQL / migration 变更
- 无 ORM 写库、无 parse_status 更新
- 无 kb_parse_job / kb_document 引用写路径
- 候选查询条件与 Plan §5.1 一致

---

## 12. P7 E2E QA 摘要

**结论**：`PASS_WITH_NOTES`，无阻断项，不要求 Dev 修复。

### 12.1 005 专项测试

```text
pytest -q tests/test_markitdown_parser.py
41 passed in ~6.5s
```

**关键用例类别**：

| 类别 | 代表用例 |
|------|----------|
| 路径规则 | `test_parsed_paths_three_level_structure`、`test_vault_original_bin_uses_two_level_vault_paths`、`test_no_raw_vault_three_level_hardcode_in_service_source` |
| in-scope 解析 | `test_parse_in_scope_success`（参数化 DOCX/PPTX/XLSX/TEXT） |
| out-of-scope skip | `test_skip_pdf`、`test_skip_image`、`test_skip_unknown`、`test_skip_unsupported_legacy_office` |
| 错误隔离 | `test_missing_original_bin`、`test_corrupted_document`、`test_password_protected_document`、`test_parser_runtime_failure` |
| CLI 护栏 | `test_cli_no_filter_rejected`、`test_cli_limit_over_max_rejected`、`test_cli_dry_run_no_parsed_and_no_adapter_call` |
| 幂等 | `test_idempotent_skip_success_manifest`、`test_failed_manifest_allows_retry` |
| 保护 | `test_no_db_write`、`test_raw_vault_unchanged`、`test_original_files_unchanged`、`test_no_curated_vector_project_card` |
| 集成 E2E | `test_parse_markitdown_integration`、`test_chinese_path_integration` |

### 12.2 全量测试

```text
83 passed in ~13s
```

001–004 回归无破坏（42 passed）+ 005 新增 41 passed。

### 12.3 Acceptance A001–A018 验收结论

| 编号 | 标准 | 结论 |
|------|------|------|
| **A001** | 只处理 MarkItDown-family 四 route_type | ✅ PASS |
| **A002** | 跳过 PDF / IMAGE / UNKNOWN / UNSUPPORTED | ✅ PASS |
| **A003** | parsed 产物三档路径正确 | ✅ PASS |
| **A004** | manifest 可追溯 | ✅ PASS |
| **A005** | raw_vault 不变；002 两档 | ✅ PASS |
| **A005b** | vault 路径经 002 helpers | ✅ PASS |
| **A006** | 原始文件不变 | ✅ PASS |
| **A007** | 不写 DB | ✅ PASS |
| **A008** | 不改 SQL schema | ✅ PASS |
| **A009** | 不写 curated / 向量库 / 项目卡 | ✅ PASS |
| **A010** | 不接 MinerU | ✅ PASS |
| **A011** | 不做 OCR | ✅ PASS |
| **A012** | parser error continue | ✅ PASS |
| **A013** | empty output 有明确状态 | ✅ PASS |
| **A014** | corrupted / password 有错误记录 | ✅ PASS |
| **A015** | CLI 护栏与 dry-run 可测 | ✅ PASS |
| **A016** | 幂等可测 | ✅ PASS |
| **A017** | 测试通过（≥20 functions） | ✅ PASS（41 functions） |
| **A018** | vault_paths / file_content_vault 未修改 | ✅ PASS |

### 12.4 阻断项

**无阻断项。** QA notes 与 P6 notes 一致（Office mock、dry_run_action、parse_limit_reached、启发式错误分类），均不要求 Dev 修复。

---

## 13. 后续 006 建议

| 建议 | 说明 |
|------|------|
| **parse-job registry 独立 Spec** | `kb_parse_job` / `kb_document` / `parse_status` 持久化 → 建议 **006-parse-job-registry** 或独立 Spec；005 manifest 设计便于未来 ingest |
| **parsed registry 不倒灌 005** | parse_status / kb_document 更新不应要求修改 005 已 merge 代码 |
| **MinerU / PDF / OCR 独立 Spec** | → **006-mineru-parser**；与 005 parsed 路径/manifest 可并存但 adapter 独立 |
| **curated / vector / project card 继续后置** | 010+ / 011+；005 只产出 parsed text |
| **真实 Office 解析质量验证** | 生产样本 docx/pptx/xlsx 真实 markitdown 集成测试可在 006 前或 QA 增强阶段补做 |
| **quality-checker** | 007 读 parsed 产物；可能触发 MinerU 重解析 |

**006 入口条件**：

- [ ] 005 已 merge `main`
- [ ] 新 feature 分支基于 `main` HEAD（如 `feature/006-mineru-parser`）
- [ ] TL 完成 006 五件套 + Dev 白名单
- [ ] 已读本文 handoff

---

## 14. 运维与风险提示

| 风险 | 缓解 |
|------|------|
| **不默认全库解析** | CLI 必须提供 `--sha256` / `--content-uid` / `--limit` 之一 |
| **limit ≤ 100** | `PARSE_MARKITDOWN_MAX_LIMIT = 100`；超限 exit 1 |
| **大文件** | 可能慢或 OOM；记入 report errors；单条 continue |
| **密码文件 / 损坏文件** | 启发式分类为 FAILED；记入 errors[]；不中断批处理 |
| **真实 Office 解析质量** | pytest 默认 mock；生产 docx/pptx/xlsx 质量需后续真实样本验证 |
| **raw_vault 只读** | 005 永不覆盖 original.bin |
| **parsed 磁盘增长** | 每次 SUCCESS 写三文件；注意 parsed_root 磁盘空间 |
| **报告累积** | 每次运行新 timestamp 报告，不覆盖旧报告 |

**勿提交**：

- `config/app.yaml`（含 MySQL 密码）
- `raw_vault/**`、`parsed/**`（本地运行产物）
- `reports/**`（本地报告）

---

## 15. TL Final Review Checklist

**P9 Tech Lead Final Review 待办**：

- [ ] 阅读本 handoff、`plan.md`、`tasks.md`（P1–P8 全部 `[x]`）
- [ ] **文件白名单**：确认 diff 仅含白名单内 6 个 backend 文件 + tasks.md
- [ ] **测试结果**：005 专项 41 passed；全链路 83 passed
- [ ] **raw_vault 两档路径**：`_resolve_vault_dir` + `build_vault_artifact_paths`；无三档 raw_vault
- [ ] **parsed 三档路径**：`parsed_paths.py` 独立构建；与 vault 不混用
- [ ] **DB 零写**：P6 PASS_WITH_NOTES 无阻断；grep + test 证据
- [ ] **scope 未膨胀**：无 MinerU / OCR / curated / vector / DB registry / schema 变更
- [ ] **handoff 文档完整**：本文 + tasks.md P8 勾选
- [ ] **是否允许 merge main**：TL 裁决（Handoff 建议：**条件允许**，待 TL 签字）

**merge main 前**：

- [ ] Handoff 文档 commit：`docs(005): add markitdown parser handoff`
- [ ] 确认分支 commits 完整（spec plan + feat + handoff）
- [ ] merge 到 `main` 后记录 merge commit

---

## 16. 当前工作区状态

| 项 | 状态 |
|----|------|
| **实现 commit** | `36aaf80 feat(005): implement markitdown parser` 已提交 |
| **Handoff 文档** | 本文待 commit |
| **tasks.md** | P8 勾选待 commit |
| **工作区** | Handoff 编写后含未提交 docs/tasks 变更 |

**Handoff 待 commit 文件**：

```text
docs/handoff-phase1-005-markitdown-parser.md
specs/005-markitdown-parser/tasks.md
```

---

## 17. 给新会话的接手提示

### 17.1 会话启动模板

```text
当前角色：<TL|DEV|DB|QA|HO>
当前 Spec：specs/005-markitdown-parser（或 006）
当前分支：feature/005-markitdown-parser-adapter（或 main，若已 merge）
当前步骤：P9 TL Final Review / 或 006 Plan
TL 批准的文件白名单：（DEV 必填）
禁止修改：001–004 封闭 service、sql/**、raw_vault 真实产物、原始用户文件
```

### 17.2 必读文档

1. `docs/handoff-phase1-005-markitdown-parser.md`（本文）
2. `docs/handoff-phase1-004-parser-router.md`
3. `docs/agent_collaboration_standard.md`
4. `specs/005-markitdown-parser/plan.md`（含附录 A Q1–Q17）
5. 若进入 006：对应 Spec 五件套

### 17.3 快速命令

```bash
cd /home/szf/dev/pyws/pkb_sdd/backend
source .venv/bin/activate

# 全链路回归
pytest -q tests/test_inventory_scanner.py tests/test_file_content_vault.py \
  tests/test_duplicate_governance.py tests/test_parser_router.py \
  tests/test_markitdown_parser.py

# CLI 全链路
python -m app.cli.main scan --path backend/tests/fixtures
python -m app.cli.main copy-to-vault
python -m app.cli.main parse-markitdown --limit 10
```

### 17.4 交接确认清单

- [ ] 已读 Executive Summary 与 commit 记录
- [ ] 已知 005 实现文件清单与 CLI 用法
- [ ] 已知 raw_vault 两档 vs parsed 三档路径规则
- [ ] 已知 schema 未变更、无 DB 写、无 migration
- [ ] 已知 P6/P7 均为 PASS_WITH_NOTES，notes 非阻断
- [ ] 已知 DB-NOTE-1–4 / QA notes（Office mock、dry_run_action 等）
- [ ] 已知 006 边界：parse registry / MinerU 不归 005
- [ ] 未在 handoff 阶段修改业务代码

---

**文档结束** — STOP → **P9 Tech Lead Final Review** → merge main → 006 Spec Plan。

# 阶段交接文档：Phase 1 — 006-parse-job-registry（Parse Job Registry）

> **项目**：个人历史项目文档知识库 `pkb_sdd`  
> **版本基线**：V1.1-SDD  
> **交接日期**：2026-06-15  
> **项目路径**：`/home/szf/dev/pyws/pkb_sdd`  
> **编写角色**：Handoff Agent（`HO`）  
> **当前 Spec**：`specs/006-parse-job-registry`  
> **前置文档**：`docs/handoff-phase1-005-markitdown-parser.md`

---

## 1. 006 基本信息

| 项 | 值 |
|----|-----|
| **Spec 名称** | `006-parse-job-registry` — Parse Run / Result / Artifact MySQL Registry |
| **当前分支** | `feature/006-parse-job-registry` |
| **当前阶段** | **P8 Handoff**（P5 Dev / P6 DB / P7 QA 已完成；待 P9 TL Final Review） |
| **是否已 merge main** | 否（005 已 merge main；006 待 TL Final Review） |

**006 相关 commits（按时间顺序）**：

```text
cb2d64b spec(006): add parse job registry plan
29e35b1 spec(006): align parse registry schema decisions
5819165 feat(006): implement parse job registry          # 主实现
ee20c5e feat(006): implement parse job registry          # document.py + down migration
```

**关键实现 commits**：

| Commit | 说明 |
|--------|------|
| `5819165` | 主实现：migration、ORM、service、CLI、pytest |
| `ee20c5e52872c66dacd3e1dca6ab13dab2de399f` | 补充 `KbDocument` ORM + `006_parse_registry_v1_down.sql` |

**审查结论**：

| 角色 | 阶段 | 结论 |
|------|------|------|
| Tech Lead | P4 TL Gate | `APPROVED_FOR_P5`（M1–M4 / S1 / S4 已写入 plan） |
| Dev | P5 Implementation | 已完成 |
| DB & Data Agent | P6 Implementation Review | `PASS_WITH_NOTES`，无阻断项 |
| E2E QA Agent | P7 E2E 验收 | `PASS_WITH_NOTES`，无阻断项 |

**测试结果（Handoff 复核）**：

```bash
cd /home/szf/dev/pyws/pkb_sdd/backend
source .venv/bin/activate

# 006 专项
pytest -q tests/test_parse_job_registry.py
# 36 passed in ~4.4s

# 全量 backend 回归（001–005 + 006）
pytest -q
# 120 passed in ~19s
```

| 模块 | 用例数 |
|------|--------|
| `test_inventory_scanner.py` | 7 |
| `test_file_content_vault.py` | 7 |
| `test_duplicate_governance.py` | 9 |
| `test_parser_router.py` | 19 |
| `test_markitdown_parser.py` | 41 |
| `test_parse_job_registry.py` | 36 |
| `test_project_safety_placeholder.py` | 1 |
| **合计** | **120** |

---

## 2. 006 目标摘要

006 在 **不重新解析、不修改 005 执行逻辑** 的前提下，将 005 磁盘解析产物与报告 **索引到 MySQL**，形成可查询的 parse lifecycle registry。

**核心目标**：

1. **Parse Run Registry**（`kb_parse_run`）：一次批处理 / 一次 report 登记的运行审计记录（业务「parse job」）。
2. **Parse Result Registry**（`kb_parse_result`）：单个 `content_uid` 在某次 run 下的解析结果。
3. **Parsed Artifact Registry**（`kb_parsed_artifact`）：parsed 三文件 + parse report 的磁盘路径与 hash 索引。
4. **承接 005 parsed 磁盘产物**：只读 ingest `parse_manifest.json` 与 `parse_markitdown_report_*.json`；更新 `kb_file_content.parse_status` 与 `kb_document` bridge。
5. **不执行解析**：006 不调用 MarkItDown / MinerU / OCR；不读 `original.bin`。

**Phase 1 进度**：

```text
001-file-inventory       ✅ 已完成
002-file-content-vault   ✅ 已完成
003-duplicate-governance ✅ 已完成
004-parser-router        ✅ 已完成
005-markitdown-parser    ✅ 已 merge main
006-parse-job-registry   ✅ 实现 + DB/QA PASS_WITH_NOTES（待 TL Final Review / merge main）
007-quality-checker      ⬜ 未开始
008-mineru-parser        ⬜ 未开始
```

**数据流**：

```text
001 scan → 002 copy-to-vault → [003] → [004] → 005 parse-markitdown
  → parsed/ 三文件 + parse_markitdown_report_{UTC}.json
  → 006 register-parse-report --report-path ...（report.dry_run 必须为 false）
    → read report JSON + parse_manifest.json（只读 parsed/）
    → upsert kb_parse_run + kb_parse_result + kb_parsed_artifact
    → update kb_file_content.parse_status
    → upsert kb_document（SUCCESS/EMPTY bridge）
    → registry_report_{UTC}.json（可选）

可选（显式 opt-in）：
  006 reconcile-parsed-artifacts --sha256 ... | --limit N
    → scan parsed/ manifest → 补齐 registry（无 report 时 synthesize run）
    → 不调用 MarkItDown
```

---

## 3. 006 实现范围

| 交付物 | 说明 |
|--------|------|
| **`kb_parse_run`** | Batch parse run 审计表；CLI「parse job」业务实体 |
| **`kb_parse_result`** | Per-content 解析结果；含 error / retry 字段 |
| **`kb_parsed_artifact`** | 磁盘产物索引（text / metadata / manifest / report） |
| **`register-parse-report`** | 读取 005 report + manifest，登记 run / results / artifacts |
| **`reconcile-parsed-artifacts`** | 显式 opt-in；从已有 `parsed/` 扫描 manifest 补齐 registry |
| **Registry CLI** | `list-parse-jobs`、`show-parse-job`、`list-parse-results`、`list-parsed-artifacts` |
| **`ParseRegistryService`** | report ingest、reconcile、查询、幂等 upsert、dry-run |
| **ORM models** | `KbParseRun`、`KbParseResult`、`KbParsedArtifact`、`KbDocument` |
| **SQL migration** | `006_parse_registry_v1.sql`（additive CREATE TABLE） |
| **`kb_file_content.parse_status`** | UPDATE（SUCCESS→PARSED、EMPTY→PARSED_EMPTY、FAILED→PARSE_FAILED） |
| **`kb_document`** | SUCCESS/EMPTY 时 bridge upsert；`document_uid = content_uid` |
| **pytest** | 006 新增 **36** 个用例（≥25 要求已满足） |

---

## 4. 006 明确不覆盖

| 非目标 | 说明 | 归属 |
|--------|------|------|
| **MinerU** | 不 import / 不 subprocess | **008-mineru-parser** |
| **OCR** | 不做 | 008 |
| **PDF / IMAGE 深度解析** | 不执行 | 008 |
| **新 parser 类型** | MVP 仅 ingest `parser_name=markitdown` | 后续 parser Spec |
| **curated/** | 不写 | 010+ |
| **vector DB / embedding** | 不做 | 011+ |
| **project card distillation** | 不做 | 010+ |
| **Streamlit / 前端** | 不做 | 012+ |
| **默认历史全量回填** | reconcile 须显式 `--sha256` / `--content-uid` / `--limit` | — |
| **默认重新解析** | 006 不调用 005；重解析须用户显式运行 `parse-markitdown` | — |
| **init SQL `kb_parse_job`** | per-content worker queue 语义保留；006 **不写** | 未来 queue Spec |
| **修改 005 `markitdown_parser.py`** | 005 service 封闭 | — |
| **修改 raw_vault / parsed 磁盘** | registry 默认只读 ingest | — |

---

## 5. 新增或修改文件清单

| 操作 | 文件 | 说明 |
|------|------|------|
| **新增** | `sql/migrations/006_parse_registry_v1.sql` | 三表 additive migration |
| **新增** | `sql/migrations/006_parse_registry_v1_down.sql` | 测试回滚（DROP 三表；生产须 TL 批准） |
| **新增** | `backend/app/models/parse_registry.py` | `KbParseRun`、`KbParseResult`、`KbParsedArtifact` |
| **新增** | `backend/app/models/document.py` | `KbDocument` ORM（bridge upsert） |
| **新增** | `backend/app/services/parse_registry.py` | `ParseRegistryService`、幂等 / dry-run / reconcile |
| **修改** | `backend/app/cli/main.py` | 006 六个 CLI 命令 |
| **新增** | `backend/tests/test_parse_job_registry.py` | 36 个 pytest 用例 |
| **修改** | `specs/006-parse-job-registry/tasks.md` | P5–P8 阶段勾选 |

**`backend/app/models/__init__.py`**：保持空文件，**未修改**（模型经直接 import 使用）。

**未修改（封闭 / 只读 import）**：

- `backend/app/services/markitdown_parser.py`
- `backend/app/adapters/markitdown_adapter.py`
- `backend/app/services/inventory_scanner.py`
- `backend/app/services/file_content_vault.py`
- `backend/app/services/parser_router.py`
- `backend/app/core/parsed_paths.py` — 只读 import
- `backend/app/core/vault_paths.py` — 只读 import
- `sql/001_init_schema_v1_1.sql`

---

## 6. SQL / Migration 说明

### 6.1 执行方式

| 项 | 说明 |
|----|------|
| **Migration runner** | 当前项目 **无** 自动 migration runner |
| **执行方式** | 运维须 **手动** 在目标 MySQL 执行 `sql/migrations/006_parse_registry_v1.sql` |
| **幂等** | `CREATE TABLE IF NOT EXISTS`；重复执行不失败 |
| **破坏性操作** | **无** DROP / TRUNCATE / destructive ALTER |
| **`kb_parse_job`** | migration **不创建、不修改** init SQL per-content queue 表 |

### 6.2 三表结构摘要

**`kb_parse_run`** — Batch parse run（业务「parse job」）：

- 业务主键：`run_uid`（UNIQUE）
- 关键列：`parser_name`、`parser_adapter_version`、`trigger_type`、`status`、summary 计数、`report_path`、`registry_report_path`
- 幂等键：`uk_parse_run_report (report_path(512), parser_adapter_version)`

**`kb_parse_result`** — Per-content 结果：

- 业务主键：`result_uid`（UNIQUE）
- 外键：`run_uid` → `kb_parse_run(run_uid)`；`retry_of_result_id` → `kb_parse_result(id)`
- 幂等键：`uk_parse_result_run_content (run_uid, content_uid, parser_adapter_version)`

**`kb_parsed_artifact`** — 磁盘产物索引：

- 业务主键：`artifact_uid`（UNIQUE）
- 外键：`run_uid` → `kb_parse_run(run_uid)`
- 幂等键：**`uk_artifact_scope (run_uid, content_uid, artifact_type, parser_name, parser_adapter_version)`**（M1）
- run 级 `PARSE_REPORT`：`content_uid = ''`（空字符串 sentinel）

### 6.3 关键索引 / UNIQUE 约束

| 表 | 约束 | 用途 |
|----|------|------|
| `kb_parse_run` | `run_uid` UNIQUE | 业务主键 |
| `kb_parse_run` | `uk_parse_run_report` | 同 report 重复 register 幂等 |
| `kb_parse_result` | `result_uid` UNIQUE | 结果业务主键 |
| `kb_parse_result` | `uk_parse_result_run_content` | 同 run + content 幂等 upsert |
| `kb_parsed_artifact` | `artifact_uid` UNIQUE | artifact 业务主键 |
| `kb_parsed_artifact` | **`uk_artifact_scope`** | M1：artifact 唯一性含 `run_uid` |

### 6.4 已有表写入（非 schema 变更）

| 表 | 006 操作 |
|----|----------|
| `kb_file_content` | UPDATE `parse_status` |
| `kb_document` | UPSERT（SUCCESS/EMPTY bridge） |
| `kb_parse_job`（init） | **不读写** |

---

## 7. M1–M4 / S1 / S4 裁决落地

| ID | 裁决 | 落地证据 |
|----|------|----------|
| **M1** | artifact UNIQUE 含 `run_uid`：`uk_artifact_scope(run_uid, content_uid, artifact_type, parser_name, parser_adapter_version)` | migration §85；`test_kb_parsed_artifact_unique_includes_run_uid`、`test_artifact_unique_includes_run_uid` |
| **M2** | 006 registry `--dry-run` **零 DB 写**；禁止 `DRY_RUN_COMPLETED` 入库 | `register_parse_report(dry_run=True)` 早返回无 session 写；`test_registry_dry_run_writes_no_db_rows`、`test_cli_dry_run_behavior`、`test_reconcile_dry_run_writes_no_db` |
| **M3** | 005 `report.dry_run=true` → exit 1 + `INVALID_DRY_RUN_REPORT` | `register_parse_report` 首行检查；`test_register_dry_run_report_rejected` |
| **M4** | `document_uid = content_uid`；禁止 sha256 备选 | bridge upsert 逻辑；`test_document_uid_equals_content_uid`、`test_no_sha256_fallback_document_uid` |
| **S1** | `run_uid = parse_run_{UTC:%Y%m%dT%H%M%SZ}_{uuid4.hex[:8]}` | `generate_run_uid()`；`RUN_UID_PATTERN`；`test_run_uid_format` |
| **S4** | SKIPPED 无 manifest 时 **零** artifact 行 | `_ingest_report_item` 分支；`test_skipped_without_manifest_creates_no_artifact` |

---

## 8. Registry Service 说明

**文件**：`backend/app/services/parse_registry.py` — `ParseRegistryService`

### 8.1 核心方法

| 方法 | 职责 |
|------|------|
| `register_parse_report()` | 读 005 report + manifest；拒绝 dry_run report；登记 run / results / artifacts |
| `reconcile_parsed_artifacts()` | 显式 filter 扫描 `parsed/` manifest；synthesize RECONCILE run |
| `create_parse_run()` | 设置 run status（PENDING→RUNNING）与 `started_at` |
| `finish_parse_run()` | 设置终态（COMPLETED / PARTIAL）与 `finished_at`、`registry_report_path` |
| `fail_parse_run()` | 设置 FAILED + `error_message` |
| `record_parse_result()` | upsert per-content result；设置 `retry_of_result_id` |
| `record_parsed_artifact()` | upsert artifact；计算 hash / size；缺失文件标 `MISSING` |
| `list_parse_runs()` / `get_parse_run()` | 查询 run |
| `list_parse_results()` / `list_parsed_artifacts()` | 查询 result / artifact |

### 8.2 Dry-run 行为（M2）

| 命令 | dry-run 行为 |
|------|--------------|
| `register-parse-report --dry-run` | **零** MySQL INSERT/UPDATE（三表 + `parse_status` + `kb_document`）；可写磁盘 `registry_report_{UTC}.json` preview |
| `reconcile-parsed-artifacts --dry-run` | **零** DB 写；返回 `manifests_found` preview |
| 005 `dry_run=true` report | **拒绝 ingest**（M3）；与 006 CLI dry-run 不同 |

### 8.3 幂等策略

| 场景 | 行为 |
|------|------|
| 重复 `register-parse-report` 同一 report | 复用已有 `run_uid`（`uk_parse_run_report`）；results upsert by `uk_parse_result_run_content` |
| 同 content 新 run | 新 result 行；`parse_status` 取 `finished_at` 最新 result |
| artifact 同 run+scope | upsert by `uk_artifact_scope` |
| reconcile 同 manifest | upsert；不 duplicate |

### 8.4 事务边界

| 粒度 | 策略 |
|------|------|
| run 创建 | 独立 commit（获取 `run_uid`） |
| 单 content ingest | `session.begin()`：result + artifacts + `kb_document` + `parse_status` 原子 |
| 单条失败 | rollback 当前 content transaction；`errors[]`；continue |
| run 终态 | `finish_parse_run` + commit |
| 006 CLI `--dry-run` | 无 DB session 写操作 |

### 8.5 Parse status 聚合

| 最新 result.status | `kb_file_content.parse_status` |
|--------------------|--------------------------------|
| SUCCESS | `PARSED` |
| EMPTY | `PARSED_EMPTY` |
| FAILED | `PARSE_FAILED` |
| SKIPPED | **不更新**（保留原值或 NULL） |

### 8.6 `kb_document` bridge

- `document_uid = content_uid`（M4）
- `parser_profile = markitdown_default_v1`
- SUCCESS → `parse_status=PARSED`；EMPTY → `parse_status=PARSED_EMPTY`
- 路径来自 manifest：`markdown_path`、`json_path`、`manifest_path`、`output_dir`

---

## 9. CLI 使用方式

### 9.1 推荐流水线

```bash
cd /home/szf/dev/pyws/pkb_sdd/backend
source .venv/bin/activate

# 前置：001–005
python -m app.cli.main scan --path backend/tests/fixtures
python -m app.cli.main copy-to-vault
python -m app.cli.main parse-markitdown --limit 10

# 006：登记 registry（report.dry_run 必须为 false）
python -m app.cli.main register-parse-report \
  --report-path ../reports/parse_markitdown_report_YYYYMMDDTHHMMSSZ.json
```

### 9.2 命令一览

| 命令 | 说明 |
|------|------|
| `register-parse-report` | 读 005 report + manifest；写入 registry 三表 + bridge |
| `list-parse-jobs` | 列出 `kb_parse_run` 摘要（`--limit` / `--status` / `--parser-name`） |
| `show-parse-job` | `--run-uid` 详情；可选 `--include-results` / `--include-artifacts` |
| `list-parse-results` | 按 `--run-uid` / `--content-uid` / `--sha256` / `--status` 过滤 |
| `list-parsed-artifacts` | 按 `--content-uid` / `--sha256` / `--artifact-type` 过滤 |
| `reconcile-parsed-artifacts` | 显式 opt-in；须 `--sha256` / `--content-uid` / `--limit` 至少其一 |

### 9.3 常用示例

```bash
# 预览 registry 将写入什么（零 DB 写）
python -m app.cli.main register-parse-report \
  --report-path ../reports/parse_markitdown_report_*.json \
  --dry-run

# 查询
python -m app.cli.main list-parse-jobs --limit 20
python -m app.cli.main show-parse-job --run-uid parse_run_20260615T120000Z_a1b2c3d4 --include-results
python -m app.cli.main list-parse-results --content-uid <sha256>
python -m app.cli.main list-parsed-artifacts --artifact-type PARSED_TEXT

# 从已有 parsed 补齐 registry（不重新解析）
python -m app.cli.main reconcile-parsed-artifacts --sha256 <hex>
python -m app.cli.main reconcile-parsed-artifacts --limit 10 --dry-run
```

### 9.4 护栏

| 规则 | 行为 |
|------|------|
| `reconcile` 无 filter | exit 1 |
| `reconcile --limit > 100` | exit 1（`PARSE_REGISTRY_MAX_LIMIT = 100`） |
| 005 `dry_run=true` report | exit 1 + `INVALID_DRY_RUN_REPORT` |
| 006 `--dry-run` | 零 DB 写；可写磁盘 preview report |
| CLI 入口 | `ensure_readonly()` |

---

## 10. 与 005 的关系

| 维度 | 005 | 006 |
|------|-----|-----|
| 读 vault bin | ✅ | ❌ |
| 调 MarkItDown | ✅ | ❌ |
| 写 parsed/ | ✅ | ❌（默认只读） |
| 写 MySQL registry | ❌ | ✅ |
| 修改对方 service | ❌ | ❌ |

**衔接方式**：

- 005 产出 `parsed/` 三文件 + `parse_markitdown_report_{UTC}.json`（MySQL 零写）。
- 006 通过 `register-parse-report` 只读 ingest 上述产物与报告。
- **006 不修改** `markitdown_parser.py`；**006 不执行** parser。
- **006 不修改** raw_vault / parsed 磁盘内容（只读 stat / hash / JSON）。

```text
005: vault bin → MarkItDown → parsed/ + parse_markitdown_report.json
006: parse_markitdown_report.json + parsed/manifest → MySQL registry
```

---

## 11. P6 PASS_WITH_NOTES 摘要

**结论**：`PASS_WITH_NOTES`，无阻断项，不要求 Dev 修复。

| 审查点 | 结论 |
|--------|------|
| ORM 与 SQL 主结构一致 | ✅ 三表字段一一对应；`metadata` 列 ORM 映射为 `metadata_json` |
| 无阻断 schema / FK 问题 | ✅ `fk_parse_result_run`、`fk_parsed_artifact_run`、`fk_parse_result_retry` 正确 |
| `uk_artifact_scope`（M1） | ✅ migration 与 ORM 一致 |
| 不写 `kb_parse_job` | ✅ migration 与 service 均无引用 |
| Plan 语义未完全落地项 | 非阻断（见下） |

**非阻断 notes（运维 / 并发风险）**：

| ID | Note | 说明 |
|----|------|------|
| **DB-NOTE-1** | migration 需手动执行 | 项目无 migration runner；部署前须人工跑 SQL |
| **DB-NOTE-2** | reconcile 每次新建 run | 未做 reconcile run 去重；重复 reconcile 可能产生多条 `trigger_type=RECONCILE` run |
| **DB-NOTE-3** | 共享 MySQL 测试库并行污染 | pytest 共用库时可能存在并行测试污染风险 |
| **DB-NOTE-4** | `report_path` UNIQUE 前缀长度 | `uk_parse_run_report (report_path(512), ...)` 极长路径理论上可能前缀碰撞（低概率） |

---

## 12. P7 E2E QA 摘要

**结论**：`PASS_WITH_NOTES`，无阻断项，不要求 Dev 修复。

### 12.1 006 专项测试

```text
pytest -q tests/test_parse_job_registry.py
36 passed in ~4.4s
```

### 12.2 全量回归

```text
pytest -q
120 passed in ~19s
```

001–005 回归无破坏（84 passed）+ 006 新增 36 passed。

### 12.3 Acceptance A001–A019 验收结论

| 编号 | 标准 | 结论 |
|------|------|------|
| **A001** | SQL schema additive；ORM 一致 | ✅ PASS |
| **A002** | 不破坏 001–005；005 pytest pass | ✅ PASS |
| **A003** | raw_vault 不变 | ✅ PASS |
| **A004** | parsed 不变（只读 ingest） | ✅ PASS |
| **A005** | 不重新解析 | ✅ PASS |
| **A006** | parse run 可记录 | ✅ PASS |
| **A007** | parse result 可记录 | ✅ PASS |
| **A008** | parsed artifact 可索引 | ✅ PASS |
| **A009** | 失败原因可追踪 | ✅ PASS |
| **A010** | 重试关系可追踪 | ✅ PASS |
| **A011** | dry-run 不写 DB（M2） | ✅ PASS |
| **A012** | 事务一致 | ✅ PASS |
| **A013** | 不接 MinerU / OCR | ✅ PASS |
| **A014** | 不做 curated / vector / project card | ✅ PASS |
| **A015** | 测试通过（≥25 functions） | ✅ PASS（36 functions） |
| **A016** | artifact UNIQUE 含 run_uid（M1） | ✅ PASS |
| **A017** | registry dry-run 零 DB 写（M2） | ✅ PASS |
| **A018** | 005 dry-run report 拒绝（M3） | ✅ PASS |
| **A019** | document_uid = content_uid（M4） | ✅ PASS |

### 12.4 M1–M4 / S1 / S4 专项

| 裁决 | 测试证据 |
|------|----------|
| M1 `uk_artifact_scope` | `test_artifact_unique_includes_run_uid` |
| M2 dry-run 零写 | `test_registry_dry_run_writes_no_db_rows`、`test_cli_dry_run_behavior` |
| M3 拒绝 dry-run report | `test_register_dry_run_report_rejected` |
| M4 document_uid | `test_document_uid_equals_content_uid` |
| S1 run_uid 公式 | `test_run_uid_format` |
| S4 SKIPPED 零 artifact | `test_skipped_without_manifest_creates_no_artifact` |

### 12.5 阻断项

**无阻断项。** 不解析、不改 raw_vault/parsed、不接 MinerU/OCR 均已验证。

---

## 13. 已知风险与运维提示

| 风险 | 缓解 |
|------|------|
| **migration 需手动执行** | merge main 后于目标 MySQL 执行 `sql/migrations/006_parse_registry_v1.sql`；确认三表存在后再跑 CLI |
| **共享 MySQL 测试库并行污染** | 生产/CI 建议独立库；本地 pytest 避免并行跑 registry 测试 |
| **reconcile 每次新建 run** | 重复 reconcile 产生多条 RECONCILE run；如需 dedup 须单独 Spec |
| **dry-run 零 DB 写** | `--dry-run` 仅 preview；正式登记须去掉 `--dry-run` |
| **dry-run report 不可 ingest** | 005 `--dry-run` 产出的 report 含 `dry_run=true`；须用非 dry-run report 调用 register |
| **reconcile 须显式 filter** | 无 `--sha256` / `--content-uid` / `--limit` → exit 1；禁止默认全库 |
| **limit ≤ 100** | `PARSE_REGISTRY_MAX_LIMIT = 100` |
| **parsed 磁盘增长** | registry 只索引不清理；注意 parsed_root 磁盘空间 |
| **报告累积** | 每次 register 可写新 `registry_report_{UTC}.json` |

**勿提交**：

- `config/app.yaml`（含 MySQL 密码）
- `raw_vault/**`、`parsed/**`（本地运行产物）
- `reports/**`（本地报告）

---

## 14. 后续 007 建议

| 建议 | 说明 |
|------|------|
| **007-quality-checker** | 读 parsed + `kb_document`；`quality_score`；可能触发重解析决策 |
| **MinerU / PDF / OCR 独立 Spec** | → **008-mineru-parser**；**不应倒灌到 006** |
| **curated / vector / project card 继续后置** | 010+ / 011+；006 仅提供 parse_status + document path |
| **registry 并发增强 / reconcile dedup** | 如需 run 去重或分布式锁，可单独 Spec |
| **真实 Office 解析 + registry E2E** | 生产样本 docx/pptx/xlsx 全链路可在 007 前或 QA 增强阶段补做 |

**007 / 008 入口条件**：

- [ ] 006 已 merge `main`
- [ ] migration 已在目标环境手动执行
- [ ] 新 feature 分支基于 `main` HEAD
- [ ] TL 完成目标 Spec 五件套 + Dev 白名单
- [ ] 已读本文 handoff

---

## 15. TL Final Review Checklist

**P9 Tech Lead Final Review 待办**：

- [ ] 阅读本 handoff、`plan.md`、`tasks.md`（P1–P8 全部 `[x]`）
- [ ] **文件白名单**：确认 diff 仅含白名单内文件（见 §5）+ handoff + tasks.md
- [ ] **migration 安全性**：additive only；无 DROP/TRUNCATE/destructive ALTER；不写 `kb_parse_job`
- [ ] **ORM / SQL 一致性**：三表字段对齐；`uk_artifact_scope` 含 `run_uid`
- [ ] **M1–M4 / S1 / S4**：六项裁决均有测试证据
- [ ] **测试结果**：006 专项 36 passed；全量 120 passed；005 回归无破坏
- [ ] **边界未膨胀**：无 MinerU/OCR/解析执行/curated/vector/Streamlit；不改 005 封闭 service
- [ ] **handoff 完整性**：本文 + tasks.md P8 勾选
- [ ] **是否允许 merge main**：TL 裁决（Handoff 建议：**条件允许**，待 TL 签字）

**merge main 前**：

- [ ] 确认目标 MySQL 已执行 migration（或 merge 后第一时间执行）
- [ ] Handoff 文档 commit：`docs(006): add parse job registry handoff`
- [ ] 确认分支 commits 完整（spec plan + plan repair + feat + handoff）
- [ ] merge 到 `main` 后记录 merge commit

---

## 16. 当前工作区状态

| 项 | 状态 |
|----|------|
| **实现 commits** | `5819165` + `ee20c5e` 已提交 |
| **Handoff 文档** | 本文待 commit |
| **tasks.md** | P6–P8 勾选待 commit |
| **工作区** | Handoff 编写后含未提交 docs/tasks 变更 |

**Handoff 待 commit 文件**：

```text
docs/handoff-phase1-006-parse-job-registry.md
specs/006-parse-job-registry/tasks.md
```

---

## 17. 给新会话的接手提示

### 17.1 会话启动模板

```text
当前角色：<TL|DEV|DB|QA|HO>
当前 Spec：specs/006-parse-job-registry（或 007/008）
当前分支：feature/006-parse-job-registry（或 main，若已 merge）
当前步骤：P9 TL Final Review / 或 007 Plan
TL 批准的文件白名单：（DEV 必填）
禁止修改：001–005 封闭 service、sql/**（无授权）、raw_vault 真实产物、原始用户文件
```

### 17.2 必读文档

1. `docs/handoff-phase1-006-parse-job-registry.md`（本文）
2. `docs/handoff-phase1-005-markitdown-parser.md`
3. `docs/agent_collaboration_standard.md`
4. `specs/006-parse-job-registry/plan.md`（含附录 A Q1–Q21）
5. 若进入 007/008：对应 Spec 五件套

### 17.3 快速命令

```bash
cd /home/szf/dev/pyws/pkb_sdd/backend
source .venv/bin/activate

# 全量回归
pytest -q

# CLI 全链路
python -m app.cli.main scan --path backend/tests/fixtures
python -m app.cli.main copy-to-vault
python -m app.cli.main parse-markitdown --limit 10
python -m app.cli.main register-parse-report --report-path ../reports/parse_markitdown_report_*.json

# migration（手动，目标 MySQL）
mysql -u ... -p ... < ../sql/migrations/006_parse_registry_v1.sql
```

### 17.4 交接确认清单

- [ ] 已读 §1 基本信息与 commit 记录
- [ ] 已知 006 实现文件清单与 CLI 用法
- [ ] 已知 migration 须手动执行、无 migration runner
- [ ] 已知 M1–M4 / S1 / S4 裁决与测试证据
- [ ] 已知 P6/P7 均为 PASS_WITH_NOTES，notes 非阻断
- [ ] 已知 006 不解析、不改 raw_vault/parsed、不写 kb_parse_job
- [ ] 已知 007/008 边界：MinerU/quality 不归 006
- [ ] 未在 handoff 阶段修改业务代码

---

**文档结束** — STOP → **P9 Tech Lead Final Review** → merge main → 007/008 Spec Plan。

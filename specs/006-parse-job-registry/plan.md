# Plan: Parse Job Registry（006 实现计划）

> **项目**：个人历史项目文档知识库 `pkb_sdd`  
> **项目路径**：`/home/szf/dev/pyws/pkb_sdd`  
> **版本基线**：V1.1-SDD  
> **编写日期**：2026-06-15  
> **编写角色**：Tech Lead Agent — 步骤 ① Plan  
> **当前分支**：`feature/006-parse-job-registry`  
> **前置条件**：001–005 merge `main`；006 Preflight PASS

---

## 1. 背景与 001–005 能力基线

Phase 1 进度：

```text
001 盘点 → 002 raw_vault → 003 重复治理 → 004 解析路由 → 005 MarkItDown → 【006 Registry】
```

| Spec | CLI | 能力 | 磁盘 | MySQL |
|------|-----|------|------|-------|
| **001** | `scan` | instance/content 登记 | inventory 报告 | 写 instance/content |
| **002** | `copy-to-vault` | 只读复制 → `original.bin`（**两档**） | raw_vault | 写 vault 元数据 |
| **003** | `govern-duplicates` | sha256 重复组 + cleanup 建议 | duplicate 报告 | upsert duplicate_group |
| **004** | `route-parsers` | `route_type` + `future_parser_hint` | parser_route_report | **只读** |
| **005** | `parse-markitdown` | MarkItDown-family 解析 | parsed 三文件 + parse_markitdown_report | **只读** |

005 关键产物（006 ingest 输入）：

- `parse_manifest.json`：`content_uid`、`sha256`、`parser_name`、`parser_adapter_version`、`status`、`error`、`parsed_*_path`
- `parse_markitdown_report_*.json`：`summary`、`items[]`、`errors[]`、`dry_run`、`filters`

**缺口**：init SQL 已有 `kb_parse_job`（per-content queue）、`kb_document`，但 001–005 均未写入；运维无法 SQL 查询「哪次批处理解析了哪些 content、产物在哪、失败原因是什么」。

---

## 2. 006 目标

1. 新增 **additive migration** 与 ORM，建立 **`kb_parse_run` + `kb_parse_result` + `kb_parsed_artifact`** registry 三表。
2. 实现 **`register-parse-report`**：将 005 一次 `parse-markitdown` 运行登记到 DB。
3. 实现 **查询 CLI** 与 **opt-in reconcile**。
4. 更新 **`kb_file_content.parse_status`** 与 **`kb_document`** bridge。
5. 支持 **dry-run**、**幂等**、**失败/重试追踪**；**不重新解析**。

---

## 3. 006 非目标

| 非目标 | 说明 |
|--------|------|
| MinerU / OCR / PDF / IMAGE 解析 | → 008-mineru-parser |
| 修改 005 `markitdown_parser.py` | → 独立 `register-parse-report` |
| 默认全库 reconcile / 回填 | 须显式 filter + limit |
| 写 init SQL `kb_parse_job` | per-content queue 语义，006 不用 |
| curated / vector / project card / Streamlit / LLM | 后续 Spec |
| 破坏性 migration | 禁止 |
| 覆盖 parsed / raw_vault 磁盘 | 禁止 |

---

## 4. 与 005 MarkItDown Parser 的关系

```text
005: vault bin → MarkItDown → parsed/ + parse_markitdown_report.json
006: parse_markitdown_report.json + parsed/manifest → MySQL registry
```

| 维度 | 005 | 006 |
|------|-----|-----|
| 读 vault bin | ✅ | ❌ |
| 调 MarkItDown | ✅ | ❌ |
| 写 parsed/ | ✅ | ❌（默认只读） |
| 写 MySQL registry | ❌ | ✅ |
| 修改对方 service | ❌ | ❌ |

**衔接方式（P1 TL 裁决）**：

- **不修改** 005 代码。
- 运维/流水线在 005 之后手动或脚本调用：

```bash
python -m app.cli.main parse-markitdown --limit 10
python -m app.cli.main register-parse-report --report-path reports/parse_markitdown_report_*.json
```

- 未来可选：005 文档中增加「推荐后续 register」说明；**不得**在 006 MVP 中改 005。

---

## 5. Registry 业务语义

| 概念 | DB 实体 | 含义 |
|------|---------|------|
| **Parse Job（业务）** | `kb_parse_run` | 一次 CLI 批处理 / 一次 report 登记的运行记录 |
| **Parse Result** | `kb_parse_result` | 单个 `content_uid` 在某次 run 下的解析结果 |
| **Parsed Artifact** | `kb_parsed_artifact` | 单个磁盘产物文件索引（text / metadata / manifest / report） |
| **Document Registry（bridge）** | `kb_document` | init SQL 下游消费用的文档级聚合（路径 + parse_status） |
| **Content Parse Status** | `kb_file_content.parse_status` | 内容级最新解析状态摘要 |

**与 init SQL `kb_parse_job` 区分**：

- init `kb_parse_job` = **per-content 可认领 worker 任务**（`claimed_by`、`priority`），供未来 `build-parse-queue` 消费。
- 006 **`kb_parse_run`** = **batch run 审计记录**，对应用户故事中的「parse job」。
- 006 MVP **不写** init `kb_parse_job`，避免语义混用；DB Review 须确认两表并存策略。

---

## 6. Parse Job（Run）Lifecycle

**实体**：`kb_parse_run.status`

| 状态 | 含义 | 进入条件 |
|------|------|----------|
| `PENDING` | 已创建 run 行，尚未处理 items | register 开始 |
| `RUNNING` | 正在 ingest items | 第一条 result 写入前 |
| `COMPLETED` | 全部 items 处理完，无致命错误 | summary 写入完成 |
| `PARTIAL` | 有 items 失败但 run 完成 | `failed_count > 0` 且非全局 abort |
| `FAILED` | run 级失败（如 report 不可读） | 全局异常 |
| `DRY_RUN_COMPLETED` | dry-run 预览完成 | `dry_run=true` |

**转换**：

```text
PENDING → RUNNING → COMPLETED | PARTIAL | FAILED
dry_run: PENDING → DRY_RUN_COMPLETED（不写 result/artifact 表）
```

**时间戳**：`started_at` 在 RUNNING；`finished_at` 在终态。

---

## 7. Parse Result Lifecycle

**实体**：`kb_parse_result.status`（对齐 005 manifest / report item）

| 状态 | 含义 | 来源 |
|------|------|------|
| `SUCCESS` | 解析成功，三文件齐全 | manifest `status=SUCCESS` |
| `EMPTY` | 解析成功但输出为空 | manifest `status=EMPTY` |
| `SKIPPED` | out-of-scope / 幂等 skip / limit skip | report item `SKIPPED` |
| `FAILED` | 解析失败 | manifest/report `FAILED` + `error` |

**Content 级 `parse_status` 聚合规则（MVP）**：

| 最新 result.status | `kb_file_content.parse_status` |
|--------------------|--------------------------------|
| SUCCESS | `PARSED` |
| EMPTY | `PARSED_EMPTY` |
| FAILED | `PARSE_FAILED` |
| SKIPPED | **不更新**（保留原值或 NULL） |

同一 content 多次 register：以 **`finished_at` 最新** 的 result 为准更新 `parse_status`（同 timestamp 则 `result_uid` 字典序大者）。

---

## 8. Parsed Artifact Index 语义

**实体**：`kb_parsed_artifact`

| `artifact_type` | 磁盘文件 | 必填条件 |
|-----------------|----------|----------|
| `PARSED_TEXT` | `parsed_text.md` | SUCCESS / EMPTY |
| `PARSED_METADATA` | `parsed_metadata.json` | SUCCESS / EMPTY |
| `PARSE_MANIFEST` | `parse_manifest.json` | 始终（含 FAILED） |
| `PARSE_REPORT` | `parse_markitdown_report_*.json` | run 级一条（挂 run_uid） |

**索引字段**：

- `artifact_path`：绝对或 config 相对路径（与 005 manifest 一致）
- `artifact_hash`：文件 SHA256（存在则计算；缺失则 NULL + result FAILED）
- `artifact_size_bytes`：`stat().st_size`

**唯一性**：`UNIQUE (content_uid, artifact_type, parser_name, parser_adapter_version)`（MVP）；report 级 artifact 用 `content_uid IS NULL` + `run_uid` 区分（见 §9）。

---

## 9. 推荐 SQL Schema 草案

> **TL 裁决**：以下为 **additive migration** 草案；**不修改** `sql/001_init_schema_v1_1.sql` 已有表定义。最终字段以 DB Plan Review 为准。

### 9.1 `kb_parse_run`（业务「Parse Job」）

对应用户草案中的 batch-level `kb_parse_job` 字段；表名用 `kb_parse_run` 避免与 init `kb_parse_job` 冲突。

```sql
CREATE TABLE IF NOT EXISTS kb_parse_run (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  run_uid VARCHAR(64) NOT NULL UNIQUE COMMENT '业务 job_uid；建议 sha256(report_path+generated_at) 或 UUID',
  parser_name VARCHAR(64) NOT NULL COMMENT '005: markitdown',
  parser_adapter_version VARCHAR(128) NOT NULL COMMENT '005: 005_mvp_v1',
  parser_family VARCHAR(64) NOT NULL DEFAULT 'MARKITDOWN_FAMILY',
  trigger_type VARCHAR(64) NOT NULL DEFAULT 'REGISTER_REPORT' COMMENT 'REGISTER_REPORT | RECONCILE',
  filters_json JSON COMMENT '来自 report.filters 或 CLI filter',
  status VARCHAR(64) NOT NULL DEFAULT 'PENDING',
  dry_run TINYINT(1) NOT NULL DEFAULT 0,
  total_candidates INT NOT NULL DEFAULT 0,
  in_scope_candidates INT NOT NULL DEFAULT 0,
  parsed_count INT NOT NULL DEFAULT 0,
  skipped_count INT NOT NULL DEFAULT 0,
  failed_count INT NOT NULL DEFAULT 0,
  empty_count INT NOT NULL DEFAULT 0,
  report_path TEXT COMMENT '源 parse_markitdown_report 路径',
  registry_report_path TEXT COMMENT '006 输出的 registry_report 路径',
  started_at DATETIME NULL,
  finished_at DATETIME NULL,
  error_message TEXT,
  metadata JSON,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  UNIQUE KEY uk_parse_run_report (report_path(512), parser_adapter_version),
  KEY idx_parser_name (parser_name),
  KEY idx_status (status),
  KEY idx_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Batch parse run registry (006 parse job)';
```

### 9.2 `kb_parse_result`

```sql
CREATE TABLE IF NOT EXISTS kb_parse_result (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  result_uid VARCHAR(64) NOT NULL UNIQUE,
  run_uid VARCHAR(64) NOT NULL,
  content_uid VARCHAR(64) NOT NULL,
  sha256 CHAR(64) NOT NULL,
  route_type VARCHAR(64),
  decision VARCHAR(64),
  status VARCHAR(64) NOT NULL,
  source_vault_path TEXT,
  parsed_dir TEXT,
  manifest_path TEXT,
  metadata_path TEXT,
  text_path TEXT,
  output_hash CHAR(64),
  output_size_bytes BIGINT,
  error_code VARCHAR(128),
  error_message TEXT,
  retry_of_result_id BIGINT NULL COMMENT '指向前一次失败 result.id',
  parser_name VARCHAR(64) NOT NULL,
  parser_adapter_version VARCHAR(128) NOT NULL,
  pipeline_version VARCHAR(64) NOT NULL DEFAULT 'v1.1',
  metadata JSON,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  UNIQUE KEY uk_parse_result_run_content (run_uid, content_uid, parser_adapter_version),
  KEY idx_run_uid (run_uid),
  KEY idx_content_uid (content_uid),
  KEY idx_sha256 (sha256),
  KEY idx_status (status),
  KEY idx_retry_of (retry_of_result_id),
  CONSTRAINT fk_parse_result_run FOREIGN KEY (run_uid) REFERENCES kb_parse_run(run_uid),
  CONSTRAINT fk_parse_result_retry FOREIGN KEY (retry_of_result_id) REFERENCES kb_parse_result(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Per-content parse result within a run';
```

### 9.3 `kb_parsed_artifact`

```sql
CREATE TABLE IF NOT EXISTS kb_parsed_artifact (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  artifact_uid VARCHAR(64) NOT NULL UNIQUE,
  run_uid VARCHAR(64) NULL COMMENT 'PARSE_REPORT 等 run 级 artifact',
  content_uid VARCHAR(64) NULL,
  sha256 CHAR(64) NULL,
  artifact_type VARCHAR(64) NOT NULL,
  artifact_path TEXT NOT NULL,
  artifact_hash CHAR(64),
  artifact_size_bytes BIGINT,
  parser_name VARCHAR(64) NOT NULL,
  parser_adapter_version VARCHAR(128) NOT NULL,
  status VARCHAR(64) NOT NULL DEFAULT 'INDEXED',
  metadata JSON,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  UNIQUE KEY uk_artifact_content_type (content_uid, artifact_type, parser_name, parser_adapter_version),
  KEY idx_run_uid (run_uid),
  KEY idx_sha256 (sha256),
  KEY idx_artifact_type (artifact_type),
  CONSTRAINT fk_parsed_artifact_run FOREIGN KEY (run_uid) REFERENCES kb_parse_run(run_uid)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Parsed disk artifact index';
```

### 9.4 已有表写入（非 schema 变更）

| 表 | 操作 | 说明 |
|----|------|------|
| `kb_file_content` | UPDATE `parse_status` | §7 聚合规则 |
| `kb_document` | UPSERT | SUCCESS/EMPTY bridge；`parser_profile='markitdown_default_v1'` |
| `kb_parse_job`（init） | **不读写** | 保留给未来 queue |

### 9.5 `kb_document` bridge 映射（upsert）

| kb_document 列 | 来源 |
|----------------|------|
| `document_uid` | `sha256` 或 `f"{content_uid}:markitdown_default_v1"`（Dev 固定一种，QA 验证） |
| `content_uid` / `source_sha256` | result |
| `parser_name` / `parser_version` | manifest |
| `parser_profile` | 固定 `markitdown_default_v1` |
| `pipeline_version` | `v1.1` |
| `markdown_path` | `text_path` |
| `json_path` | `metadata_path` |
| `manifest_path` | `manifest_path` |
| `output_dir` | `parsed_dir` |
| `text_length` | `output_size_bytes` |
| `parse_status` | `PARSED` / `PARSED_EMPTY` |

---

## 10. 推荐 ORM Model 草案

**新文件**：`backend/app/models/parse_registry.py`

```python
class KbParseRun(Base): ...
class KbParseResult(Base): ...
class KbParsedArtifact(Base): ...
```

**关系**：

- `KbParseRun.results` → `KbParseResult[]`
- `KbParseResult.run` → `KbParseRun`
- `KbParseResult.retry_of` → optional `KbParseResult`
- `KbParsedArtifact.run` / `content_uid` optional

**现有 model 扩展**：

- `KbFileContent.parse_status` — 已存在于 `file.py`，registry service UPDATE
- 可选新增 `backend/app/models/document.py` 的 `KbDocument` — 若 init 尚无 ORM

字段必须与 migration SQL **一一对应**；Dev 不得 invent 列。

---

## 11. Migration 策略

| 项 | 决策 |
|----|------|
| 文件 | `sql/migrations/006_parse_registry_v1.sql` |
| 类型 | **Additive only**：CREATE TABLE IF NOT EXISTS |
| init SQL | **不修改** `sql/001_init_schema_v1_1.sql` |
| 破坏性操作 | **禁止** DROP / ALTER 001–005 表 |
| 回滚 | 提供 `006_parse_registry_v1_down.sql`（DROP 三表，仅测试环境；生产须 TL 批准） |
| 执行 | Dev 文档化 manual migrate；pytest 用 clean DB 或 migration fixture |
| 幂等 | `CREATE TABLE IF NOT EXISTS`；重复 migrate 不失败 |

**默认结论（Preflight → Plan）**：**需要 migration**；006 不能仅用 init SQL 已有表完成 MVP（缺少 run/result/artifact 三表语义）。

---

## 12. 与 Parsed Manifest / Parse Report 的映射

### 12.1 `parse_markitdown_report_*.json` → `kb_parse_run`

| report 字段 | run 列 |
|-------------|--------|
| `parser_adapter_version` | `parser_adapter_version` |
| `dry_run` | `dry_run` |
| `filters` | `filters_json` |
| `summary.total_candidates` | `total_candidates` |
| `summary.in_scope_candidates` | `in_scope_candidates` |
| `summary.parsed_count` | `parsed_count` |
| `summary.skipped_count` | `skipped_count` |
| `summary.failed_count` | `failed_count` |
| `summary.empty_count` | `empty_count` |
| 文件路径 | `report_path` |
| — | `parser_name='markitdown'` |
| — | `parser_family='MARKITDOWN_FAMILY'` |
| — | `trigger_type='REGISTER_REPORT'` |

### 12.2 report `items[]` + manifest → `kb_parse_result`

| 来源 | result 列 |
|------|-----------|
| item.content_uid / sha256 | `content_uid`, `sha256` |
| item.route_type / decision | `route_type`, `decision` |
| item.status | `status` |
| item.parsed_dir | `parsed_dir` |
| item.source_vault_path | `source_vault_path` |
| manifest.parsed_*_path | `text_path`, `metadata_path`, `manifest_path` |
| manifest.output_hash / output_size_bytes | `output_hash`, `output_size_bytes` |
| manifest.error / errors[] | `error_code`, `error_message` |

 ingest 时 **以 manifest 为准**（若磁盘存在）；report item 为 fallback。

### 12.3 manifest → `kb_parsed_artifact`

对每个 SUCCESS/EMPTY/FAILED content，索引 `PARSE_MANIFEST`；SUCCESS/EMPTY 额外索引 TEXT + METADATA。

---

## 13. 与 raw_vault / parsed 路径的关系

**raw_vault（002 两档 — 只读引用）**：

```text
{raw_vault_root}/by_hash/{sha256[0:2].lower()}/{sha256}/original.bin
```

- registry 仅 **存储** `source_vault_path` 字符串（来自 manifest）
- **禁止** open/write raw_vault

**parsed（005 三档 — 只读 ingest）**：

```text
{parsed_root}/by_hash/{sha256[0:2]}/{sha256[2:4]}/{sha256}/
  parsed_text.md
  parsed_metadata.json
  parse_manifest.json
```

- 路径 **必须**通过 `build_parsed_content_dir()` + `build_parsed_artifact_paths()` 校验
- reconcile 扫描时 glob `parsed_root/by_hash/*/*/*/parse_manifest.json`

---

## 14. CLI 设计

### 14.1 `register-parse-report`

```bash
python -m app.cli.main register-parse-report \
  --report-path PATH \
  [--config PATH] \
  [--dry-run]
```

| 行为 | 说明 |
|------|------|
| 读 report JSON | 创建/upsert `kb_parse_run` |
| 逐 item 读 manifest | upsert result + artifacts |
| dry-run | 预览 would_register；不写 DB |
| 幂等 | 同 `report_path` + version → upsert run，不 duplicate |

### 14.2 `list-parse-jobs`

```bash
python -m app.cli.main list-parse-jobs [--limit N] [--status STATUS] [--parser-name NAME]
```

列出 `kb_parse_run` 摘要。

### 14.3 `show-parse-job`

```bash
python -m app.cli.main show-parse-job --run-uid UID [--include-results] [--include-artifacts]
```

### 14.4 `list-parse-results`

```bash
python -m app.cli.main list-parse-results \
  [--run-uid UID] [--content-uid UID] [--sha256 HEX] [--status STATUS] [--limit N]
```

### 14.5 `list-parsed-artifacts`

```bash
python -m app.cli.main list-parsed-artifacts \
  [--content-uid UID] [--sha256 HEX] [--artifact-type TYPE] [--limit N]
```

### 14.6 `reconcile-parsed-artifacts`（opt-in）

```bash
python -m app.cli.main reconcile-parsed-artifacts \
  (--sha256 HEX | --content-uid UID | --limit N) \
  [--dry-run] [--config PATH]
```

| 护栏 | 行为 |
|------|------|
| 必须提供 filter 之一 | 否则 exit 1 |
| `--limit` 上限 | `PARSE_REGISTRY_MAX_LIMIT = 100` |
| 无 report | synthesize run（`trigger_type=RECONCILE`） |
| 不调用 MarkItDown | 只读 manifest |

### 14.7 保留 placeholder

- `build-parse-queue`、`parse` — 006 **不**完整实现；可在 plan 注明未来 consume `kb_parse_job`

---

## 15. 幂等策略

| 场景 | 行为 |
|------|------|
| 重复 `register-parse-report` 同一 report | upsert 同一 `run_uid`；results upsert by `uk_parse_result_run_content` |
| 同 content 新 run | 新 result 行；`parse_status` 取最新 |
| artifact 已存在同 type | upsert path/hash/size |
| dry-run | 零 INSERT |
| reconcile 同 manifest | upsert，不 duplicate artifact |

---

## 16. 重试策略

**MVP 记录，不自动重试解析**：

1. 新 result 写入时，若存在 **同 content_uid + parser_adapter_version** 且 **status=FAILED** 的上一条 result，则设 `retry_of_result_id` 指向前条 `id`。
2. **不**自动调用 005 re-parse；重试由人工再次 `parse-markitdown` + `register-parse-report`。
3. `retry_count` 可在 run.metadata 或 result.metadata 中冗余计数（可选）。

---

## 17. 历史 Parsed Reconcile 策略

| 项 | 决策 |
|----|------|
| 默认 | **不执行**；无 CLI 调用即无 reconcile |
| 触发 | 仅 `reconcile-parsed-artifacts` + 显式 filter |
| 扫描范围 | `parsed_root` 下 manifest 路径；按 sha256/limit 过滤 |
| 无 report | 创建 `trigger_type=RECONCILE` 的 run |
| 磁盘 | **只读**；不修改 manifest 内容 |
| 全库 | **禁止**（无 filter → exit 1） |

---

## 18. DB 事务策略

| 粒度 | 策略 |
|------|------|
| 单 content ingest | 一个 transaction：result + artifacts + document + parse_status |
| run 状态 | run 行在 batch 开始 INSERT；结束时 UPDATE summary + status |
| 单条失败 | rollback 当前 content transaction；记录 `errors[]`；continue |
| run 级失败 | rollback 整个 run（或 mark FAILED 并保留 partial — MVP 选 **mark FAILED**，已写入 results 保留） |
| dry-run | 无 transaction |

---

## 19. 数据一致性策略

1. **manifest 优先**：磁盘 manifest 与 report item 冲突时，以 manifest 为准。
2. **hash 校验**：artifact 文件存在则计算 SHA256；与 manifest `output_hash` 不一致 → result.metadata 记 `HASH_MISMATCH` warning，**不**改磁盘。
3. **content 必须存在**：`kb_file_content` 无对应 sha256 → result SKIPPED registry 或 error（Plan 裁决：**errors[] + skip**，不 INSERT result）。
4. **orphan manifest**：reconcile 发现 manifest 但无 DB content → warning only，不 INSERT。
5. **kb_document** 与 result 同步在同一 transaction。

---

## 20. 错误处理

| 错误 | code | 处理 |
|------|------|------|
| report 不存在/JSON 无效 | `INVALID_REPORT` | run FAILED；exit non-zero |
| manifest 缺失 | `MISSING_MANIFEST` | result FAILED；continue |
| manifest JSON 无效 | `INVALID_MANIFEST` | result FAILED；continue |
| artifact 路径不存在 | `MISSING_ARTIFACT` | artifact status=`MISSING`；result 仍登记 |
| content 不在 DB | `UNKNOWN_CONTENT` | errors[]；skip |
| DB 失败 | `DB_ERROR` | rollback 当前条；continue |
| dry-run | — | 无 write |

---

## 21. 测试策略

**文件**：`backend/tests/test_parse_registry.py`

| 类 | 覆盖 |
|----|------|
| migration | upgrade on clean DB；重复 idempotent |
| register report | run + results + artifacts + document |
| dry-run | 无 DB row |
| retry_of_result_id | 二次 register 失败→成功链 |
| reconcile | opt-in limit；no re-parse |
| 查询 CLI | list/show smoke |
| 保护 | no raw_vault/parsed mutation；005 regression |
| 幂等 | 重复 register 行数稳定 |

**全链路 E2E**：

```bash
scan → copy-to-vault → parse-markitdown --limit N → register-parse-report --report-path ...
```

**回归**：

```bash
pytest tests/test_markitdown_parser.py  # 005 不受影响
```

目标：006 新增 **≥25** test functions。

---

## 22. 验收标准

见 `acceptance.md` A001–A015；对照 `test_cases.md`。

---

## 23. Dev 白名单

| 操作 | 文件 |
|------|------|
| **新增** | `sql/migrations/006_parse_registry_v1.sql` |
| **新增** | `sql/migrations/006_parse_registry_v1_down.sql`（测试回滚，可选） |
| **新增** | `backend/app/models/parse_registry.py` |
| **新增** | `backend/app/models/document.py`（若尚无 KbDocument） |
| **新增** | `backend/app/services/parse_registry.py` |
| **新增** | `backend/app/core/parse_registry_mapping.py`（manifest/report 映射，可选） |
| **修改** | `backend/app/cli/main.py`（006 CLI 命令） |
| **新增** | `backend/tests/test_parse_registry.py` |
| **修改** | `specs/006-parse-job-registry/tasks.md`（勾选） |

**只读 import**：

- `backend/app/core/parsed_paths.py`
- `backend/app/core/vault_paths.py`
- `backend/app/models/file.py`

**禁止修改**：

- `backend/app/services/markitdown_parser.py`
- `backend/app/adapters/markitdown_adapter.py`
- `backend/app/services/inventory_scanner.py`
- `backend/app/services/file_content_vault.py`
- `backend/app/services/parser_router.py`
- `sql/001_init_schema_v1_1.sql`

---

## 24. 禁止路径

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
parsed/**（真实产物 — 测试用 tmp_path）
curated/**、quarantine/**、data/**
specs/001-*/** … specs/005-*/**
specs/006-parse-job-registry/plan.md   # Dev 不改 Plan
```

---

## 25. DB Plan Review 关注点

| 审查点 | 期望 |
|--------|------|
| migration additive | 仅 CREATE；无破坏性 ALTER |
| 与 init SQL 共存 | `kb_parse_job` 不混用；`kb_document` bridge 字段对齐 |
| 外键 | run_uid / retry_of 引用正确；删除策略 RESTRICT |
| 幂等 UNIQUE | run/report、result/run+content、artifact/content+type |
| parse_status 枚举 | 文档化；与 005 manifest 一致 |
| parser_profile | 固定 `markitdown_default_v1` |
| 事务 | 单 content 原子性 |
| 无 parser 调用 | grep 无 markitdown/mineru |
| pytest migration | clean DB + 重复 migrate |

---

## 26. E2E QA 关注点

**必查四项**：

1. 原始文件 stat/hash 不变  
2. raw_vault 不变  
3. 重复 register 幂等  
4. 单条 manifest 损坏 continue  

**006 专项**：

- register 后 run/result/artifact 行存在  
- kb_document + parse_status 正确  
- dry-run 无 write  
- reconcile 需显式 filter  
- 无 parsed/raw_vault 覆盖  
- 无 MinerU  
- 005 pytest 回归 pass  
- migration upgrade 测试 pass  

---

## 27. STOP 条件

| 条件 | 动作 |
|------|------|
| DB Plan Review BLOCKED | 不得 P5 Dev |
| Dev 需改 markitdown_parser.py | STOP → TL |
| Dev 需破坏性 migration | STOP → TL + DB |
| Dev 需默认全库 reconcile | STOP → TL |
| QA 不通过 | 不得 Handoff |
| 005 回归失败 | 交还 Dev |

---

## 28. 与后续 008 MinerU / PDF / OCR 的边界

| 项 | 006 | 008-mineru-parser |
|----|-----|-------------------|
| 解析执行 | ❌ | ✅ |
| registry ingest | ✅（parser-agnostic） | 完成后调用 register |
| parser_name | `markitdown` MVP | 未来 `mineru` |
| artifact 路径 | 005 三档 | 可能不同 layout；artifact_type 扩展 |

006 migration 设计须 **预留** `parser_name` / `parser_family` 枚举扩展，但 MVP 不实现 MinerU ingest 逻辑（可 accept manifest if present）。

**编号**：`specs/006-mineru-parser/` stub 重编号为 **`008-mineru-parser`**（TL 文档任务，非 006 Dev 范围）。

---

## 29. 与后续 curated / vector / project card 的边界

- 006 **不写** `kb_curated_asset`、`kb_embedding_ref`、`kb_document_chunk`。
- 006 仅提供 **parse_status + document path** 供 010+ / 011+ 消费。
- 无 LLM、无 Streamlit。

---

## 附录 A：TL 实现决策（Dev 必遵）

| # | 问题 | TL 决策 |
|---|------|---------|
| **Q1** | 业务 Parse Job 表名 | **`kb_parse_run`**（避免与 init `kb_parse_job` 冲突） |
| **Q2** | 005 衔接 | **`register-parse-report`**；不改 005 service |
| **Q3** | init `kb_parse_job` | **006 不写** |
| **Q4** | `kb_document` | **bridge upsert**（SUCCESS/EMPTY） |
| **Q5** | parser_profile | **`markitdown_default_v1`** |
| **Q6** | 默认 reconcile | **禁止**；须显式 CLI + filter |
| **Q7** | parsed 磁盘 | **只读** ingest |
| **Q8** | migration | **additive** `006_parse_registry_v1.sql` |
| **Q9** | dry-run | 不写 DB；run status `DRY_RUN_COMPLETED` 或不建 run |
| **Q10** | retry | 只记录 `retry_of_result_id`；不自动 re-parse |
| **Q11** | reconcile limit | **`PARSE_REGISTRY_MAX_LIMIT = 100`** |
| **Q12** | document_uid | **`content_uid`**（与 001 一致） |
| **Q13** | MinerU stub 编号 | 重编号 **008-mineru-parser**（文档，非 Dev） |
| **Q14** | registry report | 可选 `registry_report_{UTC}.json` |
| **Q15** | HASH mismatch | warning in metadata；不 fail entire run |

---

**Plan 结束** — STOP → **P2 DB Plan Review**（Implementation 门禁：DB PASS 后 Dev 方可 P5）。

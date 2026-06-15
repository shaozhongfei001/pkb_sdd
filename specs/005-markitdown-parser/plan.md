# Plan: MarkItDown 普通文档解析（005 实现计划）

> **项目**：个人历史项目文档知识库 `pkb_sdd`  
> **项目路径**：`/home/szf/dev/pyws/pkb_sdd`  
> **版本基线**：V1.1-SDD  
> **编写日期**：2026-06-15  
> **编写角色**：Tech Lead Agent — Plan Repair（步骤 ①）  
> **当前分支**：`feature/005-markitdown-parser-adapter`  
> **前置条件**：001–004 已完成；004 handoff 已读；DB Plan Review BLOCKED 项已在本 Plan 消除

---

## 1. 背景与 001–004 能力基线

Phase 1 进度：

```text
001 盘点 → 002 raw_vault → 003 重复治理 → 004 解析路由 → 【005 MarkItDown adapter】
```

| Spec | CLI | 能力 | 磁盘 | MySQL |
|------|-----|------|------|-------|
| **001** | `scan` | instance/content 登记、duplicate 标记 | inventory 报告 | 写 instance/content |
| **002** | `copy-to-vault` | 只读复制 → `original.bin` | `raw_vault/by_hash/...` | 写 vault 元数据 |
| **003** | `govern-duplicates` | sha256 重复组 + cleanup 建议 | duplicate / cleanup 报告 | upsert duplicate_group |
| **004** | `route-parsers` | `route_type` + `future_parser_hint` | `parser_route_report_*.json` | **只读** |

004 已实现（`parser_routing.py` / `parser_router.py`）：

- `RouteType` 九值枚举
- `match_route_type(file_ext, mime_type, fallback_ext)` — 确定性、不读 bin
- `ParserRouterService.route_parsers()` — 只读 MySQL + JSON 报告

004 **明确不做**：读 `original.bin`、MarkItDown/MinerU 调用、`parsed/` 写入、任何 DB 写。

005 是 **首个** 允许：读 vault bin、调用 MarkItDown、写 `parsed/` 的 Spec；同时 **延续** 004 的「005 不写 DB」边界，parse job registry **后置**。

---

## 2. 005 目标

1. 实现 **MarkItDown-family parser adapter MVP**（非通用 parser 框架）。
2. 对 `route_type ∈ {DOCX, PPTX, XLSX, TEXT_OR_MARKDOWN}` 的 vault 内容，只读解析 `original.bin`。
3. 写入标准 **parsed 三文件** + **`parse_markitdown_report_{UTC}.json`**。
4. 提供 CLI **`parse-markitdown`**，含批处理护栏与 `--dry-run`。
5. 幂等 skip；单条失败不中断；**零 DB 写、零 schema 变更**。

---

## 3. 005 非目标

| 非目标 | 说明 |
|--------|------|
| PDF / IMAGE / OCR / MinerU | → 006 |
| UNKNOWN / UNSUPPORTED 解析 | 跳过 |
| `kb_parse_job` / `kb_document` / `parse_status` | → **006-parse-job-registry** 或后续 Spec |
| SQL schema / migration | 005 默认禁止 |
| `curated/` / 向量库 / embedding / 项目卡 / Streamlit | 后续 Spec |
| quality-checker、chunk、review queue | 007 / 008 / 009 |
| 通用 `build-parse-queue` 框架 | 后续 Spec |
| `--force-reparse` | MVP 可不实现 |
| FastAPI | 后续 Spec |

---

## 4. 与 004 Parser Router 的关系

```text
004: metadata → route_type (memory / JSON report)
005: metadata → route_type (reuse match_route_type) → IF in-scope → read bin → MarkItDown → parsed/
```

| 维度 | 004 | 005 |
|------|-----|-----|
| 读 MySQL | 只读 | 只读 |
| 写 MySQL | 禁止 | **禁止** |
| 读 `original.bin` | 禁止 | **允许（只读）** |
| MarkItDown | 禁止 | **允许（adapter）** |
| `parsed/` | 禁止 | **允许** |
| route 来源 | 内嵌 `match_route_type()` | **复用同一函数**（import，不改规则） |
| 004 JSON 报告 | 产出 | **可选消费**（005 不依赖 DB route 持久化） |

**005 不得**修改 `parser_router.py` 行为或 004 路由规则表（除非 TL 另开 Spec）。005 只 **import** `RouteType`、`match_route_type`、`normalize_file_ext`、`ext_from_path`。

**`future_parser_hint` 与 005 范围**：004 中 `TEXT_OR_MARKDOWN` 的 hint 为 `DIRECT_TEXT`，但 005 MVP **仍解析**该 `route_type`（MarkItDown-family 轻量文本/markup）。005 以 **`route_type` 四值** 为准，不以 hint  alone 过滤。

---

## 5. 输入来源

### 5.1 MySQL metadata（只读）

| 表 | 字段用途 |
|----|----------|
| `kb_file_content` | `sha256`, `content_uid`, `file_ext`, `mime_type`, `vault_path`, `vault_status`, `status` |
| `kb_raw_vault_object` | `vault_path`, `vault_uid`, `sha256` |
| `kb_file_instance` | master instance 的 `file_name` / `source_path`（ext fallback，对齐 004） |

**候选 SQL 条件**：

```text
sha256 IS NOT NULL
AND status = 'CONTENT_REGISTERED'
AND vault_status = 'COPIED'
```

### 5.2 004 route rule 复用

```python
# 伪代码 — 005 service 内
route_type, decision, rule_name, hint, reason = match_route_type(
    file_ext=content.file_ext,
    mime_type=content.mime_type,
    fallback_ext=fallback_from_master_instance,
)
if decision != "ROUTE" or route_type not in IN_SCOPE_ROUTE_TYPES:
    → skip (report item status=SKIPPED)
```

```text
IN_SCOPE_ROUTE_TYPES = {DOCX, PPTX, XLSX, TEXT_OR_MARKDOWN}
```

### 5.3 raw_vault original.bin（002 权威 — 两档）

**P4 TL 裁决**：raw_vault 路径以 **002 实现** 为唯一权威；005 **不得**硬编码三档 raw_vault 路径；**不得**修改 `vault_paths.py` 或 `file_content_vault.py`；**不得**做 raw_vault 迁移。

**002 权威公式**：

```text
{raw_vault_root}/by_hash/{sha256[0:2].lower()}/{sha256}/original.bin
```

对应 002 实现（`backend/app/core/vault_paths.py`）：

```python
def build_vault_dir(raw_vault_root: Path, sha256: str) -> Path:
    prefix = sha256[:2].lower()
    return raw_vault_root / "by_hash" / prefix / sha256

def build_vault_artifact_paths(vault_dir: Path) -> VaultArtifactPaths:
    ...
    original_bin=vault_dir / "original.bin"
```

**005 必须**：

```python
vault_dir = build_vault_dir(config.storage.raw_vault_root, sha256)
original_bin = build_vault_artifact_paths(vault_dir)["original_bin"]
```

**005 service 允许**在 `markitdown_parser.py` 内封装私有方法（内部仍调用 002 helpers）：

```text
_resolve_vault_dir(raw_vault_root, sha256) -> Path
_resolve_original_bin(raw_vault_root, sha256) -> Path
```

**005 禁止**：

- 自行拼接 `{sha256[2:4]}/` 作为 raw_vault 中间目录（该扇出 **仅** 用于 `parsed/`，见 §8）
- 修改 `backend/app/core/vault_paths.py`
- 修改 `backend/app/services/file_content_vault.py`

DB `vault_path` 列可用于 **校验**（可选 WARNING：与 `build_vault_dir()` 不一致时 log，但 **解析输入仍以 helpers 为准**）。

文件必须以 **二进制只读** 打开；不得 truncate/write。

---

## 6. route_type 选择规则

| `route_type` | 005 | `decision` 要求 | 典型 ext |
|--------------|-----|-----------------|----------|
| DOCX | **解析** | ROUTE | `.docx` |
| PPTX | **解析** | ROUTE | `.pptx` |
| XLSX | **解析** | ROUTE | `.xlsx` |
| TEXT_OR_MARKDOWN | **解析** | ROUTE | `.txt` `.md` `.csv` `.html` `.htm` `.xml` `.json` |
| PDF_DIGITAL | **跳过** | — | `.pdf` |
| PDF_SCANNED_OR_IMAGE | **跳过** | — | — |
| IMAGE | **跳过** | — | 图片 ext |
| UNKNOWN | **跳过** | UNKNOWN | — |
| UNSUPPORTED | **跳过** | UNSUPPORTED | `.doc` 等 |

Skip 项写入 report `items[]`，`status=SKIPPED`，`skip_reason` 说明 route_type。

---

## 7. MarkItDown adapter 边界

### 7.1 分层

```text
CLI (main.py)
  → MarkItDownParserService (orchestration, batch, report, idempotency)
    → MarkItDownAdapter (thin wrapper around markitdown library)
      → third-party markitdown API
```

### 7.2 硬性规则

| 层 | 允许 | 禁止 |
|----|------|------|
| **CLI** | 参数解析、Rich 汇总、`ensure_readonly()` | `import markitdown` |
| **Service** | MySQL 只读、路径构建、幂等、报告、错误隔离 | 直接调用 markitdown |
| **Adapter** | `import markitdown`、convert 单文件、返回 text + metadata | MySQL、CLI、报告路径 |

### 7.3 Adapter 接口（建议）

```text
class MarkItDownAdapter:
    parser_adapter_version: str  # 常量，如 "005_mvp_v1"

    def convert(self, *, input_path: Path, route_type: RouteType) -> AdapterResult:
        """
        AdapterResult:
          text: str
          metadata: dict   # 供 parsed_metadata.json
          warnings: list[str]
        """
```

### 7.4 `parser_name` 常量

```text
parser_name = "markitdown"
parser_adapter_version = "005_mvp_v1"
```

---

## 8. parsed 目录结构（005 三档 — 与 raw_vault 两档独立）

> **路径区分（P4 TL 裁决）**：`raw_vault` 沿用 **002 两档**；`parsed/` 采用 **005 MVP 三档** 新约定。二者 **不得混用**。

```text
{parsed_root}/
  by_hash/
    {sha256[0:2]}/
      {sha256[2:4]}/
        {sha256}/
          parsed_text.md
          parsed_metadata.json
          parse_manifest.json
```

**说明**：

- parsed 使用 **三档** prefix（`[0:2]` + `[2:4]` + 完整 `sha256`）；由 `parsed_paths.py` 构建，**不**复用 `build_vault_dir()`
- **005 MVP 不使用** `parser_profile` 子目录；profile 信息写入 `parse_manifest.json` 字段
- 路径由 `parsed_root` + content `sha256` 确定性生成

**建议新增模块**：`backend/app/core/parsed_paths.py`

```text
def build_parsed_content_dir(parsed_root: Path, sha256: str) -> Path: ...
def build_parsed_artifact_paths(parsed_dir: Path) -> ParsedArtifactPaths: ...
```

---

## 9. parse_manifest.json 字段定义

每 content 一份，UTF-8 JSON。

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `content_uid` | string | ✅ | 与 sha256 一致（001 约定） |
| `sha256` | string | ✅ | 内容身份 |
| `route_type` | string | ✅ | DOCX / PPTX / XLSX / TEXT_OR_MARKDOWN |
| `parser_name` | string | ✅ | 固定 `"markitdown"` |
| `parser_adapter_version` | string | ✅ | 如 `"005_mvp_v1"` |
| `source_vault_path` | string | ✅ | `original.bin` 绝对或 config 相对路径 |
| `parsed_text_path` | string | ✅ | `parsed_text.md` 路径 |
| `parsed_metadata_path` | string | ✅ | `parsed_metadata.json` 路径 |
| `generated_at` | string | ✅ | ISO8601 UTC |
| `status` | string | ✅ | `SUCCESS` \| `SKIPPED` \| `FAILED` \| `EMPTY` |
| `content_size_bytes` | integer | ✅ | `original.bin` 字节数 |
| `input_metadata` | object | ✅ | 含 `file_ext`, `mime_type`, `rule_name`, `vault_uid`（可选） |
| `output_size_bytes` | integer | 条件 | `parsed_text.md` 字节数；`EMPTY` 时可为 0 |
| `output_hash` | string | 可选 | `parsed_text.md` 的 SHA256 |
| `error` | object | 失败时 | `{ "code": string, "message": string }` |

**幂等判定**：当 `parse_manifest.json` 存在且 `status=SUCCESS` 且 `parser_adapter_version` 一致 → 默认 **skip**（不覆盖三文件）。

---

## 10. parsed_metadata.json 字段定义

| 字段 | 类型 | 说明 |
|------|------|------|
| `parser_name` | string | `"markitdown"` |
| `parser_adapter_version` | string | `"005_mvp_v1"` |
| `route_type` | string | 同 manifest |
| `source_vault_path` | string | 输入 bin 路径 |
| `converted_at` | string | ISO8601 UTC |
| `library_version` | string | markitdown 包版本（adapter 读取 `__version__` 或等价） |
| `warnings` | string[] | adapter 警告 |
| `extra` | object | adapter 返回的非标准 metadata（可选） |

---

## 11. parsed_text.md 约定

| 规则 | 说明 |
|------|------|
| 编码 | **UTF-8**（无 BOM） |
| 格式 | Markdown 或 plain text（MarkItDown 输出） |
| 空输出 | 仍写文件（0 字节或仅换行）；`parse_manifest.json` 中 `status=EMPTY` |
| 失败（P4 TL） | **写** `parse_manifest.json`（`status=FAILED` + `error`）；**不写** `parsed_text.md`；**不写** `parsed_metadata.json`（MVP 允许省略，或写最小 stub — Dev 须在测试中固定一种；**推荐**：FAILED 时仅 manifest） |
| 原始文件 | 005 不修改 vault bin；parsed_text 是 **新文件** |

---

## 12. parse report JSON 结构

**路径**：`{reports_root}/parse_markitdown_report_{UTC}.json`  
**UTC 格式**：`%Y%m%dT%H%M%SZ`（与 001/003/004 对齐）

```json
{
  "report_type": "parse_markitdown_report",
  "parser_adapter_version": "005_mvp_v1",
  "pipeline_version": "v1.1",
  "generated_at": "2026-06-15T12:00:00Z",
  "dry_run": false,
  "filters": {
    "sha256": null,
    "content_uid": null,
    "limit": 10
  },
  "summary": {
    "total_candidates": 8,
    "in_scope_candidates": 5,
    "parsed_count": 2,
    "skipped_count": 3,
    "failed_count": 1,
    "empty_count": 0
  },
  "items": [
    {
      "content_uid": "<sha256>",
      "sha256": "<sha256>",
      "route_type": "DOCX",
      "status": "SUCCESS",
      "parsed_dir": ".../parsed/by_hash/...",
      "skip_reason": null
    }
  ],
  "errors": [
    {
      "content_uid": "<sha256>",
      "sha256": "<sha256>",
      "code": "MISSING_ORIGINAL_BIN",
      "message": "original.bin not found"
    }
  ]
}
```

| 字段 | 说明 |
|------|------|
| `total_candidates` | **MySQL 查询候选行数**（§5.1 条件 + CLI filter 后、route 过滤 **前**） |
| `in_scope_candidates` | route 过滤后 `route_type ∈ {DOCX,PPTX,XLSX,TEXT_OR_MARKDOWN}` 且 `decision=ROUTE` 的数量 |
| `parsed_count` | `status=SUCCESS` |
| `skipped_count` | out-of-scope route skip + 幂等 skip（**不计入** `--limit`） |
| `failed_count` | `status=FAILED` |
| `empty_count` | `status=EMPTY` |

**`--dry-run`（P4 TL）**：`dry_run=true`；**不调用** MarkItDownAdapter.convert；不写 parsed 三文件；仍执行 MySQL 候选查询、route 筛选、vault/parsed 路径解析、幂等判定；`items[]` 标注 would_parse / would_skip。

---

## 13. CLI 设计

```bash
python -m app.cli.main parse-markitdown [OPTIONS]
```

| 选项 | 说明 |
|------|------|
| `--config PATH` | 默认 `config/app.yaml` |
| `--sha256 HEX` | 仅处理指定内容 |
| `--content-uid UID` | 同 `--sha256` |
| `--limit N` | 最多执行 N 次 **in-scope parse 动作**（route 过滤后）；out-of-scope skip **不计入** limit |
| `--dry-run` | 不调用 MarkItDown；不写 parsed；仍写 report（would_parse / would_skip） |

**执行流程**：

1. 校验批处理护栏（§14）
2. `load_config` → `ensure_readonly()`
3. `MarkItDownParserService.parse_markitdown(...)`
4. Rich 打印 summary + report 路径

**保留命令**：`build-parse-queue`、`parse` 保持 placeholder（005 不实现通用 parse）。

---

## 14. 批处理护栏

### 14.1 禁止无限全库解析

**硬性规则**：以下三者 **至少提供一个**，否则 CLI **exit non-zero** 并提示：

```text
--sha256  或  --content-uid  或  --limit
```

### 14.2 `--limit` 上限

| 常量 | 值 |
|------|-----|
| `PARSE_MARKITDOWN_MAX_LIMIT` | **100** |

若 `--limit > 100` → 拒绝或 clamp 到 100（Plan 决策：**拒绝**并 exit non-zero，message 说明上限）。

### 14.3 `--dry-run`

- **不调用** `MarkItDownAdapter.convert()`（不 import/执行 markitdown 解析）
- 仍执行：MySQL 候选查询、route 筛选、vault/parsed 路径解析、幂等判定
- 不创建/不修改 `parsed/` 下任何文件
- 仍生成 `parse_markitdown_report_*.json`（`items[]` 标注 would_parse / would_skip）

### 14.4 单条失败不中断

- adapter / IO 异常 → 该 content `FAILED` + `errors[]`
- 继续处理 batch 内其余 content

---

## 15. 幂等策略

| 场景 | 行为 |
|------|------|
| 路径确定性 | `{parsed_root}/by_hash/{sha256[0:2]}/{sha256[2:4]}/{sha256}/` 仅由 `sha256` 决定 |
| 版本键 | `parser_adapter_version` 写入 manifest；MVP 路径 **不含** version 子目录 |
| 已成功 | `parse_manifest.json` 存在且 `status=SUCCESS` 且 version 一致 → **skip**，不覆盖三文件 |
| 曾失败 | 无 SUCCESS manifest → **允许**重试（覆盖 FAILED 产物 — MVP 允许） |
| `--dry-run` | 不检查 skip 写盘，但 report 标注 `would_skip` |
| raw_vault | **永不**覆盖 |
| `--force-reparse` | **005 MVP 不实现** |

---

## 16. 错误隔离

| 错误类型 | `error.code` 建议 | 处理 |
|----------|-------------------|------|
| parser import error | `PARSER_IMPORT_ERROR` | 该条 FAILED；若全局 import 失败则整命令 exit non-zero |
| parser runtime error | `PARSER_RUNTIME_ERROR` | FAILED + continue |
| corrupted document | `CORRUPTED_DOCUMENT` | FAILED + continue |
| password protected | `PASSWORD_PROTECTED` | FAILED + continue |
| empty output | — | `status=EMPTY`（非 FAILED） |
| missing original.bin | `MISSING_ORIGINAL_BIN` | FAILED + continue |
| unsupported route_type | — | SKIPPED（非 error） |
| ext/mime conflict (UNKNOWN) | — | SKIPPED |
| vault path missing | `MISSING_VAULT_PATH` | FAILED + continue |
| parsed dir not writable | `OUTPUT_NOT_WRITABLE` | 全局失败 exit non-zero |

所有 FAILED 必须：`errors[]` + item 记录 + 日志 ERROR。

---

## 17. raw_vault 保护

- 只读 open `original.bin`；禁止 `write`/`truncate`/`unlink`/`rename`
- 禁止 create/delete/overwrite `raw_vault/**` 任意文件
- 禁止修改 sidecar JSON（`source_paths.json`、`file_metadata.json`）
- QA：parse 前后 vault listing + `original.bin` SHA256 不变

---

## 18. 原始文件保护

- 005 **不得**以用户 `source_path` 作为解析输入
- 不得 delete/move/rename/overwrite 原始用户文件
- CLI 入口 `ensure_readonly()`
- QA：fixtures 全链路 stat/hash 不变

---

## 19. DB / schema 策略

### 19.1 005 默认策略（硬性）

```text
005 不改 SQL schema。
005 不写 DB。
005 不写 kb_parse_job。
005 不写 kb_document。
005 不更新 parse_status。
```

005 对 MySQL **仅 SELECT**。Dev/QA 须 grep + 测试断言 **无** INSERT/UPDATE/DELETE on business tables。

### 19.2 后续 Spec（非 005）

| 能力 | 建议 Spec |
|------|-----------|
| `kb_parse_job` upsert | **006-parse-job-registry** 或独立 Spec |
| `kb_document` + `parse_status` | 同上 |
| schema 变更 | TL + migration + DB 授权 |

### 19.3 DB Review 风险（Plan 阶段）

- Dev 不得因「方便追踪」私自 upsert job 表
- 若实现中发现必须写 DB → **STOP → TL**，不得自行改 schema

---

## 20. 依赖策略

| 项 | Plan 决策（P4 TL） |
|----|-------------------|
| MarkItDown | 项目 `backend/requirements.txt` 已含 `markitdown[all]>=0.1.0` |
| 新增 PyPI 包 | **005 MVP 默认不新增** |
| `requirements.txt` | **P5 默认不修改**；Dev 第一步验证该条目存在 |
| 若依赖缺失 | Dev **STOP → TL** 重新批准依赖策略；**不得**自行改 requirements |
| Office 运行时 | docx/pptx/xlsx 可能依赖系统库；**pytest 默认 mock adapter** |
| 真实 markitdown 集成测试 | **仅限**轻量 `.txt` / `.md` fixture（可选 1–2 个）；Office 用 mock |

---

## 21. Dev 白名单

| 操作 | 文件 |
|------|------|
| **新增** | `backend/app/core/parsed_paths.py` |
| **新增** | `backend/app/adapters/markitdown_adapter.py` |
| **新增** | `backend/app/services/markitdown_parser.py`（含 `_resolve_vault_dir` / `_resolve_original_bin`） |
| **修改** | `backend/app/cli/main.py`（新增 `parse-markitdown`） |
| **新增** | `backend/tests/test_markitdown_parser.py` |
| **修改** | `specs/005-markitdown-parser/tasks.md`（勾选） |

**P5 默认禁止修改**：

- `backend/requirements.txt`（除非 TL 重新批准依赖策略）

**只读 import（禁止修改文件内容）**：

- `backend/app/core/parser_routing.py`
- `backend/app/core/vault_paths.py`（**P4：禁止修改**）
- `backend/app/core/config.py`

---

## 22. 禁止修改路径

```text
backend/app/services/inventory_scanner.py
backend/app/services/file_content_vault.py   # P4：禁止修改
backend/app/services/duplicate_governance.py
backend/app/services/parser_router.py
backend/app/core/vault_paths.py              # P4：禁止修改；005 只读 import
backend/app/core/parser_routing.py           # 005 只读 import，禁止改规则
backend/requirements.txt                     # P5 默认禁止；须 TL 重新批准
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
specs/005-markitdown-parser/plan.md     # Dev 不改 Plan
specs/其他编号/**
```

---

## 23. 测试策略

### 23.1 pytest 文件

`backend/tests/test_markitdown_parser.py`

| 用例类 | 覆盖 |
|--------|------|
| route 筛选 | DOCX/PPTX/XLSX/TEXT 进入；PDF/IMAGE/UNKNOWN/UNSUPPORTED skip |
| vault 路径 | `_resolve_original_bin` 经 `build_vault_dir` + `build_vault_artifact_paths`；**禁止**三档 raw_vault |
| adapter | **默认 mock** `MarkItDownAdapter.convert`；import failure |
| 真实 markitdown | **仅**轻量 `.txt`/`.md` 集成（可选）；Office 一律 mock |
| 产物路径 | parsed 三档 §8；raw_vault 两档 §5.3 |
| manifest 字段 | §9 必填；FAILED 仅 manifest |
| 幂等 | 第二次 SUCCESS skip |
| dry-run | 无 MarkItDown 调用；无 parsed 写入 |
| limit 语义 | out-of-scope skip 不计入 limit |
| 护栏 | 无 filter → exit non-zero；limit > 100 → reject |
| 保护 | original + raw_vault 不变；vault_paths.py 未改 |
| 无 DB 写 | mock session 或 SQL 计数 |
| 中文路径 | fixtures 全链路 |

### 23.2 CLI E2E

```bash
python -m app.cli.main scan --path backend/tests/fixtures
python -m app.cli.main copy-to-vault
python -m app.cli.main parse-markitdown --limit 10
```

### 23.3 全链路回归

```bash
pytest -q tests/test_inventory_scanner.py tests/test_file_content_vault.py \
  tests/test_duplicate_governance.py tests/test_parser_router.py \
  tests/test_markitdown_parser.py
```

目标：005 新增 **≥20** test functions。

---

## 24. 验收标准

见 `acceptance.md` A001–A017；对照 `test_cases.md`。

---

## 25. DB & Data Review 关注点

### 25.1 Plan Review（当前阶段）

| 审查点 | 期望 |
|--------|------|
| Plan 是否明确 **不写 DB** | ✅ 本文 §19 |
| 是否存在「写入 parse result / parse_status / kb_parse_job」歧义 | **已删除** |
| schema 变更是否仅为「非目标 / 后续 Spec」 | ✅ §3、§19.2 |
| 批处理护栏是否可执行 | ✅ §14 |
| 幂等 / 错误隔离是否可测 | ✅ §15–§16 |

### 25.2 Implementation Review（Dev 后）

| 审查点 | 期望 |
|--------|------|
| ORM / session 无 INSERT/UPDATE/DELETE | 仅 SELECT |
| 无新增 `models/parse.py` 写库逻辑 | 005 不应新增 DB model |
| 无 migration 文件 |
| `parse_status` 列不被 UPDATE |
| pytest 含 no-DB-write 断言 |

---

## 26. E2E QA 关注点

**必查四项**（协作规范）：

1. 原始文件 stat/hash 不变  
2. raw_vault `original.bin` 不变  
3. 重复执行幂等（SUCCESS skip）  
4. 单条失败 continue  

**005 专项**：

- 仅 DOCX/PPTX/XLSX/TEXT_OR_MARKDOWN 产生 parsed  
- PDF/IMAGE skip  
- manifest 追溯 content_uid / sha256 / source_vault_path  
- `--dry-run` 不写 parsed  
- 护栏：无 filter 失败；limit 上限  
- grep：无 `kb_parse_job` / `kb_document` / `parse_status` 写操作  
- 无 MinerU import  
- report summary 计数与 items 一致  

---

## 27. STOP 条件

| 条件 | 动作 |
|------|------|
| Dev 发现必须写 DB 才能满足需求 | **STOP → TL**（开 006-parse-job-registry） |
| Dev 需改 `parser_routing.py` 规则 | **STOP → TL** |
| Dev 需改 SQL schema | **STOP → TL + DB** |
| Dev 需接 MinerU 处理 PDF | **STOP → TL**（属 006） |
| Plan Review BLOCKED | 不得进入 Dev（**本次 Repair 目标：解除**） |
| DB Implementation Review 不通过 | 不得进入 QA |
| QA 不通过 | 不得 Handoff / merge |

---

## 28. 与 006 / 007 后续边界

| Spec | 职责 |
|------|------|
| **005（本 Spec）** | MarkItDown adapter；parsed 磁盘三文件；parse report；**无 DB** |
| **006-mineru-parser** | MinerU；PDF/IMAGE；parsed 磁盘（可能不同 manifest 约定） |
| **006-parse-job-registry**（建议名） | `kb_parse_job` / `kb_document` / `parse_status`；**005 不做** |
| **007-quality-checker** | 读 parsed 产物；quality_score；可能触发 MinerU 重解析 |

005 产出的 `parse_manifest.json` 设计应便于 006-registry **未来** ingest，但 005 **不**写 DB。

---

## 附录 A：TL 实现决策（Dev 必遵）

| # | 问题 | TL 决策 |
|---|------|---------|
| **Q1** | CLI 命令名 | **`parse-markitdown`** |
| **Q2** | adapter 路径 | **`backend/app/adapters/markitdown_adapter.py`**（优先 adapters 包） |
| **Q3** | parsed 路径 | **§8 三文件结构**（无 parser_profile 子目录） |
| **Q4** | DB 写入 | **禁止**（§19） |
| **Q5** | 批处理护栏 | 必须提供 `--sha256` / `--content-uid` / `--limit` 之一；`limit ≤ 100` |
| **Q6** | 失败时 parsed_text | **不写** text 文件（仅 manifest/report） |
| **Q7** | TEXT_OR_MARKDOWN | **纳入** 005（含 html/xml/json/txt/md/csv） |
| **Q8** | `--force-reparse` | **MVP 不实现** |
| **Q9** | 全局 import 失败 | exit non-zero；不 partially write parsed |
| **Q10** | raw_vault 路径 | **002 两档**；`build_vault_dir` + `build_vault_artifact_paths`；禁止三档 raw_vault |
| **Q11** | parsed 路径 | **005 三档** §8；与 raw_vault 独立 |
| **Q12** | FAILED 产物 | 写 `parse_manifest.json`（FAILED+error）；**不写** `parsed_text.md` |
| **Q13** | `--limit` | 仅 in-scope parse 动作；out-of-scope skip 不计入 |
| **Q14** | `--dry-run` | 不调用 MarkItDown；仍做路由/路径/幂等/report |
| **Q15** | 测试策略 | 默认 mock adapter；真实 markitdown 仅 txt/md |
| **Q16** | report 计数 | `total_candidates`=SQL 行数；增 `in_scope_candidates` |
| **Q17** | requirements.txt | P5 **默认不改**；缺失则 STOP → TL |

---

**Plan 结束** — P4 TL 已批准 → **P5 Dev Implementation**。

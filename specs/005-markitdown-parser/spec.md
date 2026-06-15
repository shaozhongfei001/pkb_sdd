# Spec: MarkItDown 普通文档解析（005-markitdown-parser）

> **项目**：个人历史项目文档知识库 `pkb_sdd`  
> **版本基线**：V1.1-SDD  
> **前置条件**：001-file-inventory、002-file-content-vault、003-duplicate-governance、004-parser-router 已完成  
> **详细实现计划**：见同目录 `plan.md`  
> **定位**：MarkItDown-family **parser adapter** MVP — 非通用 parser 框架

---

## 1. 背景

Phase 1 文件治理底座进度：

```text
001 盘点 → 002 raw_vault → 003 重复治理 → 004 解析路由 → 【005 MarkItDown 解析执行】→ 006 MinerU …
```

001–002 已将用户文档登记为 `kb_file_instance` / `kb_file_content`，并将唯一内容只读复制到 `raw_vault/by_hash/.../original.bin`。

003 已对 sha256 精确重复做元数据治理（只出报告，不执行清理）。

004 已基于 MySQL 元数据产出 `route_type` 与 `future_parser_hint`，**不执行解析、不写 parsed、不写 DB**。

005 是 Phase 1 **首次允许**调用 MarkItDown-family 解析器、读取 `raw_vault/original.bin`、写入 `parsed/` 的 Spec。005 只做 **轻量 Office / 文本 / markup 类文档** 的 Markdown 转换，**不做 DB 持久化**。

---

## 2. 用户故事

| 角色 | 故事 | 验收要点 |
|------|------|----------|
| **文档管理员** | 对已入 vault 的 `.docx/.pptx/.xlsx` 执行解析，得到可检索 Markdown 文本 | `parsed_text.md` 存在且 UTF-8 |
| **文档管理员** | 对 `.txt/.md/.csv/.html/.xml/.json` 执行轻量转换 | `route_type=TEXT_OR_MARKDOWN` 可解析 |
| **文档管理员** | 解析结果必须能追溯到 vault 原文 | `parse_manifest.json` 含 `content_uid`、`sha256`、`source_vault_path` |
| **文档管理员** | 重复执行不应破坏已有成功产物 | 幂等 skip |
| **文档管理员** | PDF/图片不应被本命令误解析 | 明确 skip，不调用 MinerU |
| **运维** | 批处理必须有上限，不能无意全库跑解析 | `--sha256` / `--content-uid` / `--limit` 护栏 |
| **DB 审查员** | 005 不得写入 MySQL 业务表 | 无 INSERT/UPDATE/DELETE |

---

## 3. 目标

1. 从 **raw_vault** 只读读取 `original.bin`，对 MarkItDown-family 候选内容生成 **parsed text** 产物。
2. 覆盖 `route_type`：**DOCX、PPTX、XLSX、TEXT_OR_MARKDOWN**。
3. 写入标准 **parsed 目录结构**（见 `plan.md` §8）：`parsed_text.md`、`parsed_metadata.json`、`parse_manifest.json`。
4. 输出 **`parse_markitdown_report_{UTC}.json`** 到 `reports_root`。
5. 提供 Typer CLI **`parse-markitdown`**（含 `--dry-run`）。
6. 保持幂等；单 content 失败不中断批处理；**不写 DB、不改 SQL schema**。

**005 的核心能力**：在原始文件与 raw_vault 均受保护的前提下，从 vault 副本 **安全生成** 可追溯到 `content_uid` / `sha256` 的 parsed text 产物。

---

## 4. 范围（005 MVP 包含）

| 项 | 说明 |
|----|------|
| MarkItDown adapter | 包装 MarkItDown-family 解析能力；CLI 不直接耦合第三方库 |
| `MarkItDownParserService` | 批处理编排：候选筛选 → adapter 调用 → 产物写入 → 报告 |
| MySQL **只读**查询 | 读取 `kb_file_content`、`kb_raw_vault_object`（及 ext fallback 所需的 `kb_file_instance`） |
| 004 route rule **复用** | 复用 `match_route_type()` / `RouteType`（只读 import，不改 004 模块行为） |
| raw_vault 只读输入 | `{raw_vault_root}/by_hash/{sha256[0:2].lower()}/{sha256}/original.bin`（**002 两档**；须经 `vault_paths.py` 解析，禁止 005 自行拼接） |
| parsed 磁盘产物 | `parsed/` 下三文件结构 |
| JSON 报告 | `parse_markitdown_report_{UTC}.json` |
| CLI `parse-markitdown` | `--config`、`--sha256`、`--content-uid`、`--limit`、`--dry-run` |
| pytest + CLI E2E | 见 `test_cases.md` |

**005 MVP 不包含、不得执行**：

- 向 MySQL **写入**任何记录（含 `kb_parse_job`、`kb_document`、`parse_status` 更新）
- 修改 SQL schema / migration
- MinerU、OCR、PDF/图片解析
- `curated/`、`quarantine/`、向量库、embedding、项目卡蒸馏、Streamlit
- 通用 parser 框架、`build-parse-queue` 完整实现、quality-checker（007）

---

## 5. 非目标（005 明确不做）

| 非目标 | 说明 | 归属 |
|--------|------|------|
| PDF / 图片 / 扫描件解析 | `PDF_DIGITAL`、`PDF_SCANNED_OR_IMAGE`、`IMAGE` | 006-mineru-parser |
| UNKNOWN / UNSUPPORTED | 跳过并记入报告 | — |
| DB parse job registry | `kb_parse_job` upsert | **006-parse-job-registry** 或后续独立 Spec |
| DB document registry | `kb_document` upsert | 同上 |
| `parse_status` 更新 | `kb_file_content.parse_status` | 同上 |
| SQL schema 变更 | init SQL / migration | 须单独 Spec + DB 授权 |
| 质量检查 / 低质量重解析 | quality_score、MinerU 回退 | 007-quality-checker |
| chunk / embedding / 检索 | `kb_document_chunk` 等 | 009 / 011 |
| FastAPI 暴露 | HTTP API | 后续 Spec |
| `--force-reparse` | 覆盖已有成功产物 | 005 MVP 可不实现 |

---

## 6. 数据流

```text
001 scan → 002 copy-to-vault → 003 govern-duplicates（可选）→ 004 route-parsers（可选，报告参考）
  → 005 parse-markitdown
    MySQL 只读（kb_file_content + kb_raw_vault_object [+ kb_file_instance fallback]）
    → match_route_type() 筛选 DOCX|PPTX|XLSX|TEXT_OR_MARKDOWN
    → 只读 open raw_vault/.../original.bin
    → MarkItDownAdapter.convert()
    → parsed/by_hash/.../parsed_text.md + parsed_metadata.json + parse_manifest.json
    → reports_root/parse_markitdown_report_{UTC}.json
```

**005 磁盘写入**：`parsed/**`（三文件结构）、`reports_root/parse_markitdown_report_*.json`。  
**005 不写入**：`raw_vault/`、`curated/`、`quarantine/`、MySQL 任何表。

---

## 7. 输入（只读）

### 7.1 MySQL 表操作边界

| 表 | 005 操作 |
|----|----------|
| `kb_file_content` | **只读**（主输入） |
| `kb_raw_vault_object` | **只读**（补全 `vault_path`） |
| `kb_file_instance` | **只读**（`file_ext` fallback，对齐 004） |
| `kb_parse_job` | **不读写** |
| `kb_document` | **不读写** |

**默认候选条件**：

```text
kb_file_content.sha256 IS NOT NULL
AND kb_file_content.status = 'CONTENT_REGISTERED'
AND kb_file_content.vault_status = 'COPIED'
```

CLI 过滤：`--sha256`、`--content-uid`、`--limit`（见 `plan.md` §13–§14）。

**005 不以 `parse_status` 作为硬过滤**（005 不更新该字段；字段值仅可在报告中只读透传，若 Dev 实现选择附带）。

### 7.2 raw_vault 输入（002 权威路径）

- 唯一解析输入文件：`original.bin`（只读）
- **权威公式（002 两档）**：

```text
{raw_vault_root}/by_hash/{sha256[0:2].lower()}/{sha256}/original.bin
```

- **必须**通过 002 已实现 helpers 解析（只读 import，**禁止修改** `vault_paths.py`）：

```text
vault_dir = build_vault_dir(config.storage.raw_vault_root, sha256)
original_bin = build_vault_artifact_paths(vault_dir)["original_bin"]
```

- 005 service 可在 `markitdown_parser.py` 内封装私有方法 `_resolve_vault_dir(...)`、`_resolve_original_bin(...)`，内部 **必须** 调用上述 002 helpers
- **禁止**硬编码 raw_vault 三档路径 `{sha256[2:4]}/`（该结构 **仅** 用于 `parsed/`，见 §8.1）
- **禁止** raw_vault 迁移；**禁止**修改 `file_content_vault.py`
- **禁止**以用户 `source_path` 作为 parse 输入

### 7.3 004 route 复用

- 复用 `backend/app/core/parser_routing.py` 中 `match_route_type()` 与 `RouteType`
- 仅当 `route_type ∈ {DOCX, PPTX, XLSX, TEXT_OR_MARKDOWN}` 且 `decision=ROUTE` 时进入解析
- 004 JSON 报告 **可选参考**；005 **不依赖** DB 中持久化 route（004 未写 DB）

---

## 8. 输出

### 8.1 parsed 产物（每 content 一组）

```text
{parsed_root}/by_hash/{sha256[0:2]}/{sha256[2:4]}/{sha256}/
  parsed_text.md
  parsed_metadata.json
  parse_manifest.json
```

字段定义见 `plan.md` §9–§11。

### 8.2 批处理报告

```text
{reports_root}/parse_markitdown_report_{UTC}.json
```

结构见 `plan.md` §12。

---

## 9. route_type 覆盖规则

| `route_type` | 005 行为 | 典型扩展名 |
|--------------|----------|------------|
| **DOCX** | 解析 | `.docx` |
| **PPTX** | 解析 | `.pptx` |
| **XLSX** | 解析 | `.xlsx` |
| **TEXT_OR_MARKDOWN** | 解析 | `.txt` `.md` `.csv` `.html` `.htm` `.xml` `.json` |
| PDF_DIGITAL | **跳过** | `.pdf` |
| PDF_SCANNED_OR_IMAGE | **跳过** | — |
| IMAGE | **跳过** | 图片扩展名 |
| UNKNOWN | **跳过** | — |
| UNSUPPORTED | **跳过** | `.doc` 等 |

---

## 10. 业务规则

1. **原始文件只读**：005 不 open 用户原始路径进行 write；不 `move`/`unlink`/`rename` 原始文件。
2. **raw_vault 只读**：只读 `original.bin`；不 create/delete/overwrite raw_vault 下任何文件。
3. **不写 DB**：005 对 MySQL 仅 SELECT；禁止 INSERT/UPDATE/DELETE。
4. **批处理护栏**：不得在无 `--sha256`/`--content-uid`/`--limit` 的情况下无限全库解析（见 `plan.md` §14）。
5. **幂等**：同 `sha256` + `parser_adapter_version` + `route_type` 路径稳定；已有成功产物默认 skip。
6. **单条失败 continue**：失败记入 report `errors[]` 与 item `status=FAILED`；**可写** `parse_manifest.json`（`status=FAILED` + `error`），**不写** `parsed_text.md`。
7. **可追溯**：所有成功/失败/跳过 item 必须含 `content_uid` 与 `sha256`。
8. CLI 入口调用 `ensure_readonly()`。
9. **`--limit`**：仅限制 **in-scope** 的 parse 动作次数；out-of-scope skip **不计入** limit。
10. **`--dry-run`**：不调用 MarkItDown；不写 `parsed/`；执行候选查询、路由、路径解析、幂等判定；report 反映 would_parse / would_skip。

---

## 11. 硬约束清单（Dev / QA 必遵）

1. 005 **只做** MarkItDown-family adapter MVP。
2. 005 **只解析** DOCX / PPTX / XLSX / TEXT_OR_MARKDOWN。
3. 005 **跳过** PDF / IMAGE / UNKNOWN / UNSUPPORTED。
4. 005 **读取** raw_vault `original.bin`（只读）。
5. 005 **写入** `parsed/` 三文件结构 + `parse_markitdown_report_*.json`。
6. 005 **不写** MySQL（无 `kb_parse_job` / `kb_document` / `parse_status`）。
7. 005 **不改** SQL schema。
8. 005 **不接** MinerU / OCR。
9. 005 **不写** `curated/` / 向量库 / 项目卡。
10. 005 **不删除/移动/覆盖** raw_vault 与原始文件。
11. CLI **必须有** `--sha256` / `--content-uid` / `--limit` 护栏。
12. 若实现发现必须写 DB → **STOP → TL**（开后续 Spec，不得 Dev 自行 upsert）。

---

## 12. 与 004 / 006 / 007 的边界

| 阶段 | 职责 |
|------|------|
| **004** | 元数据路由决策 + `parser_route_report_*.json`；不读 bin、不解析 |
| **005（本 Spec）** | MarkItDown-family 解析执行；读 vault bin；写 parsed 磁盘 + parse report；**不写 DB** |
| **006** | MinerU-family；PDF/IMAGE |
| **006-parse-job-registry（后续）** | `kb_parse_job` / `kb_document` / `parse_status` 持久化 |
| **007** | quality-checker |

004 的 `future_parser_hint=MARKITDOWN_FAMILY` 仅作 **参考**；005 以 **`route_type` 四值集合** 为准（含 `TEXT_OR_MARKDOWN`，其 hint 为 `DIRECT_TEXT`）。

---

## 13. 依赖

- MarkItDown Python 包：见 `plan.md` §20（Dev 阶段检查 `backend/requirements.txt`；Plan Repair 不安装）。
- 不新增 MinerU、OCR、向量库依赖。

---

**Spec 结束** — 实现细节见 `plan.md`；任务见 `tasks.md`；验收见 `acceptance.md`。

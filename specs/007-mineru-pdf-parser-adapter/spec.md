# Spec: MinerU PDF Parser Adapter（007-mineru-pdf-parser-adapter）

> **项目**：个人历史项目文档知识库 `pkb_sdd`  
> **版本基线**：V1.1-SDD  
> **前置条件**：001–006 已完成并 merge `main`（含 `006-parse-job-registry` migration 已手动执行）  
> **详细实现计划**：见同目录 `plan.md`  
> **定位**：MinerU-family **PDF parser adapter** MVP — 非通用 OCR 平台、非 curated / vector 阶段

---

## 1. 背景与目标

### 1.1 Phase 1 进度

```text
001 盘点 → 002 raw_vault → 003 重复治理 → 004 解析路由
  → 005 MarkItDown 解析 → 006 Parse Job Registry
  → 【007 MinerU PDF Parser Adapter】
```

001–002 已将用户文档登记为 `kb_file_content`，并将唯一内容只读复制到 `raw_vault/by_hash/.../original.bin`。

004 已基于元数据产出 `route_type`；`.pdf` 映射为 `PDF_DIGITAL`，`future_parser_hint=MINERU_FAMILY`。

005 是 Phase 1 **首个**允许调用 MarkItDown、读取 vault、写入 `parsed/` 的 Spec，但 **明确跳过** 所有 PDF / IMAGE route（见 handoff §4）。

006 在 **不执行解析** 的前提下，将 005 磁盘产物索引到 MySQL（`kb_parse_run` / `kb_parse_result` / `kb_parsed_artifact`），并更新 `parse_status` / `kb_document` bridge。

007 填补 **PDF 解析执行** 缺口：对 router 判定为 PDF 的 vault 内容调用 MinerU，在 `parsed/` 下生成与 005 **路径兼容** 的标准产物，并可 **可选** 通过 006 registry 登记 parse lifecycle。

### 1.2 为什么 005 不处理 PDF

| 原因 | 说明 |
|------|------|
| **解析器能力边界** | MarkItDown-family 面向 Office / 文本 / markup 轻量转换；对 PDF 版面、扫描件、嵌入图片表格的支持不足 |
| **004 路由语义** | `.pdf` → `PDF_DIGITAL`，`future_parser_hint=MINERU_FAMILY`；005 `IN_SCOPE` 仅四值 Office/text |
| **资源与复杂度** | PDF / 扫描件解析依赖 MinerU（布局分析 + OCR），运行时间与磁盘占用远高于 MarkItDown |
| **Spec 隔离** | 005 handoff 将 PDF/IMAGE/OCR 明确归属 MinerU 独立 Spec，避免 005 scope 膨胀 |

### 1.3 为什么 007 独立处理 MinerU / PDF

| 原因 | 说明 |
|------|------|
| **专用 adapter** | MinerU 通过外部 CLI / SDK、临时目录、assets 子树，与 MarkItDown adapter 分层不同 |
| **窄范围 MVP** | 007 只做 PDF in-scope；不做 IMAGE 独立文件、不做 Office、不做全库默认解析 |
| **可并行演进** | 005 / 006 已 merge 并封闭；007 新增 service + adapter，不修改 `markitdown_parser.py` |
| **registry 可衔接** | 006 表结构已预留 `parser_name` / `parser_family` 扩展；007 产出兼容 report 可被 ingest |

### 1.4 与 006 Registry 的关系

| 维度 | 007 默认 | 007 `--register` |
|------|----------|------------------|
| 写 parsed 磁盘 | ✅ | ✅ |
| 写 parse report | ✅ | ✅ |
| 写 MySQL registry | ❌ | ✅（经 `ParseRegistryService`，**不修改 006 schema**） |
| dry-run | 零 MinerU / 零 parsed / 零 DB | 同左 |

**推荐流水线**：

```text
007 parse-mineru-pdf --limit N
  → parse_mineru_pdf_report_{UTC}.json
  →（可选）007 --register 或 006 register-parse-report --report-path ...
```

---

## 2. 用户故事

| 角色 | 故事 | 验收要点 |
|------|------|----------|
| **文档管理员** | 对已入 vault 的 PDF 执行 MinerU 解析，得到 Markdown 与可追溯 manifest | `parsed_text.md` + `parse_manifest.json` |
| **文档管理员** | PDF 解析结果必须能追溯到 vault 原文 | manifest 含 `content_uid`、`sha256`、`source_vault_path` |
| **文档管理员** | 重复执行不应破坏已有成功产物 | 默认幂等 skip；`--force` 显式覆盖 |
| **文档管理员** | Office 文档不应被本命令误解析 | 非 PDF route **SKIPPED** |
| **运维** | 批处理必须有上限，不能无意全库跑 MinerU | `--sha256` / `--content-uid` / `--limit` 护栏 |
| **运维** | MinerU 未安装时应有清晰错误 | `DEPENDENCY_MISSING`；CLI exit 1（非 dry-run） |
| **DB 审查员** | 007 不得修改 006 SQL schema | 无 migration；registry 经既有 service API |
| **DB 审查员** | dry-run 与 registry dry-run 均零 DB 写 | pytest + DB Review 证据 |

---

## 3. 目标

1. 从 **raw_vault** 只读读取 PDF 的 `original.bin`，对 in-scope PDF 内容调用 **MinerU adapter** 生成 parsed 产物。
2. 覆盖 `route_type`：**`PDF_DIGITAL`**（MVP 主路径）；**`PDF_SCANNED_OR_IMAGE`**（若 004 未来赋值且 `decision=ROUTE` 时同样 in-scope，007 不自行做 PDF 内容嗅探改 route）。
3. 写入标准 **parsed 目录结构**（复用 005 `parsed_paths.py`）：必选三文件 + 可选 `assets/`。
4. 输出 **`parse_mineru_pdf_report_{UTC}.json`** 到 `reports_root`。
5. 提供 Typer CLI **`parse-mineru-pdf`**（含 `--dry-run`、`--force`、`--register` / `--no-register`、`--timeout`）。
6. 保持幂等；单 content 失败不中断批处理；**默认不写 DB**；**不修改 006 schema**。

---

## 4. 范围（007 MVP 包含）

| 项 | 说明 |
|----|------|
| `MinerUAdapter` | 薄包装 MinerU CLI / SDK；CLI 不直接耦合 MinerU |
| `MinerUPdfParserService` | 批处理编排：候选筛选 → adapter → 产物归一化 → 报告 → 可选 registry |
| MySQL **只读**查询 | 读取 `kb_file_content`、`kb_raw_vault_object`（及 ext fallback 所需的 `kb_file_instance`） |
| 004 route rule **复用** | 复用 `match_route_type()` / `RouteType`（只读 import，不改 004） |
| raw_vault 只读输入 | 002 两档 `original.bin`（经 `vault_paths.py`） |
| parsed 磁盘产物 | 005 三档路径 + 可选 `assets/` |
| JSON 报告 | `parse_mineru_pdf_report_{UTC}.json` |
| CLI `parse-mineru-pdf` | 见 `plan.md` §12 |
| 可选 registry | `--register` 调用 `ParseRegistryService.register_parse_report()` |
| pytest + CLI E2E | 见 `test_cases.md`（默认 mock MinerU） |

---

## 5. 非目标（007 明确不做）

| 非目标 | 说明 | 归属 |
|--------|------|------|
| **OCR 大扩展** | 不构建通用 OCR 平台、不接入多 OCR 引擎 | 后续 Spec |
| **IMAGE 独立文件** | `.png` / `.jpg` 等 `route_type=IMAGE` | 后续 MinerU-image Spec |
| **Office / Text / Markdown** | DOCX/PPTX/XLSX/TEXT | **005**（封闭） |
| **curated/** | 不写 | 010+ |
| **vector DB / embedding** | 不做 | 011+ |
| **project card distillation** | 不做 | 010+ |
| **Streamlit / 前端** | 不做 | 012+ |
| **修改 006 SQL schema** | 无 migration | — |
| **修改 001–006 既有 schema** | 除非 Plan 明确提出并 DB Review 批准 | — |
| **默认历史全量解析** | CLI 须显式 filter | — |
| **修改 raw_vault** | 只读 `original.bin` | — |
| **无 `--force` 覆盖 SUCCESS** | 默认 skip 已有 007 SUCCESS manifest | — |
| **004 router 语义扩展** | 不改 `parser_routing.py` 规则表 | — |
| **quality-checker** | 不读 quality_score 触发重解析 | `007-quality-checker`（独立 Spec 目录） |
| **修改 `markitdown_parser.py`** | 005 service 封闭 | — |
| **直接写 DB（绕过 registry）** | 禁止 service 内 raw SQL INSERT | — |

---

## 6. 数据流

```text
001 scan → 002 copy-to-vault → [003] → [004 route-parsers 可选]
  → 007 parse-mineru-pdf
    MySQL 只读（kb_file_content + kb_raw_vault_object [+ kb_file_instance fallback]）
    → match_route_type() 筛选 PDF_DIGITAL | PDF_SCANNED_OR_IMAGE
    → 只读 open raw_vault/.../original.bin
    → MinerUAdapter.convert()（temp dir；不写 raw_vault）
    → 归一化 → parsed/by_hash/.../parsed_text.md + parsed_metadata.json + parse_manifest.json [+ assets/]
    → reports_root/parse_mineru_pdf_report_{UTC}.json
    → [可选 --register] ParseRegistryService.register_parse_report()
```

**007 磁盘写入**：`parsed/**`（三文件 + 可选 assets）、`reports_root/parse_mineru_pdf_report_*.json`。  
**007 不写入**：`raw_vault/`、`curated/`、`quarantine/`。  
**007 默认不写入 MySQL**；`--register` 时经 006 service 写入 registry 三表 + bridge。

---

## 7. 输入（只读）

### 7.1 MySQL 表操作边界

| 表 | 007 默认 | 007 `--register` |
|----|----------|------------------|
| `kb_file_content` | SELECT | SELECT + UPDATE `parse_status`（经 registry） |
| `kb_raw_vault_object` | SELECT | SELECT |
| `kb_file_instance` | SELECT（ext fallback） | SELECT |
| `kb_parse_run` / `kb_parse_result` / `kb_parsed_artifact` | 不读写 | INSERT/UPSERT（经 registry） |
| `kb_document` | 不读写 | UPSERT（经 registry，mineru profile） |
| `kb_parse_job`（init queue） | 不读写 | 不读写 |

### 7.2 Vault 输入

```text
{raw_vault_root}/by_hash/{sha256[0:2].lower()}/{sha256}/original.bin
```

须经 `build_vault_dir()` + `build_vault_artifact_paths()`；禁止自行拼接路径。

### 7.3 候选条件

与 005 对齐：

```text
sha256 IS NOT NULL
AND status = 'CONTENT_REGISTERED'
AND vault_status = 'COPIED'
```

---

## 8. 输出（parsed 契约）

### 8.1 目录布局（005 三档 + 007 扩展）

```text
{parsed_root}/by_hash/{sha256[0:2]}/{sha256[2:4]}/{sha256}/
  parsed_text.md           # 必选 — MinerU 主 Markdown 文本
  parsed_metadata.json     # 必选 — parser / route / warnings / assets 索引
  parse_manifest.json      # 必选 — 追溯与 status
  assets/                  # 可选 — MinerU 提取的图片 / 表格等资源（见 plan §9）
```

### 8.2 assets 策略（P1 TL 裁决）

| 问题 | 裁决 |
|------|------|
| 是否生成 images/tables/assets？ | **是** — 当 MinerU 输出含图片 / 表格等资源时，007 **必须**将持久化副本写入 `assets/`（非仅 temp） |
| `mineru_output/` 是否落盘？ | **否** — MinerU 原始输出目录仅存在于 **系统 temp**；归一化后只保留 `assets/` 子集 |
| manifest 如何记录？ | `parse_manifest.json` 增加 `assets_dir`（若存在）；`parsed_metadata.json.extra.asset_files[]` 列表 |
| registry artifact 类型 | MVP 将 `assets/` 目录路径记入 result `metadata_json`；是否新增 `PARSED_ASSETS` artifact_type → **DB Review**（见 plan §15） |

### 8.3 报告

`parse_mineru_pdf_report_{UTC}.json` — 结构族与 `parse_markitdown_report` 对齐，字段见 `plan.md` §11。

---

## 9. 与上游 / 下游 Spec 关系摘要

| Spec | 关系 |
|------|------|
| **004** | 只消费 `PDF_DIGITAL` / `PDF_SCANNED_OR_IMAGE` + `decision=ROUTE`；不改 router |
| **005** | 复用 `parsed_paths.py`；不修改 `markitdown_parser.py`；同 sha256 不同 route 不冲突 |
| **006** | 可选 `--register`；不修改 schema；report `dry_run=true` 不得 ingest（M3 延续） |
| **007-quality-checker** | 独立 Spec；不在本 MVP |

---

## 10. 成功标准（Spec 级）

1. PDF sample（mock 或真实 MinerU）能生成标准 parsed 三文件 + 报告。
2. 非 PDF content 全部 SKIPPED，不调用 MinerU。
3. dry-run 零副作用（无 MinerU、无 parsed、无 DB）。
4. MinerU 缺失时 CLI 清晰失败（`DEPENDENCY_MISSING`）。
5. raw_vault 与原始用户文件不变。
6. 005 / 006 回归测试通过。
7. 无 curated / vector / project card / Streamlit 代码路径。

---

## 11. 后续阶段

见 `plan.md` §27 与 `tasks.md` 流水线（P2 DB Review → … → P9 Final Review）。

---

**Spec 结束** — 实现细节见 `plan.md`、`tasks.md`、`acceptance.md`、`test_cases.md`。

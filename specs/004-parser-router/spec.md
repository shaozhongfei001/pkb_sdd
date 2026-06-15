# Spec: 解析路由（004 Parser Router）

> **项目**：个人历史项目文档知识库 `pkb_sdd`  
> **版本基线**：V1.1-SDD  
> **前置条件**：001-file-inventory、002-file-content-vault、003-duplicate-governance 已完成  
> **详细实现计划**：见同目录 `plan.md`

---

## 1. 背景

Phase 1 文件治理底座进度：

```text
001 盘点 → 002 raw_vault → 003 精确重复治理 → 【004 解析路由决策】→ 005/006 解析执行
```

001 已将路径登记为 `kb_file_instance`、内容登记为 `kb_file_content`（含 `file_ext`、`mime_type`、`vault_status` 等）。

002 已将唯一内容只读复制到 `raw_vault/by_hash/...`，写入 `kb_raw_vault_object`。

003 已对 sha256 精确重复做元数据治理，输出 duplicate / cleanup suggestion 报告；**不执行清理**。

004 在 **原始文件只读、raw_vault 只读引用** 前提下，对每个 **已入 vault 的唯一内容** 生成 **未来应使用哪类解析器** 的路由决策（`route_type`），供 005-markitdown-parser、006-mineru-parser 后续消费。

---

## 2. 目标

1. 建立轻量级 **Parser Router**：纯规则、纯元数据、**无解析执行**。
2. 基于 `kb_file_content` 与 `kb_raw_vault_object` 元数据，对每个唯一内容生成 **route decision**（`route_type` + 理由 + `future_parser_hint`）。
3. 路由对象是 **content / vault object**，不是原始文件路径；原始路径仅作 **fallback 扩展名参考**。
4. 输出 **`parser_route_report_{UTC}.json`** 到 `reports_root`。
5. 提供 Typer CLI **`route-parsers`**。
6. 保持幂等；单 content 失败不中断批处理。

**Parser Router 只做「路由决策」，不做「解析执行」。**

**Parser Router 的输出是 route decision，不是 parsed content。**

---

## 3. 范围（004 MVP 包含）

| 项 | 说明 |
|----|------|
| Parser Router 路由决策 | 基于 `file_ext`、`mime_type`、instance fallback 产出 `route_type` |
| MySQL **只读**查询 | 读取 `kb_file_content`、`kb_raw_vault_object`、`kb_file_instance` 元数据列 |
| CLI `route-parsers` | 支持 `--config`、`--sha256`、`--content-uid`、`--limit` |
| JSON 报告 | **唯一**磁盘产物：`{reports_root}/parser_route_report_{UTC}.json` |
| 批处理与异常处理 | 单 content 失败记入 `errors[]` 并 continue |
| 日志 | INFO / WARNING / ERROR 可追溯 |
| 幂等性 | 同 metadata → 稳定 route decision |
| pytest + CLI E2E | 见 `test_cases.md` |

**004 MVP 不包含、不得执行**：向 MySQL **写入**任何业务记录；更新 `parse_status`；upsert `kb_parse_job`；持久化 route decision 到数据库。

---

## 4. 非目标（004 明确不做）

| 非目标 | 说明 |
|--------|------|
| 真实解析 / OCR / 文本抽取 | 属于 005/006/007 |
| 调用 MinerU / MarkItDown | 属于 005/006 |
| 写入 `parsed/` | 属于 005/006 |
| 写入 `curated/` | 属于 010+ |
| 写入 `quarantine/` | 不属于 004 |
| 向量库 / embedding | 属于 011+ |
| Streamlit / 前端 | 属于 012+ |
| 项目卡蒸馏 | 属于 010+ |
| 源代码知识库分析 | 全局禁止 |
| 读取 `original.bin` 内容做判断 | 004 禁止（含 magic-byte、OCR、文本抽取） |
| 打开 raw_vault sidecar JSON 内容 | 仅允许从 DB 列拷贝路径字符串作报告引用 |
| 持久化 route decision 到 MySQL | 004 MVP 不做 |
| upsert `kb_parse_job` / 更新 `parse_status` | 004 MVP 不做 |
| 修改 SQL schema / 新增 route 表 / 新增 migration | 004 MVP 不做 |
| 自动删除 / 移动 / 重命名原始文件或重复文件 | 全局禁止 |
| 修改 / 删除 / 覆盖 raw_vault 文件 | 002 副本只读引用 |
| 修改 `inventory_scanner.py` / `file_content_vault.py` / `duplicate_governance.py` | 001–003 已交付，默认封闭 |
| 新增第三方依赖 | 复用现有 stack |

---

## 5. 数据流

```text
001 scan → 002 copy-to-vault → 003 govern-duplicates（可选）→ 004 route-parsers
  kb_file_content（vault_status=COPIED）
    + kb_raw_vault_object（只读引用 vault_path）
    → route decision（内存 / JSON 报告）
    → reports_root/parser_route_report_{UTC}.json
```

**004 只输出** `reports_root/parser_route_report_{UTC}.json`。**不**写 `parsed/`、`curated/`、`quarantine/`、`raw_vault/`、MySQL 任何表。

---

## 6. 输入（只读）

### 6.1 MySQL 表操作边界

| 表 | 004 操作 |
|----|----------|
| `kb_file_content` | **只读**（主输入；`parse_status` 仅透传到报告，不更新） |
| `kb_raw_vault_object` | **只读**（补全 `vault_path` / `vault_uid` 等报告字段） |
| `kb_file_instance` | **只读**（`file_ext` 为空时 fallback 扩展名） |
| `kb_parse_job` | **不读写** |
| `kb_document` | **不读写** |

**默认候选条件**：

```text
kb_file_content.sha256 IS NOT NULL
AND kb_file_content.status = 'CONTENT_REGISTERED'
AND kb_file_content.vault_status = 'COPIED'
```

可选 CLI 过滤：`--sha256`、`--content-uid`、`--limit`。

### 6.2 路由决策所用字段（不得超出）

| 字段 | 来源 | 用途 |
|------|------|------|
| `sha256` | `kb_file_content` | 内容身份、报告追溯 |
| `content_uid` | `kb_file_content` | 与 sha256 一致（001 约定） |
| `file_ext` | `kb_file_content` | 主路由依据 |
| `mime_type` | `kb_file_content` | 辅助路由 / tie-break |
| `vault_path` | `kb_file_content` 或 `kb_raw_vault_object` | 报告追溯；**不读盘解析** |
| `vault_uid` / sidecar 路径 | `kb_raw_vault_object` | 报告引用（路径字符串，**不 open 文件**） |
| `file_name` / `source_path` | `kb_file_instance`（master 或首个 DISCOVERED） | **仅** 当 `file_ext` 为空时 fallback 扩展名 |

**禁止**：打开 `original.bin`、对 vault 文件做 magic-byte / OCR / 文本抽取、读取 sidecar JSON 内容。

---

## 7. 输出

### 7.1 磁盘报告（唯一 MVP 产物）

```text
{reports_root}/parser_route_report_{UTC}.json
```

UTC 格式：`%Y%m%dT%H%M%SZ`。每次运行 **新文件**，不覆盖旧报告。

### 7.2 报告决策字段

每条 decision 必须含：`content_uid`、`sha256`、`vault_path`、`file_ext`（或 fallback 说明）、`mime_type`、`route_type`、`decision`、`reason`、`future_parser_hint`。

### 7.3 `future_parser_hint` 说明

**命名**：统一使用 **`future_parser_hint`**，**不得**使用 `suggested_parser` 等易被误解为「004 正在调用解析器」的字段名。

**允许取值**：

```text
MARKITDOWN_FAMILY   # 后续 005 类 MarkItDown 路线（Office/HTML 等）
MINERU_FAMILY       # 后续 006 类 MinerU 路线（PDF/图片等）
DIRECT_TEXT         # 后续轻量文本路线（TXT/MD/CSV 等）
NONE                # 无后续解析提示（UNKNOWN / UNSUPPORTED）
```

**硬性约束**：`future_parser_hint` 仅是后续 005/006 的**静态标签**，不代表 004 import、调用、subprocess、网络访问或执行任何解析器。

### 7.4 CLI 汇总

Rich 输出 Candidates / Routed / Skipped / Unknown / Unsupported / Errors 及报告路径。

---

## 8. route_type 与路由规则（摘要）

`RouteType`：`DOCX`、`PPTX`、`XLSX`、`PDF_DIGITAL`、`PDF_SCANNED_OR_IMAGE`、`IMAGE`、`TEXT_OR_MARKDOWN`、`UNKNOWN`、`UNSUPPORTED`。

| 匹配（`file_ext`） | `route_type` | `future_parser_hint` |
|--------------------|--------------|----------------------|
| `.docx` | DOCX | MARKITDOWN_FAMILY |
| `.pptx` | PPTX | MARKITDOWN_FAMILY |
| `.xlsx` | XLSX | MARKITDOWN_FAMILY |
| `.pdf` | PDF_DIGITAL | MINERU_FAMILY |
| 图片扩展名 | IMAGE | MINERU_FAMILY |
| `.txt` `.md` `.csv` 等 | TEXT_OR_MARKDOWN | DIRECT_TEXT |
| 规则未覆盖 / ext 缺失 | UNKNOWN | NONE |
| 遗留 Office / denylist | UNSUPPORTED | NONE |

**PDF 扫描件**：004 **禁止**打开 PDF 判断 scanned vs digital。MVP 所有 `.pdf` → `PDF_DIGITAL`；`PDF_SCANNED_OR_IMAGE` **不在 MVP 自动赋值**。

规则内嵌于 `backend/app/core/parser_routing.py`（详见 `plan.md` §9）。

---

## 9. 业务规则

1. 原始文件只读；004 不 open 原始文件进行 write，不调用 `shutil.move` / `unlink` / `rename`。
2. raw_vault 只读引用；不 create / delete / overwrite `raw_vault/**` 下任何文件。
3. 任务必须幂等：同 metadata → 同 `route_type` / `rule_name` / `reason`。
4. 单 content 失败必须记入 `errors[]` 并 continue，不中断批处理。
5. `UNKNOWN` / `UNSUPPORTED` 计入 summary，**不抛异常**。
6. 关键结果必须有日志；报告 JSON 可追溯 content_uid、sha256、vault_path。
7. CLI 入口调用 `ensure_readonly()`。
8. `build-parse-queue`、`parse` **保持 placeholder**（队列落库与解析执行属于后续 Spec）。

---

## 10. 硬约束清单（Dev / QA 必遵）

1. 004 **只做** Parser Router 路由决策。
2. 004 **只输出** `reports_root/parser_route_report_{UTC}.json`。
3. 004 **不执行**真实解析。
4. 004 **不调用** MinerU。
5. 004 **不调用** MarkItDown。
6. 004 **不写** `parsed/`。
7. 004 **不写** `curated/`。
8. 004 **不做** OCR。
9. 004 **不做**文本抽取。
10. 004 **不读取** `original.bin` 内容。
11. 004 **不修改** SQL schema。
12. 004 **不新增** route 表。
13. 004 **不新增** migration。
14. 004 **不持久化** route decision 到 MySQL。
15. 004 **不 upsert** `kb_parse_job`。
16. 004 **不更新** `parse_status`。
17. 004 **不删除、不移动、不重命名**原始文件。
18. 004 **不删除、不覆盖、不移动** raw_vault 文件。

若实现阶段发现必须写 DB 才能满足需求 → **STOP → TL**，不得 Dev 自行改 schema 或偷偷 upsert。

---

## 11. 与 005/006 的边界

| 阶段 | 职责 |
|------|------|
| **004** | 产出 `route_type` + `future_parser_hint` + JSON 报告 |
| **005 markitdown** | 消费 `future_parser_hint=MARKITDOWN_FAMILY` 等，**在 005 内**调用 MarkItDown，写 `parsed/` |
| **006 mineru** | 消费 `future_parser_hint=MINERU_FAMILY` 等，**在 006 内**调用 MinerU，写 `parsed/` |

004 报告是 005/006 的 **输入参考**，不是执行器。

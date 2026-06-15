# Plan: 解析路由（004 实现计划）

> **项目**：个人历史项目文档知识库 `pkb_sdd`
> **项目路径**：`/home/szf/dev/pyws/pkb_sdd`
> **版本基线**：V1.1-SDD
> **编写日期**：2026-06-15
> **前置条件**：001-file-inventory、002-file-content-vault、003-duplicate-governance 已完成并 merge `main`；Agent 协作规范已落地
> **编写角色**：Tech Lead Agent — 步骤 ① Plan
> **当前分支**：`feature/004-parser-router`

---

## 1. 背景与当前阶段

Phase 1 文件治理底座进度：

```text
001 盘点 → 002 raw_vault → 003 精确重复治理 → 【004 解析路由决策】→ 005/006 解析执行
```

001 已将路径登记为 `kb_file_instance`、内容登记为 `kb_file_content`（含 `file_ext`、`mime_type`、`vault_status` 等）。

002 已将唯一内容只读复制到 `raw_vault/by_hash/...`，写入 `kb_raw_vault_object`。

003 已对 sha256 精确重复做元数据治理，输出 duplicate / cleanup suggestion 报告；**不执行清理**。

004 在 **原始文件只读、raw_vault 只读引用** 前提下，对每个 **已入 vault 的唯一内容** 生成 **未来应使用哪类解析器** 的路由决策（`route_type`），供 005-markitdown-parser、006-mineru-parser 后续消费。**004 不执行真实解析。**

**数据流（004 MVP）**：

```text
001 scan → 002 copy-to-vault → 003 govern-duplicates（可选）→ 004 route-parsers
  kb_file_content（vault_status=COPIED）
    + kb_raw_vault_object（只读引用 vault_path）
    → route decision（内存 / JSON 报告）
    → reports_root/parser_route_report_{UTC}.json
```

---

## 2. 004 目标

1. 建立轻量级 **Parser Router** 设计：纯规则、纯元数据、无解析执行。
2. 基于 `kb_file_content` 与 `kb_raw_vault_object` 元数据，对每个唯一内容生成 **route decision**（`route_type` + 理由 + `future_parser_hint`）。
3. 路由对象是 **content / vault object**，不是原始文件路径；原始路径仅作 **fallback 扩展名参考**（见 §9）。
4. 输出 **`parser_route_report_{UTC}.json`** 到 `reports_root`。
5. 提供 Typer CLI **`route-parsers`**。
6. 保持幂等；单 content 失败不中断批处理；补充 pytest 与 CLI E2E。
7. 为 005/006 提供可追溯的路由决策清单；**不在 004 写 `parsed/`、不调用第三方解析器**。

---

## 3. 004 非目标

| 非目标 | 说明 |
|--------|------|
| 真实解析 / OCR / 文本抽取 | 属于 005/006/007 |
| 调用 MinerU / MarkItDown | 属于 005/006 |
| 写入 `parsed/` | 属于 005/006（`.cursor/rules/004-parser.mdc` 路径约定） |
| 写入 `curated/` | 属于 010+ |
| 向量库 / embedding | 属于 011+ |
| Streamlit / 前端 | 属于 012+ |
| 项目卡蒸馏 | 属于 010+ |
| 源代码知识库分析 | 全局禁止 |
| 持久化 route decision 到 MySQL | 004 MVP 不做；见 §14 |
| upsert `kb_parse_job` / 更新 `parse_status` | 004 MVP 不做 |
| 读取 `original.bin` 内容做判断 | 004 禁止 |
| 自动删除 / 移动 / 重命名原始文件或重复文件 | 全局禁止 |
| 修改 / 删除 raw_vault | 002 副本只读引用 |
| 修改 `inventory_scanner.py` / `file_content_vault.py` / `duplicate_governance.py` | 001–003 已交付，默认封闭 |
| SQL schema 变更 | 004 MVP 无 migration |
| 新增第三方依赖 | 复用现有 stack |

---

## 4. 输入数据

### 4.1 MySQL（主输入，只读）

| 表 | 用途 | 004 操作 |
|----|------|----------|
| **`kb_file_content`** | 待路由内容 | **只读** |
| **`kb_raw_vault_object`** | vault 元数据 | **只读**（报告引用 `vault_path`） |
| **`kb_file_instance`** | 扩展名 fallback | **只读**（可选，见 §9） |

**默认选取条件**：

```text
kb_file_content.sha256 IS NOT NULL
AND kb_file_content.status = 'CONTENT_REGISTERED'
AND kb_file_content.vault_status = 'COPIED'
```

可选 CLI 过滤：`--sha256`、`--content-uid`、`--limit`。

**004 MVP 不**以 `parse_status` 作为硬过滤（避免隐式 DB 写前提）；可在报告中 **附带** 当前 `parse_status` 只读字段供人工查看。

### 4.2 路由决策所用字段（不得超出）

| 字段 | 来源 | 用途 |
|------|------|------|
| `sha256` | `kb_file_content` | 内容身份、报告追溯 |
| `content_uid` | `kb_file_content` | 与 sha256 一致（001 约定） |
| `file_ext` | `kb_file_content` | 主路由依据 |
| `mime_type` | `kb_file_content` | 辅助路由 / tie-break |
| `vault_path` | `kb_file_content` 或 `kb_raw_vault_object` | 报告追溯；**不读盘解析** |
| `vault_uid` / sidecar 路径 | `kb_raw_vault_object` | 报告引用（可选） |
| `file_name` / `source_path` | `kb_file_instance`（master 或首个 DISCOVERED） | **仅** 当 `file_ext` 为空时 fallback 扩展名 |

**禁止**：打开 `original.bin`、对 vault 文件做 magic-byte / OCR / 文本抽取。

### 4.3 配置输入

| 配置项 | 来源 | 004 用法 |
|--------|------|----------|
| `storage.reports_root` | `config/app.yaml` | 报告输出目录 |
| `storage.raw_vault_root` | `config/app.yaml` | 报告引用（只读） |
| `raw.original_files_readonly` | 必须为 `true` | 复用 `ensure_readonly()` |
| `app.pipeline_version` | 写入报告 metadata | 可选 |

**004 MVP 不修改 `config/parser_rules.yaml`**；路由规则内嵌于 `backend/app/core/parser_routing.py`（避免 Dev 改 config 白名单外文件）。后续 Spec 可外置 YAML。

### 4.4 001 / 002 / 003 已提供、004 直接复用

- `AppConfig` / `load_config` / `ensure_readonly`
- `create_db_engine` / `create_session_factory`
- `KbFileContent` / `KbFileInstance` ORM（`models/file.py`）
- `KbRawVaultObject` ORM（`models/vault.py`）
- CLI Typer + Rich 模式（`cli/main.py`）
- 批处理 / 报告 / errors[] 模式（对齐 `DuplicateGovernanceService`）
- Fixtures：`backend/tests/fixtures/中文路径/银行项目/方案.txt`（`.txt` → `TEXT_OR_MARKDOWN`）

---

## 5. 输出数据

### 5.1 磁盘报告（唯一 MVP 产物）

```text
{reports_root}/parser_route_report_{UTC}.json
```

**004 MVP 不写入**：`parsed/`、`curated/`、`quarantine/`、`raw_vault/`、MySQL 任何表。

### 5.2 CLI 汇总（Rich echo）

```text
Candidates: N
Routed: N
Skipped (unchanged decision): N
Unknown: N
Unsupported: N
Errors: N
Parser route report: {reports_root}/parser_route_report_{UTC}.json
```

### 5.3 保留命令

- `scan`、`copy-to-vault`、`govern-duplicates` 行为不变
- `build-parse-queue`、`parse` **保持 placeholder**（队列落库与解析执行属于后续 Spec）

---

## 6. 关键数据对象

### 6.1 `RouteType` 枚举（Python，非 DB）

见 §8。

### 6.2 `ParserRouteDecision`（建议 dataclass）

```text
ParserRouteDecision
  content_uid: str
  sha256: str
  file_ext: str | None
  mime_type: str | None
  vault_path: str | None
  route_type: RouteType
  decision: str          # ROUTE | UNKNOWN | UNSUPPORTED | ERROR
  rule_name: str | None
  reason: str
  future_parser_hint: str        # 报告字段：MARKITDOWN_FAMILY | MINERU_FAMILY | DIRECT_TEXT | NONE（见 §6.5）
  parse_status: str | None       # 只读透传 kb_file_content.parse_status
```

### 6.3 `ParserRouteResult`（批处理汇总）

```text
ParserRouteResult
  candidates: int
  routed: int
  skipped: int
  unknown: int
  unsupported: int
  errors: list[RouteError]    # sha256 + message
  decisions: list[ParserRouteDecision]
  report_path: Path | None
```

### 6.4 与 005/006 的衔接字段（仅报告，不执行）

| `route_type` | `future_parser_hint`（后续 Spec 参考，004 不调用） |
|--------------|------------------------------------------------------|
| DOCX / PPTX / XLSX | `MARKITDOWN_FAMILY` |
| PDF_DIGITAL / PDF_SCANNED_OR_IMAGE / IMAGE | `MINERU_FAMILY` |
| TEXT_OR_MARKDOWN | `DIRECT_TEXT` |
| UNKNOWN / UNSUPPORTED | `NONE` |

### 6.5 `future_parser_hint` 字段安全说明（必读）

**命名澄清**：本 Spec **不使用** `suggested_parser` 等易被误解为「004 当前正在调用某解析器」的字段名；统一使用 **`future_parser_hint`**。

**允许取值**（字符串枚举，报告 JSON 与 dataclass 一致）：

```text
MARKITDOWN_FAMILY   # 后续 005 类 MarkItDown 路线（Office/HTML 等）
MINERU_FAMILY       # 后续 006 类 MinerU 路线（PDF/图片等）
DIRECT_TEXT         # 后续轻量文本路线（TXT/MD/CSV 等）
NONE                # 无后续解析提示（UNKNOWN / UNSUPPORTED）
```

**硬性约束**：

```text
future_parser_hint 仅是后续 005/006 的路由提示，
不代表 004 import、调用、subprocess、网络访问或执行任何解析器。
```

- 004 **不得**因 hint 值而加载 MinerU / MarkItDown 模块或 CLI。
- hint 仅为 JSON 报告中的 **静态标签**，由 routing rule 映射产生。
- 005/006 自行决定是否消费该 hint；004 不保证 hint 与具体 parser 版本绑定。

---

## 7. Parser Router 定义

**Parser Router 只做「路由决策」，不做「解析执行」。**

**Parser Router 的输出是 route decision，不是 parsed content。**

职责边界：

| 做 | 不做 |
|----|------|
| 读取 MySQL 元数据 | 读取 `original.bin` 内容 |
| 按规则产出 `route_type` | 调用 MinerU / MarkItDown |
| 写 JSON 报告 | 写 `parsed/` / `curated/` |
| 记录 `future_parser_hint` 供 005/006 参考（静态标签） | OCR、文本抽取、chunking、import/subprocess 解析器 |
| 单条失败 continue | 修改原始文件 / raw_vault |

---

## 8. route_type 枚举设计

```text
RouteType（str Enum）
  DOCX
  PPTX
  XLSX
  PDF_DIGITAL
  PDF_SCANNED_OR_IMAGE
  IMAGE
  TEXT_OR_MARKDOWN
  UNKNOWN
  UNSUPPORTED
```

**语义说明**：

| 值 | 含义 | 004 MVP 赋值方式 |
|----|------|------------------|
| `DOCX` | Word 类文档，后续走 MarkItDown 路线 | `.docx`（可含 `.doc` 映射或标 UNSUPPORTED，见 §9） |
| `PPTX` | PowerPoint 类 | `.pptx` |
| `XLSX` | Excel 类 | `.xlsx` |
| `PDF_DIGITAL` | 数字 PDF，后续走 MinerU 路线 | `.pdf` + `mime_type` 含 pdf（**默认**） |
| `PDF_SCANNED_OR_IMAGE` | 扫描 PDF / 需 OCR 路线标记 | **004 不读 PDF 内容**；MVP **不**对普通 `.pdf` 赋此值；枚举保留供报告 schema 与 006 衔接 |
| `IMAGE` | 独立图片 | `.png` `.jpg` `.jpeg` `.tiff` `.bmp` `.gif` `.webp` |
| `TEXT_OR_MARKDOWN` | 纯文本 / Markdown / CSV | `.txt` `.md` `.markdown` `.csv` |
| `UNKNOWN` | 扩展名缺失或规则未覆盖的可疑文档 | 见 §10 |
| `UNSUPPORTED` | 明确不在 Phase 1 解析范围的类型 | 见 §10 |

**重要**：以上仅为 **route_type 标签**，**不代表** 004 会调用任何解析器。

---

## 9. routing rule 设计

### 9.1 规则原则

1. **主依据**：`kb_file_content.file_ext`（小写、含点，如 `.pdf`）。
2. **辅助**：`kb_file_content.mime_type`（tie-break / 校验）。
3. **Fallback**：当 `file_ext` 为空时，从 `kb_file_content.master_file_instance_uid` 对应 instance 的 `file_name` 或 `source_path` 提取扩展名；仍失败 → `UNKNOWN`。
4. **不得**读取 `original.bin`、vault sidecar JSON 内容、原始用户文件内容。
5. **不得**调用外部解析器、OCR、文本抽取。
6. 规则 **确定性**：同 metadata → 同 `route_type`（幂等）。

### 9.2 MVP 规则表（内嵌 `parser_routing.py`）

| 优先级 | 匹配条件（`file_ext`） | `route_type` | `rule_name` |
|--------|------------------------|--------------|-------------|
| 100 | `.docx` | DOCX | ext_docx |
| 100 | `.pptx` | PPTX | ext_pptx |
| 100 | `.xlsx` | XLSX | ext_xlsx |
| 90 | `.pdf` | PDF_DIGITAL | ext_pdf_digital |
| 90 | `.png` `.jpg` `.jpeg` `.tiff` `.bmp` `.gif` `.webp` | IMAGE | ext_image |
| 80 | `.txt` `.md` `.markdown` `.csv` | TEXT_OR_MARKDOWN | ext_text |
| 70 | `.html` `.htm` `.xml` `.json` | TEXT_OR_MARKDOWN | ext_markup_json |
| 60 | `.doc` `.ppt` `.xls` | UNSUPPORTED | ext_legacy_office |
| 60 | `.rtf` `.odt` `.ods` `.odp` | UNSUPPORTED | ext_other_office |
| — | 扩展名在 001 白名单外 / 空且 fallback 失败 | UNKNOWN | ext_unknown |
| — | 扩展名明确禁止解析（Dev 可维护 denylist） | UNSUPPORTED | ext_denied |

**PDF 扫描件区分**：004 **禁止**打开 PDF 判断 scanned vs digital。MVP 所有 `.pdf` → `PDF_DIGITAL`。`PDF_SCANNED_OR_IMAGE` **不在 MVP 自动赋值**；若测试需要覆盖该枚举，使用 mock metadata 单测，不读 bin。

**mime_type tie-break（可选）**：

- `file_ext=.pdf` 且 `mime_type` 以 `image/` 开头 → 记 WARNING，`route_type` 仍为 `PDF_DIGITAL` 或 `UNKNOWN`（Dev 实现时选 `UNKNOWN` + reason 说明 ext/mime 冲突）。

### 9.3 实现位置

- `backend/app/core/parser_routing.py`：`RouteType` enum、`match_route_type(...)`、规则常量。
- **不**在 004 修改 `config/parser_rules.yaml`。

---

## 10. unsupported / unknown 处理策略

### 10.1 `UNKNOWN`

触发条件（任一）：

- `file_ext` 为空且 instance fallback 仍无法得到扩展名
- 扩展名不在规则表且仍在 001 `DOCUMENT_EXTENSIONS` 内（未映射规则）
- `file_ext` 与 `mime_type` 明显冲突且无法 tie-break

报告要求：

- `decision = "UNKNOWN"`
- `reason` 人类可读（含 ext、mime、fallback 来源）
- 计入 summary `unknown`
- **不抛异常**；继续批处理

### 10.2 `UNSUPPORTED`

触发条件：

- 遗留 Office（`.doc` `.ppt` `.xls`）
- ODF / RTF 等 Phase 1 不解析类型
- 明确 denylist 扩展名

报告要求：

- `decision = "UNSUPPORTED"`
- `reason` 说明「当前 Phase 不解析，保留 vault 原文」
- 计入 summary `unsupported`
- **不抛异常**；继续批处理

### 10.3 错误（`errors[]`）

- DB 行缺失、`vault_path` 查询异常、单条逻辑 bug
- 记入 `errors[]`，**不**中断其他 content

---

## 11. 路由报告设计

### 11.1 文件名

```text
parser_route_report_{UTC}.json
```

UTC 格式与 001/003 对齐：`%Y%m%dT%H%M%SZ`。每次运行 **新文件**，不覆盖旧报告。

### 11.2 JSON 结构

```json
{
  "report_type": "parser_route_report",
  "pipeline_version": "v1.1",
  "generated_at": "2026-06-15T12:00:00Z",
  "summary": {
    "candidates": 2,
    "routed": 1,
    "skipped": 0,
    "unknown": 0,
    "unsupported": 0,
    "errors": 0
  },
  "decisions": [
    {
      "content_uid": "<sha256>",
      "sha256": "<sha256>",
      "file_ext": ".txt",
      "mime_type": "text/plain",
      "vault_path": ".../raw_vault/by_hash/...",
      "route_type": "TEXT_OR_MARKDOWN",
      "decision": "ROUTE",
      "rule_name": "ext_text",
      "reason": "file_ext .txt maps to TEXT_OR_MARKDOWN",
      "future_parser_hint": "DIRECT_TEXT",
      "parse_status": null
    }
  ],
  "errors": []
}
```

### 11.3 可追溯性（A010）

每条 decision **必须**含：`content_uid`、`sha256`、`vault_path`（可为 null 但需 reason）、`file_ext` 或 fallback 说明、`route_type`、`decision`、`reason`、`future_parser_hint`（§6.5 四值之一）。

---

## 12. CLI 设计建议

### 12.1 命令

```bash
python -m app.cli.main route-parsers [OPTIONS]
```

### 12.2 选项

| 选项 | 说明 |
|------|------|
| `--config PATH` | 默认 `config/app.yaml` |
| `--sha256 HEX` | 仅处理指定内容 |
| `--content-uid UID` | 同 `--sha256` |
| `--limit N` | 最多处理 N 个候选 content |

**004 MVP 不实现 `--dry-run`**。

### 12.3 执行流程

1. `load_config` → `ensure_readonly()`
2. `ParserRouterService.route_parsers(...)`
3. Rich 打印 §5.2 汇总
4. 打印报告路径

### 12.4 全链路 E2E（fixtures）

```bash
python -m app.cli.main scan --path backend/tests/fixtures
python -m app.cli.main copy-to-vault
python -m app.cli.main route-parsers
```

---

## 13. 服务层设计建议

### 13.1 新增 `ParserRouterService`

文件：`backend/app/services/parser_router.py`

**核心方法**：

```text
route_parsers(
  *,
  limit: int | None = None,
  sha256: str | None = None,
  content_uid: str | None = None,
) -> ParserRouteResult
```

**内部步骤**：

1. 查询候选 `kb_file_content`（§4.1）
2. 可选 join / 查询 `kb_raw_vault_object` 补全 `vault_path`
3. 可选加载 master instance 做 ext fallback（§9.1）
4. 调用 `match_route_type(...)` → `ParserRouteDecision`
5. 单条异常 → `errors.append`；**continue**
6. 全部完成后写 `parser_route_report_{UTC}.json`

### 13.2 核心模块

文件：`backend/app/core/parser_routing.py`

```text
class RouteType(str, Enum): ...
def normalize_file_ext(ext: str | None) -> str | None: ...
def ext_from_path(path: str) -> str | None: ...
def match_route_type(
  *,
  file_ext: str | None,
  mime_type: str | None,
  fallback_ext: str | None = None,
) -> tuple[RouteType, str, str, str]: ...
  # returns (route_type, decision, rule_name, future_parser_hint)
```

### 13.3 日志

- INFO：每条 content routed / skipped
- WARNING：ext/mime 冲突、vault_path 缺失
- ERROR：单条失败（含 sha256、message）

---

## 14. 数据库与 schema 策略

**004 MVP 不修改 SQL schema。**

**004 MVP 不新增 route 表。**

**004 MVP 不新增 migration。**

**004 MVP 只输出 parser_route_report.json。**

**004 MVP 不持久化 route decision 到数据库。**

**如后续需要持久化 route decision，必须另开 Spec 或由 TL/DB Review 明确授权。**

**Dev Agent 不得自行修改 SQL schema。**

### 14.1 表操作边界（MVP）

| 表 | 004 |
|----|-----|
| `kb_file_content` | **只读** |
| `kb_raw_vault_object` | **只读** |
| `kb_file_instance` | **只读**（ext fallback） |
| `kb_parse_job` | **不读写**（表已存在，留待后续 Spec） |
| `kb_document` | **不读写** |

若实现阶段发现必须写 DB 才能满足需求 → **STOP → TL**，不得 Dev 自行改 schema 或偷偷 upsert。

---

## 15. 幂等性设计

| 场景 | 行为 |
|------|------|
| 重复执行 `route-parsers` | 同 content metadata → 同 `route_type` / `rule_name` / `reason`（决策稳定） |
| `skipped` 计数 | 与上次报告 decision 完全一致时可计 skipped（Dev 可选：MVP 简化为 routed = candidates - errors） |
| 报告文件 | 每次运行新 timestamp 文件；不覆盖 |
| MySQL | **无写操作** → 无重复主记录风险 |
| 规则版本 | 报告可含 `routing_rules_version: "004_mvp_v1"` 常量 |

---

## 16. 异常处理设计

| 场景 | 处理 |
|------|------|
| 无候选 content | 空报告 + summary 0；exit 0 |
| 单 content DB 异常 | rollback 该条（若用了 session）；记 error；continue |
| 全局 DB 连接失败 | 任务失败，exit non-zero |
| `vault_path` 缺失 | decision 仍可生成；`vault_path=null` + WARNING reason |
| 报告目录不可写 | 记 error；decisions 已在内存则 log |
| `--sha256` 指向不存在 content | skipped/空 + 不报错（对齐 003） |

**不 swallow exception**：必须 log + 写入 `errors[]`。

---

## 17. 原始文件保护设计

- 004 **不 open 原始文件进行 write**；不调用 `shutil.move` / `unlink` / `rename`。
- 仅通过 MySQL **只读** `source_path` / `file_name`（fallback ext）；**不读文件内容**。
- CLI 入口调用 `ensure_readonly()`。
- pytest 必须含 **原始文件 stat/hash 不变** 断言。

---

## 18. raw_vault 保护设计

- 004 **只读** `kb_file_content.vault_path`、`kb_raw_vault_object`；报告引用路径。
- **不** create / delete / overwrite `raw_vault/**` 下任何文件。
- **不**读取 `original.bin` 做 magic-byte 或 OCR。
- QA 验证：`original.bin` hash 与目录 listing 在 route 前后不变。

---

## 19. 与 005/006 的边界

| 阶段 | 职责 |
|------|------|
| **004** | 产出 `route_type` + `future_parser_hint` + JSON 报告 |
| **005 markitdown** | 消费 `future_parser_hint=MARKITDOWN_FAMILY` 等路由结果，**在 005 内**调用 MarkItDown，写 `parsed/` |
| **006 mineru** | 消费 `future_parser_hint=MINERU_FAMILY` 等路由结果，**在 006 内**调用 MinerU，写 `parsed/` |

004 报告是 005/006 的 **输入参考**，不是执行器。`future_parser_hint` **不代表** 004 已调用任何解析器（见 §6.5）。`build-parse-queue` / `parse` placeholder 在 **后续 Spec**（可能 upsert `kb_parse_job`）实现。

---

## 20. 测试策略

### 20.1 pytest

文件：`backend/tests/test_parser_router.py`

| 用例 | 验证 |
|------|------|
| `test_route_txt_to_text_or_markdown` | fixtures `.txt` → `TEXT_OR_MARKDOWN` |
| `test_route_pdf_to_pdf_digital` | mock content `.pdf` → `PDF_DIGITAL` |
| `test_route_image_ext` | `.png` → `IMAGE` |
| `test_route_office_ext` | `.docx/.pptx/.xlsx` |
| `test_route_legacy_office_unsupported` | `.doc` → `UNSUPPORTED` |
| `test_route_unknown_missing_ext` | 无 ext → `UNKNOWN` |
| `test_route_idempotent` | 两次 route 决策字段一致 |
| `test_route_chinese_path` | 中文 fixture 全链路 |
| `test_route_single_error_continues` | 单条失败不中断 |
| `test_original_files_unchanged` | stat + hash |
| `test_raw_vault_unchanged` | vault bin 不变 |
| `test_route_project_fixtures_integration` | scan → copy-to-vault → route-parsers |

目标：**约 10–12** 个 test functions。

### 20.2 CLI E2E

见 §12.4。

### 20.3 全链路回归

```bash
pytest -q tests/test_inventory_scanner.py tests/test_file_content_vault.py tests/test_duplicate_governance.py tests/test_parser_router.py
```

---

## 21. Acceptance Criteria

| 编号 | 标准 | 004 验证要点 |
|------|------|--------------|
| **A001** 范围符合 | 只做路由决策，不执行解析 | 无 parsed 产物、无 parser 调用 |
| **A002** 原始文件保护 | 不 delete/move/rename/overwrite | stat/hash 测试 + QA 必查 |
| **A003** raw_vault 保护 | 不 delete/overwrite/move vault | vault bin hash 不变 |
| **A004** 不写 parsed/curated | 磁盘无 parsed/curated 新增 | QA 目录检查 |
| **A005** 不接 MinerU/MarkItDown | 无 import/subprocess/网络调用；`future_parser_hint` 仅为静态标签（§6.5） | DB/QA 代码审查 |
| **A006** 不做 OCR/文本抽取 | 不读 original.bin 内容 | 代码审查 + 测试 |
| **A007** 不做向量库/项目卡蒸馏 | 无 embedding/curated | 范围审查 |
| **A008** 幂等性 | 同输入稳定 route decision | 两次 route-parsers 决策一致 |
| **A009** 异常可恢复 | 单 content 失败不中断 | errors[] + 其他成功 |
| **A010** 报告可追溯 | content_uid/sha256/vault_path/ext/`future_parser_hint` | JSON 字段齐全 |
| **A011** SQL schema 边界 | 不修改 SQL schema | 无 migration、无 ORM 写库 |
| **A012** 测试通过 | pytest + CLI E2E | 全链路 23+ passed |

---

## 22. 明确禁止事项

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
16. 不修改 SQL schema；不持久化 route decision 到 DB（MVP）。
17. 不改 `inventory_scanner.py`、`file_content_vault.py`、`duplicate_governance.py`（默认封闭）。
18. Dev 不得自行改 schema — 发现缺口 **STOP → TL**。

---

## 23. 下一步 Dev Agent 实现边界

### 23.1 允许修改（白名单）

| 操作 | 文件 |
|------|------|
| **新增** | `backend/app/services/parser_router.py` |
| **新增** | `backend/app/core/parser_routing.py` |
| **修改** | `backend/app/cli/main.py`（新增 `route-parsers`） |
| **新增** | `backend/tests/test_parser_router.py` |
| **修改** | `specs/004-parser-router/tasks.md`（勾选完成项） |

### 23.2 禁止修改

```text
backend/app/services/inventory_scanner.py
backend/app/services/file_content_vault.py
backend/app/services/duplicate_governance.py
backend/app/models/file.py          # 004 无 DB 写，无必要不改
backend/app/models/vault.py
backend/app/models/duplicate.py
sql/**
config/**
docs/**
.cursor/**
raw_vault/**（真实产物）
specs/004-parser-router/plan.md     # Dev 不改 Plan
specs/其他编号/**
```

### 23.3 Dev 完成后 STOP 点

```text
Dev 实现 + pytest 自报 → STOP → DB Agent Plan/实现审查 → E2E QA → Handoff → TL Final Review
```

Dev **不得**自我宣布 A001–A012 通过。

### 23.4 TL 实现决策（Dev 必遵）

| # | 问题 | TL 决策 |
|---|------|---------|
| **Q1** | CLI 命令名 | **`route-parsers`**（不用 `build-parse-queue` 做 MVP） |
| **Q2** | 路由规则存放 | **`backend/app/core/parser_routing.py`** 内嵌常量；不改 `config/parser_rules.yaml` |
| **Q3** | PDF 扫描件 | MVP **全部** `.pdf` → `PDF_DIGITAL`；**不**赋 `PDF_SCANNED_OR_IMAGE`（无 bin 读取） |
| **Q4** | DB 写入 | **禁止** upsert `kb_parse_job`、**禁止** update `parse_status` |
| **Q5** | `skipped` 计数 | 可选；若实现，指同 content 决策与上次报告完全一致 |
| **Q6** | 测试清理 | 仅 pytest helper / teardown 可清理测试 DB 行；业务逻辑禁止 touch 原始文件与 raw_vault |
| **Q7** | `--sha256` 不存在 | 空结果 / errors 汇总；exit 0；不抛未捕获异常 |

---

**Plan 结束** — 请 Dev Agent 先读 `tasks.md`、§23 与白名单后再写代码。

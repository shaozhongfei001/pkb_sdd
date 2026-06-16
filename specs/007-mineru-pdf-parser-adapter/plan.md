# Plan: MinerU PDF Parser Adapter（007 实现计划）

> **项目**：个人历史项目文档知识库 `pkb_sdd`  
> **项目路径**：`/home/szf/dev/pyws/pkb_sdd`  
> **版本基线**：V1.1-SDD  
> **编写日期**：2026-06-15  
> **编写角色**：Tech Lead Agent — P1 Plan  
> **当前分支**：`feature/007-mineru-pdf-parser-adapter`  
> **前置条件**：001–006 merge `main`；006 migration 已手动执行；已读 005/006 handoff 与实现

---

## 1. 背景与 001–006 能力基线

Phase 1 进度：

```text
001 盘点 → 002 raw_vault → 003 重复治理 → 004 解析路由
  → 005 MarkItDown → 006 Registry → 【007 MinerU PDF】
```

| Spec | CLI | 解析执行 | parsed 写入 | MySQL |
|------|-----|----------|-------------|-------|
| **004** | `route-parsers` | ❌ | ❌ | 只读 |
| **005** | `parse-markitdown` | MarkItDown（Office/text） | ✅ 三文件 | 只读 |
| **006** | `register-parse-report` 等 | ❌（ingest only） | 只读 | registry 写 |
| **007** | `parse-mineru-pdf` | MinerU（PDF） | ✅ 三文件 + assets | 默认只读；`--register` 经 006 |

**007 定位**：Phase 1 **第二个** parser adapter执行 Spec（继 005 之后），专责 **PDF / MinerU**，与 005 **并列**而非替代。

---

## 2. 007 目标

1. 实现 **MinerU PDF parser adapter MVP**（非通用 OCR 框架）。
2. 对 `route_type ∈ {PDF_DIGITAL, PDF_SCANNED_OR_IMAGE}` 且 `decision=ROUTE` 的 vault PDF，只读解析 `original.bin`。
3. 写入 **005 兼容 parsed 路径** + 可选 `assets/` + **`parse_mineru_pdf_report_{UTC}.json`**。
4. 提供 CLI **`parse-mineru-pdf`**，含护栏、`--dry-run`、`--force`、`--timeout`、`--register` / `--no-register`。
5. 幂等 skip；单条失败不中断；**默认零 DB 写**；**不修改 006 schema**。

---

## 3. 007 非目标

| 非目标 | 说明 |
|--------|------|
| OCR 大扩展 / 多引擎 | 仅 MinerU adapter |
| IMAGE 独立文件（`.png` 等） | `route_type=IMAGE` 跳过 |
| Office / Text / Markdown 解析 | → 005 |
| curated / vector / embedding / project card / Streamlit | 后续 Spec |
| 修改 006 SQL schema / migration | 禁止 |
| 修改 001–006 封闭 service（vault、markitdown、inventory 等） | 禁止 |
| 默认全库 PDF 解析 | 须显式 CLI filter |
| 无 `--force` 覆盖 SUCCESS manifest | 禁止静默覆盖 |
| 修改 004 `parser_routing.py` 规则 | 禁止（MVP） |
| PDF 内容嗅探区分 digital vs scanned | 不做；沿用 004 ext 规则 |
| 在 raw_vault 写 temp / 中间文件 | 禁止 |

---

## 4. 为什么 005 不处理 PDF / 为什么 007 独立

### 4.1 005 跳过 PDF 的设计理由

- MarkItDown 对 PDF 的版面还原与扫描 OCR 能力不足。
- 004 将 `.pdf` 标为 `PDF_DIGITAL` + `MINERU_FAMILY` hint。
- 005 `IN_SCOPE_ROUTE_TYPES` 仅四值 Office/text；PDF 在 report 中为 `SKIPPED`。
- 005 handoff §4 明确 PDF → 006/007 MinerU Spec。

### 4.2 007 独立 Spec 理由

- **运行时**：MinerU subprocess 耗时、内存、GPU/CPU 与 MarkItDown 差异大，需独立 `--timeout` 与资源控制。
- **产物**：除三文件外可能含 `assets/`（图片、表格导出），adapter 归一化逻辑不同于 MarkItDown。
- **依赖**：MinerU / `magic-pdf` 可选安装；需 `DEPENDENCY_MISSING` 与 mock 测试策略。
- **封闭边界**：不修改已 merge 的 `markitdown_parser.py`；新增 `mineru_pdf_parser.py` + `mineru_adapter.py`。

### 4.3 与 006 Registry 关系

```text
007（默认）: vault bin → MinerU → parsed/ + parse_mineru_pdf_report.json
007（--register）: 上述 + ParseRegistryService.register_parse_report(report)
006（手动）: register-parse-report --report-path parse_mineru_pdf_report_*.json
```

| 登记对象 | 是否登记 | 条件 |
|----------|----------|------|
| `kb_parse_run` | 可选 | `--register` 且非 dry-run |
| `kb_parse_result` | 可选 | 同上，per content |
| `kb_parsed_artifact` | 可选 | 同上，三文件 + report；assets → metadata 或扩展 type（DB Review） |
| `kb_file_content.parse_status` | 可选 | registry 聚合规则 |
| `kb_document` | 可选 | SUCCESS/EMPTY bridge；`parser_profile=mineru_default_v1`（**需薄扩展 parse_registry，非 schema**） |

**registry dry-run**：`--dry-run` 时即使 `--register` 也 **不得**写 DB（007 不调用 register 或 registry 早返回）。

---

## 5. 输入输出契约

### 5.1 输入

| 来源 | 契约 |
|------|------|
| **raw_vault** | `{raw_vault_root}/by_hash/{sha256[0:2].lower()}/{sha256}/original.bin` |
| **路径解析** | `build_vault_dir()` + `build_vault_artifact_paths()`（002 权威） |
| **DB 元数据** | `kb_file_content` + `kb_raw_vault_object` + ext fallback（对齐 005） |
| **route 过滤** | `match_route_type()` → in-scope 见 §6 |

### 5.2 输出 — 必选三文件

与 005 相同相对路径（`parsed_paths.py`）：

| 文件 | 内容 |
|------|------|
| `parsed_text.md` | UTF-8 Markdown；MinerU 主输出归一化 |
| `parsed_metadata.json` | `parser_name=mineru`、`parser_adapter_version=007_mvp_v1`、`route_type`、`library_version`、`warnings`、`extra`（含 `asset_files`、页数等） |
| `parse_manifest.json` | 与 005 同族字段 + `assets_dir`（可选） |

### 5.3 输出 — 可选 assets

```text
{parsed_dir}/assets/
  images/          # MinerU 提取的图片（若存在）
  tables/          # 表格导出（若存在，格式依 MinerU 输出）
```

**规则**：

- MinerU 在 **系统 temp** 中产出原始目录；service 归一化后 **仅**将需要持久化的资源复制到 `assets/`。
- 若 MinerU 无图片/表格输出，`assets/` **可不创建**。
- `parsed_text.md` 内相对路径引用应指向 `assets/` 下文件（adapter 负责 rewrite）。
- **不**在 parsed 根下保留 `mineru_output/` 原始树（避免双倍磁盘）。

### 5.4 FAILED 产物

与 005 对齐：**仅**写 `parse_manifest.json`（`status=FAILED` + `error`）；**不写** `parsed_text.md` / `parsed_metadata.json` / `assets/`。

---

## 6. 与 Parser Router（004）的关系

```text
004: metadata → route_type (memory / JSON report)
007: metadata → match_route_type() → IF PDF in-scope → read bin → MinerU → parsed/
```

| 维度 | 004 | 007 |
|------|-----|-----|
| 改 router 语义 | — | **禁止**（MVP） |
| 读 `original.bin` | 禁止 | 允许（只读） |
| PDF route | 产出 `PDF_DIGITAL` | **消费** `PDF_DIGITAL` |
| 非 PDF | 各类 route | **SKIPPED** |

**IN_SCOPE（007）**：

```python
IN_SCOPE_ROUTE_TYPES = frozenset({
    RouteType.PDF_DIGITAL,
    RouteType.PDF_SCANNED_OR_IMAGE,
})
```

**说明**：

- 004 MVP 将 `.pdf` 一律映射 `PDF_DIGITAL`（`ext_pdf_digital`）；`PDF_SCANNED_OR_IMAGE` 枚举预留，007 纳入 in-scope 以便未来 route 扩展时无需改 007 过滤集合。
- 007 **不**读取 PDF 二进制来覆写 `route_type`（不做 scanned/digital 内容判别）。
- `decision != ROUTE`（UNKNOWN / UNSUPPORTED）→ SKIPPED，不调用 MinerU。

---

## 7. 与 005 MarkItDown Parser 的关系

| 维度 | 005 | 007 |
|------|-----|-----|
| in-scope | Office + text | PDF only |
| parsed 路径 | `parsed_paths.py` 三档 | **复用同一 helper** |
| 同 sha256 目录 | `{parsed_root}/by_hash/.../{sha256}/` | **同一路径**（不同 content 不会既是 PDF 又是 docx） |
| manifest 区分 | `parser_name=markitdown` | `parser_name=mineru` |
| 修改对方 service | 禁止 | 禁止 |

**幂等隔离**：

- 005 幂等检查：`status=SUCCESS` + `parser_adapter_version=005_mvp_v1`
- 007 幂等检查：`status=SUCCESS` + `parser_adapter_version=007_mvp_v1` + `parser_name=mineru`
- 互不影响：PDF 不会有 005 SUCCESS manifest；Office 不会有 007 SUCCESS manifest。

---

## 8. MinerU Adapter 设计

### 8.1 分层

```text
CLI (main.py)                    — 不 import mineru / magic_pdf
  → MinerUPdfParserService       — 批处理、幂等、报告、可选 registry
    → MinerUAdapter              — 唯一调用 MinerU CLI/SDK 的层
      → subprocess magic-pdf 或 MinerU Python API
```

### 8.2 各层职责

| 层 | 职责 |
|----|------|
| **CLI** | 参数护栏、`ensure_readonly()`、非 dry-run 预检 `MinerUAdapter.check_availability()`、Rich 汇总、`--register` 调度 |
| **Service** | MySQL 只读候选、route 过滤、limit 计数、vault/parsed 路径、幂等/force、写三文件+assets、写 report、可选 `register_parse_report` |
| **Adapter** | 单 PDF `convert()`：temp 工作区 → 调用 MinerU → 归一化 `AdapterResult(text, metadata, warnings, asset_paths)` |

### 8.3 Adapter 接口（建议）

```python
PARSER_NAME = "mineru"
PARSER_ADAPTER_VERSION = "007_mvp_v1"

@dataclass
class AdapterResult:
    text: str
    metadata: dict
    warnings: list[str]
    asset_files: list[Path]  # 待复制到 parsed_dir/assets 的源文件列表

class MinerUAdapter:
    @classmethod
    def check_availability(cls) -> None: ...

    def convert(
        self,
        *,
        input_path: Path,
        route_type: RouteType,
        timeout_seconds: int,
        work_dir: Path,
    ) -> AdapterResult: ...
```

### 8.4 外部调用方式（P1 TL 裁决）

| 优先级 | 方式 | 说明 |
|--------|------|------|
| **MVP 主路径** | **subprocess** 调用 `magic-pdf`（MinerU 2.x CLI） | `shutil.which("magic-pdf")` 预检 |
| **备选** | MinerU Python API（`mineru` 包） | 仅当 subprocess 不可用且包已安装；Dev 实现时二选一，**不**双栈并行 |

**调用参数（示意）**：

```bash
magic-pdf -p <input_pdf> -o <work_dir> -m auto
```

- 具体 flags 以目标环境 MinerU 版本为准；adapter 封装，service 不传 CLI 给运维。
- 输入 PDF 路径 = vault `original.bin`（只读）；输出 **仅**写入 `work_dir`（temp）。

### 8.5 错误处理

| code | 场景 |
|------|------|
| `DEPENDENCY_MISSING` | `magic-pdf` / mineru 包均未找到 |
| `PARSER_IMPORT_ERROR` | Python API import 失败 |
| `PARSER_RUNTIME_ERROR` | 未分类 MinerU 运行时错误 |
| `CORRUPTED_DOCUMENT` | 启发式：损坏 / 无法打开的 PDF |
| `PASSWORD_PROTECTED` | 启发式：加密 PDF |
| `TIMEOUT` | subprocess 超过 `--timeout` |
| `MISSING_ORIGINAL_BIN` | vault bin 不存在 |
| `UNSUPPORTED` | route 非 PDF（service 层 SKIPPED，非 adapter） |

Adapter 抛 `MinerUAdapterError(code, message)`；service 捕获后写 FAILED manifest。

### 8.6 超时处理

- CLI `--timeout SECONDS`（默认 **600**）；传入 adapter subprocess `timeout=`。
- 超时 → 终止子进程 → `status=FAILED`，`error.code=TIMEOUT` → 清理 temp → 批处理 continue。

### 8.7 MinerU 未安装 — graceful failure

| 场景 | 行为 |
|------|------|
| CLI 非 dry-run 入口 | `MinerUAdapter.check_availability()` 失败 → 打印 `DEPENDENCY_MISSING` → **exit 1**；**不** partial write parsed |
| dry-run | **不**调用 check（或 check 仅 warning）；不写 parsed |
| 单条 runtime 失败 | 该条 FAILED；其余 continue |

### 8.8 临时目录清理

- `tempfile.mkdtemp(prefix="pkb_mineru_")` 或 `TemporaryDirectory`。
- **finally** 块删除 work_dir（含 MinerU 原始输出）。
- 持久化仅 `parsed_dir` 下三文件 + `assets/`。
- **禁止**在 `raw_vault` 下创建 temp。

---

## 9. 路径与幂等策略

### 9.1 raw_vault（002 两档 — 权威）

```python
vault_dir = build_vault_dir(config.storage.raw_vault_root, sha256)
original_bin = build_vault_artifact_paths(vault_dir)["original_bin"]
```

- 允许 service 内 `_resolve_vault_dir()` 封装（对齐 005）。
- **禁止**修改 `vault_paths.py` / `file_content_vault.py`。

### 9.2 parsed（005 三档 — 复用）

```python
parsed_dir = build_parsed_content_dir(config.storage.parsed_root, sha256)
artifacts = build_parsed_artifact_paths(parsed_dir)
```

- **禁止**修改 `parsed_paths.py`（007 只读 import）。
- `assets/` 为 `parsed_dir / "assets"`，不纳入 `ParsedArtifactPaths` TypedDict（避免改 005 核心 helper）。

### 9.3 幂等

| 场景 | 行为 |
|------|------|
| 已有 SUCCESS manifest（`parser_name=mineru` + `007_mvp_v1`） | **skip**，`skip_reason=idempotent_success_manifest` |
| `--force` | 忽略 SUCCESS 幂等，**允许**覆盖三文件 + assets |
| FAILED / EMPTY / 无 manifest | 允许重试 |
| 005 已有同 sha256 manifest | 不冲突（不同 `parser_name`）；PDF content 不应有 005 manifest |

### 9.4 force 行为（P1 TL 裁决）

- `--force` **必须显式**；默认 `false`。
- force 时删除/覆盖 `parsed_dir` 下 007 相关产物（三文件 + `assets/`），再写入新结果。
- **不得** force 覆盖其他 `parser_name` 的 SUCCESS manifest（若检测到 `parser_name=markitdown` 且 SUCCESS → skip 或 FAILED `CONFLICTING_MANIFEST`，**DB Review 择一**；P1 建议：**skip** + `skip_reason=conflicting_parser_manifest`）。

---

## 10. 错误状态设计

### 10.1 Item / Manifest `status`

| status | 含义 | 写 parsed_text | 写 assets |
|--------|------|----------------|-----------|
| `SUCCESS` | 解析成功，有非空文本 | ✅ | 若 MinerU 产出则 ✅ |
| `EMPTY` | 成功但文本为空/仅空白 | ✅（空文件） | 可选 |
| `FAILED` | 解析失败 | ❌ | ❌ |
| `SKIPPED` | out-of-scope / 幂等 / limit | ❌ | ❌ |
| `TIMEOUT` | 超时（manifest 可用 `FAILED` + code，或独立 status） | ❌ | ❌ |
| `DEPENDENCY_MISSING` | 全局 CLI 预检失败 | — | — |
| `UNSUPPORTED` | 保留给 route 层 skip | — | — |
| `PARTIAL` | 文本成功但部分 assets 复制失败 | ✅ | 部分；manifest `warnings` |

**P1 建议**：`TIMEOUT` 在 manifest 存为 `status=FAILED` + `error.code=TIMEOUT`；report `summary` 可单独计 `timeout_count`。若 QA 需要顶层 `TIMEOUT` status，Dev 可在 report item 使用 `status=TIMEOUT`（manifest 仍 FAILED）。

### 10.2 Report summary 计数

对齐 005，增加可选：`timeout_count`、`dependency_missing`（全局）、`partial_count`。

---

## 11. 报告 JSON 契约

**文件名**：`parse_mineru_pdf_report_{UTC}.json`

| 字段 | 说明 |
|------|------|
| `report_type` | `parse_mineru_pdf_report` |
| `parser_name` | `mineru` |
| `parser_adapter_version` | `007_mvp_v1` |
| `pipeline_version` | config |
| `generated_at` | ISO UTC |
| `dry_run` | bool |
| `filters` | sha256 / content_uid / limit / force / timeout / register |
| `summary` | total_candidates, in_scope_candidates, parsed_count, skipped_count, failed_count, empty_count, timeout_count, partial_count |
| `items[]` | content_uid, sha256, route_type, status, parsed_dir, skip_reason, dry_run_action, assets_dir |
| `errors[]` | FAILED 详情 |

**006 ingest 兼容**：`register_parse_report` 从 report 读取 `parser_name` / `parser_adapter_version`；007 report **不得** `dry_run=true` 时被 register（M3 延续）。

---

## 12. CLI 设计 — `parse-mineru-pdf`

### 12.1 命令

```bash
python -m app.cli.main parse-mineru-pdf [OPTIONS]
```

### 12.2 选项

| 选项 | 默认 | 说明 |
|------|------|------|
| `--config PATH` | `config/app.yaml` | 配置 |
| `--sha256 HEX` | — | 仅处理指定内容 |
| `--content-uid UID` | — | 同 sha256（001 语义） |
| `--limit N` | — | 最多 N 次 **in-scope PDF parse** |
| `--dry-run` | false | 不调用 MinerU；不写 parsed；不写 DB |
| `--force` | false | 覆盖已有 007 SUCCESS 产物 |
| `--no-register` | **true** | 不调用 registry（默认） |
| `--register` | false | 解析完成后 `register_parse_report`（非 dry-run） |
| `--timeout SECONDS` | 600 | MinerU subprocess 超时 |

**注**：`--register` / `--no-register` 实现为 flag；默认 `--no-register`。

### 12.3 护栏

| 规则 | 行为 |
|------|------|
| 无 `--sha256` / `--content-uid` / `--limit` | exit 1 |
| `--limit < 1` | exit 1 |
| `--limit > 100` | exit 1（`PARSE_MINERU_PDF_MAX_LIMIT = 100`） |
| `--limit` 语义 | 仅 in-scope parse 动作；out-of-scope skip **不计入** |
| `--dry-run` + `--register` | **不** register；零 DB 写 |
| 非 dry-run | 预检 MinerU 可用性 |

### 12.4 dry-run 行为

- 不调用 `MinerUAdapter.convert`
- 不写 `parsed/`（无 manifest / text / assets）
- 不写 DB（即使 `--register`）
- 仍写 report（`dry_run=true`，items 用 `dry_run_action=would_parse` / `would_skip`）

---

## 13. 安全与资源控制

| 风险 | 缓解 |
|------|------|
| **PDF 大文件** | 记录 `content_size_bytes`；超时；单条 FAILED continue；limit ≤ 100 |
| **MinerU 长运行** | `--timeout`；report 记 `TIMEOUT` |
| **临时目录泄漏** | `finally` 清理 temp；pytest 断言 |
| **assets 目录膨胀** | 仅复制 MinerU 产出资源；manifest 记录总大小；运维监控 `parsed_root` 磁盘 |
| **并发** | MVP **串行**处理（batch 内无并行 subprocess）；`max_workers=1` |
| **raw_vault 污染** | 输入只读；temp 仅在系统 temp |
| **内存** | 不将整个 PDF 读入内存（交给 MinerU）；Python 侧流式 hash 可选 |

---

## 14. 测试计划（Plan 级）

见 `test_cases.md`。摘要：

| 类别 | 要点 |
|------|------|
| Adapter mock | 默认 mock `MinerUAdapter.convert` |
| MinerU 未安装 | `check_availability` → exit 1 |
| PDF in-scope | `PDF_DIGITAL` 成功三文件 |
| 非 PDF skip | docx / image / unknown |
| dry-run 零写 | 无 parsed / 无 adapter 调用 / 无 DB |
| parsed 写入 | 路径三档 + manifest 字段 |
| register / no-register | 默认无 DB；`--register` 写 registry |
| timeout | mock 挂起 → TIMEOUT |
| force / no-force | 幂等 vs 覆盖 |
| raw_vault 不变 | bin hash 不变 |
| 不覆盖 parsed（无 force） | 第二次 skip |
| 005 / 006 回归 | 全量 pytest |
| assets | mock 返回 asset_files → `assets/` 存在 |

**目标**：007 专项 ≥ **30** test functions；全量回归 120+ 仍 pass。

---

## 15. DB Review 关注点

| ID | 问题 | P1 TL 初步裁决 |
|----|------|----------------|
| **DB-Q1** | 007 是否写 registry？ | 仅 `--register` 且非 dry-run |
| **DB-Q2** | 是否修改 schema？ | **否** — 复用 006 三表 |
| **DB-Q3** | registry 幂等 | 同 `report_path` + `parser_adapter_version` upsert（006 既有） |
| **DB-Q4** | parse result status 映射 | SUCCESS/EMPTY/FAILED/SKIPPED/TIMEOUT/PARTIAL → 对齐 006 `record_parse_result` |
| **DB-Q5** | artifact 类型扩展 | `assets/` 是否新增 `PARSED_ASSETS` 或仅存 `metadata_json` → **P2 DB 裁决** |
| **DB-Q6** | `kb_document` bridge | `parser_profile=mineru_default_v1`；**可能**需薄改 `parse_registry._upsert_document`（**非 schema**） |
| **DB-Q7** | dry-run 零 DB 写 | `--dry-run` 禁止 register；registry dry-run 零写（M2 延续） |
| **DB-Q8** | 与 005 parse_status 冲突 | 同 content 先 markitdown 后 mineru：不同 parser；`parse_status` 取最新 result（006 既有规则） |

**P1 结论**：**需要 P2 DB & Data Plan Review**（registry 衔接与 artifact 策略）；**不需要** 007 migration。

---

## 16. 验收标准（Plan 级）

见 `acceptance.md` A001–A020。

---

## 17. Dev 文件白名单（P4 前预览 — 非最终）

**预计允许新增**：

```text
backend/app/adapters/mineru_adapter.py
backend/app/services/mineru_pdf_parser.py
backend/tests/test_mineru_pdf_parser.py
```

**预计允许修改**：

```text
backend/app/cli/main.py                              # 新增 parse-mineru-pdf
backend/app/services/parse_registry.py               # 仅 mineru parser_profile / ingest 薄扩展（若 P2 批准）
```

**只读 import（禁止改内容）**：

```text
backend/app/core/parsed_paths.py
backend/app/core/vault_paths.py
backend/app/core/parser_routing.py
```

**禁止修改**：

```text
backend/app/services/markitdown_parser.py
backend/app/adapters/markitdown_adapter.py
backend/app/services/inventory_scanner.py
backend/app/services/file_content_vault.py
backend/app/services/parser_router.py
backend/app/services/duplicate_governance.py
sql/**（007 无 migration）
specs/001-006/**
```

---

## 18. 依赖策略

| 依赖 | 策略 |
|------|------|
| MinerU / magic-pdf | **不**默认加入 `requirements.txt`；文档说明可选安装 |
| pytest | mock adapter；CI 不依赖 MinerU 安装 |
| 真实 E2E | 本地 opt-in：安装 MinerU 后对 sample PDF 跑单条 |

---

## 19. 附录 A — P1 待裁决项（P2 DB / P4 TL 关闭）

| ID | 问题 | P1 建议 |
|----|------|---------|
| **Q1** | `PARSED_ASSETS` artifact_type | P2 裁决；MVP 可仅 metadata |
| **Q2** | conflicting markitdown manifest on same sha256 | skip + reason（理论不上发生） |
| **Q3** | subprocess vs Python API | subprocess `magic-pdf` 优先 |
| **Q4** | PARTIAL 是否独立 status | report 层 PARTIAL；manifest FAILED 或 SUCCESS+warnings |
| **Q5** | `--register` 默认 | 默认 `--no-register`（对齐 005） |
| **Q6** | `PDF_SCANNED_OR_IMAGE` 实际触发 | 004 当前不赋值；007 仍 in-scope 集合预留 |

---

## 20. 附录 B — 推荐 E2E 命令

```bash
cd /home/szf/dev/pyws/pkb_sdd/backend
source .venv/bin/activate

# 全链路（含 PDF fixture）
python -m app.cli.main scan --path backend/tests/fixtures
python -m app.cli.main copy-to-vault
python -m app.cli.main parse-mineru-pdf --limit 5

# 可选 registry
python -m app.cli.main parse-mineru-pdf --sha256 <hex> --register
# 或
python -m app.cli.main register-parse-report \
  --report-path ../reports/parse_mineru_pdf_report_*.json
```

---

## 21. 后续阶段建议

| 阶段 | 角色 | 产出 |
|------|------|------|
| **P2** | DB & Data | Plan Review（§15 关注点） |
| **P3** | Dev | 只读实现方案 |
| **P4** | TL | Review & Approval + 最终白名单 |
| **P5** | Dev | Implementation |
| **P6** | DB | Implementation Review |
| **P7** | E2E QA | 验收 A001–A020 |
| **P8** | Handoff | `docs/handoff-phase1-007-mineru-pdf-parser-adapter.md` |
| **P9** | TL | Final Review / merge 决策 |

---

**Plan 结束** — STOP → **P2 DB & Data Plan Review**。

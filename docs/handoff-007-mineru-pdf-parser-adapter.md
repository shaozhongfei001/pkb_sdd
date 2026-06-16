# 阶段交接文档：Phase 1 — 007-mineru-pdf-parser-adapter（MinerU PDF 解析适配器）

> **项目**：个人历史项目文档知识库 `pkb_sdd`  
> **版本基线**：V1.1-SDD  
> **交接日期**：2026-06-16  
> **项目路径**：`/home/szf/dev/pyws/pkb_sdd`  
> **编写角色**：Handoff Agent（`HO`）+ Tech Lead Agent（`TL`）  
> **当前 Spec**：`specs/007-mineru-pdf-parser-adapter`  
> **前置文档**：`docs/handoff-phase1-006-parse-job-registry.md`

---

## 1. 阶段与分支

| 项 | 值 |
|----|-----|
| **Spec 名称** | `007-mineru-pdf-parser-adapter` — MinerU / magic-pdf PDF 解析适配器 |
| **当前分支** | `feature/007-mineru-pdf-parser-adapter` |
| **当前阶段** | **P9 Commit & Handoff**（P5–P8 已完成） |
| **是否已 merge main** | 否 |
| **Schema 变更** | 无（no-schema-change） |

**007 相关 commits**：

```text
cd52002 spec(007): add mineru pdf parser plan
cd9cb5a feat(007): add MinerU PDF parser adapter
```

**关键实现 commit**：`cd9cb5a95bed60f83d8bc55cc8fb63f8fd4fa1b7` — `feat(007): add MinerU PDF parser adapter`

**审查结论**：

| 角色 | 阶段 | 结论 |
|------|------|------|
| Dev | P5 Implementation | 完成 |
| E2E QA | P5-ReQA / P7 E2E | CONDITIONAL PASS |
| Tech Lead | P6 DB Review | PASS |
| Tech Lead | P8 Final Review / Cleanup | PASS |
| Handoff | P9 | 本文件 |

---

## 2. 修改文件清单

| 文件 | 说明 |
|------|------|
| `backend/app/services/mineru_pdf_parser.py` | **新增** — `MineruPdfParserService`、magic-pdf subprocess 编排、parsed 产物写入、batch report、可选 registry 注册 |
| `backend/app/cli/main.py` | **修改** — 新增 `parse-mineru-pdf` CLI 命令 |
| `backend/tests/test_mineru_pdf_parser.py` | **新增** — 007 专项测试（31 cases） |

**未修改（有意保持）**：

- `sql/**` — 无 migration
- `backend/app/models/**` — 无 ORM 变更
- `backend/app/services/parse_registry.py` — 006 registry 原样复用
- `backend/app/services/markitdown_parser.py` — 005 密封

---

## 3. CLI 用法

```bash
cd /home/szf/dev/pyws/pkb_sdd
export PYTHONPATH=backend

# 帮助
backend/.venv/bin/python -m app.cli.main parse-mineru-pdf --help

# 规划（零副作用）
backend/.venv/bin/python -m app.cli.main parse-mineru-pdf \
  --config config/app.yaml \
  --sha256 <SHA256> \
  --dry-run

# 解析（默认不写 DB）
backend/.venv/bin/python -m app.cli.main parse-mineru-pdf \
  --config config/app.yaml \
  --sha256 <SHA256> \
  --no-register \
  --timeout 600

# 强制重解析 + registry 注册
backend/.venv/bin/python -m app.cli.main parse-mineru-pdf \
  --config config/app.yaml \
  --sha256 <SHA256> \
  --force \
  --register \
  --timeout 600

# 批处理（须至少提供 --sha256、--content-uid 或 --limit 之一）
backend/.venv/bin/python -m app.cli.main parse-mineru-pdf \
  --config config/app.yaml \
  --limit 10 \
  --no-register
```

**CLI 选项语义**：

| 选项 | 默认 | 说明 |
|------|------|------|
| `--dry-run` | off | 仅规划；不调用 MinerU、不写 parsed、不写 report、不写 DB |
| `--no-register` / `--register` | **no-register** | 解析完成后是否调用 `ParseRegistryService.register_parse_report()` |
| `--force` | off | 忽略已有 SUCCESS `parse_manifest.json`（`parser_name=mineru`, `parser_adapter_version=007_mvp_v1`） |
| `--timeout` | 600 | magic-pdf subprocess 超时（秒） |

**依赖护栏**：非 dry-run 时检查 `magic-pdf` 是否在 PATH；缺失则 `DEPENDENCY_MISSING` 并 exit 1。

---

## 4. 服务分层

```text
CLI parse-mineru-pdf (main.py)
  └─ MineruPdfParserService (mineru_pdf_parser.py)
       ├─ MySQL SELECT — kb_file_content, kb_raw_vault_object, kb_file_instance（路由 fallback）
       ├─ match_route_type() — 仅 PDF_DIGITAL / PDF_SCANNED_OR_IMAGE 入 scope
       ├─ subprocess magic-pdf → staging dir
       ├─ 产物 finalize → parsed/by_hash/.../
       ├─ batch report → reports_root/parse_mineru_pdf_report_{UTC}.json
       └─ [optional] ParseRegistryService.register_parse_report()
```

**常量**：

| 常量 | 值 |
|------|-----|
| `PARSER_NAME` | `mineru` |
| `PARSER_PROFILE` | `mineru_default_v1` |
| `PARSER_ADAPTER_VERSION` | `007_mvp_v1` |
| `MAGIC_PDF_CMD` | `magic-pdf` |

**测试注入**：`MineruPdfParserService(..., subprocess_runner=...)` 支持 mock subprocess，无需真实 MinerU。

---

## 5. parsed 输出契约（005 对齐）

路径：`parsed/by_hash/{sha256[:2]}/{sha256[2:4]}/{sha256}/`

| 文件 | 说明 |
|------|------|
| `parsed_text.md` | MinerU 主 markdown 输出 |
| `parsed_metadata.json` | parser / route / vault / generated_at 等 |
| `parse_manifest.json` | 006 ingest 主索引；含 status、paths、output_hash |
| `assets/images/` | 可选；manifest 中以 `assets_dir` / `asset_files` 记录（metadata-only，无 PARSED_ASSETS artifact） |

**幂等键**：`parse_manifest.json` 中 `status=SUCCESS` + `parser_name=mineru` + `parser_adapter_version=007_mvp_v1`。

**force 清理范围**：仅 parsed 三件套 + `assets/`；不触碰 `raw_vault/original.bin`。

---

## 6. registry 行为（006 对齐）

- **默认不写 DB**（`--no-register`）。
- **`--register`**：解析完成后调用 `ParseRegistryService.register_parse_report(report_path=...)`。
- **禁止绕过 registry**：service 内无直接 `KbParseRun` / `KbParseResult` / `KbParsedArtifact` 写入。
- **ingest 路径**：registry 通过 batch report `items[].parsed_dir` 定位 `parse_manifest.json`。
- **artifact 类型**：`PARSED_TEXT`、`PARSED_METADATA`、`PARSE_MANIFEST`（+ run 级 `PARSE_REPORT`）。

手动注册（parse 与 register 分离）：

```bash
backend/.venv/bin/python -m app.cli.main register-parse-report \
  --config config/app.yaml \
  --report-path <PATH_TO_parse_mineru_pdf_report_*.json>
```

---

## 7. dry-run / no-register / force 语义

| 模式 | subprocess | parsed 写 | batch report | DB 写 |
|------|------------|-----------|--------------|-------|
| 默认 parse | ✓ | ✓ | ✓ | ✗ |
| `--no-register` | ✓ | ✓ | ✓ | ✗ |
| `--register` | ✓ | ✓ | ✓ | ✓（经 registry） |
| `--dry-run` | ✗ | ✗ | ✗ | ✗ |
| `--dry-run --register` | ✗ | ✗ | ✗ | ✗（CLI 与 service 双重门禁） |
| `--force` | ✓（重跑） | ✓（覆盖） | ✓ | 仅 `--register` 时 |

dry-run 仍会对 MySQL 做 **SELECT**（候选加载与路由规划），这是只读，不是 DB 写。

---

## 8. 测试结果

**P8 最终回归（Handoff 引用）**：

```bash
cd /home/szf/dev/pyws/pkb_sdd

backend/.venv/bin/pytest backend/tests/test_mineru_pdf_parser.py -q
# 31 passed

backend/.venv/bin/pytest \
  backend/tests/test_parser_router.py \
  backend/tests/test_markitdown_parser.py \
  backend/tests/test_parse_job_registry.py -q
# 96 passed

backend/.venv/bin/pytest backend/tests -q
# 151 passed
```

| 模块 | 用例数 |
|------|--------|
| `test_mineru_pdf_parser.py` | 31 |
| 004/005/006 回归合计 | 96 |
| **backend/tests 全量** | **151** |

**007 专项覆盖要点**：

- mock subprocess 成功 / 超时 / 非零退出 / 无 markdown
- manifest 三件套命名与字段完整性
- 幂等（`parse_manifest.json`）与 `--force`
- dry-run 零 parsed / 零 report / 零 DB
- `--register` 真实 `ParseRegistryService` ingest（SUCCESS、artifact ≥ 3）
- route mismatch、missing original.bin、empty markdown、asset incomplete
- CLI 参数解析与 dependency-missing 护栏

---

## 9. 007 完成范围

007 已完成以下验收：

- mock subprocess + 真实 `ParseRegistryService` ingest
- CLI / dry-run / dependency 护栏
- 005 parsed 三件套 contract
- 006 registry ingest 兼容（无 `parse_registry.py` 修改）
- no-schema-change
- 全量 pytest 回归（151 passed）
- NOTE-001 CLI `--force` help 文案修复（`parse_manifest.json`）

**不得声明**：真实 MinerU 生产链路已完整验收。

---

## 10. 已知 caveat：真实 magic-pdf E2E 未完成

**真实 MinerU / magic-pdf E2E 未执行。**

原因：

1. `magic-pdf` 不在 PATH
2. 当前 DB 中唯一 COPIED PDF 的 `vault_path` 指向已删除 `/tmp/p5_reqa_*` 路径
3. 无 COPIED 非 PDF live 样本可用于 CLI ROUTE_MISMATCH 真实验收

**正确表述**：

007 已完成 mock subprocess + 真实 ParseRegistryService ingest + CLI/dry-run/dependency 护栏 + 全量 pytest 回归验收。真实 magic-pdf 端到端解析需在安装 MinerU 并准备干净 PDF vault 样本后补跑。

---

## 11. 后续建议

### 11.1 真实 E2E 补跑命令

```bash
which magic-pdf
magic-pdf --help

PYTHONPATH=backend backend/.venv/bin/python -m app.cli.main scan \
  --config config/app.yaml \
  --path <PDF_SAMPLE_DIR>

PYTHONPATH=backend backend/.venv/bin/python -m app.cli.main copy-to-vault \
  --config config/app.yaml \
  --limit 10

PYTHONPATH=backend backend/.venv/bin/python -m app.cli.main parse-mineru-pdf \
  --config config/app.yaml \
  --sha256 <FRESH_PDF_SHA256> \
  --dry-run

PYTHONPATH=backend backend/.venv/bin/python -m app.cli.main parse-mineru-pdf \
  --config config/app.yaml \
  --sha256 <FRESH_PDF_SHA256> \
  --no-register \
  --timeout 300

PYTHONPATH=backend backend/.venv/bin/python -m app.cli.main parse-mineru-pdf \
  --config config/app.yaml \
  --sha256 <FRESH_PDF_SHA256> \
  --force \
  --register \
  --timeout 300
```

### 11.2 合并前检查

- [ ] 安装并验证 `magic-pdf` 在目标环境 PATH
- [ ] 准备新鲜 PDF 样本（scan → copy-to-vault → 确认 `original.bin` 存在）
- [ ] 补跑真实 E2E 上述命令序列
- [ ] TL Final Review on main merge
- [ ] 可选后续 Spec：registry `parser_family` / `kb_document.parser_profile` 多 parser 桥接（NOTE-003，非 007 范围）

### 11.3 有意未做（007 MVP 范围外）

- 拆分独立 `mineru_adapter.py`（NOTE-002：MVP 接受 service 内联 subprocess）
- `parse_registry.py` kb_document bridge 薄改（NOTE-003）
- `PARSED_ASSETS` artifact 类型逐项索引
- 真实 MinerU 安装与 CI 集成

---

## 12. 下一 Spec 入口

007 完成后，Phase 1 解析链路状态：

```text
001-file-inventory       ✅
002-file-content-vault   ✅
003-duplicate-governance ✅
004-parser-router        ✅
005-markitdown-parser    ✅
006-parse-job-registry   ✅
007-mineru-pdf-parser    ✅ 实现 + CONDITIONAL PASS（真实 E2E 待补）
008+                     ⬜ 按 roadmap 继续
```

**Handoff 结束。**

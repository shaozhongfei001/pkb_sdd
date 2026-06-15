# Test Cases: MinerU PDF Parser Adapter（007）

> **Plan 对照**：`plan.md` §14  
> **验收对照**：`acceptance.md` A001–A020

---

## 正例 — PDF in-scope

| 编号 | 场景 | 输入 | 预期 |
|------|------|------|------|
| **TC001** | PDF_DIGITAL 正例 | vault 中 `.pdf` content；`parse-mineru-pdf --sha256 <hex>` | `route_type=PDF_DIGITAL`；三文件写入；manifest `status=SUCCESS`；`parser_name=mineru` |
| **TC002** | PDF 带 assets | mock adapter 返回 `asset_files` | `{parsed_dir}/assets/` 存在；manifest `assets_dir` 或 metadata 含 `asset_files` |
| **TC003** | EMPTY 输出 | mock 返回空文本 | manifest `status=EMPTY`；`empty_count++` |
| **TC004** | PARTIAL | mock 文本成功、assets 复制部分失败 | report `partial_count++`；manifest 含 warnings |

---

## 跳过 — 非 PDF route_type

| 编号 | 场景 | 输入 | 预期 |
|------|------|------|------|
| **TC010** | DOCX 跳过 | `.docx` | 不调用 MinerU；`status=SKIPPED`；无 parsed 三文件 |
| **TC011** | TEXT 跳过 | `.txt` | 同 TC010 |
| **TC012** | IMAGE 跳过 | `.png` | 同 TC010 |
| **TC013** | UNKNOWN 跳过 | 无 ext | `status=SKIPPED` |
| **TC014** | UNSUPPORTED 跳过 | `.doc` | `status=SKIPPED` |
| **TC015** | PDF mime conflict | `.pdf` + `mime_type=image/png` → UNKNOWN（004） | SKIPPED；不解析 |

---

## MinerU adapter — mock / 依赖

| 编号 | 场景 | 输入 | 预期 |
|------|------|------|------|
| **TC020** | 默认 mock | pytest 绝大多数用例 | `MinerUAdapter.convert` mock；不依赖真实 MinerU |
| **TC021** | MinerU 未安装 | mock `check_availability` 失败 | CLI exit 1；`DEPENDENCY_MISSING` |
| **TC022** | runtime 失败 | mock convert 抛错 | `FAILED`；`PARSER_RUNTIME_ERROR`；continue |
| **TC023** | corrupted PDF | mock 分类 CORRUPTED | `FAILED`；`CORRUPTED_DOCUMENT` |
| **TC024** | password PDF | mock 分类 PASSWORD | `FAILED`；`PASSWORD_PROTECTED` |
| **TC025** | timeout | mock subprocess 超时 | `FAILED`；`error.code=TIMEOUT` |

---

## 错误与边界

| 编号 | 场景 | 输入 | 预期 |
|------|------|------|------|
| **TC030** | missing original.bin | DB 有记录但 bin 缺失 | `FAILED`；`MISSING_ORIGINAL_BIN` |
| **TC031** | FAILED 仅 manifest | convert 失败 | 存在 `parse_manifest.json` FAILED；**无** `parsed_text.md` / `assets/` |
| **TC032** | temp 清理 | 成功或失败后 | 系统 temp 无残留 `pkb_mineru_*`（或上下文 manager 清理） |

---

## CLI 选项与护栏

| 编号 | 场景 | 输入 | 预期 |
|------|------|------|------|
| **TC040** | `--sha256` filter | 指定 hex | 仅该 content |
| **TC041** | `--content-uid` filter | 指定 uid | 同 TC040 |
| **TC042** | `--limit` filter | `--limit 3` | 最多 3 次 in-scope parse |
| **TC043** | 无 filter 拒绝 | 无参数 | exit non-zero |
| **TC044** | limit 上限 | `--limit 101` | exit non-zero |
| **TC045** | `--dry-run` | `--dry-run --limit 5` | 不调用 convert；无 parsed 写入；report `dry_run=true` |
| **TC046** | `--timeout` | 短超时 + 挂起 mock | TIMEOUT |
| **TC047** | limit 不计 out-of-scope | 混合 pdf+docx `--limit 1` | 1 次 PDF parse；docx skip 不占 limit |

---

## 幂等、force 与报告

| 编号 | 场景 | 输入 | 预期 |
|------|------|------|------|
| **TC050** | idempotent skip | 连续两次同 sha256 | 第二次 skip；hash 不变 |
| **TC051** | `--force` 覆盖 | 第二次带 `--force` | 三文件更新；新 manifest |
| **TC052** | report summary | 混合 success/skip/fail | 计数与 items 一致 |
| **TC053** | dry_run_action | `--dry-run` | items 含 `would_parse` / `would_skip` |

---

## vault / parsed 路径

| 编号 | 场景 | 输入 | 预期 |
|------|------|------|------|
| **TC060** | vault via helpers | mock sha256 | `original_bin` 等价于 002 helpers |
| **TC061** | parsed 三档 | 成功 parse | 路径匹配 `{[0:2]}/{[2:4]}/{sha256}` |
| **TC062** | 禁止 raw_vault 三档 | grep / 审查 | 无错误 vault 扇出 |
| **TC063** | 禁止改 vault_paths | git diff | `vault_paths.py` 不在 diff |

---

## Registry — register / no-register

| 编号 | 场景 | 输入 | 预期 |
|------|------|------|------|
| **TC070** | 默认 no-register | parse 成功 | 无 `kb_parse_run` 新增（DB 计数或 mock session） |
| **TC071** | `--register` | parse + register | run / result / artifact 写入；`parser_name=mineru` |
| **TC072** | dry-run + register | 两 flag | 零 DB 写 |
| **TC073** | dry-run report ingest 拒绝 | register dry_run report | `INVALID_DRY_RUN_REPORT`（006 M3） |

---

## 保护 — 无越界 / 回归

| 编号 | 场景 | 输入 | 预期 |
|------|------|------|------|
| **TC080** | no DB write（默认） | parse-mineru-pdf | 无 INSERT/UPDATE/DELETE |
| **TC081** | no schema change | diff sql/ | 无 migration |
| **TC082** | raw_vault unchanged | parse 前后 | bin hash 不变 |
| **TC083** | original files unchanged | fixtures | stat/hash 不变 |
| **TC084** | no curated/vector/project card | grep | 无越界路径 |
| **TC085** | 005 回归 | `test_markitdown_parser.py` | 全 pass |
| **TC086** | 006 回归 | `test_parse_job_registry.py` | 全 pass |
| **TC087** | 全量回归 | `pytest -q` | 120+ pass |

---

## 集成 E2E（可选 — 真实 MinerU）

| 编号 | 场景 | 输入 | 预期 |
|------|------|------|------|
| **TC090** | 真实 MinerU PDF | 本地安装 MinerU + sample PDF；`--limit 1` | 三文件 + 可选 assets；**opt-in**，CI 不强制 |
| **TC091** | 中文路径 fixture | fixtures 含中文名 PDF | 路径正确；不修改原始文件 |

---

## 测试策略摘要

| 策略 | 说明 |
|------|------|
| **默认 mock** | CI / pytest 不依赖 MinerU 安装 |
| **真实 MinerU** | 本地 opt-in；单条 PDF 验证 |
| **DB 测试** | 默认 no-register；register 用例可 mock `ParseRegistryService` 或测试库 |
| **数量目标** | ≥ **30** test functions in `test_mineru_pdf_parser.py` |

---

## 推荐执行命令

```bash
cd /home/szf/dev/pyws/pkb_sdd/backend
source .venv/bin/activate

# 007 专项
pytest -q tests/test_mineru_pdf_parser.py

# 全量回归
pytest -q tests/test_inventory_scanner.py tests/test_file_content_vault.py \
  tests/test_duplicate_governance.py tests/test_parser_router.py \
  tests/test_markitdown_parser.py tests/test_parse_job_registry.py \
  tests/test_mineru_pdf_parser.py
```

---

**Test Cases 结束**

# Acceptance: MarkItDown 普通文档解析（005）

> **Spec**：`specs/005-markitdown-parser`  
> **Plan 对照**：`plan.md` §24、§19  
> **测试对照**：`test_cases.md`

---

## A001 范围符合 — 只处理 MarkItDown-family 四 route_type

005 只解析 **DOCX、PPTX、XLSX、TEXT_OR_MARKDOWN**。

- 存在 MarkItDown adapter + service + CLI `parse-markitdown`
- 不是通用 parser 框架
- `build-parse-queue`、`parse` 保持 placeholder

## A002 跳过 PDF / IMAGE / UNKNOWN / UNSUPPORTED

以下 `route_type` **不得**调用 MarkItDown，须 **SKIPPED** 并写入 report：

- `PDF_DIGITAL`、`PDF_SCANNED_OR_IMAGE`、`IMAGE`、`UNKNOWN`、`UNSUPPORTED`

## A003 parsed 产物路径正确

每个成功解析的 content，三文件位于：

```text
{parsed_root}/by_hash/{sha256[0:2]}/{sha256[2:4]}/{sha256}/
  parsed_text.md
  parsed_metadata.json
  parse_manifest.json
```

## A004 manifest 可追溯

`parse_manifest.json` 必须含：

- `content_uid`、`sha256`、`source_vault_path`
- `route_type`、`parser_name`、`parser_adapter_version`
- `parsed_text_path`、`parsed_metadata_path`、`generated_at`、`status`

## A005 raw_vault 不变 — 002 两档路径

执行 parse 前后：

- `raw_vault/**` 目录 listing 不变
- 每个 `original.bin` SHA256 不变
- 无 create/delete/overwrite/truncate raw_vault 文件
- **禁止** raw_vault 三档路径 `{sha256[2:4]}/`
- **禁止**修改 `backend/app/core/vault_paths.py`

## A005b raw_vault 路径解析权威

`original.bin` 路径 **必须**通过 002 helpers 得到：

```text
build_vault_dir(raw_vault_root, sha256)
build_vault_artifact_paths(vault_dir)["original_bin"]
```

- pytest 断言 service 调用上述 helpers（或等价 `_resolve_original_bin` 内部调用）
- **禁止** 005 自行拼接 raw_vault 三档路径

## A006 原始文件不变

执行 parse 前后，用户原始 fixture 文件 stat / 内容 hash 不变。

- CLI 入口调用 `ensure_readonly()`
- 005 不以 `source_path` 作为解析输入

## A007 不写 DB

005 对 MySQL **仅 SELECT**。

- **禁止** INSERT/UPDATE/DELETE
- **禁止** upsert `kb_parse_job`
- **禁止** upsert `kb_document`
- **禁止** update `kb_file_content.parse_status`
- 代码审查 + pytest 断言

## A008 不改 SQL schema

005 MVP 不修改 `sql/001_init_schema_v1_1.sql`，不新增 migration。

## A009 不写 curated / 向量库 / 项目卡

不得写入 `curated/`；无 embedding、向量库、项目卡蒸馏、Streamlit 相关代码或产物。

## A010 不接 MinerU

005 不得 import、subprocess 或调用 MinerU；不做 PDF/图片解析。

## A011 不做 OCR

005 不得调用 OCR 引擎或依赖 OCR 专用库处理扫描件。

## A012 parser error continue

单 content 的 parser import（单条）、runtime、corrupted、password 等错误：

- 该条 `status=FAILED` 记入 report
- **写** `parse_manifest.json`（`status=FAILED` + `error`）
- **不写** `parsed_text.md`
- **不中断**批处理其余 content

## A013 empty output 有明确状态

MarkItDown 返回空文本时：

- `parse_manifest.json` 中 `status=EMPTY`
- report `empty_count` 递增
- 行为与 plan §11、§16 一致（非 FAILED）

## A014 corrupted / password 有错误记录

损坏或密码保护文档：

- `errors[]` 含 `content_uid`、`sha256`、`code`、`message`
- item `status=FAILED`

## A015 CLI 护栏与 dry-run 可测

| 行为 | 预期 |
|------|------|
| 无 `--sha256`/`--content-uid`/`--limit` | exit non-zero |
| `--limit 101` | exit non-zero（上限 100） |
| `--sha256` / `--content-uid` | 仅处理指定 content |
| `--limit N` | 最多 N 次 **in-scope parse**；out-of-scope skip **不计入** limit |
| `--dry-run` | **不调用** MarkItDown；不写 parsed 三文件；report `dry_run=true`；would_parse/would_skip |

## A016 幂等可测

同 `sha256` 在已有 `parse_manifest.json` 且 `status=SUCCESS` 且 version 一致时：

- 第二次执行 **skip**，不覆盖三文件
- report `skipped_count` 反映 skip

## A017 测试通过

```bash
pytest -q tests/test_markitdown_parser.py
pytest -q tests/test_inventory_scanner.py tests/test_file_content_vault.py \
  tests/test_duplicate_governance.py tests/test_parser_router.py \
  tests/test_markitdown_parser.py
```

- CLI E2E：`scan` → `copy-to-vault` → `parse-markitdown --limit N`
- `parse_markitdown_report_*.json` 存在于 reports_root；含 `in_scope_candidates`
- 005 新增 ≥20 test functions
- **默认 mock** MarkItDownAdapter；真实 markitdown 集成 **仅限** txt/md fixture

## A018 vault_paths 与 file_content_vault 不可修改

P5 实现 diff **不得**包含：

- `backend/app/core/vault_paths.py`
- `backend/app/services/file_content_vault.py`

QA 可通过 `git diff --name-only` 或实现前 baseline 对比验证。

---

**Acceptance 结束** — QA 输出验收表时须逐条附证据（命令输出、路径 listing、hash、grep）。

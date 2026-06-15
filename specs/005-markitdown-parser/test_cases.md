# Test Cases: MarkItDown 普通文档解析（005）

> **Plan 对照**：`plan.md` §23  
> **验收对照**：`acceptance.md` A001–A018

---

## 正例 — MarkItDown-family route_type

| 编号 | 场景 | 输入 | 预期 |
|------|------|------|------|
| **TC001** | DOCX 正例 | vault 中 `.docx` content；`parse-markitdown --sha256 <hex>` | `route_type=DOCX`；三文件写入；manifest `status=SUCCESS`；`parsed_text.md` 非空（或 fixture 允许 EMPTY 若 mock） |
| **TC002** | PPTX 正例 | vault 中 `.pptx` | 同 TC001，`route_type=PPTX` |
| **TC003** | XLSX 正例 | vault 中 `.xlsx` | 同 TC001，`route_type=XLSX` |
| **TC004** | TXT 正例 | `.txt` → `TEXT_OR_MARKDOWN` | 解析成功；manifest `route_type=TEXT_OR_MARKDOWN` |
| **TC005** | MD 正例 | `.md` | 同 TC004 |
| **TC006** | CSV 正例 | `.csv` | 同 TC004 |
| **TC007** | HTML 正例 | `.html` / `.htm` | 同 TC004 |
| **TC008** | JSON 正例 | `.json` | 同 TC004 |
| **TC009** | XML 正例 | `.xml` | 同 TC004 |

---

## 跳过 — 非 005 route_type

| 编号 | 场景 | 输入 | 预期 |
|------|------|------|------|
| **TC010** | PDF 跳过 | `.pdf` → `PDF_DIGITAL` | **不**调用 MarkItDown；item `status=SKIPPED`；**无** parsed 三文件 |
| **TC011** | IMAGE 跳过 | `.png` / `.jpg` | 同 TC010 |
| **TC012** | UNKNOWN 跳过 | 无 ext 且 fallback 失败 | `status=SKIPPED`；不解析 |
| **TC013** | legacy office 跳过 | `.doc` → UNSUPPORTED | `status=SKIPPED` |
| **TC014** | route conflict | `.pdf` + `mime_type=image/png` → UNKNOWN（004 规则） | SKIPPED 或 FAILED（与 `match_route_type` 一致）；**不**解析 |

---

## 错误与边界

| 编号 | 场景 | 输入 | 预期 |
|------|------|------|------|
| **TC015** | missing original.bin | DB 有 vault_path 但 bin 缺失 | `FAILED`；`error.code=MISSING_ORIGINAL_BIN`；批处理 continue |
| **TC016** | corrupted document | 损坏 docx bin | `FAILED`；`CORRUPTED_DOCUMENT`；continue |
| **TC017** | password protected | 密码保护 office（fixture 或 mock） | `FAILED`；`PASSWORD_PROTECTED`；continue |
| **TC018** | parser import failure | mock import markitdown 失败 | 单条 FAILED 或全局 exit non-zero（与 plan Q9 一致） |
| **TC019** | parser runtime failure | mock convert 抛异常 | `FAILED`；`PARSER_RUNTIME_ERROR`；continue |
| **TC020** | empty output | mock 返回空字符串 | manifest `status=EMPTY`；`empty_count++` |

---

## CLI 选项与护栏

| 编号 | 场景 | 输入 | 预期 |
|------|------|------|------|
| **TC021** | `--sha256` filter | 指定 hex | 仅该 content 进入处理 |
| **TC022** | `--content-uid` filter | 指定 uid | 同 TC021 |
| **TC023** | `--limit` filter | `--limit 3` | 最多 3 个 in-scope |
| **TC024** | 无 filter 拒绝 | 无任何 filter 参数 | exit non-zero |
| **TC025** | limit 上限 | `--limit 101` | exit non-zero |
| **TC026** | `--dry-run` | `--dry-run --limit 5` | **不调用** MarkItDownAdapter.convert；parsed 目录无新增/修改；report `dry_run=true` |

---

## 幂等与报告

| 编号 | 场景 | 输入 | 预期 |
|------|------|------|------|
| **TC027** | existing success skip | 连续两次 parse 同 sha256 | 第二次 skip；三文件 hash 不变 |
| **TC028** | report summary | 混合 success/skip/fail | `total_candidates`=SQL 行数；`in_scope_candidates` 与 items 一致；计数正确 |

---

## vault 路径 — 002 权威（P4 TL）

| 编号 | 场景 | 输入 | 预期 |
|------|------|------|------|
| **TC038** | vault 路径 via helpers | mock sha256 | `_resolve_original_bin` 等价于 `build_vault_artifact_paths(build_vault_dir(root, sha256)).original_bin` |
| **TC039** | 禁止 raw_vault 三档 | 代码审查 / grep | 无 `{sha256[2:4]}` 拼接用于 raw_vault；parsed 三档仅出现在 `parsed_paths.py` |
| **TC040** | 禁止改 vault_paths | git diff | `vault_paths.py`、`file_content_vault.py` 不在 P5 diff 中 |

---

## 测试策略 — mock vs 真实 markitdown（P4 TL）

| 编号 | 场景 | 输入 | 预期 |
|------|------|------|------|
| **TC041** | 默认 mock adapter | 绝大多数 pytest | `MarkItDownAdapter.convert` 被 mock；不依赖 Office 运行时 |
| **TC042** | 真实 markitdown txt/md | 可选集成测试 `.txt`/`.md` fixture | 可调用真实 markitdown；docx/pptx/xlsx **仍 mock** |
| **TC043** | FAILED 仅 manifest | mock convert 抛错 | 存在 `parse_manifest.json` status=FAILED；**无** `parsed_text.md` |
| **TC044** | limit 不计 out-of-scope skip | 混合 pdf+docx，`--limit 1` | 仅 1 次 in-scope parse；pdf skip 不占 limit |

---

## 保护 — 无 DB / 无 schema / 无越界写入

| 编号 | 场景 | 输入 | 预期 |
|------|------|------|------|
| **TC029** | no DB write | 执行 parse-markitdown | 无 INSERT/UPDATE/DELETE；无 parse_status 变化 |
| **TC030** | no schema change | 实现前后 `sql/**` diff | 无 migration；无 init SQL 修改 |
| **TC031** | raw_vault unchanged | parse 前后 | bin hash + listing 不变 |
| **TC032** | original files unchanged | fixtures 全链路 | stat/hash 不变 |
| **TC033** | no curated/vector/project card | parse 前后 | `curated/` 无新增；无 embedding 代码路径 |

---

## 集成 E2E

| 编号 | 场景 | 输入 | 预期 |
|------|------|------|------|
| **TC034** | CLI E2E | `scan` → `copy-to-vault` → `parse-markitdown --limit 10` | exit 0；report 存在；≥1 SUCCESS 或 SKIP（视 fixtures） |
| **TC035** | 中文路径 | `tests/fixtures/中文路径/` 全链路 | 路径正确；无编码错误 |
| **TC036** | 004 回归 | 全量 pytest 001–004 + 005 | 全部 pass |
| **TC037** | no MinerU | grep / import 审查 | 无 mineru |

---

## pytest 映射（建议）

| Test Case | 建议 test function（`test_markitdown_parser.py`） |
|-----------|---------------------------------------------------|
| TC001–TC003 | `test_parse_docx_success`、`test_parse_pptx_success`、`test_parse_xlsx_success` |
| TC004–TC009 | `test_parse_text_or_markdown_*`（参数化 ext） |
| TC010–TC014 | `test_skip_pdf`、`test_skip_image`、`test_skip_unknown`、`test_skip_unsupported` |
| TC015–TC020 | `test_missing_original_bin`、`test_corrupted_document`、… |
| TC021–TC026 | `test_cli_sha256_filter`、`test_cli_no_filter_rejected`、`test_cli_dry_run` |
| TC027–TC028, TC044 | `test_idempotent_skip_success`、`test_report_summary_counts`、`test_limit_excludes_out_of_scope_skip` |
| TC029–TC033 | `test_no_db_write`、`test_raw_vault_unchanged`、`test_original_files_unchanged` |
| TC034–TC037 | `test_parse_markitdown_integration`、`test_chinese_path_integration` |
| TC038–TC040 | `test_resolve_original_bin_via_vault_paths`、`test_no_raw_vault_three_tier_path`、`test_vault_paths_not_modified` |
| TC041–TC043 | mock 默认 + 可选 `test_real_markitdown_txt_integration`、`test_failed_writes_manifest_only` |

---

**Test Cases 结束** — 共 **44** 条；Dev 实现时须全部可映射到 pytest 或 QA 手工步骤。

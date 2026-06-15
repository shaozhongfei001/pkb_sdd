# Acceptance: Parse Job Registry（006）

> **Spec**：`specs/006-parse-job-registry`  
> **Plan 对照**：`plan.md` §22、§9–§20  
> **测试对照**：`test_cases.md`

---

## A001 SQL schema 经 DB Review

- migration `006_parse_registry_v1.sql` 存在且 **additive only**
- DB Plan Review 结论为 **PASS** 或 **PASS_WITH_NOTES**（无阻断项）
- ORM 字段与 migration SQL 一致；无未文档化列
- **不修改** `sql/001_init_schema_v1_1.sql`

## A002 Registry 不破坏 001–005

- 001–005 CLI 行为不变；005 pytest 全 pass
- **不修改** `markitdown_parser.py`、`parser_router.py`、001–003 封闭 service
- 004/005 磁盘语义不变

## A003 不重写 raw_vault

- registry 前后 `raw_vault/**` listing 与 `original.bin` SHA256 不变
- 无 create/delete/overwrite/truncate raw_vault

## A004 不重写 parsed

- 默认 register/reconcile **只读** parsed 产物
- `parsed_text.md` / `parsed_metadata.json` / `parse_manifest.json` hash 在 register 前后不变
- 无 truncate/overwrite parsed（除非未来 TL 授权的显式 repair，MVP 无）

## A005 不重新解析文件

- 006 CLI **不** import/call MarkItDown / MinerU / OCR
- **不** read `original.bin` 做解析
- 重新解析仅当用户 **显式** 运行 005 `parse-markitdown`（非 006 默认）

## A006 Parse job（run）可记录一次运行

- `register-parse-report` 创建/upsert **`kb_parse_run`**
- 含 `run_uid`、`parser_name`、`parser_adapter_version`、`status`、summary 计数、`report_path`、时间戳
- 同一 report 重复 register 幂等（不 duplicate run）

## A007 Parse result 可记录单个 content 结果

- 每个 report item + manifest 对应 **`kb_parse_result`** 行
- 含 `content_uid`、`sha256`、`route_type`、`status`、路径字段、error 字段

## A008 Parsed artifact 可索引三文件产物

- SUCCESS/EMPTY：`PARSED_TEXT`、`PARSED_METADATA`、`PARSE_MANIFEST` 三类 artifact
- FAILED：至少 `PARSE_MANIFEST`
- run 级：`PARSE_REPORT` 索引（可选，Plan Q14）

## A009 失败原因可追踪

- FAILED result 含 `error_code`、`error_message`
- 与 manifest `error` 或 report `errors[]` 一致

## A010 重试关系可追踪

- 同 content 新 result 失败后再成功/失败时，可设置 **`retry_of_result_id`**
- 查询可还原 retry 链

## A011 dry-run 不写 DB

- `register-parse-report --dry-run` 与 `reconcile-parsed-artifacts --dry-run`：
  - 无 INSERT/UPDATE registry 三表
  - 无 parse_status / kb_document 变更
  - 输出 preview / would_register 证据

## A012 Registry 写入事务一致

- 单 content：result + artifacts + kb_document + parse_status **同一 transaction**
- 单条失败 rollback 当前 content；不污染其他 content
- run 终态 summary 与 results 计数一致

## A013 不接 MinerU / OCR

- 无 mineru / ocr import 或 subprocess
- 不做 PDF / IMAGE 解析

## A014 不做 curated / vector / project card

- 不写 `curated/`、`kb_curated_asset`、`kb_embedding_ref`、`kb_document_chunk`
- 无 embedding / LLM / Streamlit 代码路径

## A015 测试通过

```bash
# migration（测试环境）
mysql ... < sql/migrations/006_parse_registry_v1.sql

# 006 专项
pytest -q tests/test_parse_registry.py

# 全链路回归
pytest -q tests/test_inventory_scanner.py tests/test_file_content_vault.py \
  tests/test_duplicate_governance.py tests/test_parser_router.py \
  tests/test_markitdown_parser.py tests/test_parse_registry.py
```

- CLI E2E：`scan` → `copy-to-vault` → `parse-markitdown --limit N` → `register-parse-report --report-path ...`
- reconcile：`reconcile-parsed-artifacts --limit N`（opt-in）可测
- migration upgrade + 重复 migrate idempotency 测试 pass
- 006 新增 ≥25 test functions

---

**Acceptance 结束** — QA 输出验收表时须逐条附证据（MySQL 查询、pytest、CLI 输出、hash/stat）。

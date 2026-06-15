# Acceptance: Parse Job Registry（006）

> **Spec**：`specs/006-parse-job-registry`  
> **Plan 对照**：`plan.md` §22、§9–§20、附录 A Q16–Q21  
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
- 无 truncate/overwrite parsed（MVP 无 repair 子命令）

## A005 不重新解析文件

- 006 CLI **不** import/call MarkItDown / MinerU / OCR
- **不** read `original.bin` 做解析
- 重新解析仅当用户 **显式** 运行 005 `parse-markitdown`

## A006 Parse job（run）可记录一次运行

- `register-parse-report` 创建/upsert **`kb_parse_run`**
- 含 `run_uid`（§5.1 公式）、`parser_name`、`status`、summary、`report_path`、时间戳
- 同一 report 重复 register 幂等

## A007 Parse result 可记录单个 content 结果

- 每个 report item + manifest 对应 **`kb_parse_result`** 行
- 含 `content_uid`、`sha256`、`route_type`、`status`、路径、error 字段

## A008 Parsed artifact 可索引三文件产物

- SUCCESS/EMPTY：`PARSED_TEXT`、`PARSED_METADATA`、`PARSE_MANIFEST`（文件存在时）
- FAILED：`PARSE_MANIFEST`（005 FAILED manifest 存在时）
- SKIPPED 且无 manifest：**零** artifact 行（S4）
- run 级：`PARSE_REPORT`（`content_uid=''`）

## A009 失败原因可追踪

- FAILED result 含 `error_code`、`error_message`

## A010 重试关系可追踪

- `retry_of_result_id` 可还原 retry 链

## A011 dry-run 不写 DB（M2 / Q17）

- 006 `register-parse-report --dry-run` 与 `reconcile-parsed-artifacts --dry-run`：
  - **零** INSERT/UPDATE：`kb_parse_run`、`kb_parse_result`、`kb_parsed_artifact`、`kb_document`、`kb_file_content.parse_status`
  - 禁止 `DRY_RUN_COMPLETED` 或任何 dry-run 状态入库
  - 可写磁盘 `registry_report_*.json` preview

## A012 Registry 写入事务一致

- 单 content persist：result + artifacts + kb_document + parse_status 同一 transaction
- 单条失败 rollback 当前 content；continue

## A013 不接 MinerU / OCR

- 无 mineru / ocr import 或 subprocess

## A014 不做 curated / vector / project card

- 不写 curated / chunk / embedding 相关表或目录

## A015 测试通过

- pytest 006 专项 + 001–005 回归 pass（≥25 006 functions）
- CLI E2E：parse-markitdown（非 dry-run）→ register-parse-report

## A016 Artifact UNIQUE 含 run_uid（M1 / Q16）

- migration 与 ORM 使用 **`uk_artifact_scope(run_uid, content_uid, artifact_type, parser_name, parser_adapter_version)`**
- **不得**使用 `uk_artifact_content_type(content_uid, ...)`
- 同一 content 不同 run 可并存多条 artifact 行

## A017 Registry dry-run 零 DB 写（M2 / Q17）

- 006 registry `--dry-run` 前后 MySQL 行数不变（registry 三表 + parse_status + kb_document）
- 证据：pytest + CLI 前后 SELECT COUNT

## A018 005 dry-run report 拒绝 ingest（M3 / Q18）

- `register-parse-report` 对 `report.dry_run=true`：**exit non-zero**
- 错误码 **`INVALID_DRY_RUN_REPORT`**
- **零** registry 行写入

## A019 document_uid 规则（M4 / Q19）

- `kb_document.document_uid` **恒等于** `content_uid`
- **禁止** sha256 或其它 hash 作为 document_uid 备选
- QA：`SELECT document_uid, content_uid FROM kb_document` 逐行相等

---

**Acceptance 结束** — QA 须逐条附证据。

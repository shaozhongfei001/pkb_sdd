# Test Cases: Parse Job Registry（006）

> **Plan 对照**：`plan.md` §21  
> **验收对照**：`acceptance.md` A001–A015

---

## Migration

| 编号 | 场景 | 输入 | 预期 |
|------|------|------|------|
| **TC001** | migration upgrade | clean test DB | 三表创建成功 |
| **TC002** | migration idempotency | 连续执行 migration 两次 | 无 error；表结构不变 |
| **TC003** | migration clean DB test | pytest fixture 空库 | ORM 可 CRUD |

---

## Parse Job（Run）

| 编号 | 场景 | 输入 | 预期 |
|------|------|------|------|
| **TC010** | create parse job | `register-parse-report` 有效 report | `kb_parse_run` 行；status 终态 COMPLETED/PARTIAL |
| **TC011** | update parse job status | register 过程中 | PENDING→RUNNING→终态 |
| **TC012** | report_path 记录 | register | `report_path` 与源文件一致 |
| **TC013** | duplicate register idempotent | 同一 report 注册两次 | 单 run_uid；summary 一致 |
| **TC014** | dry-run job | `--dry-run` | 无 run/result/artifact 行；或 status=DRY_RUN_COMPLETED 且无子表 |

---

## Parse Result

| 编号 | 场景 | 输入 | 预期 |
|------|------|------|------|
| **TC020** | insert parse result success | item SUCCESS + manifest | result.status=SUCCESS；路径字段齐全 |
| **TC021** | insert parse result skipped | item SKIPPED | result.status=SKIPPED |
| **TC022** | insert parse result failed | item FAILED + manifest error | result.status=FAILED；error_code/message |
| **TC023** | insert parse result empty | manifest EMPTY | result.status=EMPTY |
| **TC024** | retry_of_result_id | 同 content 先 FAILED 后 SUCCESS register | 新 result.retry_of_result_id 指向前条 |
| **TC025** | parse_status update | SUCCESS result | kb_file_content.parse_status=PARSED |
| **TC026** | kb_document bridge | SUCCESS/EMPTY | kb_document upsert；路径与 result 一致 |

---

## Parsed Artifact

| 编号 | 场景 | 输入 | 预期 |
|------|------|------|------|
| **TC030** | insert parsed artifact parsed_text | SUCCESS manifest | artifact_type=PARSED_TEXT；hash/size |
| **TC031** | insert parsed artifact parsed_metadata | SUCCESS manifest | artifact_type=PARSED_METADATA |
| **TC032** | insert parsed artifact parse_manifest | 任意 status | artifact_type=PARSE_MANIFEST |
| **TC033** | insert parsed artifact parse_report | register run | artifact_type=PARSE_REPORT（run 级） |
| **TC034** | missing artifact file | text 路径不存在 | artifact status=MISSING；result 仍登记 |

---

## Reconcile

| 编号 | 场景 | 输入 | 预期 |
|------|------|------|------|
| **TC040** | reconcile existing parsed artifact | `reconcile-parsed-artifacts --sha256 HEX` | result+artifact 从 manifest 补齐；trigger_type=RECONCILE |
| **TC041** | reconcile no filter rejected | 无 sha256/limit/content-uid | exit non-zero |
| **TC042** | reconcile limit cap | `--limit 101` | exit non-zero（上限 100） |
| **TC043** | reconcile no re-parse | reconcile 前后 | 无 MarkItDown 调用；parsed hash 不变 |

---

## 保护 — 磁盘 / 越界

| 编号 | 场景 | 输入 | 预期 |
|------|------|------|------|
| **TC050** | no raw_vault mutation | register + reconcile | raw_vault listing + bin hash 不变 |
| **TC051** | no parsed mutation | register + reconcile | parsed 三文件 hash 不变 |
| **TC052** | no MinerU/OCR | grep / import 审查 | 无 mineru/ocr |
| **TC053** | no curated/vector/project card | register 前后 | curated 无新增；无 chunk/embedding 写 |

---

## CLI 查询

| 编号 | 场景 | 输入 | 预期 |
|------|------|------|------|
| **TC060** | list-parse-jobs | 有 run 数据 | 输出 run 摘要列表 |
| **TC061** | show-parse-job | `--run-uid` | 详情含 summary |
| **TC062** | list-parse-results | `--content-uid` | 过滤正确 |
| **TC063** | list-parsed-artifacts | `--artifact-type PARSED_TEXT` | 过滤正确 |

---

## 错误与批处理

| 编号 | 场景 | 输入 | 预期 |
|------|------|------|------|
| **TC070** | invalid report JSON | 损坏 report | run FAILED；exit non-zero |
| **TC071** | invalid manifest | 损坏 manifest | 该 content result FAILED；continue |
| **TC072** | unknown content sha256 | manifest 有但 DB 无 content | errors[]；skip 或 FAILED（与 plan 一致） |
| **TC073** | single failure continue | 混合 valid/invalid manifest | 有效 content 仍登记 |

---

## 集成 E2E

| 编号 | 场景 | 输入 | 预期 |
|------|------|------|------|
| **TC080** | CLI E2E full chain | scan→copy→parse-markitdown→register-parse-report | exit 0；DB 有 run/result/artifact |
| **TC081** | 005 regression | 全量 pytest 含 test_markitdown_parser | 全部 pass |
| **TC082** | 中文路径 | fixtures 全链路 + register | 路径正确；无编码错误 |
| **TC083** | transaction consistency | 模拟 DB 中途失败 | 当前 content rollback；其他 content 不受影响 |

---

## pytest 映射（建议）

| Test Case | 建议 test function |
|-----------|-------------------|
| TC001–TC003 | `test_migration_upgrade`、`test_migration_idempotent` |
| TC010–TC014 | `test_register_creates_run`、`test_register_dry_run` |
| TC020–TC026 | `test_result_success/skipped/failed/empty`、`test_retry_chain`、`test_parse_status_update` |
| TC030–TC034 | `test_artifact_text/metadata/manifest/report` |
| TC040–TC043 | `test_reconcile_opt_in`、`test_reconcile_no_filter_rejected` |
| TC050–TC053 | `test_no_raw_vault_mutation`、`test_no_parsed_mutation` |
| TC060–TC063 | `test_cli_list_show_*` |
| TC070–TC073 | `test_invalid_report/manifest`、`test_continue_on_error` |
| TC080–TC083 | `test_register_e2e_integration`、`test_005_regression` |

---

**Test Cases 结束** — 共 **34** 条；Dev 实现时须全部可映射到 pytest 或 QA 手工步骤。

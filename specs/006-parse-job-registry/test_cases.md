# Test Cases: Parse Job Registry（006）

> **Plan 对照**：`plan.md` §21、附录 A Q16–Q21  
> **验收对照**：`acceptance.md` A001–A019

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
| **TC010** | create parse job | `register-parse-report` 有效 report | `kb_parse_run` 行；status COMPLETED/PARTIAL |
| **TC011** | update parse job status | register 过程中 | PENDING→RUNNING→终态 |
| **TC012** | report_path 记录 | register | `report_path` 与源文件一致 |
| **TC013** | duplicate register idempotent | 同一 report 两次 | 单 run_uid；summary 一致 |
| **TC014** | dry-run writes no DB | `--dry-run` | **零** run/result/artifact/parse_status/kb_document 行 |
| **TC015** | run_uid format | register | `run_uid` 匹配 `parse_run_{UTC}_{8hex}` |

---

## P4 裁决专项（M1–M4 / S4）

| 编号 | 场景 | 输入 | 预期 |
|------|------|------|------|
| **TC016** | artifact unique includes run_uid | 同 content 两次不同 run register | 各 run 下均有 artifact 行；`uk_artifact_scope` 不冲突 |
| **TC017** | dry-run writes no DB | registry `--dry-run` | MySQL COUNT 不变；无 `DRY_RUN_COMPLETED` |
| **TC018** | dry-run report ingest rejected | `report.dry_run=true` | exit non-zero；`INVALID_DRY_RUN_REPORT`；零 DB 行 |
| **TC019** | document_uid equals content_uid | SUCCESS register | `kb_document.document_uid == content_uid` |
| **TC01A** | skipped no artifact | item SKIPPED 且无 manifest | 仅 `kb_parse_result`；**零** `kb_parsed_artifact` |

---

## Parse Result

| 编号 | 场景 | 输入 | 预期 |
|------|------|------|------|
| **TC020** | insert parse result success | SUCCESS + manifest | result.status=SUCCESS |
| **TC021** | insert parse result skipped | SKIPPED | result.status=SKIPPED |
| **TC022** | insert parse result failed | FAILED + manifest | result.status=FAILED；error 字段 |
| **TC023** | insert parse result empty | EMPTY | result.status=EMPTY |
| **TC024** | retry_of_result_id | FAILED 后 SUCCESS | retry 链正确 |
| **TC025** | parse_status update | SUCCESS | parse_status=PARSED |
| **TC026** | kb_document bridge | SUCCESS/EMPTY | document_uid=content_uid |

---

## Parsed Artifact

| 编号 | 场景 | 输入 | 预期 |
|------|------|------|------|
| **TC030** | insert parsed artifact parsed_text | SUCCESS | PARSED_TEXT；uk_artifact_scope 含 run_uid |
| **TC031** | insert parsed artifact parsed_metadata | SUCCESS | PARSED_METADATA |
| **TC032** | insert parsed artifact parse_manifest | FAILED | PARSE_MANIFEST |
| **TC033** | insert parsed artifact parse_report | register | PARSE_REPORT；content_uid='' |
| **TC034** | missing artifact file | text 缺失 | artifact status=MISSING；result 仍登记 |

---

## Reconcile

| 编号 | 场景 | 输入 | 预期 |
|------|------|------|------|
| **TC040** | reconcile existing parsed | `--sha256 HEX` | result+artifact；无 re-parse |
| **TC041** | reconcile no filter | 无 filter | exit non-zero |
| **TC042** | reconcile limit cap | `--limit 101` | exit non-zero |
| **TC043** | reconcile no re-parse | reconcile 前后 | parsed hash 不变 |

---

## 保护 — 磁盘 / 越界

| 编号 | 场景 | 输入 | 预期 |
|------|------|------|------|
| **TC050** | no raw_vault mutation | register + reconcile | raw_vault 不变 |
| **TC051** | no parsed mutation | register + reconcile | parsed hash 不变 |
| **TC052** | no MinerU/OCR | grep | 无 mineru/ocr |
| **TC053** | no curated/vector | register | 无 chunk/embedding 写 |

---

## CLI 查询

| 编号 | 场景 | 输入 | 预期 |
|------|------|------|------|
| **TC060** | list-parse-jobs | 有 run | 列表正确 |
| **TC061** | show-parse-job | `--run-uid` | 详情含 summary |
| **TC062** | list-parse-results | `--content-uid` | 过滤正确 |
| **TC063** | list-parsed-artifacts | `--artifact-type` | 过滤正确 |

---

## 错误与批处理

| 编号 | 场景 | 输入 | 预期 |
|------|------|------|------|
| **TC070** | invalid report JSON | 损坏 report | exit non-zero |
| **TC071** | invalid manifest | 损坏 manifest | 该 content FAILED；continue |
| **TC072** | unknown content | DB 无 content | errors[]；skip |
| **TC073** | single failure continue | 混合 valid/invalid | 有效 content 仍登记 |

---

## 集成 E2E

| 编号 | 场景 | 输入 | 预期 |
|------|------|------|------|
| **TC080** | CLI E2E | scan→copy→parse→register | DB 有 run/result/artifact |
| **TC081** | 005 regression | 全量 pytest | 全部 pass |
| **TC082** | 中文路径 | fixtures + register | 无编码错误 |
| **TC083** | transaction consistency | DB 中途失败 | 当前 content rollback |

---

## pytest 映射（建议）

| Test Case | 建议 test function |
|-----------|-------------------|
| TC014–TC019, TC01A | `test_registry_dry_run_no_db`、`test_dry_run_report_rejected`、`test_document_uid_equals_content_uid`、`test_skipped_no_artifact`、`test_artifact_unique_includes_run_uid` |
| TC015 | `test_run_uid_format` |
| 其余 | 同 P1 Plan 映射 |

---

**Test Cases 结束** — 共 **39** 条（含 P4 专项 TC016–TC019、TC01A）。

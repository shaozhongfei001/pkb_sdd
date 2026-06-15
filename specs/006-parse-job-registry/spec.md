# Spec: Parse Job Registry（006-parse-job-registry）

> **项目**：个人历史项目文档知识库 `pkb_sdd`  
> **版本基线**：V1.1-SDD  
> **前置条件**：001–005 已完成并 merge `main`（含 `005-markitdown-parser`）  
> **详细实现计划**：见同目录 `plan.md`  
> **定位**：解析任务 / 解析结果 / parsed 产物 **MySQL registry 层** — 非 parser 执行器

---

## 1. 背景

Phase 1 文件治理底座进度：

```text
001 盘点 → 002 raw_vault → 003 重复治理 → 004 解析路由 → 005 MarkItDown 解析执行
  → 【006 Parse Job Registry】→ 008 MinerU …
```

001–004 已完成文件/instance/content 登记、vault 复制、重复治理与解析路由决策。

005 是 Phase 1 **首个**允许调用 MarkItDown、读取 `raw_vault/original.bin`、写入 `parsed/` 的 Spec。005 产出：

- 磁盘：`parsed/by_hash/{2}/{4}/{sha256}/` 下 `parsed_text.md`、`parsed_metadata.json`、`parse_manifest.json`
- 报告：`reports_root/parse_markitdown_report_{UTC}.json`
- MySQL：**零写入**（`kb_parse_job`、`kb_document`、`parse_status` 仍为空置）

006 在 **不重新解析、不修改 005 执行逻辑** 的前提下，建立 parse run / parse result / parsed artifact 的 **DB registry**，使解析状态可 SQL 查询、可审计、可支撑重试关系与后续 quality / MinerU Spec。

---

## 2. 用户故事

| 角色 | 故事 | 验收要点 |
|------|------|----------|
| **文档管理员** | 005 跑完 `parse-markitdown` 后，希望 DB 能查到本次批处理的 job 与每条 content 结果 | `register-parse-report` 写入 run + results |
| **文档管理员** | 希望 parsed 三文件在 DB 中有路径与 hash 索引 | `kb_parsed_artifact`（按 run 范围；SKIPPED 无 manifest 时无 artifact 行） |
| **运维** | 希望 list/show CLI 查询 job、result、artifact，不必扫全盘 | `list-parse-jobs` 等命令 |
| **运维** | 希望 dry-run 可预览 registry 将写入什么 | `--dry-run` **零 DB 写**；仅 preview report |
| **运维** | 005 dry-run report 不得误入 registry | `INVALID_DRY_RUN_REPORT` + exit non-zero |
| **DB 审查员** | registry 不得破坏 raw_vault / parsed 磁盘产物 | 只读 ingest；无 overwrite |
| **开发** | 006 不得倒灌修改 005 `markitdown_parser.py` | 独立 registry service + register CLI |

---

## 3. 目标

1. 通过 **additive migration** 新增 registry 表（见 `plan.md` §9）：`kb_parse_run`、`kb_parse_result`、`kb_parsed_artifact`。
2. 提供 **`register-parse-report`**：读取 005 `parse_markitdown_report_*.json` + 磁盘 manifest，登记一次 parse run 及 per-content results / artifacts。
3. 提供 **查询 CLI**：`list-parse-jobs`、`show-parse-job`、`list-parse-results`、`list-parsed-artifacts`。
4. 提供 **`reconcile-parsed-artifacts`**（**显式 opt-in**）：从已有 `parsed/` 扫描 manifest 补齐 registry，**不**重新解析。
5. 更新 **`kb_file_content.parse_status`** 与 **`kb_document`**（SUCCESS 时 bridge upsert，对齐 init SQL 下游消费）。
6. 记录 **失败原因**（`error_code` / `error_message`）与 **重试关系**（`retry_of_result_id`）。
7. 支持 **`--dry-run`** registry preview（**零 DB 写入**）。
8. **拒绝** 005 `dry_run=true` 的 parse report ingest（`INVALID_DRY_RUN_REPORT`）。
9. 保持幂等；单 content 登记失败不中断批处理；**不写 curated / 向量 / 项目卡**。

**006 核心能力**：将 005 磁盘解析产物与报告 **索引到 MySQL**，形成可查询的 parse lifecycle registry。

---

## 4. 范围（006 MVP 包含）

| 项 | 说明 |
|----|------|
| SQL migration | 新增 `kb_parse_run`、`kb_parse_result`、`kb_parsed_artifact`（additive，非破坏性） |
| ORM models | `KbParseRun`、`KbParseResult`、`KbParsedArtifact` |
| `ParseRegistryService` | report ingest、reconcile、查询、幂等 upsert |
| CLI | `register-parse-report`、`list-parse-jobs`、`show-parse-job`、`list-parse-results`、`list-parsed-artifacts`、`reconcile-parsed-artifacts` |
| `kb_file_content.parse_status` | UPDATE（来自最新 result 聚合规则，见 plan） |
| `kb_document` | SUCCESS/EMPTY 时 upsert（bridge）；**`document_uid = content_uid`** |
| pytest + CLI E2E | 见 `test_cases.md` |

**006 MVP 不包含、不得执行**：

- 调用 MarkItDown / MinerU / OCR；读取 `original.bin` 做解析
- 修改 `markitdown_parser.py` 或 005 行为
- 默认全库 reconcile / 默认历史回填（须显式 CLI + 护栏）
- 写入 `curated/`、向量库、embedding、项目卡、Streamlit
- 修改 001–005 已有表结构（init SQL 语义不变；仅 additive 新表 + 写已有可写列）
- 删除 / 移动 / 覆盖 raw_vault 或 parsed（registry 默认只读磁盘）

---

## 5. 非目标（006 明确不做）

| 非目标 | 说明 | 归属 |
|--------|------|------|
| MinerU / OCR / PDF / IMAGE 解析 | 不 import、不 subprocess | **008-mineru-parser**（原 stub 重编号） |
| 新 parser 类型 | 仅 ingest 005 `parser_name=markitdown` | 后续 parser Spec |
| 修改 005 parse-markitdown | 005 service 封闭 | 006 用 `register-parse-report` 衔接 |
| 默认历史 parsed 全库 reconcile | 须 `--limit` / `--sha256` 等显式参数 | — |
| 自动全库解析 | 无 | — |
| quality_score / 低质量重解析 | 只读登记 status | 007-quality-checker |
| chunk / embedding / 检索 | 不写 `kb_document_chunk` 等 | 009 / 011 |
| 写入 init SQL `kb_parse_job` | 语义为 per-content worker queue，与 006 batch run 不同 | 后续 queue Spec |
| LLM 总结 | 无 | — |
| FastAPI | 无 | 后续 Spec |
| 破坏性 migration | 禁止 DROP/ALTER 001–005 依赖列 | — |

---

## 6. 数据流

```text
001 scan → 002 copy-to-vault → [003] → [004 route-parsers]
  → 005 parse-markitdown
    → parsed/ 三文件 + parse_markitdown_report_{UTC}.json
  → 006 register-parse-report --report-path ...（report.dry_run 必须为 false）
    → read report JSON + parse_manifest.json（只读 parsed/）
    → upsert kb_parse_run + kb_parse_result + kb_parsed_artifact
    → update kb_file_content.parse_status
    → upsert kb_document（SUCCESS/EMPTY bridge）
    → registry_report_{UTC}.json（可选）

可选（显式 opt-in）：
  006 reconcile-parsed-artifacts --sha256 ... | --limit N
    → scan parsed/ manifest → 补齐 registry（无 report 时 synthesize run）
    → 不调用 MarkItDown
```

**006 磁盘**：仅 **只读** `parsed/`、`reports_root/`；**不写入** raw_vault / parsed（除非未来 TL 授权的显式 repair 子命令，MVP 不做）。  
**006 MySQL 写入**：`kb_parse_run`、`kb_parse_result`、`kb_parsed_artifact`、`kb_file_content.parse_status`、`kb_document`。

---

## 7. 与 init SQL 已有表的关系

| 表 | init SQL | 006 MVP |
|----|----------|---------|
| `kb_parse_job` | per-content worker job | **不读写**（语义保留给未来 queue） |
| `kb_document` | parsed document registry | **upsert**（bridge，来自 result SUCCESS/EMPTY） |
| `kb_file_content.parse_status` | 内容级解析状态 | **UPDATE** |
| `kb_parse_run` | — | **新增**（batch run /「parse job」业务实体） |
| `kb_parse_result` | — | **新增**（per-content 结果） |
| `kb_parsed_artifact` | — | **新增**（三文件 + report 索引） |

**命名说明**：CLI 与文档中的 **「parse job」** 对应 DB 表 **`kb_parse_run`**，以避免与 init SQL 中 per-content 的 `kb_parse_job` 混淆（见 `plan.md` §5、§9）。

---

## 8. 业务规则

1. **原始文件只读**：006 不 open 用户原始路径 write。
2. **raw_vault 只读**：006 不 create/delete/overwrite raw_vault。
3. **parsed 默认只读**：registry ingest 只读 manifest 与 artifact hash；**不**覆盖 `parsed_text.md` 等。
4. **不重新解析**：除非用户显式运行 005 `parse-markitdown`（不属于 006 默认路径）。
5. **幂等**：同一 `report_path` 或同一 `(run_uid, content_uid, parser_adapter_version)` 重复 register 不产生 duplicate 主记录。
6. **单条失败 continue**：单 content manifest 损坏 → `errors[]`；继续批处理。
7. **dry-run**：006 registry `--dry-run` **零 MySQL 写入**；仅 preview / registry report。
8. **005 dry-run report**：`register-parse-report` 遇到 `report.dry_run=true` **必须拒绝**（`INVALID_DRY_RUN_REPORT`）。
9. **reconcile opt-in**：`reconcile-parsed-artifacts` 必须提供 `--sha256` / `--content-uid` / `--limit` 至少其一；**不得**默认全库。
10. **SKIPPED artifact**：无 manifest / parsed 三文件时 **不创建** `kb_parsed_artifact` 行（仅 `kb_parse_result`）。
11. CLI 入口 `ensure_readonly()`。
12. **`document_uid`**：upsert `kb_document` 时 **`document_uid = content_uid`**（禁止 sha256 备选）。
13. 若 Dev 发现必须修改 005 service → **STOP → TL**（不得倒灌）。

---

## 9. 硬约束清单（Dev / QA 必遵）

1. 006 **只做** parse registry / ingest / 查询。
2. 006 **不**调用 MarkItDown / MinerU / OCR。
3. 006 **不**读 `original.bin` 做解析。
4. 006 **不**修改 `markitdown_parser.py`。
5. 006 **不**默认全库 reconcile。
6. 006 **不** delete/move/overwrite raw_vault 或 parsed。
7. 006 **必须**走 additive migration + DB Plan Review。
8. 006 **必须**支持 dry-run（零 DB 写）。
9. 006 **必须**拒绝 005 dry-run report。
10. 006 **必须**记录 failure + retry 关系字段。
11. 006 **artifact UNIQUE** 含 `run_uid`（`uk_artifact_scope`）。
12. 006 **不写** curated / 向量 / 项目卡。

---

## 10. 与 005 / 008 / 007 的边界

| 阶段 | 职责 |
|------|------|
| **005** | MarkItDown 解析执行；写 parsed 磁盘 + parse report；**零 DB 写** |
| **006（本 Spec）** | 读 report + manifest；写 registry 三表 + parse_status + kb_document bridge |
| **007-quality-checker** | 读 parsed + kb_document；quality_score |
| **008-mineru-parser** | MinerU 解析；完成后同样可被 006 register/reconcile ingest |

---

**Spec 结束** — 实现细节见 `plan.md`；任务见 `tasks.md`；验收见 `acceptance.md`。

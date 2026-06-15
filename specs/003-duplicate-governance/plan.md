# Plan: 重复文件治理（003 实现计划）

> **项目**：个人历史项目文档知识库 `pkb_sdd`
> **项目路径**：`/home/szf/dev/pyws/pkb_sdd`
> **版本基线**：V1.1-SDD
> **编写日期**：2026-06-15
> **前置条件**：001-file-inventory、002-file-content-vault 已完成；Agent 协作规范已落地；003 前置确认已完成
> **编写角色**：Tech Lead Agent — 步骤 ① Plan

---

## 1. 背景与当前阶段

Phase 1 文件治理底座进度：

```text
001 盘点 → 002 raw_vault → 【003 精确重复治理】→ 004+ 解析 / 价值 / 前端
```

001 已将路径登记为 `kb_file_instance`、内容登记为 `kb_file_content`，并在扫描时标记 `is_duplicate_instance`、`instance_count`、`master_file_instance_uid`（按扫描顺序，**不写** `duplicate_group_uid`）。

002 已将唯一内容只读复制到 `raw_vault/by_hash/...`，更新 `vault_status` 与 `kb_raw_vault_object`。

003 在 **原始文件只读、raw_vault 只读引用** 前提下，对 **sha256 完全一致** 的多路径重复进行元数据治理：写入 `kb_duplicate_group`、关联 `kb_file_instance.duplicate_group_uid`、输出 duplicate / cleanup suggestion 报告。**不执行任何文件系统清理操作。**

---

## 2. 003 目标

1. 识别 **sha256 完全一致** 的重复文件内容组（`instance_count >= 2`）。
2. 基于已存在的 **`kb_duplicate_group`** 表 upsert 重复组记录。
3. 为每个重复组按规则选择 **master candidate**，写入 `kb_duplicate_group.master_file_instance_uid`。
4. 更新同组全部 `kb_file_instance.duplicate_group_uid`。
5. 输出 **`duplicate_report_{UTC}.json`**。
6. 输出 **`cleanup_suggestion_report_{UTC}.json`**（仅建议，`auto_execute=false`）。
7. 提供 Typer CLI 命令 **`govern-duplicates`**。
8. 保持幂等；单组失败不中断批处理；补充 pytest 与 CLI E2E。

---

## 3. 003 非目标

| 非目标 | 说明 |
|--------|------|
| 语义 / 文本 / 路径 / 文件名相似去重 | 非 sha256 精确重复 |
| LLM 判断版本或选 master | 无 LLM |
| `kb_version_candidate_group` | 后续 Spec |
| 执行删除 / 移动 / 重命名 / quarantine | 只出建议报告 |
| 修改 / 删除 raw_vault | 002 副本只读引用 |
| 修改 `inventory_scanner.py` / `file_content_vault.py` | 001/002 已封闭 |
| MinerU / MarkItDown / Parser Router | 004+ |
| `parsed/` / `curated/` 写入 | 004 / 010+ |
| Streamlit / 向量库 / 项目卡蒸馏 | 011 / 012 / 010+ |
| 源代码知识库分析 | 全局禁止 |
| SQL schema 变更 | 003 MVP 无 migration |
| 新增第三方依赖 | 复用现有 stack |

---

## 4. 输入数据

### 4.1 MySQL（主输入）

| 表 | 用途 | 003 操作 |
|----|------|----------|
| **`kb_file_content`** | 候选重复内容 | **只读**；筛选 `instance_count >= 2` 且 `sha256 IS NOT NULL` |
| **`kb_file_instance`** | 组内路径实例 | **读** + **写** `duplicate_group_uid` |
| **`kb_duplicate_group`** | 重复组主记录 | **upsert** |
| **`kb_raw_vault_object`** | vault 元数据 | **只读**（报告引用 `vault_path`） |

**默认选取条件**：

```text
kb_file_content.instance_count >= 2
AND kb_file_content.sha256 IS NOT NULL
AND kb_file_content.status = 'CONTENT_REGISTERED'   -- 可选过滤，与 002 对齐
```

可选 CLI 过滤：`--sha256`、`--content-uid`、`--limit`。

### 4.2 配置输入

| 配置项 | 来源 |
|--------|------|
| `storage.reports_root` | `config/app.yaml` |
| `storage.raw_vault_root` | 报告引用 vault 路径（只读） |
| `raw.original_files_readonly` | 必须为 `true`（复用 `ensure_readonly()`） |
| `app.pipeline_version` | 写入报告 metadata（可选） |

### 4.3 001 / 002 已提供、003 直接复用

- `AppConfig` / `load_config` / `ensure_readonly`
- `create_db_engine` / `create_session_factory` / `session_scope`
- `KbFileInstance` / `KbFileContent` ORM（`models/file.py`）
- `KbRawVaultObject` ORM（`models/vault.py`）
- CLI Typer 模式（`cli/main.py`）
- 测试：`tests/fixtures/中文路径/银行项目/方案.txt` + `方案副本.txt`（同 sha256）

---

## 5. 输出数据

### 5.1 数据库

| 表 | 写入 |
|----|------|
| `kb_duplicate_group` | upsert：`duplicate_group_uid`、`sha256`、`content_uid`、`instance_count`、`master_file_instance_uid`、`decision=PENDING` |
| `kb_file_instance` | 更新 `duplicate_group_uid`（同 sha256 下全部 instance） |

### 5.2 磁盘报告（`reports_root`）

```text
{reports_root}/duplicate_report_{UTC}.json
{reports_root}/cleanup_suggestion_report_{UTC}.json
```

### 5.3 CLI 汇总（Rich echo）

```text
Candidates: N          # instance_count >= 2 的 content 数
Groups processed: N
Groups upserted: N
Instances linked: N
Suggestions generated: N
Skipped (unchanged): N
Errors: N
```

---

## 6. 关键数据对象

### 6.1 `duplicate_group_uid`

- **值**：`= sha256`（64 位 hex，与 `content_uid` 一致）
- **唯一键**：`kb_duplicate_group.duplicate_group_uid` UNIQUE

### 6.2 治理结果 dataclass（建议）

```text
DuplicateGovernResult
  candidates: int
  groups_processed: int
  groups_upserted: int
  instances_linked: int
  suggestions_generated: int
  skipped: int
  errors: list[GovernError]   # sha256 + message
  duplicate_report_path: Path | None
  cleanup_suggestion_report_path: Path | None
```

### 6.3 ORM 新增

`KbDuplicateGroup` → `kb_duplicate_group`，字段与 SQL 一一对应，**不发明字段**。

---

## 7. 精确重复定义

**只有 sha256 完全一致才视为精确重复。**

- 不做文件名相似。
- 不做路径相似。
- 不做文本相似。
- 不做语义相似。
- 不做 LLM 判断版本。

**判定规则**：

```text
同一 kb_file_content.sha256 下，kb_file_instance 数量 >= 2（由 001 维护的 instance_count）
→ 构成一个精确重复组
```

单 instance（`instance_count = 1`）**不**生成 duplicate group。

---

## 8. duplicate group 生成策略

对每个候选 `kb_file_content`（`instance_count >= 2`）：

1. 加载该 `sha256` 下全部 `kb_file_instance`（`status IN ('DISCOVERED', ...)` 可配置；默认含 `DISCOVERED`）。
2. 若实际 instance 数 < 2 → 记 warning/error，跳过（数据不一致防护）。
3. 设置 `duplicate_group_uid = sha256`。
4. **upsert** `kb_duplicate_group`：
   - `duplicate_group_uid = sha256`
   - `sha256`、`content_uid = sha256`
   - `instance_count = len(instances)`
   - `master_file_instance_uid` = §9 规则选出
   - `decision = 'PENDING'`
   - `decision_reason = NULL`（MVP 不写）
5. **UPDATE** 组内每个 instance：`duplicate_group_uid = sha256`。
6. 若组已存在且字段一致 → 计 `skipped`；否则 `upserted`。

**不写入** `kb_version_candidate_group`。

---

## 9. master candidate 选择规则

003 为每个 duplicate group **独立计算** master candidate，写入 `kb_duplicate_group.master_file_instance_uid`。

**不得通过 LLM 判断哪个版本更好。**

在组内全部 instance 上，按以下 **优先级依次比较**（数值越小越优先）：

| 优先级 | 规则 | 比较方式 |
|--------|------|----------|
| 1 | 优先选择 **非 duplicate instance** | `is_duplicate_instance = 0` 优于 `1` |
| 2 | 优先选择 **路径较短** 的 instance | `len(source_path)` 升序 |
| 3 | 优先选择文件名 **不含** 副本标记的 instance | 文件名（小写）不含：`副本`、`copy`、`bak`、`tmp`、`临时`、`- copy`、`_copy` |
| 4 | 优先选择 **修改时间较早或较稳定** 的 instance | `modified_time` 升序；NULL 排后 |
| 5 | **稳定排序** 保证幂等 | `created_at` 升序 → `file_instance_uid` 升序 |

**说明**：

- 规则 1 与 001 扫描顺序通常一致，但 003 **以本规则重算** 并写入 duplicate group，**不修改** `kb_file_content.master_file_instance_uid`（002 vault 源不变）。
- 文件名规则对 fixtures `方案.txt` vs `方案副本.txt`：`方案.txt` 应胜出。
- 全部 tie-break 必须确定性；同输入多次运行结果相同。

---

## 10. cleanup suggestion 规则

对每个 duplicate group 中 **非 master candidate** 的 instance 生成一条 cleanup suggestion：

| 字段 | 值 / 说明 |
|------|-----------|
| `duplicate_group_uid` | `sha256` |
| `sha256` | 内容 hash |
| `content_uid` | `= sha256` |
| `master_file_instance_uid` | §9 选出 |
| `master_source_path` | master 的 `source_path` |
| `duplicate_file_instance_uid` | 建议审查的 instance |
| `duplicate_source_path` | 重复路径 |
| `duplicate_file_name` | 重复文件名 |
| `suggested_action` | **`REVIEW_DUPLICATE`**（MVP 固定） |
| `auto_execute` | **`false`**（MVP 固定） |
| `decision` | **`PENDING`** |
| `reason` | 人类可读说明，如「与 master 内容 sha256 相同，建议人工确认是否保留此路径实例」 |
| `vault_path` | 来自 `kb_file_content.vault_path` 或 `kb_raw_vault_object`（只读引用，可为 null） |

**硬性约束**：

1. **只生成建议**。
2. **不执行删除**。
3. **不执行移动**。
4. **不执行重命名**。
5. **不移动到 quarantine**。
6. **不删除 raw_vault**。
7. 每条建议必须可追溯到 **duplicate group**、**master candidate**、**duplicate instance**（含 uid + path）。

---

## 11. 报告输出设计

### 11.1 `duplicate_report_{UTC}.json`

```json
{
  "report_type": "duplicate_report",
  "pipeline_version": "v1.1",
  "generated_at": "2026-06-15T12:00:00Z",
  "summary": {
    "candidates": 1,
    "groups_processed": 1,
    "groups_upserted": 1,
    "instances_linked": 2,
    "errors": 0
  },
  "groups": [
    {
      "duplicate_group_uid": "<sha256>",
      "sha256": "<sha256>",
      "content_uid": "<sha256>",
      "instance_count": 2,
      "master_file_instance_uid": "<uid>",
      "master_source_path": ".../方案.txt",
      "decision": "PENDING",
      "vault_path": ".../raw_vault/by_hash/...",
      "instances": [
        {
          "file_instance_uid": "...",
          "source_path": "...",
          "file_name": "方案.txt",
          "is_duplicate_instance": 0,
          "duplicate_group_uid": "<sha256>"
        }
      ]
    }
  ],
  "errors": []
}
```

### 11.2 `cleanup_suggestion_report_{UTC}.json`

```json
{
  "report_type": "cleanup_suggestion_report",
  "pipeline_version": "v1.1",
  "generated_at": "2026-06-15T12:00:00Z",
  "auto_execute": false,
  "summary": {
    "suggestions_generated": 1,
    "groups_with_suggestions": 1
  },
  "suggestions": [
    {
      "duplicate_group_uid": "<sha256>",
      "sha256": "<sha256>",
      "master_file_instance_uid": "...",
      "master_source_path": ".../方案.txt",
      "duplicate_file_instance_uid": "...",
      "duplicate_source_path": ".../方案副本.txt",
      "duplicate_file_name": "方案副本.txt",
      "suggested_action": "REVIEW_DUPLICATE",
      "auto_execute": false,
      "decision": "PENDING",
      "reason": "...",
      "vault_path": "..."
    }
  ]
}
```

**规则**：

- 文件名 UTC 格式与 001 `inventory_scan_*` 对齐（如 `%Y%m%dT%H%M%SZ`）。
- 报告仅写入 `reports_root`；不写入 `parsed/` / `curated/` / `quarantine/`。

---

## 12. CLI 设计

### 12.1 命令

```bash
python -m app.cli.main govern-duplicates [OPTIONS]
```

### 12.2 选项

| 选项 | 说明 |
|------|------|
| `--config PATH` | 默认 `config/app.yaml` |
| `--sha256 HEX` | 仅处理指定内容 |
| `--content-uid UID` | 同 `--sha256`（001 中 `content_uid = sha256`） |
| `--limit N` | 最多处理 N 个候选 content |
| `--dry-run` | 可选：只输出报告不写 DB（若实现成本高，MVP 可省略，Plan 允许 Dev 评估） |

### 12.3 执行流程

1. `load_config` → `ensure_readonly()`
2. 调用 `DuplicateGovernanceService.govern_duplicates(...)`
3. Rich 打印 §5.3 汇总
4. 打印报告路径

### 12.4 保留命令

- `scan`、`copy-to-vault` 不变
- `build-parse-queue`、`parse` 保持 placeholder

---

## 13. 服务层设计

### 13.1 新增 `DuplicateGovernanceService`

文件：`backend/app/services/duplicate_governance.py`

**核心方法**：

```text
govern_duplicates(
  *,
  limit: int | None = None,
  sha256: str | None = None,
  content_uid: str | None = None,
) -> DuplicateGovernResult
```

**内部步骤**（每个 content 一组事务或 savepoint）：

1. 查询候选 `kb_file_content`
2. 加载 instances + 可选 `kb_raw_vault_object`
3. `select_master_candidate(instances) -> KbFileInstance`（§9）
4. upsert `kb_duplicate_group`
5. link `duplicate_group_uid` on instances
6. 构建 group 条目 + cleanup suggestions
7. 单组异常 → `errors.append`；**continue**
8. 全部完成后写两份 JSON 报告

### 13.2 辅助函数（同文件或 `core/` 内联）

```text
DUPLICATE_NAME_MARKERS = ("副本", "copy", "bak", "tmp", "临时", "- copy", "_copy")

def is_copy_like_filename(file_name: str) -> bool: ...
def select_master_candidate(instances: list[KbFileInstance]) -> KbFileInstance: ...
def build_cleanup_suggestions(group, master, instances) -> list[dict]: ...
```

### 13.3 日志

- INFO：每组 processed / upserted / skipped
- WARNING：instance_count 与 DB 不一致
- ERROR：单组失败（含 sha256、exception message）

---

## 14. 数据库与 schema 策略

**003 MVP 不修改 SQL schema。**

**复用已存在的 `kb_duplicate_group` 表 / 列及 `kb_file_instance.duplicate_group_uid` 列。**

如果实现阶段发现现有 schema 无法满足 Plan，必须 **STOP**，返回 Tech Lead 重新评审，**不得由 Dev Agent 自行修改 schema**。

### 14.1 `kb_duplicate_group` 字段用法

| 字段 | 003 用法 |
|------|----------|
| `duplicate_group_uid` | **写**；`= sha256` |
| `sha256` | **写** |
| `content_uid` | **写**；`= sha256` |
| `instance_count` | **写** |
| `master_file_instance_uid` | **写**；§9 规则 |
| `decision` | **写**；默认 `PENDING` |
| `decision_reason` | MVP 不写（NULL） |

### 14.2 `kb_file_instance` 字段用法

| 字段 | 003 用法 |
|------|----------|
| `duplicate_group_uid` | **写**；`= sha256` |
| 其余 | 只读 |

### 14.3 `kb_file_content` / `kb_raw_vault_object`

只读；**不写** `master_file_instance_uid`、`vault_*`。

---

## 15. 幂等性设计

| 场景 | 行为 |
|------|------|
| 重复执行 `govern-duplicates` | `kb_duplicate_group` upsert 同键更新；`duplicate_group_uid` 已是目标值则 skip 计数 |
| 同一 sha256 第三次 scan 新增 instance | 重跑 003 → 更新 `instance_count`、重新 link、报告反映新 instance |
| master 规则稳定 | 同 instance 集合 → 同一 master uid |
| 报告文件 | 每次运行 **新 timestamp 文件**（与 001 scan report 一致）；不覆盖旧报告 |
| DB 主记录 | 每组最多 1 行 `kb_duplicate_group`（UNIQUE `duplicate_group_uid`） |

---

## 16. 异常处理设计

| 场景 | 处理 |
|------|------|
| 候选 content 无 instance | 记 error，continue |
| `instance_count` 与实查 instance 数不一致 | WARNING + 以实查为准或 skip（Dev 实现时取实查并 log） |
| 单组 DB 异常 | rollback 该组；记 error；continue |
| 全局 DB 连接失败 | 任务失败，exit non-zero |
| 报告目录不可写 | 记 error；DB 已提交部分不自动回滚（与 001 对齐） |
| `--sha256` 不存在或非重复 | 空结果 + 友好汇总 |

**不 swallow exception**：必须 log + 写入 `errors[]`。

---

## 17. 原始文件保护设计

- 003 **不 open 原始文件进行 write**；不调用 `shutil.move` / `unlink` / `rename`。
- 仅通过 MySQL 读 `source_path` 写入 JSON 报告。
- CLI 入口调用 `ensure_readonly()`。
- pytest 必须含 **原始文件 stat/hash 不变** 断言（复用 001/002 测试模式）。

---

## 18. raw_vault 保护设计

- 003 **只读** `kb_file_content.vault_path`、`kb_raw_vault_object`；报告引用路径。
- **不** create / delete / overwrite `raw_vault/**` 下任何文件。
- cleanup suggestion **不得**包含删除 vault 的动作或 `auto_execute=true`。
- QA 验证：`original.bin` hash 与路径在 govern 前后不变。

---

## 19. 测试策略

### 19.1 单元 / 集成 pytest

文件：`backend/tests/test_duplicate_governance.py`

| 用例 | 验证 |
|------|------|
| `test_govern_normal_duplicate_group` | fixtures 2 instance → 1 group，master=`方案.txt` |
| `test_govern_idempotent` | 连续两次 govern，group 行数不变，duplicate_group_uid 稳定 |
| `test_govern_chinese_path` | 中文路径正常 |
| `test_govern_master_selection_copy_like_name` | `方案副本.txt` 不为 master |
| `test_govern_single_content_no_group` | instance_count=1 不建 group |
| `test_govern_single_group_error_continues` | mock 单组失败不中断（若可测） |
| `test_original_files_unchanged` | stat + hash |
| `test_raw_vault_unchanged` | vault bin 不变 |
| `test_govern_project_fixtures_integration` | scan → copy-to-vault → govern-duplicates |

目标：**约 7–9 个** test functions。

### 19.2 CLI E2E

```bash
python -m app.cli.main scan --path tests/fixtures
python -m app.cli.main copy-to-vault
python -m app.cli.main govern-duplicates
```

期望：Groups processed >= 1；Suggestions >= 1；Errors = 0；报告文件存在。

### 19.3 全链路回归

```bash
pytest -q tests/test_inventory_scanner.py tests/test_file_content_vault.py tests/test_duplicate_governance.py
```

---

## 20. Acceptance Criteria

对照 `acceptance.md`：

| 编号 | 标准 | 003 验证要点 |
|------|------|--------------|
| **A001** 范围符合 | 仅 duplicate group + 报告 + CLI | 无 parsed/解析/前端/向量库 |
| **A002** 原始文件保护 | 不 move/delete/rename/overwrite | stat/hash 测试 + QA 必查 |
| **A003** 幂等性 | 重复执行无重复主记录 | 两次 govern-duplicates |
| **A004** 异常可恢复 | 单组失败不中断 | errors 有记录，其他组成功 |
| **A005** 数据一致性 | DB ↔ 报告 ↔ group uid 一致 | MySQL 查询 + JSON 对照 |
| **A006** 测试通过 | pytest + CLI E2E | 全链路 14+ passed |

**003 专项**：

- cleanup report `auto_execute=false`
- 无文件系统清理副作用
- master 选择符合 §9

---

## 21. 明确禁止事项

1. 不处理源代码知识库。
2. 不移动、不删除、不重命名原始文件。
3. 不自动删除重复文件。
4. 不删除 raw_vault 文件。
5. 不接 MinerU / MarkItDown / Parser Router。
6. 不做 parsed / curated / Streamlit / 向量库 / 项目卡蒸馏。
7. 不修改 SQL schema。
8. 不新增第三方依赖。
9. 不改 `inventory_scanner.py`、`file_content_vault.py`。
10. 不做语义 / 文本 / 路径相似去重。
11. 不用 LLM 选 master 或判断版本。
12. 不写 quarantine 执行逻辑。
13. Dev 不得自行改 schema — 发现缺口 STOP → TL。

---

## 22. 下一步 Dev Agent 实现边界

### 22.1 允许修改（白名单）

| 操作 | 文件 |
|------|------|
| **新增** | `backend/app/services/duplicate_governance.py` |
| **新增** | `backend/app/models/duplicate.py`（或扩 `models/file.py` 增加 `KbDuplicateGroup`） |
| **修改** | `backend/app/cli/main.py`（新增 `govern-duplicates`） |
| **新增** | `backend/tests/test_duplicate_governance.py` |
| **修改** | `specs/003-duplicate-governance/tasks.md`（勾选完成项） |

### 22.2 禁止修改

```text
backend/app/services/inventory_scanner.py
backend/app/services/file_content_vault.py
backend/app/models/vault.py          # 除非只读 import，无必要不改
sql/**
config/**
docs/**
.cursor/**
raw_vault/**（真实产物）
specs/003-duplicate-governance/plan.md   # Dev 不改 Plan
specs/其他编号/**
```

### 22.3 Dev 完成后 STOP 点

```text
Dev 实现 + pytest 自报 → STOP → DB Agent 审查 → E2E QA → Handoff → TL Final Review
```

Dev **不得**自我宣布 A001–A006 通过。

---

**Plan 结束** — 请 Dev Agent 先读 `tasks.md` 与白名单后再写代码。

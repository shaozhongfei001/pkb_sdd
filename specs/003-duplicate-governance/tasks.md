# Tasks: 重复文件治理（003）

> **Spec**：`specs/003-duplicate-governance`
> **分支**：`feature/003-duplicate-governance`
> **Plan**：`plan.md`（Tech Lead 步骤 ① 已落地）
> **Dev 必读**：本文件 → `plan.md` → `spec.md` → `acceptance.md` → `test_cases.md`

---

## Dev 文件白名单（全局）

**允许修改**：

```text
backend/app/services/duplicate_governance.py          # 新增
backend/app/models/duplicate.py                       # 新增（KbDuplicateGroup；不扩 file.py，见 plan §23 Q1）
backend/app/cli/main.py                               # 新增 govern-duplicates
backend/tests/test_duplicate_governance.py            # 新增
specs/003-duplicate-governance/tasks.md               # 勾选
```

**禁止修改**：

```text
backend/app/services/inventory_scanner.py
backend/app/services/file_content_vault.py
sql/**
config/**
docs/**
.cursor/**
raw_vault/**（真实产物）
specs/003-duplicate-governance/plan.md
specs/其他编号/**
```

---

## 全局硬约束（T001–T014 均适用）

1. 不处理源代码知识库。
2. 不移动、不删除、不重命名原始文件。
3. 不自动删除重复文件。
4. 不删除 raw_vault 文件。
5. 不接 MinerU / MarkItDown / Parser Router。
6. 不做 parsed / curated / Streamlit / 向量库 / 项目卡蒸馏。
7. 不修改 SQL schema。
8. 不新增第三方依赖。
9. 精确重复 **仅** sha256 完全一致（见 `plan.md` §7）；不用 LLM。
10. cleanup suggestion **只生成建议**，不执行删除 / 移动 / 重命名 / quarantine（见 `plan.md` §10）。

11. **TL 实现决策**：实现前必读 `plan.md` **§23**（Q1–Q7：duplicate.py、无 dry-run、DISCOVERED 过滤、skipped 计数、测试 helper 清理、单实例 sha256 不建组）。

---

## T001 阅读 001/002 相关模型、服务、CLI 与测试

### 目标

理解 001/002 已提供的 ORM、批处理模式、CLI 与 pytest fixture，为 003 实现做准备。

### 允许修改范围

- 无（阅读 only）
- 可在本文件勾选 `[x]`（Dev 完成后）

### 禁止事项

- 不改任何 `backend/**` 代码
- 不改 SQL / config / docs

### 验收标准

- [x] 已读 `backend/app/models/file.py`、`vault.py`
- [x] 已读 `inventory_scanner.py`、`file_content_vault.py`（只读，不改）
- [x] 已读 `cli/main.py` 中 `scan`、`copy-to-vault`
- [x] 已读 `test_inventory_scanner.py`、`test_file_content_vault.py`
- [x] 已读 `tests/fixtures/中文路径/银行项目/` 重复样本
- [x] 已读 `plan.md` 全文

---

## T002 确认 003 复用已存在 schema，不做 schema 变更

### 目标

确认 `kb_duplicate_group`、`kb_file_instance.duplicate_group_uid` 已满足 MVP；不创建 migration。

### 允许修改范围

- 无代码；本 task 勾选

### 禁止事项

- **禁止**修改 `sql/001_init_schema_v1_1.sql`
- **禁止**新增 `sql/migrations/**`
- 若 ORM 需求超出 init SQL → **STOP → TL**，不得自行改 schema

### 验收标准

- [x] 已对照 `sql/001_init_schema_v1_1.sql` 中 `kb_duplicate_group` 全部字段
- [x] `KbDuplicateGroup` ORM 计划字段与 SQL 一致，无发明字段
- [x] 书面确认：003 MVP 无 schema 变更

---

## T003 实现 duplicate governance service

### 目标

新增 `DuplicateGovernanceService` 与 `DuplicateGovernResult`，实现批处理入口 `govern_duplicates()`。

### 允许修改范围

- `backend/app/services/duplicate_governance.py`（新增）
- `backend/app/models/duplicate.py`（`KbDuplicateGroup`；**不**扩 `models/file.py`）
- `specs/003-duplicate-governance/tasks.md`（勾选）

### 禁止事项

- 不改 001/002 service
- 不改 SQL schema
- 不引入新依赖
- 不 touch 原始文件 / raw_vault 磁盘
- **不实现** `--dry-run`（plan §23 Q2）

### 验收标准

- [x] Service 可实例化并连接 MySQL
- [x] 返回 `DuplicateGovernanceResult` 汇总结构
- [x] 调用 `ensure_readonly()` 由 CLI 或 service 入口保证
- [x] 单组失败记入 `errors`，不中断批处理

---

## T004 实现 duplicate group 识别逻辑

### 目标

筛选 `instance_count >= 2` 的 content，加载 instances，upsert `kb_duplicate_group`，link `duplicate_group_uid`。

### 允许修改范围

- `backend/app/services/duplicate_governance.py`
- `backend/app/models/duplicate.py`（**不**扩 `file.py`）

### 禁止事项

- 不做非 sha256 重复识别
- 不写 `kb_version_candidate_group`
- 不修改 `kb_file_content` 行（含 **不** 改 `master_file_instance_uid`）
- MVP 仅加载 `status == "DISCOVERED"` 的 instance（plan §23 Q4）

### 验收标准

- [x] `duplicate_group_uid = sha256`
- [x] `instance_count >= 2` 才建组；`= 1` 跳过
- [x] 组内全部 instance 写入相同 `duplicate_group_uid`
- [x] upsert 幂等（重复运行无重复 INSERT）

---

## T005 实现 master candidate 选择逻辑

### 目标

按 `plan.md` §9 优先级实现 `select_master_candidate()`，写入 `kb_duplicate_group.master_file_instance_uid`。

### 允许修改范围

- `backend/app/services/duplicate_governance.py`

### 禁止事项

- 不用 LLM
- **不修改** `kb_file_content.master_file_instance_uid`（002 vault 源保持不变）
- 与 content master 不一致时，仅在报告 / suggestion `reason` 说明（plan §23 Q3）

### 验收标准

- [x] 优先级：非 duplicate → 短路径 → 非 copy-like 文件名 → modified_time → created_at → uid
- [x] fixtures：`方案.txt` 为 master，`方案副本.txt` 为 duplicate suggestion 对象
- [x] 同输入多次运行 master uid 一致
- [x] copy-like 标记含：`副本`、`copy`、`bak`、`tmp`、`临时` 等（见 Plan）

---

## T006 实现 cleanup suggestion 生成逻辑

### 目标

为非 master instance 生成 suggestion 条目，`auto_execute=false`，`suggested_action=REVIEW_DUPLICATE`。

### 允许修改范围

- `backend/app/services/duplicate_governance.py`

### 禁止事项

- 不执行删除 / 移动 / 重命名 / quarantine
- 不删除 raw_vault
- `auto_execute` 不得为 `true`

### 验收标准

- [x] 每条 suggestion 含 group uid、master uid/path、duplicate uid/path
- [x] `decision=PENDING`，`auto_execute=false`
- [x] 可追溯到 vault_path（只读，可为 null）

---

## T007 实现 duplicate report 输出

### 目标

写入 `reports_root/duplicate_report_{UTC}.json` 与 `cleanup_suggestion_report_{UTC}.json`。

### 允许修改范围

- `backend/app/services/duplicate_governance.py`

### 禁止事项

- 不写 parsed / curated / quarantine
- 报告不包含可执行 shell 删除命令作为默认行为

### 验收标准

- [x] 两份 JSON 结构符合 `plan.md` §11
- [x] `cleanup_suggestion_report` 顶层 `auto_execute: false`
- [x] 报告路径写入 `DuplicateGovernanceResult`
- [x] `reports_root` 自动 `mkdir`

---

## T008 实现 CLI 命令

### 目标

在 `cli/main.py` 新增 `govern-duplicates` 命令及 `--config` / `--sha256` / `--content-uid` / `--limit`。

### 允许修改范围

- `backend/app/cli/main.py`

### 禁止事项

- 不删除或破坏现有 `scan`、`copy-to-vault`
- 不实现 parse 链
- **不实现** `--dry-run`（plan §23 Q2）

### 验收标准

- [x] `python -m app.cli.main govern-duplicates` 可运行
- [x] Rich 输出 Plan §5.3 汇总字段
- [x] 可选过滤参数生效
- [x] `--sha256` 指向单实例：skipped/空结果，exit 0（plan §23 Q7）

---

## T009 补充 pytest 单元测试

### 目标

新增 `test_duplicate_governance.py`，覆盖 master 选择、幂等、中文路径、无组场景等。

### 允许修改范围

- `backend/tests/test_duplicate_governance.py`（新增）

### 禁止事项

- 不修改 `backend/app/services/**` 以「凑测试」（测试失败应修实现）
- 测试使用 `tmp_path`；不污染生产 raw_vault

### 验收标准

- [x] ≥ 7 个 test functions（见 Plan §19.1）
- [x] `pytest -q tests/test_duplicate_governance.py` 全部通过
- [x] 含 master 非 copy-like 文件名断言

---

## T010 补充 CLI E2E 测试

### 目标

pytest 或文档化步骤验证 scan → copy-to-vault → govern-duplicates 全链路。

### 允许修改范围

- `backend/tests/test_duplicate_governance.py`（集成用例）

### 禁止事项

- 不要求外部网络
- 不修改用户真实原始目录

### 验收标准

- [x] `test_govern_project_fixtures_integration`（或等价）通过
- [x] CLI E2E 输出 Groups processed ≥ 1、Errors = 0
- [x] 报告文件在 tmp reports_root 中存在

---

## T011 验证原始文件未被修改

### 目标

测试 govern 前后原始 fixture 文件 mtime / 内容 hash 不变。

### 允许修改范围

- `backend/tests/test_duplicate_governance.py`

### 禁止事项

- 不 delete/rename fixture 源文件
- 业务 service 不得 DELETE 数据；**仅** pytest helper / teardown 可清理测试行（plan §23 Q6）

### 验收标准

- [x] `test_original_files_unchanged` 通过
- [x] 与 001/002 测试断言风格一致

---

## T012 验证 raw_vault 未被删除

### 目标

govern 前后 `original.bin` 及 vault 目录 listing 不变。

### 允许修改范围

- `backend/tests/test_duplicate_governance.py`

### 禁止事项

- 测试中 vault 必须在 `tmp_path`

### 验收标准

- [x] `test_raw_vault_unchanged` 通过
- [x] bin sha256 与 govern 前一致

---

## T013 验证重复执行幂等

### 目标

连续两次 `govern-duplicates`（或两次 service 调用）不产生重复 group 行、状态一致。

### 允许修改范围

- `backend/tests/test_duplicate_governance.py`

### 禁止事项

- 不通过 DELETE 数据「伪造」幂等
- group 无字段变化应计 `skipped`（plan §23 Q5）

### 验收标准

- [x] `test_govern_idempotent` 通过
- [x] `kb_duplicate_group` 行数稳定
- [x] `duplicate_group_uid` 与 master uid 两次一致

---

## T014 验收并生成阶段交接记录

### 目标

Dev 完成后 STOP；由 **QA** 执行 A001–A006，**Handoff** 写交接文档；Dev 本 task 仅勾选自测完成项。

### Handoff 文档

```text
docs/handoff-phase1-003-duplicate-governance.md
```

### 允许修改范围

- Dev：`specs/003-duplicate-governance/tasks.md` 勾选 T001–T013
- QA / HO：按角色权限（Dev **不写** handoff）

### 禁止事项

- Dev **不得**自我宣布验收通过
- Dev **不得**写 `docs/handoff-*.md`
- Dev **不得** merge main

### 验收标准

- [x] Dev 已输出：修改文件清单、pytest 命令、CLI 命令、遗留问题
- [x] 全链路：`pytest -q tests/test_inventory_scanner.py tests/test_file_content_vault.py tests/test_duplicate_governance.py` 通过
- [x] STOP → **DB Agent** → **E2E QA** → **Handoff Agent** → **TL Final Review**

---

## 任务进度总览

| Task | 说明 | 状态 |
|------|------|------|
| T001 | 阅读 001/002 | [x] |
| T002 | 确认无 schema 变更 | [x] |
| T003 | governance service | [x] |
| T004 | duplicate group 识别 | [x] |
| T005 | master candidate | [x] |
| T006 | cleanup suggestion | [x] |
| T007 | report 输出 | [x] |
| T008 | CLI | [x] |
| T009 | pytest 单元 | [x] |
| T010 | CLI E2E 测试 | [x] |
| T011 | 原始文件保护 | [x] |
| T012 | raw_vault 保护 | [x] |
| T013 | 幂等 | [x] |
| T014 | 验收交接（STOP→DB/QA/HO） | [x] |

---

**Tasks 结束** — Dev 从 T001 开始，完成后 STOP → DB Agent。

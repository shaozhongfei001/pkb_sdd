# 阶段交接文档：Phase 1 — 003-duplicate-governance（精确重复治理）

> **项目**：个人历史项目文档知识库 `pkb_sdd`  
> **版本基线**：V1.1-SDD  
> **交接日期**：2026-06-15  
> **项目路径**：`/home/szf/dev/pyws/pkb_sdd`  
> **编写角色**：Handoff Agent（`HO`）  
> **当前 Spec**：`specs/003-duplicate-governance`  
> **前置文档**：`docs/handoff-phase1-001-002-before-003.md`、`docs/handoff-phase1-002-file-content-vault.md`

---

## 1. Executive Summary

**003-duplicate-governance** MVP 已完成实现、DB 审查与 E2E QA 验收，当前处于 **Handoff → Tech Lead Final Review** 阶段。

**Phase 1 文件治理底座进度**：

```text
001-file-inventory       ✅ 已完成
002-file-content-vault   ✅ 已完成
003-duplicate-governance ✅ 实现 + DB/QA PASS_WITH_NOTES（待 TL Final Review / merge main）
004+ 解析 / 价值 / 前端  ⬜ 未开始
```

**本 Spec 交付物**：

- 精确 sha256 重复组识别与 `kb_duplicate_group` upsert
- `kb_file_instance.duplicate_group_uid` 关联
- master candidate 确定性选择（§9 规则）
- cleanup suggestion 报告（`auto_execute=false`，仅建议）
- CLI：`govern-duplicates`
- pytest：003 新增 9 个用例；全链路回归 **23 passed**

**审查结论**：

| 角色 | 结论 |
|------|------|
| DB & Data Agent | `PASS_WITH_NOTES`，无阻断项，不要求 Dev 修复 |
| E2E QA Agent | `PASS_WITH_NOTES`，无阻断项，不要求 Dev 修复 |

**003 MVP 未修改 SQL schema**；不删除、不移动、不重命名原始文件；不删除 raw_vault 文件。

---

## 2. 当前分支与 commit 记录

| 项 | 值 |
|----|-----|
| **当前分支** | `feature/003-duplicate-governance` |
| **是否已 merge main** | 否（待 TL Final Review） |
| **工作区状态** | 干净（Handoff 提交前） |

**003 相关 commits（按时间顺序）**：

```text
07aa56f spec(003): add duplicate governance plan
aa56e08 feat(003): implement duplicate governance
9da3a2b spec(003): record review notes
```

**分支 HEAD**：`9da3a2b`（review notes 记录 commit）

---

## 3. 003 目标回顾

003 在 **原始文件只读、raw_vault 只读引用** 前提下，对 **sha256 完全一致** 的多路径重复进行元数据治理：

1. 识别 `instance_count >= 2` 的 `kb_file_content`（精确 sha256 重复）
2. upsert `kb_duplicate_group`（`duplicate_group_uid = sha256`）
3. 按 §9 规则选择 master candidate，写入 `kb_duplicate_group.master_file_instance_uid`
4. 更新同组全部 `kb_file_instance.duplicate_group_uid`
5. 输出 `duplicate_report_{UTC}.json`
6. 输出 `cleanup_suggestion_report_{UTC}.json`（`auto_execute=false`，`suggested_action=REVIEW_DUPLICATE`）
7. 提供 Typer CLI **`govern-duplicates`**
8. 保持幂等；单组失败不中断批处理

**数据流**：

```text
001 scan → 002 copy-to-vault → 003 govern-duplicates
  kb_file_content (instance_count>=2)
    → kb_duplicate_group upsert
    → kb_file_instance.duplicate_group_uid link
    → reports_root/*.json
```

---

## 4. 003 非目标与禁止事项

| 非目标 / 禁止 | 说明 |
|---------------|------|
| 语义 / 文本 / 路径 / 文件名相似去重 | 仅 sha256 精确重复 |
| LLM 判断版本或选 master | 无 LLM |
| `kb_version_candidate_group` | 后续 Spec |
| 执行删除 / 移动 / 重命名 / quarantine | 只出建议报告 |
| 修改 / 删除 raw_vault | 002 副本只读引用 |
| 修改 `inventory_scanner.py` / `file_content_vault.py` | 001/002 已封闭 |
| SQL schema 变更 | 003 MVP 无 migration |
| `--dry-run` | Plan §23 Q2：MVP 不实现 |
| MinerU / MarkItDown / Parser Router | 004+ |
| `parsed/` / `curated/` 写入 | 004 / 010+ |
| Streamlit / 向量库 / 项目卡蒸馏 | 011 / 012 / 010+ |
| 源代码知识库分析 | 全局禁止 |

---

## 5. 本次实现文件清单

| 操作 | 文件 | 说明 |
|------|------|------|
| **新增** | `backend/app/models/duplicate.py` | `KbDuplicateGroup` ORM（独立文件，不扩 `file.py`） |
| **新增** | `backend/app/services/duplicate_governance.py` | `DuplicateGovernanceService`、master 选择、cleanup suggestion、报告输出 |
| **修改** | `backend/app/cli/main.py` | 新增 `govern-duplicates` 命令 |
| **新增** | `backend/tests/test_duplicate_governance.py` | 9 个 pytest 用例 |
| **修改** | `specs/003-duplicate-governance/tasks.md` | T001–T013 勾选；T014 Handoff 完成 |

**未修改（封闭）**：

- `backend/app/services/inventory_scanner.py`
- `backend/app/services/file_content_vault.py`
- `sql/**`（无 migration）

---

## 6. 核心能力说明

### 6.1 重复组识别

- 候选条件：`kb_file_content.sha256 IS NOT NULL`、`instance_count >= 2`、`status = 'CONTENT_REGISTERED'`
- 组内 instance：仅加载 `status == 'DISCOVERED'`
- `duplicate_group_uid = sha256`；实查 DISCOVERED instance < 2 时跳过，不建组、不报错

### 6.2 Master candidate 选择（§9）

优先级（数值越小越优先）：

1. `is_duplicate_instance = 0` 优于 `1`
2. 路径较短（`len(source_path)` 升序）
3. 文件名不含 copy-like 标记（`副本`、`copy`、`bak`、`tmp`、`临时`、`- copy`、`_copy`）
4. `modified_time` 升序（NULL 排后）
5. 稳定排序：`created_at` → `file_instance_uid`

fixtures 预期：`方案.txt` 为 master，`方案副本.txt` 进入 cleanup suggestion。

**不修改** `kb_file_content.master_file_instance_uid`；若与 003 group master 不同，在 cleanup `reason` 中说明。

### 6.3 Cleanup suggestion

- 对每个非 master instance 生成一条建议
- `suggested_action = REVIEW_DUPLICATE`，`decision = PENDING`，`auto_execute = false`
- 不执行任何文件系统操作

### 6.4 批处理与异常

- 单组 DB 异常：rollback 该组 session，记入 `errors[]`，continue
- 全局 DB 连接失败：任务失败
- 报告写入失败：记 error；已提交 DB 部分不自动回滚（与 001 对齐）

---

## 7. CLI 使用方式

### 7.1 命令

```bash
cd /home/szf/dev/pyws/pkb_sdd/backend
source .venv/bin/activate

python -m app.cli.main govern-duplicates [--config PATH] [--sha256 HEX] [--content-uid UID] [--limit N]
```

### 7.2 选项

| 选项 | 说明 |
|------|------|
| `--config PATH` | 默认 `config/app.yaml` |
| `--sha256 HEX` | 仅处理指定内容 sha256 |
| `--content-uid UID` | 同 `--sha256`（001 中 `content_uid = sha256`） |
| `--limit N` | 最多处理 N 个候选 content |

### 7.3 全链路 E2E（fixtures）

```bash
python -m app.cli.main scan --path backend/tests/fixtures
python -m app.cli.main copy-to-vault
python -m app.cli.main govern-duplicates
```

**预期 Rich 汇总字段**：

```text
Candidates: N
Groups processed: N
Groups upserted: N
Instances linked: N
Suggestions generated: N
Skipped (unchanged): N
Errors: N
Duplicate report: {reports_root}/duplicate_report_{UTC}.json
Cleanup suggestion report: {reports_root}/cleanup_suggestion_report_{UTC}.json
```

### 7.4 保留命令

- `scan`、`copy-to-vault` 行为不变
- `build-parse-queue`、`parse` 仍为 placeholder

---

## 8. 数据库与 schema 结论

**003 MVP 未修改 SQL schema。**

- 复用已有 `kb_duplicate_group` 表
- 复用已有 `kb_file_instance.duplicate_group_uid` 列
- **未新增 migration**

| 表 | 003 操作 |
|----|----------|
| `kb_duplicate_group` | upsert |
| `kb_file_instance` | 读 + 写 `duplicate_group_uid` |
| `kb_file_content` | 只读 |
| `kb_raw_vault_object` | 只读（报告引用 `vault_path`） |

`KbDuplicateGroup` ORM 字段与 `sql/001_init_schema_v1_1.sql` 一一对应，无发明字段。

---

## 9. 报告输出说明

报告目录：`{storage.reports_root}/`（来自 `config/app.yaml`）

| 文件 | 说明 |
|------|------|
| `duplicate_report_{UTC}.json` | 重复组明细、instance 列表、summary |
| `cleanup_suggestion_report_{UTC}.json` | cleanup 建议列表；顶层 `auto_execute: false` |

**规则**：

- UTC 时间戳格式与 001 `inventory_scan_*` 对齐（`%Y%m%dT%H%M%SZ`）
- 每次运行生成 **新 timestamp 文件**，不覆盖旧报告
- 不写入 `parsed/`、`curated/`、`quarantine/`

---

## 10. 测试与验收结果

### 10.1 pytest 命令

```bash
cd /home/szf/dev/pyws/pkb_sdd/backend
source .venv/bin/activate

# 003 专项
pytest -q tests/test_duplicate_governance.py

# 全链路回归（001 + 002 + 003）
pytest -q tests/test_inventory_scanner.py tests/test_file_content_vault.py tests/test_duplicate_governance.py
```

### 10.2 测试结果

```text
23 passed in 4.01s
```

（QA 记录；Handoff 复核：`23 passed in 5.01s`）

| 模块 | 用例数 |
|------|--------|
| `test_inventory_scanner.py` | 7 |
| `test_file_content_vault.py` | 7 |
| `test_duplicate_governance.py` | 9 |

### 10.3 003 关键用例

| 用例 | 验证要点 |
|------|----------|
| `test_govern_normal_duplicate_group` | 2 instance → 1 group，master=`方案.txt` |
| `test_govern_idempotent` | 连续两次 govern，group 行数不变 |
| `test_govern_chinese_path` | 中文路径正常 |
| `test_govern_master_selection_copy_like_name` | `方案副本.txt` 不为 master |
| `test_govern_single_content_no_group` | instance_count=1 不建 group |
| `test_govern_single_group_error_continues` | 单组失败不中断 |
| `test_original_files_unchanged` | stat + hash 不变 |
| `test_raw_vault_unchanged` | vault bin 不变 |
| `test_govern_project_fixtures_integration` | scan → copy-to-vault → govern-duplicates 全链路 |

### 10.4 Acceptance A001–A006

| 编号 | 标准 | 结论 |
|------|------|------|
| **A001** 范围符合 | 仅 duplicate group + 报告 + CLI | ✅ PASS |
| **A002** 原始文件保护 | 不 move/delete/rename/overwrite | ✅ PASS |
| **A003** 幂等性 | 重复执行无重复主记录 | ✅ PASS |
| **A004** 异常可恢复 | 单组失败不中断 | ✅ PASS |
| **A005** 数据一致性 | DB ↔ 报告 ↔ group uid 一致 | ✅ PASS |
| **A006** 测试通过 | pytest + CLI E2E | ✅ PASS（23 passed） |

---

## 11. DB & Data Agent Review 结论

**结论**：`PASS_WITH_NOTES`，无阻断项，不要求 Dev 修复。

审查范围：ORM 与 init SQL 一致性、`kb_duplicate_group` upsert 幂等、`duplicate_group_uid` link 语义、状态字段流转、数据污染风险。

---

## 12. E2E QA Agent Review 结论

**结论**：`PASS_WITH_NOTES`，无阻断项，不要求 Dev 修复。

审查范围：pytest 全链路、CLI E2E（scan → copy-to-vault → govern-duplicates）、Acceptance A001–A006、原始文件只读、raw_vault 不变、重复执行幂等。

---

## 13. 已知 notes / 非阻断事项

以下 notes **不要求 Dev 修复**，可作为后续增强或文档备忘：

| ID | 说明 |
|----|------|
| **NOTE-1** | Plan 中列出的单实例 sha256 用例由 `test_govern_single_content_no_group` 覆盖，CLI 层可作为后续 QA 增强项 |
| **NOTE-2** | `content.instance_count >= 2` 但 DISCOVERED instance < 2 时不会建组、不报错；`groups_processed` / `skipped` 计数语义可后续微调 |
| **NOTE-3** | 单组事务隔离依赖 SQLAlchemy Session rollback，与 002 模式一致 |
| **NOTE-4** | pytest helper 清理测试数据，不删除真实原始文件和真实 raw_vault |

---

## 14. 原始文件保护结论

- 003 **不 open 原始文件进行 write**；不调用 `shutil.move` / `unlink` / `rename`
- CLI 入口通过 `ensure_readonly()` 保证 `original_files_readonly: true`
- `test_original_files_unchanged` 验证 govern 前后 stat + content hash 不变

**安全结论**：

```text
不删除、不移动、不重命名原始文件。
```

---

## 15. raw_vault 保护结论

- 003 **只读** `kb_file_content.vault_path`、`kb_raw_vault_object`；报告引用路径
- **不** create / delete / overwrite `raw_vault/**` 下任何文件
- cleanup suggestion **不得**包含删除 vault 的动作或 `auto_execute=true`
- `test_raw_vault_unchanged` 验证 `original.bin` hash 与目录 listing 在 govern 前后不变

**安全结论**：

```text
不删除 raw_vault 文件。
cleanup suggestion 仅为建议，auto_execute=false。
```

---

## 16. 幂等性结论

| 场景 | 行为 |
|------|------|
| 重复执行 `govern-duplicates` | `kb_duplicate_group` upsert 同键；group 各字段无变化 → 计 `skipped` |
| instance link | `duplicate_group_uid` UPDATE 幂等；已是目标值不重复计数 |
| 同一 sha256 新增 instance 后重跑 | 更新 `instance_count`、重新 link、报告反映新 instance |
| master 规则 | 同 instance 集合 → 同一 master uid（确定性） |
| 报告文件 | 每次运行新 timestamp 文件，不覆盖旧报告 |

`test_govern_idempotent` 验证：第二次 `groups_upserted == 0`，`skipped >= 1`，group 行数稳定。

---

## 17. 当前未提交 / 不应提交内容

| 类别 | 说明 |
|------|------|
| **工作区** | Handoff 编写前：干净 |
| **`config/app.yaml`** | 本地配置，含 MySQL 密码，**勿提交** |
| **`.env`** | 若有，勿提交 |
| **`backend/.venv/`** | 本地 Python 环境，勿提交 |
| **`raw_vault/**`** | 002 真实产物，勿提交 |
| **`reports/**`** | 本地运行报告，通常勿提交 |
| **pytest 临时数据** | `tmp_path` 与测试 DB 行由 helper 清理，非生产数据 |

Handoff 文档本身待 commit：

```text
docs/handoff-phase1-003-duplicate-governance.md
specs/003-duplicate-governance/tasks.md  （T014 勾选）
```

---

## 18. 下一阶段入口条件

**003 merge main 前（TL Final Review checklist）**：

- [ ] TL 阅读本 handoff、`plan.md`、`tasks.md`（T001–T014 全部 `[x]`）
- [ ] 确认 DB Review `PASS_WITH_NOTES` 无阻断项
- [ ] 确认 E2E QA `PASS_WITH_NOTES` 无阻断项
- [ ] 复核全链路 pytest：`23 passed`
- [ ] 确认未修改 SQL schema、未 touch 001/002 封闭 service
- [ ] 确认分支 `feature/003-duplicate-governance` commits 完整（plan + feat + review notes + handoff）
- [ ] merge 到 `main` 后打 tag 或记录 merge commit

**进入 004+ Spec 前**：

- [ ] 003 已 merge `main`
- [ ] 新 feature 分支基于 `main` HEAD 创建（如 `feature/004-*`）
- [ ] TL 完成下一 Spec 的 `plan.md` / `tasks.md` 与 Dev 白名单
- [ ] 已读最新 `docs/handoff-phase1-003-duplicate-governance.md`

---

## 19. 下一阶段禁止事项

继承 `docs/agent_collaboration_standard.md` §9 全局硬约束；**003 完成后仍禁止「顺便实现」**：

```text
MinerU
MarkItDown
Parser Router
parsed
curated
Streamlit
向量库
项目卡蒸馏
源代码知识库
```

额外提醒：

- 不自动删除重复文件
- 不删除 raw_vault 文件
- 不修改 SQL schema（除非目标 Spec 授权 + migration）
- 不修改 `inventory_scanner.py`、`file_content_vault.py`（除非 TL 明确解封）

---

## 20. 给新 ChatGPT / Cursor 会话的接手提示

### 20.1 会话启动模板

```text
当前角色：<TL|DEV|DB|QA|HO>
当前 Spec：specs/003-duplicate-governance（或下一 Spec）
当前分支：feature/003-duplicate-governance（或 main，若已 merge）
当前步骤：⑥ TL Final Review / 或 004 Plan
TL 批准的文件白名单：（DEV 必填）
禁止修改：backend 封闭 service、sql/**、raw_vault 真实产物、原始用户文件
```

### 20.2 必读文档（按顺序）

1. `docs/handoff-phase1-003-duplicate-governance.md`（本文）
2. `docs/agent_collaboration_standard.md`
3. `specs/003-duplicate-governance/plan.md`（含 §23 TL 决策）
4. 若进入 004+：对应 Spec 五件套 + 最新 handoff

### 20.3 快速命令

```bash
cd /home/szf/dev/pyws/pkb_sdd/backend
source .venv/bin/activate

# 全链路回归
pytest -q tests/test_inventory_scanner.py tests/test_file_content_vault.py tests/test_duplicate_governance.py

# CLI 全链路
python -m app.cli.main scan --path backend/tests/fixtures
python -m app.cli.main copy-to-vault
python -m app.cli.main govern-duplicates
```

### 20.4 交接确认清单

- [ ] 已读本文 Executive Summary 与 commit 记录
- [ ] 已知 003 实现文件清单与 CLI 用法
- [ ] 已知 schema 未变更、无 migration
- [ ] 已知 DB/QA 均为 `PASS_WITH_NOTES`，notes 非阻断
- [ ] 已知 NOTE-1–NOTE-4 非阻断备忘
- [ ] 已知下一阶段禁止事项（MinerU / parsed / curated / 向量库等）
- [ ] 未在 handoff 阶段修改业务代码

---

**文档结束** — STOP → Tech Lead Final Review → merge main → 下一 Spec Plan。

# 阶段总交接文档：Phase 1 — 001+002 文件治理底座 & 003 启动说明

> **项目**：个人历史项目文档知识库 `pkb_sdd`  
> **版本基线**：V1.1-SDD  
> **交接日期**：2026-06-15  
> **项目路径**：`/home/szf/dev/pyws/pkb_sdd`  
> **编写角色**：Handoff Agent / Tech Lead 汇总  
> **前置文档**：`docs/handoff-phase1-001-inventory.md`、`docs/handoff-phase1-002-file-content-vault.md`（细项可参考）

---

## 1. Executive Summary

Phase 1 **文件治理底座**前两步已完成并 merge 至 `main`：

| Spec | 状态 | Commit |
|------|------|--------|
| **001-file-inventory** | ✅ 验收通过 | `08e59ef` |
| **002-file-content-vault** | ✅ 验收通过 | `2f7eb46` |
| **Agent 协作规范** | ✅ 已 commit | `8b0004b` |
| **003-duplicate-governance** | ⬜ 未编码；Plan 已在会话中输出，**待落地 `plan.md`** | — |

**E2E 总结论**：

> 001 + 002 **可以验收通过**；pytest **14/14 passed**（2026-06-15 复验）。

**下一工作**：在 `feature/003-duplicate-governance`（需先 `merge main`）上，按 **Agent 协作流水线** 启动 003。

---

## 2. 已完成项

### 2.1 001-file-inventory

| 项 | 说明 |
|----|------|
| 功能 | 扫描目录 → `source_path_hash` + `sha256` → `kb_file_instance` / `kb_file_content` |
| CLI | `python -m app.cli.main scan --path <目录>` |
| 测试 | `tests/test_inventory_scanner.py` — 7 passed |
| Acceptance | A001–A006 ✅ |
| 关键文件 | `inventory_scanner.py`、`models/file.py`、`core/config|database|ids|file_types.py` |

### 2.2 002-file-content-vault

| 项 | 说明 |
|----|------|
| 功能 | 唯一 content → `raw_vault/by_hash/{prefix}/{sha256}/` + sidecar JSON |
| CLI | `python -m app.cli.main copy-to-vault` |
| 表 | `kb_file_content.vault_*`、`kb_raw_vault_object` |
| 测试 | `tests/test_file_content_vault.py` — 7 passed |
| Acceptance | A001–A006 ✅ |
| 关键文件 | `file_content_vault.py`、`models/vault.py`、`core/vault_paths.py` |
| Plan | `specs/002-file-content-vault/plan.md` 已落地 |

### 2.3 基础设施与规范

| 项 | 说明 |
|----|------|
| Git | `main` @ `8b0004b`；001/002 已 merge |
| Agent 协作 | `docs/agent_collaboration_standard.md`、`docs/role_prompts/*`、`.cursor/rules/007-agent-collaboration.mdc` |
| fixtures | `backend/tests/fixtures/中文路径/银行项目/`（2 个同内容 txt） |
| `.gitignore` | 排除 `.venv`、`config/app.yaml`、`raw_vault/` |

---

## 3. 未完成项 / 遗留

| 项 | 优先级 | 说明 |
|----|--------|------|
| **003 实现** | P0 | 编码未开始 |
| **003 plan.md 落地** | P0 | TL 会话 Plan 待写入 `specs/003-duplicate-governance/plan.md` |
| **feature/003 merge main** | P0 | `feature/003-duplicate-governance` 落后 `main` 1 commit（`8b0004b`） |
| **MySQL 可选清理** | P2 | pytest 历史行 / `COPY_ERROR` vault_object；不阻塞 003 |
| **`app.yaml` raw_vault_root`** | P2 | 本机可能为 `./raw_vault`；生产建议 `/home/szf/dev/data/personal-kb/raw_vault` |
| **001 TC004 扩展** | P3 | 扫描目录不存在行为；非阻塞 |
| **004+ 解析链** | — | 明确未开始 |

---

## 4. Commit 与分支状态

### 4.1 main 提交历史（相关）

```text
8b0004b docs: add lightweight multi-agent collaboration standard
2f7eb46 feat(002): implement file content vault
08e59ef feat(001): implement file inventory scanner
3002d87 docs: add phase1 inventory handoff
```

### 4.2 分支

| 分支 | 指向 | 说明 |
|------|------|------|
| `main` | `8b0004b` | **稳定底座 + 协作规范** |
| `feature/003-duplicate-governance` | `2f7eb46` | ⚠️ **需 merge main 后再开发 003** |
| `feature/002-file-content-vault` | `2f7eb46` | 可保留归档 |
| `feature/001-file-inventory` | `39ccb47` | 历史分支 |

### 4.3 003 启动前 Git 操作（必做）

```bash
cd /home/szf/dev/pyws/pkb_sdd
git checkout feature/003-duplicate-governance
git merge main
# 确认含 8b0004b 协作规范
```

---

## 5. 测试结果（交接时复验）

```bash
cd backend && source .venv/bin/activate
pytest -q tests/test_inventory_scanner.py tests/test_file_content_vault.py
# 14 passed in ~2.4s
```

### 5.1 CLI E2E 链路（fixtures）

```bash
python -m app.cli.main scan --path backend/tests/fixtures
python -m app.cli.main copy-to-vault
# 预期：scan 2 instance / 1 content；copy Candidates: 1, Copied: 1
```

### 5.2 QA 必查三项（001+002 已满足）

| 检查项 | 状态 |
|--------|------|
| 原始文件只读 | ✅ |
| 重复执行幂等 | ✅ |
| 单条异常不中断批处理 | ✅ |

---

## 6. 稳定底座（003 依赖，只读消费）

### 6.1 数据模型

```text
file_instance（路径）  →  kb_file_instance
file_content（SHA256）  →  kb_file_content
raw_vault 副本         →  kb_raw_vault_object + 磁盘产物
```

### 6.2 001 已写、003 只读

- `is_duplicate_instance`、`master_file_instance_uid`、`instance_count`
- `duplicate_group_uid` 字段存在但 **001/002 未填** → **003 写入**

### 6.3 002 已写、003 只读

- `vault_path`、`vault_status`、`kb_raw_vault_object`
- `raw_vault/.../original.bin` + sidecar JSON

### 6.4 003 将写

- `kb_duplicate_group` upsert
- `kb_file_instance.duplicate_group_uid`
- `duplicate_report_*.json`、`cleanup_suggestion_report_*.json`

---

## 7. 全局禁止项（003 仍适用）

| 不要做 | 原因 |
|--------|------|
| 自动删除 / 移动 / 重命名原始文件 | A002 |
| 删除 raw_vault 真实产物 | 项目规则 |
| 改 `inventory_scanner.py` / `file_content_vault.py` | 001/002 已封闭 |
| 改 `sql/001_init_schema_v1_1.sql` | 003 无 schema 缺口 |
| MinerU / MarkItDown / 前端 / 向量库 / LLM | 非 003 范围 |
| 版本树 / 内容相似度 | 003 仅 exact sha256 |
| 在 `feature/002-*` 上继续 003 | 分支策略 |

---

## 8. 003 启动说明

### 8.1 目标（精确重复治理）

```text
instance_count >= 2 的 content
  → upsert kb_duplicate_group（duplicate_group_uid = sha256）
  → 链接 kb_file_instance.duplicate_group_uid
  → 选择 master candidate（继承 001 master）
  → duplicate_report + cleanup_suggestion_report（仅建议，不执行删除）
  → decision = PENDING
```

### 8.2 TL 已输出 Plan 要点（待落地 plan.md）

| 项 | 决策 |
|----|------|
| 候选 | `kb_file_content.instance_count >= 2` |
| group uid | `duplicate_group_uid = sha256` |
| master | 优先 `content.master_file_instance_uid`；fallback 最早 `created_at` instance |
| 幂等 | 按 `duplicate_group_uid` upsert；bin/report 可刷新 |
| CLI | `govern-duplicates`（`--limit`、`--sha256`、`--refresh-reports-only`） |
| 服务 | `duplicate_governance.py`（或 `duplicate_detector.py`） |
| 测试 | `test_duplicate_governance.py` — 7 用例 |

完整 Plan 见新会话 TL 输出或待写入的 `specs/003-duplicate-governance/plan.md`。

### 8.3 Dev 文件白名单（预告，以 TL 最终 Plan 为准）

| 操作 | 路径 |
|------|------|
| 新增 | `backend/app/models/duplicate.py`（或扩 `file.py`） |
| 新增 | `backend/app/services/duplicate_governance.py` |
| 新增 | `backend/tests/test_duplicate_governance.py` |
| 修改 | `backend/app/cli/main.py` |
| 修改 | `specs/003-duplicate-governance/plan.md`、`tasks.md` |

**禁止改**：`inventory_scanner.py`、`file_content_vault.py`、`sql/**`、001/002 specs。

---

## 9. Agent 协作流水线（003 强制）

```text
① Tech Lead Plan     → 落地 plan.md；DEV 白名单；越界拒绝
② Dev Implementation → 先读 tasks.md；仅白名单
③ DB Review          → 幂等 / 污染 / schema 偏差；不改业务代码
④ E2E QA             → 测试设计 + 执行 + A001–A006 验收表
⑤ Handoff            → handoff-phase1-003-*.md
⑥ TL Final Review    → merge main；开 004 或下一 feature
```

**角色提示词**：`docs/role_prompts/*.md`  
**总规范**：`docs/agent_collaboration_standard.md`

---

## 10. 新会话启动模板（复制即用）

### 10.1 会话 A — Tech Lead（第一步）

```text
你是 Tech Lead Agent（TL）。你不写代码。

项目：/home/szf/dev/pyws/pkb_sdd
分支：feature/003-duplicate-governance（先 merge main）
必读：docs/handoff-phase1-001-002-governance-base.md
      docs/agent_collaboration_standard.md
      specs/003-duplicate-governance/*

任务：将 003 实现计划落地到 specs/003-duplicate-governance/plan.md，
      更新 tasks.md 骨架与 Dev 文件白名单。不改 backend。
```

### 10.2 会话 B — Dev（TL Plan 完成后）

```text
你是 Dev Agent（DEV）。先读 specs/003-duplicate-governance/tasks.md。

项目：/home/szf/dev/pyws/pkb_sdd
分支：feature/003-duplicate-governance
必读：docs/handoff-phase1-001-002-governance-base.md
      TL 提供的白名单

任务：按 tasks.md 实现 003 MVP。不改 SQL schema。不碰原始文件与 raw_vault 真实产物。
完成后 STOP → DB Agent。
```

### 10.3 后续会话

| 顺序 | 角色 | 提示词文件 |
|------|------|------------|
| ③ | DB | `docs/role_prompts/db_data_agent.md` |
| ④ | QA | `docs/role_prompts/e2e_qa_agent.md` |
| ⑤ | HO | `docs/role_prompts/handoff_agent.md` |
| ⑥ | TL | Final Review — `docs/role_prompts/tech_lead_agent.md` |

---

## 11. 快速命令参考

```bash
# 环境
cd /home/szf/dev/pyws/pkb_sdd/backend && source .venv/bin/activate

# 测试（001+002）
pytest -q tests/test_inventory_scanner.py tests/test_file_content_vault.py

# 流水线
python -m app.cli.main scan --path backend/tests/fixtures
python -m app.cli.main copy-to-vault
# 003 完成后：
# python -m app.cli.main govern-duplicates

# MySQL
mysql -upersonal_kb -pmahound personal_kb

# Git（003 启动前）
git checkout feature/003-duplicate-governance && git merge main
```

---

## 12. 相关文档索引

| 文档 | 路径 |
|------|------|
| **本文（总交接 + 003 启动）** | `docs/handoff-phase1-001-002-governance-base.md` |
| 001 交接 | `docs/handoff-phase1-001-inventory.md` |
| 002 交接 | `docs/handoff-phase1-002-file-content-vault.md` |
| Agent 协作 | `docs/agent_collaboration_standard.md` |
| 003 Spec | `specs/003-duplicate-governance/spec.md` |
| 002 Plan 范例 | `specs/002-file-content-vault/plan.md` |

---

## 13. 交接确认清单（003 启动前）

- [ ] 已读本文档与 `docs/agent_collaboration_standard.md`
- [ ] `main` 含 `08e59ef` + `2f7eb46` + `8b0004b`
- [ ] `feature/003-duplicate-governance` 已 `merge main`
- [ ] pytest 14/14 通过
- [ ] 本地 `config/app.yaml` 已配置（未提交）
- [ ] 理解 003 **不做** 删文件 / 解析器 / LLM
- [ ] 新会话从 **TL Plan** 开始，不跳过直接 Dev

---

**文档结束**

003 入口条件已满足（merge main 后）。请开 **新 Cursor 会话**，角色 **Tech Lead**，粘贴 §10.1 模板。

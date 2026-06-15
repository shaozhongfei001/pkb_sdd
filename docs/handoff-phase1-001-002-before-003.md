# 阶段交接文档：Phase 1 — 001+002 完成，003 启动前

> **项目路径**：`/home/szf/dev/pyws/pkb_sdd`  
> **版本基线**：V1.1-SDD（`sql/001_init_schema_v1_1.sql`）  
> **交接日期**：2026-06-15（本文档校验复验同日）  
> **读者**：新 Cursor 会话 / SubAgent — **无长上下文可直接接手**

---

## 硬性约束（全阶段有效，003 不得违反）

以下约束在后续 Spec 中**一律不做**，新会话不得「顺便实现」：

| 禁止项 | 说明 |
|--------|------|
| **不接 MinerU** | PDF/扫描/复杂版式解析 → 004+ |
| **不接 MarkItDown** | Office/HTML/JSON 等普通解析 → 005 |
| **不做 Parser Router** | 004 |
| **不做 `parsed/` 写入** | 解析产物目录，004 起 |
| **不做 `curated/` 写入** | 项目卡蒸馏，010 |
| **不做前端** | Streamlit / Web UI → 012 |
| **不做向量库** | embedding / 检索 → 011 |
| **不删除原始文件** | 扫描、复制、治理均为只读；不得 move/rename/overwrite |
| **不删除 `raw_vault`** | 002 副本只增不删；幂等时跳过已存在 `original.bin` |
| **003 仅重复治理 + 清理建议** | 精确 `sha256` 重复；报告 `duplicate_report` / `cleanup_suggestion_report`；**只建议，不执行删除/移动/quarantine** |

---

## 1. 项目路径与当前 Git 状态

### 1.1 路径

```text
项目根：/home/szf/dev/pyws/pkb_sdd
后端：  /home/szf/dev/pyws/pkb_sdd/backend
配置：  /home/szf/dev/pyws/pkb_sdd/config/app.yaml（本地，不提交）
Schema：/home/szf/dev/pyws/pkb_sdd/sql/001_init_schema_v1_1.sql
```

### 1.2 Git 状态（2026-06-15 校验时）

```text
当前分支：main @ e18c4fd
工作区：  ?? docs/handoff-phase1-001-002-before-003.md（本文，待 commit）
```

### 1.3 已完成 commit（按时间倒序）

| SHA | 说明 |
|-----|------|
| `e18c4fd` | docs: phase1 001+002 governance handoff + 003 kickoff |
| `8b0004b` | docs: lightweight multi-agent collaboration standard |
| `2f7eb46` | **feat(002): implement file content vault** |
| `08e59ef` | **feat(001): implement file inventory scanner** |
| `3002d87` | docs: phase1 inventory handoff |
| `70b17cd` | init: personal kb sdd cursor workspace |

### 1.4 分支

| 分支 | HEAD | 用途 |
|------|------|------|
| **`main`** | `e18c4fd` | 稳定底座（001+002+协作规范） |
| `feature/003-duplicate-governance` | `2f7eb46` | ⚠️ **落后 main 3 commit**；003 开发前必须 merge |
| `feature/002-file-content-vault` | `2f7eb46` | 已 merge，勿继续开发 |
| `feature/001-file-inventory` | `39ccb47` | 历史分支 |

### 1.5 003 启动前 Git 操作（必做）

```bash
cd /home/szf/dev/pyws/pkb_sdd
git checkout feature/003-duplicate-governance
git merge main
git log --oneline -3   # 应含 e18c4fd、8b0004b、2f7eb46
```

---

## 2. V1.1-SDD 总边界

### 2.1 本仓库在 V1.1 中的位置

```text
Phase 1 文件治理底座：
  001 盘点 → 002 raw_vault → 003 精确重复治理 → （后续 004+ 解析/价值/前端）
```

### 2.2 包含

- 历史**项目文档**（Office、PDF、图片、CSV/TXT 等）的路径登记与内容哈希
- MySQL 元数据（`kb_file_instance`、`kb_file_content`、`kb_raw_vault_object` 等）
- Typer CLI 批处理、`reports/` JSON 报告
- SDD 五件套（`spec.md` / `plan.md` / `tasks.md` / `acceptance.md` / `test_cases.md`）
- 轻量级五角色 Agent 协作（003 起强制）

### 2.3 不包含（当前阶段）

- 源代码仓库分析（Java/Python/JS 等）
- MinerU、MarkItDown、Parser Router、`parsed/`、`curated/`
- Streamlit / 任意前端、向量库、LLM 蒸馏
- 自动删除或移动用户原始文件、`raw_vault` 内容
- 多用户权限、企业协同

### 2.4 核心身份模型

| 概念 | 表 / 目录 | 身份键 |
|------|-----------|--------|
| `file_instance` | `kb_file_instance` | `source_path_hash`（规范化路径 SHA256） |
| `file_content` | `kb_file_content` | `sha256`（文件内容 SHA256） |
| `raw_vault` 副本 | `{raw_vault_root}/by_hash/...` | 按 `sha256` 内容寻址 |
| `duplicate_group` | `kb_duplicate_group` | **003 写入**；`duplicate_group_uid` 计划 = `sha256` |

### 2.5 SDD + Agent 推进顺序

```text
Spec → Plan → Tasks → Dev → DB Review → E2E QA → Handoff → TL Final Review → merge main
```

必读：`.cursor/rules/*.mdc`、`docs/sdd_development_standard.md`、目标 Spec 目录下全部五件套。

---

## 3. 已完成 Spec：001-file-inventory

| 项 | 值 |
|----|-----|
| 目录 | `specs/001-file-inventory/` |
| 实现 commit | **`08e59ef`** |
| `tasks.md` | T001–T005 全部 `[x]` |
| 验收 | A001–A006 ✅ |

### 3.1 实现目标（一句话）

扫描目录 → 文档候选 → `source_path_hash` + 分块 `sha256` → upsert `kb_file_instance` / `kb_file_content` → 同内容多路径标记 `is_duplicate_instance` → 幂等 → `inventory_scan_*.json`。

**001 不做**：`kb_duplicate_group`、`raw_vault`、解析、价值分层。

### 3.2 Commit `08e59ef` 涉及实现

见 **§6 已实现文件清单**（001 列）。

### 3.3 pytest 结果（2026-06-15 复验）

```bash
cd /home/szf/dev/pyws/pkb_sdd/backend && source .venv/bin/activate
pytest -q tests/test_inventory_scanner.py
```

```text
7 passed in ~2.4s
```

| 测试函数 | 验证点 |
|----------|--------|
| `test_scan_normal_files` | 普通文件入库 |
| `test_scan_idempotent` | 重复扫描无重复行 |
| `test_scan_chinese_path` | 中文路径 |
| `test_scan_duplicate_content` | 同 SHA256 → 1 content、2 instance |
| `test_scan_single_file_error_continues` | 单文件失败不中断批次 |
| `test_original_files_unchanged` | 原始文件 mtime/内容不变 |
| `test_scan_project_fixtures` | fixtures 集成 |

### 3.4 CLI E2E 结果（2026-06-15 实跑）

```bash
cd /home/szf/dev/pyws/pkb_sdd/backend && source .venv/bin/activate
python -m app.cli.main scan --path tests/fixtures
```

```text
Scanned files: 2
New instances: 2
Updated instances: 0
New contents: 1
Updated contents: 1
Duplicate instances: 1
Errors: 0
```

说明：fixtures 为 `backend/tests/fixtures/中文路径/银行项目/方案.txt` 与 `方案副本.txt`（同内容）。

### 3.5 Acceptance

| 编号 | 结论 |
|------|------|
| A001 范围 | ✅ 仅盘点与两表 |
| A002 只读 | ✅ 不修改原始文件 |
| A003 幂等 | ✅ `source_path_hash` upsert |
| A004 容错 | ✅ 单文件 ERROR 继续 |
| A005 一致性 | ✅ instance ↔ content |
| A006 可验证 | ✅ pytest + CLI |

---

## 4. 已完成 Spec：002-file-content-vault

| 项 | 值 |
|----|-----|
| 目录 | `specs/002-file-content-vault/` |
| 实现 commit | **`2f7eb46`** |
| `plan.md` | 已落地（492 行） |
| `tasks.md` | T001–T005 全部 `[x]` |
| 验收 | A001–A006 ✅ |

### 4.1 实现目标（一句话）

`vault_status=NOT_COPIED` 的 content → 从 master instance **只读**分块复制 → `raw_vault/by_hash/{sha256[:2]}/{sha256}/` → sidecar JSON → 更新 `kb_file_content.vault_*` + upsert `kb_raw_vault_object` → bin 已存在且 hash 正确则跳过复制。

### 4.2 Commit `2f7eb46` 新增实现

见 **§6**（002 列：`vault_paths.py`、`vault.py`、`file_content_vault.py`、`copy-to-vault` CLI、vault tests）。

### 4.3 pytest 结果（2026-06-15 复验）

```bash
pytest -q tests/test_file_content_vault.py
```

```text
7 passed
```

合并跑：

```bash
pytest -q tests/test_inventory_scanner.py tests/test_file_content_vault.py
# 14 passed in 2.36s
```

| 测试函数 | 验证点 |
|----------|--------|
| `test_copy_normal_content` | 首次复制 COPIED |
| `test_copy_idempotent` | 二次跳过 bin、刷新元数据 |
| `test_copy_chinese_master_path` | 中文 master 路径 |
| `test_copy_duplicate_instances_one_bin` | 2 instance → 1 `original.bin` |
| `test_copy_source_missing_continues` | 单 content 失败不中断 |
| `test_original_files_unchanged` | 原始文件不变 |
| `test_copy_project_fixtures_integration` | scan → vault 链路 |

### 4.4 CLI E2E 结果（2026-06-15 实跑，在 scan 之后）

```bash
python -m app.cli.main copy-to-vault
```

```text
Candidates: 1
Copied: 0
Skipped (already copied): 1
Metadata refreshed: 1
Errors: 0
```

说明：fixtures 对应 content `sha256=536985990c2e...` 已 COPIED，二次执行验证 **幂等跳过**（A003）。

### 4.5 Acceptance

| 编号 | 结论 |
|------|------|
| A001 范围 | ✅ vault + 两表 + CLI |
| A002 只读 | ✅ 分块复制，不改源文件 |
| A003 幂等 | ✅ bin hash 正确则 skip |
| A004 容错 | ✅ 单 content 失败继续 |
| A005 一致性 | ✅ vault_path ↔ 磁盘 ↔ sha256 |
| A006 可验证 | ✅ pytest + CLI |

---

## 5. 已实现文件清单（`main` 业务代码 @ `2f7eb46`）

### 5.1 `backend/app/`（11 个 Python 模块）

| 文件 | Spec | 职责 |
|------|------|------|
| `core/config.py` | 001 | 读 `app.yaml`；`ensure_readonly()` |
| `core/database.py` | 001 | SQLAlchemy engine / session |
| `core/ids.py` | 001 | 路径规范化、`source_path_hash`、分块 `sha256` |
| `core/file_types.py` | 001 | 扩展名白名单；跳过 `reports` 等目录 |
| `core/vault_paths.py` | 002 | vault 路径与状态常量 |
| `models/file.py` | 001 | `KbFileInstance`、`KbFileContent` |
| `models/vault.py` | 002 | `KbRawVaultObject` |
| `services/inventory_scanner.py` | 001 | 扫描核心（**003 勿改**） |
| `services/file_content_vault.py` | 002 | vault 复制（**003 勿改**） |
| `cli/main.py` | 001+002 | `scan`、`copy-to-vault` |
| `main.py` | init | FastAPI `GET /health` |

### 5.2 测试与 fixtures

| 文件 | Spec |
|------|------|
| `tests/test_inventory_scanner.py` | 001（7 tests） |
| `tests/test_file_content_vault.py` | 002（7 tests） |
| `tests/fixtures/中文路径/银行项目/方案.txt` | 共用 fixture |
| `tests/fixtures/中文路径/银行项目/方案副本.txt` | 重复内容 fixture |

### 5.3 依赖与环境

| 文件 | 说明 |
|------|------|
| `backend/requirements.txt` | pip 依赖 |
| `backend/.venv/` | 本地 venv，**不提交** |

### 5.4 003 预期新增（尚未存在）

```text
backend/app/services/duplicate_governance.py
backend/app/models/duplicate.py（或扩 file.py）
backend/app/cli/main.py          # 新增 govern-duplicates
backend/tests/test_duplicate_governance.py
```

---

## 6. 当前数据库状态与关键表

### 6.1 连接

```bash
mysql -upersonal_kb -p personal_kb
# 用户 personal_kb@localhost；密码见 config/app.yaml（勿提交）
```

Schema 版本：`v1.1.0` — **003 MVP 不修改** `sql/001_init_schema_v1_1.sql`。

### 6.2 行数快照（2026-06-15 校验后，含 pytest + CLI 残留）

| 表 | 行数 | 001 | 002 | 003 |
|----|------|-----|-----|-----|
| `kb_file_instance` | **2** | 写 | 读 | 读+写 `duplicate_group_uid` |
| `kb_file_content` | **3** | 写 | 写 `vault_*` | 读 |
| `kb_raw_vault_object` | **3** | — | 写 | 读 |
| `kb_duplicate_group` | **0** | — | — | **写** |
| `kb_schema_version` | 1 | — | — | — |
| `kb_version_candidate_group` | 0 | — | — | **不做** |
| `kb_parse_job` | 0 | — | — | **不做**（MinerU/MarkItDown） |
| `kb_document` 及下游 | 0 | — | — | **不做**（parsed/curated） |
| `kb_embedding_ref` | 0 | — | — | **不做**（向量库） |

### 6.3 fixtures 相关实例（可直接用于 003 验收设计）

**`kb_file_instance`（2 行，同一 `sha256`）**

| `file_instance_uid`（前缀） | `source_path` 末尾 | `is_duplicate_instance` | `duplicate_group_uid` |
|----------------------------|-------------------|-------------------------|----------------------|
| `6e996e8c...` | `.../方案.txt` | 0（master） | `NULL` |
| `df5ac3b6...` | `.../方案副本.txt` | 1 | `NULL` |

共同 `sha256`：`536985990c2e2203a74c297bf66c7939873e53647bb41fb9cc72bb42bd6463d6`

**`kb_file_content`（fixtures 行）**

| `sha256`（前缀） | `instance_count` | `vault_status` | `vault_path` |
|-----------------|------------------|----------------|--------------|
| `536985990c2e...` | **2** | **COPIED** | `.../raw_vault/by_hash/53/536985990c2e...` |

另 2 行来自 pytest 临时数据，`vault_status=COPY_ERROR`（可忽略或手动清理，不阻塞 003）。

### 6.4 003 将使用的已有字段

- `kb_file_instance.duplicate_group_uid` — 001 已建列，001 未写
- `kb_duplicate_group` — SQL 已建表，全字段可用，无需 migration

---

## 7. 配置文件与不提交 Git 的内容

### 7.1 配置

| 文件 | 提交 | 说明 |
|------|------|------|
| `config/app.example.yaml` | ✅ | 模板 |
| `config/app.yaml` | ❌ | 本地密码与路径 |
| `config/parser_rules.yaml` 等 | ✅ | 004+ 用，当前代码未读 |

创建本地配置：

```bash
cp config/app.example.yaml config/app.yaml
# 编辑 mysql.password、storage.*_root
```

本机 `app.yaml` 实测：`raw_vault_root` 指向项目内 `./raw_vault`（非 `/home/szf/dev/data/personal-kb/`）。**以本地 `app.yaml` 为准。**

### 7.2 不得提交（`.gitignore` 已覆盖）

| 路径 | 原因 |
|------|------|
| `config/app.yaml` | 数据库密码 |
| `backend/.venv/` | 本地 Python |
| `__pycache__/`、`*.pyc`、`.pytest_cache/` | 缓存 |
| `raw_vault/` | 002 运行时产物 |
| `reports/`、`parsed/`、`curated/`、`quarantine/` | 运行时数据 |
| 用户原始文档目录 | 永不入库 |

误加 venv：`git rm -r --cached backend/.venv`

---

## 8. raw_vault 产物说明

### 8.1 目录布局

```text
{raw_vault_root}/by_hash/{sha256[0:2]}/{sha256}/
  original.bin           # 内容副本（与 sha256 一致）
  original_name.txt      # master 的 file_name（可中文）
  source_paths.json      # 全部 instance 路径清单
  file_metadata.json     # 内容与 vault 元数据
```

### 8.2 本机实测路径（2026-06-15）

```text
/home/szf/dev/pyws/pkb_sdd/raw_vault/by_hash/53/536985990c2e2203a74c297bf66c7939873e53647bb41fb9cc72bb42bd6463d6/
  original.bin
  original_name.txt
  source_paths.json
  file_metadata.json
```

对应 DB：`kb_file_content.vault_status=COPIED`，`kb_raw_vault_object.copy_status=COPIED`。

### 8.3 操作约束

- Dev / QA 在 **pytest `tmp_path`** 内测 vault；勿删改本机生产 `raw_vault/`
- 幂等：已存在且 hash 正确的 `original.bin` **不覆盖、不删除**
- 003 只读引用 vault 路径写报告，**不写、不删** raw_vault

---

## 9. 003-duplicate-governance 入口条件

| # | 条件 | 状态 |
|---|------|------|
| 1 | `main` 含 `08e59ef`（001）+ `2f7eb46`（002） | ✅ |
| 2 | pytest 001+002：**14 passed** | ✅ |
| 3 | CLI `scan` + `copy-to-vault` E2E 可跑 | ✅ |
| 4 | `kb_file_instance` / `kb_file_content` 有重复样本（`instance_count=2`） | ✅ |
| 5 | `kb_duplicate_group` 表存在、0 行 | ✅ |
| 6 | Agent 协作规范 commit `8b0004b` | ✅ |
| 7 | `feature/003` **merge `main`** | ⚠️ 待做 |
| 8 | `specs/003-duplicate-governance/plan.md` 落地 | ⚠️ 待 TL |
| 9 | 理解硬性约束（§ 文首） | 接手时确认 |

---

## 10. 003 推荐范围（收敛）

### 10.1 只做这些

```text
筛选 instance_count >= 2 的 kb_file_content（精确 sha256 重复）
  → upsert kb_duplicate_group（duplicate_group_uid = sha256）
  → 更新 kb_file_instance.duplicate_group_uid
  → master = kb_file_content.master_file_instance_uid（与 001 一致）
  → reports_root/duplicate_report_{UTC}.json
  → reports_root/cleanup_suggestion_report_{UTC}.json
  → decision = PENDING；suggested_action = REVIEW_DUPLICATE；auto_execute = false
```

CLI：`python -m app.cli.main govern-duplicates`

### 10.2 表操作

| 表 | 003 |
|----|-----|
| `kb_duplicate_group` | upsert |
| `kb_file_instance` | 读 + 写 `duplicate_group_uid` |
| `kb_file_content` | 只读 |
| `kb_raw_vault_object` | 只读（报告引用） |

**不修改** `inventory_scanner.py`、`file_content_vault.py`、`sql/001_init_schema_v1_1.sql`。

### 10.3 明确不做（003 内）

| 不做 | 原因 |
|------|------|
| 版本树 / `kb_version_candidate_group` | 后续 Spec |
| 内容相似度（非 sha256） | 超出精确重复 |
| LLM 选 master | 无 LLM |
| 自动 quarantine / 自动删路径 | 只出清理**建议** |
| MinerU / MarkItDown / parsed / curated / 前端 / 向量库 | 见文首硬性约束 |

---

## 11. Agent 协作规范（003 起强制）

已 commit：`8b0004b`

| 文档 | 路径 |
|------|------|
| 总规范 | `docs/agent_collaboration_standard.md` |
| Cursor 规则 | `.cursor/rules/007-agent-collaboration.mdc` |
| 角色提示词 | `docs/role_prompts/{tech_lead,dev,db_data,e2e_qa,handoff}_agent.md` |

```text
① TL Plan（不写代码）→ ② Dev（仅白名单）→ ③ DB Review → ④ E2E QA → ⑤ Handoff → ⑥ TL Final Review
```

| 角色 | 写权限 |
|------|--------|
| Tech Lead | `specs/*/plan.md`、`tasks.md` |
| Dev | TL 白名单 `backend/**` |
| DB | 审查报告；授权时 `sql/migrations/**` |
| QA | `backend/tests/**`（若授权）、验收记录 |
| Handoff | `docs/handoff-*.md` |

---

## 12. 下一步 Cursor 提示词

### 12.1 Tech Lead（新会话第一步）

```text
你是 Tech Lead Agent。你不写代码。

项目：/home/szf/dev/pyws/pkb_sdd
分支：feature/003-duplicate-governance（先 git merge main）

必读：
- docs/handoff-phase1-001-002-before-003.md
- docs/agent_collaboration_standard.md
- docs/role_prompts/tech_lead_agent.md
- specs/003-duplicate-governance/spec.md、acceptance.md、test_cases.md

任务：
1. 落地 specs/003-duplicate-governance/plan.md
2. 更新 tasks.md（Dev 文件白名单）
3. 不改 backend/**、sql/**

硬性约束：不接 MinerU/MarkItDown；不做 parsed/curated/前端/向量库；
不删原始文件与 raw_vault；003 只做精确重复治理与清理建议报告。

越界拒绝。完成后 STOP → Dev。
```

### 12.2 Dev（TL Plan 后）

```text
你是 Dev Agent。先读 specs/003-duplicate-governance/tasks.md 与白名单。

项目：/home/szf/dev/pyws/pkb_sdd
分支：feature/003-duplicate-governance

禁止改：inventory_scanner.py、file_content_vault.py、sql/**、原始文件、raw_vault 真实目录。

完成后 STOP → DB。不要自我验收。
```

### 12.3 后续步骤

| 步骤 | 读 `docs/role_prompts/` |
|------|-------------------------|
| DB Review | `db_data_agent.md` |
| E2E QA | `e2e_qa_agent.md` |
| Handoff | `handoff_agent.md` |
| TL Final | `tech_lead_agent.md` |

### 12.4 003 完成后全链路验证

```bash
cd /home/szf/dev/pyws/pkb_sdd/backend && source .venv/bin/activate
python -m app.cli.main scan --path tests/fixtures
python -m app.cli.main copy-to-vault
python -m app.cli.main govern-duplicates
pytest -q tests/test_inventory_scanner.py tests/test_file_content_vault.py tests/test_duplicate_governance.py
```

---

## 13. 交接确认清单

- [ ] 已读本文 + 文首**硬性约束**
- [ ] `main` @ `e18c4fd`；`feature/003` 已 merge main
- [ ] `config/app.yaml` 存在且未提交；`backend/.venv` 未跟踪
- [ ] pytest **14 passed**；CLI scan + copy-to-vault 实跑 OK
- [ ] DB 有 `instance_count=2` 的 fixtures 行（§6.3）
- [ ] 明确 003 **只建议不删除**；不改 001/002 service
- [ ] 新会话从 **§12.1 Tech Lead** 开始

---

## 附录：相关文档

| 文档 | 路径 |
|------|------|
| 001 详交接 | `docs/handoff-phase1-001-inventory.md` |
| 002 详交接 | `docs/handoff-phase1-002-file-content-vault.md` |
| 002 plan | `specs/002-file-content-vault/plan.md` |
| 003 spec | `specs/003-duplicate-governance/spec.md` |
| SQL | `sql/001_init_schema_v1_1.sql` |

**文档结束** — 新会话从 §12.1 开始。

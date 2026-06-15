# Agent 协作规范（轻量级）

> **项目**：个人历史项目文档知识库 `pkb_sdd`  
> **项目路径**：`/home/szf/dev/pyws/pkb_sdd`  
> **版本基线**：V1.1-SDD  
> **适用阶段**：Phase 1 文件治理底座（001、002 已完成；003 起强制适用本规范）  
> **目标**：控制 Cursor / ChatGPT 多角色协作范围，减少上下文污染，防止越界开发

---

## 1. 项目当前阶段说明

### 1.1 已完成

| Spec | 说明 | 状态 |
|------|------|------|
| **001-file-inventory** | 扫描目录 → `kb_file_instance` / `kb_file_content` → 盘点报告 | ✅ 已实现 |
| **002-file-content-vault** | 只读复制 → `raw_vault/by_hash/...` → vault 元数据 | ✅ 已实现 |

### 1.2 当前位置

```text
Phase 1 文件治理底座：
  001 盘点 → 002 raw_vault → 【003 精确重复治理】→ 004+ 解析 / 价值 / 前端
```

- **003-duplicate-governance** 尚未开发；进入 003 前须完成 TL Plan（`plan.md` / `tasks.md`）及本规范落地。
- 本规范文档任务 **不开发 003**，不修改任何业务代码。

### 1.3 核心身份模型（全阶段有效）

| 概念 | 表 / 目录 | 身份键 |
|------|-----------|--------|
| `file_instance` | `kb_file_instance` | `source_path_hash`（规范化路径 SHA256） |
| `file_content` | `kb_file_content` | `sha256`（文件内容 SHA256） |
| `raw_vault` 副本 | `{raw_vault_root}/by_hash/...` | 按 `sha256` 内容寻址 |
| `duplicate_group` | `kb_duplicate_group` | 003 写入；`duplicate_group_uid` 计划 = `sha256` |

---

## 2. SDD 基本流程

每个 Spec 按 **SDD 五件套** 推进（`spec.md` / `plan.md` / `tasks.md` / `acceptance.md` / `test_cases.md`），配合五角色 Agent：

```text
Plan → 实现 → 测试 → 验收 → 交接 → Final Review
```

对应 Agent 流水线：

```text
① Tech Lead Plan        → plan.md / tasks.md / Dev 文件白名单
② Dev Implementation    → 仅白名单内 backend/**
③ DB Review             → 审查报告；不交还则阻断 QA
④ E2E QA                → pytest + CLI E2E + 验收表 A001–A006
⑤ Handoff               → docs/handoff-*.md
⑥ Tech Lead Final Review → 是否可 merge main；下一 Spec 入口
```

**门禁原则**：

- 没有 Plan / Tasks，不进入实现。
- 没有 DB 审查通过，不进入 QA。
- 没有 QA 验收通过，不写 handoff「可 merge」结论。
- 单文件单写者；下一角色开始前上一角色 STOP。

---

## 3. Agent 角色分工

| 角色 | 代号 | 核心职责 |
|------|------|----------|
| **Tech Lead Agent** | `TL` | 范围控制、Plan、设计审查、Final Review |
| **Dev Agent** | `DEV` | **唯一**允许修改业务代码（TL 白名单内） |
| **DB & Data Agent** | `DB` | SQL / ORM / 数据一致性 / 幂等审查 |
| **E2E QA Agent** | `QA` | 测试设计、执行、Acceptance 验收 |
| **Handoff Agent** | `HO` | 阶段交接文档，供新会话无缝接手 |

不新增其他 Agent 角色；不引入复杂工作流系统或自动化脚本。

---

## 4. 各角色职责边界

### 4.1 Tech Lead Agent（`TL`）

**做**：

- 读取交接文档、Spec、Plan、Acceptance
- 范围判断：任务是否属于当前活跃 Spec
- 产出 / 更新 `plan.md`、`tasks.md`
- 拆分任务、识别越界风险、审查验收标准
- 为 Dev 列出 **文件白名单** 与 **禁止修改清单**
- Final Review：是否可 merge、下一 Spec 入口条件

**不做**：写 / 改 `backend/**`、执行实现、替 QA 宣布验收通过。

### 4.2 Dev Agent（`DEV`）

**做**：

- 先读 `tasks.md`，再读 plan / spec / acceptance
- 仅改 TL 白名单内 `backend/**`
- 同步补充或更新 pytest（若 TL 将测试划入白名单）
- 保持幂等性；保护原始文件只读
- 更新 `tasks.md` 勾选；汇报变更与运行方式

**不做**：改白名单外文件、改 SQL schema（无 Spec 授权）、碰原始文件与 raw_vault 真实产物、自我验收、写 handoff。

### 4.3 DB & Data Agent（`DB`）

**做**：

- 审查 ORM 与 `sql/001_init_schema_v1_1.sql` 一致性
- 审查状态字段流转（`vault_status`、`decision` 等）
- 指出幂等问题、数据污染、schema 偏差
- 输出审查报告：通过 / 需修改（交还 DEV）

**不做**：直接改 `backend/app/services/**` 等业务代码；未授权改 init SQL。

### 4.4 E2E QA Agent（`QA`）

**做**：

- 测试设计（对照 `test_cases.md`）
- 执行 pytest、CLI E2E、MySQL 查询
- 输出验收表 A001–A006（附证据）
- 必查：原始文件只读、重复执行幂等、异常不中断批处理

**不做**：改 `backend/app/services/**` 以凑通过；删 raw_vault / 原始文件「清理环境」。

### 4.5 Handoff Agent（`HO`）

**做**：

- 撰写 `docs/handoff-phase*-*.md`
- 记录分支、commit、修改文件、测试命令与结果、验收结论
- 记录未完成项、下一阶段入口条件与禁止事项
- 使新 ChatGPT / Cursor 会话可无长上下文接手

**不做**：改代码、Spec、SQL；QA 未通过时写「可验收」；引入新设计。

---

## 5. 各角色禁止事项

| 角色 | 禁止 |
|------|------|
| **TL** | 写业务代码；越界任务不拒绝；擅自扩大 Spec 范围；跳过 DB / QA 直接 merge |
| **DEV** | 未读 tasks.md 即写代码；改白名单外文件；改 SQL schema（无授权）；move/delete/rename/overwrite 原始文件；改 raw_vault 真实产物；自我验收 |
| **DB** | 直接 patch 业务 service；无 migration 流程批准 init SQL 修改；建议 DELETE 原始数据作默认清理 |
| **QA** | 改 service 使测试通过；触碰 raw_vault 或原始文件做清理；自行 merge main |
| **HO** | QA 未通过时写可 merge；同时改 handoff 与 backend；删除 / 移动 raw_vault / 原始文件 |
| **全部** | 多 Agent 同时改同一文件；实现非当前 Spec 功能；未经 Spec + migration 改 schema |

---

## 6. 进入开发前检查清单

Dev 或 TL 在步骤 ② 开始前确认：

- [ ] 已读目标 Spec 五件套（`spec.md`、`plan.md`、`tasks.md`、`acceptance.md`、`test_cases.md`）
- [ ] 已读 `docs/agent_collaboration_standard.md` 与 `.cursor/rules/*.mdc`
- [ ] 已读最新 `docs/handoff-*.md`（若有）
- [ ] TL Plan 已完成；**Dev 文件白名单** 已列出
- [ ] 当前分支正确（如 `feature/00N-*`）
- [ ] 明确本 Spec **不做项**（见 §10 全局硬约束）
- [ ] 无要求跳过 DB Review 或 QA
- [ ] `config/app.yaml` 本地存在且未误提交（不纳入 git）

---

## 7. 提交前检查清单

Dev 在 STOP → DB 前自检；QA / HO 可复核：

- [ ] 改动文件 **全部** 在 TL 白名单内
- [ ] 未修改 `sql/001_init_schema_v1_1.sql` 或未授权 schema
- [ ] 未 touch 原始文件目录与 raw_vault 真实产物
- [ ] pytest 可运行（Dev 汇报命令与结果，不替代 QA 验收）
- [ ] 幂等路径已考虑（重复 CLI 不产生重复主记录）
- [ ] 单条失败不中断批处理（若适用）
- [ ] ORM 字段与 init SQL 一致，无未文档化字段
- [ ] `tasks.md` 已勾选完成项
- [ ] 无 `.env`、`config/app.yaml`、密码明文被提交

---

## 8. 阶段交接要求

Handoff 文档（`docs/handoff-phase{N}-{spec-id}.md`）**必须**包含：

| # | 内容 |
|---|------|
| 1 | **当前分支** 与 **commit** hash |
| 2 | **修改文件清单**（实现 + 测试） |
| 3 | **测试命令** 与 **测试结果**（pytest 数、CLI E2E 摘要） |
| 4 | **验收结论**（A001–A006，引用 QA 报告） |
| 5 | **未提交文件** / 工作区状态 |
| 6 | **已完成项** / **未完成项** |
| 7 | **下一阶段入口条件**（可执行、可验证） |
| 8 | **下一阶段禁止事项**（继承全局硬约束） |
| 9 | 快速命令、交接确认清单 |
| 10 | 无密码明文 |

命名示例：`docs/handoff-phase1-003-duplicate-governance.md`

---

## 9. 当前项目全局硬约束

以下约束 **全阶段有效**；任何 Agent 不得「顺便实现」：

| # | 禁止项 |
|---|--------|
| 1 | **不处理源代码知识库**（Java/Python/JS 等源码仓库分析） |
| 2 | **不移动、不删除、不重命名、不覆盖** 原始用户文件 |
| 3 | **不自动删除重复文件** |
| 4 | **不删除 raw_vault** 文件（002 副本只增不删；幂等跳过已存在 bin） |
| 5 | **不接 MinerU**（PDF/扫描/复杂版式 → 006+） |
| 6 | **不接 MarkItDown**（Office/HTML 等 → 005+） |
| 7 | **不做 Parser Router**（004+） |
| 8 | **不做 `parsed/` 写入**（004 起） |
| 9 | **不做 `curated/` 写入**（010 起） |
| 10 | **不做 Streamlit / 前端**（012+） |
| 11 | **不做向量库**（embedding / 检索 → 011+） |
| 12 | **不做项目卡蒸馏** |
| 13 | **不修改 SQL schema**，除非目标 Spec 明确授权且走 migration |
| 14 | **不上传私有文档到外部云服务**（默认） |

001 / 002 已封闭 service（003 默认禁止 Dev 修改）：

- `backend/app/services/inventory_scanner.py`
- `backend/app/services/file_content_vault.py`

---

## 10. 003 前的特别约束

进入 **003-duplicate-governance** 时，在 §9 基础上额外收敛：

### 10.1 003 只做

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

### 10.2 003 明确不做

| 不做 | 原因 |
|------|------|
| **删除 / 移动 / 重命名** 原始文件或 instance | 只出清理**建议**，`auto_execute = false` |
| **语义相似 / 非 sha256 去重** | 超出精确重复 |
| **LLM 判断版本 / 选 master** | 无 LLM；master 沿用 001 |
| **版本树 / `kb_version_candidate_group`** | 后续 Spec |
| **自动 quarantine** | 只报告，不执行 |
| MinerU / MarkItDown / parsed / curated / 前端 / 向量库 | 见 §9 |

### 10.3 003 表操作边界

| 表 | 003 |
|----|-----|
| `kb_duplicate_group` | upsert |
| `kb_file_instance` | 读 + 写 `duplicate_group_uid` |
| `kb_file_content` | 只读 |
| `kb_raw_vault_object` | 只读（报告引用） |

**不修改** `sql/001_init_schema_v1_1.sql`（表已存在，无需 migration）。

---

## 11. 角色写权限一览

| 角色 | 可写 | 禁止 |
|------|------|------|
| **TL** | `specs/*/plan.md`、`specs/*/tasks.md`；Review 结论 | 任何 `backend/**`、`sql/**`、替 QA 验收 |
| **DEV** | TL 白名单内 `backend/**`；`tasks.md` 勾选 | 白名单外、SQL schema、原始文件、raw_vault 真实产物 |
| **DB** | 审查报告；TL 授权时 `sql/migrations/**` | 业务 Python、未授权 schema |
| **QA** | `backend/tests/**`（若 TL 授权）、验收记录 | `backend/app/services/**`、handoff |
| **HO** | `docs/handoff-*.md` | 代码、Spec、SQL、pytest 代替 QA |

**唯一业务代码实现者**：`DEV`（且在 TL 白名单内）。

---

## 12. 会话启动模板

```text
当前角色：<TL|DEV|DB|QA|HO>
当前 Spec：specs/00N-*
当前分支：feature/00N-*
当前步骤：①–⑥
TL 批准的文件白名单：（DEV 必填）
禁止修改：（黑名单）
```

---

## 13. 相关引用

| 文档 | 路径 |
|------|------|
| SDD 开发标准 | `docs/sdd_development_standard.md` |
| Cursor 规则 | `.cursor/rules/000-project-rules.mdc` … `007-agent-collaboration.mdc` |
| 角色提示词 | `docs/role_prompts/*.md` |
| Phase 1 交接 | `docs/handoff-phase1-001-002-before-003.md` |

---

**文档结束**

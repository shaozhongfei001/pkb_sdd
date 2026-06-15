# Agent 协作规范（轻量级）

> **项目**：个人历史项目文档知识库 `pkb_sdd`  
> **版本基线**：V1.1-SDD  
> **适用阶段**：Phase 1 文件治理底座（003 起强制适用）  
> **目标**：缓解上下文变长、角色混乱、自我验收问题

---

## 1. 设计原则

1. **单 Spec、单主线、单写者**：同一时刻只有一个 Agent 角色持有「写权限」。
2. **SDD 先行**：没有 Spec / Plan / Tasks，不进入实现。
3. **原始文件只读**：任何 Agent 不得移动、删除、重命名、覆盖原始文件。
4. **raw_vault 真实产物不可触碰**：除 Dev 在测试隔离环境（`tmp_path`）外，不得修改生产 `raw_vault` 目录内容。
5. **越界即拒绝**：Tech Lead 对越界任务必须拒绝并缩小范围，不得「顺便实现」。

---

## 2. 角色核心职责（必读）

### 2.1 Tech Lead Agent（`TL`）

- **不写代码**。
- **只做**：范围判断、Plan、设计审查、**最终 Review**。
- **越界处理**：任务超出当前 Spec / Plan / tasks.md → **必须拒绝**，输出缩小后的可执行范围。

### 2.2 Dev Agent（`DEV`）

- **只按 Tech Lead 批准的文件白名单改代码**。
- **必须先读** `tasks.md`（再读 plan / spec / acceptance）。
- **不能**修改 SQL schema（含 `sql/001_init_schema_v1_1.sql`）。
- **不能**碰原始文件目录与 **raw_vault 真实产物**。

### 2.3 DB & Data Agent（`DB`）

- **只审查** SQL / ORM / 数据状态一致性。
- **不能直接改**业务代码（`backend/app/services/**` 等）。
- **必须指出**：幂等问题、数据污染问题、schema 偏差。

### 2.4 E2E QA Agent（`QA`）

- **只做**：测试设计、执行命令、验收表（A001–A006）。
- **必须检查**：原始文件只读、重复执行幂等、异常可恢复。
- **不修改**业务实现代码以「凑通过」。

### 2.5 Handoff Agent（`HO`）

- **只生成**阶段交接文档（`docs/handoff-*.md`）。
- **必须记录**：commit、测试结果、已完成项、未完成项、下一阶段入口条件。

---

## 3. 角色写权限一览

| 角色 | 代号 | 可写 | 禁止 |
|------|------|------|------|
| **Tech Lead** | `TL` | `specs/*/plan.md`、`specs/*/tasks.md`；Review 结论 | **任何代码**、`backend/**`、`sql/**`、替 QA 验收 |
| **Dev** | `DEV` | TL 白名单内 `backend/**`；`tasks.md` 勾选 | 白名单外文件、SQL schema、原始文件、raw_vault 真实产物、handoff、自我验收 |
| **DB & Data** | `DB` | 审查报告；TL 授权时 `sql/migrations/**` | **业务 Python**、Spec 正文、未授权 schema |
| **E2E QA** | `QA` | `backend/tests/**`（若 TL 授权）、验收记录 | `backend/app/services/**`、handoff、Plan |
| **Handoff** | `HO` | `docs/handoff-*.md` | 代码、Spec、SQL、pytest 代替 QA |

**唯一业务代码实现者**：`DEV`（且在 TL 白名单内）。

---

## 4. Spec 推进顺序（强制）

```text
① Tech Lead Plan        → plan.md / tasks.md / 文件白名单
② Dev Implementation    → 仅白名单；先读 tasks.md
③ DB Review             → 审查报告；不交还则阻断 QA
④ E2E QA                → 测试设计 + 执行 + 验收表
⑤ Handoff               → handoff 文档
⑥ Tech Lead Final Review → 是否可 merge；下一 Spec 入口
```

### 4.1 步骤门禁

| 步骤 | 进入条件 | 退出条件 |
|------|----------|----------|
| ① Plan | Spec 五件套已读 | plan 落地；tasks 可执行；**DEV 白名单已列出** |
| ② Dev | ① 完成 | 实现完成；仅改白名单文件 |
| ③ DB | ② 完成 | 通过，或修改清单交还 DEV |
| ④ QA | ③ 通过 | A001–A006 验收表有证据 |
| ⑤ Handoff | ④ 通过 | handoff 含 commit / 测试 / 完成度 / 下阶段入口 |
| ⑥ Final Review | ⑤ 完成 | TL 批准 merge 或开下一 Spec |

---

## 5. 全局禁止项

| # | 禁止 | 适用 |
|---|------|------|
| 1 | 多 Agent **同时改同一文件** | 全部 |
| 2 | 移动 / 删除 / 重命名 / 覆盖 **原始文件** | 全部 |
| 3 | 修改 **raw_vault 真实产物**（测试 `tmp_path` 除外） | DEV、QA |
| 4 | 未经 Spec + migration 授权改 **SQL schema** | DEV、DB |
| 5 | TL **越界任务不拒绝** | TL |
| 6 | DEV 未读 **tasks.md** 即写代码 | DEV |
| 7 | DEV 改 **白名单外** 文件 | DEV |
| 8 | DB **直接改** business code | DB |
| 9 | QA 改 service 以通过测试 | QA |
| 10 | HO 在 QA 未通过时写「可验收」 | HO |
| 11 | 非当前 Spec 范围（解析器 / 前端 / 向量库） | 全部 |

---

## 6. 文件锁与冲突

- 单文件单写者；下一角色开始前上一角色 STOP。
- 冲突由 **TL** 裁定；禁止 force push `main`。

---

## 7. SDD 与规则引用

- `.cursor/rules/000-project-rules.mdc` … `007-agent-collaboration.mdc`
- `docs/sdd_development_standard.md`
- `docs/role_prompts/*.md`

---

## 8. 会话启动模板

```text
当前角色：<TL|DEV|DB|QA|HO>
当前 Spec：specs/00N-*
当前分支：feature/00N-*
当前步骤：①–⑥
TL 批准的文件白名单：（DEV 必填）
禁止修改：（黑名单）
```

---

**文档结束**

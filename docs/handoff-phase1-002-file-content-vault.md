# 阶段交接文档：Phase 1 — 文件治理底座（002-file-content-vault）

> **项目**：个人历史项目文档知识库 `pkb_sdd`  
> **版本基线**：V1.1-SDD  
> **交接日期**：2026-06-15  
> **项目路径**：`/home/szf/dev/pyws/pkb_sdd`  
> **编写角色**：Tech Lead / Cursor 开发会话汇总  
> **前置文档**：`docs/handoff-phase1-001-inventory.md`

---

## 1. Executive Summary

本阶段在 **001-file-inventory** 已验收并 commit 的基础上，完成 **002-file-content-vault（唯一原文仓库 raw_vault）** MVP，并将稳定底座 merge 到 `main`，拉出 **003-duplicate-governance** 开发分支。

**E2E 最终结论（已确认）**：

> `specs/002-file-content-vault` **可以验收通过**。

**Phase 1 文件治理底座进度**：

```text
001-file-inventory       ✅ 已 merge 到 main（08e59ef）
002-file-content-vault   ✅ 已 merge 到 main（2f7eb46）
003-duplicate-governance ⬜ 下一 Spec（分支已建，未开始编码）
004–006 解析链           ⬜ 未开始
```

**当前最关键提醒（下一阶段仍适用）**：

| 不要做 | 原因 |
|--------|------|
| 接 MinerU / MarkItDown | 属于 004–006，解析链尚未开始 |
| Streamlit 前端 | 012 Spec，Phase 2 |
| 项目卡蒸馏 / curated | 010 Spec |
| 向量库 / embedding | 检索 Phase 2 |
| 扫描真实大目录 | 先用 fixtures / 小样本 |
| 在 `feature/002-*` 上继续做 003 | 003 应基于 `main` 稳定底座 |
| 自动删除 / 移动原始文件 | 全 Phase 1 硬性约束 |

**003 依赖的稳定底座（已在 main）**：

- `kb_file_instance` / `kb_file_content`（001）
- `raw_vault` 目录 + `kb_raw_vault_object`（002）
- CLI：`scan`、`copy-to-vault`
- pytest：001 7 + 002 7 = **14 passed**

---

## 2. 项目边界（必须遵守）

### 2.1 包含

- 历史项目 **文档** 资产：Office、PDF、图片、CSV/TXT 等
- 文件盘点、去重治理、raw_vault、解析、MySQL 元数据、证据链、curated 梳理

### 2.2 不包含

- 源代码（Java/Python/JS 等）分析
- 自动删除 / 移动 / 重命名原始文件
- 默认上传私有文档到外部云服务
- 企业级权限、多用户协同

### 2.3 核心概念

| 概念 | 含义 |
|------|------|
| `file_instance` | 物理路径上的一次文件出现 |
| `file_content` | SHA256 唯一内容对象 |
| `raw_vault` | 内容寻址的唯一原文副本仓库（002 写入） |
| `parsed` | 按 hash + parser_profile 的解析产物 |
| `curated` | 项目级梳理成果（不是原始文件搬家） |

### 2.4 SDD 开发流程

```text
Spec → Plan → Tasks → Code → Tests → Acceptance → Review → merge main → 下一 feature 分支
```

实现前必读：`.cursor/rules/*.mdc`、`docs/sdd_development_standard.md`、目标 Spec 五件套。

---

## 3. 环境就绪状态

### 3.1 目录与规范层（✅ 就绪）

| 类别 | 状态 | 说明 |
|------|------|------|
| `.cursor/rules/` | ✅ | 7 个规则文件完整 |
| `docs/` | ✅ | 规范文档 + 001/002 handoff |
| `specs/001`、`specs/002` | ✅ | 五件套完整；002 `plan.md` 已落地实现计划 |
| `specs/003` | ✅ | 五件套结构完整（内容偏模板） |
| `sql/001_init_schema_v1_1.sql` | ✅ | V1.1.0，002 未改 schema |
| `config/app.example.yaml` | ✅ | 配置模板 |
| `backend/app/` | ✅ | 001 + 002 实现齐全 |
| `backend/tests/fixtures/` | ✅ | 中文路径样本（2 个同内容 txt） |

### 3.2 Python 环境

```bash
cd /home/szf/dev/pyws/pkb_sdd/backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

- Python：**3.11+**（本机实测 3.12）
- **`backend/.venv/` 为本地 runtime，不得提交 GitHub**

### 3.3 MySQL

- 数据库：`personal_kb`
- Schema 版本：`v1.1.0`
- 用户：`personal_kb@localhost`（密码见本地 `config/app.yaml`，**勿提交**）

```bash
mysql -upersonal_kb -pmahound personal_kb
```

**交接时 DB 快照（仅供参考，pytest 会变动）**：

| 表 | 典型状态 | 说明 |
|----|----------|------|
| `kb_file_instance` | 0–2 行 | fixtures 扫描后 2 行；pytest teardown 可能清零 |
| `kb_file_content` | 1–3 行 | fixtures 1 行 + pytest 历史残留可能 |
| `kb_raw_vault_object` | 0–3 行 | 成功 COPIED + pytest ERROR 残留可能 |

> **不强制清理 MySQL** 即可开始 003；合并前可选清理 orphan 行（见 §6.2）。

### 3.4 存储目录

**推荐生产路径**（handoff 001 约定）：

```text
/home/szf/dev/data/personal-kb/
  source_registry/
  raw_vault/        ← 002 产物（推荐指向此处）
  parsed/
  curated/
  quarantine/
  reports/          ← 001 扫描报告 JSON
```

**当前本机 `config/app.yaml` 实际配置**：

| 键 | 当前值 | 说明 |
|----|--------|------|
| `raw_vault_root` | `./raw_vault` | 相对项目根，CLI E2E 已写入此处 |
| `reports_root` | `/home/szf/dev/data/personal-kb/reports` | 001 报告 |

接手 003 前建议统一 `raw_vault_root` 到 `/home/szf/dev/data/personal-kb/raw_vault`（本地 `app.yaml` 修改，不提交）。

### 3.5 Git 状态（✅ 已就绪）

| 项 | 状态 |
|----|------|
| `main` | `2f7eb46` — 含 001 + 002 |
| `feature/002-file-content-vault` | 已 merge（可保留或删除） |
| `feature/003-duplicate-governance` | **当前开发分支**，基于 `main` |
| 001 commit | `08e59ef feat(001): implement file inventory scanner` |
| 002 commit | `2f7eb46 feat(002): implement file content vault` |

**分支策略（已执行）**：

```text
feature/002-file-content-vault → merge → main
main → checkout -b → feature/003-duplicate-governance
```

不要在 `feature/002-*` 上继续 003。

---

## 4. specs/001-file-inventory 状态摘要

> 详情见 `docs/handoff-phase1-001-inventory.md` §4。

| 项 | 状态 |
|----|------|
| 验收 A001–A006 | ✅ |
| pytest | 7/7 |
| CLI | `scan --path` |
| Git | 已在 `main` |

**001 不提供、002/003 才涉及**：raw_vault 复制、`kb_duplicate_group` 治理。

---

## 5. specs/002-file-content-vault 实现摘要

### 5.1 功能目标

```text
查询 kb_file_content (NOT_COPIED)
  → 解析 master / fallback 复制源
  → 分块只读复制 → raw_vault/by_hash/{prefix}/{sha256}/
  → 写 original.bin + sidecar JSON
  → 更新 kb_file_content.vault_*
  → upsert kb_raw_vault_object
  → 幂等 / 单 content 失败不中断
```

### 5.2 实现文件

| 文件 | 职责 |
|------|------|
| `backend/app/core/vault_paths.py` | vault 路径构造、状态常量 |
| `backend/app/models/vault.py` | `KbRawVaultObject` ORM |
| `backend/app/services/file_content_vault.py` | 复制核心业务逻辑 |
| `backend/app/cli/main.py` | `copy-to-vault` 命令 |
| `backend/tests/test_file_content_vault.py` | 7 个 pytest 用例 |
| `backend/app/core/config.py` | 增加 `pipeline_version`（metadata JSON） |
| `specs/002-file-content-vault/plan.md` | 完整实现计划 |
| `specs/002-file-content-vault/tasks.md` | T001–T005 已 `[x]` |

### 5.3 关键设计决策

| 项 | 决策 |
|----|------|
| vault 目录 | `raw_vault/by_hash/{sha256[:2]}/{sha256}/` |
| 产物 | `original.bin`、`original_name.txt`、`source_paths.json`、`file_metadata.json` |
| UID | `vault_uid = content_uid = sha256` |
| 复制源 | `master_file_instance_uid` → fallback 首个可读 DISCOVERED instance |
| 幂等 | `original.bin` 存在且 hash 正确 → 跳过二进制复制，刷新 JSON + DB |
| 分块 | 1MB chunk 复制 + 1MB chunk SHA256 校验 |
| 002 不写 | `kb_duplicate_group`、parsed、curated、解析队列 |

### 5.4 CLI 用法

```bash
cd /home/szf/dev/pyws/pkb_sdd/backend
source .venv/bin/activate

# 完整 E2E（fixtures）
python -m app.cli.main scan --path backend/tests/fixtures
python -m app.cli.main copy-to-vault

# 可选参数
python -m app.cli.main copy-to-vault --limit 100
python -m app.cli.main copy-to-vault --sha256 <64hex>
python -m app.cli.main copy-to-vault --content-uid <64hex>
python -m app.cli.main copy-to-vault --refresh-metadata-only
```

**fixtures 首次 copy 预期**：

```text
Candidates: 1
Copied: 1
Skipped (already copied): 0
Metadata refreshed: 1
Errors: 0
```

**重复 copy（`--sha256` 指定同一 content）**：

```text
Copied: 0
Skipped (already copied): 1
```

### 5.5 测试

```bash
pytest -q tests/test_file_content_vault.py
pytest -q tests/test_inventory_scanner.py tests/test_file_content_vault.py
```

**交接时验收结果**：14 passed（001 7 + 002 7）

| 测试 | 场景 |
|------|------|
| `test_copy_normal_content` | 普通 content 复制 |
| `test_copy_idempotent` | 重复执行幂等 |
| `test_copy_chinese_master_path` | 中文 master 路径 |
| `test_copy_duplicate_instances_one_bin` | 多 instance 单 bin |
| `test_copy_source_missing_continues` | 单 content 失败不中断 |
| `test_original_files_unchanged` | 原始文件保护 |
| `test_copy_project_fixtures_integration` | scan → vault 集成 |

### 5.6 Acceptance 映射

| 编号 | 状态 | 说明 |
|------|------|------|
| A001 范围符合 | ✅ | 仅 vault + 两表 + CLI |
| A002 原始文件保护 | ✅ | 只读分块复制 |
| A003 幂等性 | ✅ | bin hash 正确则跳过 |
| A004 异常可恢复 | ✅ | 单 content ERROR 不中断 |
| A005 数据一致性 | ✅ | vault_path ↔ 磁盘 ↔ sha256 |
| A006 测试通过 | ✅ | pytest + CLI E2E |

### 5.7 sidecar JSON 契约（摘要）

**source_paths.json**：`content_uid`、`sha256`、`instance_count`、`master_file_instance_uid`、`instances[]`（含中文 `source_path`）

**file_metadata.json**：`content_uid`、`sha256`、`file_size`、`file_ext`、`mime_type`、`instance_count`、`master_*`、`vault_path`、`copy_source_path`、`vault_status`、`pipeline_version`、`copied_at`

---

## 6. 当前磁盘 / 数据状态

### 6.1 源码与 Git（✅ 正常）

| 检查项 | 状态 |
|--------|------|
| 001/002 源码 | ✅ 在 `main` 与工作区一致 |
| `specs/002/tasks.md` | ✅ 已勾选 |
| `specs/002/plan.md` | ✅ 完整实现计划 |
| pytest | ✅ 14 passed |

### 6.2 MySQL / 产物残留（⚠️ 可选清理）

pytest 可能在 DB 中留下 `/tmp/pytest-of-*` 相关行或 `COPY_ERROR` 的 `kb_raw_vault_object`。

**不影响 003 开发判定**；合并前可选执行：

```sql
-- 删除无 instance 引用的 content
DELETE FROM kb_file_content
WHERE sha256 NOT IN (
  SELECT DISTINCT sha256 FROM kb_file_instance WHERE sha256 IS NOT NULL
);

-- 删除 ERROR 状态的 vault_object（pytest 残留）
DELETE FROM kb_raw_vault_object WHERE copy_status = 'ERROR';
```

重新验证 fixtures 基线：

```bash
python -m app.cli.main scan --path backend/tests/fixtures
python -m app.cli.main copy-to-vault
```

### 6.3 raw_vault 产物位置

| 路径 | 说明 |
|------|------|
| `/home/szf/dev/pyws/pkb_sdd/raw_vault/` | 当前 `app.yaml` 默认写入位置 |
| `/home/szf/dev/data/personal-kb/raw_vault/` | 推荐生产位置（需改 app.yaml） |

**不得提交 Git**：`raw_vault/`、`.venv/`、`config/app.yaml`（已在 `.gitignore`）

---

## 7. 已解决的关键问题（002 会话）

### 7.1 DetachedInstanceError（001 恢复期）

- **现象**：scan 后 logging 访问已关闭 session 的 ORM 对象
- **解决**：commit 前缓存 `instance_uid` / `content_uid` 再 log

### 7.2 pytest 扫描 reports 目录

- **现象**：`reports/*.json` 被 scan 计入，破坏幂等测试
- **解决**：`SKIP_DIR_NAMES` 加入 `reports`

### 7.3 copy_to_vault 批处理污染

- **现象**：无 filter 时处理全库 NOT_COPIED，测试断言失真
- **解决**：测试隔离候选集；生产使用 `--limit` / `--sha256`

### 7.4 分支策略

- **决策**：002 merge `main` 后再建 `feature/003-duplicate-governance`，避免 003 依赖未合并代码

---

## 8. 下一阶段：003-duplicate-governance

### 8.1 目标

```text
识别重复 → 分组 (kb_duplicate_group) → 主文件建议 → 清理建议 → 人工确认
不允许自动删除
```

### 8.2 依赖（已在 main）

- 001：`is_duplicate_instance`、`master_file_instance_uid`、`instance_count`
- 002：`vault_path`、`kb_raw_vault_object`、raw_vault 原文副本

### 8.3 003 明确不做

- 自动删除 / 移动原始文件
- 解析器 / parsed / curated
- 002 已完成的 vault 复制逻辑（003 只读消费）

### 8.4 建议开发顺序

```text
1. 在 feature/003-duplicate-governance 输出 003 实现计划（不改代码）
2. 阅读 specs/003 五件套 + kb_duplicate_group schema
3. 实现 duplicate_detector service + CLI
4. pytest + fixtures 验证
5. merge main → 004-parser-router
```

---

## 9. 仓库与保密清单

### 9.1 不得提交 GitHub

```gitignore
backend/.venv/
.venv/
__pycache__/
.pytest_cache/
config/app.yaml
raw_vault/
reports/          # 若在本仓库相对路径下
```

### 9.2 应提交

- `backend/app/**/*.py`
- `backend/tests/**`
- `specs/**`（含 002 plan/tasks）
- `sql/**`
- `docs/handoff-*.md`
- `.gitignore`

---

## 10. 快速命令参考

```bash
# 环境
cd /home/szf/dev/pyws/pkb_sdd/backend && source .venv/bin/activate

# 测试（001 + 002）
pytest -q tests/test_inventory_scanner.py tests/test_file_content_vault.py

# 001 扫描
python -m app.cli.main scan --path backend/tests/fixtures

# 002 复制
python -m app.cli.main copy-to-vault

# 查库
mysql -upersonal_kb -pmahound personal_kb -e "
  SELECT file_name, is_duplicate_instance FROM kb_file_instance;
  SELECT sha256, vault_status, vault_path FROM kb_file_content;
  SELECT vault_uid, copy_status, original_name FROM kb_raw_vault_object;
"

# 查 vault 产物
ls -la ../raw_vault/by_hash/*/*

# 创建测试样本
bash ../scripts/create_sample_dataset.sh

# 分支
git checkout main
git checkout feature/003-duplicate-governance
```

---

## 11. 相关文档索引

| 文档 | 路径 |
|------|------|
| 001 交接 | `docs/handoff-phase1-001-inventory.md` |
| 002 交接 | `docs/handoff-phase1-002-file-content-vault.md`（本文） |
| 002 实现计划 | `specs/002-file-content-vault/plan.md` |
| 003 Spec | `specs/003-duplicate-governance/spec.md` |
| SDD 规范 | `docs/sdd_development_standard.md` |
| SQL 初始化 | `sql/001_init_schema_v1_1.sql` |
| Feature 索引 | `docs/feature_index.md` |

---

## 12. 交接确认清单

接手 003 前请逐项确认：

- [ ] 已阅读 `.cursor/rules/*.mdc` 与本文档
- [ ] 当前分支为 `feature/003-duplicate-governance`（基于 `main` @ `2f7eb46`）
- [ ] MySQL `personal_kb` 用户可连接
- [ ] 本地 `config/app.yaml` 已配置（未提交）
- [ ] pytest 001+002 全绿（14 passed）
- [ ] 理解 **003 之前不接解析器 / 前端 / 向量库**
- [ ] 理解 **002 不做 duplicate_group；003 才开始**
- [ ] 已阅读 `specs/003-duplicate-governance/spec.md` 准备下一迭代
- [ ] 不在 `feature/002-*` 上继续开发

---

**文档结束**

如有疑问，优先对照 `specs/002-file-content-vault/acceptance.md` 与 `specs/002-file-content-vault/plan.md`。

# 阶段交接文档：Phase 1 — 文件治理底座（001-file-inventory）

> **项目**：个人历史项目文档知识库 `pkb_sdd`  
> **版本基线**：V1.1-SDD  
> **交接日期**：2026-06-15  
> **项目路径**：`/home/szf/dev/pyws/pkb_sdd`  
> **编写角色**：Tech Lead / Cursor 开发会话汇总

---

## 1. Executive Summary

本阶段目标是在 **原始文件只读** 前提下，完成 **001-file-inventory（文件盘点与资产登记）** MVP，并为 **002-file-content-vault**、**003-duplicate-governance** 打下基础。

**E2E 最终结论（已确认）**：

> `specs/001-file-inventory` **可以验收通过**。

**当前最关键提醒（下一阶段仍适用）**：

| 不要做 | 原因 |
|--------|------|
| 接 MinerU / MarkItDown | 属于 004–006，解析链尚未开始 |
| Streamlit 前端 | 012 Spec，Phase 2 |
| 项目卡蒸馏 / curated | 010 Spec |
| 向量库 / embedding | 检索 Phase 2 |
| 扫描真实大目录 | 先用 fixtures / 小样本 |
| Codex 并行参与 | 避免范围失控 |

**下一阶段只做**：

```text
001-file-inventory     ✅ 逻辑验收通过（见 §6 磁盘状态警告）
002-file-content-vault ⬜ 下一 Spec
003-duplicate-governance ⬜ 第三 Spec
```

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
| `raw_vault` | 内容寻址的唯一原文副本仓库 |
| `parsed` | 按 hash + parser_profile 的解析产物 |
| `curated` | 项目级梳理成果（不是原始文件搬家） |

### 2.4 SDD 开发流程

```text
Spec → Plan → Tasks → Code → Tests → Acceptance → Review
```

实现前必读：`.cursor/rules/*.mdc`、`docs/sdd_development_standard.md`、目标 Spec 五件套。

---

## 3. 环境就绪状态

### 3.1 目录与规范层（✅ 就绪）

| 类别 | 状态 | 说明 |
|------|------|------|
| `.cursor/rules/` | ✅ | 7 个规则文件完整 |
| `docs/` | ✅ | 10 个规范文档完整 |
| `specs/000`–`008` | ✅ | 五件套结构完整（内容偏模板） |
| `sql/001_init_schema_v1_1.sql` | ✅ | V1.1.0 初始化脚本 |
| `config/app.example.yaml` | ✅ | 配置模板 |
| `config/parser_rules.yaml` 等 | ✅ | 解析/价值/质量规则模板 |
| `ai_tasks/` | ✅ | Cursor/Codex 任务模板 |
| `scripts/` | ✅ | init_db / create_sample_dataset / run_pipeline |

### 3.2 Python 环境

```bash
cd /home/szf/dev/pyws/pkb_sdd/backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

- Python：**3.11+**（本机实测 3.12）
- 依赖：`fastapi`、`SQLAlchemy`、`pymysql`、`typer`、`rich`、`pytest`、`PyYAML` 等
- **`backend/.venv/` 为本地 runtime，不得提交 GitHub**（见 §8）

### 3.3 MySQL

- 数据库：`personal_kb`
- Schema 版本：`v1.1.0`（`kb_schema_version`）
- 初始化：

```bash
sudo service mysql start
mysql -uroot -p < sql/001_init_schema_v1_1.sql
```

**重要：WSL 下 root 用户使用 `auth_socket`**

- OS 用户 `szf` **无法**用 `root` + 密码连接 MySQL
- 已创建专用用户（会话中完成，需在接手环境确认仍存在）：

```sql
CREATE USER IF NOT EXISTS 'personal_kb'@'localhost' IDENTIFIED BY 'mahound';
GRANT ALL PRIVILEGES ON personal_kb.* TO 'personal_kb'@'localhost';
FLUSH PRIVILEGES;
```

- **`config/app.yaml` 应使用 `username: personal_kb`**，不要用 `root`
- 本机交接时 DB 中已有 fixtures 扫描结果：`kb_file_instance` 2 行、`kb_file_content` 1 行

### 3.4 外部存储目录

```text
/home/szf/dev/data/personal-kb/
  source_registry/
  raw_vault/        ← 002 将写入
  parsed/
  curated/
  quarantine/
  reports/          ← 001 扫描报告 JSON
```

`app.yaml` 中 `storage.*_root` 应指向上述路径（从 `app.example.yaml` 复制后修改）。

### 3.5 Git 状态（⚠️ 需处理）

- 当前仓库仅 **1 个 commit**：`init: personal kb sdd cursor workspace`
- **001 实现代码尚未 commit**
- 可能存在 `dubious ownership` 警告，需在本机执行：

```bash
git config --global --add safe.directory /home/szf/dev/pyws/pkb_sdd
```

---

## 4. specs/001-file-inventory 实现摘要

### 4.1 功能目标

```text
扫描目录 → 识别文档候选 → source_path_hash → SHA256
  → kb_file_instance + kb_file_content
  → 同 SHA256 重复实例标记 → 幂等 → 写扫描报告
```

### 4.2 应存在的实现文件（001 MVP 最小闭环）

| 文件 | 职责 |
|------|------|
| `backend/app/core/config.py` | 加载 `app.yaml`；`ensure_readonly()` |
| `backend/app/core/database.py` | SQLAlchemy Engine/Session；WSL unix socket 处理 |
| `backend/app/core/ids.py` | 路径规范化、source_path_hash、分块 SHA256 |
| `backend/app/core/file_types.py` | 文档扩展名白名单、跳过目录 |
| `backend/app/models/file.py` | `KbFileInstance` / `KbFileContent` ORM |
| `backend/app/services/inventory_scanner.py` | 扫描核心业务逻辑 |
| `backend/app/cli/main.py` | `scan --path` Typer 命令 |
| `backend/tests/test_inventory_scanner.py` | 7 个 pytest 用例 |

### 4.3 关键设计决策

| 项 | 决策 |
|----|------|
| 路径身份 | `source_path_hash = SHA256(normalize(path).as_posix())` |
| 内容身份 | `sha256` 分块读取（1MB chunk） |
| UID | `file_instance_uid = source_path_hash`；`content_uid = sha256` |
| 幂等 | 按 `source_path_hash` / `sha256` upsert，不重复 INSERT |
| 重复标记 | 同 content 下最早 instance 为 master；其余 `is_duplicate_instance=1` |
| 001 不写 | `kb_duplicate_group`、raw_vault 复制、价值分层、解析队列 |

### 4.4 CLI 用法

```bash
cd /home/szf/dev/pyws/pkb_sdd/backend
source .venv/bin/activate

python -m app.cli.main scan --path /home/szf/dev/pyws/pkb_sdd/backend/tests/fixtures
```

可选参数：`--config`、`--source-root`

**首次扫描预期**（2 个同内容 txt）：

```text
Scanned files: 2
New instances: 2
New contents: 1
Duplicate instances: 1
Errors: 0
```

**查库**：

```bash
mysql -upersonal_kb -pmahound personal_kb -e "
  SELECT file_name, sha256, is_duplicate_instance FROM kb_file_instance;
"
```

### 4.5 测试

```bash
pytest -q tests/test_inventory_scanner.py
```

**会话中验收结果**：7 passed

| 测试 | 场景 |
|------|------|
| `test_scan_normal_files` | 普通文件 |
| `test_scan_idempotent` | 重复扫描幂等 |
| `test_scan_chinese_path` | 中文路径 |
| `test_scan_duplicate_content` | 同 SHA256 多路径 |
| `test_scan_single_file_error_continues` | 单文件失败不中断 |
| `test_original_files_unchanged` | 原始文件保护 |
| `test_scan_project_fixtures` | fixtures 集成 |

### 4.6 Acceptance 映射

| 编号 | 状态 | 说明 |
|------|------|------|
| A001 范围符合 | ✅ | 仅 001 范围 |
| A002 原始文件保护 | ✅ | 只读 scan/hash |
| A003 幂等性 | ✅ | source_path_hash 唯一 |
| A004 异常可恢复 | ✅ | 单文件 ERROR 不中断 |
| A005 数据一致性 | ✅ | instance ↔ content 一致 |
| A006 测试通过 | ✅ | E2E + pytest |

### 4.7 tasks.md 同步状态（会话中已完成，磁盘需核对）

T001–T003、T005 应全部 `[x]`；T004 Typer CLI `[x]`；FastAPI 项标注「001 不适用」。

### 4.8 后续迭代备忘（非阻塞 001 验收）

- 补 **TC004 扩展**：扫描目录不存在时的 CLI/服务行为（当前 TC004 覆盖单文件异常）
- 无需为 001 修改 Spec 或 README

---

## 5. 已解决的关键问题

### 5.1 MySQL root 无法用 szf 连接

- **现象**：`Access denied for user 'root'@'localhost' (1698)`
- **原因**：MySQL `root` 使用 `auth_socket`
- **解决**：创建 `personal_kb` 用户；`app.yaml` 改用该用户

### 5.2 pytest 污染生产库

- **现象**：`kb_file_instance` 出现大量 `/tmp/pytest-of-*` 行，手工查库困惑
- **解决**：测试模块增加 session/teardown 清理 pytest 临时路径数据

### 5.3 duplicate_instances 指标重复累加

- **现象**：重复扫描 fixtures 时 Duplicate instances 显示 2 而非 1
- **解决**：扫描结束时按 DB 统计前缀下 `is_duplicate_instance=1` 的数量

### 5.4 backend/.venv 不应提交

- 根目录应添加 `.gitignore`，排除 `backend/.venv/`、`config/app.yaml` 等

---

## 6. ⚠️ 当前磁盘状态警告（接手必读）

**交接扫描时间**：2026-06-15

会话中 **001 E2E 已通过**，且 MySQL / reports 留有成功扫描痕迹，但 **工作区源码可能已回退**：

| 检查项 | 预期（001 完成后） | 交接时磁盘状态 |
|--------|-------------------|----------------|
| `backend/app/core/config.py` 等 6 个 core/models/services 源文件 | 存在 | **缺失**（仅 `__pycache__/*.pyc` 残留） |
| `backend/app/cli/main.py` | 完整 scan 实现 | **回退为 placeholder** |
| `backend/tests/test_inventory_scanner.py` | 存在 | **缺失** |
| `backend/tests/fixtures/中文路径/...` | 存在 | **缺失** |
| `config/app.yaml` | 存在 | **缺失**（仅 `app.example.yaml`） |
| 根目录 `.gitignore` | 存在 | **缺失** |
| `specs/001-file-inventory/tasks.md` 勾选 | 已同步 | **仍为未勾选** |
| Git commit | 含 001 feat | **仅 init commit** |

**残留证据（证明 001 曾运行成功）**：

- MySQL：`kb_file_instance` 2 行、`kb_file_content` 1 行（fixtures 路径）
- Reports：`/home/szf/dev/data/personal-kb/reports/inventory_scan_*.json`
- `__pycache__`：`config.cpython-312.pyc`、`inventory_scanner.cpython-312.pyc` 等

### 6.1 接手人第一步建议

**优先级 P0**：恢复 001 源码并提交 Git，再开始 002。

可选路径：

1. **从 Git 恢复**（若其他分支/机器已 commit）
2. **从 Cursor 会话 / 备份恢复** 8 个实现文件 + `app.yaml` + `.gitignore` + fixtures + tasks.md
3. **按本文件 §4 重新实现** 001 最小闭环（预计 1 个会话）

恢复后验证清单：

```bash
pytest -q tests/test_inventory_scanner.py
python -m app.cli.main scan --path backend/tests/fixtures
git add .gitignore backend/app backend/tests config/app.example.yaml
git status   # 确认无 backend/.venv
git commit -m "feat(001): implement file inventory scanner"
```

---

## 7. 下一阶段：002-file-content-vault

### 7.1 目标

同一 SHA256 **只复制一份**到 `raw_vault`：

```text
raw_vault/by_hash/{sha256_prefix}/{sha256}/
  original.bin
  original_name.txt
  source_paths.json
  file_metadata.json
```

### 7.2 涉及表

- `kb_file_content`：`vault_path`、`vault_status`
- `kb_raw_vault_object`

### 7.3 约束（继承 001）

- **原始目录文件仍不动**；raw_vault 是额外副本
- 幂等：同 content 已复制则跳过
- 先读 `specs/002-file-content-vault/` 五件套 + `sql/001_init_schema_v1_1.sql`

### 7.4 建议开发顺序

```text
1. 输出 002 实现计划（不改代码）
2. 分支 feature/002-file-content-vault
3. 实现 file_content_vault service + CLI
4. pytest + 手工验证
5. 验收后进入 003-duplicate-governance
```

---

## 8. 仓库与保密清单

### 8.1 不得提交 GitHub

```gitignore
backend/.venv/
.venv/
__pycache__/
.pytest_cache/
config/app.yaml          # 含数据库密码
```

### 8.2 应提交

- `config/app.example.yaml`
- `backend/app/**/*.py`（001 实现）
- `backend/tests/**`
- `specs/**`
- `sql/**`
- `.gitignore`

若 `backend/.venv` 曾被 `git add`，执行：

```bash
git rm -r --cached backend/.venv
```

---

## 9. 快速命令参考

```bash
# 环境
cd /home/szf/dev/pyws/pkb_sdd/backend && source .venv/bin/activate

# 测试
pytest -q tests/test_inventory_scanner.py

# 扫描
python -m app.cli.main scan --path backend/tests/fixtures

# 创建测试样本
bash scripts/create_sample_dataset.sh

# MySQL
mysql -upersonal_kb -pmahound personal_kb

# 健康检查 API（占位）
uvicorn app.main:app --reload   # GET /health
```

---

## 10. 相关文档索引

| 文档 | 路径 |
|------|------|
| 项目说明 | `README.md` |
| SDD 规范 | `docs/sdd_development_standard.md` |
| 数据库规范 | `docs/database_standard.md` |
| 编码规范 | `docs/coding_standard.md` |
| 001 Spec | `specs/001-file-inventory/spec.md` |
| 002 Spec | `specs/002-file-content-vault/spec.md` |
| 003 Spec | `specs/003-duplicate-governance/spec.md` |
| Feature 索引 | `docs/feature_index.md` |
| SQL 初始化 | `sql/001_init_schema_v1_1.sql` |

---

## 11. 交接确认清单

接手人请逐项确认：

- [ ] 已阅读 `.cursor/rules/*.mdc` 与本文档
- [ ] MySQL `personal_kb` 用户可连接
- [ ] 已从 `app.example.yaml` 创建本地 `config/app.yaml`
- [ ] 001 源码已恢复且 pytest 全绿
- [ ] `.gitignore` 已添加，`backend/.venv` 未跟踪
- [ ] 001 已 commit，分支策略明确（如 `feature/001-file-inventory` → `main`）
- [ ] 理解 **002 之前不接解析器/前端/向量库**
- [ ] 已阅读 `specs/002-file-content-vault/spec.md` 准备下一迭代

---

**文档结束**

如有疑问，优先对照 `specs/001-file-inventory/acceptance.md` 与本文 §6 磁盘状态警告。

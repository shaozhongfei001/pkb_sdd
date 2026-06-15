# Plan: 唯一原文仓库 raw_vault（002 实现计划）

> **项目**：个人历史项目文档知识库 `pkb_sdd`  
> **版本基线**：V1.1-SDD  
> **编写日期**：2026-06-15  
> **前置条件**：001-file-inventory 已 commit；A001–A006 已通过  
> **编写角色**：Tech Lead / 002 实现计划

---

## 0. 摘要

002 在 **原始文件只读** 前提下，基于 001 写入的 `kb_file_content` / `kb_file_instance`，将每个唯一 `sha256` 的原文 **额外复制一份** 到内容寻址目录 `raw_vault`，并更新 MySQL 元数据。

**不做**：解析、OCR、MinerU、MarkItDown、parsed、curated、duplicate_group、前端、向量库、项目蒸馏。

---

## 1. 当前 002 的输入

### 1.1 数据输入（MySQL）

| 来源 | 用途 |
|------|------|
| **`kb_file_content`** | 待复制内容列表；关键字段：`content_uid`、`sha256`、`vault_status`、`vault_path`、`master_file_instance_uid`、`instance_count`、`file_size`、`file_ext`、`mime_type` |
| **`kb_file_instance`** | 构建 `source_paths.json`；按 `content_uid` / `sha256` 关联；含 `source_path`、`file_name`、`is_duplicate_instance`、`source_root`、`status` |

**默认选取条件**：

```text
vault_status = 'NOT_COPIED'
AND status = 'CONTENT_REGISTERED'（可选过滤）
AND sha256 IS NOT NULL
```

可选 CLI 过滤：`--sha256`、`--content-uid`、`--limit`。

### 1.2 文件输入（只读）

- **复制源**：`master_file_instance_uid` 对应 instance 的 `source_path`
- 若 master 不可用（路径不存在 / 无读权限 / `status=ERROR`），**fallback** 到同 `sha256` 下第一个 `status=DISCOVERED` 且可读的 instance；仍失败则记 ERROR，继续下一条 content

### 1.3 配置输入

| 配置项 | 来源 |
|--------|------|
| `storage.raw_vault_root` | `config/app.yaml` |
| `raw.original_files_readonly` | 必须为 `true`（复用 `ensure_readonly()`） |
| `app.pipeline_version` | 写入 `file_metadata.json`（可选） |

### 1.4 001 已提供、002 直接复用的能力

- `AppConfig` / `load_config` / `ensure_readonly`
- `create_db_engine` / `session_factory`
- `compute_sha256`（分块验证 `original.bin`）
- `normalize_path`
- `KbFileContent` / `KbFileInstance` ORM

---

## 2. 当前 002 的输出

### 2.1 磁盘产物（每个唯一 `sha256` 一套）

```text
{raw_vault_root}/by_hash/{sha256[:2]}/{sha256}/
  original.bin           # 内容副本（从 master 源只读复制）
  original_name.txt      # master instance 的 file_name
  source_paths.json      # 该 content 的全部 instance 路径清单
  file_metadata.json     # 内容级元数据
```

### 2.2 数据库更新

| 表 | 更新 |
|----|------|
| **`kb_file_content`** | `vault_path`、`vault_status`（`COPIED` / `COPY_ERROR`） |
| **`kb_raw_vault_object`** | upsert：`vault_uid`、`content_uid`、`sha256`、`vault_path`、sidecar 路径、`copy_status`、`copied_at`、`error_message` |

### 2.3 CLI 汇总输出（Rich echo）

```text
Candidates: N
Copied: N
Skipped (already copied): N
Metadata refreshed: N
Errors: N
```

### 2.4 可选（非验收阻塞）

- `reports/vault_copy_{timestamp}.json` — 与 001 scan report 对齐，便于运维；Spec 未强制

---

## 3. 需要新增或修改的文件

| 操作 | 文件 |
|------|------|
| **新增** | `backend/app/services/file_content_vault.py` |
| **新增** | `backend/app/models/vault.py`（或扩展现有 `models/file.py`） |
| **新增** | `backend/app/core/vault_paths.py`（vault 路径构造 + 常量，推荐） |
| **修改** | `backend/app/cli/main.py`（新增 vault 命令） |
| **新增** | `backend/tests/test_file_content_vault.py` |
| **实现后修改** | `specs/002-file-content-vault/tasks.md`（勾选） |

**不修改**：`sql/001_init_schema_v1_1.sql`、`inventory_scanner.py`（001 行为）、`specs/003+`、`README.md`、`docs/**`

---

## 4. 每个文件的职责

### 4.1 `backend/app/core/vault_paths.py`（推荐新增）

- 常量：`VAULT_NOT_COPIED`、`VAULT_COPIED`、`VAULT_COPY_ERROR`；`COPY_PENDING`、`COPY_COPIED`、`COPY_ERROR`
- `build_vault_dir(raw_vault_root, sha256) -> Path`
- `build_vault_artifact_paths(vault_dir) -> dict`（四个产物路径）
- `vault_uid_for(sha256) -> str`（建议 `vault_uid = sha256 = content_uid`）

### 4.2 `backend/app/models/vault.py`（或并入 `file.py`）

- `KbRawVaultObject` → `kb_raw_vault_object`，字段与 SQL 一一对应，不发明字段

### 4.3 `backend/app/services/file_content_vault.py`

核心服务 `FileContentVaultService`：

1. 查询待处理 `kb_file_content`
2. 加载关联 `kb_file_instance` 列表
3. 解析 master 复制源路径
4. 幂等判断 → 复制 / 跳过 / 修复
5. 分块复制 → `original.bin`；写 sidecar JSON
6. 复制后 SHA256 校验
7. upsert `kb_raw_vault_object`；更新 `kb_file_content`
8. 单 content 失败不中断批处理
9. 返回 `VaultCopyResult` 汇总

### 4.4 `backend/app/cli/main.py`（修改）

- 新增 Typer 命令（建议名：`copy-to-vault`）
- 加载 config → `ensure_readonly()` → 调用 service → 打印汇总
- 保留 `scan`；`build-parse-queue` / `parse` 仍为 placeholder

### 4.5 `backend/tests/test_file_content_vault.py`

- 7 个左右用例（见 §12）
- 测试 config 将 `raw_vault_root` 指向 `tmp_path`（不污染生产 vault）
- teardown 清理测试 vault 目录 + 测试 DB 行

---

## 5. 数据库表和字段

### 5.1 `kb_file_content`（读 + 写）

| 字段 | 002 用法 |
|------|----------|
| `content_uid` | 主键身份；`= sha256` |
| `sha256` | 目录命名、校验 |
| `file_size` / `file_ext` / `mime_type` | 写入 `file_metadata.json` |
| `master_file_instance_uid` | 定位复制源 |
| `instance_count` | 写入 JSON |
| `vault_path` | **写**：vault 目录绝对路径 |
| `vault_status` | **写**：`NOT_COPIED` → `COPIED` / `COPY_ERROR` |
| `status` | 读；过滤非 `CONTENT_REGISTERED` 可选 |

**不写**：`value_*`、`parse_status`、`quality_status`、`metadata`

### 5.2 `kb_file_instance`（读为主）

| 字段 | 002 用法 |
|------|----------|
| `file_instance_uid` | `source_paths.json` |
| `source_path` | 复制源 + JSON |
| `file_name` | `original_name.txt`（取 master） |
| `file_ext` / `file_size` / `mime_type` | JSON 补充 |
| `content_uid` / `sha256` | 关联 content |
| `source_root` | JSON |
| `is_duplicate_instance` | JSON |
| `status` | 选复制源 / JSON |

**不写** `kb_file_instance`（002 不改 instance 表）

### 5.3 `kb_raw_vault_object`（upsert）

| 字段 | 002 用法 |
|------|----------|
| `vault_uid` | `= sha256`（64 hex，UNIQUE） |
| `content_uid` | `= sha256` |
| `sha256` | 内容 hash |
| `vault_path` | vault 目录路径 |
| `original_name` | master `file_name` |
| `source_paths_json_path` | sidecar 绝对路径 |
| `file_metadata_json_path` | sidecar 绝对路径 |
| `copy_status` | `PENDING` → `COPIED` / `ERROR` |
| `copied_at` | 成功时间 UTC |
| `error_message` | 失败原因 |

**SQL 与需求对齐**：无 schema 差异，**不需要 migration**。

---

## 6. raw_vault 目录结构

```text
{raw_vault_root}/
  by_hash/
    {sha256[0:2]}/          # 例如 "53"
      {sha256}/             # 完整 64 位 hex
        original.bin
        original_name.txt
        source_paths.json
        file_metadata.json
```

**规则**：

- `sha256_prefix = sha256[:2]`（小写 hex，与 001 一致）
- 目录由程序 `mkdir(parents=True, exist_ok=True)` 创建
- **只写 raw_vault**；不碰原始目录、`parsed/`、`curated/`
- 同一 `sha256` 全局唯一目录；多 instance 共享一套 vault 产物

**示例**（fixtures）：

```text
/home/szf/dev/data/personal-kb/raw_vault/by_hash/53/53698599.../
  original.bin
  original_name.txt
  source_paths.json
  file_metadata.json
```

---

## 7. source_paths.json 字段设计

```json
{
  "content_uid": "536985990c2e2203a74c297bf66c7939873e53647bb41fb9cc72bb42bd6463d6",
  "sha256": "536985990c2e2203a74c297bf66c7939873e53647bb41fb9cc72bb42bd6463d6",
  "instance_count": 2,
  "master_file_instance_uid": "<source_path_hash of master>",
  "generated_at": "2026-06-15T12:00:00Z",
  "instances": [
    {
      "file_instance_uid": "...",
      "source_path": "/home/szf/.../方案.txt",
      "file_name": "方案.txt",
      "file_ext": ".txt",
      "source_root": "/home/szf/.../fixtures",
      "is_duplicate_instance": 0,
      "status": "DISCOVERED"
    },
    {
      "file_instance_uid": "...",
      "source_path": "/home/szf/.../方案副本.txt",
      "file_name": "方案副本.txt",
      "file_ext": ".txt",
      "source_root": "/home/szf/.../fixtures",
      "is_duplicate_instance": 1,
      "status": "DISCOVERED"
    }
  ]
}
```

**说明**：

- 每次 vault 运行 **重写**（反映最新 instance 列表；001 新增路径后重跑会更新）
- 幂等复制：`original.bin` 已存在且 hash 正确则 **不重拷**，但可刷新 JSON
- UTF-8 + `ensure_ascii=False`（支持中文路径）

---

## 8. file_metadata.json 字段设计

```json
{
  "content_uid": "53698599...",
  "sha256": "53698599...",
  "file_size": 19,
  "file_ext": ".txt",
  "mime_type": "text/plain",
  "instance_count": 2,
  "master_file_instance_uid": "...",
  "master_source_path": "/home/szf/.../方案.txt",
  "master_file_name": "方案.txt",
  "vault_path": "/home/szf/dev/data/personal-kb/raw_vault/by_hash/53/53698599...",
  "copy_source_path": "/home/szf/.../方案.txt",
  "vault_status": "COPIED",
  "pipeline_version": "v1.1",
  "copied_at": "2026-06-15T12:00:00Z"
}
```

**说明**：

- `copy_source_path`：实际用于复制的路径（可能与 master 相同；fallback 时不同）
- 复制完成后对 `original.bin` 做 SHA256 校验，不一致 → `COPY_ERROR`

---

## 9. 幂等逻辑

```text
对每个 content (sha256):
  1. vault_dir = build_vault_dir(raw_vault_root, sha256)
  2. bin_path = vault_dir / "original.bin"

  3. 若 bin_path 存在:
       actual_hash = compute_sha256(bin_path)
       若 actual_hash == sha256:
         → 跳过二进制复制 (skipped_copy)
         → 仍刷新 source_paths.json / file_metadata.json / original_name.txt
         → upsert kb_raw_vault_object (copy_status=COPIED)
         → 更新 kb_file_content.vault_status=COPIED, vault_path=vault_dir
         → return

  4. 若 vault_status=COPIED 但 bin 缺失或 hash 不匹配:
       → 视为需修复，重新复制（不删旧目录，覆盖 original.bin）

  5. 否则:
       mkdir vault_dir
       分块只读复制 source → original.bin
       校验 hash
       写 sidecar 文件
       upsert DB

  6. kb_raw_vault_object upsert 键: content_uid 或 sha256 (UNIQUE)
```

**保证**：

- 同一 `sha256` 不产生第二套目录
- 重复 CLI 运行：`Copied=0, Skipped=N`（bin 已正确）
- 001 重复 scan 新增 instance 后：bin 不重拷，JSON 刷新
- **不覆盖原始文件**；仅写 raw_vault

---

## 10. 异常处理

| 场景 | 处理 |
|------|------|
| **master 源不存在** | fallback 其他 DISCOVERED instance；全失败 → `vault_status=COPY_ERROR`，`copy_status=ERROR`，记 `error_message`，继续下一个 content |
| **源无读权限** | 同上 |
| **复制 IO 错误** | 单 content 事务 rollback；记 ERROR；继续批处理 |
| **复制后 hash 不匹配** | 不标 COPIED；`COPY_ERROR`；保留 bin 供排查或下次覆盖 |
| **DB 写入失败** | 当前 content rollback；已写文件不主动删（可重试修复） |
| **vault_dir 无写权限** | 记 ERROR，继续 |
| **无待处理 content** | 正常退出，Candidates=0 |
| **instance 列表为空** | ERROR（数据不一致） |

**原则**（对齐 001 + plan 异常策略）：

- 单 content 独立 try/except + session
- 不 silent swallow；`logger.exception` + 汇总 `errors[]`
- 失败可重跑（状态仍为 `NOT_COPIED` / `COPY_ERROR`）

---

## 11. CLI 命令设计

### 11.1 命令

```bash
cd /home/szf/dev/pyws/pkb_sdd/backend
source .venv/bin/activate

python -m app.cli.main copy-to-vault \
  [--config /path/to/app.yaml] \
  [--limit 100] \
  [--sha256 <64hex>] \
  [--content-uid <64hex>] \
  [--refresh-metadata-only]
```

### 11.2 参数

| 参数 | 说明 |
|------|------|
| `--config` | 默认 `config/app.yaml` |
| `--limit` | 最多处理 N 条（默认无限制或 1000） |
| `--sha256` | 仅处理指定 content |
| `--content-uid` | 同 `--sha256`（001 中二者相等） |
| `--refresh-metadata-only` | 仅刷新 JSON，不复制 bin（bin 已存在且 hash 正确时） |

### 11.3 典型 E2E 流程

```bash
# 1. 001 扫描
python -m app.cli.main scan --path backend/tests/fixtures

# 2. 002 复制
python -m app.cli.main copy-to-vault

# 3. 验证
ls /home/szf/dev/data/personal-kb/raw_vault/by_hash/*/*
mysql -upersonal_kb -pmahound personal_kb -e "
  SELECT sha256, vault_status, vault_path FROM kb_file_content;
  SELECT vault_uid, copy_status, original_name FROM kb_raw_vault_object;
"
```

---

## 12. pytest 测试设计

| # | 函数名 | TC | 场景 | 断言要点 |
|---|--------|-----|------|----------|
| 1 | `test_copy_normal_content` | TC001 | tmp_path 扫描 + vault | 四套文件存在；DB `vault_status=COPIED`；`kb_raw_vault_object` 1 行 |
| 2 | `test_copy_idempotent` | TC002 | 连续两次 copy | 第二次 `Copied=0`；DB 行数不变；bin hash 不变 |
| 3 | `test_copy_chinese_master_path` | TC003 | master 在中文路径 | `original_name.txt` 含中文；JSON 路径正确 |
| 4 | `test_copy_duplicate_instances_one_bin` | — | 2 instance 同 sha256 | 仅 1 个 vault 目录；`source_paths.json` 含 2 条 |
| 5 | `test_copy_source_missing_continues` | TC004 | 1 有效 + 1 无效 content | 有效成功；无效 ERROR；批处理不中断 |
| 6 | `test_original_files_unchanged` | TC005 | copy 前后 stat + hash | 原始文件不变 |
| 7 | `test_copy_project_fixtures_integration` | TC001 | fixtures scan → vault | 与 CLI E2E 一致 |

**测试基础设施**：

- fixture：临时 `raw_vault_root` + MySQL（复用 001 模式）
- 先调 `InventoryScanner.scan()` 再 `FileContentVaultService.copy()`
- teardown：删测试 vault 目录 + 清理测试 content/vault_object 行
- 不依赖外网；覆盖中文路径

**运行**：

```bash
pytest -q tests/test_file_content_vault.py
```

---

## 13. 本阶段明确不做

| 不做 | 原因 |
|------|------|
| **003 duplicate_group** | 下一 Spec |
| **004–006 解析**（MinerU / MarkItDown / router） | 解析链未开始 |
| **parsed / curated / quarantine 写入** | 非 002 范围 |
| **修改原始文件** | A002 |
| **修改 SQL schema** | 无字段缺口 |
| **FastAPI vault 路由** | 批处理走 CLI |
| **价值分层 / parse_status** | 001/002 均不写 |
| **自动删除 vault 旧副本** | 幂等跳过，不删 |
| **Streamlit / 向量库 / 项目蒸馏** | Phase 2+ |
| **OCR / 转码 / 改内容** | 原样复制 bytes |
| **修改 `inventory_scanner.py`** | 001 已封闭 |

---

## 14. 验收标准对应 acceptance.md

| 编号 | 002 实现如何满足 | 验证方式 |
|------|------------------|----------|
| **A001 范围符合** | 仅 vault 复制 + sidecar + 两表更新 + CLI + pytest | 代码 review；无 parser/frontend 依赖 |
| **A002 原始文件保护** | 源文件只读 open + 分块 copy；不写源路径 | `test_original_files_unchanged`；copy 前后 stat/hash |
| **A003 幂等性** | bin 存在且 hash 正确则跳过复制；DB upsert 不重复 INSERT | `test_copy_idempotent`；重复 CLI |
| **A004 异常可恢复** | 单 content 失败记 ERROR，继续批处理 | `test_copy_source_missing_continues` |
| **A005 数据一致性** | `vault_path` ↔ 磁盘目录；`sha256` ↔ `original.bin` hash；`kb_raw_vault_object.content_uid` ↔ `kb_file_content` | 集成测试 + MySQL + `ls` 对照 |
| **A006 测试通过** | `test_file_content_vault.py` 全绿 + CLI E2E | `pytest` + 手工 `copy-to-vault` |

---

## 15. 建议实现顺序

```text
1. 分支 feature/002-file-content-vault
2. core/vault_paths.py + models/vault.py
3. services/file_content_vault.py
4. cli/main.py 接入 copy-to-vault
5. tests/test_file_content_vault.py
6. pytest + CLI E2E（fixtures）
7. 更新 specs/002-file-content-vault/tasks.md
8. commit feat(002): implement file content vault
9. 进入 003-duplicate-governance
```

---

## 16. 001 → 002 衔接要点

- 002 **只读** 001 产物（DB + 原始路径），在 `raw_vault_root` **额外** 建副本
- `vault_status` 从 `NOT_COPIED` 流转到 `COPIED` 即标志 002 对该 content 完成
- 原始目录文件 **始终不动**；raw_vault 是独立的内容寻址仓库

---

**文档结束**

实现前另读：`spec.md`、`tasks.md`、`acceptance.md`、`test_cases.md`、`sql/001_init_schema_v1_1.sql`、`.cursor/rules/*.mdc`。

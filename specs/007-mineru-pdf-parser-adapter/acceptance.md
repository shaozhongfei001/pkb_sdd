# Acceptance: MinerU PDF Parser Adapter（007）

> **Spec**：`specs/007-mineru-pdf-parser-adapter`  
> **Plan 对照**：`plan.md` §10、§14、§16  
> **测试对照**：`test_cases.md`

---

## A001 范围符合 — 只处理 PDF route_type

007 只解析 **`PDF_DIGITAL`** 与 **`PDF_SCANNED_OR_IMAGE`**（且 `decision=ROUTE`）。

- 存在 MinerU adapter + service + CLI `parse-mineru-pdf`
- 不是通用 OCR 框架
- `build-parse-queue`、`parse` 保持 placeholder

## A002 跳过非 PDF route_type

以下 **不得**调用 MinerU，须 **SKIPPED** 并写入 report：

- `DOCX`、`PPTX`、`XLSX`、`TEXT_OR_MARKDOWN`
- `IMAGE`、`UNKNOWN`、`UNSUPPORTED`

## A003 parsed 产物路径正确

每个成功解析的 content，必选三文件位于：

```text
{parsed_root}/by_hash/{sha256[0:2]}/{sha256[2:4]}/{sha256}/
  parsed_text.md
  parsed_metadata.json
  parse_manifest.json
```

路径须经 `build_parsed_content_dir()` + `build_parsed_artifact_paths()`。

## A004 manifest 可追溯

`parse_manifest.json` 必须含：

- `content_uid`、`sha256`、`source_vault_path`
- `route_type`、`parser_name=mineru`、`parser_adapter_version=007_mvp_v1`
- `parsed_text_path`、`parsed_metadata_path`、`generated_at`、`status`
- 若存在 assets：`assets_dir`

## A005 raw_vault 不变 — 002 两档路径

执行 parse 前后：

- `raw_vault/**` 目录 listing 不变
- 每个 `original.bin` SHA256 不变
- 无 create/delete/overwrite/truncate raw_vault 文件
- **禁止** raw_vault 三档路径
- **禁止**修改 `backend/app/core/vault_paths.py`

## A005b raw_vault 路径解析权威

`original.bin` 路径 **必须**通过 002 helpers 得到：

```text
build_vault_dir(raw_vault_root, sha256)
build_vault_artifact_paths(vault_dir)["original_bin"]
```

## A006 原始用户文件不变

执行 parse 前后，用户原始 fixture 文件 stat / 内容 hash 不变。

- CLI 入口调用 `ensure_readonly()`
- 007 不以 `source_path` 作为解析输入

## A007 默认不写 DB

007 **默认**（无 `--register`）对 MySQL **仅 SELECT**。

- **禁止** INSERT/UPDATE/DELETE
- pytest `test_no_db_write` 证据

## A008 不改 SQL schema

007 实现前后：

- 无新增 migration
- 无 init SQL 修改
- 无 ORM 新表

## A009 不写 curated / 向量库 / 项目卡

- 无 `curated/` 写入
- 无 embedding / vector DB 代码路径
- 无 project card distillation

## A010 不修改 005 封闭逻辑

- `markitdown_parser.py` / `markitdown_adapter.py` 不在 007 diff 中
- `parse-markitdown` 行为回归通过

## A011 MinerU 依赖可选 — 缺失时清晰失败

- 非 dry-run：MinerU / `magic-pdf` 不可用 → CLI exit 1
- `error.code=DEPENDENCY_MISSING` 或等价消息
- 不 partial write parsed

## A012 单条失败不中断批处理

- 损坏 PDF / 超时 / runtime 错误 → 该条 FAILED + `errors[]`
- 其余 content 继续处理

## A013 empty output 有明确状态

- MinerU 返回空文本 → manifest `status=EMPTY`；`empty_count++`

## A014 错误状态可记录

FAILED manifest 含 `error.code` + `error.message`：

- `MISSING_ORIGINAL_BIN`、`TIMEOUT`、`CORRUPTED_DOCUMENT`、`PASSWORD_PROTECTED`、`PARSER_RUNTIME_ERROR` 等

## A015 CLI 护栏与 dry-run

- 无 filter → exit 1
- `--limit > 100` → exit 1
- `--dry-run`：不调用 MinerU；不写 parsed；不写 DB

## A016 幂等可测

- 连续两次 parse 同 PDF（无 `--force`）→ 第二次 skip
- `--force` → 覆盖 007 SUCCESS 产物

## A017 assets 策略（若 MinerU 产出）

- 图片 / 表格等资源复制到 `{parsed_dir}/assets/`
- temp MinerU 原始目录 **不**持久化到 parsed
- `parsed_metadata.json` 或 manifest 可索引 assets

## A018 可选 registry（`--register`）

- `--register` 且非 dry-run：调用 `ParseRegistryService.register_parse_report`
- 写入 run / result / artifact（及 bridge，若 P2 批准）
- `--dry-run` + `--register`：零 DB 写
- 007 report `dry_run=true` 不得被 register（M3）

## A019 测试通过

- 007 专项 pytest ≥ **30** functions，全部通过
- 全量回归（含 005 / 006）通过

## A020 scope 未膨胀

- 无 IMAGE 独立解析
- 无 OCR 大扩展
- 无 Streamlit
- 无修改 004 router 规则
- grep 无 curated / vector / embedding 越界

---

## 验收结论模板（QA 填写）

| 编号 | 标准 | 结论 |
|------|------|------|
| A001 | PDF in-scope only | |
| A002 | 非 PDF skip | |
| A003 | parsed 三档路径 | |
| A004 | manifest 可追溯 | |
| A005 | raw_vault 不变 | |
| A005b | vault helpers | |
| A006 | 原始文件不变 | |
| A007 | 默认不写 DB | |
| A008 | 无 schema 变更 | |
| A009 | 无 curated/vector/项目卡 | |
| A010 | 005 封闭 | |
| A011 | MinerU 缺失失败 | |
| A012 | 错误隔离 | |
| A013 | EMPTY 状态 | |
| A014 | 错误记录 | |
| A015 | CLI / dry-run | |
| A016 | 幂等 / force | |
| A017 | assets | |
| A018 | registry opt-in | |
| A019 | 测试通过 | |
| A020 | scope 未膨胀 | |

---

**Acceptance 结束**

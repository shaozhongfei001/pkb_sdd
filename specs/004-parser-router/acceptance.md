# Acceptance: 解析路由（004 Parser Router）

> **Spec**：`specs/004-parser-router`  
> **Plan 对照**：`plan.md` §21  
> **测试对照**：`test_cases.md`

---

## A001 范围符合

004 只做 Parser Router **路由决策**，不执行真实解析。

- 无 `parsed/`、`curated/` 产物
- 无 MinerU / MarkItDown import、subprocess 或网络调用
- `future_parser_hint` 仅为 JSON 报告中的静态标签，不代表 004 已调用任何解析器
- `build-parse-queue`、`parse` 保持 placeholder

## A002 原始文件保护

执行本功能不得删除、移动、重命名、覆盖或修改任何原始用户文件。

- CLI 入口调用 `ensure_readonly()`
- pytest 验证 route 前后原始 fixture 文件 stat / 内容 hash 不变

## A003 raw_vault 保护

执行本功能不得删除、覆盖、移动 `raw_vault/**` 下任何文件。

- 004 只读引用 `vault_path`（及 DB 中的 sidecar 路径字符串）
- pytest 验证 route 前后 `original.bin` hash 与 vault 目录 listing 不变

## A004 不写 parsed / curated / quarantine

004 MVP **唯一**磁盘产物为 `{reports_root}/parser_route_report_{UTC}.json`。

- 不得写入 `parsed/`、`curated/`、`quarantine/`
- 不得写入 `raw_vault/`

## A005 不接 MinerU / MarkItDown

004 不得 import、调用、subprocess 或网络访问 MinerU、MarkItDown 或任何第三方解析器。

- 代码审查 + grep 确认无 `markitdown` / `mineru` 依赖调用
- `future_parser_hint` 字段名不得使用 `suggested_parser`

## A006 不做 OCR / 文本抽取，不读取 original.bin 内容

路由决策仅基于 MySQL 元数据列（`file_ext`、`mime_type`、instance fallback 等）。

- 禁止 open `original.bin` 做 magic-byte、OCR 或文本抽取
- 禁止 open raw_vault sidecar JSON 内容（仅允许从 DB 列拷贝路径字符串）
- MVP 所有 `.pdf` → `PDF_DIGITAL`，不区分扫描件

## A007 不做向量库 / 项目卡蒸馏

004 不涉及 embedding、向量库、项目卡蒸馏或 `curated/` 写入。

## A008 幂等性

同样输入（同 content metadata）得到稳定 route decision。

- 连续两次 `route-parsers`：`route_type`、`rule_name`、`reason` 一致
- MySQL **无写操作** → 无重复主记录风险
- 报告每次新 UTC timestamp 文件，不覆盖旧报告

## A009 异常可恢复

单 content 路由失败不中断整体批处理。

- 失败记入 `errors[]`（含 sha256 + message）
- 其他 content 正常产出 decision
- `UNKNOWN` / `UNSUPPORTED` 计入 summary，不抛未捕获异常
- `--sha256` 指向不存在 content：空结果 / 汇总，exit 0

## A010 报告可追溯

`parser_route_report_{UTC}.json` 每条 decision 必须含：

- `content_uid`
- `sha256`
- `vault_path`（可为 null 但 reason 须说明）
- `file_ext` 或 fallback 说明
- `mime_type`
- `route_type`
- `decision`（ROUTE / UNKNOWN / UNSUPPORTED / ERROR）
- `reason`
- `future_parser_hint`（`MARKITDOWN_FAMILY` | `MINERU_FAMILY` | `DIRECT_TEXT` | `NONE`）

## A011 SQL schema 边界

004 MVP 不修改 SQL schema、不新增 route 表、不新增 migration、不持久化 route decision 到 MySQL。

- 禁止 upsert `kb_parse_job`
- 禁止 update `kb_file_content.parse_status`
- `kb_file_content`、`kb_raw_vault_object`、`kb_file_instance` 仅 SELECT
- 若实现发现必须写 DB → STOP → TL

## A012 测试通过

- `pytest -q tests/test_parser_router.py` 通过（≥10 test functions）
- 全链路回归通过：

```bash
pytest -q tests/test_inventory_scanner.py tests/test_file_content_vault.py tests/test_duplicate_governance.py tests/test_parser_router.py
```

- CLI E2E：`route-parsers --help` 及一次正常执行（scan → copy-to-vault → route-parsers）

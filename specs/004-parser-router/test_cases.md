# Test Cases: 解析路由（004 Parser Router）

> **Plan 对照**：`plan.md` §20  
> **验收对照**：`acceptance.md` A001–A012

---

| 编号 | 场景 | 输入 | 预期 |
|------|------|------|------|
| **TC001** | Office 扩展名路由 | mock/DB 行：`file_ext=.docx` / `.pptx` / `.xlsx` | `route_type` 分别为 `DOCX` / `PPTX` / `XLSX`；`future_parser_hint=MARKITDOWN_FAMILY`；不 import/call MarkItDown |
| **TC002** | PDF 路由（不读内容） | mock/DB 行：`file_ext=.pdf`，`mime_type=application/pdf` | `route_type=PDF_DIGITAL`；`future_parser_hint=MINERU_FAMILY`；**不** open `original.bin`；**不**判断扫描件；**不**赋 `PDF_SCANNED_OR_IMAGE` |
| **TC003** | 图片路由（不 OCR） | mock/DB 行：`file_ext=.png`（或 `.jpg` 等） | `route_type=IMAGE`；`future_parser_hint=MINERU_FAMILY`；**不** OCR、**不**读 bin |
| **TC004** | 文本 / Markdown 路由（不抽取） | fixtures `.txt` 或 mock：`file_ext=.txt` / `.md` | `route_type=TEXT_OR_MARKDOWN`；`future_parser_hint=DIRECT_TEXT`；**不**抽取文本内容 |
| **TC005** | UNKNOWN / UNSUPPORTED 可报告、不中断 | 无 ext 且 fallback 失败 → UNKNOWN；`.doc` → UNSUPPORTED | `decision=UNKNOWN` 或 `UNSUPPORTED`；计入 summary；批处理 continue；`future_parser_hint=NONE` |
| **TC006** | `--sha256` 过滤 | CLI：`route-parsers --sha256 <hex>` | 仅处理指定 content；其他跳过 |
| **TC007** | `--content-uid` 过滤 | CLI：`route-parsers --content-uid <uid>` | 行为同 `--sha256`（001 约定 content_uid ≡ sha256） |
| **TC008** | `--limit` 限制 | CLI：`route-parsers --limit N` | 最多处理 N 个候选 content |
| **TC009** | 重复执行幂等 | 同一数据集连续两次 `route-parsers`（或两次 service 调用） | 两次 `route_type`、`rule_name`、`reason` 一致；MySQL 无写；无重复主记录 |
| **TC010** | 单 content 异常不中断整体 | 注入单条 DB/逻辑异常（如缺失关联行） | 该条记入 `errors[]`；其余 content 正常产出 decision；批处理完成 |
| **TC011** | 原始文件 stat/hash 不变 | `backend/tests/fixtures/中文路径/银行项目/` 全链路前后 | 原始 fixture mtime / 内容 hash 不变；无 delete/move/rename |
| **TC012** | raw_vault listing/hash 不变 | scan → copy-to-vault → route-parsers 前后 | `original.bin` sha256 不变；vault 目录 listing 不变；service 不读 bin 做路由 |
| **TC013** | 不写 parsed / curated / quarantine | route-parsers 执行前后目录对比 | `parsed/`、`curated/`、`quarantine/` 无新增文件 |
| **TC014** | 不修改 SQL schema | 实现前后对比 `sql/**`；审查 ORM/service 写操作 | 无 migration；无 upsert `kb_parse_job`；无 update `parse_status`；无 route 表 |
| **TC015** | CLI E2E | `python -m app.cli.main route-parsers --help`；`scan` → `copy-to-vault` → `route-parsers` | `--help` 正常；Routed ≥ 1、Errors = 0；`parser_route_report_*.json` 存在于 reports_root；Rich 汇总含报告路径 |

---

## pytest 映射（建议）

| Test Case | 建议 test function（`test_parser_router.py`） |
|-----------|---------------------------------------------|
| TC001 | `test_route_office_ext` |
| TC002 | `test_route_pdf_to_pdf_digital` |
| TC003 | `test_route_image_ext` |
| TC004 | `test_route_txt_to_text_or_markdown` |
| TC005 | `test_route_unknown_missing_ext`、`test_route_legacy_office_unsupported` |
| TC006–TC008 | CLI 选项集成测试（可合入 `test_route_project_fixtures_integration`） |
| TC009 | `test_route_idempotent` |
| TC010 | `test_route_single_error_continues` |
| TC011 | `test_original_files_unchanged` |
| TC012 | `test_raw_vault_unchanged` |
| TC013–TC014 | 合入集成测试断言或 QA 目录检查 |
| TC015 | `test_route_project_fixtures_integration` + `--help` smoke |

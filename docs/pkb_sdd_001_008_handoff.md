# pkb_sdd 项目完整交接文档：001–008 收口与下一阶段接手指南

> 适用对象：新开的 ChatGPT 会话 / Cursor / Tech Lead Agent / Dev Agent / QA Agent / E2E Agent  
> 项目：`pkb_sdd`，个人历史项目文档知识库  
> 当前状态：001–008 已完成并 merge 到 `main`  
> 当前 main 最新提交：`1edb12e merge: feature/008-parse-quality-checker into main`  
> 远端状态：`origin/main` 已推送到 `1edb12e`  
> 交接目的：让新会话无需翻阅长上下文，即可准确理解项目阶段、已完成能力、契约边界、008 收口情况和下一阶段启动方式。

---

## 0. 一句话总览

截至本交接文档生成时，`pkb_sdd` 已完成并合入 `main` 的阶段为：

```text
001 File Inventory
002 File Content Vault
003 Duplicate Governance
004 Parser Router
005 MarkItDown Parser
006 Parse Job Registry
007 MinerU PDF Parser Adapter
008 Parse Quality Checker
```

当前项目状态：

```text
001–008：DONE
Contract Alignment：DONE
008 Parse Quality Checker：DONE
main merge：DONE
origin/main push：DONE
```

当前最新主干：

```text
main / origin/main -> 1edb12e merge: feature/008-parse-quality-checker into main
```

下一阶段尚未启动。必须先读取：

```text
specs/SPEC_INDEX.md
```

不要按目录编号猜测 active spec。

---

## 1. 项目定位

项目名称：`pkb_sdd`

项目目标：建设“个人历史项目文档知识库”，以 SDD 阶段化方式完成：

1. 文件盘点
2. 原文内容入 vault
3. 精确重复治理
4. parser 路由规划
5. MarkItDown 文档解析
6. 解析注册入 DB
7. MinerU PDF 解析适配
8. 解析质量检查

项目当前仍处于基础数据与解析链路建设阶段，尚未进入：

```text
vector / embedding
curated
project card
semantic similarity
LLM semantic judgment
automatic repair
human review workflow
```

---

## 2. 全局硬约束

后续所有 Agent 必须继续遵守：

```text
1. 不处理源代码知识库。
2. 不移动、删除、重命名原始文件。
3. 不自动删除重复文件。
4. 不删除 raw_vault。
5. 不做语义相似 / LLM 判断。
6. 不写向量库。
7. 不写 curated。
8. 不写 project card。
9. DB 使用 MySQL。
10. 任何新 DB 写入或 schema 修改必须先进入 DB Review。
11. 默认只读优先。
12. 质量检查阶段只报告问题，不修复问题。
13. 不按目录编号猜 active spec，必须以 specs/SPEC_INDEX.md 为准。
```

---

## 3. 权威路径契约

### 3.1 raw_vault 路径契约

```text
raw_vault/by_hash/{sha256[:2]}/{sha256}/original.bin
```

说明：

- `KbRawVaultObject.vault_path` 存的是 vault directory。
- 检查 `original.bin` 时，应通过 `build_vault_artifact_paths(vault_dir)["original_bin"]` 定位。
- 不得直接假设 `vault_path` 本身就是 `original.bin`。

### 3.2 parsed 路径契约

```text
parsed/by_hash/{sha256[:2]}/{sha256[2:4]}/{sha256}/
  parsed_text.md
  parsed_metadata.json
  parse_manifest.json
```

注意：

```text
parser_profile 和 parser_adapter_version 是 parse_manifest.json 中的元数据字段。
它们不是 parsed 路径层级。
```

禁止使用旧路径：

```text
parsed/by_hash/{sha256_prefix}/{sha256}/{parser_profile}/
```

---

## 4. 权威 Spec Index 规则

当前仓库存在历史 stub 与正式 SDD spec 并存情况。因此：

```text
specs/SPEC_INDEX.md 是唯一权威索引。
Cursor / ChatGPT / Agent 选择 spec 时必须先读取该文件。
如果目录编号与 SPEC_INDEX 冲突，以 SPEC_INDEX 为准。
不要按 specs/00x-* glob 自动判断当前阶段。
```

已明确的历史 stub：

```text
specs/006-mineru-parser/      -> DEPRECATED，已由 specs/007-mineru-pdf-parser-adapter/ 取代
specs/007-quality-checker/    -> DEPRECATED，已顺延为 specs/008-parse-quality-checker/
specs/008-review-workflow/    -> FUTURE STUB / NOT CURRENT
```

008 完成后，下一阶段必须由 `SPEC_INDEX.md` 明确指定。

---

## 5. 已完成阶段总表

| 阶段 | 权威 Spec 目录 | 核心能力 | 状态 |
|---|---|---|---|
| 001 | `specs/001-file-inventory/` | 文件盘点 / scan | DONE |
| 002 | `specs/002-file-content-vault/` | raw_vault 原文内容入库 | DONE |
| 003 | `specs/003-duplicate-governance/` | 精确重复治理，只报告不删除 | DONE |
| 004 | `specs/004-parser-router/` | parser 路由规划，只规划不解析 | DONE |
| 005 | `specs/005-markitdown-parser/` | MarkItDown 文档解析适配 | DONE |
| 006 | `specs/006-parse-job-registry/` | parse run/result/artifact 注册 | DONE |
| 007 | `specs/007-mineru-pdf-parser-adapter/` | MinerU PDF parser adapter | DONE |
| 008 | `specs/008-parse-quality-checker/` | parsed / registry / raw_vault 一致性质量检查 | DONE |

---

## 6. 001 File Inventory 收口

权威目录：

```text
specs/001-file-inventory/
```

核心 CLI：

```text
scan
```

主要职责：

```text
1. 盘点文件实例。
2. 记录 kb_file_instance。
3. 记录 kb_file_content。
4. 计算 sha256。
5. 识别 file_ext / mime_type。
6. 记录 vault_status 初始状态。
```

边界：

```text
不复制文件到 raw_vault。
不解析文件内容。
不做重复治理。
不做 parser 路由。
```

状态：

```text
DONE
```

---

## 7. 002 File Content Vault 收口

权威目录：

```text
specs/002-file-content-vault/
```

核心 CLI：

```text
copy-to-vault
```

主要职责：

```text
1. 将原始文件复制到 raw_vault。
2. 使用 sha256 分桶路径。
3. 建立 kb_raw_vault_object。
4. 标记 vault_status=COPIED。
```

路径契约：

```text
raw_vault/by_hash/{sha256[:2]}/{sha256}/original.bin
```

边界：

```text
不删除原文件。
不移动原文件。
不改名原文件。
不解析内容。
```

状态：

```text
DONE
```

---

## 8. 003 Duplicate Governance 收口

权威目录：

```text
specs/003-duplicate-governance/
```

核心 CLI：

```text
govern-duplicates
```

主要职责：

```text
1. 基于 sha256 做精确重复分组。
2. 建立 KbDuplicateGroup。
3. 输出重复治理报告。
4. 只给治理建议，不自动删除、不自动清理。
```

边界：

```text
不做语义相似。
不使用 LLM 判断。
不删除重复文件。
```

状态：

```text
DONE
```

---

## 9. 004 Parser Router 收口

权威目录：

```text
specs/004-parser-router/
```

核心 CLI：

```text
route-parsers
```

主要职责：

```text
1. 对文件做 parser route planning。
2. 判断文件应交给哪类 parser。
3. 输出 parser_route_report_{UTC}.json。
4. 不执行解析。
```

典型 route：

```text
PDF_DIGITAL
PDF_SCANNED_OR_IMAGE
OFFICE
TEXT
HTML
JSON
XML
UNSUPPORTED
```

边界：

```text
不调用 MarkItDown。
不调用 MinerU。
不写 parsed。
不写 registry。
```

状态：

```text
DONE
```

---

## 10. 005 MarkItDown Parser 收口

权威目录：

```text
specs/005-markitdown-parser/
```

核心 CLI：

```text
parse-markitdown
```

主要职责：

```text
1. 处理 Office / HTML / XML / JSON / TXT / Markdown 等普通文档。
2. 读取 raw_vault original.bin。
3. 写 parsed 三件套。
4. 只写磁盘 parsed，不默认写 DB。
```

标准 parsed 产物：

```text
parsed_text.md
parsed_metadata.json
parse_manifest.json
```

重要结论：

```text
005 是 parsed artifact contract 的实际奠基阶段。
007 MinerU 和 008 Quality Checker 均已对齐该 contract。
```

边界：

```text
不处理 MinerU PDF。
不写 registry。
不写 vector / curated / project card。
```

状态：

```text
DONE
```

---

## 11. 006 Parse Job Registry 收口

权威目录：

```text
specs/006-parse-job-registry/
```

核心 CLI：

```text
register-parse-report
```

主要职责：

```text
1. 将 parse report 登记到 DB。
2. 建立 parse run。
3. 建立 parse result。
4. 建立 parsed artifact。
5. 对 parsed 三件套做 registry ingest。
```

核心表：

```text
kb_parse_run
kb_parse_result
kb_parsed_artifact
```

注意：

```text
早期文档中出现过 kb_parse_job 表述。
008 P2/P3 已裁决：以 KbParseRun / kb_parse_run 为准。
```

关键 DB 决策：

```text
M1：kb_parsed_artifact 唯一键：
    uk_artifact_scope(run_uid, content_uid, artifact_type, parser_name, parser_adapter_version)

M2：--dry-run 零 DB 写；删除 DRY_RUN_COMPLETED。

M3：dry-run 报告拒绝 ingest，错误为 INVALID_DRY_RUN_REPORT。

M4：document_uid = content_uid。
```

006 ingest 期望 parsed 文件：

```text
parsed_text.md
parsed_metadata.json
parse_manifest.json
```

边界：

```text
不执行解析。
不修改 raw_vault。
不修改 parsed。
不调用 MarkItDown / MinerU。
```

状态：

```text
DONE
```

---

## 12. 007 MinerU PDF Parser Adapter 收口

权威目录：

```text
specs/007-mineru-pdf-parser-adapter/
```

核心 CLI：

```text
parse-mineru-pdf
```

核心 commits：

```text
cd9cb5a feat(007): add MinerU PDF parser adapter
b1fce01 docs(007): add MinerU PDF parser handoff
68d99c2 merge: feature/007-mineru-pdf-parser-adapter into main
```

新增/修改核心文件：

```text
backend/app/services/mineru_pdf_parser.py
backend/app/cli/main.py
backend/tests/test_mineru_pdf_parser.py
docs/handoff-007-mineru-pdf-parser-adapter.md
specs/007-mineru-pdf-parser-adapter/*
```

实现范围：

```text
1. 新增 MineruPdfParserService。
2. 新增 CLI：parse-mineru-pdf。
3. 支持 --config。
4. 支持 --sha256。
5. 支持 --content-uid。
6. 支持 --limit。
7. 支持 --dry-run。
8. 支持 --force。
9. 支持 --timeout。
10. 支持 --register / --no-register。
11. 默认 --no-register。
12. dry-run 零副作用。
13. 可选 registry 登记，只走 ParseRegistryService.register_parse_report()。
14. 复用 005 parsed contract。
15. 复用 006 registry ingest contract。
```

007 parsed 输出契约：

```text
parsed_text.md
parsed_metadata.json
parse_manifest.json
```

已废弃的 P4 初版产物名称：

```text
content.md
metadata.json
parse_report.json
```

007 registry 行为：

```text
默认：--no-register
显式登记：--register
登记路径：ParseRegistryService.register_parse_report(report_path=...)
```

禁止：

```text
直接 SQL
直接 ORM insert/update
修改 parse_registry.py
修改 schema
新增 migration
```

测试结果：

```text
007 专项测试：31 passed
004/005/006 回归：96 passed
backend/tests 全量：151 passed
```

007 caveat 必须保留：

```text
真实 magic-pdf / MinerU E2E 未完成。
```

原因：

```text
1. magic-pdf 不在 PATH。
2. 当前 DB 中唯一 COPIED PDF 的 vault_path 指向已删除 /tmp/p5_reqa_* 路径。
3. 无 COPIED 非 PDF live 样本用于 ROUTE_MISMATCH CLI 验收。
```

正确表述：

```text
007 已完成 mock subprocess + 真实 ParseRegistryService ingest + CLI/dry-run/dependency 护栏 + 全量 pytest 回归。
真实 magic-pdf 端到端需在安装 MinerU 并准备干净 PDF vault 样本后补跑。
```

禁止表述：

```text
真实 MinerU 生产链路已完整验收。
```

状态：

```text
DONE
```

---

## 13. 008 Parse Quality Checker 收口

权威目录：

```text
specs/008-parse-quality-checker/
```

核心 CLI：

```text
check-parse-quality
```

主干 merge：

```text
1edb12e merge: feature/008-parse-quality-checker into main
```

远端状态：

```text
origin/main 已推送到 1edb12e
```

主要实现文件：

```text
backend/app/services/parse_quality_checker.py
backend/app/cli/main.py
backend/tests/test_parse_quality_checker.py
```

交接 / 审查 / QA / E2E 文件：

```text
docs/handoff-008-parse-quality-checker.md
specs/008-parse-quality-checker/spec.md
specs/008-parse-quality-checker/plan.md
specs/008-parse-quality-checker/tasks.md
specs/008-parse-quality-checker/acceptance.md
specs/008-parse-quality-checker/test_cases.md
specs/008-parse-quality-checker/p2_p3_review.md
specs/008-parse-quality-checker/p5_qa_report.md
specs/008-parse-quality-checker/p6_e2e_report.md
specs/008-parse-quality-checker/p7_final_review.md
```

---

## 14. 008 阶段目标

008 是跨层只读一致性质量检查器，检查对象包括：

```text
raw_vault
parsed artifacts
parse_manifest.json
parse registry records
parser metadata
report output
```

008 的定位：

```text
只报告质量问题。
不修复数据。
不调用 parser。
不写 DB。
不修改 raw_vault。
不修改 parsed。
不修改 registry。
```

---

## 15. 008 CLI 使用方式

基础命令：

```text
PYTHONPATH=backend python -m app.cli.main check-parse-quality \
  --config config/app.yaml
```

支持参数：

```text
--config
--sha256
--content-uid
--parser-name
--status
--limit
--output
--fail-on-issue
```

示例：指定输出路径：

```text
PYTHONPATH=backend python -m app.cli.main check-parse-quality \
  --config config/app.yaml \
  --output /tmp/pkb_sdd_008_p6/parse_quality_report.json
```

Exit code：

```text
0：成功生成报告
1：配置 / DB / 运行时错误
2：仅当 --fail-on-issue 且 issue_count > 0
```

禁止参数 / 行为：

```text
--fix
--repair
--reparse
--run-parser
--write-db
--markitdown
--mineru
--magic-pdf
```

---

## 16. 008 Report Contract

默认输出路径：

```text
{reports_root}/parse_quality_report_{YYYYMMDDTHHMMSSZ}.json
```

指定输出路径：

```text
--output /path/to/parse_quality_report.json
```

稳定字段：

```text
report_type = parse_quality_report
schema_version = 1.0
mode = check
```

Top-level fields：

```text
report_type
schema_version
generated_at
mode
scope
summary
issue_counts
by_parser
by_status
by_route_type
by_severity
issues
recommendations
```

recommendations 只能是非变更建议，不执行修复。

---

## 17. 008 Issue Taxonomy

008 issue_counts 必须包含全部 18 个稳定 code，即使 count 为 0：

```text
MISSING_RAW_VAULT_OBJECT
STALE_RAW_VAULT_PATH
MISSING_PARSED_DIR
MISSING_PARSED_TEXT
MISSING_PARSED_METADATA
MISSING_PARSE_MANIFEST
INVALID_PARSE_MANIFEST_JSON
MANIFEST_REQUIRED_FIELD_MISSING
MANIFEST_SHA256_MISMATCH
MANIFEST_CONTENT_UID_MISMATCH
MANIFEST_PARSER_NAME_INVALID
MANIFEST_ADAPTER_VERSION_MISSING
REGISTRY_ARTIFACT_PATH_MISSING
REGISTRY_STATUS_FILE_MISMATCH
REGISTRY_MISSING_MANIFEST_RESULT
REGISTRY_FAILED_RESULT
REGISTRY_EMPTY_RESULT
REGISTRY_SKIPPED_RESULT
```

Severity：

```text
CRITICAL
ERROR
WARNING
INFO
```

每个 issue item 应包含：

```text
issue_code
severity
content_uid
sha256
parser_name
parser_adapter_version
artifact_type
path
message
evidence
```

---

## 18. 008 P1–P8 阶段收口

### P1 Tech Lead Plan

完成阶段级 specs 五件套：

```text
spec.md
plan.md
tasks.md
acceptance.md
test_cases.md
```

提交：

```text
3019f22 spec(008): add parse quality checker plan
```

### P2 / P3 Review

完成 DB/Data Read Review + Implementation Gate。

关键裁决：

```text
1. 无阻断性契约冲突。
2. DB 写审豁免，因为 008 只读。
3. 允许只读 ORM 查询。
4. 允许写唯一副作用文件：JSON report。
5. 不新增 issue code。
6. 不修改 schema / migration / registry。
```

提交：

```text
bea3a28 spec(008): add P2 P3 implementation gate
```

### P4 Dev Implementation

实现：

```text
backend/app/services/parse_quality_checker.py
backend/app/cli/main.py
backend/tests/test_parse_quality_checker.py
```

提交：

```text
ed5769a feat(008): implement parse quality checker
```

P4 测试：

```text
008 专项：26 passed
004–007 回归：127 passed
合计：153 passed
```

### P5 QA + Defect Fix

P5 发现真实缺陷：

```text
真实 config/app.yaml + MySQL 环境中，历史 pytest DB 记录指向 /tmp/pytest-of-root/...。
部分路径当前用户无权限访问。
Path.is_dir() / Path.is_file() / Path.read_text() 抛 PermissionError。
CLI 因 PermissionError 崩溃，未生成 report。
```

修复策略：

```text
不新增 issue code。
将 PermissionError / OSError 映射到已有 issue code。
继续生成 report。
evidence 包含 error、errno、path。
```

映射：

| 场景 | issue_code | severity |
|---|---|---|
| parsed_dir.is_dir() access failure | MISSING_PARSED_DIR | ERROR |
| parsed_text.is_file() access failure | MISSING_PARSED_TEXT | ERROR |
| parsed_metadata.is_file() access failure | MISSING_PARSED_METADATA | ERROR |
| parse_manifest.is_file() access failure | MISSING_PARSE_MANIFEST | ERROR |
| parse_manifest.read_text() access failure | INVALID_PARSE_MANIFEST_JSON | ERROR |
| original_bin.is_file() access failure | MISSING_RAW_VAULT_OBJECT | ERROR |
| registry artifact is_file() access failure | REGISTRY_ARTIFACT_PATH_MISSING | ERROR |

提交：

```text
e4d611c fix(008): handle inaccessible paths in quality checker
1552249 test(008): add parse quality checker QA report
```

P5 结果：

```text
008 specialized tests：30 passed
004–007 regression tests：127 passed
P5 real-environment --output validation：PASS
output ok
json ok
```

真实报告摘要：

```text
Issues: 964
Critical: 140
Errors: 676
Checked parse results: 148
PermissionError issues: 540
MISSING_PARSED_DIR issues: 140
issue_counts still contains all 18 stable issue codes
```

### P6 E2E Validation

P6 验证真实环境：

```text
real config/app.yaml
real MySQL
real raw_vault
real parsed artifacts
explicit report output path
```

验证点：

```text
CLI generated report
JSON valid
DB row counts unchanged
raw_vault mtimes unchanged
parsed mtimes unchanged
only JSON report output created
```

提交：

```text
86cf3ae test(008): add parse quality checker E2E report
```

### P7 Tech Lead Final Review

P7 结论：

```text
P7 Tech Lead Final Review：PASS
008 approved for P8 Handoff & Final Commit
```

提交：

```text
590c4f7 review(008): add parse quality checker final review
```

### P8 Handoff & Merge

P8 内容：

```text
docs/handoff-008-parse-quality-checker.md
specs/SPEC_INDEX.md 更新 008 DONE
merge feature/008-parse-quality-checker into main
push origin main
```

提交：

```text
29de57f docs(008): add parse quality checker handoff
1edb12e merge: feature/008-parse-quality-checker into main
```

---

## 19. 当前 Git 状态

最终主干：

```text
main
1edb12e (HEAD -> main, origin/main) merge: feature/008-parse-quality-checker into main
```

008 feature 分支：

```text
feature/008-parse-quality-checker 已 merge 到 main。
远端 feature/008-parse-quality-checker 不存在。
如果本地仍存在，可删除。
```

远端删除检查结果：

```text
git branch -r | grep feature/008-parse-quality-checker || true
# 无输出

git push origin --delete feature/008-parse-quality-checker
# remote ref does not exist
# 这是正常情况，说明远端没有该分支。
```

本地清理：

```text
git branch -d feature/008-parse-quality-checker
```

---

## 20. 当前重要 commit 链

最新主干可见链路：

```text
1edb12e merge: feature/008-parse-quality-checker into main
29de57f docs(008): add parse quality checker handoff
590c4f7 review(008): add parse quality checker final review
86cf3ae test(008): add parse quality checker E2E report
1552249 test(008): add parse quality checker QA report
e4d611c fix(008): handle inaccessible paths in quality checker
bea3a28 spec(008): add P2 P3 implementation gate
ed5769a feat(008): implement parse quality checker
3019f22 spec(008): add parse quality checker plan
4732135 docs(specs): align active spec contracts
95106f2 docs(rules): align parser contracts after 007
d6b845a docs(specs): mark deprecated parser and quality checker stubs
68d99c2 merge: feature/007-mineru-pdf-parser-adapter into main
```

---

## 21. Cursor Rules 当前对齐点

已修正：

```text
.cursor/rules/004-parser.mdc
.cursor/rules/007-agent-collaboration.mdc
```

核心对齐：

```text
parsed 输出路径使用：
parsed/by_hash/{sha256[:2]}/{sha256[2:4]}/{sha256}/

标准产物：
parsed_text.md
parsed_metadata.json
parse_manifest.json

parser_profile / parser_adapter_version：
写入 parse_manifest.json，不是路径层级。
```

007-agent-collaboration 修正口径：

```text
Completed parser contracts are 005 MarkItDown (`parse-markitdown`) and 007 MinerU PDF parser adapter (`parse-mineru-pdf`);
new parser behavior must follow the completed parsed artifact contract unless a later Spec explicitly changes it.
```

---

## 22. 多 Agent 角色规范

后续统一使用四类角色：

| 角色 | 职责 |
|---|---|
| Tech Lead Agent | 范围、契约、方案、Review、准入裁决 |
| Dev Agent | 按白名单编码实现，不扩大范围 |
| QA Agent | 单元测试、回归测试、缺陷报告 |
| E2E Agent | 真实链路验收、CLI/DB/文件联通验证 |

重要规则：

```text
P5 是 QA Agent。
P6 是 E2E Agent。
不要把 QA Agent 叫 E2E QA Agent。
不要新增混合角色名。
```

---

## 23. 后续新会话接手前必须执行

建议新会话第一步让用户运行：

```text
cd /home/szf/dev/pyws/pkb_sdd
source backend/.venv/bin/activate
git branch --show-current
git status --short
git log --oneline --decorate -12
sed -n '1,260p' specs/SPEC_INDEX.md
```

期望：

```text
当前分支 main
git status --short 无输出
main / origin/main 在 1edb12e 或之后
SPEC_INDEX 显示 001–008 DONE
```

---

## 24. 下一阶段启动原则

当前不要直接启动 `specs/008-review-workflow/`，除非 `SPEC_INDEX.md` 明确把它设为 active。

下一阶段应先由 Tech Lead Agent 做：

```text
P0 / P1 Active Spec Selection Review
```

必须回答：

```text
1. SPEC_INDEX.md 当前 active / future 状态是什么？
2. 是否已有 009 spec？
3. specs/008-review-workflow/ 是否仍是 future stub？
4. 下一阶段是 review workflow、repair planning、quality report consumption，还是其他？
5. 是否需要先整理 DB 中历史 pytest 脏记录的治理策略？
6. 是否需要为 008 报告增加消费入口，而不是直接修复？
```

---

## 25. 可能的下一阶段候选

以下只是候选，不是 active spec。必须以 SPEC_INDEX 为准。

### 25.1 Parse Quality Report Consumption

目标：

```text
读取 008 quality report。
输出更适合人工阅读的摘要。
不修复数据。
不改 DB。
```

### 25.2 Repair Planning / Remediation Proposal

目标：

```text
基于 008 report 生成修复计划。
只生成 proposal。
不执行修复。
```

### 25.3 Human Review Workflow

目标：

```text
把质量问题进入人工复核队列。
可能涉及 review status、review decision、review notes。
若写 DB，必须先 DB Review。
```

### 25.4 Test-data Cleanup Governance

目标：

```text
治理历史 pytest 脏记录。
必须明确是否允许删除测试 DB 记录。
这不应由 008 自动完成。
```

---

## 26. 后续红线

未来 Agent 必须记住：

```text
1. 不要再把 MinerU 当作 006。
2. 不要再把 Quality Checker 当作 007。
3. 不要把 specs/008-review-workflow/ 自动当作当前 active spec。
4. 不要使用旧 parsed 路径。
5. 不要让质量检查器修复数据。
6. 不要让质量检查器调用 parser。
7. 不要让质量检查器写 DB。
8. 不要宣称 007 已完成真实 magic-pdf E2E。
9. 不要用 sudo git。
10. 不要跳过 specs/SPEC_INDEX.md。
11. 不要因为 008 报告出大量问题就自动清理 raw_vault / parsed / DB。
```

---

## 27. 常用命令

### 27.1 环境

```text
cd /home/szf/dev/pyws/pkb_sdd
source backend/.venv/bin/activate
```

### 27.2 运行 008

```text
PYTHONPATH=backend python -m app.cli.main check-parse-quality \
  --config config/app.yaml
```

指定输出：

```text
PYTHONPATH=backend python -m app.cli.main check-parse-quality \
  --config config/app.yaml \
  --output /tmp/pkb_sdd_008_check/parse_quality_report.json
```

### 27.3 测试

008 专项：

```text
PYTHONPATH=backend pytest backend/tests/test_parse_quality_checker.py
```

004–008 回归：

```text
PYTHONPATH=backend pytest \
  backend/tests/test_parser_router.py \
  backend/tests/test_markitdown_parser.py \
  backend/tests/test_parse_job_registry.py \
  backend/tests/test_mineru_pdf_parser.py \
  backend/tests/test_parse_quality_checker.py
```

全量：

```text
PYTHONPATH=backend pytest backend/tests
```

### 27.4 Git

```text
git status --short
git log --oneline --decorate -12
git branch
git branch -d feature/008-parse-quality-checker
```

---

## 28. 给下一次新 ChatGPT 会话的启动提示词

可以直接复制下面内容作为新会话第一条消息：

```text
你接手 pkb_sdd 项目，担任 Tech Lead Agent。

当前状态：
1. 001–008 已完成并 merge 到 main。
2. main / origin/main 最新提交为 1edb12e merge: feature/008-parse-quality-checker into main。
3. 008 Parse Quality Checker 已完成 P1–P8。
4. 008 实现了 check-parse-quality，只读检查 raw_vault / parsed / parse_manifest.json / registry 一致性，只输出 JSON report。
5. 008 不修复数据，不调用 MarkItDown / MinerU / magic-pdf，不写 DB，不修改 raw_vault / parsed / registry。
6. 007 MinerU PDF Parser Adapter 已完成，但真实 magic-pdf / MinerU E2E 仍保留 caveat。
7. specs/SPEC_INDEX.md 是唯一权威索引。
8. specs/006-mineru-parser/ 与 specs/007-quality-checker/ 是 deprecated stub。
9. specs/008-review-workflow/ 不能自动当作当前 active spec，除非 SPEC_INDEX.md 明确指定。
10. 下一阶段尚未启动，必须先读取 SPEC_INDEX.md 做 Active Spec Selection Review。

请先要求我贴出：
- git status --short
- git log --oneline --decorate -12
- sed -n '1,260p' specs/SPEC_INDEX.md

然后帮我判断下一阶段应该启动哪个 spec，并按 Tech Lead Agent 流程输出 P1 计划。
```

---

## 29. 最终结论

```text
001 File Inventory：DONE
002 File Content Vault：DONE
003 Duplicate Governance：DONE
004 Parser Router：DONE
005 MarkItDown Parser：DONE
006 Parse Job Registry：DONE
007 MinerU PDF Parser Adapter：DONE
008 Parse Quality Checker：DONE

Contract Alignment：DONE
Cursor rules alignment：DONE
Deprecated stubs marked：DONE
008 handoff：DONE
main merge：DONE
origin/main push：DONE

下一步：不要猜阶段；先读 specs/SPEC_INDEX.md，做下一 active spec 选择。
```

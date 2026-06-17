# 009 Parse Quality Report Summary — spec.md

> Project: `pkb_sdd`  
> Spec Directory: `specs/009-quality-report-summary/`  
> Branch: `feature/009-quality-report-summary`  
> Phase: `P1 Tech Lead Plan — COMPLETE (awaiting user review)`  
> Status: `ACTIVE SPEC / NOT IMPLEMENTED`  
> Authority: `specs/SPEC_INDEX.md`  
> Scope: Read-only consumption of 008 `parse_quality_report.json`; output human-readable Markdown / JSON summary only.

---

## 1. Background

The completed SDD chain through 008 is:

```text
001-file-inventory
002-file-content-vault
003-duplicate-governance
004-parser-router
005-markitdown-parser
006-parse-job-registry
007-mineru-pdf-parser-adapter
008-parse-quality-checker
```

008 produces a machine-readable JSON report:

```text
parse_quality_report_{UTC}.json
report_type = parse_quality_report
schema_version = 1.0
```

Real-environment P6 validation showed large issue counts (964 total) with significant test/stale-path noise (540 PermissionError-related issues). Operators need a **summary layer** that makes the 008 report easier to triage without re-scanning the project or mutating data.

The current active spec is:

```text
specs/009-quality-report-summary/
```

The following directories are **not** current implementation sources:

```text
specs/006-mineru-parser/           # deprecated stub
specs/007-quality-checker/         # deprecated stub
specs/008-review-workflow/         # future stub; NOT current 008
specs/010-evidence-chain/          # future stub
```

---

## 2. Problem Statement

008 JSON reports are complete but verbose. Without a summary layer:

```text
1. Manual triage is slow.
2. Test/stale-path noise mixes with real data defects.
3. There is no stable, human-readable artifact for review / repair planning specs to reference.
```

009 solves this with a **pure report pipeline**: read 008 JSON → write summary file.

---

## 3. Goals

### 3.1 Functional Goals

```text
G001 Read an existing 008 parse_quality_report.json (--input or latest under reports_root).
G002 Validate report_type=parse_quality_report and schema_version=1.0.
G003 Output Markdown summary by default.
G004 Output JSON summary when --format json.
G005 Preserve all 18 stable issue_counts from 008 (even when zero).
G006 Aggregate by severity, issue_code, parser_name, status, route_type.
G007 Classify issues into noise buckets: TEST_STALE_PATH, STALE_VAULT_PATH, REAL_DEFECT.
G008 Support CLI filters: --severity, --issue-code, --parser-name, --top.
G009 Write summary under reports_root or --output.
G010 Support --fail-on-issue with exit code 2 when filtered issue_count > 0.
```

### 3.2 Safety Goals

```text
S001 Default read-only file pipeline.
S002 No MySQL connection.
S003 No raw_vault access.
S004 No parsed filesystem access.
S005 No parser invocation.
S006 No repair or cleanup.
S007 Deterministic summary from same input (except generated_at).
S008 Invalid input fails clearly with exit code 1.
```

---

## 4. Non-goals

009 explicitly must not:

```text
NG001 Re-run check-parse-quality.
NG002 Read raw_vault.
NG003 Read parsed artifacts.
NG004 Connect to MySQL or ORM.
NG005 Write DB records.
NG006 Call MarkItDown, MinerU, or magic-pdf.
NG007 Repair, reparse, delete, move, or rename files.
NG008 Clean pytest dirty DB records.
NG009 Modify 008 parse_quality_report.json input (read-only).
NG010 Use LLM to generate summary text.
NG011 Write vector / embedding / curated / project card.
NG012 Introduce schema migration.
NG013 Add DB write behavior without explicit DB Review.
```

---

## 5. In-scope Data Sources

009 may read from:

```text
config/app.yaml          # reports_root only; for default input discovery
008 JSON report file     # --input or latest parse_quality_report_*.json under reports_root
```

009 must not read from:

```text
MySQL
raw_vault filesystem
parsed filesystem
kb_* tables via ORM
```

---

## 6. Input Contract (008 Report)

009 accepts only reports produced by 008 with:

```text
report_type = parse_quality_report
schema_version = 1.0
mode = check
```

Required top-level fields (must exist in input):

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

The 18 stable issue codes in `issue_counts` (from 008):

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

If input schema does not match, 009 must reject with exit code 1.

---

## 7. Output Contract

### 7.1 Markdown Summary (default)

Default path:

```text
{reports_root}/parse_quality_summary_{YYYYMMDDTHHMMSSZ}.md
```

Suggested sections:

```text
1. Source Report Metadata
2. Executive Summary
3. Issue Code Matrix (all 18 codes)
4. By Severity / Parser / Status / Route Type
5. Noise Classification Breakdown
6. Top Issue Samples (truncated by --top)
7. Recommendations (non-mutating; may echo or refine 008 recommendations)
```

### 7.2 JSON Summary (`--format json`)

```json
{
  "report_type": "parse_quality_summary",
  "schema_version": "1.0",
  "mode": "summarize",
  "generated_at": "2026-06-17T00:00:00Z",
  "source_report_path": "/path/to/parse_quality_report.json",
  "source_report_generated_at": "2026-06-16T00:00:00Z",
  "filters": {},
  "summary": {},
  "issue_counts": {},
  "noise_breakdown": {
    "TEST_STALE_PATH": 0,
    "STALE_VAULT_PATH": 0,
    "REAL_DEFECT": 0
  },
  "top_issue_codes": [],
  "recommendations": []
}
```

No other file writes are allowed.

---

## 8. Noise Classification Rules

Each issue in the input `issues[]` array is classified into exactly one bucket:

| Bucket | Rule |
|---|---|
| `TEST_STALE_PATH` | `evidence.error` is `PermissionError`, or `path` / `evidence.path` contains `/tmp/pytest-of-` |
| `STALE_VAULT_PATH` | `issue_code` is `STALE_RAW_VAULT_PATH`, or path contains known stale markers such as `/tmp/p5_reqa_` |
| `REAL_DEFECT` | All other issues |

Summary must report counts per bucket separately from raw severity totals.

---

## 9. Relationship with 008

```text
008 check-parse-quality  ->  parse_quality_report.json
009 summarize-parse-quality -> parse_quality_summary.md | .json
```

009 never replaces 008. It consumes 008 output only.

---

## 10. CLI Contract (Planned — P4 Implementation)

Proposed CLI command:

```bash
PYTHONPATH=backend python -m app.cli.main summarize-parse-quality \
  --config config/app.yaml \
  --input /path/to/parse_quality_report.json \
  --output /path/to/parse_quality_summary.md
```

Parameters:

```text
--config          Read reports_root for default input discovery
--input           Explicit 008 JSON path
--output          Summary output path
--format          markdown (default) | json
--severity        Filter: CRITICAL | ERROR | WARNING | INFO
--issue-code      Filter by issue code (repeatable)
--parser-name     Filter by parser_name
--top             Max sample issues per group (default 20)
--fail-on-issue   Exit 2 when filtered issue_count > 0
```

Exit codes:

```text
0  Success
1  Config / input / schema error
2  --fail-on-issue and filtered issue_count > 0
```

Forbidden parameters:

```text
--fix
--repair
--reparse
--write-db
--markitdown
--mineru
--magic-pdf
--check-parse-quality
```

**Note:** CLI is planned for P4. P1 creates specs only; no implementation in P1.

---

## 11. Role Boundaries for Cursor Agents

| Role | 009 Responsibility |
|---|---|
| Tech Lead Agent | P1 spec/plan, P2/P3 gates, P7 final review. |
| Dev Agent | P4 implementation within whitelist only. |
| QA Agent | P5 unit tests and regression. |
| E2E Agent | P6 real 008 report → summary CLI; verify no DB/raw_vault/parsed access. |

Do not use mixed role names. P5 = QA; P6 = E2E.

---

## 12. DB Review Gate (Expected)

```text
P2/P3 expected outcome: DB Review exemption.
Reason: no MySQL, no ORM, no registry writes.
Allowed side effect: summary Markdown/JSON file only.
```

If P4 proposes MySQL or raw_vault/parsed reads → STOP and return to TL.

---

## 13. P1 STOP Condition

P1 ends after:

```text
specs/009-quality-report-summary/spec.md
specs/009-quality-report-summary/plan.md
specs/009-quality-report-summary/tasks.md
specs/009-quality-report-summary/acceptance.md
specs/009-quality-report-summary/test_cases.md
specs/SPEC_INDEX.md aligned (008 DONE, 009 ACTIVE)
Future stub renumber complete (git mv)
```

After P1, STOP. Do not enter P2/P3/P4 until user approves.

No `backend/**` code in P1.

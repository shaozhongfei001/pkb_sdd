# 009 Parse Quality Report Summary — P6 E2E Validation Report

> Role: E2E Agent  
> Spec: `specs/009-quality-report-summary/`  
> Branch: `feature/009-quality-report-summary`  
> Stage: P6 E2E Validation  
> Base QA commit: `9e0d18d`  
> Input authority: 008 P6 report `/tmp/pkb_sdd_008_p6/parse_quality_report.json`

---

## 1. Gate Conclusion

P6 E2E Validation: **PASS**

009 `summarize-parse-quality` was validated against the real 008 P6 JSON report in the local environment:

- real `config/app.yaml` (for `reports_root` resolution only)
- real 008 `parse_quality_report.json` input
- Markdown and JSON summary output
- input report hash / mtime unchanged
- no MySQL connection observed at runtime
- no raw_vault / parsed filesystem access observed
- project `raw_vault/` and `parsed/` mtimes unchanged

009 may enter **P7 Tech Lead Final Review** after user confirmation.

---

## 2. Input Report

| Field | Value |
|---|---|
| Path | `/tmp/pkb_sdd_008_p6/parse_quality_report.json` |
| Source | 008 P6 E2E output (see `specs/008-parse-quality-checker/p6_e2e_report.md`) |
| SHA256 (before/after) | `191238ad2b59539f793abf6bc351f1823a2ccae7d8772284930b6594e0d0326b` (unchanged) |
| `report_type` | `parse_quality_report` |
| `schema_version` | `1.0` |
| `mode` | `check` |
| `generated_at` | `2026-06-16T16:55:29.592772Z` |
| `issue_count` | 988 |
| `checked_parse_result_count` | 152 |

Input immutability:

```bash
sha256sum "$INPUT_REPORT"  # before == after
stat "$INPUT_REPORT"       # before == after (diff empty)
```

Result: **PASS**

Artifacts:

```text
/tmp/pkb_sdd_009_p6/input.sha256.before
/tmp/pkb_sdd_009_p6/input.sha256.after
/tmp/pkb_sdd_009_p6/input.stat.before
/tmp/pkb_sdd_009_p6/input.stat.after
```

---

## 3. E2E Commands

Environment:

```bash
cd /home/szf/dev/pyws/pkb_sdd
source backend/.venv/bin/activate
mkdir -p /tmp/pkb_sdd_009_p6
INPUT_REPORT=/tmp/pkb_sdd_008_p6/parse_quality_report.json
```

### 3.1 Markdown Summary

```bash
PYTHONPATH=backend python -m app.cli.main summarize-parse-quality \
  --config config/app.yaml \
  --input "$INPUT_REPORT" \
  --output /tmp/pkb_sdd_009_p6/parse_quality_summary.md \
  --format markdown
```

Result:

```text
Exit code: 0
Filtered issues: 988
Noise breakdown: TEST_STALE_PATH=836, STALE_VAULT_PATH=152, REAL_DEFECT=0
Output: /tmp/pkb_sdd_009_p6/parse_quality_summary.md (6814 bytes)
```

### 3.2 JSON Summary

```bash
PYTHONPATH=backend python -m app.cli.main summarize-parse-quality \
  --config config/app.yaml \
  --input "$INPUT_REPORT" \
  --output /tmp/pkb_sdd_009_p6/parse_quality_summary.json \
  --format json
```

Result:

```text
Exit code: 0
Filtered issues: 988
Noise breakdown: TEST_STALE_PATH=836, STALE_VAULT_PATH=152, REAL_DEFECT=0
Output: /tmp/pkb_sdd_009_p6/parse_quality_summary.json (17866 bytes)
```

---

## 4. Output Validation

### 4.1 JSON Schema

Validated fields present:

```text
report_type = parse_quality_summary
schema_version = 1.0
mode = summarize
issue_counts length = 18
noise_breakdown = {TEST_STALE_PATH: 836, STALE_VAULT_PATH: 152, REAL_DEFECT: 0}
summary.input_issue_count = 988
summary.filtered_issue_count = 988
```

All required top-level keys from P3 §8.3 present (no missing keys).

Result: **PASS**

### 4.2 Markdown Structure

Required sections verified:

```text
# Parse Quality Summary
## Source Report
## Executive Summary
## Issue Code Matrix
## Aggregations
## Noise Classification
## Top Issues
## Recommendations
```

Result: **PASS**

---

## 5. Noise Classification Validation

Input issue signals (from 008 report):

| Signal | Count in input |
|---|---:|
| `evidence.error == PermissionError` | 540 |
| path contains `/tmp/pytest-of-` | 836 |

E2E summary `noise_breakdown`:

| Bucket | Count |
|---|---:|
| `TEST_STALE_PATH` | 836 |
| `STALE_VAULT_PATH` | 152 |
| `REAL_DEFECT` | 0 |

Interpretation:

- All 988 input issues classified into noise buckets.
- `TEST_STALE_PATH` count matches pytest-path signal count (836), confirming PermissionError / `/tmp/pytest-of-` priority routing.
- Remaining 152 issues classified as `STALE_VAULT_PATH` (stale temp vault markers such as `/tmp/p5_reqa_*` and other `/tmp/` paths not caught by pytest marker).
- No issues classified as `REAL_DEFECT` on this dataset — consistent with 008 P6 environment dominated by test/stale-path noise.

Result: **PASS**

---

## 6. No-side-effect Validation

### 6.1 Input Report

| Check | Result |
|---|---|
| SHA256 unchanged | PASS |
| mtime/stat unchanged | PASS |

### 6.2 raw_vault / parsed

Sampled project paths:

```text
./raw_vault/**
./parsed/**
```

Before/after mtime snapshots under `/tmp/pkb_sdd_009_p6/` — diff empty.

Result: **PASS**

### 6.3 MySQL

009 CLI / summarizer must not connect to MySQL.

Runtime check (during summarize, `lsof -p $PID`):

```text
no mysql / 3306 / raw_vault / parsed paths in open files
```

External read-only DB row count snapshot (outside 009 process, for environment reference only):

```text
kb_file_content      10
kb_parse_result     164
kb_parsed_artifact  574
kb_raw_vault_object   3
```

009 did not open MySQL sockets; no before/after DB diff required for 009 because the feature is DB-exempt by design.

Result: **PASS**

### 6.4 Forbidden Behavior

Verified in P6:

```text
no check-parse-quality re-invocation
no parser subprocess
no raw_vault/parsed reads
no input JSON mutation
only summary files written under /tmp/pkb_sdd_009_p6/
```

Result: **PASS**

---

## 7. Issues Observed (Informational)

The real 008 report contains large test/stale-path noise (988 issues). 009 correctly surfaces this in `noise_breakdown` without attempting repair, re-check, or DB cleanup.

This matches the 007/008 caveat documented in `SPEC_INDEX.md` §6.

---

## 8. P6 Gate

P6-GATE: **PASS**

009 may enter P7 Tech Lead Final Review.

STOP — P6 completed. No handoff or SPEC_INDEX update in this stage.

# 009 Parse Quality Report Summary — test_cases.md

> Project: `pkb_sdd`  
> Spec: `specs/009-quality-report-summary/`  
> Test owner: QA Agent (P5), E2E Agent (P6)  
> Current phase: P1 planning only — no tests implemented yet.

---

## 1. Test Strategy

009 tests must prove:

```text
1. Valid 008 report ingestion and summary output.
2. Schema validation and rejection paths.
3. All 18 issue_counts preserved in output.
4. Noise classification correctness.
5. CLI filters and exit codes.
6. No MySQL connection.
7. No raw_vault / parsed access.
8. No parser or 008 checker invocation.
9. No regression in 004–008.
```

Recommended test file (P4/P5):

```text
backend/tests/test_parse_quality_report_summarizer.py
```

Fixtures:

```text
tests/fixtures/parse_quality_report_valid.json
tests/fixtures/parse_quality_report_with_noise.json
tests/fixtures/parse_quality_report_empty_issues.json
tests/fixtures/parse_quality_report_invalid_schema.json
```

Fixtures must be minimal synthetic 008 reports; they must not require MySQL, raw_vault, or parsed.

---

## 2. Unit Test Cases

### TC001 — Valid 008 Report → Markdown Summary

Setup:

```text
Fixture with report_type=parse_quality_report, schema_version=1.0, 2 issues.
```

Expected:

```text
Exit 0.
Markdown file created.
Contains executive summary and issue matrix.
issue_counts has all 18 keys.
```

---

### TC002 — Valid 008 Report → JSON Summary

Command / API:

```text
--format json
```

Expected:

```text
report_type=parse_quality_summary
schema_version=1.0
mode=summarize
noise_breakdown present
```

---

### TC003 — Invalid report_type

Setup:

```text
Input report_type=wrong_type.
```

Expected:

```text
Exit 1.
No summary file written (or partial write forbidden).
```

---

### TC004 — Invalid schema_version

Setup:

```text
schema_version=2.0.
```

Expected:

```text
Exit 1.
```

---

### TC005 — Malformed JSON Input

Expected:

```text
Exit 1.
Clear error message.
```

---

### TC006 — Missing Input File

Expected:

```text
Exit 1.
```

---

### TC007 — Empty issues Array

Setup:

```text
Valid schema, issues=[].
```

Expected:

```text
Exit 0.
issue_counts all zero.
Valid summary generated.
```

---

### TC008 — Preserve All 18 Issue Codes

Setup:

```text
Input issue_counts with 3 non-zero codes.
```

Expected:

```text
Output issue_counts contains exactly 18 keys matching 008 ISSUE_CODES.
Non-present codes appear as 0.
```

---

### TC009 — TEST_STALE_PATH Classification

Setup:

```text
Issue with evidence.error=PermissionError.
```

Expected:

```text
noise_breakdown.TEST_STALE_PATH += 1.
```

---

### TC010 — STALE_VAULT_PATH Classification

Setup:

```text
Issue with issue_code=STALE_RAW_VAULT_PATH.
```

Expected:

```text
noise_breakdown.STALE_VAULT_PATH += 1.
```

---

### TC011 — REAL_DEFECT Classification

Setup:

```text
Issue with code MISSING_PARSED_TEXT, no PermissionError.
```

Expected:

```text
noise_breakdown.REAL_DEFECT += 1.
```

---

### TC012 — Classification Priority

Setup:

```text
Issue with PermissionError AND STALE_RAW_VAULT_PATH.
```

Expected:

```text
Classified as TEST_STALE_PATH (priority rule).
```

---

### TC013 — --severity Filter

Setup:

```text
Mix of CRITICAL and ERROR issues.
--severity CRITICAL
```

Expected:

```text
Summary counts and samples only include CRITICAL.
```

---

### TC014 — --issue-code Filter

Setup:

```text
Multiple issue codes in input.
--issue-code MISSING_PARSED_DIR
```

Expected:

```text
Only matching issues in filtered views.
```

---

### TC015 — --parser-name Filter

Expected:

```text
Filtered issues match parser_name when set.
```

---

### TC016 — --top Truncation

Setup:

```text
50 issues in input.
--top 5
```

Expected:

```text
Sample section shows at most 5 issues per aggregation group (per P3 definition).
```

---

### TC017 — --fail-on-issue Exit 2

Setup:

```text
Input with issue_count > 0.
--fail-on-issue
```

Expected:

```text
Exit 2.
Summary still written (unless P3 decides otherwise — default: write then exit 2).
```

---

### TC018 — Chinese Path in Issue

Setup:

```text
Issue path contains Chinese directory/file name.
```

Expected:

```text
Markdown summary displays path correctly (UTF-8).
```

---

### TC019 — Idempotency

Setup:

```text
Run summarize twice on same input with fixed output path (if supported) or compare body excluding generated_at.
```

Expected:

```text
Identical summary content except timestamps.
```

---

## 3. No-side-effect Test Cases

### TC020 — No MySQL Connection

Setup:

```text
Patch create_db_engine / Session / or spy mysql connector.
```

Expected:

```text
No database connection attempted during summarize.
```

---

### TC021 — No raw_vault Access

Setup:

```text
Spy Path operations on configured raw_vault_root or known vault paths.
```

Expected:

```text
No raw_vault path reads.
```

---

### TC022 — No parsed Access

Setup:

```text
Spy Path operations on configured parsed_root.
```

Expected:

```text
No parsed path reads.
```

---

### TC023 — No Parser / 008 Checker Invocation

Setup:

```text
Patch ParseQualityCheckerService and parser services.
```

Expected:

```text
Not called.
```

---

### TC024 — Input Report Not Modified

Setup:

```text
Capture input file mtime and content hash before/after.
```

Expected:

```text
Input JSON unchanged.
```

---

### TC025 — Only Summary Output Written

Setup:

```text
Temp reports_root with one input report.
```

Expected:

```text
Only new summary .md or .json created.
Input report untouched.
```

---

## 4. CLI Test Cases (P5)

### TC026 — CLI Default Markdown

```bash
PYTHONPATH=backend python -m app.cli.main summarize-parse-quality \
  --config config/app.yaml \
  --input /path/to/parse_quality_report.json
```

Expected:

```text
Exit 0.
Markdown summary under reports_root or documented default.
```

---

### TC027 — CLI --output

Expected:

```text
Summary written to explicit --output path.
```

---

### TC028 — CLI Latest Report Discovery

Setup:

```text
reports_root with multiple parse_quality_report_*.json files.
No --input.
```

Expected:

```text
Latest by filename timestamp or generated_at is selected (P3 must define rule).
```

---

## 5. Regression Test Cases

### TC029 — 008 Parse Quality Checker Regression

```bash
PYTHONPATH=backend pytest backend/tests/test_parse_quality_checker.py
```

Expected:

```text
pass
```

---

### TC030 — 004–007 Regression

```bash
PYTHONPATH=backend pytest \
  backend/tests/test_parser_router.py \
  backend/tests/test_markitdown_parser.py \
  backend/tests/test_parse_job_registry.py \
  backend/tests/test_mineru_pdf_parser.py
```

Expected:

```text
pass
```

---

## 6. E2E Test Cases (P6)

### TC031 — Real 008 Report → Summary

Setup:

```text
Use parse_quality_report.json from 008 P6 E2E run.
```

Command:

```bash
PYTHONPATH=backend python -m app.cli.main summarize-parse-quality \
  --config config/app.yaml \
  --input /path/to/parse_quality_report.json \
  --output /tmp/pkb_sdd_009_p6/parse_quality_summary.md
```

Expected:

```text
Summary generated.
noise_breakdown shows TEST_STALE_PATH > 0 if PermissionError issues present.
DB row counts unchanged.
raw_vault / parsed mtimes unchanged.
```

---

## 7. Minimum P5 QA Evidence

```text
009 targeted tests: N passed
004–008 regression: N passed
no MySQL test: passed
no raw_vault/parsed access test: passed
input immutability test: passed
```

---

## 8. Minimum P6 E2E Evidence

```text
CLI command used
input report path
output summary path
noise_breakdown totals
DB sanity check (no connection expected)
raw_vault / parsed mtime check
```

# 008 Parse Quality Checker — test_cases.md

> Project: `pkb_sdd`  
> Spec: `specs/008-parse-quality-checker/`  
> Test owner: QA Agent for P5, E2E Agent for P6  
> Current phase: P1 planning only.

---

## 1. Test Strategy

008 tests must prove:

```text
1. Correct issue detection.
2. Correct aggregation.
3. Stable report schema.
4. CLI filter behavior.
5. No parser invocation.
6. No DB writes.
7. No filesystem mutation except report output.
8. No regression in 004/005/006/007.
```

Recommended test file:

```text
backend/tests/test_parse_quality_checker.py
```

---

## 2. Unit Test Cases

### TC001 — Valid Parsed Artifact Set

Setup:

```text
raw_vault original.bin exists.
parsed_text.md exists.
parsed_metadata.json exists.
parse_manifest.json exists.
manifest fields match DB.
registry artifact paths exist.
```

Expected:

```text
issue_count = 0
no ERROR or CRITICAL issue
report JSON valid
```

---

### TC002 — Missing raw_vault original.bin

Setup:

```text
DB raw_vault object points to non-existing original.bin.
```

Expected:

```text
issue code MISSING_RAW_VAULT_OBJECT
severity ERROR
```

---

### TC003 — Stale /tmp raw_vault Path

Setup:

```text
raw_vault DB path points to /tmp/p5_reqa_xxx/original.bin or similar temp path.
```

Expected:

```text
issue code STALE_RAW_VAULT_PATH
severity WARNING
```

---

### TC004 — Missing Parsed Directory

Setup:

```text
Expected parsed directory does not exist.
```

Expected:

```text
issue code MISSING_PARSED_DIR
severity ERROR
```

---

### TC005 — Missing parsed_text.md

Setup:

```text
parsed directory exists.
parsed_metadata.json exists.
parse_manifest.json exists.
parsed_text.md missing.
```

Expected:

```text
issue code MISSING_PARSED_TEXT
severity ERROR
```

---

### TC006 — Missing parsed_metadata.json

Setup:

```text
parsed_text.md exists.
parse_manifest.json exists.
parsed_metadata.json missing.
```

Expected:

```text
issue code MISSING_PARSED_METADATA
severity ERROR
```

---

### TC007 — Missing parse_manifest.json

Setup:

```text
parsed_text.md exists.
parsed_metadata.json exists.
parse_manifest.json missing.
```

Expected:

```text
issue code MISSING_PARSE_MANIFEST
severity ERROR
```

---

### TC008 — Invalid Manifest JSON

Setup:

```text
parse_manifest.json exists but contains invalid JSON.
```

Expected:

```text
issue code INVALID_PARSE_MANIFEST_JSON
severity ERROR
```

---

### TC009 — Manifest Required Field Missing

Setup:

```text
parse_manifest.json lacks required logical field such as sha256 or parser_name.
```

Expected:

```text
issue code MANIFEST_REQUIRED_FIELD_MISSING
severity ERROR
```

---

### TC010 — Manifest sha256 Mismatch

Setup:

```text
kb_file_content.sha256 = A
manifest.sha256 = B
```

Expected:

```text
issue code MANIFEST_SHA256_MISMATCH
severity CRITICAL
```

---

### TC011 — Manifest content_uid Mismatch

Setup:

```text
expected content_uid = C1
manifest.content_uid = C2
```

Expected:

```text
issue code MANIFEST_CONTENT_UID_MISMATCH
severity CRITICAL
```

---

### TC012 — Invalid parser_name

Setup:

```text
manifest.parser_name is absent from allowed parser set or inconsistent with registry.
```

Expected:

```text
issue code MANIFEST_PARSER_NAME_INVALID
severity ERROR
```

---

### TC013 — Missing parser_adapter_version

Setup:

```text
manifest lacks parser_adapter_version.
```

Expected:

```text
issue code MANIFEST_ADAPTER_VERSION_MISSING
severity ERROR
```

---

### TC014 — Registry Artifact Path Missing

Setup:

```text
kb_parsed_artifact path points to missing file.
```

Expected:

```text
issue code REGISTRY_ARTIFACT_PATH_MISSING
severity ERROR
```

---

### TC015 — Registry SUCCESS but Files Missing

Setup:

```text
kb_parse_result.status = SUCCESS
Required parsed artifact file missing.
```

Expected:

```text
issue code REGISTRY_STATUS_FILE_MISMATCH
severity CRITICAL
```

---

### TC016 — Registry MISSING_MANIFEST Aggregation

Setup:

```text
parse result status or error code indicates missing manifest.
```

Expected:

```text
issue_counts includes REGISTRY_MISSING_MANIFEST_RESULT
by_status includes MISSING_MANIFEST or equivalent existing status
```

---

### TC017 — FAILED Result Aggregation

Setup:

```text
parse result status = FAILED.
```

Expected:

```text
by_status.FAILED increments
issue code REGISTRY_FAILED_RESULT or equivalent warning issue
```

---

### TC018 — EMPTY Result Aggregation

Setup:

```text
parse result status = EMPTY.
```

Expected:

```text
by_status.EMPTY increments
issue code REGISTRY_EMPTY_RESULT or equivalent warning issue
```

---

### TC019 — SKIPPED Result Aggregation

Setup:

```text
parse result status = SKIPPED.
```

Expected:

```text
by_status.SKIPPED increments
issue code REGISTRY_SKIPPED_RESULT or equivalent info issue
```

---

### TC020 — Empty Candidate Set

Setup:

```text
Filter by sha256/content_uid that does not exist.
```

Expected:

```text
checked counts = 0
issue_count = 0
valid report generated
command succeeds
```

---

## 3. CLI Test Cases

### TC021 — CLI Default Scope

Command:

```bash
PYTHONPATH=backend python -m app.cli.main check-parse-quality --config config/app.yaml
```

Expected:

```text
report generated under reports_root
exit code 0
```

---

### TC022 — CLI --limit

Command:

```bash
PYTHONPATH=backend python -m app.cli.main check-parse-quality --config config/app.yaml --limit 5
```

Expected:

```text
checked candidate count <= 5
report.scope.limit = 5
```

---

### TC023 — CLI --sha256

Command:

```bash
PYTHONPATH=backend python -m app.cli.main check-parse-quality --config config/app.yaml --sha256 <sha256>
```

Expected:

```text
report.scope.sha256 = <sha256>
all issues belong to that sha256
```

---

### TC024 — CLI --content-uid

Command:

```bash
PYTHONPATH=backend python -m app.cli.main check-parse-quality --config config/app.yaml --content-uid <content_uid>
```

Expected:

```text
report.scope.content_uid = <content_uid>
all issues belong to that content_uid
```

---

### TC025 — CLI --parser-name

Command:

```bash
PYTHONPATH=backend python -m app.cli.main check-parse-quality --config config/app.yaml --parser-name markitdown
```

Expected:

```text
report.scope.parser_name = markitdown
all inspected parser-scoped records match parser_name when applicable
```

---

### TC026 — CLI --status

Command:

```bash
PYTHONPATH=backend python -m app.cli.main check-parse-quality --config config/app.yaml --status SUCCESS
```

Expected:

```text
report.scope.status = SUCCESS
all inspected parse results match status when applicable
```

---

### TC027 — CLI --output

Command:

```bash
PYTHONPATH=backend python -m app.cli.main check-parse-quality --config config/app.yaml --output /tmp/parse_quality_report_test.json
```

Expected:

```text
report is written to specified output path if allowed by implementation contract
JSON is valid
```

If P3 decides `--output` must remain under reports_root, update this test accordingly.

---

## 4. No-side-effect Test Cases

### TC028 — No DB Write

Setup:

```text
Instrument session or compare row counts before/after.
```

Expected:

```text
No insert/update/delete.
No commit for feature behavior.
```

---

### TC029 — No Parser Invocation

Setup:

```text
Patch or spy MarkItDown/MinerU parser calls and subprocess invocation.
```

Expected:

```text
No parser service method called.
No magic-pdf subprocess called.
```

---

### TC030 — No raw_vault Mutation

Setup:

```text
Capture raw_vault file list and mtimes before/after.
```

Expected:

```text
No raw_vault changes.
```

---

### TC031 — No parsed Mutation

Setup:

```text
Capture parsed file list and mtimes before/after.
```

Expected:

```text
No parsed changes.
```

---

### TC032 — Only Report File Written

Setup:

```text
Use temp reports_root.
Run checker.
```

Expected:

```text
Only parse_quality_report_{UTC}.json is created.
```

---

## 5. Report Schema Test Cases

### TC033 — Top-level Report Schema

Expected top-level keys:

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

---

### TC034 — Issue Item Schema

Each issue must include:

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

Fields may be null only when not applicable.

---

### TC035 — Severity Aggregation

Setup:

```text
Create one CRITICAL, one ERROR, one WARNING, one INFO issue.
```

Expected:

```text
summary.critical_count = 1
summary.error_count = 1
summary.warning_count = 1
summary.info_count = 1
by_severity has all four values
```

---

### TC036 — Recommendations Are Non-mutating

Expected:

```text
recommendations do not claim that 008 automatically fixed anything.
recommendations do not trigger parser or DB writes.
```

---

## 6. Regression Test Cases

### TC037 — 004 Parser Router Regression

Command:

```bash
PYTHONPATH=backend pytest backend/tests/test_parser_router.py
```

Expected:

```text
pass
```

---

### TC038 — 005 MarkItDown Parser Regression

Command:

```bash
PYTHONPATH=backend pytest backend/tests/test_markitdown_parser.py
```

Expected:

```text
pass
```

---

### TC039 — 006 Parse Registry Regression

Command:

```bash
PYTHONPATH=backend pytest backend/tests/test_parse_registry.py
```

Expected:

```text
pass
```

---

### TC040 — 007 MinerU PDF Parser Regression

Command:

```bash
PYTHONPATH=backend pytest backend/tests/test_mineru_pdf_parser.py
```

Expected:

```text
pass
```

---

### TC041 — Full Backend Regression

Command:

```bash
PYTHONPATH=backend pytest backend/tests
```

Expected:

```text
pass
```

If skipped due to environment, QA Agent must document reason.

---

## 7. E2E Test Cases

### TC042 — Real CLI Generates Report

Setup:

```text
Use local dev config and existing DB.
```

Command:

```bash
cd /home/szf/dev/pyws/pkb_sdd
source backend/.venv/bin/activate
PYTHONPATH=backend python -m app.cli.main check-parse-quality --config config/app.yaml --limit 20
```

Expected:

```text
report file generated
report JSON valid
summary visible
```

---

### TC043 — Real CLI Detects Known Stale /tmp Vault Path

Setup:

```text
Use existing environment if stale /tmp vault_path still exists.
```

Expected:

```text
report contains STALE_RAW_VAULT_PATH
```

If no stale path exists, mark as not applicable and use fixture-based unit test as coverage.

---

### TC044 — Real DB Row Counts Unchanged

Setup:

```text
Count relevant DB tables before and after CLI.
```

Expected:

```text
kb_parse_job unchanged
kb_parse_result unchanged
kb_parsed_artifact unchanged
kb_raw_vault_object unchanged
```

---

### TC045 — Real raw_vault / parsed Unchanged

Setup:

```text
Capture file list or mtimes before and after CLI.
```

Expected:

```text
raw_vault unchanged
parsed unchanged
reports_root has one new report
```

---

## 8. Minimum P5 QA Evidence

QA Agent should report:

```text
008 targeted tests: N passed
004/005/006/007 regression: N passed
full backend tests: N passed or skipped with reason
no DB write test: passed
no parser invocation test: passed
no filesystem mutation test: passed
```

---

## 9. Minimum P6 E2E Evidence

E2E Agent should report:

```text
CLI command used
report path
summary.issue_count
top issue codes
DB row count before/after
raw_vault mutation check
parsed mutation check
known caveats
```

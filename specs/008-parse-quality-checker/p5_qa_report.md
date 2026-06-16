cd /home/szf/dev/pyws/pkb_sdd

# 008 Parse Quality Checker — P5 QA Report

> Role: QA Agent
> Spec: specs/008-parse-quality-checker/
> Branch: feature/008-parse-quality-checker
> Stage: P5 QA Test & Regression

---

## 1. Gate Conclusion

P5 QA Test & Regression: PASS

008 Parse Quality Checker passed:

- 008 specialized tests
- 004–007 regression tests
- no DB write review
- no parser/subprocess invocation review
- real-environment --output validation
- P5 PermissionError defect fix validation

008 may enter P6 E2E Validation.

---

## 2. P5 Defect Found and Fixed

### 2.1 Defect Summary

During real-environment --output validation, check-parse-quality scanned historical pytest records in MySQL.

Some records pointed to stale or inaccessible paths under:

    /tmp/pytest-of-root/...

The checker attempted to call filesystem methods such as Path.is_dir(), Path.is_file(), or Path.read_text() on inaccessible paths and raised PermissionError.

This caused the CLI to fail before generating the JSON report.

### 2.2 Expected Behavior

As a quality checker, 008 must not crash on inaccessible paths.

It must convert filesystem access errors into quality issues and continue generating the report.

008 must remain read-only:

- no DB write
- no parser call
- no subprocess call
- no raw_vault modification
- no parsed artifact modification
- no registry modification
- only JSON report output is allowed

### 2.3 Fix Summary

parse_quality_checker.py was updated to safely handle PermissionError and OSError from:

- Path.is_dir()
- Path.is_file()
- Path.read_text()

The fix maps access failures to existing issue codes without changing the 18-code issue taxonomy.

| Scenario | issue_code | severity |
|---|---|---|
| parsed_dir.is_dir() access failure | MISSING_PARSED_DIR | ERROR |
| parsed_text.is_file() access failure | MISSING_PARSED_TEXT | ERROR |
| parsed_metadata.is_file() access failure | MISSING_PARSED_METADATA | ERROR |
| parse_manifest.is_file() access failure | MISSING_PARSE_MANIFEST | ERROR |
| parse_manifest.read_text() access failure | INVALID_PARSE_MANIFEST_JSON | ERROR |
| original_bin.is_file() access failure | MISSING_RAW_VAULT_OBJECT | ERROR |
| registry artifact is_file() access failure | REGISTRY_ARTIFACT_PATH_MISSING | ERROR |

Each issue evidence includes:

- error
- errno
- path

No new issue code was added.

---

## 3. Test Results

### 3.1 008 Specialized Tests

Command:

    PYTHONPATH=backend pytest backend/tests/test_parse_quality_checker.py

Result:

    30 passed

### 3.2 004–007 Regression Tests

Command:

    PYTHONPATH=backend pytest \
      backend/tests/test_parser_router.py \
      backend/tests/test_markitdown_parser.py \
      backend/tests/test_parse_job_registry.py \
      backend/tests/test_mineru_pdf_parser.py

Result:

    127 passed

### 3.3 P5 Real-environment Output Validation

Command:

    mkdir -p /tmp/pkb_sdd_008_qa

    PYTHONPATH=backend python -m app.cli.main check-parse-quality \
      --config config/app.yaml \
      --output /tmp/pkb_sdd_008_qa/parse_quality_report.json

    test -f /tmp/pkb_sdd_008_qa/parse_quality_report.json && echo "output ok"
    python -m json.tool /tmp/pkb_sdd_008_qa/parse_quality_report.json >/dev/null && echo "json ok"

Result:

    Issues: 964
    Critical: 140
    Errors: 676
    Checked parse results: 148
    output ok
    json ok

Report observations:

    PermissionError issues: 540
    MISSING_PARSED_DIR issues: 140
    issue_counts still contains all 18 stable issue codes

The CLI no longer crashes on inaccessible /tmp/pytest-of-root/... paths.

---

## 4. No-side-effect Verification

### 4.1 DB Write Check

Command:

    grep -R "session\\.add\\|session\\.delete\\|session\\.merge\\|session\\.commit" \
      backend/app/services/parse_quality_checker.py backend/app/cli/main.py || true

Result:

    PASS — no session.add/delete/merge/commit found.

### 4.2 Parser and Subprocess Check

Command:

    grep -nE "subprocess|magic-pdf|parse_markitdown\\(|parse_mineru|MarkItDownAdapter|MineruPdfParserService" \
      backend/app/services/parse_quality_checker.py || true

Result:

    PASS — no parser or subprocess call found in parse_quality_checker.py.

Manual CLI review:

    PASS — check-parse-quality only loads config, initializes ParseQualityCheckerService, invokes service.check(), prints summary, and handles exit codes.

Existing parse-markitdown and parse-mineru-pdf commands in backend/app/cli/main.py are pre-existing 005/007 commands and are not invoked by 008.

---

## 5. Acceptance Coverage

Covered in P5:

- 008 unit tests
- 004–007 regression tests
- report generation
- explicit --output path
- JSON validity
- no DB write behavior
- no parser call
- no subprocess call
- inaccessible path handling
- 18-code issue taxonomy stability
- PermissionError/OSError conversion into quality issues

Not completed in P5:

- Full PYTHONPATH=backend pytest backend/tests, unless separately executed.
- P6 mtime validation for real raw_vault and parsed artifacts.
- P6 DB row count before/after validation.

---

## 6. Remaining P6 E2E Scope

P6 must validate in the real environment:

- real config/app.yaml
- real MySQL
- real raw_vault
- real parsed artifacts
- real reports_root

P6 must verify:

- CLI generates report.
- report JSON is valid.
- DB row counts do not change before and after CLI.
- raw_vault file mtimes do not change before and after CLI.
- parsed artifact mtimes do not change before and after CLI.
- stale /tmp/pytest-of-root/... and /tmp/raw_vault/... paths are reported, not repaired.

---

## 7. P5 Gate

P5-GATE: PASS

008 Parse Quality Checker may enter P6 E2E Validation.

STOP — P5 QA completed. No handoff or SPEC_INDEX update in this stage.
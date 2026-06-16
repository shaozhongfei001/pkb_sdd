# 008 Parse Quality Checker — Handoff

> Spec: specs/008-parse-quality-checker/  
> Branch: feature/008-parse-quality-checker  
> Stage: P8 Handoff & Final Commit  
> Status: DONE

---

## 1. Completion Summary

008 Parse Quality Checker has been completed.

The feature provides a read-only consistency checker across:

- raw_vault
- parsed artifacts
- parse_manifest.json
- parse registry records
- parser metadata
- JSON quality report output

The checker reports quality issues only. It does not repair data.

---

## 2. Implemented Scope

Implemented command:

    PYTHONPATH=backend python -m app.cli.main check-parse-quality \
      --config config/app.yaml

Supported options:

- --config
- --sha256
- --content-uid
- --parser-name
- --status
- --limit
- --output
- --fail-on-issue

Implemented files:

- backend/app/services/parse_quality_checker.py
- backend/app/cli/main.py
- backend/tests/test_parse_quality_checker.py

Spec / review / QA / E2E files:

- specs/008-parse-quality-checker/spec.md
- specs/008-parse-quality-checker/plan.md
- specs/008-parse-quality-checker/tasks.md
- specs/008-parse-quality-checker/acceptance.md
- specs/008-parse-quality-checker/test_cases.md
- specs/008-parse-quality-checker/p2_p3_review.md
- specs/008-parse-quality-checker/p5_qa_report.md
- specs/008-parse-quality-checker/p6_e2e_report.md
- specs/008-parse-quality-checker/p7_final_review.md

---

## 3. Report Contract

Default report path:

    {reports_root}/parse_quality_report_{YYYYMMDDTHHMMSSZ}.json

Explicit output path:

    --output /path/to/parse_quality_report.json

Top-level report fields:

- report_type
- schema_version
- generated_at
- mode
- scope
- summary
- issue_counts
- by_parser
- by_status
- by_route_type
- by_severity
- issues
- recommendations

Stable values:

- report_type = parse_quality_report
- schema_version = 1.0
- mode = check

issue_counts contains all 18 stable issue codes, even when count is 0.

---

## 4. Issue Taxonomy

Stable issue codes:

- MISSING_RAW_VAULT_OBJECT
- STALE_RAW_VAULT_PATH
- MISSING_PARSED_DIR
- MISSING_PARSED_TEXT
- MISSING_PARSED_METADATA
- MISSING_PARSE_MANIFEST
- INVALID_PARSE_MANIFEST_JSON
- MANIFEST_REQUIRED_FIELD_MISSING
- MANIFEST_SHA256_MISMATCH
- MANIFEST_CONTENT_UID_MISMATCH
- MANIFEST_PARSER_NAME_INVALID
- MANIFEST_ADAPTER_VERSION_MISSING
- REGISTRY_ARTIFACT_PATH_MISSING
- REGISTRY_STATUS_FILE_MISMATCH
- REGISTRY_MISSING_MANIFEST_RESULT
- REGISTRY_FAILED_RESULT
- REGISTRY_EMPTY_RESULT
- REGISTRY_SKIPPED_RESULT

Severity values:

- CRITICAL
- ERROR
- WARNING
- INFO

---

## 5. Read-only Contract

008 is read-only except for writing the JSON quality report.

Forbidden behavior:

- no MarkItDown call
- no MinerU call
- no magic-pdf call
- no subprocess parser execution
- no DB write
- no migration
- no schema change
- no registry mutation
- no raw_vault modification
- no parsed artifact modification
- no automatic repair
- no --fix / --repair / --reparse / --run-parser / --write-db

P5 and P6 verified that 008 does not modify DB row counts, raw_vault mtimes, or parsed artifact mtimes.

---

## 6. P5 Defect and Fix

P5 found a real defect:

- real-environment check scanned historical pytest DB records
- some records pointed to inaccessible /tmp/pytest-of-root/... paths
- Path.is_dir(), Path.is_file(), or Path.read_text() could raise PermissionError
- CLI failed before generating report

Fix:

- PermissionError / OSError is converted into existing quality issue codes
- evidence includes error, errno, and path
- no new issue code was added
- the 18-code taxonomy remains stable
- CLI now continues and generates a report

P5 verification after fix:

- 008 specialized tests: 30 passed
- 004–007 regression tests: 127 passed
- real-environment --output validation: PASS
- output ok
- json ok

Observed real report summary:

- Issues: 964
- Critical: 140
- Errors: 676
- Checked parse results: 148
- PermissionError issues: 540
- MISSING_PARSED_DIR issues: 140

These are reported only. No repair was performed.

---

## 7. P6 E2E Result

P6 validated 008 against the real local environment:

- real config/app.yaml
- real MySQL
- real raw_vault
- real parsed artifacts
- explicit report output path

P6 verified:

- CLI generated report
- report JSON was valid
- DB row counts unchanged
- raw_vault file mtimes unchanged
- parsed artifact mtimes unchanged
- only JSON report output was created

P6 result:

    PASS

---

## 8. Completed Stage Chain

Relevant commits on feature/008-parse-quality-checker:

- spec(008): add parse quality checker plan
- feat(008): implement parse quality checker
- spec(008): add P2 P3 implementation gate
- fix(008): handle inaccessible paths in quality checker
- test(008): add parse quality checker QA report
- test(008): add parse quality checker E2E report
- review(008): add parse quality checker final review

---

## 9. Residual Caveats

008 may report many issues from historical pytest records, stale /tmp paths, missing artifacts, inaccessible paths, or manifest inconsistencies.

This is expected.

008 does not repair them.

Carried-forward caveats:

- 007 real magic-pdf / MinerU E2E remains separately caveated.
- 008 detects stale or inaccessible paths but does not fix them.
- cleanup / repair workflow is not part of 008.
- human review workflow remains future scope.

---

## 10. Next Stage Suggestion

After 008 is merged to main, the next active spec should be selected only through specs/SPEC_INDEX.md.

Potential next stages may include:

- review workflow
- repair planning
- human review queue
- parse quality report consumption

Do not infer the next stage from directory numbering alone.

---

## 11. Final Status

008 Parse Quality Checker: DONE

Ready to update specs/SPEC_INDEX.md and merge feature/008-parse-quality-checker into main after final checks.
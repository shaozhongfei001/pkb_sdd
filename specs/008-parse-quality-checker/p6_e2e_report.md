# 008 Parse Quality Checker — P6 E2E Validation Report

> Role: E2E Agent
> Spec: specs/008-parse-quality-checker/
> Branch: feature/008-parse-quality-checker
> Stage: P6 E2E Validation

---

## 1. Gate Conclusion

P6 E2E Validation: PASS

008 Parse Quality Checker was validated against the real local environment:

- real config/app.yaml
- real MySQL database
- real raw_vault
- real parsed artifacts
- explicit report output path

The checker generated a JSON report and did not modify DB rows, raw_vault files, or parsed artifact files.

---

## 2. E2E Command

Command:

    PYTHONPATH=backend python -m app.cli.main check-parse-quality \
      --config config/app.yaml \
      --output /tmp/pkb_sdd_008_p6/parse_quality_report.json

Result:

    <PASTE CLI RESULT HERE>

Report path:

    /tmp/pkb_sdd_008_p6/parse_quality_report.json

JSON validation:

    PASS

---

## 3. Report Schema Validation

Observed:

    report_type: <PASTE>
    schema_version: <PASTE>
    mode: <PASTE>
    issue_count: <PASTE>
    checked_parse_result_count: <PASTE>
    issue_codes: <PASTE>

Expected:

    report_type = parse_quality_report
    schema_version = 1.0
    mode = check
    issue_codes = 18

Result:

    PASS

---

## 4. DB Row Count Validation

Before snapshot:

    /tmp/pkb_sdd_008_p6/db_counts_before.tsv

After snapshot:

    /tmp/pkb_sdd_008_p6/db_counts_after.tsv

Diff result:

    DB row counts unchanged

Result:

    PASS

---

## 5. raw_vault / parsed mtime Validation

Before snapshot:

    /tmp/pkb_sdd_008_p6/file_mtimes_before.tsv

After snapshot:

    /tmp/pkb_sdd_008_p6/file_mtimes_after.tsv

Diff result:

    raw_vault and parsed files unchanged

Result:

    PASS

---

## 6. Issues Observed

The generated report may include quality issues such as:

- stale /tmp paths
- inaccessible pytest historical paths
- missing parsed files
- manifest field issues
- registry/file consistency issues

These are reported only.

No automatic repair was performed.

---

## 7. No-side-effect Conclusion

Verified:

- no DB row count change
- no raw_vault file mtime change
- no parsed artifact mtime change
- only JSON report output was created

---

## 8. P6 Gate

P6-GATE: PASS

008 may enter P7 Tech Lead Final Review.

STOP — P6 completed. No handoff or SPEC_INDEX update in this stage.

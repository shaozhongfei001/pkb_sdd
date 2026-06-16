# 008 Parse Quality Checker — acceptance.md

> Project: `pkb_sdd`  
> Spec: `specs/008-parse-quality-checker/`  
> Acceptance scope: read-only quality checker for parsed / registry / raw_vault consistency.

---

## 1. Acceptance Philosophy

008 is accepted only when it proves that it can inspect parse quality and consistency without changing project data.

The checker is a reporting capability, not a repair capability.

---

## 2. Hard Acceptance Gates

### A001 — Active Spec Alignment

008 must follow:

```text
specs/SPEC_INDEX.md
specs/008-parse-quality-checker/
```

It must not implement from:

```text
specs/006-mineru-parser/
specs/007-quality-checker/
specs/008-review-workflow/
```

Pass criteria:

```text
Implementation and docs reference 008-parse-quality-checker as current active spec.
```

---

### A002 — Default Read-only Behavior

Pass criteria:

```text
Default command performs checks and writes only a report file.
No DB records are inserted, updated, deleted, or committed.
No raw_vault or parsed files are changed.
```

---

### A003 — No Parser Invocation

Pass criteria:

```text
008 does not call MarkItDown parser.
008 does not call MinerU parser.
008 does not call magic-pdf.
008 does not spawn parser subprocesses.
```

---

### A004 — No DB Write

Pass criteria:

```text
No session.commit() for feature behavior.
No INSERT / UPDATE / DELETE SQL.
No schema migration.
No new registry records.
```

---

### A005 — No raw_vault Mutation

Pass criteria:

```text
No file under raw_vault is created, modified, moved, renamed, or deleted.
```

---

### A006 — No parsed Mutation

Pass criteria:

```text
No file under parsed is created, modified, moved, renamed, or deleted.
```

---

### A007 — Report Output

Pass criteria:

```text
A JSON report is written to reports_root as parse_quality_report_{UTC}.json.
The report is valid JSON.
The report contains summary, issue_counts, issues, and recommendations.
```

---

### A008 — Detect Missing raw_vault original.bin

Pass criteria:

```text
When raw_vault original.bin is missing, report contains MISSING_RAW_VAULT_OBJECT.
```

---

### A009 — Detect Stale raw_vault Path

Pass criteria:

```text
When vault path points to stale /tmp-like location, report contains STALE_RAW_VAULT_PATH.
```

---

### A010 — Detect Missing parsed Directory

Pass criteria:

```text
When expected parsed directory is missing, report contains MISSING_PARSED_DIR.
```

---

### A011 — Detect Missing parsed_text.md

Pass criteria:

```text
When parsed_text.md is missing, report contains MISSING_PARSED_TEXT.
```

---

### A012 — Detect Missing parsed_metadata.json

Pass criteria:

```text
When parsed_metadata.json is missing, report contains MISSING_PARSED_METADATA.
```

---

### A013 — Detect Missing parse_manifest.json

Pass criteria:

```text
When parse_manifest.json is missing, report contains MISSING_PARSE_MANIFEST.
```

---

### A014 — Detect Invalid Manifest JSON

Pass criteria:

```text
When parse_manifest.json is not valid JSON, report contains INVALID_PARSE_MANIFEST_JSON.
```

---

### A015 — Detect Missing Required Manifest Fields

Pass criteria:

```text
When required manifest fields are missing, report contains MANIFEST_REQUIRED_FIELD_MISSING.
```

---

### A016 — Detect Manifest sha256 Mismatch

Pass criteria:

```text
When manifest sha256 differs from kb_file_content.sha256, report contains MANIFEST_SHA256_MISMATCH.
Severity should be CRITICAL.
```

---

### A017 — Detect Manifest content_uid Mismatch

Pass criteria:

```text
When manifest content_uid differs from expected content_uid, report contains MANIFEST_CONTENT_UID_MISMATCH.
Severity should be CRITICAL.
```

---

### A018 — Detect Invalid parser_name

Pass criteria:

```text
When parser_name is not allowed or inconsistent with registry, report contains MANIFEST_PARSER_NAME_INVALID or equivalent approved issue code.
```

---

### A019 — Detect Missing parser_adapter_version

Pass criteria:

```text
When parser_adapter_version is missing, report contains MANIFEST_ADAPTER_VERSION_MISSING.
```

---

### A020 — Validate Registry Artifact Paths

Pass criteria:

```text
When kb_parsed_artifact path points to a missing file, report contains REGISTRY_ARTIFACT_PATH_MISSING.
```

---

### A021 — Detect Registry Status vs File Mismatch

Pass criteria:

```text
When registry status indicates SUCCESS but required parsed artifacts are missing, report contains REGISTRY_STATUS_FILE_MISMATCH.
Severity should be CRITICAL.
```

---

### A022 — Aggregate MISSING_MANIFEST

Pass criteria:

```text
Registry missing-manifest cases are counted under issue_counts and by_status.
```

---

### A023 — Aggregate FAILED / EMPTY / SKIPPED

Pass criteria:

```text
FAILED, EMPTY, and SKIPPED parse results are aggregated without treating all as fatal implementation errors.
```

---

### A024 — CLI Supports Basic Filters

Pass criteria:

```text
CLI supports:
--config
--sha256
--content-uid
--parser-name
--status
--limit
--output
```

Implementation may defer optional filters only if Tech Lead explicitly approves before P4.

---

### A025 — Empty Candidate Set Is Handled

Pass criteria:

```text
When no candidates match filters, command still writes valid report with checked counts = 0 and issue_count = 0.
```

---

### A026 — Report Schema Stability

Pass criteria:

```text
Report has stable top-level fields:
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

### A027 — Deterministic Issue Codes

Pass criteria:

```text
Issue codes are stable strings and are covered by tests.
No free-form issue code generation.
```

---

### A028 — No New Manifest Contract

Pass criteria:

```text
008 validates the existing 005/007 manifest contract.
008 does not require parsers to emit a new manifest shape.
```

---

### A029 — Previous Stage Regression

Pass criteria:

```text
004 parser router tests pass.
005 MarkItDown parser tests pass.
006 parse registry tests pass.
007 MinerU PDF parser adapter tests pass.
Full backend tests pass if feasible.
```

---

### A030 — Handoff Completeness

Pass criteria:

```text
Handoff documents:
implemented files
CLI usage
test results
known caveats
no-side-effect evidence
next stage recommendation
```

---

## 3. P1 Acceptance

For P1 only, acceptance is:

```text
P1-A001 spec.md exists.
P1-A002 plan.md exists.
P1-A003 tasks.md exists.
P1-A004 acceptance.md exists.
P1-A005 test_cases.md exists.
P1-A006 Cursor role work allocation is explicit.
P1-A007 P1 stops before implementation.
```

---

## 4. Rejection Conditions

Reject 008 if any of the following occurs:

```text
R001 It calls a parser.
R002 It modifies raw_vault.
R003 It modifies parsed artifacts.
R004 It writes DB records.
R005 It changes schema.
R006 It changes 005/006/007 contracts.
R007 It uses deprecated stubs as authority.
R008 It performs LLM semantic quality judgment.
R009 It auto-repairs data.
R010 It lacks no-side-effect tests.
```

---

## 5. Minimum Test Evidence for Final Acceptance

Final acceptance requires evidence similar to:

```text
008 targeted tests: passed
004/005/006/007 regression tests: passed
backend full tests: passed or justified if skipped
real CLI E2E: passed
report JSON validation: passed
DB no-write check: passed
raw_vault/parsed no-mutation check: passed
```

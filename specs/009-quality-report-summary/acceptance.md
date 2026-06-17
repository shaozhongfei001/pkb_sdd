# 009 Parse Quality Report Summary — acceptance.md

> Project: `pkb_sdd`  
> Spec: `specs/009-quality-report-summary/`  
> Acceptance scope: read-only consumption of 008 JSON report; Markdown / JSON summary output only.

---

## 1. Acceptance Philosophy

009 is accepted only when it proves that it can summarize 008 quality reports without accessing MySQL, raw_vault, parsed, or parsers.

The summarizer is a reporting capability, not a repair or re-check capability.

---

## 2. Hard Acceptance Gates (Final — P7)

### A001 — Active Spec Alignment

009 must follow:

```text
specs/SPEC_INDEX.md
specs/009-quality-report-summary/
```

It must not implement from:

```text
specs/008-review-workflow/
specs/010-evidence-chain/   (future stub)
specs/006-mineru-parser/
specs/007-quality-checker/
```

Pass criteria:

```text
Implementation and docs reference 009-quality-report-summary as current active spec.
```

---

### A002 — Pure Report Pipeline

Pass criteria:

```text
Input is only 008 parse_quality_report.json (+ config for reports_root).
No MySQL connection or ORM session.
No raw_vault filesystem access.
No parsed filesystem access.
```

---

### A003 — No Parser Invocation

Pass criteria:

```text
009 does not call MarkItDown, MinerU, magic-pdf, or check-parse-quality.
No parser subprocesses.
```

---

### A004 — No DB Write

Pass criteria:

```text
No session.commit() for feature behavior.
No INSERT / UPDATE / DELETE.
No schema migration.
```

---

### A005 — No Filesystem Mutation Except Summary Output

Pass criteria:

```text
Does not modify 008 input JSON.
Does not modify raw_vault or parsed.
Creates only summary Markdown or JSON under reports_root or --output.
```

---

### A006 — Input Validation

Pass criteria:

```text
Rejects wrong report_type or schema_version with exit 1.
Accepts valid 008 report with report_type=parse_quality_report, schema_version=1.0.
```

---

### A007 — Preserve 18 Issue Codes

Pass criteria:

```text
Output issue_counts contains all 18 stable codes from 008, even when count is 0.
Codes match 008 ISSUE_CODES tuple exactly.
```

---

### A008 — Noise Classification

Pass criteria:

```text
Each issue classified into exactly one of:
TEST_STALE_PATH, STALE_VAULT_PATH, REAL_DEFECT.
Summary reports per-bucket counts.
PermissionError evidence => TEST_STALE_PATH.
STALE_RAW_VAULT_PATH issue_code => STALE_VAULT_PATH (unless already TEST_STALE_PATH).
```

---

### A009 — Markdown Summary Output

Pass criteria:

```text
Default --format markdown produces readable .md file.
Contains executive summary, issue matrix, noise breakdown, recommendations section.
```

---

### A010 — JSON Summary Output

Pass criteria:

```text
--format json produces valid JSON with:
report_type=parse_quality_summary
schema_version=1.0
mode=summarize
noise_breakdown
issue_counts (18 codes)
```

---

### A011 — CLI Filters

Pass criteria:

```text
CLI supports --config, --input, --output, --format, --severity, --issue-code, --parser-name, --top, --fail-on-issue.
```

---

### A012 — Exit Codes

Pass criteria:

```text
0 on success.
1 on config/input/schema error.
2 when --fail-on-issue and filtered issue_count > 0.
```

---

### A013 — Idempotency

Pass criteria:

```text
Same input + filters => identical summary body except generated_at / filename timestamp.
```

---

### A014 — No Repair Behavior

Pass criteria:

```text
No --fix, --repair, --reparse flags.
Recommendations are non-mutating.
Does not clean pytest DB records.
```

---

### A015 — Regression

Pass criteria:

```text
004–008 regression tests pass.
009 targeted tests pass.
```

---

### A016 — Handoff Completeness (P8)

Pass criteria:

```text
Handoff documents CLI usage, test results, pure-pipeline evidence, next-stage recommendation.
```

---

## 3. P1 Acceptance

For P1 only:

```text
P1-A001 spec.md exists under specs/009-quality-report-summary/.
P1-A002 plan.md exists.
P1-A003 tasks.md exists.
P1-A004 acceptance.md exists.
P1-A005 test_cases.md exists.
P1-A006 SPEC_INDEX marks 008 DONE and 009 ACTIVE.
P1-A007 SPEC_INDEX marks 008-review-workflow as FUTURE STUB / NOT CURRENT.
P1-A008 Future stub renumber complete; no two 009 semantics.
P1-A009 No backend/** files modified.
P1-A010 P1 stops before P2/P3/P4.
```

---

## 4. Rejection Conditions

Reject 009 if any of the following occurs:

```text
R001 Connects to MySQL or uses ORM for feature behavior.
R002 Reads raw_vault or parsed filesystem.
R003 Calls parser or re-invokes check-parse-quality.
R004 Modifies 008 input report, raw_vault, or parsed.
R005 Writes DB records or changes schema.
R006 Performs repair or pytest cleanup.
R007 Uses LLM for summary generation.
R008 Uses deprecated or future stubs as authority.
R009 Drops any of the 18 issue codes from output.
R010 Lacks tests proving no MySQL / no vault / no parsed access.
```

---

## 5. Minimum Test Evidence for Final Acceptance

```text
009 targeted tests: passed
004–008 regression: passed
real 008 report → summary E2E: passed
no MySQL connection test: passed
no raw_vault/parsed access test: passed
only summary file written: passed
```

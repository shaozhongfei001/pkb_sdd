# 009 Parse Quality Report Summary — plan.md

> Project: `pkb_sdd`  
> Phase: `P1 Tech Lead Plan — COMPLETE (awaiting user review)`  
> Status: `ACTIVE SPEC / NOT IMPLEMENTED`  
> Implementation status: `NOT STARTED (P4 blocked until P1 approved)`

---

## 1. Architecture Overview

009 introduces a read-only summarizer that consumes 008 JSON output only:

```text
parse_quality_report.json (008)
        |
        v
ParseQualityReportSummarizerService   [P4]
        |
        v
parse_quality_summary_{UTC}.md | .json
```

Proposed component (P4 — not implemented in P1):

```text
backend/app/services/parse_quality_report_summarizer.py
```

Proposed CLI integration (P4):

```text
backend/app/cli/main.py   # register summarize-parse-quality
```

Proposed tests (P5):

```text
backend/tests/test_parse_quality_report_summarizer.py
```

The summarizer must not invoke 008 checker, parser services, or database layers.

---

## 2. Logical Flow

```text
1. Load config (reports_root only).
2. Resolve input:
   2.1 Use --input if provided.
   2.2 Else find latest parse_quality_report_*.json under reports_root.
3. Read and parse JSON.
4. Validate report_type and schema_version.
5. Apply CLI filters (--severity, --issue-code, --parser-name).
6. Classify each issue into noise bucket.
7. Aggregate summaries (preserve 18 issue_counts from input).
8. Render Markdown or JSON summary.
9. Write output to --output or default reports_root path.
10. Return exit code.
```

No step may open MySQL, raw_vault, or parsed paths.

---

## 3. Service Design (Planned — P4)

### 3.1 Proposed Class

```python
class ParseQualityReportSummarizerService:
    def __init__(self, config: AppConfig) -> None: ...

    def summarize(
        self,
        *,
        input_path: Path | None = None,
        output: Path | None = None,
        output_format: str = "markdown",
        severity: str | None = None,
        issue_codes: list[str] | None = None,
        parser_name: str | None = None,
        top: int = 20,
    ) -> ParseQualitySummaryResult:
        ...
```

Final P4 signatures may adjust to match project conventions.

### 3.2 Internal Concepts

```text
ParseQualitySummaryResult
  Holds output path, counts, noise_breakdown, exit hint.

NoiseBucket
  TEST_STALE_PATH | STALE_VAULT_PATH | REAL_DEFECT

IssueSample
  Truncated issue row for Markdown display.
```

### 3.3 ISSUE_CODES Alignment

The 18 issue codes must match 008 `parse_quality_checker.py` `ISSUE_CODES` tuple exactly. P4 may duplicate the tuple or extract to a shared constants module only if TL approves in P3; default is duplicate + test assertion against 008 list.

---

## 4. Config Usage

009 reads only:

```text
config.reports_root   # default input discovery + default output directory
```

009 must not read:

```text
database DSN / session factory
raw_vault_root
parsed_root
```

If `AppConfig` loading currently requires DB fields, P3 must define a read-only config access pattern that does not open MySQL during summarize.

---

## 5. Markdown Renderer (Planned)

Markdown output is the default human triage artifact.

Minimum sections:

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

Renderer must handle:

```text
- Chinese paths in issue.path
- Null optional fields
- Large issue lists (truncate with --top)
- Zero-issue reports
```

---

## 6. JSON Summary Renderer (Planned)

When `--format json`:

```text
report_type = parse_quality_summary
schema_version = 1.0
mode = summarize
```

Must include `noise_breakdown` and full `issue_counts` (18 codes).

---

## 7. Noise Classification Implementation Notes

Classification uses only fields already present in 008 issue items:

```text
issue_code
path
evidence.error
evidence.path
evidence.errno
```

Priority (first match wins):

```text
1. TEST_STALE_PATH
2. STALE_VAULT_PATH
3. REAL_DEFECT
```

Do not re-stat filesystem paths during classification.

---

## 8. CLI Design (Planned — P4)

Command name:

```text
summarize-parse-quality
```

Registration location:

```text
backend/app/cli/main.py
```

Help text must state clearly:

```text
Read-only summary of 008 parse_quality_report.json.
Does not connect to MySQL, raw_vault, or parsed.
Does not repair issues.
```

---

## 9. Dev File Whitelist (P3/P4 Reference)

**Allowed (P4):**

```text
backend/app/services/parse_quality_report_summarizer.py   # new
backend/app/cli/main.py
backend/tests/test_parse_quality_report_summarizer.py       # new
```

**Forbidden:**

```text
backend/app/services/parse_quality_checker.py
backend/app/services/inventory_scanner.py
backend/app/services/file_content_vault.py
backend/app/services/markitdown_parser.py
backend/app/services/mineru_pdf_parser.py
backend/app/services/parse_registry.py
sql/**
```

---

## 10. Exception Handling

| Scenario | Handling |
|---|---|
| Input file missing | Exit 1, clear error message |
| Invalid JSON | Exit 1 |
| Wrong report_type / schema_version | Exit 1 |
| Empty issues array | Exit 0, valid summary with zero counts |
| reports_root missing | Exit 1 |
| Output path not writable | Exit 1 |

---

## 11. Idempotency

```text
Same input JSON + same filters + same format
=> identical summary content except generated_at and output filename timestamp.
```

---

## 12. P1 Deliverables Checklist

```text
[x] spec.md
[x] plan.md
[x] tasks.md
[x] acceptance.md
[x] test_cases.md
[x] SPEC_INDEX.md updated
[x] Future stub renumber via git mv
[ ] backend/** implementation        # explicitly out of P1 scope
[ ] STOP — await user P1 review
```

---

## 13. P1 STOP

No P2/P3/P4 work until user approves P1.

No `backend/**` changes in P1.

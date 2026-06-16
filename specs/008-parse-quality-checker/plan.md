# 008 Parse Quality Checker — plan.md

> Project: `pkb_sdd`  
> Phase: `P1 Tech Lead Plan`  
> Status: `PLANNED`  
> Implementation status: `NOT STARTED`

---

## 1. Architecture Overview

008 introduces a read-only quality checker that inspects consistency across:

```text
MySQL registry tables
raw_vault filesystem
parsed filesystem
parse_manifest.json
reports_root
```

Proposed component:

```text
backend/app/services/parse_quality_checker.py
```

Proposed CLI integration:

```text
backend/app/cli/main.py
```

Proposed tests:

```text
backend/tests/test_parse_quality_checker.py
```

The checker must not invoke parser services. It should be a validator/report generator, not a repair tool.

---

## 2. Logical Flow

```text
1. Load config.
2. Resolve DB connection and configured roots:
   - raw_vault root
   - parsed root
   - reports_root
3. Select candidate content / parse results / artifacts using filters.
4. For each candidate:
   4.1 Check raw_vault original.bin.
   4.2 Check parsed directory.
   4.3 Check parsed_text.md.
   4.4 Check parsed_metadata.json.
   4.5 Check parse_manifest.json.
   4.6 Parse and validate manifest JSON.
   4.7 Compare manifest fields with DB identity fields.
   4.8 Validate registry artifact paths.
   4.9 Compare registry status with filesystem state.
5. Aggregate issues.
6. Write parse_quality_report_{UTC}.json to reports_root.
7. Return CLI exit code and summary.
```

---

## 3. Service Design

### 3.1 Proposed Class

```python
class ParseQualityCheckerService:
    def __init__(self, config: AppConfig, session_factory: SessionFactory): ...

    def check(
        self,
        sha256: str | None = None,
        content_uid: str | None = None,
        parser_name: str | None = None,
        status: str | None = None,
        limit: int | None = None,
        output: Path | None = None,
    ) -> ParseQualityReport:
        ...
```

The final implementation may adjust signatures to match existing project conventions.

### 3.2 Internal Concepts

```text
ParseQualityCandidate
  Represents one content/parse-result/artifact inspection unit.

ParseQualityIssue
  Represents one issue with:
  - issue_code
  - severity
  - content_uid
  - sha256
  - parser_name
  - parser_adapter_version
  - artifact_type
  - path
  - message
  - evidence

ParseQualityReport
  Represents the full output contract.
```

Implementation may use dataclasses or Pydantic models if consistent with existing code style.

---

## 4. CLI Design

### 4.1 Command

```bash
PYTHONPATH=backend python -m app.cli.main check-parse-quality \
  --config config/app.yaml
```

### 4.2 Filters

```bash
--sha256 <sha256>
--content-uid <content_uid>
--parser-name <parser_name>
--status <status>
--limit <N>
--output <report_path>
```

### 4.3 Exit Code Policy

Recommended:

```text
0 = command executed successfully; report generated.
1 = command failed due to configuration, DB, or unexpected runtime error.
2 = quality issues found and --fail-on-issue is explicitly set.
```

For 008 initial implementation, `--fail-on-issue` is optional and should not be required for acceptance.

### 4.4 Explicitly Rejected CLI Options

Do not add:

```text
--fix
--repair
--reparse
--run-parser
--markitdown
--mineru
--magic-pdf
--write-db
```

---

## 5. Data Read Plan

### 5.1 Required Tables

Read only:

```text
kb_file_content
kb_file_instance
kb_raw_vault_object
kb_parse_job
kb_parse_result
kb_parsed_artifact
```

### 5.2 DB Write Rule

008 must not call:

```text
session.add()
session.delete()
session.merge()
session.commit()
bulk_insert
bulk_update
raw INSERT / UPDATE / DELETE SQL
migration
```

If implementation needs DB writes, STOP and enter DB Review.

### 5.3 Candidate Selection

Candidate selection should support:

```text
all registered parse results
all parsed artifacts
specific sha256
specific content_uid
specific parser_name
specific status
limited sample
```

Recommended default:

```text
registered parse results and artifacts only
```

Reason:

```text
008 checks post-parse quality. It should not require every file in inventory to have parsed artifacts.
```

A later spec may add route-planned-but-unparsed coverage.

---

## 6. Filesystem Check Plan

### 6.1 raw_vault

Expected raw vault contract:

```text
raw_vault/by_hash/{sha256[:2]}/{sha256}/original.bin
```

Checks:

```text
1. DB vault path exists.
2. DB vault path is not stale temp path.
3. original.bin exists.
4. original.bin is a file.
```

### 6.2 parsed

Expected parsed contract:

```text
parsed/by_hash/{sha256[:2]}/{sha256[2:4]}/{sha256}/
  parsed_text.md
  parsed_metadata.json
  parse_manifest.json
```

Checks:

```text
1. parsed directory exists.
2. parsed_text.md exists.
3. parsed_metadata.json exists.
4. parse_manifest.json exists.
5. JSON files are valid JSON.
6. parsed_text.md can be empty only if registry status explicitly indicates EMPTY.
```

### 6.3 Registry Artifact Paths

For each `kb_parsed_artifact`:

```text
1. artifact path exists.
2. artifact path is under configured parsed root unless existing contract allows otherwise.
3. artifact_type matches expected file when possible.
```

---

## 7. Manifest Validation Plan

Validate manifest against existing 005/007 contract.

Minimum logical checks:

```text
content_uid is present.
sha256 is present.
parser_name is present.
parser_adapter_version is present.
parser_profile is present or intentionally nullable per existing contract.
status is present.
artifact references are present when status is SUCCESS.
```

Consistency checks:

```text
manifest.sha256 == kb_file_content.sha256
manifest.content_uid == expected content_uid
manifest.parser_name == kb_parse_result.parser_name or kb_parsed_artifact.parser_name
manifest.parser_adapter_version == registry adapter version when available
```

Do not create a new manifest schema in 008.

---

## 8. Issue Severity Model

| Severity | Use Case |
|---|---|
| `CRITICAL` | Registry success is contradicted by missing artifact; identity mismatch. |
| `ERROR` | Required file or required manifest field is missing. |
| `WARNING` | Suspicious or review-worthy condition. |
| `INFO` | Informational distribution, skipped status, empty scope. |

---

## 9. Report Schema

The report must include:

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

Recommendations must be non-mutating, for example:

```text
"Re-run copy-to-vault for missing raw vault object after manual review."
"Re-run parser only after raw vault sample is restored."
"Review stale /tmp vault path and rebuild vault object if needed."
```

Do not include automated repair instructions as executable commands unless explicitly marked as manual and outside 008.

---

## 10. No-side-effect Rules

008 may write only:

```text
reports_root/parse_quality_report_{UTC}.json
```

008 must not write:

```text
raw_vault/**
parsed/**
curated/**
vector/**
project_card/**
DB tables
schema migrations
```

Tests must verify no side effects.

---

## 11. Cursor Role Work Allocation

### 11.1 Tech Lead Agent

Owns:

```text
P1 specs five-file set
P2 DB/Data Read Review
P3 implementation whitelist
P7 final review
P8 handoff quality
```

Must decide:

```text
1. Exact scope of candidate selection.
2. Issue taxonomy.
3. Acceptance gates.
4. Whether implementation is allowed to proceed.
```

Must not code in P1.

### 11.2 Dev Agent

Owns after P3:

```text
backend/app/services/parse_quality_checker.py
backend/app/cli/main.py
backend/tests/test_parse_quality_checker.py only if test scaffolding is part of implementation task
```

Must obey whitelist:

```text
Allowed:
- add new service
- add new CLI command
- add unit tests
- add report fixture if needed

Forbidden:
- schema migration
- DB write
- parser invocation
- changing existing parser behavior
- changing 005/006/007 contracts
```

### 11.3 QA Agent

Owns:

```text
unit test coverage
regression test coverage
no-side-effect verification
issue taxonomy verification
report schema verification
```

Must run at minimum:

```bash
PYTHONPATH=backend pytest backend/tests/test_parse_quality_checker.py
PYTHONPATH=backend pytest backend/tests/test_parser_router.py backend/tests/test_markitdown_parser.py backend/tests/test_parse_registry.py backend/tests/test_mineru_pdf_parser.py
PYTHONPATH=backend pytest backend/tests
```

Exact test file names may be adjusted to the real repository.

### 11.4 E2E Agent

Owns after implementation:

```text
real CLI execution
real DB read verification
real filesystem report generation
manual inspection of produced report
confirmation that raw_vault and parsed are unchanged
```

E2E Agent must not run parser as part of 008 acceptance.

---

## 12. Implementation Whitelist

Implementation phase may create or modify:

```text
backend/app/services/parse_quality_checker.py
backend/app/cli/main.py
backend/tests/test_parse_quality_checker.py
docs/handoff-008-parse-quality-checker.md
specs/008-parse-quality-checker/*
```

Implementation phase must not modify unless explicitly approved:

```text
backend/app/services/markitdown_parser.py
backend/app/services/mineru_pdf_parser.py
backend/app/services/parse_registry.py
backend/app/models/*
backend/migrations/*
config/app.yaml
raw_vault/**
parsed/**
```

---

## 13. Testing Strategy

### 13.1 Unit Tests

Mock DB rows and temp filesystem:

```text
valid parsed set
missing raw vault
stale vault path
missing parsed_text.md
missing parsed_metadata.json
missing parse_manifest.json
invalid manifest JSON
manifest sha256 mismatch
registry success but file missing
empty candidate set
```

### 13.2 Regression Tests

Run previous stage tests:

```text
003 duplicate governance
004 parser router
005 MarkItDown parser
006 parse registry
007 MinerU PDF parser adapter
```

008 must not break completed contracts.

### 13.3 E2E Tests

Use a controlled test config or local dev DB.

Validate:

```text
CLI produces report.
Report JSON is parseable.
Report is under reports_root.
No parser command is invoked.
No DB writes occur.
No raw_vault / parsed mutations occur.
```

---

## 14. Rollout Plan

```text
P1 Tech Lead Plan
  Create five specs files; STOP.

P2 DB/Data Read Review
  Inspect existing models and registry service read patterns.
  Confirm no migration and no DB write.

P3 Implementation Plan
  Create allowed file whitelist and exact CLI contract.

P4 Dev Implementation
  Implement service and CLI.

P5 QA Test & Regression
  Add/execute tests and no-side-effect checks.

P6 E2E Validation
  Run real CLI against dev environment.

P7 TL Final Review
  Review report, tests, caveats, contract compliance.

P8 Commit & Handoff
  Commit implementation and handoff docs.
```

---

## 15. Open Questions for P2

P1 does not require answers to these, but P2 must resolve them before coding:

```text
Q001 Exact ORM model names and field names for parse registry tables.
Q002 Exact manifest field names emitted by 005 and 007.
Q003 Existing config object names for raw_vault, parsed, and reports_root.
Q004 Whether route_type can be reliably joined from existing tables.
Q005 Whether artifact paths are absolute or relative in registry.
Q006 Whether parser_name allowed values are already centralized.
```

If any answer implies schema modification or DB writes, STOP and enter DB Review.

# 009 Parse Quality Report Summary — P2/P3 Tech Lead Review

> Role: Tech Lead Agent  
> Spec: `specs/009-quality-report-summary/`  
> Branch: `feature/009-quality-report-summary`  
> Base commit: `e1cfac3` (P1 approved)  
> Stage: P2 TL Read Review + P3 Implementation Gate

---

## 1. Gate Conclusion

P2 TL Read Review: **PASS**  
P3 Implementation Gate: **PASS**

Conclusion:

`009 Parse Quality Report Summary` is approved to enter **P4 Dev Implementation** only after explicit user confirmation.

This stage remains a **pure file pipeline**: read existing 008 JSON report → write Markdown / JSON summary only.

---

## 2. P2 — Data & Side-effect Read Review

### 2.1 Read Surface Matrix

| Data source | 009 reads? | Decision |
|---|---|---|
| MySQL / ORM / `create_db_engine` | **No** | Forbidden. 009 must not import or call DB layers. |
| `raw_vault` filesystem | **No** | Forbidden. Stale/missing vault facts come only from 008 `issues[]`. |
| `parsed` filesystem | **No** | Forbidden. Parsed defects come only from 008 `issues[]`. |
| Parse registry tables | **No** | Forbidden at runtime. Registry-related findings are already materialized in 008 report fields (`issue_code`, `issues[]`, aggregations). |
| `config/app.yaml` | **Yes (limited)** | Allowed: YAML load via `load_config()`; use **`config.storage.reports_root` only** at runtime. |
| 008 `parse_quality_report.json` | **Yes (primary)** | Required input contract. |

### 2.2 Does 009 Read MySQL?

**No.**

Codebase truth (`backend/app/core/config.py`):

- `load_config()` parses YAML into `AppConfig` dataclass only.
- MySQL connection requires separate `create_db_engine()` / `create_session_factory()` usage (as in 008 checker).

P3 locked rule for P4:

```text
ParseQualityReportSummarizerService must NOT import:
  app.core.database.create_db_engine
  app.core.database.create_session_factory
  sqlalchemy.orm.Session / sessionmaker
  app.models.*
```

P5 must spy/patch DB factory and assert zero connection attempts.

### 2.3 Does 009 Read raw_vault / parsed?

**No.**

009 must not:

- read `config.storage.raw_vault_root` or `config.storage.parsed_root` for feature logic
- stat/open paths under those roots
- import `vault_paths` or `parsed_paths` for summarization

Path strings inside 008 `issues[].path` and `issues[].evidence.path` are **opaque text** used for noise classification only.

### 2.4 Does 009 Read Registry?

**No direct registry access.**

008 already aggregates registry mismatch codes:

```text
REGISTRY_ARTIFACT_PATH_MISSING
REGISTRY_STATUS_FILE_MISMATCH
REGISTRY_MISSING_MANIFEST_RESULT
REGISTRY_FAILED_RESULT
REGISTRY_EMPTY_RESULT
REGISTRY_SKIPPED_RESULT
```

009 summarizes these from the input JSON only.

### 2.5 Does 009 Read Only 008 parse_quality_report.json?

**Yes — feature input is exclusively the 008 JSON report file.**

Allowed ancillary read:

```text
config/app.yaml   # to resolve reports_root for default input discovery and default output dir
```

Not allowed:

```text
invoke check-parse-quality to regenerate report
read any other report types as primary input
```

### 2.6 DB Review Required?

**No. DB Review EXEMPT.**

Reason:

| Check | Result |
|---|---|
| Schema change | None |
| Migration | None |
| ORM session | None |
| DB read at runtime | None |
| DB write | None |
| Registry backfill | None |

P2-GATE: **PASS**  
DB write review: **WAIVED — pure file pipeline, zero DB I/O**

### 2.7 Schema Migration Required?

**No.**

### 2.8 Data Write Risk

| Write target | Risk | Decision |
|---|---|---|
| MySQL | None if P4 follows gate | No ORM / no DML |
| raw_vault | None if P4 follows gate | No vault reads/writes |
| parsed | None if P4 follows gate | No parsed reads/writes |
| 008 input JSON | Overwrite risk | Input must be **read-only** |
| Summary output file | Expected | Only allowed mutation |

Side effect allowed:

```text
Write one parse_quality_summary_{UTC}.md or .json under reports_root or --output
```

### 2.9 README.md P1 Change Summary (Reference for P2)

P1 updated `README.md` only as index/reference sync — **not** functional backend documentation:

| Section | Change |
|---|---|
| Directory tree (§项目结构) | Added `008-parse-quality-checker/`, `009-quality-report-summary/`; renumbered future stubs `010`–`013` |
| §8.9 | `008-review-workflow` labeled **FUTURE STUB / NOT CURRENT** with pointer to `SPEC_INDEX.md` |
| §9 | Added authority note → `SPEC_INDEX.md`; §9.1 documents active 009 boundary summary |
| §9.2–9.7 | Renumbered former 009–012 future specs to 010–013 + deployment/test dataset sections |
| §阶段二 | Roadmap list aligned to `009-quality-report-summary` + renumbered futures |

No README change alters 009 runtime behavior. P4 does not require README edits unless CLI help references are added in a later handoff doc.

---

## 3. P2 — Contract Conflict Review

No blocking conflict between 009 and completed 001–008 contracts.

| Dimension | 009 Design | Upstream contract | Decision |
|---|---|---|---|
| Input authority | 008 `parse_quality_report.json` | 008 output schema 1.0 | Aligned |
| issue_codes | 18 stable codes | 008 `ISSUE_CODES` tuple | Must match exactly |
| Side effect | Summary file only | Global read-only rule | Aligned |
| Parser calls | None | 005/007 sealed | Aligned |
| DB | None | 006 registry contract untouched | Aligned |
| 008 checker | Not invoked | 008 completed | Aligned |
| review workflow stub | Not used | `008-review-workflow` future | Aligned |

### 3.1 Non-blocking P1 Corrections Locked by P3

| ID | Issue | P3 Decision |
|---|---|---|
| D1 | `load_config()` loads mysql block | Allowed for config parse only; **must not connect** |
| D2 | Latest report discovery rule | Select newest by **filename timestamp** `parse_quality_report_{YYYYMMDDTHHMMSSZ}.json` under `reports_root`; tie-break by `generated_at` if timestamps equal |
| D3 | `--fail-on-issue` with summary write | **Write summary first**, then exit 2 if filtered `issue_count > 0` |
| D4 | ISSUE_CODES duplication | Duplicate tuple in summarizer module; P5 test asserts equality with 008 list |
| D5 | recommendations | May echo 008 list; may add **non-mutating** triage notes derived from noise buckets |
| D6 | Filter semantics | Filters apply to `issues[]` and derived aggregations; **`issue_counts` in output always shows full input counts** unless P4 implements dual view — **P3 locks: output `issue_counts` = input `issue_counts` unchanged; filtered counts live under `filtered_summary`** |

---

## 4. P3 — Dev File Whitelist

### 4.1 Allowed Files (P4)

Dev Agent may create or modify **only**:

```text
backend/app/services/parse_quality_report_summarizer.py   # NEW
backend/app/cli/main.py                                   # register summarize-parse-quality
backend/tests/test_parse_quality_report_summarizer.py     # NEW
```

Optional fixture directory (if needed):

```text
backend/tests/fixtures/parse_quality_report_*.json        # NEW synthetic 008 reports only
```

### 4.2 Allowed Behavior

Dev Agent may:

- Call `load_config()` to resolve `reports_root`
- Read 008 JSON from `--input` or latest under `reports_root`
- Validate input schema
- Classify noise buckets from issue JSON fields
- Write Markdown or JSON summary
- Return exit codes per locked contract

---

## 5. P3 — Forbidden Files (Black List)

Dev Agent must **not** modify:

```text
backend/app/services/parse_quality_checker.py
backend/app/services/inventory_scanner.py
backend/app/services/file_content_vault.py
backend/app/services/markitdown_parser.py
backend/app/services/mineru_pdf_parser.py
backend/app/services/parse_registry.py
backend/app/services/parser_router.py
backend/app/services/duplicate_governance.py
backend/app/adapters/*
backend/app/models/*
backend/app/core/database.py
backend/app/core/vault_paths.py
backend/app/core/parsed_paths.py
backend/migrations/*
sql/**
config/app.yaml
config/parser_rules.yaml
raw_vault/**
parsed/**
curated/**
specs/008-parse-quality-checker/**
specs/008-review-workflow/**
specs/010-evidence-chain/**
specs/SPEC_INDEX.md
docs/handoff-*.md
README.md                    # unless user explicitly requests doc sync in handoff phase
```

### 5.1 Forbidden Behavior

Dev Agent must **not**:

- Call `check-parse-quality`
- Call MarkItDown / MinerU / `magic-pdf` / `subprocess` for parsing
- Connect to MySQL or create ORM sessions
- Read or write `raw_vault` / `parsed`
- Modify 008 input JSON
- Implement `--fix`, `--repair`, `--reparse`, `--write-db`
- Clean pytest dirty DB records
- Implement review workflow
- Add migrations or schema changes
- Move/delete/rename user files

---

## 6. CLI Contract (Final — P4)

Command:

```bash
PYTHONPATH=backend python -m app.cli.main summarize-parse-quality \
  --config config/app.yaml \
  --input /path/to/parse_quality_report.json \
  --output /path/to/parse_quality_summary.md
```

Parameters:

| Flag | Required | Values | Notes |
|---|---|---|---|
| `--config` | No | path | Default `config/app.yaml`. Used for `reports_root` only. |
| `--input` | No* | path | Explicit 008 JSON. *Required indirectly if no matching file under `reports_root`. |
| `--output` | No | path | Default `{reports_root}/parse_quality_summary_{UTC}.md` or `.json` |
| `--format` | No | `markdown` (default), `json` | Controls renderer and default extension |
| `--severity` | No | `CRITICAL`, `ERROR`, `WARNING`, `INFO` | Repeat not allowed; single filter |
| `--issue-code` | No | 008 issue code | Repeatable |
| `--parser-name` | No | `markitdown`, `mineru` | Filter issues |
| `--top` | No | int ≥ 1 | Default `20`; max samples per displayed group |
| `--fail-on-issue` | No | flag | Exit 2 when **filtered** issue count > 0 |

Forbidden parameters:

```text
--fix  --repair  --reparse  --write-db
--markitdown  --mineru  --magic-pdf
--check-parse-quality
--sha256  --content-uid  --status  --limit   # these are 008 checker scope, not 009
```

CLI help must state:

```text
Read-only summary of 008 parse_quality_report.json.
Does not connect to MySQL, raw_vault, or parsed.
Does not repair issues.
```

---

## 7. Input Schema Validation Rules (Final)

### 7.1 File-level

Reject with exit **1** when:

```text
input path missing
input not readable
JSON parse error
```

### 7.2 Top-level identity

Must equal / exist:

```text
report_type == "parse_quality_report"
schema_version == "1.0"
mode == "check"
generated_at     (non-empty string)
```

Reject with exit **1** if any identity check fails.

### 7.3 Required objects

Must exist and be correct type:

```text
scope            object
summary          object
issue_counts     object
by_parser        object
by_status        object
by_route_type    object
by_severity      object
issues           array
recommendations  array
```

### 7.4 Required summary keys

```text
checked_content_count
checked_raw_vault_count
checked_parse_result_count
checked_artifact_count
issue_count
critical_count
error_count
warning_count
info_count
```

Values must be numeric (int). Reject exit **1** on missing keys or wrong types.

### 7.5 issue_counts validation

```text
Must contain every code in ISSUE_CODES (18 codes from 008).
Each value must be int >= 0.
Extra unknown keys: reject exit 1.
Missing any required code: reject exit 1.
```

### 7.6 issues[] item shape

Each item must have:

```text
issue_code   string
severity     string
message      string
```

Optional fields (may be null):

```text
content_uid, sha256, parser_name, parser_adapter_version, artifact_type, path, evidence (object)
```

Malformed issue objects: reject exit **1** (strict validation).

### 7.7 scope object

Must exist; keys may be null:

```text
sha256, content_uid, parser_name, status, limit
```

---

## 8. Summary Output Contract (Final)

### 8.1 Default Markdown path

```text
{reports_root}/parse_quality_summary_{YYYYMMDDTHHMMSSZ}.md
```

### 8.2 JSON summary path

When `--format json` or output ends with `.json`:

```text
{reports_root}/parse_quality_summary_{YYYYMMDDTHHMMSSZ}.json
```

### 8.3 JSON summary schema

```json
{
  "report_type": "parse_quality_summary",
  "schema_version": "1.0",
  "mode": "summarize",
  "generated_at": "<ISO8601 Z>",
  "source_report_path": "<absolute path>",
  "source_report_generated_at": "<from input>",
  "source_scope": { },
  "filters": {
    "severity": null,
    "issue_codes": [],
    "parser_name": null
  },
  "summary": {
    "input_issue_count": 0,
    "filtered_issue_count": 0,
    "critical_count": 0,
    "error_count": 0,
    "warning_count": 0,
    "info_count": 0
  },
  "issue_counts": { },
  "filtered_issue_counts": { },
  "by_parser": { },
  "by_status": { },
  "by_route_type": { },
  "by_severity": { },
  "noise_breakdown": {
    "TEST_STALE_PATH": 0,
    "STALE_VAULT_PATH": 0,
    "REAL_DEFECT": 0
  },
  "top_issue_codes": [],
  "sample_issues": [],
  "recommendations": []
}
```

Rules:

```text
issue_counts           = copy of input issue_counts (all 18 codes, unchanged)
filtered_issue_counts  = recomputed from filtered issues[] only
noise_breakdown        = computed from filtered issues[] (or all issues if no filter — P3 locks: use filtered set when filters active, else full set)
top_issue_codes        = top N issue codes by filtered count
sample_issues          = truncated to --top
recommendations        = subset relevant to filtered codes + noise notes (non-mutating)
```

### 8.4 Markdown sections (required order)

```text
1. Parse Quality Summary
2. Source Report
3. Executive Summary
4. Issue Code Matrix (18 codes)
5. Aggregations (severity / parser / status / route)
6. Noise Classification
7. Top Issues (truncated)
8. Recommendations
```

---

## 9. Noise Classification Rules (Final)

Each issue maps to **exactly one** bucket. Priority **first match wins**:

| Priority | Bucket | Rule |
|---:|---|---|
| 1 | `TEST_STALE_PATH` | `evidence.error == "PermissionError"` **OR** `/tmp/pytest-of-` in normalized `path` or `evidence.path` |
| 2 | `STALE_VAULT_PATH` | `issue_code == "STALE_RAW_VAULT_PATH"` **OR** `/tmp/p5_reqa_` in normalized `path` or `evidence.path` **OR** any 008 stale marker substring in path: `/tmp/`, `/var/tmp/`, `/private/tmp/` (excluding pytest paths already bucketed) |
| 3 | `REAL_DEFECT` | all remaining issues |

Normalization:

```text
Use path.replace("\\", "/") before substring tests.
Treat null path fields as empty string.
Do not stat filesystem during classification.
```

---

## 10. Exit Code Rules (Final)

| Code | Condition |
|---|---|
| **0** | Summary written successfully; `--fail-on-issue` not set **or** filtered issue count == 0 |
| **1** | Config missing/unreadable; `reports_root` missing; no input file found; JSON invalid; schema validation failed; output path not writable; unexpected runtime error |
| **2** | `--fail-on-issue` set **and** filtered `issue_count > 0` (after successful summary write) |

Notes:

```text
Exit 2 still requires summary file written (default behavior).
Exit 1 must not leave partial/corrupt summary unless write failed mid-stream — prefer atomic write (temp + rename) if practical.
```

---

## 11. Service Contract (Final — P4)

```python
ISSUE_CODES: tuple[str, ...] = ( ... )  # identical to 008 parse_quality_checker.py

@dataclass
class ParseQualitySummaryResult:
    summary_path: Path
    input_path: Path
    filtered_issue_count: int
    noise_breakdown: dict[str, int]
    exit_code_hint: int  # 0 or 2 for fail-on-issue

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
        fail_on_issue: bool = False,
    ) -> ParseQualitySummaryResult: ...
```

Latest input discovery (when `--input` omitted):

```python
reports_root.glob("parse_quality_report_*.json")
# pick max by embedded UTC timestamp in filename; if none, exit 1
```

---

## 12. pytest Plan (P5)

Test file:

```text
backend/tests/test_parse_quality_report_summarizer.py
```

Fixtures (synthetic 008 JSON only):

```text
parse_quality_report_valid.json
parse_quality_report_with_noise.json
parse_quality_report_empty_issues.json
parse_quality_report_invalid_schema.json
parse_quality_report_missing_issue_code.json
```

Minimum P5 coverage mapping:

| TC | Focus |
|---|---|
| TC001–TC002 | Markdown + JSON happy path |
| TC003–TC007 | Schema rejection + empty issues |
| TC008 | 18 issue codes preserved |
| TC009–TC012 | Noise classification + priority |
| TC013–TC017 | CLI filters + fail-on-issue |
| TC018 | Chinese path UTF-8 in Markdown |
| TC019 | Idempotency excluding timestamps |
| TC020 | No MySQL connection (spy `create_db_engine`) |
| TC021–TC022 | No raw_vault / parsed path reads |
| TC023 | No ParseQualityCheckerService / parser calls |
| TC024–TC025 | Input immutability; only summary written |
| TC026–TC028 | CLI integration |
| TC029–TC030 | 004–008 regression pytest pass |

Regression command:

```bash
PYTHONPATH=backend pytest backend/tests/test_parse_quality_report_summarizer.py \
  backend/tests/test_parse_quality_checker.py \
  backend/tests/test_parser_router.py \
  backend/tests/test_markitdown_parser.py \
  backend/tests/test_parse_job_registry.py \
  backend/tests/test_mineru_pdf_parser.py
```

---

## 13. E2E Plan (P6)

Setup:

```text
Use real parse_quality_report.json from 008 P6 E2E (964 issues environment if available).
```

Command:

```bash
PYTHONPATH=backend python -m app.cli.main summarize-parse-quality \
  --config config/app.yaml \
  --input /path/to/parse_quality_report.json \
  --output /tmp/pkb_sdd_009_p6/parse_quality_summary.md \
  --format markdown
```

Verify:

```text
1. Exit 0 (or exit 2 only when --fail-on-issue explicitly tested)
2. Summary file exists and contains noise_breakdown
3. TEST_STALE_PATH > 0 when PermissionError issues present in input
4. Input JSON mtime + content hash unchanged
5. raw_vault / parsed mtimes unchanged (sanity — 009 should not touch them)
6. Optional DB row count sanity: unchanged because 009 must not connect
7. Re-run with --format json produces valid JSON matching schema §8.3
```

E2E report artifact:

```text
specs/009-quality-report-summary/p6_e2e_report.md
```

---

## 14. P2/P3 Gate Summary

| Gate | Result |
|---|---|
| P2-GATE | **PASS** |
| DB Review | **EXEMPT** (no MySQL, no schema) |
| P3-GATE | **PASS** |
| P4 entry | **BLOCKED until user confirms** |

---

## 15. STOP

P2/P3 completed. **Do not enter P4 Dev Implementation** until user explicitly approves.

Next step after approval:

```text
Dev Agent → P4 using whitelist §4.1 only
```

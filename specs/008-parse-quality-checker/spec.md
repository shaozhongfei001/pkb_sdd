# 008 Parse Quality Checker — spec.md

> Project: `pkb_sdd`  
> Spec Directory: `specs/008-parse-quality-checker/`  
> Branch: `feature/008-parse-quality-checker`  
> Phase: `P1 Tech Lead Plan`  
> Status: `PLANNED / ACTIVE SPEC`  
> Authority: `specs/SPEC_INDEX.md`  
> Scope: Read-only quality checking for parsed artifacts, registry records, raw vault objects, and parse manifests.

---

## 1. Background

The completed SDD chain is:

```text
001-file-inventory
002-file-content-vault
003-duplicate-governance
004-parser-router
005-markitdown-parser
006-parse-job-registry
007-mineru-pdf-parser-adapter
```

The current active spec is:

```text
specs/008-parse-quality-checker/
```

The following directories are **not** current implementation sources:

```text
specs/006-mineru-parser/      # deprecated stub
specs/007-quality-checker/    # deprecated stub; superseded by this 008
specs/008-review-workflow/    # future stub, not current 008
```

008 follows the completed parsed artifact contract introduced in 005 and reused in 007:

```text
parsed/by_hash/{sha256[:2]}/{sha256[2:4]}/{sha256}/
  parsed_text.md
  parsed_metadata.json
  parse_manifest.json
```

The parser metadata must be recorded in `parse_manifest.json`, not as parsed path segments.

---

## 2. Problem Statement

After 001–007, the project has multiple durable layers:

```text
source file inventory
raw_vault object
parser route report
parsed artifact files
parse report
parse registry tables
```

The project needs a dedicated quality checker to verify consistency across those layers without performing any parsing or repair.

Typical issues that 008 should detect include:

```text
1. raw_vault path points to stale /tmp location.
2. raw_vault original.bin is missing.
3. parsed_text.md is missing.
4. parsed_metadata.json is missing.
5. parse_manifest.json is missing.
6. parse_manifest.json has missing or inconsistent fields.
7. manifest sha256 does not match kb_file_content.sha256.
8. manifest content_uid does not match registry content_uid.
9. registry says SUCCESS but parsed files are missing.
10. registry artifact paths point to non-existing files.
11. result status distribution contains FAILED / EMPTY / SKIPPED / MISSING_MANIFEST cases needing review.
```

---

## 3. Goals

008 must provide a read-only parse quality inspection capability.

### 3.1 Functional Goals

```text
G001 Inspect raw_vault object existence.
G002 Detect stale raw_vault paths, especially /tmp-like paths.
G003 Inspect parsed artifact directory existence.
G004 Inspect required parsed files:
     - parsed_text.md
     - parsed_metadata.json
     - parse_manifest.json
G005 Validate parse_manifest.json presence and required metadata fields.
G006 Validate consistency between manifest, registry, and kb_file_content.
G007 Validate registry artifact paths.
G008 Aggregate quality issues by severity, issue code, parser, status, route type, and content_uid.
G009 Output a JSON report under reports_root.
G010 Provide CLI filters for scoped checks.
```

### 3.2 Safety Goals

```text
S001 Default read-only.
S002 No parser invocation.
S003 No DB writes.
S004 No raw_vault modification.
S005 No parsed artifact modification.
S006 No registry modification.
S007 No automatic repair.
S008 Deterministic, idempotent checks.
```

---

## 4. Non-goals

008 explicitly must not:

```text
NG001 Re-parse files.
NG002 Call MarkItDown.
NG003 Call MinerU.
NG004 Call magic-pdf.
NG005 Modify raw_vault.
NG006 Modify parsed artifacts.
NG007 Modify registry tables.
NG008 Delete files.
NG009 Move files.
NG010 Rename files.
NG011 Auto-fix stale paths.
NG012 Auto-generate missing parse_manifest.json.
NG013 Write vector / embedding.
NG014 Write curated dataset.
NG015 Write project card.
NG016 Perform semantic similarity.
NG017 Perform LLM-based quality judgment.
NG018 Perform OCR quality judgment.
NG019 Introduce schema migration.
NG020 Add DB write behavior without explicit DB Review.
```

---

## 5. In-scope Data Sources

008 may read from:

```text
config/app.yaml
kb_file_content
kb_file_instance
kb_raw_vault_object
kb_parse_job
kb_parse_result
kb_parsed_artifact
raw_vault filesystem
parsed filesystem
reports_root filesystem
```

008 may also read existing JSON reports if needed for context, but the primary contract should be DB + filesystem consistency.

---

## 6. Output Contract

008 writes one report file to `reports_root`:

```text
parse_quality_report_{UTC}.json
```

No other file writes are allowed.

Recommended report schema:

```json
{
  "report_type": "parse_quality_report",
  "schema_version": "1.0",
  "generated_at": "2026-06-16T00:00:00Z",
  "mode": "check",
  "scope": {
    "sha256": null,
    "content_uid": null,
    "parser_name": null,
    "status": null,
    "limit": null
  },
  "summary": {
    "checked_content_count": 0,
    "checked_raw_vault_count": 0,
    "checked_parse_result_count": 0,
    "checked_artifact_count": 0,
    "issue_count": 0,
    "critical_count": 0,
    "error_count": 0,
    "warning_count": 0,
    "info_count": 0
  },
  "issue_counts": {
    "MISSING_RAW_VAULT_OBJECT": 0,
    "STALE_RAW_VAULT_PATH": 0,
    "MISSING_PARSED_TEXT": 0,
    "MISSING_PARSED_METADATA": 0,
    "MISSING_PARSE_MANIFEST": 0,
    "MANIFEST_SHA256_MISMATCH": 0,
    "MANIFEST_CONTENT_UID_MISMATCH": 0,
    "REGISTRY_ARTIFACT_PATH_MISSING": 0,
    "REGISTRY_STATUS_FILE_MISMATCH": 0
  },
  "by_parser": {},
  "by_status": {},
  "by_route_type": {},
  "by_severity": {},
  "issues": [],
  "recommendations": []
}
```

---

## 7. Issue Taxonomy

### 7.1 Severity

```text
CRITICAL
  Cross-layer inconsistency that invalidates trust in a registered successful parse.

ERROR
  Missing required artifact or required manifest field.

WARNING
  Suspicious but not immediately invalidating condition, such as stale-looking path.

INFO
  Aggregated status observation or empty candidate set.
```

### 7.2 Issue Codes

| Code | Severity | Meaning |
|---|---:|---|
| `MISSING_RAW_VAULT_OBJECT` | ERROR | raw vault DB object exists but file path is missing. |
| `STALE_RAW_VAULT_PATH` | WARNING | raw vault path points to suspicious temp location, especially `/tmp`. |
| `MISSING_PARSED_DIR` | ERROR | Expected parsed directory is missing. |
| `MISSING_PARSED_TEXT` | ERROR | `parsed_text.md` is missing. |
| `MISSING_PARSED_METADATA` | ERROR | `parsed_metadata.json` is missing. |
| `MISSING_PARSE_MANIFEST` | ERROR | `parse_manifest.json` is missing. |
| `INVALID_PARSE_MANIFEST_JSON` | ERROR | Manifest exists but cannot be parsed as JSON. |
| `MANIFEST_REQUIRED_FIELD_MISSING` | ERROR | Manifest lacks required field. |
| `MANIFEST_SHA256_MISMATCH` | CRITICAL | Manifest sha256 differs from `kb_file_content.sha256`. |
| `MANIFEST_CONTENT_UID_MISMATCH` | CRITICAL | Manifest content_uid differs from expected content_uid. |
| `MANIFEST_PARSER_NAME_INVALID` | ERROR | Manifest parser_name is not in allowed parser set. |
| `MANIFEST_ADAPTER_VERSION_MISSING` | ERROR | Manifest parser adapter version is missing. |
| `REGISTRY_ARTIFACT_PATH_MISSING` | ERROR | Registry artifact path points to non-existing file. |
| `REGISTRY_STATUS_FILE_MISMATCH` | CRITICAL | Registry status says success but required artifacts are missing. |
| `REGISTRY_MISSING_MANIFEST_RESULT` | WARNING | Registry result contains missing-manifest status. |
| `REGISTRY_FAILED_RESULT` | WARNING | Registry result is failed. |
| `REGISTRY_EMPTY_RESULT` | WARNING | Registry result is empty. |
| `REGISTRY_SKIPPED_RESULT` | INFO | Registry result is skipped. |

---

## 8. Required Manifest Fields

The quality checker should validate at least the following logical fields when they are part of the completed parsed contract:

```text
content_uid
sha256
parser_name
parser_profile
parser_adapter_version
status
created_at or generated_at
artifacts or output_files
```

If the actual 005/007 manifest field names differ, implementation must align with existing code and tests. The P1 rule is:

```text
Do not invent a new manifest contract in 008.
Only validate the existing 005/007 manifest contract.
```

---

## 9. Relationship with 001–007

```text
001 provides kb_file_content and file identity.
002 provides raw_vault object and original.bin location.
003 is not directly modified; duplicate groups may be read only if needed later.
004 provides route types; 008 may aggregate by route type if data is already available.
005 provides MarkItDown parsed artifacts using the standard parsed contract.
006 provides registry tables and ingest contract.
007 provides MinerU PDF parsed artifacts using the same parsed contract.
008 checks consistency across the completed layers.
```

---

## 10. CLI Contract

Proposed CLI command:

```bash
PYTHONPATH=backend python -m app.cli.main check-parse-quality \
  --config config/app.yaml
```

Optional filters:

```bash
--sha256 <sha256>
--content-uid <content_uid>
--parser-name <parser_name>
--status <status>
--limit <N>
--output <report_path>
```

Safety options:

```bash
--check-only
```

`--check-only` may be implicit/default. There should be no `--fix` flag in 008.

---

## 11. Role Boundaries for Cursor Agents

| Role | 008 Responsibility |
|---|---|
| Tech Lead Agent | Owns P1 spec, plan, scope, gates, review, final acceptance decision. |
| Dev Agent | Implements only after P1/P2 approval; must follow allowed files and no-side-effect rules. |
| QA Agent | Owns unit tests, regression tests, issue taxonomy test coverage, no-side-effect tests. |
| E2E Agent | Owns real CLI + DB + filesystem validation after implementation, not during P1. |

Do not introduce `E2E QA Agent`. P5 is QA; P6 is E2E.

---

## 12. Acceptance Summary

008 is acceptable only if:

```text
1. It produces a JSON report under reports_root.
2. It detects missing raw vault and missing parsed artifacts.
3. It validates parse_manifest consistency.
4. It validates registry artifact paths.
5. It has no DB writes.
6. It has no parser invocation.
7. It has no mutation of raw_vault or parsed.
8. It passes 001–007 regression tests.
9. It documents caveats and handoff clearly.
```

---

## 13. P1 STOP Condition

P1 ends after the following files are created or updated:

```text
specs/008-parse-quality-checker/spec.md
specs/008-parse-quality-checker/plan.md
specs/008-parse-quality-checker/tasks.md
specs/008-parse-quality-checker/acceptance.md
specs/008-parse-quality-checker/test_cases.md
```

After P1, STOP.

No implementation code should be written in P1.

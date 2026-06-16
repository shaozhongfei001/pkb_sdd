# 008 Parse Quality Checker — P2/P3 Tech Lead Review

> Role: Tech Lead Agent  
> Spec: `specs/008-parse-quality-checker/`  
> Branch: `feature/008-parse-quality-checker`  
> Stage: P2 DB/Data Read Review + P3 Implementation Gate

---

## 1. Gate Conclusion

P2 DB/Data Read Review: **PASS**  
P3 Implementation Gate: **PASS**

Conclusion:

`008 Parse Quality Checker` is approved to enter P4 Dev Implementation.

This stage remains read-only except for writing the JSON quality report under `reports_root` or an explicit `--output` path.

---

## 2. Contract Conflict Review

No blocking conflict was found between 008 and completed 001–007 contracts.

008 is a cross-layer read-only consistency checker for:

- `raw_vault`
- parsed artifacts
- `parse_manifest.json`
- parse registry records
- parser metadata
- quality report output

It does not call parser services, does not repair data, does not write DB, and does not modify `raw_vault` or parsed outputs.

### 2.1 Contract Alignment Matrix

| Dimension | 008 Design | 001–007 Contract | Decision |
|---|---|---|---|
| parsed path | `parsed/by_hash/{sha256[:2]}/{sha256[2:4]}/{sha256}/` | `parsed_paths.py` / parser rules | Aligned |
| standard artifacts | `parsed_text.md`, `parsed_metadata.json`, `parse_manifest.json` | 005 / 007 | Aligned |
| raw vault path | `raw_vault/by_hash/{sha256[:2]}/{sha256}/original.bin` | `vault_paths.py` | Aligned |
| parser metadata | Stored in `parse_manifest.json`, not path segments | 004 parser rule correction | Aligned |
| side effect | Only writes quality report | global read-only rule | Aligned |
| parsing behavior | Does not call MarkItDown / MinerU | 005 / 007 sealed parser contracts | Aligned |
| DB behavior | SELECT-only ORM reads | 006 registry contract | Aligned |
| sealed services | No change required | 001–007 services | Aligned |

---

## 3. Non-blocking P1 Corrections Locked by P3

The following P1 documentation issues are non-blocking. P3 locks the implementation decisions below.

| ID | Issue | P1 Wording | Codebase Truth | P3 Decision |
|---|---|---|---|---|
| D1 | Table name | `kb_parse_job` | actual registry model is `KbParseRun` / `kb_parse_run` | Dev must use `KbParseRun` / `kb_parse_run` |
| D2 | Manifest fields | `created_at` / `artifacts` / `output_files` | 005/007 use existing manifest fields such as `generated_at`, `parsed_text_path`, `parsed_metadata_path`; MinerU additionally has `parser_profile` | Validate existing 005/007 manifest fields only; do not invent a new schema |
| D3 | `parser_profile` required | Listed as generally required | MinerU manifest has it; MarkItDown manifest may not | Require `parser_profile` for `mineru` only; do not require it for `markitdown` |
| D4 | raw vault object check | Check `original.bin` directly | `KbRawVaultObject.vault_path` stores vault directory | Treat `vault_path` as `vault_dir`, then call `build_vault_artifact_paths(vault_dir)["original_bin"]` |
| D5 | `issue_counts` examples | Partial issue code examples | spec defines 18 stable issue codes | Report must include all 18 stable issue codes, even when count is 0 |
| D6 | `by_route_type` aggregation | Required aggregation | `KbParseResult.route_type` may be available; manifest may also contain `route_type` | Use `KbParseResult.route_type` first, then manifest `route_type`; otherwise `null` |

---

## 4. Relationship with 007 Caveat

The 007 caveat states that real `magic-pdf` / MinerU E2E was not completed because:

- `magic-pdf` was not available in PATH.
- The available PDF vault sample had a stale `/tmp/p5_reqa_*` path.
- There was no clean live COPIED non-PDF sample for some route mismatch validation.

008 does not conflict with this caveat.

Instead, 008 explicitly detects this type of condition through `STALE_RAW_VAULT_PATH`.

Therefore:

- 007 remains DONE with its caveat.
- 008 adds read-only quality visibility.
- 008 must not claim to repair or complete the missing real MinerU E2E validation.

---

## 5. DB Review Decision

No independent DB write review is required.

Reason:

- No schema change.
- No migration.
- No new DB table.
- No new DB field.
- No registry backfill.
- No DB write.
- No `session.add`.
- No `session.delete`.
- No `session.merge`.
- No `session.commit`.
- No raw SQL DML.
- Only SELECT-style ORM reads are allowed.

P5 must still verify no DB write behavior as QA evidence.

P2-GATE: **PASS**  
DB write review: **WAIVED because this stage is read-only**

---

## 6. Approved Data Read Plan

### 6.1 Config Inputs

Allowed config fields:

- `AppConfig.storage.raw_vault_root`
- `AppConfig.storage.parsed_root`
- `AppConfig.storage.reports_root`

Config loading must follow existing project conventions:

- `load_config()`
- read-only mode behavior consistent with 005 / 006 / 007 where applicable

### 6.2 ORM Read Sources

Allowed ORM read models:

- `KbFileContent`
- `KbFileInstance`
- `KbRawVaultObject`
- `KbParseRun`
- `KbParseResult`
- `KbParsedArtifact`

### 6.3 Candidate Source

The default candidate source is `KbParseResult`, optionally joined or correlated with:

- `KbParsedArtifact`
- `KbFileContent`
- `KbRawVaultObject`

### 6.4 Allowed Filters

Allowed CLI / service filters:

- `--sha256`
- `--content-uid`
- `--parser-name`
- `--status`
- `--limit`

### 6.5 Allowed Path Helpers

008 may import and use these helpers read-only:

- `app.core.vault_paths.build_vault_dir`
- `app.core.vault_paths.build_vault_artifact_paths`
- `app.core.parsed_paths.build_parsed_content_dir`
- `app.core.parsed_paths.build_parsed_artifact_paths`

008 must not modify these helper modules.

### 6.6 Registry Status Constants

Allowed parse result status values:

- `SUCCESS`
- `EMPTY`
- `SKIPPED`
- `FAILED`

Special handling:

- `error_code == "MISSING_MANIFEST"` maps to `REGISTRY_MISSING_MANIFEST_RESULT`.

### 6.7 Parser Names

Allowed parser names:

- `markitdown`
- `mineru`

Any other parser name in manifest or registry must be reported as `MANIFEST_PARSER_NAME_INVALID`, not repaired.

---

## 7. P3 Implementation White List

### 7.1 Allowed Deliverables

| Deliverable | Path / Name |
|---|---|
| Service | `backend/app/services/parse_quality_checker.py` |
| CLI | `backend/app/cli/main.py` |
| Tests | `backend/tests/test_parse_quality_checker.py` |

### 7.2 Allowed File Changes

Dev Agent may create or modify only:

- `backend/app/services/parse_quality_checker.py`
- `backend/app/cli/main.py`
- `backend/tests/test_parse_quality_checker.py`

### 7.3 Allowed Behavior

Dev Agent may:

- Read config.
- Read DB through ORM.
- Read `raw_vault`, parsed files, and manifest files.
- Write one JSON report to `reports_root`.
- Write one JSON report to an explicit `--output` path.
- Return CLI exit codes according to the locked CLI contract.

---

## 8. P3 Implementation Black List

### 8.1 Forbidden Files

Dev Agent must not modify:

- `backend/app/services/inventory_scanner.py`
- `backend/app/services/file_content_vault.py`
- `backend/app/services/markitdown_parser.py`
- `backend/app/services/mineru_pdf_parser.py`
- `backend/app/services/parse_registry.py`
- `backend/app/services/parser_router.py`
- `backend/app/services/duplicate_governance.py`
- `backend/app/adapters/*`
- `backend/app/models/*`
- `backend/migrations/*`
- `config/app.yaml`
- `config/parser_rules.yaml`
- `raw_vault/**`
- `parsed/**`
- `curated/**`
- `specs/006-mineru-parser/**`
- `specs/007-quality-checker/**`
- `specs/008-review-workflow/**`
- `backend/app/core/vault_paths.py`
- `backend/app/core/parsed_paths.py`
- `docs/handoff-*.md`
- `specs/SPEC_INDEX.md`

### 8.2 Forbidden Behavior

Dev Agent must not:

- Call MarkItDown.
- Call MinerU.
- Call `magic-pdf`.
- Call `subprocess`.
- Re-parse files.
- Repair data.
- Modify `raw_vault`.
- Modify parsed artifacts.
- Modify registry records.
- Add migrations.
- Change schema.
- Execute raw SQL DML.
- Implement `--fix`.
- Implement `--repair`.
- Implement `--reparse`.
- Implement `--run-parser`.
- Implement `--write-db`.
- Add `session.add`.
- Add `session.delete`.
- Add `session.merge`.
- Add `session.commit`.

---

## 9. CLI Contract

Command:

```bash
PYTHONPATH=backend python -m app.cli.main check-parse-quality \
  --config config/app.yaml
```

Allowed parameters:

- `--config`
- `--sha256`
- `--content-uid`
- `--parser-name`
- `--status`
- `--limit`
- `--output`
- `--fail-on-issue`

Forbidden parameters:

- `--fix`
- `--repair`
- `--reparse`
- `--run-parser`
- `--write-db`
- `--markitdown`
- `--mineru`
- `--magic-pdf`

Exit codes:

- `0`: report generated successfully.
- `1`: configuration, DB, or runtime error.
- `2`: only when `--fail-on-issue` is set and `issue_count > 0`.

---

## 10. Service Contract

Service:

```python
class ParseQualityCheckerService:
    def __init__(self, config: AppConfig, session_factory):
        ...

    def check(
        self,
        *,
        sha256: str | None = None,
        content_uid: str | None = None,
        parser_name: str | None = None,
        status: str | None = None,
        limit: int | None = None,
        output: Path | None = None,
    ) -> ParseQualityReport:
        ...
```

Internal dataclasses:

- `ParseQualityCandidate`
- `ParseQualityIssue`
- `ParseQualityReport`

The service must remain deterministic for the same DB and filesystem state, except for `generated_at` and default report filename timestamp.

---

## 11. Report Contract

Default output:

```text
{reports_root}/parse_quality_report_{YYYYMMDDTHHMMSSZ}.json
```

When `--output` is specified, the report is written to the explicit output path.

Top-level schema:

```json
{
  "report_type": "parse_quality_report",
  "schema_version": "1.0",
  "generated_at": "<ISO8601 Z>",
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
  "issue_counts": {},
  "by_parser": {},
  "by_status": {},
  "by_route_type": {},
  "by_severity": {},
  "issues": [],
  "recommendations": []
}
```

Required top-level fields:

- `report_type`
- `schema_version`
- `generated_at`
- `mode`
- `scope`
- `summary`
- `issue_counts`
- `by_parser`
- `by_status`
- `by_route_type`
- `by_severity`
- `issues`
- `recommendations`

`schema_version` must be:

```text
1.0
```

`report_type` must be:

```text
parse_quality_report
```

`mode` must be:

```text
check
```

---

## 12. Issue Taxonomy

`issue_counts` must include all 18 stable issue codes, even when count is 0:

- `MISSING_RAW_VAULT_OBJECT`
- `STALE_RAW_VAULT_PATH`
- `MISSING_PARSED_DIR`
- `MISSING_PARSED_TEXT`
- `MISSING_PARSED_METADATA`
- `MISSING_PARSE_MANIFEST`
- `INVALID_PARSE_MANIFEST_JSON`
- `MANIFEST_REQUIRED_FIELD_MISSING`
- `MANIFEST_SHA256_MISMATCH`
- `MANIFEST_CONTENT_UID_MISMATCH`
- `MANIFEST_PARSER_NAME_INVALID`
- `MANIFEST_ADAPTER_VERSION_MISSING`
- `REGISTRY_ARTIFACT_PATH_MISSING`
- `REGISTRY_STATUS_FILE_MISMATCH`
- `REGISTRY_MISSING_MANIFEST_RESULT`
- `REGISTRY_FAILED_RESULT`
- `REGISTRY_EMPTY_RESULT`
- `REGISTRY_SKIPPED_RESULT`

Severity values:

- `CRITICAL`
- `ERROR`
- `WARNING`
- `INFO`

Each issue item must contain:

- `issue_code`
- `severity`
- `content_uid`
- `sha256`
- `parser_name`
- `parser_adapter_version`
- `artifact_type`
- `path`
- `message`
- `evidence`

---

## 13. Stale Raw Vault Path Rule

`STALE_RAW_VAULT_PATH` is triggered when either of the following paths indicates a temporary or stale location:

- `KbRawVaultObject.vault_path`
- `parse_manifest.json` field such as `source_vault_path`, if present

The required detection rule for P4:

- path contains `/tmp/`
- or path matches a known temporary prefix used by prior test artifacts

This rule is intended to detect the 007 stale `/tmp/p5_reqa_*` caveat.

P5 / P6 must distinguish between:

- expected test-triggered `/tmp/` paths
- actual stale production vault paths

008 must report the condition only. It must not repair it.

---

## 14. P5 QA Obligations

P5 QA must verify:

- 008 unit tests pass.
- 004–007 regression tests pass.
- Full `backend/tests` test suite passes, if feasible.
- No DB write behavior exists.
- No parser call exists.
- No `subprocess` call exists.
- Only report output is written.
- `--output` writes to the explicit path.
- `--fail-on-issue` returns exit code `2` when issues exist.
- `issue_counts` always includes all 18 issue codes.
- MarkItDown manifest does not require `parser_profile`.
- MinerU manifest requires `parser_profile`.
- The `/tmp/` stale vault rule is covered by test evidence.

---

## 15. P6 E2E Obligations

P6 E2E must validate against a real environment, where available:

- real `config/app.yaml`
- real MySQL connection
- real `raw_vault`
- real parsed artifacts
- real `reports_root`

P6 must verify:

- CLI can generate a report.
- Report path exists.
- JSON report schema is valid.
- DB row counts do not change.
- `raw_vault` file mtimes do not change.
- parsed artifact file mtimes do not change.
- Any stale `/tmp/` vault path is reported, not repaired.

---

## 16. P3 Final Gate

P3-GATE: **PASS**

P4 Dev Implementation is approved.

STOP — P2/P3 review completed. No implementation code is included in this document.

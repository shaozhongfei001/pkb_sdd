# 011 Curated Project Assets — P5 QA Report

> Role: QA Agent  
> Spec: `specs/011-curated-project-assets/`  
> Branch: `feature/011-curated-project-assets`  
> Stage: P5 QA Test & Regression  
> P4 implementation commit: `d8ac4ba`  
> P3 gate commit: `9de94fc`  
> P2 review commit: `2d4f8d7`

---

## 1. Gate Conclusion

**P5 QA Test & Regression: PASS**

011 Curated Project Assets passed:

- P1/P2/P3 contract compliance review
- 011 specialized tests (**18 passed** after P5 gap supplements)
- Full `backend/tests` regression (**246 passed**)
- CLI contract static review
- DB write boundary review
- Filesystem boundary review
- Forbidden runtime/import static review
- Fixture pollution review

**No blocking implementation defects found.** P4 production code was not modified in P5.

011 may enter **P6 E2E Validation** after user confirmation.

---

## 2. P1/P2/P3 Contract Compliance Review

| Contract item | Expected (P1/P2/P3) | Observed in P4 `d8ac4ba` | Result |
|---|---|---|---|
| ORM | Add `project.py` only (`KbProject`, `KbProjectDocument`, `KbCuratedAsset`) | New file; no edits to `evidence.py` / `document.py` | PASS |
| Schema migration | Not required MVP | No sql/migrations changes | PASS |
| DB write allowlist | UPSERT `kb_project`, `kb_project_document`, `kb_curated_asset` only | Three `_upsert_*` methods via `mysql_insert` only | PASS |
| `kb_document` | SELECT only | `select(KbDocument)` in `_resolve_document_uid` / `_load_documents` | PASS |
| `kb_evidence` | SELECT only; no `project_uid` backfill | `select(KbEvidence)` in `_load_evidence`; no evidence DML | PASS |
| `kb_document_chunk` | No access | Not imported or referenced | PASS |
| Parse registry | No write | Not referenced in service | PASS |
| Review / embedding | No write | Not referenced | PASS |
| Idempotency | Deterministic UID + UNIQUE upsert | `project\|v1\|…` / `curated\|v1\|…\|1`; ON DUPLICATE KEY UPDATE | PASS |
| `generation_method` | `TEMPLATE_RULE` | Constant + DB field lock | PASS |
| `version_no` | Fixed `1` | Constant; `--force` does not bump | PASS |
| `related_*` | JSON arrays | ORM JSON columns; list serialization in upsert | PASS |
| `--dry-run` | Zero DB + zero curated file write | No upsert/file write branch; tests T1/T15 | PASS |
| Curated files | Three MVP files only | `ASSET_FILES` dict; test `test_only_three_markdown_files_written` | PASS |
| Traceability | UID refs in Markdown | Tests T12/T19; tables in index/source docs | PASS |
| mapping_method | MANIFEST / CLI / SEED | Tests T13/T14/T18 + new CLI/limit tests | PASS |
| No parser / LLM / embed / search / UI | Forbidden | No imports in `curated_project_assets.py` | PASS |
| No raw_vault binary | Do not open `original.bin` | Test T8 | PASS |
| No parsed mutation | Read-only if present | Test T9 | PASS |
| Dev whitelist | 6 backend paths only | `git diff 9de94fc..d8ac4ba` matches whitelist | PASS |

P2 constraints C1–C13: **PASS** (unchanged by P4).

---

## 3. P4 Whitelist / Forbidden Path Review

### 3.1 P4 modified files (`d8ac4ba`)

```text
backend/app/cli/main.py
backend/app/models/project.py
backend/app/services/curated_project_assets.py
backend/tests/test_curated_project_assets.py
backend/tests/fixtures/curated_project/demo_project.manifest.yaml.fixture
backend/tests/fixtures/curated_project/chinese_project.manifest.yaml.fixture
```

All within P3 §2 whitelist. **PASS**

### 3.2 Forbidden paths untouched

```text
sql/**                  — not modified
backend/migrations/**   — not modified
raw_vault/**            — not modified
parsed/**               — not modified (repo tree)
curated/**              — not modified (repo tree)
docs/handoff-*.md       — not modified
sealed services         — not modified
evidence_chain.py       — not modified
```

**PASS**

---

## 4. Test Execution

Environment:

```bash
cd /home/szf/dev/pyws/pkb_sdd
PYTHONPATH=backend backend/.venv/bin/pytest ...
```

### 4.1 011 Specialized Tests

```bash
PYTHONPATH=backend backend/.venv/bin/pytest backend/tests/test_curated_project_assets.py -q
```

Result:

```text
18 passed in 0.48s
```

| Test | P3/P5 coverage |
|---|---|
| `test_dry_run_zero_db_and_file_writes` | dry-run zero DB + zero files |
| `test_first_run_writes_three_files_and_upserts_tables` | first run 3 files + 3 tables |
| `test_no_force_rerun_skips_without_duplicate_rows` | no-force skip |
| `test_force_rerun_overwrites_files_same_uids` | force overwrite; UID/version stable |
| `test_related_json_arrays_correct` | related_* JSON |
| `test_chinese_project_name_utf8` | Chinese UTF-8 |
| `test_no_evidence_warning_without_crash` | no evidence warning |
| `test_does_not_read_raw_vault_binary` | no original.bin |
| `test_parsed_files_not_modified` | parsed mtime unchanged |
| `test_does_not_call_parser_services` | no parser invocation |
| `test_forbidden_tables_not_written` | evidence.project_uid unchanged |
| `test_markdown_contains_traceability_uids` | UID traceability in Markdown |
| `test_seed_mapping_method` | SEED mapping_method |
| `test_cli_smoke_dry_run` | CLI dry-run smoke |
| `test_manifest_project_code_mismatch_raises` | manifest/code mismatch exit |
| `test_limit_truncates_manifest_documents` | **P5 added** — `--limit` |
| `test_only_three_markdown_files_written` | **P5 added** — three-file boundary |
| `test_cli_content_uid_mapping_method` | **P5 added** — CLI mapping_method |

### 4.2 Full Regression

```bash
PYTHONPATH=backend backend/.venv/bin/pytest backend/tests -q
```

Result:

```text
246 passed in 27.74s
```

Baseline before 011 P4: 228 passed. Delta: **+18** (011 specialized suite).

Inventory scanner regression included in full suite — **PASS** (no new `.txt`/`.pdf`/`.json` document fixtures under scannable paths).

---

## 5. CLI Contract QA

Command: `build-curated-project` in `backend/app/cli/main.py` (L799+)

| Flag | Present | Wired to service | Result |
|---|---|---|---|
| `--config` | Yes | `load_config(config_path)` | PASS |
| `--project-code` | Yes (required) | `project_code=` | PASS |
| `--project-name` | Yes | `project_name=` | PASS |
| `--content-uid` | Yes | `content_uid=` | PASS |
| `--manifest` | Yes | `manifest_path=manifest` | PASS |
| `--limit` | Yes | `limit=` | PASS |
| `--dry-run` | Yes | `dry_run=` | PASS |
| `--force` | Yes | `force=` | PASS |
| `--output` | Yes | `output=` | PASS |

Help text documents: no parsers, no raw_vault binaries, dry-run zero writes. **PASS**

---

## 6. dry-run / no-force / force QA

| Scenario | Expected | Evidence | Result |
|---|---|---|---|
| `--dry-run` | Zero DB DML + zero curated files | `test_dry_run_zero_db_and_file_writes`, `test_cli_smoke_dry_run` | PASS |
| no-force rerun | Skip when SUCCESS + file exists | `test_no_force_rerun_skips_without_duplicate_rows` | PASS |
| `--force` rerun | Overwrite files; same UID/version | `test_force_rerun_overwrites_files_same_uids` | PASS |
| JSON report | `curated_build_report` v1.0 | dry-run `--output` test parses schema | PASS |

---

## 7. Forbidden DB Write QA

Static review of `curated_project_assets.py`:

```text
mysql_insert targets:
  kb_project.__table__
  kb_project_document.__table__
  kb_curated_asset.__table__

SELECT only:
  KbDocument
  KbEvidence

No references to:
  kb_document_chunk, kb_review_item, kb_manual_correction, kb_embedding_ref,
  kb_parse_run, kb_parse_result, kb_parsed_artifact
```

Runtime test: `test_forbidden_tables_not_written` — evidence dict unchanged; `project_uid` remains `None`. **PASS**

---

## 8. Forbidden Import / Runtime QA

```bash
grep -R "markitdown|mineru|magic_pdf|openai|embedding|vector|streamlit|subprocess" \
  backend/app/services/curated_project_assets.py \
  backend/app/models/project.py
```

Result: **no matches** in 011 service/model files.

Note: `backend/app/cli/main.py` contains parser imports for **other** CLI commands (`parse-markitdown`, `parse-mineru-pdf`). The `build-curated-project` handler imports only `CuratedProjectAssetsService` — no parser invocation on that code path. **PASS**

Runtime: `test_does_not_call_parser_services` patches parser classes — not called during curated build. **PASS**

No LLM / embedding / Streamlit / search imports in 011 implementation scope. **PASS**

---

## 9. raw_vault / parsed / curated Repo Pollution QA

| Area | Check | Result |
|---|---|---|
| `raw_vault/**` | P4/P5 git diff — no repo changes | PASS |
| `parsed/**` | P4/P5 git diff — no repo changes | PASS |
| `curated/**` (repo) | P4/P5 git diff — no repo changes; tests use `tmp_path` curated_root | PASS |
| Fixtures | `.yaml.fixture` suffix under `backend/tests/fixtures/curated_project/` | PASS |
| Inventory scanner | Full regression 246 passed; no new document-suffix fixtures | PASS |

---

## 10. Defects Found

| ID | Severity | Description | Action |
|---|---|---|---|
| — | — | **None blocking** | — |

### P5 Notes (non-blocking)

1. **Evidence index skip policy:** Assets with `generation_status=SKIPPED` (zero evidence) are re-written on no-force rerun because skip requires `SUCCESS`. Acceptable MVP behavior per P3; document if E2E observes unexpected rewrites.
2. **`--limit` on SEED mode:** Limited via slice on seed rows — not separately tested; low risk.
3. **CLI `--config` path:** Smoke test uses tmp `app.yaml`; production default path not E2E-tested until P6.

---

## 11. P5 Changes

| File | Change |
|---|---|
| `specs/011-curated-project-assets/p5_qa_report.md` | NEW — this report |
| `backend/tests/test_curated_project_assets.py` | +3 gap tests (limit, three-file boundary, CLI mapping_method) |

P4 production files (`project.py`, `curated_project_assets.py`, `cli/main.py`): **not modified**.

---

## 12. P5 Gate Summary

| Item | Result |
|---|---|
| P5 QA | **PASS** |
| Specialized tests | **18 passed** |
| Full regression | **246 passed** |
| Contract drift | **None blocking** |
| Approve P6 | **Yes** (pending user confirmation) |

---

## 13. STOP

P5 completed. **Do not enter P6** until user confirms.

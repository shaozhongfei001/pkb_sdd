# 010 Evidence Chain — P5 QA Report

> Role: QA Agent  
> Spec: `specs/010-evidence-chain/`  
> Branch: `feature/010-evidence-chain`  
> Stage: P5 QA Test & Regression  
> P4 implementation commit: `afc4464`  
> P4 regression fix commit: `45b21e4`  
> P3 gate commit: `543c8dd`

---

## 1. Gate Conclusion

**P5 QA Test & Regression: PASS**

010 Evidence Chain passed:

- P1/P2/P3 contract compliance review
- 010 specialized tests (16 passed)
- Full `backend/tests` regression (228 passed)
- DB write boundary review
- Filesystem boundary review
- Forbidden runtime behavior review
- Baseline regression fix review (`45b21e4`)

**No implementation defects found.** P4 production code was not modified in P5.

010 may enter **P6 E2E Validation** after user confirmation.

---

## 2. P1/P2/P3 Contract Compliance Review

| Contract item | Expected (P1/P2/P3) | Observed in P4 `afc4464` | Result |
|---|---|---|---|
| ORM | Add `KbDocumentChunk` + `KbEvidence` only | `backend/app/models/evidence.py`; no `KbDocument` edits | PASS |
| Schema migration | Not required MVP | No sql/migrations changes | PASS |
| DB write | INSERT/UPSERT chunk + evidence only | `mysql_insert` on `kb_document_chunk` / `kb_evidence` only | PASS |
| `kb_document` | SELECT only | `select(KbDocument)` in `_resolve_document_uid`; no DML | PASS |
| Parse registry | SELECT only | `select(KbParseResult)`; no registry writes | PASS |
| Idempotency | Deterministic UID + UNIQUE upsert | `_chunk_uid` / `_evidence_uid` sha256 payloads; ON DUPLICATE KEY UPDATE | PASS |
| `--dry-run` | Zero DB write | Upsert skipped; `session.rollback()` | PASS |
| Parsed input | Read-only artifacts | `read_text` on parsed_text / metadata / manifest | PASS |
| No raw_vault binary | Do not open `original.bin` | No `vault_paths` import; path strings from manifest only | PASS |
| No parser call | No MarkItDown/MinerU/magic-pdf | No parser service imports; `_chunk_markitdown` / `_chunk_mineru` are local splitters | PASS |
| No repair/reparse | Skip missing parsed; no fix | Warning + `errors[]`; batch continues | PASS |
| No LLM/embedding/curated | Out of MVP | No related imports or writes | PASS |
| MarkItDown MVP | Section/heading/char offset | `HEADING_PATTERN` split; `page_no`/`bbox` null | PASS |
| MinerU MVP | Page + bbox best-effort | `metadata.pages` page chunks; fallback to section split | PASS |
| CLI contract | All P3 flags | `build-evidence-chain` with `--config/--content-uid/--sha256/--limit/--dry-run/--force/--output` | PASS |
| Dev whitelist | 6 backend paths only | `git diff 543c8dd..45b21e4` matches whitelist + test fix | PASS |

P2 constraints C1–C8: **PASS** (unchanged by P4).

---

## 3. Test Execution

Environment:

```bash
cd /home/szf/dev/pyws/pkb_sdd
source backend/.venv/bin/activate
```

### 3.1 010 Specialized Tests

```bash
PYTHONPATH=backend python -m pytest backend/tests/test_evidence_chain.py -q
```

Result:

```text
16 passed in 0.67s
```

| Test | P3/P5 coverage |
|---|---|
| `test_dry_run_zero_db_writes` | T1 dry-run zero DB write |
| `test_repeated_run_idempotent` | T2 idempotent re-run |
| `test_missing_parsed_artifact_skips_without_repair` | T3 missing parsed skip |
| `test_markitdown_section_chunks_without_page_bbox` | T4 MarkItDown no page/bbox |
| `test_mineru_page_bbox_best_effort` | T5 MinerU page/bbox |
| `test_does_not_read_raw_vault_binary` | T6 no raw_vault binary |
| `test_does_not_call_parser_services` | T7 no parser call |
| `test_does_not_write_curated` | T8 no curated write |
| `test_registry_models_unchanged` | T9 registry unchanged |
| `test_parsed_mtime_unchanged` | T10 parsed mtime |
| `test_force_upsert_no_duplicate_rows` | T12 `--force` no duplicate UID rows |
| `test_output_json_report` | T13 `--output` JSON schema |
| `test_chinese_path_and_content` | T11 Chinese path/content |
| `test_deterministic_uid_generation` | UID contract |
| `test_cli_build_evidence_chain_smoke` | CLI smoke |
| `test_cli_help_documents_contract` | CLI help text |

### 3.2 Full Backend Regression

```bash
PYTHONPATH=backend python -m pytest backend/tests -q
```

Result:

```text
228 passed in 24.83s
```

Includes 001–009 suites plus 010 and baseline fix `test_scan_project_fixtures`.

---

## 4. QA Additional Verification (Static Review)

### 4.1 `evidence_chain.py` import surface

```text
SELECT: KbDocument, KbParseResult, KbDocumentChunk (count), KbEvidence (upsert)
WRITE:  mysql_insert → kb_document_chunk, kb_evidence
READ FS: parsed_text.md, parsed_metadata.json, parse_manifest.json
WRITE FS: optional --output JSON report only (reports path)
```

No imports of: `vault_paths`, parser services, quality checker/summarizer, `subprocess`.

### 4.2 CLI help contract

`build-evidence-chain --help` states parsed read-only, chunk/evidence DB writes only, no parsers/raw_vault/repair, `--dry-run` for zero DB writes. **PASS**

### 4.3 Baseline regression fix (`45b21e4`)

| Question | Finding |
|---|---|
| Root cause | `test_scan_project_fixtures` scanned entire `backend/tests/fixtures/`; 009 `parse_quality_report_*.json` (5 files) counted as documents → 7 vs expected 2 |
| Fix approach | Scope scan to `INVENTORY_FIXTURES_ROOT = FIXTURES_ROOT / "中文路径"` (original 2 txt duplicate pair) |
| Hides scanner bug? | **No** — scanner correctly treats `.json` as documents; test scope was wrong |
| `inventory_scanner.py` changed? | **No** |
| 009 fixtures deleted? | **No** |

---

## 5. DB Write Boundary Check

| Table / operation | Allowed | Observed | Result |
|---|---|---|---|
| `kb_document_chunk` INSERT/UPSERT | Yes | `mysql_insert(KbDocumentChunk.__table__)` | PASS |
| `kb_evidence` INSERT/UPSERT | Yes | `mysql_insert(KbEvidence.__table__)` | PASS |
| `kb_document` UPDATE/INSERT/DELETE | No | SELECT only | PASS |
| `kb_parse_run` / `kb_parse_result` / `kb_parsed_artifact` | No write | SELECT on `KbParseResult` only | PASS |
| `kb_review_item` / `kb_curated_asset` / `kb_embedding_ref` | No | Not referenced | PASS |
| Schema migration | No | None | PASS |

Dry-run path: upsert methods not called; `session.rollback()` at end of `build()`. **PASS**

---

## 6. Filesystem Boundary Check

| Boundary | Expected | Observed | Result |
|---|---|---|---|
| raw_vault `original.bin` | Do not read | No vault_paths; test spies Path.open — not called for original.bin | PASS |
| parsed artifacts | Read-only | `read_text` only; test verifies mtime unchanged | PASS |
| parsed mutation | None | No write to parsed tree | PASS |
| curated / raw_vault / parsed dirs | No writes | Test + static review | PASS |
| Report output | Optional JSON | `_write_report` writes `--output` path only | PASS |

Note: `source_file_path` on evidence may store manifest `parsed_text_path` or `source_vault_path` **string** — metadata reference only, not binary read. **Within contract.**

---

## 7. Forbidden Runtime Behavior Check

| Behavior | Expected | Evidence | Result |
|---|---|---|---|
| MarkItDown / MinerU / magic-pdf | Not called | No parser imports; mock assert_not_called test | PASS |
| Reparse / repair | Not performed | Missing parsed → skip + error message | PASS |
| LLM / semantic chunking | Not performed | Heading/page split only | PASS |
| Embedding / summarization | Not performed | Not present | PASS |
| 008/009 quality auto-fix | Not consumed | No quality service imports | PASS |

---

## 8. Defects

**None blocking.**

Informational (defer to P6, not P4 fix):

| ID | Severity | Note |
|---|---|---|
| INFO-1 | Low | No unit test for default skip when chunks exist without `--force` (logic present in `_has_existing_chunks`) |
| INFO-2 | Low | Upsert/idempotency validated via fake session; real MySQL E2E deferred to P6 |

---

## 9. P5 Change Summary

P5 modified **documentation only**:

```text
specs/010-evidence-chain/p5_qa_report.md  (this file)
```

No test or production code changes required.

---

## 10. STOP

P5 completed. **Do not enter P6** until user confirms.

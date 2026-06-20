# 012 Search Service — P5 QA Report

> Role: QA Agent  
> Spec: `specs/012-search-service/`  
> Branch: `feature/012-search-service`  
> Stage: P5 QA Test & Regression  
> P4 base: 26 targeted tests / 272 full regression (Dev smoke)  
> P5 delta: +6 gap tests (32 targeted / 278 full)

---

## 1. QA Conclusion

**PASS WITH NON-BLOCKING NOTES**

012 Search Service P5 QA passed unit/regression review with no blocking defects. CLI contract, JSON envelope, SELECT-only guards, scope coverage, and project-filter path align with P3 gate. Six gap tests were added in P5 (table format, CLI exit codes, FULLTEXT SQL assertion, per-scope COUNT, evidence `project_uid` isolation).

**No production-code fixes were required in P5.**

P6 E2E remains mandatory for real MySQL ngram FULLTEXT validation (`ngram_token_size`, Chinese hit fidelity).

**STOP — await user confirmation before P6 E2E.**

---

## 2. Contract Alignment Review

| P3 contract area | Verdict | Evidence |
|------------------|---------|----------|
| `SearchService.search(SearchQuery) -> SearchResponse` | PASS | `search_service.py` L77–117 |
| `SearchQuery.validate_and_build` validation rules | PASS | `search.py` L41–82 |
| `SearchHit` / `SearchResponse` DTO fields | PASS | `search.py` L85–108 |
| JSON `report_type=search_results`, `schema_version=1.0` | PASS | `search_service.py` L26–28, L592–619 |
| `summary.total_count`, `hits[]` | PASS | `build_success_payload`; tests `test_json_output_shape` |
| `scope=all` merge algorithm (C9) | PASS | `_search_all_scopes` L140–170; gap test `test_scope_all_executes_per_scope_count` |
| Ranking: relevance DESC → hit_type → uid | PASS | `_hit_sort_key` L53–62; `test_scope_all_merge_and_sort` |
| `--project-code` via `kb_project` → `kb_project_document` | PASS | `_resolve_project_filter` L119–138; gap test `test_evidence_hits_via_project_document_not_evidence_project_uid` |
| CLI-only MVP (no FastAPI route) | PASS | No `api/v1/search` or `routes/search.py` |
| Chinese ngram C10 documented, no LIKE workaround | PASS | CLI docstring L950–955; `test_cli_help_documents_contract` |

**Non-blocking:** `summary.scopes_executed` always lists all five scopes even when project filter skips document/chunk/evidence due to empty `allowed_document_uids` (cosmetic; totals still correct).

---

## 3. White/Black List Compliance

### 3.1 P4 production whitelist (reviewed)

| File | Status |
|------|--------|
| `backend/app/services/search_service.py` | NEW — in whitelist |
| `backend/app/schemas/search.py` | NEW — in whitelist |
| `backend/app/cli/main.py` | MODIFIED — search-kb registration only (+imports) |
| `backend/tests/test_search_service.py` | NEW — in whitelist |
| `backend/tests/fixtures/search/chinese_evidence.fixture.json` | NEW — `.fixture` metadata only |

### 3.2 Blacklist / forbidden paths — no violations found

| Forbidden area | Checked | Result |
|----------------|---------|--------|
| `backend/app/models/**` | `git status` + diff | NOT modified |
| `sql/**`, `backend/migrations/**` | `git status` | NOT modified |
| Sealed services (`inventory_scanner`, `file_content_vault`, etc.) | diff scope | NOT modified |
| `backend/app/api/**`, `backend/app/main.py` | grep | NOT modified |
| `streamlit/**` | glob | NOT touched |
| `raw_vault/**`, `parsed/**`, `curated/**` runtime reads | code + tests | NOT invoked |
| Parser adapters / subprocess | tests T16 | NOT invoked |

### 3.3 Out-of-whitelist repo changes (non-P4 code)

Working tree also contains P1/P2/P3 spec artifacts and index sync (`README.md`, `docs/feature_index.md`, `specs/SPEC_INDEX.md`, `specs/012-search-service/*.md`). These are spec-phase deliverables, not P4 production scope. **No additional backend production files beyond whitelist.**

---

## 4. CLI Contract QA

Command: `search-kb` registered at `main.py` L897.

| Flag | Required by P3 | Implemented | Tested |
|------|----------------|-------------|--------|
| `--query` | Yes (required) | `typer.Option(...)` L904–907 | `test_cli_empty_query_exit_1` |
| `--scope` | `all\|document\|chunk\|evidence\|project\|curated` | L909–912 | per-scope tests + `test_cli_invalid_scope_exit_1` |
| `--project-code` | Optional | L914–917 | `test_cli_unknown_project_exit_1`, mapping tests |
| `--content-uid` / `--document-uid` | Optional | L919–927 | `test_content_uid_and_document_uid_filters` |
| `--limit` / `--offset` | Optional (1–100 / ≥0) | L929–937 | `test_limit_offset` |
| `--format json\|table` | Optional (default json) | L939–942 | json + **gap** `test_cli_table_format_smoke` |
| `--output` | Optional | L944–947 | `test_cli_output_file` |
| `--config` | Optional | L899–902 | used in CLI smoke tests |

**Exit codes:**

| Condition | Expected | Verified |
|-----------|----------|----------|
| Success (including zero hits) | 0 | `test_cli_no_hits_exit_0`, `test_cli_smoke_json` |
| Empty query | 1 `SEARCH_EMPTY_QUERY` | `test_cli_empty_query_exit_1` |
| Unknown `project_code` | 1 `SEARCH_PROJECT_NOT_FOUND` | `test_cli_unknown_project_exit_1` |
| Invalid scope | 1 `SEARCH_INVALID_SCOPE` | **gap** `test_cli_invalid_scope_exit_1` |

**Help text (C10):** docstring includes `ngram_token_size=2`, `kb_project_document`, `raw_vault` denial — `test_cli_help_documents_contract`.

---

## 5. DB SELECT-only QA

| Check | Result |
|-------|--------|
| All SQL starts with `SELECT` | `_assert_select_only` L37–42 |
| DML/DDL regex guard | `_DML_DENYLIST` L31–34; `test_select_only_guard_blocks_dml` |
| No INSERT/UPDATE/DELETE in executed SQL | `test_no_dml_in_executed_sql` |
| FULLTEXT `MATCH ... AGAINST ... NATURAL LANGUAGE MODE` | All five scopes; **gap** `test_fulltext_natural_language_mode_in_sql` |
| No SQL `LIKE` fallback | Grep + gap test — **no LIKE in SQL** |
| Per-scope COUNT + SELECT for `scope=all` | **gap** `test_scope_all_executes_per_scope_count` (5 COUNT queries) |

**Note:** P5 uses `_FakeSession` mock, not live MySQL row-count before/after (TC020–TC022 full table denylist). Live row-count guard deferred to **P6 E2E**.

---

## 6. Scope / Project Filter QA

| Scope | Hit test | UID traceability |
|-------|----------|------------------|
| `document` | `test_document_scope_hit` | `document_uid`, `content_uid` |
| `chunk` | `test_chunk_scope_hit` | `chunk_uid`, `document_uid`, `content_uid` |
| `evidence` | `test_evidence_scope_hit` | `evidence_uid`, `document_uid`, `content_uid`, `chunk_uid` |
| `project` | `test_project_scope_hit` | `project_uid`, `project_code` |
| `curated` | `test_curated_scope_hit` | `curated_uid`, `project_uid` |
| `all` | `test_scope_all_merge_and_sort` | merge + relevance sort |

**Project filter:**

- Resolution: `kb_project.project_code` → `kb_project_document.document_uid` (`_resolve_project_filter`).
- Evidence row seeded with `project_uid="should_not_filter"` still hits when `project_code=DEMO-2024` — **gap** `test_evidence_hits_via_project_document_not_evidence_project_uid`.
- SQL does not reference `e.project_uid` for filtering.
- Unknown code raises `SearchProjectNotFoundError` → CLI exit 1.
- Empty mapping returns zero hits, exit 0 — `test_project_code_excludes_unmapped_document`.

---

## 7. Forbidden Runtime QA

| Forbidden | Guard test | Result |
|-----------|------------|--------|
| Parser / subprocess | `test_no_parser_subprocess` | PASS |
| `raw_vault` / `parsed` filesystem read | `test_no_raw_vault_or_parsed_reads` | PASS |
| `curated/**` filesystem read | `test_no_curated_filesystem_reads` | PASS |
| LLM / embedding modules | `test_no_llm_or_embedding_imports` | PASS |
| FastAPI search route | repo grep | PASS — not present |
| Streamlit / UI | blacklist review | PASS — not touched |

Service code imports only: `sqlalchemy`, `app.core.config`, `app.core.database`, `app.schemas.search` — no parser/vault/parsed path modules.

---

## 8. Gap Tests Added

P5 added **6** tests to `backend/tests/test_search_service.py`:

| ID | Test | Maps to |
|----|------|---------|
| G01 | `test_cli_table_format_smoke` | TC014 |
| G02 | `test_cli_no_hits_exit_0` | TC008 (CLI path) |
| G03 | `test_cli_invalid_scope_exit_1` | P3 validation |
| G04 | `test_fulltext_natural_language_mode_in_sql` | C5 FULLTEXT primary |
| G05 | `test_scope_all_executes_per_scope_count` | C9 COUNT+SELECT×5 |
| G06 | `test_evidence_hits_via_project_document_not_evidence_project_uid` | TC011 |

No production code changes in P5.

---

## 9. Test Results

### 9.1 012 targeted tests (required)

```bash
PYTHONPATH=backend backend/.venv/bin/pytest backend/tests/test_search_service.py -q
```

```
32 passed in 0.69s
```

(P4: 26 passed → P5: +6 gap tests)

### 9.2 Full regression (required)

```bash
PYTHONPATH=backend backend/.venv/bin/pytest backend/tests -q
```

```
278 passed in 26.56s
```

(P4: 272 passed → P5: +6 from gap tests)

### 9.3 TC001–TC026 mapping (unit/mock layer)

| TC | Status | Notes |
|----|--------|-------|
| TC001–TC006 | PASS | Per-scope + scope=all |
| TC007–TC009 | PASS | Validation + pagination |
| TC010–TC011c | PASS | Project + uid filters |
| TC012 | PASS | Chinese fixture metadata |
| TC013–TC015 | PASS | JSON + output; TC014 via G01 |
| TC016–TC019 | PASS | Forbidden runtime mocks |
| TC020–TC023 | PARTIAL | DML guard on fake session; live row-count → P6 |
| TC024 | PASS | 278/278 regression |
| TC025–TC026 | PASS | Curated/evidence hits in seed data |

---

## 10. Remaining Risks / Non-blocking Notes

1. **Real MySQL ngram not exercised in P5** — `_FakeSession` simulates token substring match, not InnoDB FULLTEXT scoring. P6 must run `search-kb` against test MySQL and record `SHOW VARIABLES LIKE 'ngram_token_size'`.
2. **Single-character Chinese queries** — documented in CLI help; behavior unverified on live DB until P6 (C10).
3. **TC020–TC022 live row counts** — fake-session DML guard only; P6 should assert denylist table counts unchanged after CLI search.
4. **`scopes_executed` cosmetic** — always lists five scopes even when project filter short-circuits document/chunk/evidence with empty mapping.
5. **Evidence `matched_field` selection** — post-query Python `in` check on quote/normalized text (snippet UX only); SQL remains FULLTEXT-only, not LIKE fallback.
6. **Config load failure** — CLI prints plain `ERROR:` text (not `search_error` JSON envelope) when `--config` missing; acceptable MVP; document if P6 observes operator confusion.
7. **Remote branch verification** — P2 noted SSH unavailable; operator should confirm `feature/012-search-service` remote state before merge.

---

## 11. P6 E2E Readiness

| Prerequisite | P5 status |
|--------------|-----------|
| P4 implementation complete | YES |
| P5 QA PASS (non-blocking notes) | YES |
| Unit tests green | YES (32 + 278) |
| CLI contract locked | YES |
| DB SELECT-only design | YES (code review + mock guards) |
| No blocking bugs | YES |

**P6 recommended chain:**

```text
1. Apply init schema FULLTEXT indexes on test MySQL (if not already).
2. Seed or reuse 010/011 sample rows (document, chunk, evidence, project, curated).
3. Record SHOW VARIABLES LIKE 'ngram_token_size'.
4. Run search-kb per scope + scope=all + --project-code.
5. Assert UID traceability on hits.
6. Assert denylist table row counts unchanged pre/post search.
7. Chinese multi-char + single-char query outcomes (C10).
8. Produce specs/012-search-service/p6_e2e_report.md.
```

**P6 must NOT:** modify production code unless blocking defect found; enter P7/P8; write migrations.

---

## P5 STOP

P5 QA complete. **Do not enter P6 E2E until user confirms.**

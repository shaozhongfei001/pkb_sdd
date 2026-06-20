# 012 Search Service — Handoff

> Spec: `specs/012-search-service/`  
> Branch: `feature/012-search-service` → merged to `main`  
> Stage: P8 Handoff & Final Commit  
> Status: **DONE**

---

## 1. Completion Summary

012 Search Service has been completed.

The feature provides **read-only** MySQL FULLTEXT keyword search over 010/011-populated tables:

- CLI: `search-kb`
- Service: `SearchService`
- Mechanism: `MATCH ... AGAINST` in **NATURAL LANGUAGE MODE** on existing ngram FULLTEXT indexes
- Scopes: `document` / `chunk` / `evidence` / `project` / `curated` / `all`
- `scope=all`: five per-scope COUNT+SELECT → merge → relevance sort → global offset/limit
- `--project-code` filter via `kb_project` → `kb_project_document` (not `kb_evidence.project_uid`)

It does **not** read `raw_vault` / `parsed` / curated filesystem content, call parsers, LLM, embedding, subprocess, or Streamlit. It does **not** write any MySQL table (SELECT-only MVP).

**P7 Final Review: PASS WITH NOTES** — no blocking defects.

---

## 2. P1–P8 Stage Chain

| Stage | Deliverable | Commit |
|---|---|---|
| P1 | Plan + SPEC_INDEX | `f5723c1` |
| P2 | DB Review PASS WITH CONSTRAINTS | `a9de72d` |
| P3 | Implementation gate PASS | `1aa38a7` |
| P4 | Dev implementation | `483bdbc` |
| P5 | QA report PASS + gap tests | `6d155cf` |
| P6 | E2E PASS WITH NOTES | `ef12cbb` |
| P7 | Final review PASS WITH NOTES | `325ebb4` |
| P8 | This handoff + merge | (P8 commit) |

---

## 3. P2 DB Review — Key Constraints

**P2-GATE: PASS WITH CONSTRAINTS**

| ID | Constraint |
|---|---|
| C1 | No schema migration for MVP — reuse init SQL FULLTEXT indexes as-is |
| C2 | No new ORM models — read existing tables via SQL/text |
| C3 | MVP is SELECT-only — zero INSERT/UPDATE/DELETE on any MySQL table |
| C4 | No `kb_search_log` / audit table in MVP |
| C5 | Primary search: `MATCH ... AGAINST` ngram FULLTEXT (NATURAL LANGUAGE MODE) |
| C6 | LIKE fallback NOT required for MVP |
| C7 | `--project-code` MUST use `kb_project` → `kb_project_document` JOIN |
| C8 | Do NOT use `kb_evidence.project_uid` for project scoping (011 C8) |
| C9 | `scope=all`: per-scope FULLTEXT → tag hit_type → merge-sort by relevance |
| C10 | `ngram_token_size=2` — single-character Chinese queries may return no hits |
| C11 | NULL indexed columns excluded from FULLTEXT matches |
| C12 | Optional enrichment JOIN `kb_document` on chunk/evidence hits — SELECT only |
| C13 | Optional `KbFileContent` / `KbParseResult` enrichment — not required MVP |
| C14 | Do not read raw_vault, parsed FS, curated FS for search text |
| C15 | Do not write review/embedding/chunk/evidence/project/curated/parse registry |
| C16 | MySQL 8.0+ ngram FULLTEXT validated in P6 |
| C17 | Do not modify init SQL, migrations, or existing ORM model files |

---

## 4. P3 Whitelist / Blacklist Summary

**P4 whitelist (only):**

```text
backend/app/services/search_service.py
backend/app/schemas/search.py
backend/app/cli/main.py
backend/tests/test_search_service.py
backend/tests/fixtures/search/**
```

**Forbidden:**

- Parser / LLM / embedding / Streamlit / subprocess invocation
- Read `raw_vault` / `parsed` / curated filesystem for search text
- Modify parsed artifacts, curated files, or original user files
- Write any MySQL table (MVP SELECT-only)
- FastAPI `GET /api/v1/search` (deferred per P3 CLI-only MVP)
- Schema migration; sealed services; `backend/app/models/**` edits

---

## 5. P4 Implementation

### 5.1 Components

| Component | Path |
|---|---|
| CLI | `search-kb` in `backend/app/cli/main.py` |
| Service | `backend/app/services/search_service.py` — `SearchService` |
| Schemas | `backend/app/schemas/search.py` — `SearchQuery`, `SearchHit`, response DTOs |
| Tests | `backend/tests/test_search_service.py` (32 tests) |
| Fixtures | `backend/tests/fixtures/search/**` |

### 5.2 Search Mechanics

- All scopes use `MATCH(column) AGAINST (:q IN NATURAL LANGUAGE MODE)`
- `_assert_select_only` + DML denylist on every executed query
- `scope=all`: `_search_all_scopes` — five COUNT+SELECT queries, merge, sort by `relevance_score DESC`, global offset/limit
- Project filter: `_resolve_project_filter` → `document_uid IN (...)` from `kb_project_document`
- Snippet max 200 chars; ranking: relevance → hit_type rank → uid

---

## 6. CLI Contract

```bash
PYTHONPATH=backend python -m app.cli.main search-kb \
  --config config/app.yaml \
  --query "<keywords>" \
  --scope all|document|chunk|evidence|project|curated \
  --project-code <code> \
  --limit 20 \
  --offset 0 \
  --format json|table \
  --output /path/to/search_results.json
```

| Flag | Required | Notes |
|---|---|---|
| `--query` | Yes | Non-empty keywords; empty rejected (exit 1) |
| `--scope` | No | Default `all`; one of six scope values |
| `--project-code` | No | Filters via `kb_project_document` mapping |
| `--limit` | No | Default 20; pagination cap |
| `--offset` | No | Default 0; global offset for merged results |
| `--format` | No | `json` (default) or `table` |
| `--output` | No | Optional JSON results file (operator path only) |
| `--config` | No | Defaults to `config/app.yaml` |

---

## 7. JSON Contract

| Field | Value |
|---|---|
| `report_type` | `search_results` |
| `schema_version` | `1.0` |
| `summary.total_count` | Total hits before offset/limit |
| `summary.scopes_executed` | Scopes queried (cosmetic: always lists five for `scope=all`) |
| `hits[]` | Array of hit objects with traceability UIDs |

Each hit includes applicable identity fields: `document_uid`, `content_uid`, `chunk_uid`, `evidence_uid`, `project_uid`, `project_code`, `curated_uid`, `hit_type`, `snippet`, `relevance_score`, metadata.

---

## 8. DB Boundary

**MVP runtime: SELECT-only**

- No INSERT / UPDATE / DELETE on any table
- No `session.commit()` in search path
- No SQL `LIKE` fallback on MEDIUMTEXT columns
- P6 verified 12 tables row-count delta **0** across 13 CLI runs

**Queried tables (SELECT):**

- `kb_document`, `kb_document_chunk`, `kb_evidence`, `kb_project`, `kb_project_document`, `kb_curated_asset`

---

## 9. Forbidden Runtime Boundaries

**Must not:**

- read `raw_vault` binary objects or filesystem paths for search text
- read `parsed_text.md`, `parsed_metadata.json`, or `parse_manifest.json`
- read curated Markdown files on disk (curated scope uses `kb_curated_asset.asset_title`)
- call MarkItDown, MinerU, `magic-pdf`, or any parser adapter
- invoke `subprocess`
- call LLM query expansion or semantic judgment
- call embedding generation or vector stores
- write `kb_review_item`, `kb_embedding_ref`, chunk/evidence, project/curated, or parse registry
- start Streamlit or register new FastAPI search routes (API deferred per P3)

**Storage:**

- `raw_vault` / `parsed` / `curated` mtime unchanged after search (P6 verified)
- Only operator `--output` JSON may be written (not DB, not asset dirs)

---

## 10. Test Results

| Suite | Result |
|---|---|
| 012 specialized pytest | **32 passed** |
| Full `backend/tests` | **278 passed** |

---

## 11. P6 E2E Results

Validated with real `config/app.yaml`, real MySQL, and 010/011 sample.

| Field | Value |
|---|---|
| MySQL version | **8.0.46** |
| `ngram_token_size` | **2** |
| Config | real `config/app.yaml` |
| Sample | real 010/011 P6 residue |
| `project_code` | `P6-YHXM-011` |
| `content_uid` | `536985990c2e2203a74c297bf66c7939873e53647bb41fb9cc72bb42bd6463d6` |

| Check | Result |
|---|---|
| Five scopes + `scope=all` | PASS — chunk/evidence/project/curated hits; document 0 (NULL titles) |
| `--project-code P6-YHXM-011` | PASS — mapping filter via `kb_project_document` |
| 12 tables before/after | **delta 0** |
| `raw_vault` / `parsed` / `curated` mtime | unchanged |
| Forbidden runtime | no parser / LLM / embed / UI |

P6 reports: `/tmp/pkb_sdd_012_p6/*.json` (not in git).

---

## 12. P6 Non-Blocking Notes

| Note | Assessment |
|---|---|
| `scope=document` returns 0 hits for some keywords when `kb_document.title IS NULL` | Data condition, not search defect |
| Single-character Chinese query (`银`) returns 0 hits | Expected per `ngram_token_size=2` (C10) |
| `summary.scopes_executed` always lists five scopes even when per-scope COUNT=0 | Cosmetic display; counts unaffected |

---

## 13. Current Final State

| Item | Status |
|---|---|
| Specs 001–012 | **DONE** |
| Current ACTIVE spec | **None** — requires Active Spec Selection Review before next work |
| `013-streamlit-admin` | **FUTURE — not started** |
| `008-review-workflow` | **FUTURE STUB / NOT CURRENT** (≠ completed 008 parse quality checker) |

---

## 14. Spec / Review Artifacts

```text
specs/012-search-service/spec.md
specs/012-search-service/plan.md
specs/012-search-service/tasks.md
specs/012-search-service/acceptance.md
specs/012-search-service/test_cases.md
specs/012-search-service/p2_db_review.md
specs/012-search-service/p3_implementation_gate.md
specs/012-search-service/p5_qa_report.md
specs/012-search-service/p6_e2e_report.md
specs/012-search-service/p7_final_review.md
```

---

## 15. Next Stage

**Do not auto-start the next spec.**

Before any new implementation:

1. Read `specs/SPEC_INDEX.md`
2. Run explicit **Active Spec Selection Review**
3. Do **not** infer active spec from directory numbering

Potential future specs (not active until index says so):

- `specs/013-streamlit-admin/` — **not started**
- `specs/008-review-workflow/` — future stub, **NOT CURRENT**

---

## 16. Merge Notes

Branch `feature/012-search-service` merged to `main` after P8 handoff commit.

P8 did not modify `backend/**`, `sql/**`, `raw_vault/**`, `parsed/**`, or repo `curated/**`.

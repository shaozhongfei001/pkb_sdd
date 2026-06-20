# 012 Search Service — plan.md

> Project: `pkb_sdd`  
> Phase: `P1 Tech Lead Plan — COMPLETE (awaiting user review)`  
> Status: `ACTIVE SPEC / NOT IMPLEMENTED`  
> Implementation status: `NOT STARTED (P4 blocked until P1–P3 approved)`

---

## 1. Architecture Overview

012 adds a read-only search service over existing MySQL FULLTEXT indexes populated by 010/011:

```text
CLI search-kb  /  optional GET /api/v1/search
        |
        v
SearchService                              [P4]
        |
        +--> SQLAlchemy session (SELECT only)
        |
        +--> MATCH ... AGAINST per scope / UNION for all
        |
        +--> optional JOIN kb_project_document for --project-code
        |
        v
SearchResponse (hits + pagination meta)
```

Proposed component (P4 — not implemented in P1):

```text
backend/app/services/search_service.py
```

Proposed schemas (P4 — optional):

```text
backend/app/schemas/search.py             # SearchHit, SearchResponse
backend/app/api/routes/search.py          # optional FastAPI route
```

Proposed ORM (read-only — verify in P2):

```text
backend/app/models/document.py            # KbDocument
backend/app/models/evidence.py            # KbDocumentChunk, KbEvidence
backend/app/models/project.py             # KbProject, KbProjectDocument, KbCuratedAsset
```

Proposed CLI (P4):

```text
backend/app/cli/main.py                   # register search-kb
```

Proposed tests (P5):

```text
backend/tests/test_search_service.py
backend/tests/fixtures/search/
```

---

## 2. Logical Flow

```text
1. Load config (mysql, pipeline_version).
2. Validate --query non-empty; normalize scope enum.
3. If --project-code provided:
     resolve project_uid from kb_project.project_code
     build allowed document_uid set from kb_project_document
4. For each requested scope (or single scope):
     a) Build MATCH ... AGAINST query against documented FULLTEXT index
     b) Apply document_uid / content_uid filters
     c) Apply project document_uid restriction when project filter active
     d) Fetch relevance score + locator columns for snippet
5. Merge results for scope=all (tag hit_type per row).
6. Sort by relevance_score DESC (P3 lock tie-breakers).
7. Apply limit/offset pagination.
8. Format json|table; optional --output JSON file.
9. Log query scope, hit count, duration; no DB writes.
```

No step may invoke parsers, read raw_vault binaries, read parsed files, or write review/embedding/curated records.

---

## 3. Service Design (Planned — P4)

### 3.1 Proposed Class

```python
class SearchService:
    def __init__(self, config: AppConfig, session_factory) -> None: ...

    def search(
        self,
        *,
        query: str,
        scope: str = "all",
        project_code: str | None = None,
        content_uid: str | None = None,
        document_uid: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> SearchResponse:
        ...
```

P3 finalizes signatures and validation rules.

### 3.2 Internal Concepts

```text
SearchResponse
  query, scope, total_count, hits[], limit, offset

SearchHit
  hit_type, matched_field, snippet, relevance_score,
  evidence_uid, document_uid, content_uid, chunk_uid,
  project_uid, project_code, curated_uid, metadata

ProjectDocumentFilter
  project_uid, allowed_document_uids[]
```

### 3.3 FULLTEXT Query Pattern (illustrative — P2 validates)

```sql
SELECT document_uid, content_uid, title,
       MATCH(title) AGAINST (:q IN NATURAL LANGUAGE MODE) AS score
FROM kb_document
WHERE MATCH(title) AGAINST (:q IN NATURAL LANGUAGE MODE)
ORDER BY score DESC
LIMIT :limit OFFSET :offset;
```

Chinese ngram behavior must be validated in P2/P6 against real data.

---

## 4. Scope Query Mapping (MVP — P2/P3 lock)

| scope | Primary table | FULLTEXT key | Snippet source |
|---|---|---|---|
| `document` | `kb_document` | `ftx_document_title` | `title` |
| `chunk` | `kb_document_chunk` | `ftx_chunk_content` | truncated `content` |
| `evidence` | `kb_evidence` | `ftx_evidence_text` | `quote_text` or `normalized_text` |
| `project` | `kb_project` | `ftx_project_name_desc` | `project_name` / `description` |
| `curated` | `kb_curated_asset` | `ftx_curated_asset_title` | `asset_title` |

`scope=all` executes per-scope queries (or UNION ALL with hit_type column) — P2 recommends performant approach.

---

## 5. Config Usage

012 reads:

```text
config.mysql (connection via standard session factory — P4)
config.pipeline_version (optional logging metadata)
```

012 must not read/write for feature purposes:

```text
raw_vault/**
parsed/**
curated/** (filesystem)
reports_root for 008/009 auto-consumption
curated_root for file reads (MVP uses kb_curated_asset DB rows)
```

P2 must confirm `AppConfig` mysql block is sufficient; no new config keys required for MVP unless P2 identifies need.

---

## 6. Idempotency (Read-only MVP)

Design intent:

```text
Repeated identical search queries return the same hits for the same DB snapshot.
No DB side effects => no upsert/idempotency keys required for MVP.
```

P2 confirms SELECT-only and documents any session/cache behavior.

---

## 7. Dev File Whitelist Preview (P3 reference)

**Allowed (P4):**

```text
backend/app/services/search_service.py       # new
backend/app/schemas/search.py              # new (if API MVP)
backend/app/api/routes/search.py           # new (if API MVP)
backend/app/api/main.py or app factory     # register route (if API MVP)
backend/app/cli/main.py
backend/tests/test_search_service.py         # new
backend/tests/fixtures/search/               # synthetic DB rows
```

**Forbidden:**

```text
backend/app/services/inventory_scanner.py
backend/app/services/file_content_vault.py
backend/app/services/evidence_chain.py
backend/app/services/curated_project_assets.py
backend/app/services/markitdown_parser.py
backend/app/services/mineru_pdf_parser.py
backend/app/services/parse_registry.py
backend/app/services/parse_quality_checker.py
backend/app/services/parse_quality_report_summarizer.py
streamlit/**                                 # 013 scope
sql/** without approved migration
raw_vault/** parsed/** curated/** (no mutation)
```

---

## 8. Exception Handling

| Scenario | Handling |
|---|---|
| empty `--query` | Fail fast with clear error; exit non-zero |
| invalid `--scope` | Fail fast with allowed enum list |
| `--project-code` not found | Empty result or clear error (P3 lock) |
| no FULLTEXT matches | Empty hits; total_count=0; success |
| MySQL connection failure | Log error; fail with non-zero exit |
| Chinese query / content | Must succeed when data exists |
| SQL timeout / syntax error | Log query context; fail gracefully |
| single scope SQL error in `all` | Log scope; continue other scopes or fail batch (P3 lock) |

---

## 9. P2 DB Review Checklist (Mandatory before P4)

```text
[ ] FULLTEXT indexes documented per MVP scope in init SQL
[ ] ngram MATCH ... AGAINST syntax validated for Chinese
[ ] ORM models exist for all queried tables
[ ] --project-code filter JOIN via kb_project_document documented
[ ] kb_evidence.project_uid NOT required for project filter (011 C8)
[ ] SELECT-only MVP confirmed — zero DML tables
[ ] No invented columns vs sql/001_init_schema_v1_1.sql
[ ] Migration need assessed — if yes, STOP P4 until migration merged
[ ] Pagination + relevance ordering strategy documented
[ ] scope=all UNION performance acceptable for MVP dataset
[ ] No raw_vault / parsed filesystem read in design
[ ] No parser re-invocation in design
```

If FULLTEXT coverage / ORM insufficient → **STOP** at P2.

---

## 10. P1 Deliverables Checklist

```text
[x] spec.md
[x] plan.md
[x] tasks.md
[x] acceptance.md
[x] test_cases.md
[x] SPEC_INDEX.md updated (012 ACTIVE / NOT IMPLEMENTED)
[x] README.md 012 active sync
[x] docs/feature_index.md 012 ACTIVE sync
[ ] backend/** implementation        # out of P1 scope
[ ] STOP — await user P1 review → P2 DB Review
```

---

## 11. P1 STOP

No P2/P3/P4 until user approves P1.

No `backend/**` changes in P1.

Remote `origin/main` verification: attempted in P1 environment; SSH failed — local `origin/main` at `f698e26`; operator should confirm remotely when SSH available.

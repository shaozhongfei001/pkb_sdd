# 013 Streamlit Admin — plan.md

> Project: `pkb_sdd`  
> Phase: `P1 Tech Lead Plan — COMPLETE (awaiting user review)`  
> Status: `ACTIVE SPEC / NOT IMPLEMENTED`  
> Implementation status: `NOT STARTED (P4 blocked until P1–P3 approved)`

---

## 1. Architecture Overview

013 adds a read-only Streamlit admin UI consuming 001–012 backend contracts:

```text
streamlit run frontend/streamlit_admin/app.py
        |
        v
Streamlit pages (st.navigation or multipage)
        |
        +--> lib/config_loader.py          # AppConfig from app.yaml
        +--> lib/db_session.py             # SQLAlchemy session factory (SELECT)
        +--> lib/search_client.py          # thin SearchService wrapper
        +--> lib/evidence_repository.py    # SELECT kb_evidence / kb_document_chunk
        +--> lib/project_repository.py     # SELECT kb_project / kb_curated_asset
        +--> lib/registry_repository.py    # SELECT kb_parse_*
        +--> lib/report_reader.py          # list/read reports_root files
        +--> lib/curated_reader.py         # read curated_root Markdown
        |
        v
Operator browser (local)
```

Backend dependency (read-only — no modification in 013 P4 whitelist for services):

```text
backend/app/services/search_service.py     # 012 — import only
backend/app/core/config.py                 # AppConfig
backend/app/core/database.py               # session factory
backend/app/models/*                       # ORM SELECT
```

Proposed frontend tree (P4 — not created in P1):

```text
frontend/streamlit_admin/
  app.py
  pages/
    01_kb_search.py
    02_evidence_explorer.py
    03_projects_curated.py
    04_parse_registry.py
    05_quality_reports.py
    06_inventory_snapshot.py               # optional MVP page
  lib/
    config_loader.py
    db_session.py
    search_client.py
    evidence_repository.py
    project_repository.py
    registry_repository.py
    report_reader.py
    curated_reader.py
    formatters.py
```

Proposed tests (P5):

```text
backend/tests/test_streamlit_admin_lib.py   # lib layer unit tests (import lib via path hack or package layout)
backend/tests/fixtures/streamlit_admin/
```

UI manual checklist documented in P5/P6 (Streamlit not headless-automated in MVP unless P3 approves).

---

## 2. Logical Flow

### 2.1 App bootstrap

```text
1. Resolve config path (default config/app.yaml or PKB_CONFIG env).
2. Load AppConfig via backend config loader.
3. Initialize read-only SQLAlchemy session factory (shared pattern with CLI).
4. Render sidebar navigation for MVP pages.
5. On page load: open session, execute SELECT or SearchService call, close session.
6. On error: log + st.error with operator message; do not expose raw stack trace by default.
```

### 2.2 KB Search page

```text
1. Render query input, scope select, optional project_code, limit/offset controls.
2. Validate query non-empty (mirror 012).
3. Call SearchService.search(...) in-process.
4. Display hits table: hit_type, snippet, relevance_score, UIDs.
5. Offer "View evidence" action when evidence_uid present -> navigate to Evidence Explorer.
```

### 2.3 Evidence Explorer page

```text
1. Optional filters: evidence_uid, document_uid, content_uid, chunk_uid.
2. SELECT from kb_evidence JOIN kb_document / kb_document_chunk as needed.
3. Display quote_text, locators, UIDs.
4. No edit/save controls in MVP.
```

### 2.4 Projects & Curated page

```text
1. List kb_project rows; select project_code.
2. Show kb_project_document mapping and kb_curated_asset list.
3. For selected asset: resolve file_path under curated_root; read Markdown; st.markdown render.
4. Read-only — no save.
```

### 2.5 Parse Registry page

```text
1. List recent kb_parse_run rows (ORDER BY created_at DESC, limit N).
2. Expand to kb_parse_result + kb_parsed_artifact for selected run.
3. Display parser_profile, status, content_uid references from registry metadata.
4. No re-parse button in MVP.
```

### 2.6 Quality Reports page

```text
1. Glob reports_root for parse_quality_report*.json and parse_quality_summary*.md/json.
2. Sort by mtime; let operator pick file.
3. Display JSON (structured) or Markdown (rendered) read-only.
4. Do not invoke 008/009 CLIs to regenerate.
```

### 2.7 Inventory Snapshot page (optional MVP)

```text
1. SELECT COUNT summaries from kb_file_instance, kb_file_content.
2. Optional paginated table: file_instance_uid, absolute_path (metadata), sha256, copy_status.
3. Do not read raw_vault binaries; do not offer vault copy action.
```

No step may invoke parsers, write review items, mutate originals, or hand-write FULLTEXT SQL outside SearchService.

---

## 3. Component Design (Planned — P4)

### 3.1 search_client.py

```python
def search_kb(
    config: AppConfig,
    *,
    query: str,
    scope: str = "all",
    project_code: str | None = None,
    content_uid: str | None = None,
    document_uid: str | None = None,
    limit: int = 20,
    offset: int = 0,
) -> SearchResponse:
    service = SearchService(config)
    return service.search(...)
```

P3 finalizes error mapping to Streamlit messages.

### 3.2 Repository modules

Each repository module:

```text
- accepts session or session_factory
- SELECT only
- maps ORM rows to plain dicts/DTOs for Streamlit display
- no business logic duplication from sealed services
```

P2 validates table/column mapping per repository.

### 3.3 Session lifecycle

```text
Prefer context manager per request/page interaction:
  with session_factory() as session:
      ...
Streamlit reruns: avoid leaking connections; P2 reviews pool settings.
```

---

## 4. Config Usage

013 reads via AppConfig:

```text
config.mysql              # DB connection
config.reports_root       # Quality Reports page
config.curated_root       # Projects & Curated page
config.pipeline_version   # optional display in sidebar/footer
```

013 must not require new config keys for MVP unless P2 identifies need.

013 must not write config files.

---

## 5. Idempotency (Read-only MVP)

```text
UI reruns and repeated page loads perform read-only queries.
No DB side effects => no upsert/idempotency keys required for MVP.
Curated/report file reads are idempotent (content unchanged unless external pipeline ran).
```

---

## 6. Dev File Whitelist Preview (P3 reference)

**Allowed (P4):**

```text
frontend/streamlit_admin/**                  # new tree
backend/requirements.txt                     # add streamlit dependency if absent
backend/tests/test_streamlit_admin_lib.py    # new
backend/tests/fixtures/streamlit_admin/        # new
```

**Conditionally allowed (P3 lock — prefer import-only):**

```text
backend/app/api/routes/search.py              # only if P3 approves 012-deferred API sub-task
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
backend/app/services/search_service.py       # modify — 012 sealed unless defect spec
backend/app/cli/main.py                        # modify — out of 013 scope unless P3 exception
sql/** without approved migration
raw_vault/** parsed/**                         # no mutation
curated/**                                     # no mutation from UI
```

---

## 7. Exception Handling

| Scenario | Handling |
|---|---|
| config file missing | st.error; show expected path; stop DB pages |
| MySQL connection failure | st.error; log exception; other pages degrade gracefully |
| empty search query | st.warning; do not call SearchService |
| SearchService validation error | Display 012 error message |
| no search hits | st.info empty state |
| curated file missing on disk | st.warning with expected path; DB row still shown |
| report file malformed JSON | st.error with file path; no CLI re-run |
| Chinese path in inventory metadata | Display UTF-8 correctly |
| Streamlit rerun mid-query | Session closed cleanly; no connection leak (P6 verify) |

---

## 8. P2 DB Review Checklist (Mandatory before P4)

```text
[ ] SELECT-only MVP confirmed — zero DML on denylist tables
[ ] ORM models exist for all repository tables
[ ] Search page delegates to SearchService — no UI-layer FULLTEXT SQL
[ ] kb_file_instance path display is metadata-only (no vault bin read)
[ ] curated_root path join strategy documented vs kb_curated_asset.file_path
[ ] parse registry SELECT fields map to 006 schema
[ ] No invented columns vs sql/001_init_schema_v1_1.sql + 006 migration
[ ] Session factory reuse safe for Streamlit rerun model
[ ] Migration need assessed — if yes, STOP P4 until migration merged
[ ] Denylist: kb_review_item, kb_manual_correction, kb_embedding_ref — no writes
[ ] No parser subprocess design in UI
[ ] Inventory Snapshot optional page — P3 confirm in/out of MVP whitelist
```

If ORM / denylist / session coverage insufficient → **STOP** at P2.

---

## 9. Dependencies

**Python (P4 — P3 lock versions):**

```text
streamlit>=1.28   # P3 pin exact minimum
```

Reuse existing backend stack (SQLAlchemy, pydantic, etc.) via PYTHONPATH=backend.

No new cloud API dependencies.

---

## 10. P1 Deliverables Checklist

```text
[x] spec.md
[x] plan.md
[x] tasks.md
[x] acceptance.md
[x] test_cases.md
[x] SPEC_INDEX.md updated (013 ACTIVE / NOT IMPLEMENTED)
[x] README.md 013 active sync
[x] docs/feature_index.md 013 ACTIVE sync
[ ] frontend/** implementation        # out of P1 scope
[ ] backend/** implementation         # out of P1 scope
[ ] STOP — await user P1 review → P2 DB Review
```

---

## 11. P1 STOP

No P2/P3/P4 until user approves P1.

No `backend/**` or `frontend/**` changes in P1.

# 013 Streamlit Admin — spec.md

> Project: `pkb_sdd`  
> Spec Directory: `specs/013-streamlit-admin/`  
> Branch: `feature/013-streamlit-admin`  
> Phase: `P1 Tech Lead Plan — COMPLETE (awaiting user review)`  
> Status: `ACTIVE SPEC / NOT IMPLEMENTED`  
> Authority: `specs/SPEC_INDEX.md`  
> Scope: Read-only Streamlit admin UI over 001–012 CLI/DB contracts (P4+).

---

## 1. Background

The completed SDD chain through 012 is:

```text
001-file-inventory
002-file-content-vault
003-duplicate-governance
004-parser-router
005-markitdown-parser
006-parse-job-registry
007-mineru-pdf-parser-adapter
008-parse-quality-checker
009-quality-report-summary
010-evidence-chain
011-curated-project-assets
012-search-service
```

012 provides `SearchService` and CLI `search-kb` — read-only MySQL FULLTEXT search over 010/011-populated tables.

013 introduces the **Streamlit admin UI layer**: a local operator console to browse search hits, evidence, projects/curated assets, parse registry status, and quality reports — without re-implementing pipeline logic in the UI and without triggering parsers or DB writes in MVP.

The current active spec is:

```text
specs/013-streamlit-admin/
```

The following directories are **not** current implementation sources:

```text
specs/006-mineru-parser/           # deprecated stub
specs/007-quality-checker/         # deprecated stub
specs/008-review-workflow/         # future stub; NOT current 008 checker
specs/012-search-service/            # DONE; consumed by 013, not re-opened
```

---

## 2. Problem Statement

Without an admin UI:

```text
1. Operators must run multiple CLIs and ad-hoc SQL to explore KB state.
2. 012 search results lack a visual hit list with UID traceability and drill-down.
3. 010 evidence and 011 curated assets are hard to navigate relationally.
4. 008/009 quality reports under reports_root lack a read-only viewer.
5. Parse registry status (006) is invisible without direct SQL queries.
```

013 solves this by providing a **read-only Streamlit application** that consumes existing backend services and SELECT queries, without parsers, embeddings, review writes, or original-file mutation.

---

## 3. Goals

### 3.1 Functional Goals (MVP — P4 target)

```text
G001  Load config/app.yaml (mysql, reports_root, curated_root, pipeline_version).
G002  Streamlit entry: streamlit run frontend/streamlit_admin/app.py
      (with PYTHONPATH=backend so backend services are importable).
G003  Page: KB Search — invoke SearchService in-process (same contract as CLI search-kb).
G004  Page: Evidence Explorer — SELECT kb_evidence + kb_document_chunk; show UID locators.
G005  Page: Projects & Curated — SELECT kb_project / kb_curated_asset;
      render curated Markdown from curated_root (read-only filesystem).
G006  Page: Parse Registry — SELECT kb_parse_run / kb_parse_result / kb_parsed_artifact summaries.
G007  Page: Quality Reports — list and display latest 008 parse_quality_report.json
      and 009 summary Markdown/JSON under reports_root (read-only filesystem).
G008  Optional Page: Inventory Snapshot — read-only SELECT kb_file_instance / kb_file_content
      counts and metadata (no path mutation; no vault binary read).
G009  Chinese UI labels, Chinese query strings, and Chinese DB content (UTF-8).
G010  Global error handling: DB/file failures show operator-readable messages; app does not crash silently.
G011  MVP read-only: no INSERT/UPDATE/DELETE to MySQL (P2 must confirm).
G012  Every evidence view shows evidence_uid / document_uid / content_uid where applicable.
G013  Search page supports scope, project-code, limit, offset aligned with 012 SearchService API.
G014  Navigation from search hit to Evidence Explorer detail by UID (in-app drill-down).
G015  001–012 regression unaffected; UI does not modify sealed 001/002 services.
```

### 3.2 MVP Pages

| Page | Primary data source | Write scope |
|---|---|---|
| KB Search | `SearchService` → 012 FULLTEXT tables | None |
| Evidence Explorer | SELECT `kb_evidence`, `kb_document_chunk`, `kb_document` | None |
| Projects & Curated | SELECT `kb_project`, `kb_project_document`, `kb_curated_asset` + read `curated_root/**` Markdown | None |
| Parse Registry | SELECT `kb_parse_run`, `kb_parse_result`, `kb_parsed_artifact` | None |
| Quality Reports | Read `reports_root/**` (008 JSON, 009 MD/JSON) | None |
| Inventory Snapshot (optional) | SELECT `kb_file_instance`, `kb_file_content` metadata | None |

MVP does **not** include buttons to run inventory, vault copy, parse, evidence build, or curated build CLIs.

### 3.3 Safety Goals

```text
S001  Original user files remain read-only; UI provides no delete/move/rename/quarantine actions.
S002  raw_vault binary objects (original.bin) are not read or displayed.
S003  parsed artifact files are not read for MVP primary views (010 data already in MySQL).
S004  No parser re-invocation (MarkItDown / MinerU / magic-pdf).
S005  No automatic repair of 008/009 quality findings.
S006  No LLM summarization, semantic search, or embedding generation in UI.
S007  No writes to kb_review_item, kb_manual_correction, kb_embedding_ref, parse registry,
      chunk/evidence, project/curated tables, or inventory tables.
S008  Search queries go through SearchService only — UI must not hand-write MATCH ... AGAINST SQL.
S009  Curated Markdown display is read-only; no in-UI editing or save.
S010  Quality report viewer does not invoke check-parse-quality or summarize-quality-report CLIs.
```

---

## 4. Non-goals

013 explicitly must not (MVP / P1 lock):

```text
NG001  Trigger pipeline CLIs from UI (scan-inventory, copy-to-vault, parse-*, build-evidence-chain,
       build-curated-project, check-parse-quality, summarize-quality-report).
NG002  Review workflow (kb_review_item / kb_manual_correction) — 008-review-workflow scope.
NG003  Vector DB / embedding generation / kb_embedding_ref writes.
NG004  Semantic similarity search or LLM reranking beyond 012 SearchService.
NG005  Reparse, repair, auto-fix, or cleanup of pytest dirty records.
NG006  Read raw_vault original.bin for content extraction or preview.
NG007  Read parsed_text.md / parsed_metadata.json / parse_manifest.json for MVP primary views.
NG008  Call MarkItDown, MinerU, or magic-pdf.
NG009  Modify sealed 001/002 services or parse registry write behavior.
NG010  Move, delete, rename, or overwrite original user files.
NG011  Write or mutate curated/ Markdown files from UI.
NG012  Introduce schema migration in P4 without P2 DB Review approval.
NG013  Implement FastAPI routes unless P3 explicitly adds 012-deferred GET /api/v1/search
       as a separate sub-task (not required for 013 MVP).
NG014  Upload private documents to external cloud services.
NG015  Source-code repository analysis as KB assets.
NG016  Auto-delete duplicate files or execute 003 cleanup suggestions.
NG017  kb_task_log or audit table writes in MVP (defer unless P2 mandates).
```

---

## 5. In-scope Data Sources

### 5.1 Read-only filesystem

```text
config/app.yaml
reports_root/**          # 008 parse_quality_report.json, 009 summaries (read-only list + display)
curated_root/projects/** # 011 Markdown outputs (read-only render)
```

Must not read for MVP primary paths:

```text
raw_vault/**/original.bin
parsed/**                # parsed_text.md, parsed_metadata.json, parse_manifest.json
```

Duplicate/cleanup JSON reports may be displayed if already on disk under operator workspace paths (read-only); UI must not generate new reports in MVP.

### 5.2 Read-only MySQL (SELECT)

Expected tables (P2 must verify ORM coverage):

```text
kb_document
kb_document_chunk
kb_evidence
kb_project
kb_project_document
kb_curated_asset
kb_parse_run
kb_parse_result
kb_parsed_artifact
kb_file_instance          # optional Inventory Snapshot page
kb_file_content           # optional Inventory Snapshot page
kb_duplicate_group        # optional read-only summary (P3 lock)
```

Search path must use `SearchService` (012), not duplicate FULLTEXT SQL in UI layer.

### 5.3 Write MySQL (MVP default)

```text
None — SELECT-only MVP.
```

If P2 identifies mandatory session/audit logging requiring DML → STOP at P2; migration spec required before P4.

### 5.4 Write filesystem (MVP)

```text
None.
Streamlit may write local cache/session state only (browser session); no KB artifact writes.
```

---

## 6. Search Integration Model (MVP)

012 P3 locked **CLI-only** delivery; FastAPI `GET /api/v1/search` is deferred.

013 MVP integrates search by **in-process import**:

```python
from app.services.search_service import SearchService
```

Parameters exposed in UI (aligned with 012):

```text
query           # required; non-empty
scope           # all | document | chunk | evidence | project | curated
project_code    # optional
content_uid     # optional (P3 lock UI exposure)
document_uid    # optional (P3 lock UI exposure)
limit           # default 20, max 100 (P3 lock)
offset          # default 0
```

UI displays `SearchHit` fields: `hit_type`, `snippet`, `relevance_score`, traceability UIDs.

Subprocess fallback via `search-kb --format json` is **not** MVP default (P3 may document as fallback only).

---

## 7. Evidence & Curated Display Contract (Planned)

### 7.1 Evidence Explorer row (P3 finalizes columns)

```text
evidence_uid, document_uid, content_uid, chunk_uid (nullable),
quote_text, normalized_text, source_location, page_no (nullable),
heading_path (nullable), created_at
```

### 7.2 Curated asset row

```text
curated_uid, project_uid, project_code, asset_type, asset_title,
file_path (relative under curated_root), render Markdown body read-only
```

### 7.3 Traceability requirement

No fabricated UIDs; only DB-backed or file-backed values from 010/011 outputs.

Drill-down: selecting `evidence_uid` from Search page opens Evidence Explorer filtered to that UID.

---

## 8. Relationship with 001–012

```text
001–003 inventory/vault/duplicate  ->  optional read-only metadata views (no CLI trigger)
004–007 parse pipeline               ->  Parse Registry page (SELECT only)
008–009 quality reports              ->  Quality Reports page (filesystem read only)
010 evidence                         ->  Evidence Explorer + search scopes chunk/evidence
011 curated                          ->  Projects & Curated page
012 search                           ->  KB Search page via SearchService
013 UI                               ->  consumes above; never replaces pipeline services
```

013 never replaces 010, 011, or 012. Re-running pipeline CLIs is out of 013 MVP scope.

---

## 9. Streamlit Launch Contract (Planned — P4)

Proposed command:

```bash
cd /path/to/pkb_sdd
PYTHONPATH=backend streamlit run frontend/streamlit_admin/app.py \
  --server.headless true
```

Config path default: `config/app.yaml` (override via env `PKB_CONFIG` — P3 lock).

Forbidden UI actions (MVP):

```text
Run Parser / Reparse / Repair / Delete Original / Auto Dedup / Submit Review / Generate Embedding
```

**Note:** Streamlit app is P4. P1 creates specs only.

---

## 10. P2 DB Review Gate (Mandatory)

P2 must verify:

```text
SELECT-only MVP — confirm zero DML on all KB tables
ORM models exist for all UI-queried tables
Search page uses SearchService only — no duplicate FULLTEXT SQL in frontend
Inventory Snapshot (if in MVP) — confirm kb_file_instance path display is metadata-only
Curated page — confirm read curated_root aligns with kb_curated_asset.file_path
Parse Registry — confirm SELECT fields map to 006 schema columns
No undocumented fields invented by Dev
Session factory reuse from backend — connection pool / lifecycle safe for Streamlit
If audit table or new index required -> migration script + STOP before P4
Denylist unchanged: kb_review_item, kb_manual_correction, kb_embedding_ref writes forbidden
```

P1 **does not** assert "no migration required."

If schema / ORM coverage insufficient → **STOP**; P4 blocked.

---

## 11. Role Boundaries

| Role | 013 Responsibility |
|---|---|
| Tech Lead | P1 spec, P2/P3 gates, P7 final review |
| DB & Data | P2 SELECT-only / ORM / denylist review |
| Dev | P4 Streamlit + lib implementation within whitelist |
| QA | P5 lib tests + UI checklist |
| E2E | P6 real MySQL + Streamlit manual/E2E validation |

---

## 12. P1 STOP Condition

P1 ends after:

```text
specs/013-streamlit-admin/spec.md
specs/013-streamlit-admin/plan.md
specs/013-streamlit-admin/tasks.md
specs/013-streamlit-admin/acceptance.md
specs/013-streamlit-admin/test_cases.md
specs/SPEC_INDEX.md aligned (013 ACTIVE / NOT IMPLEMENTED)
README.md 013 active sync
docs/feature_index.md 013 ACTIVE sync
```

After P1, STOP. No P2/P3/P4 until user approves.

No `backend/**` or `frontend/**` code in P1.

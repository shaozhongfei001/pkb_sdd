# 013 Streamlit Admin — acceptance.md

> Project: `pkb_sdd`  
> Spec: `specs/013-streamlit-admin/`  
> Acceptance scope: read-only Streamlit admin UI over 001–012 contracts (P4+).

---

## 1. Acceptance Philosophy

013 is accepted when it provides a local Streamlit operator console to browse KB search results, evidence, projects/curated assets, parse registry status, and quality reports — without parsers, without embeddings, without review writes, without pipeline CLI triggers, and without mutation of original files, raw_vault, parsed, or curated artifacts.

MVP is SELECT-only plus read-only filesystem reads under `reports_root` and `curated_root` unless P2 explicitly expands write scope (not expected).

---

## 2. P1 Acceptance

```text
P1-A001 spec.md exists under specs/013-streamlit-admin/ (non-stub)
P1-A002 plan.md exists (non-stub)
P1-A003 tasks.md exists (non-stub)
P1-A004 acceptance.md exists (non-stub)
P1-A005 test_cases.md exists (non-stub)
P1-A006 SPEC_INDEX marks 013 ACTIVE / NOT IMPLEMENTED
P1-A007 SPEC_INDEX branch = feature/013-streamlit-admin
P1-A008 SPEC_INDEX keeps 001–012 DONE
P1-A009 SPEC_INDEX keeps 008-review-workflow FUTURE STUB / NOT CURRENT
P1-A010 SPEC_INDEX adds §4.8 013 boundary reference
P1-A011 README §9.5 reflects 013 ACTIVE / NOT IMPLEMENTED
P1-A012 docs/feature_index.md 013 ACTIVE sync
P1-A013 No backend/** files modified
P1-A014 No frontend/** files modified
P1-A015 No sql/** / migrations/** modified
P1-A016 No raw_vault/** / parsed/** / curated/** modified
P1-A017 P1 stops before P2/P3/P4
P1-A018 P1 does not pre-judge "no migration required"
P1-A019 MVP scope locked: read-only Streamlit admin UI
P1-A020 Non-goals documented: no parser/review/LLM/embed/pipeline-trigger/original mutation
```

---

## 3. Hard Acceptance Gates (Final — P7)

### A001 — Active Spec Alignment

Must implement from `specs/013-streamlit-admin/` only.

Must not use `008-review-workflow`, deprecated stubs, or re-open `012-search-service` as authority unless defect spec approved.

### A002 — Read Scope

SELECT from documented tables; search via `SearchService` only.

Read-only filesystem under `reports_root` and `curated_root` for display pages.

Does not re-run or modify 010/011/012 pipeline logic.

### A003 — No raw_vault Read

Does not open `original.bin` or read `raw_vault/**` for content display.

### A004 — No parsed Filesystem Read (MVP primary views)

Does not read `parsed_text.md`, `parsed_metadata.json`, or `parse_manifest.json` for MVP primary pages.

### A005 — No Parser Re-invocation

Does not call MarkItDown, MinerU, or magic-pdf.

Does not expose UI buttons to run parse/inventory/vault CLIs in MVP.

### A006 — DB Write Scope (MVP)

MVP performs **no** INSERT/UPDATE/DELETE.

Does not write `kb_document_chunk`, `kb_evidence`, `kb_project`, `kb_curated_asset`, parse registry, inventory tables, `kb_review_item`, or `kb_embedding_ref`.

### A007 — No Curated Filesystem Write

Does not write or edit under `curated/` from UI.

### A008 — Traceability

Evidence views and search hits show applicable `evidence_uid` / `document_uid` / `content_uid`.

Drill-down from search hit to evidence detail works for evidence hits.

### A009 — Read-only Idempotency

Repeated page loads on same DB snapshot perform equivalent read queries; no DB mutation.

### A010 — Original File Safety

User original files unchanged; UI provides no delete/move/rename/quarantine actions.

### A011 — No LLM / Embedding / Review

No LLM UI features, embedding generation, or review workflow writes.

### A012 — Search Integration

KB Search page uses in-process `SearchService`; no duplicate FULLTEXT SQL in frontend lib.

### A013 — No Repair / Reparse

Does not auto-fix 008/009 findings or trigger quality checker from UI.

### A014 — Chinese Support

Chinese query strings, Chinese DB content, and Chinese paths display correctly (UTF-8).

### A015 — Empty Search Query

Blank search query shows validation message; does not call SearchService with empty query.

### A016 — Regression

001–012 regression tests pass; 013 targeted lib tests pass.

### A017 — P2 DB Review

P2 DB Review PASS documented before P4 merge.

### A018 — Schema Discipline

No undocumented DB fields; migration if P2 required it.

### A019 — Quality Reports Read-only

Quality Reports page lists/displays existing 008/009 files; does not invoke 008/009 CLIs.

### A020 — Streamlit Launch

Documented launch command works with `PYTHONPATH=backend`.

---

## 4. Rejection Conditions

```text
R001  Invented DB columns not in approved schema
R002  P4 started without P2 DB Review PASS
R003  Parser re-invocation or pipeline CLI trigger from UI
R004  raw_vault binary read for display
R005  DB writes in MVP without P2 approval
R006  LLM / embedding / review writes
R007  UI-layer hand-written FULLTEXT SQL bypassing SearchService
R008  auto repair/reparse based on 008/009 from UI
R009  Sealed service modification (001/002) or unauthorized search_service.py edit
R010  Curated Markdown edit/save from UI
R011  Vector / semantic similarity features in MVP
R012  Original file delete/move/rename from UI
R013  Duplicate auto-delete or 003 cleanup execution from UI
```

---

## 5. Minimum Test Evidence (Final)

```text
013 lib unit tests: passed
001–012 regression: passed
Streamlit manual/E2E checklist: passed
Search page hits with UID traceability: passed
Evidence drill-down: passed
Curated Markdown read-only render: passed
Quality report read-only display: passed
Parse registry SELECT view: passed
no DB row count changes after UI session: passed
no review/embedding rows written: passed
original / parsed / raw_vault / curated unchanged: passed
```

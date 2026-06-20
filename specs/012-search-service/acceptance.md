# 012 Search Service — acceptance.md

> Project: `pkb_sdd`  
> Spec: `specs/012-search-service/`  
> Acceptance scope: read-only MySQL FULLTEXT search over evidence/chunk/document/project/curated metadata (P4+).

---

## 1. Acceptance Philosophy

012 is accepted when it provides unified keyword search over 010/011-populated MySQL FULLTEXT indexes without embeddings, without parsers, without filesystem reads of raw_vault/parsed/curated, and with full traceability via evidence_uid / document_uid / content_uid on applicable hits.

MVP is SELECT-only unless P2 explicitly expands write scope (not expected).

---

## 2. P1 Acceptance

```text
P1-A001 spec.md exists under specs/012-search-service/ (non-stub)
P1-A002 plan.md exists (non-stub)
P1-A003 tasks.md exists (non-stub)
P1-A004 acceptance.md exists (non-stub)
P1-A005 test_cases.md exists (non-stub)
P1-A006 SPEC_INDEX marks 012 ACTIVE / NOT IMPLEMENTED
P1-A007 SPEC_INDEX branch = feature/012-search-service
P1-A008 SPEC_INDEX keeps 001–011 DONE
P1-A009 SPEC_INDEX keeps 008-review-workflow FUTURE STUB / NOT CURRENT
P1-A010 SPEC_INDEX keeps 013-streamlit-admin FUTURE
P1-A011 README §9.4 reflects 012 ACTIVE / NOT IMPLEMENTED
P1-A012 docs/feature_index.md 012 ACTIVE sync
P1-A013 No backend/** files modified
P1-A014 No sql/** / migrations/** modified
P1-A015 No raw_vault/** / parsed/** / curated/** modified
P1-A016 P1 stops before P2/P3/P4
P1-A017 P1 does not pre-judge "no migration required"
P1-A018 MVP scope locked: MySQL FULLTEXT read-only search
P1-A019 Non-goals documented: no LLM/embed/review/parser/raw_vault/parsed/UI
```

---

## 3. Hard Acceptance Gates (Final — P7)

### A001 — Active Spec Alignment

Must implement from `specs/012-search-service/` only.

Must not use `008-review-workflow`, deprecated stubs, or `013-streamlit-admin` as authority.

### A002 — Read Scope

SELECT from documented tables with documented FULLTEXT indexes only.

Does not re-run or modify 010 evidence or 011 curated builder logic.

### A003 — No raw_vault Read

Does not open `original.bin` or read `raw_vault/**` for search.

### A004 — No parsed Filesystem Read

Does not read `parsed_text.md`, `parsed_metadata.json`, or `parse_manifest.json`.

### A005 — No Parser Re-invocation

Does not call MarkItDown, MinerU, or magic-pdf.

### A006 — DB Write Scope (MVP)

MVP performs **no** INSERT/UPDATE/DELETE.

Does not write `kb_document_chunk`, `kb_evidence`, `kb_project`, `kb_curated_asset`, parse registry, `kb_review_item`, or `kb_embedding_ref`.

### A007 — No Curated Filesystem Write

Does not write under `curated/` or modify curated Markdown files.

### A008 — Traceability

`chunk` and `evidence` hits include `document_uid` and `content_uid`.

`evidence` hits include `evidence_uid`.

### A009 — Read-only Idempotency

Repeated identical queries on same DB snapshot return equivalent hit sets (no DB mutation).

### A010 — Original File Safety

User original files unchanged.

### A011 — No LLM / Embedding / Review

No LLM query expansion, semantic rerank, embedding generation, or review workflow.

### A012 — No Streamlit UI

No Streamlit admin UI (013 scope). Optional FastAPI search route is allowed if P3 locks it.

### A013 — No Repair / Reparse

Does not auto-fix 008/009 findings or reparse content.

### A014 — Chinese Query Support

Chinese query strings and Chinese indexed content handled correctly.

### A015 — Empty Query Rejected

Blank `--query` fails with clear error; no unbounded table scan.

### A016 — Regression

001–011 regression tests pass; 012 targeted tests pass.

### A017 — P2 DB Review

P2 DB Review PASS documented before P4 merge.

### A018 — Schema Discipline

No undocumented DB fields; migration if P2 required it.

### A019 — Project Filter

`--project-code` filter uses `kb_project_document` mapping; does not require `kb_evidence.project_uid` backfill.

---

## 4. Rejection Conditions

```text
R001 Invented DB columns not in approved schema
R002 P4 started without P2 DB Review PASS
R003 Parser re-invocation
R004 raw_vault or parsed filesystem reads for search text
R005 DB writes in MVP without P2 approval
R006 LLM / embedding / review writes
R007 Streamlit UI scope in MVP
R008 auto repair/reparse based on 008/009
R009 Sealed service modification (001/002)
R010 Missing traceability UIDs on chunk/evidence hits
R011 Vector / semantic similarity search in MVP
R012 Writing kb_document_chunk or kb_evidence from 012
```

---

## 5. Minimum Test Evidence (Final)

```text
012 targeted tests: passed
001–011 regression: passed
MySQL FULLTEXT search E2E: passed
Chinese query hit test: passed
project-code filter test: passed
empty query rejected: passed
no DB row count changes after search: passed
no review/embedding rows written: passed
original / parsed / raw_vault unchanged: passed
```

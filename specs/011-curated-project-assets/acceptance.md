# 011 Curated Project Assets — acceptance.md

> Project: `pkb_sdd`  
> Spec: `specs/011-curated-project-assets/`  
> Acceptance scope: read evidence/chunk/document/registry; write curated files + project/curated DB records (P4+).

---

## 1. Acceptance Philosophy

011 is accepted when it builds curated project assets from 010 evidence and registry metadata without LLM distillation, without parsers, without review/search/UI scope creep, and with full traceability to evidence_uid / content_uid / document_uid.

DB writes require P2 DB Review PASS before P4.

---

## 2. P1 Acceptance

```text
P1-A001 spec.md exists under specs/011-curated-project-assets/ (non-stub)
P1-A002 plan.md exists (non-stub)
P1-A003 tasks.md exists (non-stub)
P1-A004 acceptance.md exists (non-stub)
P1-A005 test_cases.md exists (non-stub)
P1-A006 SPEC_INDEX marks 011 ACTIVE / PLANNED
P1-A007 SPEC_INDEX branch = feature/011-curated-project-assets
P1-A008 SPEC_INDEX keeps 001–010 DONE
P1-A009 SPEC_INDEX keeps 008-review-workflow FUTURE STUB / NOT CURRENT
P1-A010 README §9.3 reflects 011 ACTIVE / PLANNED
P1-A011 docs/feature_index.md renumber drift fixed
P1-A012 No backend/** files modified
P1-A013 No sql/** / migrations/** modified
P1-A014 No raw_vault/** / parsed/** / curated/** modified
P1-A015 P1 stops before P2/P3/P4
P1-A016 P1 does not pre-judge "no migration required"
P1-A017 MVP scope locked: template/rule generation + evidence index only
P1-A018 Non-goals documented: no LLM/embed/review/parser/search/UI
```

---

## 3. Hard Acceptance Gates (Final — P7)

### A001 — Active Spec Alignment

Must implement from `specs/011-curated-project-assets/` only.

Must not use `008-review-workflow`, deprecated stubs, `012-search-service`, or `013-streamlit-admin` as authority.

### A002 — Evidence / Registry Read Scope

Reads `kb_document`, `kb_document_chunk`, `kb_evidence`, and related registry tables (SELECT).

Does not re-run or modify 010 evidence builder logic.

### A003 — No raw_vault Binary Read

Does not open `original.bin` for content extraction.

### A004 — No Parser Re-invocation

Does not call MarkItDown, MinerU, or magic-pdf.

### A005 — parsed Read-only

If parsed files are read, they are not modified.

### A006 — DB Write Scope

Writes only `kb_project`, `kb_project_document`, and `kb_curated_asset` (MVP). No other table DML unless P2 explicitly expands.

Does not write `kb_document_chunk`, `kb_evidence`, `kb_review_item`, or `kb_embedding_ref`.

### A007 — Curated Filesystem Write Scope

Writes only under `{curated_root}/projects/{project_code}/` for MVP asset types:

```text
00_project_card.md
10_evidence_index.md
source_documents.md
```

### A008 — Traceability

Every curated artifact references `evidence_uid`, `content_uid`, and/or `document_uid` as documented in spec §7.2.

### A009 — Idempotency

Re-run on same project + same input produces no duplicate project/curated primary records without `--force`.

### A010 — Original File Safety

User original files unchanged.

### A011 — No LLM / Embedding / Review

No LLM distillation, semantic summarization, embedding, or review workflow.

### A012 — No Search / UI

No FULLTEXT search service (012) or Streamlit/FastAPI admin UI (013).

### A013 — No Repair / Reparse

Does not auto-fix 008/009 findings or reparse content.

### A014 — Chinese Path Support

Chinese project names, paths, and UTF-8 curated content handled correctly.

### A015 — Batch Failure Tolerance

Single project or document failure does not abort entire batch.

### A016 — Regression

001–010 regression tests pass; 011 targeted tests pass.

### A017 — P2 DB Review

P2 DB Review PASS documented before P4 merge.

### A018 — Schema Discipline

No undocumented DB fields; migration if P2 required it.

### A019 — generation_method

MVP assets use `generation_method = TEMPLATE_RULE`.

---

## 4. Rejection Conditions

```text
R001 Invented DB columns not in approved schema
R002 P4 started without P2 DB Review PASS
R003 Parser re-invocation
R004 raw_vault binary reads for text extraction
R005 parsed artifact modification
R006 LLM / embedding / review writes in MVP
R007 search-service or Streamlit scope in MVP
R008 auto repair/reparse based on 008/009
R009 Sealed service modification (001/002)
R010 Missing traceability (UID references) in curated output
R011 Missing idempotency proof
R012 Writing kb_document_chunk or kb_evidence from 011
```

---

## 5. Minimum Test Evidence (Final)

```text
011 targeted tests: passed
001–010 regression: passed
evidence → curated E2E: passed
curated files contain UID references: passed
parsed mtime unchanged (if parsed read): passed
original files unchanged: passed
idempotency re-run test: passed
no review/embedding rows written: passed
```

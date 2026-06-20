# 012 Search Service — tasks.md

> Project: `pkb_sdd`  
> Spec: `specs/012-search-service/`  
> Phase model: P1–P8  
> Current phase: `P1 Tech Lead Plan — COMPLETE (awaiting user review)`  
> Current implementation state: `NOT STARTED (P4 blocked)`

---

## 1. Cursor Role Model

| Role | Responsibility |
|---|---|
| Tech Lead Agent | Scope, contract, plan, gates, final review |
| DB & Data Agent | P2 FULLTEXT/ORM/read-only scope review |
| Dev Agent | P4 implementation within whitelist |
| QA Agent | P5 unit + regression tests |
| E2E Agent | P6 real MySQL search validation |

Mapping:

```text
P1/P3/P7/P8 = Tech Lead Agent
P2 = Tech Lead + DB & Data Agent
P4 = Dev Agent
P5 = QA Agent
P6 = E2E Agent
```

---

## 2. P1 — Tech Lead Plan

Owner: Tech Lead Agent

Goal:

```text
Create 012 design specs, align SPEC_INDEX, sync README and feature_index.
No backend implementation.
```

Deliverables:

```text
specs/012-search-service/spec.md
specs/012-search-service/plan.md
specs/012-search-service/tasks.md
specs/012-search-service/acceptance.md
specs/012-search-service/test_cases.md
specs/SPEC_INDEX.md (012 ACTIVE / NOT IMPLEMENTED)
README.md (012 active sync)
docs/feature_index.md (012 ACTIVE sync)
```

Forbidden:

```text
backend/**
backend/tests/**
sql/**
migrations/**
raw_vault/**
parsed/**
curated/**
docs/handoff-*.md
P2/P3/P4 entry
```

Exit gate:

```text
P1-GATE: five spec files exist; SPEC_INDEX 012 ACTIVE; README/feature_index synced; no backend changes.
STOP after P1 — await user review → P2 DB Review.
```

P1 checklist:

```text
[x] Create spec.md (non-stub)
[x] Create plan.md (non-stub)
[x] Create tasks.md (non-stub)
[x] Create acceptance.md (non-stub)
[x] Create test_cases.md (non-stub)
[x] Mark 012 ACTIVE / NOT IMPLEMENTED in SPEC_INDEX
[x] Set branch feature/012-search-service in SPEC_INDEX
[x] Keep 001–011 DONE in SPEC_INDEX
[x] Keep 008-review-workflow FUTURE STUB / NOT CURRENT
[x] Keep 013-streamlit-admin FUTURE
[x] Sync README §9.4 012 ACTIVE
[x] Sync docs/feature_index.md 012 ACTIVE
[ ] User P1 review approval
[ ] STOP → P2 DB Review on user confirmation
```

---

## 3. P2 — DB & Data Review (Not Started)

Owner: Tech Lead + DB & Data Agent

Goal:

```text
Verify FULLTEXT indexes, ORM coverage, SELECT-only MVP, project filter JOIN,
ngram Chinese behavior, migration need.
BLOCK P4 if schema/ORM/FULLTEXT insufficient.
```

Tasks:

```text
P2-T001 Confirm FULLTEXT indexes in sql/001_init_schema_v1_1.sql per MVP scope
P2-T002 Document MATCH ... AGAINST syntax and relevance column per table
P2-T003 Audit ORM: KbDocument, KbDocumentChunk, KbEvidence, KbProject, KbProjectDocument, KbCuratedAsset
P2-T004 Map every SELECT field to documented SQL column
P2-T005 Define --project-code filter via kb_project_document (not evidence.project_uid)
P2-T006 Confirm SELECT-only MVP — zero DML denylist
P2-T007 Assess migration requirement (audit table / new index) — do NOT assume none
P2-T008 Confirm no raw_vault / parsed filesystem read in design
P2-T009 Confirm no parser re-invocation in design
P2-T010 Validate ngram Chinese query notes for P6
P2-T011 Produce DB Review pass/fail note (p2_db_review.md)
```

Exit gate:

```text
P2-GATE: DB Review PASS required before P3/P4.
If FAIL -> migration spec + STOP.
```

**Status:** NOT STARTED — blocked until P1 user approval.

---

## 4. P3 — Implementation Gate (Not Started)

Owner: Tech Lead Agent

Goal:

```text
Publish P4 Dev whitelist, CLI/API contracts, SearchHit DTO, test plan.
```

Deliverable:

```text
specs/012-search-service/p3_implementation_gate.md
```

P3 checklist:

```text
[ ] P4 file whitelist
[ ] P4 forbidden list
[ ] CLI search-kb contract
[ ] Optional FastAPI /api/v1/search contract (or CLI-only MVP lock)
[ ] SearchHit / SearchResponse schema
[ ] scope=all merge and pagination strategy
[ ] P4/P5 test plan
[ ] Dev Agent handoff template
```

**Status:** BLOCKED until P2 PASS.

---

## 5. P4 — Dev Implementation (Not Started)

Likely allowed files:

```text
backend/app/services/search_service.py
backend/app/schemas/search.py              # if API MVP
backend/app/api/routes/search.py             # if API MVP
backend/app/cli/main.py
backend/tests/test_search_service.py
backend/tests/fixtures/search/
```

**Status:** BLOCKED until P3 gate.

---

## 6. P5 — QA (Not Started)

**Status:** BLOCKED until P4 complete.

---

## 7. P6 — E2E (Not Started)

Suggested chain:

```text
existing 010/011 sample data in MySQL -> search-kb CLI -> verify hits + UID traceability
```

**Status:** BLOCKED until P5 complete.

---

## 8. P7 — Tech Lead Final Review (Not Started)

**Status:** BLOCKED until P6 complete.

---

## 9. P8 — Handoff & Merge (Not Started)

Suggested commits:

```text
spec(012): add search service plan
review(012): add P2 P3 implementation gate
feat(012): implement search service
test(012): add search service QA report
test(012): add search service E2E report
review(012): add search service final review
docs(012): add search service handoff
merge: feature/012-search-service into main
```

**Status:** BLOCKED until P7 complete.

---

## 10. Current Action

```text
P1 COMPLETE — awaiting user approval before P2 DB Review.
STOP. Do not write backend/** until P4 explicitly approved.
```

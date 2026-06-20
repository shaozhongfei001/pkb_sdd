# 013 Streamlit Admin — tasks.md

> Project: `pkb_sdd`  
> Spec: `specs/013-streamlit-admin/`  
> Phase model: P1–P8  
> Current phase: `P1 Tech Lead Plan — COMPLETE (awaiting user review)`  
> Current implementation state: `NOT STARTED (P4 blocked)`

---

## 1. Cursor Role Model

| Role | Responsibility |
|---|---|
| Tech Lead Agent | Scope, contract, plan, gates, final review |
| DB & Data Agent | P2 SELECT-only / ORM / denylist review |
| Dev Agent | P4 Streamlit + lib implementation within whitelist |
| QA Agent | P5 lib unit tests + UI checklist |
| E2E Agent | P6 real MySQL + Streamlit validation |

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
Create 013 design specs, align SPEC_INDEX, sync README and feature_index.
No backend or frontend implementation.
```

Deliverables:

```text
specs/013-streamlit-admin/spec.md
specs/013-streamlit-admin/plan.md
specs/013-streamlit-admin/tasks.md
specs/013-streamlit-admin/acceptance.md
specs/013-streamlit-admin/test_cases.md
specs/SPEC_INDEX.md (013 ACTIVE / NOT IMPLEMENTED)
README.md (013 active sync)
docs/feature_index.md (013 ACTIVE sync)
```

Forbidden:

```text
backend/**
frontend/**
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
P1-GATE: five spec files exist; SPEC_INDEX 013 ACTIVE; README/feature_index synced;
         no backend/frontend changes.
STOP after P1 — await user review → P2 DB Review.
```

P1 checklist:

```text
[x] Create spec.md (non-stub)
[x] Create plan.md (non-stub)
[x] Create tasks.md (non-stub)
[x] Create acceptance.md (non-stub)
[x] Create test_cases.md (non-stub)
[x] Mark 013 ACTIVE / NOT IMPLEMENTED in SPEC_INDEX
[x] Set branch feature/013-streamlit-admin in SPEC_INDEX
[x] Keep 001–012 DONE in SPEC_INDEX
[x] Keep 008-review-workflow FUTURE STUB / NOT CURRENT
[x] Add SPEC_INDEX §4.8 013 boundary reference
[x] Sync README §9.5 013 ACTIVE
[x] Sync docs/feature_index.md 013 ACTIVE
[ ] User P1 review approval
[ ] STOP → P2 DB Review on user confirmation
```

---

## 3. P2 — DB & Data Review (Not Started)

Owner: Tech Lead + DB & Data Agent

Goal:

```text
Verify SELECT-only MVP, ORM coverage for all UI repositories, SearchService-only search path,
session lifecycle for Streamlit, denylist tables, migration need.
BLOCK P4 if schema/ORM/session design insufficient.
```

Tasks:

```text
P2-T001 Confirm SELECT-only MVP — zero DML denylist documented
P2-T002 Audit ORM: document, evidence, project, curated, parse registry, file_instance/content
P2-T003 Map every UI SELECT field to documented SQL column
P2-T004 Confirm Search page uses SearchService — no duplicate FULLTEXT SQL
P2-T005 Document curated_root path resolution vs kb_curated_asset.file_path
P2-T006 Document reports_root glob patterns for 008/009 artifacts
P2-T007 Confirm kb_file_instance path display is metadata-only (no vault bin)
P2-T008 Confirm parse registry SELECT aligns with 006 schema
P2-T009 Assess Streamlit + SQLAlchemy session pool / rerun lifecycle
P2-T010 Assess migration requirement — do NOT assume none
P2-T011 Confirm denylist: no kb_review_item / kb_manual_correction / kb_embedding_ref writes
P2-T012 Lock Inventory Snapshot page in/out of MVP
P2-T013 Produce DB Review pass/fail note (p2_db_review.md)
```

Exit gate:

```text
P2-GATE: DB Review PASS required before P3/P4.
If FAIL -> migration spec + STOP.
```

**Status:** NOT STARTED — blocked until P1 user approval.

---

## 4. P3 — Implementation Gate (COMPLETE — awaiting user review)

Owner: Tech Lead Agent

Goal:

```text
Publish P4 Dev whitelist, page contracts, lib module list, test plan, streamlit launch command.
```

Deliverable:

```text
specs/013-streamlit-admin/p3_implementation_gate.md
```

P3 checklist:

```text
[x] P4 file whitelist (frontend/streamlit_admin/**, tests, requirements.txt)
[x] P4 forbidden list (sealed services, sql, vault, parsed mutation)
[x] Page-by-page UI contract (6 pages IN MVP)
[x] SearchClient / SearchService-only contract
[x] Config path override (PKB_CONFIG) decision
[x] Inventory Snapshot IN MVP; kb_duplicate_group OUT
[x] streamlit dependency pin guidance
[x] 012 FastAPI sub-task decision: NO (remains deferred)
[x] Path traversal protection contract
[x] Session lifecycle contract (no session_scope)
[x] ORM field mapping lock (curated_path, source_path, storage.*)
[x] pytest baseline risk documented
[x] P4/P5 test plan
[x] Gate decision: PASS WITH CONSTRAINTS
[ ] User P3 review approval
[ ] STOP → P4 Dev on user confirmation
```

Exit gate:

```text
P3-GATE: PASS WITH CONSTRAINTS — P4 blocked until user confirms.
Branch must be feature/013-streamlit-admin (verified at P3 start).
```

**Status:** COMPLETE — awaiting user review → P4 Dev.

---

## 5. P4 — Dev Implementation (Not Started)

Likely allowed files:

```text
frontend/streamlit_admin/app.py
frontend/streamlit_admin/pages/**
frontend/streamlit_admin/lib/**
backend/requirements.txt                     # streamlit dep
backend/tests/test_streamlit_admin_lib.py
backend/tests/fixtures/streamlit_admin/
```

**Status:** BLOCKED until P3 gate.

---

## 6. P5 — QA (Not Started)

Deliverables:

```text
backend/tests/test_streamlit_admin_lib.py (expanded)
specs/013-streamlit-admin/p5_qa_report.md
UI manual checklist results
```

**Status:** BLOCKED until P4 complete.

---

## 7. P6 — E2E (Not Started)

Suggested chain:

```text
existing MySQL with 010/011/012 sample data
  -> streamlit run frontend/streamlit_admin/app.py
  -> manual/E2E: search, evidence drill-down, curated render, registry view, quality report view
  -> verify row counts unchanged (SELECT-only)
```

**Status:** BLOCKED until P5 complete.

---

## 8. P7 — Tech Lead Final Review (Not Started)

**Status:** BLOCKED until P6 complete.

---

## 9. P8 — Handoff & Merge (Not Started)

Suggested commits:

```text
spec(013): add streamlit admin P1 plan
review(013): add P2 DB review
review(013): add P3 implementation gate
feat(013): implement streamlit admin read-only UI
test(013): add streamlit admin QA report
test(013): add streamlit admin E2E report
review(013): add streamlit admin final review
docs(013): add streamlit admin handoff
merge: feature/013-streamlit-admin into main
```

**Status:** BLOCKED until P7 complete.

---

## 10. Current Action

```text
P3 COMPLETE — awaiting user approval before P4 Dev.
Branch: feature/013-streamlit-admin
Gate: PASS WITH CONSTRAINTS (see p3_implementation_gate.md)
STOP. Do not write backend/** or frontend/** until user confirms P4.
```

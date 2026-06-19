# 010 Evidence Chain — tasks.md

> Project: `pkb_sdd`  
> Spec: `specs/010-evidence-chain/`  
> Phase model: P1–P8  
> Current phase: `P1 Tech Lead Plan`  
> Current implementation state: `NOT STARTED`

---

## 1. Cursor Role Model

| Role | Responsibility |
|---|---|
| Tech Lead Agent | Scope, contract, plan, gates, final review |
| DB & Data Agent | P2 schema/ORM/idempotency review |
| Dev Agent | P4 implementation within whitelist |
| QA Agent | P5 unit + regression tests |
| E2E Agent | P6 real parsed → evidence validation |

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
Create 010 design specs, align SPEC_INDEX, fix README drift.
No backend implementation.
```

Deliverables:

```text
specs/010-evidence-chain/spec.md
specs/010-evidence-chain/plan.md
specs/010-evidence-chain/tasks.md
specs/010-evidence-chain/acceptance.md
specs/010-evidence-chain/test_cases.md
specs/SPEC_INDEX.md (010 ACTIVE / PLANNED)
README.md (009 DONE, 010 active sync)
```

Forbidden:

```text
backend/**
sql/**
migrations/**
P2/P3/P4 entry
```

Exit gate:

```text
P1-GATE: five spec files exist; SPEC_INDEX 010 ACTIVE; README drift fixed; no backend changes.
STOP after P1 — await user review.
```

P1 checklist:

```text
[x] Create spec.md
[x] Create plan.md
[x] Create tasks.md
[x] Create acceptance.md
[x] Create test_cases.md
[x] Mark 010 ACTIVE / PLANNED in SPEC_INDEX
[x] Set branch feature/010-evidence-chain in SPEC_INDEX
[x] Keep 008-review-workflow FUTURE STUB
[x] Fix README 009 ACTIVE drift
[ ] User P1 review approval
[ ] STOP
```

---

## 3. P2 — DB & Data Read Review (Not Started)

Owner: Tech Lead + DB & Data Agent

Goal:

```text
Verify kb_document_chunk / kb_evidence schema, ORM, idempotency keys, migration need.
BLOCK P4 if schema/ORM insufficient.
```

Tasks:

```text
P2-T001 Confirm kb_document_chunk in sql/001_init_schema_v1_1.sql
P2-T002 Confirm kb_evidence in sql/001_init_schema_v1_1.sql
P2-T003 Audit ORM: KbDocument exists; KbDocumentChunk/KbEvidence missing?
P2-T004 Map every write field to documented SQL column
P2-T005 Define idempotency keys and upsert strategy
P2-T006 Assess migration requirement — do NOT assume none
P2-T007 Confirm no raw_vault binary read in design
P2-T008 Confirm no parser re-invocation in design
P2-T009 Produce DB Review pass/fail note
```

Exit gate:

```text
P2-GATE: DB Review PASS required before P3/P4.
If FAIL -> migration spec + STOP.
```

**Status:** BLOCKED until P1 approved.

---

## 4. P3 — Implementation Gate (Not Started)

Owner: Tech Lead Agent

Tasks:

```text
P3-T001 Finalize EvidenceChainService API
P3-T002 Finalize chunk strategy per parser_name
P3-T003 Finalize CLI build-evidence-chain contract
P3-T004 Finalize Dev whitelist / blacklist
P3-T005 Finalize test fixture strategy
P3-T006 Publish Dev Agent prompt
```

**Status:** BLOCKED until P2 PASS.

---

## 5. P4 — Dev Implementation (Not Started)

Likely allowed files:

```text
backend/app/services/evidence_chain.py
backend/app/models/evidence.py
backend/app/cli/main.py
backend/tests/test_evidence_chain.py
```

**Status:** BLOCKED until P3 gate.

---

## 6. P5 — QA (Not Started)

**Status:** BLOCKED until P4 complete.

---

## 7. P6 — E2E (Not Started)

**Status:** BLOCKED until P5 complete.

---

## 8. P7 — Tech Lead Final Review (Not Started)

**Status:** BLOCKED until P6 complete.

---

## 9. P8 — Handoff & Merge (Not Started)

Suggested commits:

```text
spec(010): add evidence chain plan
review(010): add P2 P3 implementation gate
feat(010): implement evidence chain builder
test(010): add evidence chain QA report
test(010): add evidence chain E2E report
review(010): add evidence chain final review
docs(010): add evidence chain handoff
merge: feature/010-evidence-chain into main
```

**Status:** BLOCKED until P7 complete.

---

## 10. Current Action

```text
P1 COMPLETE — awaiting user review.
STOP. Do not proceed to P2.
```

# 011 Curated Project Assets — tasks.md

> Project: `pkb_sdd`  
> Spec: `specs/011-curated-project-assets/`  
> Phase model: P1–P8  
> Current phase: `P1 Tech Lead Plan — COMPLETE (awaiting user review)`  
> Current implementation state: `NOT STARTED (P4 blocked)`

---

## 1. Cursor Role Model

| Role | Responsibility |
|---|---|
| Tech Lead Agent | Scope, contract, plan, gates, final review |
| DB & Data Agent | P2 schema/ORM/idempotency/curated_root review |
| Dev Agent | P4 implementation within whitelist |
| QA Agent | P5 unit + regression tests |
| E2E Agent | P6 evidence → curated validation |

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
Create 011 design specs, align SPEC_INDEX, sync README and feature_index.
No backend implementation.
```

Deliverables:

```text
specs/011-curated-project-assets/spec.md
specs/011-curated-project-assets/plan.md
specs/011-curated-project-assets/tasks.md
specs/011-curated-project-assets/acceptance.md
specs/011-curated-project-assets/test_cases.md
specs/SPEC_INDEX.md (011 ACTIVE / PLANNED)
README.md (011 active sync)
docs/feature_index.md (numbering drift fix)
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
P1-GATE: five spec files exist; SPEC_INDEX 011 ACTIVE; README/feature_index synced; no backend changes.
STOP after P1 — await user review.
```

P1 checklist:

```text
[x] Create spec.md (non-stub)
[x] Create plan.md (non-stub)
[x] Create tasks.md (non-stub)
[x] Create acceptance.md (non-stub)
[x] Create test_cases.md (non-stub)
[x] Mark 011 ACTIVE / PLANNED in SPEC_INDEX
[x] Set branch feature/011-curated-project-assets in SPEC_INDEX
[x] Keep 001–010 DONE in SPEC_INDEX
[x] Keep 008-review-workflow FUTURE STUB / NOT CURRENT
[x] Sync README §9.3 011 active
[x] Fix docs/feature_index.md renumber drift
[ ] User P1 review approval
[ ] STOP
```

---

## 3. P2 — DB & Data Review (Not Started)

Owner: Tech Lead + DB & Data Agent

Goal:

```text
Verify kb_project / kb_project_document / kb_curated_asset schema, ORM, idempotency keys,
curated_root config, migration need.
BLOCK P4 if schema/ORM insufficient.
```

Tasks:

```text
P2-T001 Confirm kb_project in sql/001_init_schema_v1_1.sql
P2-T002 Confirm kb_project_document in sql/001_init_schema_v1_1.sql
P2-T003 Confirm kb_curated_asset in sql/001_init_schema_v1_1.sql
P2-T004 Audit ORM: KbProject / KbProjectDocument / KbCuratedAsset exist?
P2-T005 Map every write field to documented SQL column
P2-T006 Define idempotency keys and upsert strategy (project_uid, curated_uid, uk_project_document)
P2-T007 Confirm curated_root in config/app.example.yaml and AppConfig
P2-T008 Assess migration requirement — do NOT assume none
P2-T009 Confirm kb_document_chunk / kb_evidence read-only from 011
P2-T010 Confirm no raw_vault binary read in design
P2-T011 Confirm no parser re-invocation in design
P2-T012 Produce DB Review pass/fail note (p2_db_review.md)
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
Publish P4 Dev whitelist, CLI/DB/ORM contracts, manifest schema, test plan.
```

Deliverable:

```text
specs/011-curated-project-assets/p3_implementation_gate.md
```

P3 checklist:

```text
[ ] P4 file whitelist
[ ] P4 forbidden list
[ ] CLI build-curated-project contract
[ ] DB write contract (kb_project*, kb_curated_asset only)
[ ] ORM contract
[ ] Project manifest YAML schema
[ ] Template/asset_type MVP strategy
[ ] P4/P5 test plan
[ ] Dev Agent handoff template
```

**Status:** BLOCKED until P2 PASS.

---

## 5. P4 — Dev Implementation (Not Started)

Likely allowed files:

```text
backend/app/services/curated_project_assets.py
backend/app/models/project.py
backend/app/cli/main.py
backend/tests/test_curated_project_assets.py
backend/tests/fixtures/curated_project/
config/projects/*.yaml                    # sample manifests only
```

**Status:** BLOCKED until P3 gate.

---

## 6. P5 — QA (Not Started)

**Status:** BLOCKED until P4 complete.

---

## 7. P6 — E2E (Not Started)

Suggested chain:

```text
scan → copy-to-vault → parse → register → build-evidence-chain → build-curated-project
```

**Status:** BLOCKED until P5 complete.

---

## 8. P7 — Tech Lead Final Review (Not Started)

**Status:** BLOCKED until P6 complete.

---

## 9. P8 — Handoff & Merge (Not Started)

Suggested commits:

```text
spec(011): add curated project assets plan
review(011): add P2 P3 implementation gate
feat(011): implement curated project assets builder
test(011): add curated project assets QA report
test(011): add curated project assets E2E report
review(011): add curated project assets final review
docs(011): add curated project assets handoff
merge: feature/011-curated-project-assets into main
```

**Status:** BLOCKED until P7 complete.

---

## 10. Current Action

```text
P1 COMPLETE — awaiting user approval before P2 DB Review.
STOP. Do not write backend/** until P4 explicitly approved.
```

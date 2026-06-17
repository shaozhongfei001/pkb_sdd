# 009 Parse Quality Report Summary — tasks.md

> Project: `pkb_sdd`  
> Spec: `specs/009-quality-report-summary/`  
> Phase model: P1–P8  
> Current phase: `P3 Implementation Gate — COMPLETE (awaiting P4 approval)`  
> Current implementation state: `NOT STARTED (P4 blocked)`

---

## 1. Cursor Role Model

Use only these four roles:

| Role | Responsibility |
|---|---|
| Tech Lead Agent | Scope, contract, plan, gates, final review. |
| Dev Agent | Implementation within approved whitelist only. |
| QA Agent | Unit tests, regression tests, fixture validation. |
| E2E Agent | Real 008 report → summary CLI; no-side-effect validation. |

Mapping:

```text
P1/P2/P3/P7/P8 = Tech Lead Agent
P4 = Dev Agent
P5 = QA Agent
P6 = E2E Agent
```

---

## 2. P1 — Tech Lead Plan

Owner:

```text
Tech Lead Agent
```

Goal:

```text
Create 009 design specs, align SPEC_INDEX, renumber future stubs.
No backend implementation.
```

Deliverables:

```text
specs/009-quality-report-summary/spec.md
specs/009-quality-report-summary/plan.md
specs/009-quality-report-summary/tasks.md
specs/009-quality-report-summary/acceptance.md
specs/009-quality-report-summary/test_cases.md
specs/SPEC_INDEX.md (008 DONE, 009 ACTIVE)
git mv future stub renumber (009-evidence-chain -> 010-evidence-chain, etc.)
README.md reference sync (if paths cited)
```

Allowed actions:

```text
write specs only
git mv spec directories for renumber
update SPEC_INDEX and doc references
```

Forbidden actions:

```text
do not write backend/**
do not change DB schema
do not implement CLI
do not enter P2/P3/P4
```

Exit gate:

```text
P1-GATE: five spec files exist; SPEC_INDEX aligned; no two 009 semantics; no backend changes.
STOP after P1 — await user review.
```

P1 checklist:

```text
[x] Create spec.md
[x] Create plan.md
[x] Create tasks.md
[x] Create acceptance.md
[x] Create test_cases.md
[x] Mark 008 DONE in SPEC_INDEX
[x] Mark 009 ACTIVE in SPEC_INDEX
[x] Confirm 008-review-workflow remains FUTURE STUB
[x] Renumber future stubs via git mv
[x] User P1 review approval (commit e1cfac3)
[x] STOP
```

---

## 3. P2 — TL Read Review (Not Started)

Owner:

```text
Tech Lead Agent
```

Goal:

```text
Confirm 009 remains a pure file pipeline with DB Review exemption.
Validate config access pattern does not open MySQL.
```

Tasks:

```text
P2-T001 Confirm no ORM / session usage in design.
P2-T002 Confirm input contract matches 008 report schema.
P2-T003 Confirm 18 issue_codes list matches 008 ISSUE_CODES.
P2-T004 Confirm noise classification rules use issue fields only.
P2-T005 Confirm reports_root-only config access or document exception.
P2-T006 Produce DB Review exemption note.
```

Exit gate:

```text
P2-GATE: DB Review exemption documented; no schema change.
```

**Status:** **COMPLETE** — see `p2_p3_review.md` §2.

P2 checklist:

```text
[x] Confirm no ORM / session usage in design
[x] Confirm input contract matches 008 report schema
[x] Confirm 18 issue_codes list matches 008 ISSUE_CODES
[x] Confirm noise classification rules use issue fields only
[x] Confirm reports_root-only config access at runtime
[x] Produce DB Review exemption note
```

---

## 4. P3 — Implementation Gate

Owner:

```text
Tech Lead Agent
```

Goal:

```text
Convert P1/P2 into Dev Agent package with exact whitelist.
```

Tasks:

```text
P3-T001 Finalize service file path and class API.
P3-T002 Finalize CLI args and exit codes.
P3-T003 Finalize Markdown and JSON output schemas.
P3-T004 Finalize ISSUE_CODES duplication strategy.
P3-T005 Finalize test file and fixture strategy.
P3-T006 Publish Dev Agent prompt and whitelist.
```

Exit gate:

```text
P3-GATE: Dev receives whitelist; no-go list explicit.
```

P3 checklist:

```text
[x] Finalize service file path and class API
[x] Finalize CLI args and exit codes
[x] Finalize Markdown and JSON output schemas
[x] Finalize ISSUE_CODES duplication strategy
[x] Finalize test file and fixture strategy
[x] Publish Dev Agent whitelist and blacklist in p2_p3_review.md
```

**Status:** **COMPLETE** — P4 blocked until user confirms.

Deliverable:

```text
specs/009-quality-report-summary/p2_p3_review.md
```

---

## 5. P4 — Dev Implementation (Not Started)

Owner:

```text
Dev Agent
```

Likely allowed files:

```text
backend/app/services/parse_quality_report_summarizer.py
backend/app/cli/main.py
backend/tests/test_parse_quality_report_summarizer.py
```

Implementation tasks:

```text
P4-T001 ParseQualityReportSummarizerService — load/validate input JSON.
P4-T002 Preserve 18 issue_counts in output.
P4-T003 Noise classification.
P4-T004 Markdown renderer.
P4-T005 JSON summary renderer.
P4-T006 CLI summarize-parse-quality.
P4-T007 Unit tests with fixture 008 reports.
```

Hard constraints:

```text
No MySQL.
No raw_vault / parsed reads.
No parser calls.
No repair.
No 008 checker re-invocation.
```

**Status:** BLOCKED until P3 gate.

---

## 6. P5 — QA (Not Started)

Owner:

```text
QA Agent
```

Tasks:

```text
P5-T001 Run 009 targeted tests.
P5-T002 Verify noise classification fixtures.
P5-T003 Verify schema rejection paths.
P5-T004 Verify no MySQL session created (mock/spy).
P5-T005 Run 004–008 regression tests.
P5-T006 Produce QA report.
```

**Status:** BLOCKED until P4 complete.

---

## 7. P6 — E2E (Not Started)

Owner:

```text
E2E Agent
```

Tasks:

```text
P6-T001 Use real 008 P6 parse_quality_report.json as input.
P6-T002 Run summarize-parse-quality CLI.
P6-T003 Verify summary file created.
P6-T004 Verify DB row counts unchanged (sanity — 009 should not connect).
P6-T005 Verify raw_vault / parsed mtimes unchanged.
P6-T006 Document noise breakdown on real report.
```

**Status:** BLOCKED until P5 complete.

---

## 8. P7 — Tech Lead Final Review (Not Started)

Owner:

```text
Tech Lead Agent
```

**Status:** BLOCKED until P6 complete.

---

## 9. P8 — Handoff & Merge (Not Started)

Owner:

```text
Tech Lead Agent / Handoff Agent
```

Suggested commits:

```text
spec(009): add quality report summary plan
feat(009): implement quality report summarizer
docs(009): add quality report summary handoff
merge: feature/009-quality-report-summary into main
```

**Status:** BLOCKED until P7 complete.

---

## 10. Current Action

```text
P2/P3 COMPLETE — awaiting user approval before P4 Dev Implementation.
STOP. Do not write backend/** until P4 explicitly approved.
```

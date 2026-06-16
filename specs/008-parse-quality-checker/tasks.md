# 008 Parse Quality Checker — tasks.md

> Project: `pkb_sdd`  
> Spec: `specs/008-parse-quality-checker/`  
> Phase model: P1–P8  
> Current phase: `P1 Tech Lead Plan`  
> Current implementation state: `NOT STARTED`

---

## 1. Cursor Role Model

Use only these four roles:

| Role | Responsibility |
|---|---|
| Tech Lead Agent | Scope, contract, plan, DB/data read review, implementation gates, final review. |
| Dev Agent | Implementation within approved whitelist only. |
| QA Agent | Unit tests, regression tests, no-side-effect tests. |
| E2E Agent | Real CLI + DB + filesystem validation after implementation. |

Do not use:

```text
Architect Agent
Plan Agent
Backend Coding Agent
Implementation Agent
Integration Agent
E2E QA Agent
```

Mapping rule:

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
Create and review 008 design specs only.
```

Deliverables:

```text
specs/008-parse-quality-checker/spec.md
specs/008-parse-quality-checker/plan.md
specs/008-parse-quality-checker/tasks.md
specs/008-parse-quality-checker/acceptance.md
specs/008-parse-quality-checker/test_cases.md
```

Allowed actions:

```text
write specs only
align with specs/SPEC_INDEX.md
align with .cursor/rules/004-parser.mdc
align with .cursor/rules/007-agent-collaboration.mdc
```

Forbidden actions:

```text
do not write backend code
do not change DB schema
do not modify parser services
do not run implementation tasks
do not call parser
```

Exit gate:

```text
P1-GATE: five specs files exist and define read-only 008 scope clearly.
STOP after P1.
```

Cursor prompt:

```text
You are Tech Lead Agent for pkb_sdd 008 Parse Quality Checker.
Read specs/SPEC_INDEX.md and the Cursor parser/collaboration rules first.
Create only the P1 five-file spec set under specs/008-parse-quality-checker/.
Do not write implementation code.
Do not modify DB schema.
Do not call or change parsers.
STOP after specs are complete.
```

---

## 3. P2 — DB/Data Read Review

Owner:

```text
Tech Lead Agent
```

Goal:

```text
Confirm data sources, read-only query plan, ORM model fields, and manifest fields before implementation.
```

Inputs:

```text
backend/app/models/*
backend/app/services/parse_registry.py
backend/app/services/markitdown_parser.py
backend/app/services/mineru_pdf_parser.py
existing 005/006/007 tests
```

Tasks:

```text
P2-T001 Identify exact ORM model names and fields.
P2-T002 Identify exact registry artifact path fields.
P2-T003 Identify exact parse result status values.
P2-T004 Identify exact manifest field names from 005/007 output.
P2-T005 Confirm reports_root config access pattern.
P2-T006 Confirm raw_vault and parsed root config access pattern.
P2-T007 Confirm no migration is needed.
P2-T008 Confirm no DB write is needed.
P2-T009 Produce implementation whitelist for P4.
```

Forbidden:

```text
schema migration
DB write
parser behavior change
manifest contract change
```

Exit gate:

```text
P2-GATE: DB/data read plan approved; no schema change required.
```

If schema change or DB write appears necessary:

```text
STOP and enter DB Review.
```

Cursor prompt:

```text
You are Tech Lead Agent for P2 DB/Data Read Review.
Inspect models, registry service, and 005/007 manifest output.
Produce a read-only data access plan and implementation whitelist.
Do not write feature code.
If DB writes or migrations seem necessary, STOP.
```

---

## 4. P3 — Implementation Plan

Owner:

```text
Tech Lead Agent
```

Goal:

```text
Convert P1/P2 into a precise Dev Agent implementation package.
```

Tasks:

```text
P3-T001 Define exact service file path.
P3-T002 Define exact CLI command and args.
P3-T003 Define exact report schema.
P3-T004 Define exact issue taxonomy constants.
P3-T005 Define exact allowed test files.
P3-T006 Define no-side-effect validation method.
P3-T007 Define regression command list.
P3-T008 Prepare Dev Agent prompt.
```

Exit gate:

```text
P3-GATE: Dev Agent receives exact whitelist and no-go list.
```

Cursor prompt:

```text
You are Tech Lead Agent for P3.
Create the final implementation plan for Dev Agent.
Specify exact files allowed to edit and exact behavior required.
Do not implement code yourself.
```

---

## 5. P4 — Dev Implementation

Owner:

```text
Dev Agent
```

Goal:

```text
Implement read-only parse quality checker and CLI according to P3 whitelist.
```

Likely allowed files:

```text
backend/app/services/parse_quality_checker.py
backend/app/cli/main.py
backend/tests/test_parse_quality_checker.py
```

Implementation tasks:

```text
P4-T001 Add ParseQualityCheckerService.
P4-T002 Add issue model / report model.
P4-T003 Implement candidate selection.
P4-T004 Implement raw_vault checks.
P4-T005 Implement parsed artifact checks.
P4-T006 Implement manifest validation.
P4-T007 Implement registry artifact path validation.
P4-T008 Implement issue aggregation.
P4-T009 Implement report writing to reports_root.
P4-T010 Add check-parse-quality CLI.
P4-T011 Add unit tests.
```

Hard constraints:

```text
No DB writes.
No parser invocation.
No raw_vault writes.
No parsed writes.
No schema migration.
No change to MarkItDown/MinerU behavior.
```

Exit gate:

```text
P4-GATE: implementation complete, local targeted tests pass.
```

Cursor prompt:

```text
You are Dev Agent for pkb_sdd 008.
Implement only the read-only parse quality checker.
Edit only approved files.
Do not call MarkItDown, MinerU, or magic-pdf.
Do not write DB.
Do not change schemas or existing parser contracts.
After implementation, run targeted tests and report results.
```

---

## 6. P5 — QA Test & Regression

Owner:

```text
QA Agent
```

Goal:

```text
Verify behavior, report schema, issue taxonomy, and no-side-effect guarantees.
```

Tasks:

```text
P5-T001 Run 008 targeted tests.
P5-T002 Add or request missing tests for all acceptance gates.
P5-T003 Verify no DB writes.
P5-T004 Verify no parser invocation.
P5-T005 Verify only report file is written.
P5-T006 Verify issue severity and issue codes.
P5-T007 Verify CLI filters.
P5-T008 Run 004/005/006/007 regression tests.
P5-T009 Run full backend tests if feasible.
P5-T010 Produce QA result summary.
```

Recommended commands:

```bash
PYTHONPATH=backend pytest backend/tests/test_parse_quality_checker.py
PYTHONPATH=backend pytest backend/tests/test_parser_router.py backend/tests/test_markitdown_parser.py backend/tests/test_parse_registry.py backend/tests/test_mineru_pdf_parser.py
PYTHONPATH=backend pytest backend/tests
```

Exit gate:

```text
P5-GATE: targeted + regression tests pass, or defects are clearly reported.
```

Cursor prompt:

```text
You are QA Agent for pkb_sdd 008.
Verify test coverage and run targeted/regression tests.
Focus on no DB writes, no parser calls, and no filesystem mutation except report output.
Do not implement new feature behavior unless explicitly asked by Tech Lead.
```

---

## 7. P6 — E2E Validation

Owner:

```text
E2E Agent
```

Goal:

```text
Validate real CLI behavior against local dev config, DB, raw_vault, parsed, and reports_root.
```

Tasks:

```text
P6-T001 Confirm clean git status before E2E.
P6-T002 Activate backend virtual environment.
P6-T003 Run check-parse-quality CLI with default scope.
P6-T004 Run scoped CLI with --limit.
P6-T005 Run scoped CLI with --sha256 or --content-uid if sample exists.
P6-T006 Confirm report file is generated under reports_root.
P6-T007 Parse report JSON.
P6-T008 Confirm no DB row count changes.
P6-T009 Confirm raw_vault and parsed mtimes are unchanged except report output.
P6-T010 Document environment caveats.
```

Example commands:

```bash
cd /home/szf/dev/pyws/pkb_sdd
source backend/.venv/bin/activate
PYTHONPATH=backend python -m app.cli.main check-parse-quality --config config/app.yaml --limit 20
```

Exit gate:

```text
P6-GATE: real CLI report generated and no mutation observed.
```

Cursor prompt:

```text
You are E2E Agent for pkb_sdd 008.
Run the real CLI in the local project environment.
Validate report output and no-side-effect guarantees.
Do not run parser commands.
Do not repair data.
```

---

## 8. P7 — Tech Lead Final Review

Owner:

```text
Tech Lead Agent
```

Goal:

```text
Review implementation, tests, E2E evidence, caveats, and contract compliance.
```

Tasks:

```text
P7-T001 Review git diff.
P7-T002 Verify no forbidden files changed.
P7-T003 Verify no schema migration.
P7-T004 Verify no parser behavior change.
P7-T005 Verify report schema.
P7-T006 Verify issue taxonomy.
P7-T007 Verify acceptance checklist.
P7-T008 Confirm caveats.
P7-T009 Decide GO / FIX / STOP.
```

Exit gate:

```text
P7-GATE: Tech Lead approves commit or sends back to Dev/QA.
```

Cursor prompt:

```text
You are Tech Lead Agent for P7 final review.
Inspect diff, tests, E2E output, and acceptance gates.
Approve only if 008 remains read-only and does not change parser/registry contracts.
```

---

## 9. P8 — Commit & Handoff

Owner:

```text
Tech Lead Agent
```

Goal:

```text
Commit completed 008 and produce handoff.
```

Tasks:

```text
P8-T001 Confirm clean tests.
P8-T002 Create docs/handoff-008-parse-quality-checker.md.
P8-T003 Commit implementation.
P8-T004 Merge feature branch to main if approved.
P8-T005 Update specs/SPEC_INDEX.md only if status transition is approved.
P8-T006 Produce next-stage handoff.
```

Suggested commit messages:

```text
spec(008): add parse quality checker plan
feat(008): implement parse quality checker
docs(008): add parse quality checker handoff
merge: feature/008-parse-quality-checker into main
```

Exit gate:

```text
P8-GATE: 008 complete on main with handoff.
```

---

## 10. Current P1 Action Checklist

For the current stage only:

```text
[ ] Create specs/008-parse-quality-checker/spec.md
[ ] Create specs/008-parse-quality-checker/plan.md
[ ] Create specs/008-parse-quality-checker/tasks.md
[ ] Create specs/008-parse-quality-checker/acceptance.md
[ ] Create specs/008-parse-quality-checker/test_cases.md
[ ] Confirm no implementation files modified
[ ] STOP
```

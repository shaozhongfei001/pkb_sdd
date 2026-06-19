# 010 Evidence Chain — acceptance.md

> Project: `pkb_sdd`  
> Spec: `specs/010-evidence-chain/`  
> Acceptance scope: read parsed + registry metadata; write chunk/evidence DB records (P4+).

---

## 1. Acceptance Philosophy

010 is accepted when it builds evidence chain records from parsed artifacts without re-parsing, without mutating originals, and without early curated/LLM/review scope creep.

DB writes require P2 DB Review PASS before P4.

---

## 2. P1 Acceptance

```text
P1-A001 spec.md exists under specs/010-evidence-chain/
P1-A002 plan.md exists
P1-A003 tasks.md exists
P1-A004 acceptance.md exists
P1-A005 test_cases.md exists
P1-A006 SPEC_INDEX marks 010 ACTIVE / PLANNED
P1-A007 SPEC_INDEX branch = feature/010-evidence-chain
P1-A008 SPEC_INDEX keeps 008-review-workflow FUTURE STUB / NOT CURRENT
P1-A009 README no longer claims 009 ACTIVE
P1-A010 No backend/** files modified
P1-A011 P1 stops before P2/P3/P4
P1-A012 P1 does not pre-judge "no migration required"
```

---

## 3. Hard Acceptance Gates (Final — P7)

### A001 — Active Spec Alignment

Must implement from `specs/010-evidence-chain/` only.

Must not use `008-review-workflow`, deprecated stubs, or `011-curated-project-assets` as authority.

### A002 — Parsed Read-only

Reads `parsed_text.md`, `parsed_metadata.json`, `parse_manifest.json` without modification.

### A003 — No raw_vault Binary Read

Does not open `original.bin` for chunk extraction.

### A004 — No Parser Re-invocation

Does not call MarkItDown, MinerU, or magic-pdf.

### A005 — DB Write Scope

Writes only `kb_document_chunk` and `kb_evidence` (MVP). No other table DML unless P2 explicitly expands.

### A006 — Idempotency

Re-run on same content + same parsed input produces no duplicate chunk/evidence primary records.

### A007 — Original File Safety

User original files unchanged.

### A008 — No Curated / Vector / LLM

No curated/, project_card, embedding, or LLM chunking.

### A009 — No Review Workflow

Does not write `kb_review_item` or implement review UI/CLI.

### A010 — No Repair / Reparse

Does not auto-fix 008/009 findings or reparse content.

### A011 — Chinese Path Support

Chinese parsed paths and UTF-8 text handled correctly.

### A012 — Batch Failure Tolerance

Single content failure does not abort entire batch.

### A013 — Regression

001–009 regression tests pass; 010 targeted tests pass.

### A014 — P2 DB Review

P2 DB Review PASS documented before P4 merge.

### A015 — Schema Discipline

No undocumented DB fields; migration if P2 required it.

---

## 4. Rejection Conditions

```text
R001 Invented DB columns not in approved schema
R002 P4 started without P2 DB Review PASS
R003 Parser re-invocation
R004 raw_vault binary reads for chunk text
R005 parsed artifact modification
R006 curated / LLM / vector writes in MVP
R007 review workflow implementation
R008 auto repair/reparse based on 008/009
R009 Sealed service modification (001/002)
R010 Missing idempotency proof
```

---

## 5. Minimum Test Evidence (Final)

```text
010 targeted tests: passed
001–009 regression: passed
real parsed → evidence E2E: passed
parsed mtime unchanged: passed
original files unchanged: passed
idempotency re-run test: passed
```

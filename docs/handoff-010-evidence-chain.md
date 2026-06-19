# 010 Evidence Chain — Handoff

> Spec: `specs/010-evidence-chain/`  
> Branch: `feature/010-evidence-chain` → merged to `main`  
> Stage: P8 Handoff & Final Commit  
> Status: **DONE**

---

## 1. Completion Summary

010 Evidence Chain has been completed.

The feature builds chunk and evidence records from **read-only** parsed artifacts and registry metadata:

- CLI: `build-evidence-chain`
- ORM: `KbDocumentChunk`, `KbEvidence`
- Service: `EvidenceChainService`
- Deterministic `chunk_uid` / `evidence_uid` with MySQL upsert idempotency

It does **not** reparse, repair quality issues, or write curated / vector / review data.

---

## 2. P1–P8 Stage Chain

| Stage | Deliverable | Commit |
|---|---|---|
| P1 | Plan + SPEC_INDEX | `4ec9cf0` |
| P2 | DB Review PASS WITH CONSTRAINTS | `a48b25e` |
| P3 | Implementation gate | `543c8dd` |
| P4 | Dev implementation | `afc4464` |
| P4 regression fix | Inventory test isolation | `45b21e4` |
| P5 | QA report PASS | `d45b71d` |
| P6 blocked | E2E blocked report | `ea18034` |
| P6 complete | E2E PASS | `b08f644` |
| P7 | Final review PASS | `56875f6` |
| P8 | This handoff + merge | (P8 commit) |

---

## 3. P2 DB Review

**P2-GATE: PASS WITH CONSTRAINTS**

- Reuse init SQL tables `kb_document_chunk`, `kb_evidence` — **no migration** for MVP
- New ORM only (`evidence.py`); `KbDocument` read-only
- Idempotency via deterministic UID + UNIQUE upsert
- Parser metadata via manifest / registry join — no new columns on chunk/evidence

---

## 4. P4 Implementation Scope

Implemented files:

- `backend/app/services/evidence_chain.py`
- `backend/app/models/evidence.py`
- `backend/app/cli/main.py` (`build-evidence-chain`)
- `backend/tests/test_evidence_chain.py`
- `backend/tests/fixtures/evidence_chain_markitdown/*.fixture`
- `backend/tests/fixtures/evidence_chain_mineru/*.fixture`

CLI:

```bash
PYTHONPATH=backend python -m app.cli.main build-evidence-chain \
  --config config/app.yaml \
  --content-uid <uid> \
  --sha256 <hash> \
  --limit <n> \
  --dry-run \
  --force \
  --output /path/to/evidence_build_report.json
```

Chunk MVP:

- **MarkItDown:** section / heading / char offset (`page_no`/`bbox` null OK)
- **MinerU:** page + bbox best-effort; fallback to section split

---

## 5. P4 Regression Fix (`45b21e4`)

**Not a 010 implementation fix.**

- `test_scan_project_fixtures` scanned all of `backend/tests/fixtures/`
- 009 `parse_quality_report_*.json` were counted as documents → 7 vs expected 2
- Fix: scope scan to `INVENTORY_FIXTURES_ROOT = fixtures/中文路径/` only
- Full regression restored: **228 passed**

---

## 6. P6 E2E

### 6.1 First attempt — BLOCKED (`ea18034`)

- Real parsed tree existed on disk but no `kb_file_content` / non-`/tmp` `kb_parse_result`
- `build-evidence-chain` returned 0 candidates
- **Did not fake PASS**

### 6.2 Completion — PASS (`b08f644`)

Setup (001/002/005/006 — **not** 010 runtime):

```bash
scan --path backend/tests/fixtures/中文路径
copy-to-vault --sha256 536985990c2e2203a74c297bf66c7939873e53647bb41fb9cc72bb42bd6463d6
parse-markitdown --sha256 536985...
register-parse-report --report-path .../parse_markitdown_report_20260619T132348Z.json
```

Sample: `content_uid` = `sha256` = `536985990c2e2203a74c297bf66c7939873e53647bb41fb9cc72bb42bd6463d6`

Evidence-chain E2E:

| Step | Result |
|---|---|
| dry-run | 0 DB writes |
| first run | +1 chunk, +1 evidence |
| no-force rerun | skip (documents_skipped=1) |
| force rerun | upsert, same UIDs |
| parsed/raw_vault mtime | unchanged |

---

## 7. P6 Dev MySQL Expected Residual (Do Not Auto-Clean)

| Table | Delta |
|---|---|
| `kb_document_chunk` | +1 |
| `kb_evidence` | +1 |

`content_uid` = `536985990c2e2203a74c297bf66c7939873e53647bb41fb9cc72bb42bd6463d6`

Setup also added registry rows for this sample via 006 (separate from evidence window).

---

## 8. 010 Runtime Boundaries

**May:**

- read `parsed_text.md`, `parsed_metadata.json`, `parse_manifest.json` (read-only)
- SELECT `kb_document`, `kb_parse_result`, `kb_file_content`
- INSERT/UPSERT `kb_document_chunk`, `kb_evidence`
- write optional JSON build report (`--output`)

**Must not:**

- read `raw_vault` `original.bin` for extraction
- modify parsed artifacts or original user files
- call MarkItDown, MinerU, or `magic-pdf`
- write parse registry during `build-evidence-chain`
- write `curated/`, `kb_review_item`, `kb_embedding_ref`, project cards
- consume or auto-fix 008/009 quality reports
- LLM / semantic chunking / embedding / summarization / repair
- schema migration (MVP)

---

## 9. Test Results

| Suite | Result |
|---|---|
| 010 specialized pytest | **16 passed** |
| Full `backend/tests` | **228 passed** |
| P6 real MySQL E2E | **PASS** |

---

## 10. Spec / Review Artifacts

```text
specs/010-evidence-chain/spec.md
specs/010-evidence-chain/plan.md
specs/010-evidence-chain/tasks.md
specs/010-evidence-chain/acceptance.md
specs/010-evidence-chain/test_cases.md
specs/010-evidence-chain/p2_db_review.md
specs/010-evidence-chain/p3_implementation_gate.md
specs/010-evidence-chain/p5_qa_report.md
specs/010-evidence-chain/p6_e2e_report.md
specs/010-evidence-chain/p7_final_review.md
```

---

## 11. Next Stage

**Do not auto-start the next spec.**

Before any new implementation:

1. Read `specs/SPEC_INDEX.md`
2. Run explicit **Active Spec Selection Review**
3. Do **not** infer active spec from directory numbering

Potential future specs (not active until index says so):

- `specs/011-curated-project-assets/`
- `specs/008-review-workflow/` (future stub — not the completed 008 checker)
- `specs/012-search-service/`
- `specs/013-streamlit-admin/`

011 depends on 010 evidence foundation but must not start automatically.

---

## 12. Merge Notes

Branch `feature/010-evidence-chain` merged to `main` after P8 handoff commit.

P8 did not modify `backend/**`, `sql/**`, `raw_vault/**`, `parsed/**`, or `curated/**`.

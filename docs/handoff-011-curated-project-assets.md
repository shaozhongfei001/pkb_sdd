# 011 Curated Project Assets — Handoff

> Spec: `specs/011-curated-project-assets/`  
> Branch: `feature/011-curated-project-assets` → merged to `main`  
> Stage: P8 Handoff & Final Commit  
> Status: **DONE**

---

## 1. Completion Summary

011 Curated Project Assets has been completed.

The feature builds rule/template curated project Markdown files from **read-only** 010 evidence and registry metadata:

- CLI: `build-curated-project`
- ORM: `KbProject`, `KbProjectDocument`, `KbCuratedAsset`
- Service: `CuratedProjectAssetsService`
- Deterministic `project_uid` / `curated_uid` with MySQL upsert idempotency
- MVP curated files: `00_project_card.md`, `10_evidence_index.md`, `source_documents.md`

It does **not** call parsers, LLM, embedding, search, Streamlit, or evidence-chain at runtime. It does **not** backfill `kb_evidence.project_uid`.

---

## 2. P1–P8 Stage Chain

| Stage | Deliverable | Commit |
|---|---|---|
| P1 | Plan + SPEC_INDEX | `1e4c87e` |
| P2 | DB Review PASS WITH CONSTRAINTS | `2d4f8d7` |
| P3 | Implementation gate PASS | `9de94fc` |
| P4 | Dev implementation | `d8ac4ba` |
| P5 | QA report PASS + gap tests | `2a2caed` |
| P6 | E2E PASS | `c22cc8a` |
| P7 | Final review PASS | `02f1024` |
| P8 | This handoff + merge | (P8 commit) |

---

## 3. P2 DB Review — Key Constraints

**P2-GATE: PASS WITH CONSTRAINTS**

| ID | Constraint |
|---|---|
| C1 | No schema migration for MVP — reuse init SQL tables as-is |
| C2 | New ORM `project.py` — `KbProject`, `KbProjectDocument`, `KbCuratedAsset` |
| C3 | Idempotency via deterministic `project_uid` / `curated_uid` UNIQUE upsert |
| C4 | `related_*` fields use native JSON columns |
| C5 | `generation_method` locked to `TEMPLATE_RULE`; status SUCCESS \| SKIPPED \| FAILED |
| C6 | `version_no` MVP default = 1; `--force` updates file + `updated_at` without bumping version |
| C7 | `kb_document` / `kb_document_chunk` / `kb_evidence` — read-only SELECT |
| C8 | `kb_evidence.project_uid` must NOT be backfilled in MVP |
| C9 | `kb_project_document` has `created_at` only — acceptable for MVP |
| C10 | `curated_path` stores resolved path string |
| C11 | `kb_project.document_count` may be updated denormalized on build |
| C12 | `mapping_method` MVP: MANIFEST \| CLI \| SEED |
| C13 | Do not modify init SQL, migrations, or existing ORM except read-only imports |

---

## 4. P3 Whitelist / Blacklist Summary

**P4 whitelist (only):**

```text
backend/app/models/project.py
backend/app/services/curated_project_assets.py
backend/app/cli/main.py
backend/tests/test_curated_project_assets.py
backend/tests/fixtures/curated_project/**
```

**Forbidden:**

- Parser / LLM / embedding / search / Streamlit invocation
- Read `raw_vault` `original.bin` for text extraction
- Modify parsed artifacts or original user files
- Write `kb_document`, `kb_document_chunk`, `kb_evidence`, parse registry, `kb_review_item`, `kb_manual_correction`, `kb_embedding_ref`
- Schema migration; sealed services; repo `curated/**` commits

---

## 5. P4 Implementation

### 5.1 Components

| Component | Path |
|---|---|
| CLI | `build-curated-project` in `backend/app/cli/main.py` |
| Service | `backend/app/services/curated_project_assets.py` — `CuratedProjectAssetsService` |
| ORM | `backend/app/models/project.py` — `KbProject`, `KbProjectDocument`, `KbCuratedAsset` |
| Tests | `backend/tests/test_curated_project_assets.py` (18 tests) |
| Fixtures | `backend/tests/fixtures/curated_project/*.yaml.fixture` |

### 5.2 UID Rules (locked)

```text
project_uid = SHA256("project|v1|" + normalized_project_code)
curated_uid = SHA256("curated|v1|" + normalized_code + "|" + asset_type + "|" + 1)
generation_method = TEMPLATE_RULE
version_no = 1
```

### 5.3 MVP Curated Output

```text
{curated_root}/projects/{project_code}/
  00_project_card.md
  10_evidence_index.md
  source_documents.md
```

---

## 6. CLI Contract

```bash
PYTHONPATH=backend python -m app.cli.main build-curated-project \
  --config config/app.yaml \
  --project-code <code> \
  --project-name "<name>" \
  --content-uid <uid> \
  --manifest config/projects/<code>.yaml \
  --limit <n> \
  --dry-run \
  --force \
  --output /path/to/curated_build_report.json
```

| Flag | Required | Notes |
|---|---|---|
| `--project-code` | Yes | Drives `project_uid` |
| `--project-name` | No | Template / card display |
| `--content-uid` | No* | CLI document mapping when no manifest |
| `--manifest` | No | Optional YAML project manifest |
| `--limit` | No | Max documents per build |
| `--dry-run` | No | Zero DB + zero file writes |
| `--force` | No | Overwrite existing curated files |
| `--output` | No | JSON build report path |
| `--config` | No | Defaults to `config/app.yaml` |

---

## 7. DB Write Boundary

**May write (011 runtime only):**

- `kb_project`
- `kb_project_document`
- `kb_curated_asset`

**Must not write:**

- `kb_document`
- `kb_document_chunk`
- `kb_evidence` (including `project_uid` backfill)
- `kb_review_item`
- `kb_manual_correction`
- `kb_embedding_ref`
- Parse registry (`kb_parse_run`, `kb_parse_result`, `kb_parsed_artifact`)

---

## 8. Forbidden Runtime Boundaries

**Must not:**

- invoke MarkItDown, MinerU, `magic-pdf`, or subprocess parse
- call `build-evidence-chain` or any parser adapter at runtime
- read `raw_vault` `original.bin` for text extraction
- modify parsed artifacts or original user files
- use LLM distillation, semantic summarization, embedding, vector, or search service
- implement Streamlit / admin UI
- consume or auto-fix 008/009 quality reports
- commit files under repo `curated/` directory

**Storage:**

- `raw_vault` / `parsed` mtime unchanged after build (P6 verified)
- Runtime curated output lives under configured `curated_root` only — not in git

---

## 9. Test Results

| Suite | Result |
|---|---|
| 011 specialized pytest | **18 passed** |
| Full `backend/tests` | **246 passed** |
| P6 real MySQL E2E | **PASS** |

---

## 10. P6 E2E Results

Validated with real `config/app.yaml`, real MySQL, and 010 evidence sample.

| Field | Value |
|---|---|
| `project_code` | `P6-YHXM-011` |
| `project_name` | `银行项目 P6 E2E` |
| `content_uid` | `536985990c2e2203a74c297bf66c7939873e53647bb41fb9cc72bb42bd6463d6` |
| `evidence_count` | **1** |
| `project_uid` | `34e9a380d9728839677790a6fde01014c20a5532ceda388efa15c1ac254dabb5` |
| `mapping_method` | `CLI` |

| Step | Result |
|---|---|
| dry-run | 0 DB writes, 0 curated files |
| first run | +1 project, +1 mapping, +3 curated_asset, 3 files |
| no-force rerun | skip 3, no new primary rows |
| force rerun | overwrite 3 files, UIDs/version unchanged |
| forbidden tables | delta 0 |
| `kb_evidence.project_uid` | still NULL |
| parsed / raw_vault mtime | unchanged |

**Curated files generated (runtime, not in git):**

```text
curated/projects/P6-YHXM-011/00_project_card.md
curated/projects/P6-YHXM-011/10_evidence_index.md
curated/projects/P6-YHXM-011/source_documents.md
```

File content includes traceability fields: `project_code`, `project_name`, `document_uid`, `content_uid`, `evidence_uid`.

P6 reports: `/tmp/pkb_sdd_011_p6/*.json` (not in git).

---

## 11. P6 Intentional Residual (Do Not Auto-Clean)

**Dev MySQL E2E residue:**

```text
kb_project           +1  (P6-YHXM-011)
kb_project_document  +1
kb_curated_asset     +3
```

**Runtime curated residue:**

```text
curated/projects/P6-YHXM-011/00_project_card.md
curated/projects/P6-YHXM-011/10_evidence_index.md
curated/projects/P6-YHXM-011/source_documents.md
```

These are **intentional P6 E2E residue** — do not auto-clean unless an operator explicitly requests cleanup.

Pre-existing unrelated row: `kb_project` `uncategorized` / `未归属项目池` — not part of P6 delta.

---

## 12. Current Final State

| Item | Status |
|---|---|
| Specs 001–011 | **DONE** |
| Current ACTIVE spec | **None** — requires Active Spec Selection Review before next work |
| `012-search-service` | **FUTURE — not started** |
| `013-streamlit-admin` | **FUTURE — not started** |
| `008-review-workflow` | **FUTURE STUB / NOT CURRENT** (≠ completed 008 parse quality checker) |

---

## 13. Spec / Review Artifacts

```text
specs/011-curated-project-assets/spec.md
specs/011-curated-project-assets/plan.md
specs/011-curated-project-assets/tasks.md
specs/011-curated-project-assets/acceptance.md
specs/011-curated-project-assets/test_cases.md
specs/011-curated-project-assets/p2_db_review.md
specs/011-curated-project-assets/p3_implementation_gate.md
specs/011-curated-project-assets/p5_qa_report.md
specs/011-curated-project-assets/p6_e2e_report.md
specs/011-curated-project-assets/p7_final_review.md
```

---

## 14. Next Stage

**Do not auto-start the next spec.**

Before any new implementation:

1. Read `specs/SPEC_INDEX.md`
2. Run explicit **Active Spec Selection Review**
3. Do **not** infer active spec from directory numbering

Potential future specs (not active until index says so):

- `specs/012-search-service/` — **not started**
- `specs/013-streamlit-admin/` — **not started**
- `specs/008-review-workflow/` — future stub, **NOT CURRENT**

---

## 15. Merge Notes

Branch `feature/011-curated-project-assets` merged to `main` after P8 handoff commit.

P8 did not modify `backend/**`, `sql/**`, `raw_vault/**`, `parsed/**`, or commit repo `curated/**`.

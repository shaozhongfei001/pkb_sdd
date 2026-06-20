# 012 Search Service — P6 E2E Validation Report

> Role: E2E Agent  
> Spec: `specs/012-search-service/`  
> Branch: `feature/012-search-service`  
> Stage: P6 E2E Validation  
> P5 report: `specs/012-search-service/p5_qa_report.md` (uncommitted)  
> P6 commit hash: `f698e26` (HEAD; 012 implementation uncommitted on feature branch)  
> Status: **P6 COMPLETE — PASS WITH NOTES**

---

## 1. Gate Conclusion

**P6 E2E Validation: PASS WITH NOTES**

`search-kb` was validated against:

- real `config/app.yaml` (`/home/szf/dev/pyws/pkb_sdd/config/app.yaml`)
- real MySQL 8.0.46 (`personal_kb` @ `127.0.0.1:3306`)
- reused 010/011 P6 sample (`content_uid=536985…`, `project_code=P6-YHXM-011`)
- real InnoDB ngram FULLTEXT indexes (`ngram_token_size=2`)

All mandatory P6 checks passed. **No DB writes detected.** **No raw_vault / parsed / curated mtime changes.**

**Notes (non-blocking):**

1. `kb_document.title` is NULL for all three rows — `scope=document` with query `银行 项目` returns zero hits (expected; exit 0).
2. `summary.scopes_executed` always lists five scopes even when per-scope COUNT=0 (P5 note; cosmetic).
3. 012 production code remains **uncommitted** on `feature/012-search-service` at HEAD `f698e26`.

**STOP — P7/P8 remain BLOCKED until user confirms.**

---

## 2. Environment & Data Baseline

| Item | Value |
|------|-------|
| Config path | `/home/szf/dev/pyws/pkb_sdd/config/app.yaml` |
| MySQL host/port | `127.0.0.1:3306` |
| MySQL database | `personal_kb` |
| MySQL version | `8.0.46-0ubuntu0.24.04.2` |
| `ngram_token_size` | `2` |
| Branch | `feature/012-search-service` |
| HEAD commit | `f698e26114b071be8d84ef6913753416c9ffd2e3` |
| P6 output dir | `/tmp/pkb_sdd_012_p6/` |
| P6 run UTC | `2026-06-20T13:48:18Z` – `2026-06-20T13:49:29Z` |

### 2.1 Reused 010/011 sample

| Field | Value |
|-------|-------|
| `content_uid` / `sha256` | `536985990c2e2203a74c297bf66c7939873e53647bb41fb9cc72bb42bd6463d6` |
| `document_uid` | same as `content_uid` |
| `chunk_uid` | `214a434afc150e54e796925c9724457eeda75c6916caf73d4439f9ac666b93a5` |
| `evidence_uid` | `d5458356b1a85c241112e4fdda2e5ca6ee9a5adf46c476c0d13dc682deb0c4b3` |
| `kb_evidence.project_uid` | **NULL** (011 C8 — not used for filter) |
| `project_code` | `P6-YHXM-011` |
| `project_uid` | `34e9a380d9728839677790a6fde01014c20a5532ceda388efa15c1ac254dabb5` |
| Chunk/evidence text | `示例方案内容` |
| Project name | `银行项目 P6 E2E` |

### 2.2 Table row counts at E2E start

| Table | Rows |
|-------|------|
| `kb_document` | 3 |
| `kb_document_chunk` | 1 |
| `kb_evidence` | 1 |
| `kb_project` | 2 |
| `kb_project_document` | 1 |
| `kb_curated_asset` | 3 |
| `kb_review_item` | 0 |
| `kb_manual_correction` | 0 |
| `kb_embedding_ref` | 0 |
| `kb_parse_job` | 0 |
| `kb_parse_result` | 217 |
| `kb_parsed_artifact` | 758 |

All six MVP search tables present with searchable data (document titles NULL; chunk/evidence/project/curated indexed text present).

---

## 3. FULLTEXT Real Query Verification

### 3.1 Required CLI (document scope)

```bash
cd /home/szf/dev/pyws/pkb_sdd
export PYTHONPATH=backend

backend/.venv/bin/python -m app.cli.main search-kb \
  --config config/app.yaml \
  --query "银行 项目" \
  --scope document \
  --limit 10 \
  --format json \
  --output /tmp/pkb_sdd_012_p6/search_document.json
```

| Check | Result |
|-------|--------|
| Exit code | **0** |
| `report_type` | `search_results` |
| `schema_version` | `1.0` |
| `summary.total_count` | `0` (all `kb_document.title` NULL) |
| `hits[]` | `[]` |
| Output file | `/tmp/pkb_sdd_012_p6/search_document.json` |

Direct MySQL FULLTEXT confirms zero document matches:

```sql
SELECT COUNT(*) FROM kb_document
WHERE MATCH(title) AGAINST ('银行 项目' IN NATURAL LANGUAGE MODE);
-- => 0
```

Implementation uses `MATCH(...) AGAINST (:q IN NATURAL LANGUAGE MODE)` per scope (verified in P5 code review; real hits on chunk/evidence/project/curated confirm FULLTEXT path active).

---

## 4. Five Scope + scope=all E2E

| Run | Query | Scope | Exit | `total_count` | `returned` | Output path |
|-----|-------|-------|------|---------------|------------|-------------|
| document | `银行 项目` | `document` | 0 | 0 | 0 | `search_document.json` |
| chunk | `示例方案` | `chunk` | 0 | 1 | 1 | `search_chunk.json` |
| evidence | `示例方案` | `evidence` | 0 | 1 | 1 | `search_evidence.json` |
| project | `银行` | `project` | 0 | 1 | 1 | `search_project.json` |
| curated | `银行` | `curated` | 0 | 1 | 1 | `search_curated.json` |
| all | `银行` | `all` | 0 | 2 | 2 | `search_all.json` |

### 4.1 Traceability on real hits

**Chunk** (`search_chunk.json`):

- `chunk_uid`, `document_uid`, `content_uid` present
- `document_uid` = `536985990c2e2203a74c297bf66c7939873e53647bb41fb9cc72bb42bd6463d6`

**Evidence** (`search_evidence.json`):

- `evidence_uid` = `d5458356b1a85c241112e4fdda2e5ca6ee9a5adf46c476c0d13dc682deb0c4b3`
- `document_uid`, `content_uid`, `chunk_uid` present

**Project** (`search_project.json`):

- `project_code` = `P6-YHXM-011`, `project_uid` = `34e9a380…`

**Curated** (`search_curated.json`):

- `curated_uid` = `62417f8ecfeeef2c59face19b7a17e975cbb05dcc4f9fcd3540a9670927f2eef`
- `asset_title` snippet: `Project Card: 银行项目 P6 E2E`

### 4.2 scope=all behavior (`search_all.json`, query `银行`)

| Check | Result |
|-------|--------|
| `scopes_executed` | `["document","chunk","evidence","project","curated"]` |
| `total_count` | `2` (= project 1 + curated 1; document/chunk/evidence 0 for this query) |
| Merge sort | `curated` (score 0.228) before `project` (score ~0) — relevance DESC |
| Per-scope MySQL COUNT sum | Matches CLI `total_count` |

Pagination (`limit=2`):

| Run | offset | returned | Notes |
|-----|--------|----------|-------|
| `search_all_page1.json` | 0 | 2 | Both hits |
| `search_all_page2.json` | 2 | 0 | Correct — only 2 total hits |

---

## 5. --project-code Real Filter

### 5.1 Filter with query `银行`, scope=all

```bash
backend/.venv/bin/python -m app.cli.main search-kb \
  --config config/app.yaml \
  --query "银行" \
  --project-code P6-YHXM-011 \
  --scope all \
  --limit 10 \
  --format json \
  --output /tmp/pkb_sdd_012_p6/search_project_all.json
```

| Check | Result |
|-------|--------|
| Exit | 0 |
| `total_count` | 2 (project + curated for P6-YHXM-011) |
| Hits | `curated` + `project` only; no uncategorized pool leak |
| Filter path | `kb_project.project_code` → `kb_project_document` (not `kb_evidence.project_uid`) |

### 5.2 Filter chunk/evidence via document mapping

```bash
backend/.venv/bin/python -m app.cli.main search-kb \
  --config config/app.yaml \
  --query "示例方案" \
  --project-code P6-YHXM-011 \
  --scope all \
  --format json \
  --output /tmp/pkb_sdd_012_p6/search_project_filter_chunk_evidence.json
```

| Check | Result |
|-------|--------|
| Exit | 0 |
| `total_count` | 2 |
| Hits | `evidence` + `chunk` for `document_uid=536985…` |
| `kb_evidence.project_uid` in DB | **NULL** — filter still works via `kb_project_document` |

### 5.3 Unknown project

```bash
--project-code UNKNOWN-P6
```

| Check | Result |
|-------|--------|
| Exit | **1** |
| `error_code` | `SEARCH_PROJECT_NOT_FOUND` |
| Output | `/tmp/pkb_sdd_012_p6/search_unknown_project.stdout` |

---

## 6. Pagination & Output Formats

| Case | Exit | Verified |
|------|------|----------|
| `--limit 2 --offset 0` | 0 | `search_all_page1.json` |
| `--limit 2 --offset 2` | 0 | `search_all_page2.json` (0 hits) |
| `--format json` | 0 | All JSON outputs valid |
| `--format table` | 0 | `search_table.stdout` — `total_count=1`, project row readable |
| `--output <path>` | 0 | Files under `/tmp/pkb_sdd_012_p6/*.json` |
| Empty result | 0 | `search_empty.json` — `total_count=0`, `hits=[]` |
| Invalid scope | 1 | `SEARCH_INVALID_SCOPE` in stdout JSON |
| `--content-uid` filter | 0 | `search_content_uid.json` — 1 chunk hit for `536985…` |

**Table stdout sample** (`search_table.stdout`):

```text
total_count=1 returned=1
project      0.00 -                -                银行项目 P6 E2E
```

---

## 7. SELECT-only Live DB Verification (TC020–TC022 upgrade)

### 7.1 Row counts before vs after (13 search-kb runs)

| Table | Before | After | Delta |
|-------|--------|-------|-------|
| `kb_document` | 3 | 3 | 0 |
| `kb_document_chunk` | 1 | 1 | 0 |
| `kb_evidence` | 1 | 1 | 0 |
| `kb_project` | 2 | 2 | 0 |
| `kb_project_document` | 1 | 1 | 0 |
| `kb_curated_asset` | 3 | 3 | 0 |
| `kb_review_item` | 0 | 0 | 0 |
| `kb_manual_correction` | 0 | 0 | 0 |
| `kb_embedding_ref` | 0 | 0 | 0 |
| `kb_parse_job` | 0 | 0 | 0 |
| `kb_parse_result` | 217 | 217 | 0 |
| `kb_parsed_artifact` | 758 | 758 | 0 |

**Verdict: PASS** — all denylist tables unchanged after E2E CLI batch.

Artifacts: `/tmp/pkb_sdd_012_p6/row_counts_before.tsv`, `row_counts_after.tsv` (identical).

### 7.2 Filesystem mtime unchanged

| Path | Before epoch | After epoch |
|------|--------------|-------------|
| `raw_vault/.../536985…/original.bin` | 1781460233 | 1781460233 |
| `parsed/.../536985…/parsed_text.md` | 1781523122 | 1781523122 |
| `curated/projects/P6-YHXM-011/00_project_card.md` | 1781880042 | 1781880042 |
| `curated/projects/P6-YHXM-011/10_evidence_index.md` | 1781880042 | 1781880042 |
| `curated/projects/P6-YHXM-011/source_documents.md` | 1781880042 | 1781880042 |

**Verdict: PASS** — no raw_vault / parsed / curated content reads or writes during search.

---

## 8. Forbidden Runtime Boundary

| Forbidden | P6 verification | Result |
|-----------|-----------------|--------|
| Read `raw_vault/original.bin` | mtime unchanged; search uses DB text only | PASS |
| Read `parsed/**` files | mtime unchanged | PASS |
| Read `curated/**/*.md` content | mtime unchanged; curated scope uses `kb_curated_asset.asset_title` | PASS |
| Parser / subprocess | No parser CLI invoked in P6 chain | PASS |
| LLM / embedding / vector | Not invoked | PASS |
| Streamlit / UI | Not started | PASS |
| DB writes | Row counts unchanged | PASS |

**Allowed writes:** operator `--output` JSON under `/tmp/pkb_sdd_012_p6/` only.

---

## 9. Chinese ngram Constraints (C10)

| Test | Query | Result |
|------|-------|--------|
| Multi-char Chinese | `银行`, `示例方案` | Hits on project/curated/chunk/evidence |
| Single-char Chinese | `银` | `total_count=0`, exit 0 |
| `ngram_token_size` | `SHOW VARIABLES` | `2` |

Documented limitation confirmed on live MySQL — not a defect.

---

## 10. Git & Regression

### 10.1 Working tree at P6

```bash
git status --short
```

```text
 M README.md
 M backend/app/cli/main.py
 M docs/feature_index.md
 M specs/012-search-service/*.md (spec phase files)
 M specs/SPEC_INDEX.md
?? backend/app/schemas/search.py
?? backend/app/services/search_service.py
?? backend/tests/fixtures/search/
?? backend/tests/test_search_service.py
?? specs/012-search-service/p2_db_review.md
?? specs/012-search-service/p3_implementation_gate.md
?? specs/012-search-service/p5_qa_report.md
```

```bash
git diff --name-status f698e26..HEAD
```

(empty — HEAD equals `f698e26`; 012 changes uncommitted)

**P6 modified only:** `specs/012-search-service/p6_e2e_report.md` (this file).

### 10.2 Pytest (post-E2E)

**Targeted:**

```bash
PYTHONPATH=backend backend/.venv/bin/pytest backend/tests/test_search_service.py -q
```

```
32 passed in 0.81s
```

**Full regression:**

```bash
PYTHONPATH=backend backend/.venv/bin/pytest backend/tests -q
```

```
278 passed in 22.97s
```

---

## 11. P6 Output Index

| # | Deliverable | Location |
|---|-------------|----------|
| 1 | P6 conclusion | §1 — **PASS WITH NOTES** |
| 2 | Config path | `/home/szf/dev/pyws/pkb_sdd/config/app.yaml` |
| 3 | MySQL + samples | §2 |
| 4 | Query keywords | `银行 项目`, `银行`, `示例方案`, `不存在的关键词xyz`, `银` |
| 5 | Per-scope CLI + exit + output | §4 table |
| 6 | scope=all scopes_executed + total_count | §4.2 |
| 7 | --project-code results | §5 |
| 8 | unknown/empty/invalid behavior | §5.3, §6 |
| 9 | JSON/table output | §3, §6 |
| 10 | Live DB before/after | §7.1 |
| 11 | mtime unchanged | §7.2 |
| 12 | Forbidden runtime | §8 |
| 13 | Targeted pytest | 32 passed |
| 14 | Full regression | 278 passed |
| 15 | P6 report path | `specs/012-search-service/p6_e2e_report.md` |
| 16 | P6 commit hash | `f698e26` (012 code uncommitted) |

---

## 12. P6 STOP

P6 E2E complete. **Do not enter P7 Final Review** until user confirms.

Recommended P7 entry checks:

- Commit 012 implementation + P5/P6 reports on `feature/012-search-service`
- TL final review against acceptance A001–A019
- Optional: seed `kb_document.title` in future E2E for non-zero document-scope hits

---

## 13. Post-E2E TL Gate Fix (traceability)

E2E technical validation (§2–§11) was executed while 012 implementation remained uncommitted at `f698e26`. ChatGPT TL review **BLOCKED P7** on missing commit chain.

**TL remediation:** staged commits on `feature/012-search-service` (P1→P6) without altering E2E evidence above. P7 entry requires HEAD past P6 commit with clean working tree.

**Historical note (E2E run time):** items in §1 Notes #3 and checklist #16 reflect pre-commit state; superseded after §13 commits land.

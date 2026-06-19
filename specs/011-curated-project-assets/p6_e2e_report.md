# 011 Curated Project Assets — P6 E2E Validation Report

> Role: E2E Agent  
> Spec: `specs/011-curated-project-assets/`  
> Branch: `feature/011-curated-project-assets`  
> Stage: P6 E2E Validation  
> P5 commit: `2a2caed`  
> Status: **P6 COMPLETE — PASS**

---

## 1. Gate Conclusion

**P6 E2E Validation: PASS**

`build-curated-project` was validated against:

- real `config/app.yaml` (explicit `--config` and default-path dry-run)
- real MySQL (`personal_kb` @ `127.0.0.1`)
- real 010 evidence sample (`536985…` / MarkItDown `方案.txt` chain)
- real `curated_root` under project path (`./curated` → `/home/szf/dev/pyws/pkb_sdd/curated`)

All P6 curated checks passed. **011 runtime did not invoke parsers, evidence builder, LLM, embedding, search, or UI.**

No P6 setup CLI chain was required — 010 P6 sample rows already present in MySQL.

---

## 2. Sample Selection

Reused 010 P6 validated sample:

| Field | Value |
|---|---|
| `content_uid` / `sha256` | `536985990c2e2203a74c297bf66c7939873e53647bb41fb9cc72bb42bd6463d6` |
| `document_uid` | same as `content_uid` (010 registry row) |
| `evidence_uid` | `d5458356b1a85c241112e4fdda2e5ca6ee9a5adf46c476c0d13dc682deb0c4b3` |
| Evidence count | **1** |
| Chunk count | **1** |
| Source | `backend/tests/fixtures/中文路径/银行项目/方案.txt` (010 setup) |
| `parser_name` | `markitdown` |

P6 project (new, CLI mapping):

| Field | Value |
|---|---|
| `project_code` | `P6-YHXM-011` |
| `project_name` | `银行项目 P6 E2E` |
| `project_uid` | `34e9a380d9728839677790a6fde01014c20a5532ceda388efa15c1ac254dabb5` |
| `mapping_method` | `CLI` |

Pre-existing unrelated row: `kb_project` had `uncategorized` / `未归属项目池` — not modified by P6 runs.

---

## 3. Config & Paths

| Item | Value |
|---|---|
| Config (primary) | `/home/szf/dev/pyws/pkb_sdd/config/app.yaml` |
| Default config smoke | dry-run **without** `--config` → exit 0, report `/tmp/pkb_sdd_011_p6/curated_default_config_dry_run.json` |
| `curated_root` | `/home/szf/dev/pyws/pkb_sdd/curated` |
| P6 reports dir | `/tmp/pkb_sdd_011_p6/` |
| Parsed sample | `/home/szf/dev/pyws/pkb_sdd/parsed/by_hash/53/69/536985…/parsed_text.md` |
| raw_vault sample | `/home/szf/dev/pyws/pkb_sdd/raw_vault/by_hash/53/536985…/original.bin` |

---

## 4. E2E Commands (011 runtime only)

```bash
cd /home/szf/dev/pyws/pkb_sdd
source backend/.venv/bin/activate

CONTENT_UID=536985990c2e2203a74c297bf66c7939873e53647bb41fb9cc72bb42bd6463d6
PROJECT_CODE=P6-YHXM-011
PROJECT_NAME='银行项目 P6 E2E'
P6_DIR=/tmp/pkb_sdd_011_p6

# 1 dry-run
PYTHONPATH=backend python -m app.cli.main build-curated-project \
  --config config/app.yaml \
  --project-code "$PROJECT_CODE" \
  --project-name "$PROJECT_NAME" \
  --content-uid "$CONTENT_UID" \
  --dry-run \
  --output "$P6_DIR/curated_dry_run_report.json"

# 2 first non dry-run
PYTHONPATH=backend python -m app.cli.main build-curated-project \
  --config config/app.yaml \
  --project-code "$PROJECT_CODE" \
  --project-name "$PROJECT_NAME" \
  --content-uid "$CONTENT_UID" \
  --output "$P6_DIR/curated_run_report.json"

# 3 no-force rerun
PYTHONPATH=backend python -m app.cli.main build-curated-project \
  --config config/app.yaml \
  --project-code "$PROJECT_CODE" \
  --project-name "$PROJECT_NAME" \
  --content-uid "$CONTENT_UID" \
  --output "$P6_DIR/curated_rerun_no_force_report.json"

# 4 force rerun
PYTHONPATH=backend python -m app.cli.main build-curated-project \
  --config config/app.yaml \
  --project-code "$PROJECT_CODE" \
  --project-name "$PROJECT_NAME" \
  --content-uid "$CONTENT_UID" \
  --force \
  --output "$P6_DIR/curated_force_report.json"

# 5 default config path smoke (dry-run, no --config)
PYTHONPATH=backend python -m app.cli.main build-curated-project \
  --project-code "$PROJECT_CODE" \
  --content-uid "$CONTENT_UID" \
  --dry-run \
  --output "$P6_DIR/curated_default_config_dry_run.json"
```

**Note:** Used `CONTENT_UID` env var (not bash `UID`, which is readonly) — lesson from 010 P6.

---

## 5. Report Summaries

### 5.1 Dry-run (`curated_dry_run_report.json`)

| Field | Value |
|---|---|
| `dry_run` | `true` |
| `documents_mapped` | 1 |
| `evidence_rows_read` | 1 |
| `assets_written` | **0** |
| `files_written` | **0** |
| `db_projects_upserted` | **0** |

**PASS** — zero DB write, zero curated file write.

### 5.2 First run (`curated_run_report.json`)

| Field | Value |
|---|---|
| `assets_written` | **3** |
| `files_written` | **3** |
| `assets_skipped` | 0 |

**PASS** — first real write.

### 5.3 No-force rerun (`curated_rerun_no_force_report.json`)

| Field | Value |
|---|---|
| `assets_written` | **0** |
| `assets_skipped` | **3** |
| `files_written` | **0** |

**PASS** — skip when SUCCESS assets + files exist.

### 5.4 Force rerun (`curated_force_report.json`)

| Field | Value |
|---|---|
| `assets_written` | **3** (overwrite + upsert) |
| `files_written` | **3** |
| `project_uid` | unchanged |
| `curated_uid` set | unchanged (3 UIDs) |
| `version_no` | **1** on all assets |

**PASS** — force overwrite without duplicate primary rows.

### 5.5 Default config dry-run (`curated_default_config_dry_run.json`)

Exit 0, `dry_run=true`, `assets_written=0`. **PASS**

### 5.6 JSON schema

All reports: `report_type=curated_build_report`, `schema_version=1.0`, `mode=build`. **PASS**

---

## 6. Generated Curated Files (runtime output — not committed)

Under `{curated_root}/projects/P6-YHXM-011/`:

```text
/home/szf/dev/pyws/pkb_sdd/curated/projects/P6-YHXM-011/00_project_card.md
/home/szf/dev/pyws/pkb_sdd/curated/projects/P6-YHXM-011/10_evidence_index.md
/home/szf/dev/pyws/pkb_sdd/curated/projects/P6-YHXM-011/source_documents.md
```

**Exactly 3 Markdown files** — no extra assets. **PASS**

### 6.1 Content traceability

| Field | Present in output | Result |
|---|---|---|
| `project_code` | `00_project_card.md` | PASS |
| `project_name` | `00_project_card.md` header | PASS |
| `document_uid` | all three files | PASS |
| `content_uid` | all three files | PASS |
| `evidence_uid` | `10_evidence_index.md` | PASS |
| `generation_method` | `TEMPLATE_RULE` in card + DB | PASS |

Example evidence row in index:

```text
d5458356b1a85c241112e4fdda2e5ca6ee9a5adf46c476c0d13dc682deb0c4b3
quote_snippet: 示例方案内容
```

---

## 7. DB Row Counts (curated window)

Counts before first **non-dry-run** (after dry-run; dry-run wrote nothing):

| Table | Before curated writes | After all curated runs | Delta |
|---|---|---|---|
| `kb_project` | 1 | **2** | **+1** (P6-YHXM-011) |
| `kb_project_document` | 0 | **1** | **+1** |
| `kb_curated_asset` | 0 | **3** | **+3** |
| `kb_document` | 3 | 3 | 0 |
| `kb_document_chunk` | 1 | 1 | 0 |
| `kb_evidence` | 1 | 1 | 0 |
| `kb_review_item` | 0 | 0 | 0 |
| `kb_manual_correction` | 0 | 0 | 0 |
| `kb_embedding_ref` | 0 | 0 | 0 |
| `kb_parse_run` | 197 | 197 | 0 |
| `kb_parse_result` | 195 | 195 | 0 |
| `kb_parsed_artifact` | 682 | 682 | 0 |

**PASS** — only `kb_project`, `kb_project_document`, `kb_curated_asset` changed.

### 7.1 Persisted curated UIDs

| asset_type | curated_uid | version_no |
|---|---|---|
| `project_card` | `62417f8ecfeeef2c59face19b7a17e975cbb05dcc4f9fcd3540a9670927f2eef` | 1 |
| `evidence_index` | `2c4248cb63118fd5716db94a561e711298a9a1db349bdb4b4755e48caade6fa0` | 1 |
| `source_documents` | `4d7f2ac7897a6e53205b6f2bd723eb85a1e1d66a14dab5cd44bf00e0cb8db892` | 1 |

### 7.2 Evidence backfill check

```text
kb_evidence.project_uid = NULL  (unchanged after curated runs)
```

**PASS** — no evidence backfill.

---

## 8. Filesystem Boundary

| Path | mtime before | mtime after | Result |
|---|---|---|---|
| `parsed_text.md` (536985…) | `1781523122` | `1781523122` | **unchanged** |
| `original.bin` (536985…) | `1781460233` | `1781460233` | **unchanged** |
| `raw_vault/**` (repo) | — | no git changes | PASS |
| `parsed/**` (repo) | — | no git changes | PASS |

011 runtime reads evidence/registry from MySQL only — did not open `original.bin` for extraction during curated build.

---

## 9. Forbidden Runtime Confirmation

| Check | Result |
|---|---|
| Parser invocation during `build-curated-project` | **No** |
| `build-evidence-chain` during 011 runs | **No** |
| LLM / embedding / search / Streamlit | **No** |
| raw_vault binary read for text | **No** (mtime unchanged) |
| parsed artifact mutation | **No** (mtime unchanged) |
| Forbidden DB writes | **No** |

---

## 10. Regression (post-E2E)

```bash
PYTHONPATH=backend pytest backend/tests/test_curated_project_assets.py -q
# 18 passed

PYTHONPATH=backend pytest backend/tests -q
# 246 passed
```

**PASS**

---

## 11. P6 Artifacts & Git Scope

| Artifact | Location | Committed to git? |
|---|---|---|
| P6 report | `specs/011-curated-project-assets/p6_e2e_report.md` | **Yes** |
| JSON reports | `/tmp/pkb_sdd_011_p6/*.json` | No |
| Runtime curated files | `curated/projects/P6-YHXM-011/*.md` | **No** (runtime only) |
| MySQL rows | dev DB residual for P6-YHXM-011 | Intentional E2E artifact |

Do **not** auto-clean dev MySQL or runtime curated files unless operator requests.

---

## 12. P6 Gate Summary

| Item | Result |
|---|---|
| P6 E2E | **PASS** |
| Default `--config` path | **PASS** |
| dry-run zero write | **PASS** |
| First run 3 files + 3 tables | **PASS** |
| no-force skip | **PASS** |
| force idempotent UID | **PASS** |
| Forbidden table delta | **0** |
| Regression | **246 passed** |
| Approve P7 | **Yes** (pending user confirmation) |

---

## 13. STOP

P6 completed. **Do not enter P7** until user confirms.

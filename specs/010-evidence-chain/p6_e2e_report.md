# 010 Evidence Chain — P6 E2E Validation Report

> Role: E2E Agent  
> Spec: `specs/010-evidence-chain/`  
> Branch: `feature/010-evidence-chain`  
> Stage: P6 E2E Validation  
> P5 commit: `d45b71d`  
> Status: **P6 BLOCKED — cannot complete full E2E**

---

## 1. Gate Conclusion

**P6 E2E Validation: BLOCKED**

Full end-to-end validation of `build-evidence-chain` against real MySQL + real parsed artifacts **cannot be completed** in the current local environment.

Reason: the only on-disk MarkItDown SUCCESS parsed tree under `config/app.yaml` `parsed_root` is **not linked** to `kb_parse_result` / `kb_file_content`. All registry SUCCESS rows point to **deleted** `/tmp/pytest-of-root/...` paths. Using registry-only or synthetic fixture data would violate P6 rules.

**Do not enter P7** until a real parsed + registry-linked sample is available and P6 is re-run.

Partial checks performed (dry-run probe, schema validation, environment inventory) are documented below.

---

## 2. Blocker Analysis

### 2.1 On-disk parsed sample (real, not synthetic)

| Field | Value |
|---|---|
| `content_uid` | `536985990c2e2203a74c297bf66c7939873e53647bb41fb9cc72bb42bd6463d6` |
| `sha256` | `536985990c2e2203a74c297bf66c7939873e53647bb41fb9cc72bb42bd6463d6` |
| `parser_name` | `markitdown` |
| `manifest status` | `SUCCESS` |
| `parsed_dir` | `/home/szf/dev/pyws/pkb_sdd/parsed/by_hash/53/69/536985990c2e2203a74c297bf66c7939873e53647bb41fb9cc72bb42bd6463d6` |
| `parsed_text.md` | Present (19 bytes, Chinese text `示例方案内容`) |
| `raw_vault original.bin` | Present at `/home/szf/dev/pyws/pkb_sdd/raw_vault/by_hash/53/536985990c2e2203a74c297bf66c7939873e53647bb41fb9cc72bb42bd6463d6/original.bin` |

This is the **only** `parse_manifest.json` under project `parsed/` (verified via `find parsed -name parse_manifest.json`).

### 2.2 MySQL registry gap

```sql
SELECT COUNT(*) FROM kb_parse_result WHERE parsed_dir NOT LIKE '/tmp/%';
-- 0

SELECT COUNT(*) FROM kb_parse_result;
-- 180 (all parsed_dir under /tmp/pytest-of-root/...)
```

Sample path check:

```text
/tmp/pytest-of-root/pytest-60/.../8888.../parsed_text.md → MISSING on disk
```

`kb_file_content` for sha256 `536985...`:

```text
(no row)
```

### 2.3 Reconcile attempt (prerequisite probe, not P6 success path)

```bash
PYTHONPATH=backend python -m app.cli.main reconcile-parsed-artifacts \
  --config config/app.yaml \
  --sha256 536985990c2e2203a74c297bf66c7939873e53647bb41fb9cc72bb42bd6463d6
```

Result:

```text
Orphan manifest without DB content: .../parse_manifest.json
Results recorded: 0
Artifacts recorded: 0
```

Cannot register parsed manifest without prior `kb_file_content` / inventory row.

### 2.4 Evidence chain probe (dry-run only)

```bash
PYTHONPATH=backend python -m app.cli.main build-evidence-chain \
  --config config/app.yaml \
  --content-uid 536985990c2e2203a74c297bf66c7939873e53647bb41fb9cc72bb42bd6463d6 \
  --dry-run \
  --output /tmp/pkb_sdd_010_p6/evidence_dry_run_probe.json
```

CLI exit code: **0**

```text
Candidates selected: 0
Documents processed: 0
Chunks upserted: 0
Evidence upserted: 0
Dry run: True
```

Expected behavior: service selects candidates from `kb_parse_result` only; no matching row → zero candidates. **Not sufficient for P6 PASS.**

---

## 3. E2E Steps Not Executed

Due to blocker, the following P6 steps were **not run**:

| Step | Status |
|---|---|
| Non dry-run build | **NOT RUN** (0 candidates) |
| Re-run without `--force` (skip) | **NOT RUN** |
| Re-run with `--force` (upsert idempotent) | **NOT RUN** |
| DB before/after chunk/evidence growth | **NOT RUN** (tables remain 0) |
| Idempotency UID verification on real MySQL | **NOT RUN** |

---

## 4. Partial Validation Results

### 4.1 Dry-run report schema (`evidence_dry_run_probe.json`)

| Field | Observed | Expected | Result |
|---|---|---|---|
| `report_type` | `evidence_build_report` | `evidence_build_report` | PASS |
| `schema_version` | `1.0` | `1.0` | PASS |
| `mode` | `build` | `build` | PASS |
| `dry_run` | `true` | `true` | PASS |
| `summary.candidates_selected` | `0` | N/A (blocked env) | INFO |

JSON file generated at `/tmp/pkb_sdd_010_p6/evidence_dry_run_probe.json`. **Schema valid.**

### 4.2 DB table counts (snapshot at P6 time)

| Table | Row count |
|---|---|
| `kb_document_chunk` | 0 |
| `kb_evidence` | 0 |
| `kb_document` | 2 |
| `kb_parse_run` | 182 |
| `kb_parse_result` | 180 |
| `kb_parsed_artifact` | 630 |
| `kb_curated_asset` | 0 |
| `kb_review_item` | 0 |
| `kb_embedding_ref` | 0 |

No chunk/evidence rows before or after probe. Registry tables unchanged by probe (dry-run + 0 candidates).

### 4.3 Filesystem mtime (real sample, unchanged after probe)

| Path | mtime |
|---|---|
| `parsed/.../parsed_text.md` | 2026-06-15 19:32:02 +0800 |
| `parsed/.../parsed_metadata.json` | 2026-06-15 19:32:02 +0800 |
| `parsed/.../parse_manifest.json` | 2026-06-15 19:32:02 +0800 |
| `raw_vault/.../original.bin` | 2026-06-15 02:03:10 +0800 |

No modification during dry-run probe. **PASS** (read-only boundary preserved).

---

## 5. Report Summaries (executed vs planned)

| Report file | Executed | Summary |
|---|---|---|
| `evidence_dry_run_report.json` | Partial (`evidence_dry_run_probe.json`) | 0 candidates; schema OK |
| `evidence_run_report.json` | **NOT RUN** | — |
| `evidence_rerun_no_force_report.json` | **NOT RUN** | — |
| `evidence_force_report.json` | **NOT RUN** | — |

---

## 6. E2E Defects

| ID | Severity | Description |
|---|---|---|
| E2E-BLOCK-1 | **Blocker** | No `kb_parse_result` row with non-`/tmp` `parsed_dir` pointing to existing artifacts |
| E2E-BLOCK-2 | **Blocker** | Sole real parsed sample (`536985...`) has no `kb_file_content`; reconcile cannot register |
| E2E-BLOCK-3 | **Blocker** | 180 registry SUCCESS rows reference deleted pytest temp parsed trees |

**Not an implementation defect in 010 code** — environment / data pipeline gap (001 scan → 002 vault → 005/006 parse/register not completed for the real parsed sample).

---

## 7. Recommended Unblock Steps (for operator, not P6 scope)

1. Re-run **001 scan** + **002 copy-to-vault** for source file matching sha256 `536985...`, **or** insert consistent `kb_file_content` if vault already exists.
2. Run **006 reconcile-parsed-artifacts** or **register-parse-report** so `kb_parse_result` references the on-disk parsed dir.
3. Re-run P6 E2E with same `content_uid` / `sha256`.

Alternative: parse a fresh COPIED content (e.g. `796751...` has vault but no parsed) via **005 parse-markitdown** + registry, then run P6.

---

## 8. P6 Change Summary

P6 modified **documentation only**:

```text
specs/010-evidence-chain/p6_e2e_report.md
```

No `backend/**`, `parsed/**`, or `raw_vault/**` modifications.

---

## 9. STOP

P6 completed with **BLOCKED** status. **Do not enter P7** until user confirms unblock path and P6 re-run.

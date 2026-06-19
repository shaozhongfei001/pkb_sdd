# 010 Evidence Chain — P6 E2E Validation Report

> Role: E2E Agent  
> Spec: `specs/010-evidence-chain/`  
> Branch: `feature/010-evidence-chain`  
> Stage: P6 E2E Validation  
> Initial blocked report: `ea18034`  
> P5 commit: `d45b71d`  
> Status: **P6 COMPLETE — PASS** (after environment setup + re-run)

---

## 1. Gate Conclusion

**P6 E2E Validation: PASS**

After P6 environment setup (001 scan → 002 copy-to-vault → 005 parse-markitdown → 006 register-parse-report), `build-evidence-chain` was validated against:

- real `config/app.yaml`
- real MySQL
- real `raw_vault` + `parsed` artifacts (MarkItDown SUCCESS)
- real registry-linked `kb_parse_result` row

All P6 evidence-chain checks passed. **010 runtime did not invoke parsers** during `build-evidence-chain` runs.

Initial attempt (`ea18034`) was **BLOCKED** due to missing registry link; resolved by setup below without modifying 010 backend code.

---

## 2. Candidate Sample Selection

### 2.1 Selection criteria

| Criterion | Result |
|---|---|
| MarkItDown-suitable content | `.txt` / `text/plain` |
| `kb_file_content.vault_status = COPIED` (after setup) | Yes |
| `raw_vault/.../original.bin` on project path | Yes |
| Valid parsed three-file set on disk | Yes (pre-existing from prior 005 run) |
| No non-`/tmp` `kb_parse_result` before setup | Yes (gap filled by setup) |

### 2.2 Selected sample

| Field | Value |
|---|---|
| `content_uid` | `536985990c2e2203a74c297bf66c7939873e53647bb41fb9cc72bb42bd6463d6` |
| `sha256` | same as `content_uid` |
| Source file | `backend/tests/fixtures/中文路径/银行项目/方案.txt` |
| `parser_name` | `markitdown` |
| `file_ext` | `.txt` |
| Parsed text | `示例方案内容` (single section, no headings → 1 chunk) |

### 2.3 Why this sample

- SHA256 matches existing project `raw_vault` and `parsed` trees under `config/app.yaml` paths (real artifacts, not synthetic fixture dir copied into `/tmp`).
- Chinese filename path preserved in inventory scan source.
- Before setup: parsed on disk but **no** `kb_file_content` → evidence chain could not select candidate (initial P6 BLOCKED).
- After setup: full chain `kb_file_content` → parsed → `kb_parse_result SUCCESS`.

### 2.4 Rejected alternatives

| Candidate | Reason rejected |
|---|---|
| `796751...` (only COPIED row before setup) | `.pdf`; vault_path under `/tmp/p5_reqa_...`; no project parsed tree |
| Registry rows under `/tmp/pytest-of-root/...` | Parsed paths deleted on disk |

---

## 3. P6 Environment Setup (not 010 runtime)

Setup used existing 001/002/005/006 CLI only. **Not** part of `build-evidence-chain` behavior.

```bash
cd /home/szf/dev/pyws/pkb_sdd
source backend/.venv/bin/activate

# 001 — register file instances from real fixture path
PYTHONPATH=backend python -m app.cli.main scan \
  --config config/app.yaml \
  --path backend/tests/fixtures/中文路径

# 002 — link DB to existing project raw_vault (skipped bin copy, refreshed metadata)
PYTHONPATH=backend python -m app.cli.main copy-to-vault \
  --config config/app.yaml \
  --sha256 536985990c2e2203a74c297bf66c7939873e53647bb41fb9cc72bb42bd6463d6

# 005 — idempotent skip (manifest already SUCCESS on disk); report still emitted
PYTHONPATH=backend python -m app.cli.main parse-markitdown \
  --config config/app.yaml \
  --sha256 536985990c2e2203a74c297bf66c7939873e53647bb41fb9cc72bb42bd6463d6

# 006 — register parse report → kb_parse_result SUCCESS + artifacts
PYTHONPATH=backend python -m app.cli.main register-parse-report \
  --config config/app.yaml \
  --report-path /home/szf/dev/data/personal-kb/reports/parse_markitdown_report_20260619T132348Z.json
```

Setup results:

```text
scan: 2 instances, 1 unique content
copy-to-vault: Skipped (already copied), Metadata refreshed: 1
parse-markitdown: Skipped: 1 (idempotent_success_manifest)
register-parse-report: Results recorded: 1, Artifacts recorded: 4, Status: COMPLETED
```

Registry row after setup:

```text
kb_parse_result.status = SUCCESS
parsed_dir = /home/szf/dev/pyws/pkb_sdd/parsed/by_hash/53/69/536985.../
manifest_path = .../parse_manifest.json
```

---

## 4. Parsed Artifact Paths

```text
/home/szf/dev/pyws/pkb_sdd/parsed/by_hash/53/69/536985990c2e2203a74c297bf66c7939873e53647bb41fb9cc72bb42bd6463d6/
  parsed_text.md
  parsed_metadata.json
  parse_manifest.json

/home/szf/dev/pyws/pkb_sdd/raw_vault/by_hash/53/536985990c2e2203a74c297bf66c7939873e53647bb41fb9cc72bb42bd6463d6/
  original.bin
```

---

## 5. E2E Evidence Chain Commands

Evidence window DB baseline taken **after setup**, **before** `build-evidence-chain` runs. Pre-existing chunk/evidence rows for this content were cleared once for a clean first-write test.

```bash
CONTENT_UID=536985990c2e2203a74c297bf66c7939873e53647bb41fb9cc72bb42bd6463d6

# 1 dry-run
PYTHONPATH=backend python -m app.cli.main build-evidence-chain \
  --config config/app.yaml \
  --content-uid "$CONTENT_UID" \
  --dry-run \
  --output /tmp/pkb_sdd_010_p6/evidence_dry_run_report.json

# 2 non dry-run
PYTHONPATH=backend python -m app.cli.main build-evidence-chain \
  --config config/app.yaml \
  --content-uid "$CONTENT_UID" \
  --output /tmp/pkb_sdd_010_p6/evidence_run_report.json

# 3 no-force rerun
PYTHONPATH=backend python -m app.cli.main build-evidence-chain \
  --config config/app.yaml \
  --content-uid "$CONTENT_UID" \
  --output /tmp/pkb_sdd_010_p6/evidence_rerun_no_force_report.json

# 4 force rerun
PYTHONPATH=backend python -m app.cli.main build-evidence-chain \
  --config config/app.yaml \
  --content-uid "$CONTENT_UID" \
  --force \
  --output /tmp/pkb_sdd_010_p6/evidence_force_report.json
```

**Note:** First failed E2E attempt used bash variable `UID` (readonly) — `--content-uid` was empty → 0 candidates. Re-run used `CONTENT_UID`. Documented as operator error, not product defect.

---

## 6. Report Summaries

### 6.1 Dry-run (`evidence_dry_run_report.json`)

| Field | Value |
|---|---|
| `dry_run` | `true` |
| `candidates_selected` | 1 |
| `documents_processed` | 1 |
| `chunks_planned` | 1 |
| `chunks_upserted` | **0** |
| `evidence_upserted` | **0** |
| DB chunk rows after | **0** |

**PASS** — zero DB write.

### 6.2 Non dry-run (`evidence_run_report.json`)

| Field | Value |
|---|---|
| `chunks_upserted` | 1 |
| `evidence_upserted` | 1 |
| Chunk | `chunk_index=0`, `chunk_level=section`, `page_no=null`, `bbox=null` |
| Content | `示例方案内容` |

**PASS** — first real write.

### 6.3 No-force rerun (`evidence_rerun_no_force_report.json`)

| Field | Value |
|---|---|
| `documents_processed` | 0 |
| `documents_skipped` | **1** |
| `chunks_upserted` | 0 |

**PASS** — skip when chunks already exist.

### 6.4 Force rerun (`evidence_force_report.json`)

| Field | Value |
|---|---|
| `chunks_upserted` | 1 (upsert) |
| `documents_processed` | 1 |
| Chunk UID set | **unchanged** vs after first run |

**PASS** — upsert idempotent; no duplicate UID rows.

### 6.5 JSON schema

All four reports: `report_type=evidence_build_report`, `schema_version=1.0`, `mode=build`. **PASS**

---

## 7. DB Row Counts (evidence window)

| Table | Before evidence runs | After evidence runs | Delta |
|---|---|---|---|
| `kb_document_chunk` | 0 | **1** | +1 |
| `kb_evidence` | 0 | **1** | +1 |
| `kb_document` | 3 | 3 | 0 |
| `kb_parse_run` | 183 | 183 | 0 |
| `kb_parse_result` | 181 | 181 | 0 |
| `kb_parsed_artifact` | 634 | 634 | 0 |
| `kb_curated_asset` | 0 | 0 | 0 |
| `kb_review_item` | 0 | 0 | 0 |
| `kb_embedding_ref` | 0 | 0 | 0 |

**PASS** — only chunk + evidence tables changed during evidence-chain runs.

Persisted rows:

```text
chunk_uid:   214a434afc150e54e796925c9724457eeda75c6916caf73d4439f9ac666b93a5
evidence_uid: d5458356b1a85c241112e4fdda2e5ca6ee9a5adf46c476c0d13dc682deb0c4b3
evidence_type: section_quote
quote_text: 示例方案内容
```

---

## 8. Filesystem Boundary

| Path | mtime before | mtime after | Changed |
|---|---|---|---|
| `parsed/.../parsed_text.md` | 2026-06-15 19:32:02 | same | **No** |
| `parsed/.../parsed_metadata.json` | 2026-06-15 19:32:02 | same | **No** |
| `parsed/.../parse_manifest.json` | 2026-06-15 19:32:02 | same | **No** |
| `raw_vault/.../original.bin` | 2026-06-15 02:03:53 | same | **No** |

**PASS**

---

## 9. 010 Runtime Behavior

| Check | Result |
|---|---|
| `build-evidence-chain` calls MarkItDown/MinerU | **No** (reads parsed only) |
| Setup phase parser use | 005 used during setup only (separate CLI) |
| Reparse / repair / 008/009 consume | **No** |
| LLM / embedding / curated writes | **No** |

**PASS**

---

## 10. Defects

**No 010 implementation defects found.**

| ID | Severity | Note |
|---|---|---|
| OPS-1 | Info | Initial P6 blocked: orphan parsed without `kb_file_content` — fixed by setup |
| OPS-2 | Info | bash `UID` readonly variable caused empty `--content-uid` on first re-run attempt |

---

## 11. Historical: Initial BLOCKED (`ea18034`)

First P6 attempt documented missing registry-linked sample. Resolved by §3 setup without code changes.

---

## 12. STOP

P6 E2E **COMPLETE**. **Do not enter P7** until user confirms.

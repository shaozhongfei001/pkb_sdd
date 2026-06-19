# Spec Index

> This file is the authoritative index for active, completed, deprecated, and future specs.
>
> When Cursor / ChatGPT / Agent workflows choose a spec, they must read this file first.
> Do not infer the active spec from directory numbering alone.

---

## 1. Active Completed Chain

| Phase | Active Spec Directory | Implementation Status | Notes |
|---|---|---:|---|
| 001 | `specs/001-file-inventory/` | DONE | File inventory / scan |
| 002 | `specs/002-file-content-vault/` | DONE | Raw file content vault |
| 003 | `specs/003-duplicate-governance/` | DONE | Exact duplicate governance |
| 004 | `specs/004-parser-router/` | DONE | Parser route planning only |
| 005 | `specs/005-markitdown-parser/` | DONE | MarkItDown parser adapter |
| 006 | `specs/006-parse-job-registry/` | DONE | Parse job/result/artifact registry |
| 007 | `specs/007-mineru-pdf-parser-adapter/` | DONE | MinerU PDF parser adapter |
| 008 | `specs/008-parse-quality-checker/` | DONE | Parse quality checker |
| 009 | `specs/009-quality-report-summary/` | DONE | Parse quality report summary |
| 010 | `specs/010-evidence-chain/` | DONE | Evidence chain (chunk + evidence) |

---

## 2. Deprecated / Superseded Stub Specs

These directories are early roadmap or stub specs. They are preserved for historical context, but must not be used as the active implementation contract.

| Directory | Status | Replacement / Current Authority |
|---|---|---|
| `specs/006-mineru-parser/` | DEPRECATED | Use `specs/007-mineru-pdf-parser-adapter/` |
| `specs/007-quality-checker/` | DEPRECATED | Use `specs/008-parse-quality-checker/` |

---

## 3. Future / Not Current Specs

| Directory | Status | Notes |
|---|---|---|
| `specs/008-review-workflow/` | FUTURE STUB / NOT CURRENT | Human review workflow. This is **not** the completed 008 parse quality checker. Do not start unless this index explicitly sets it ACTIVE. |
| `specs/011-curated-project-assets/` | FUTURE | Curated assets / project cards (renumbered from former `010-curated-project-assets`) |
| `specs/012-search-service/` | FUTURE | Search service (renumbered from former `011-search-service`) |
| `specs/013-streamlit-admin/` | FUTURE | Streamlit admin UI (renumbered from former `012-streamlit-admin`) |
| `specs/901-docker-compose-deployment/` | SUPPORT / FUTURE | Deployment support |
| `specs/902-test-dataset/` | SUPPORT / FUTURE | Test dataset support |

### 3.1 Future Spec Renumber Note (2026-06)

To avoid two `009` semantics coexisting, former future stubs were renumbered:

```text
009-evidence-chain        -> 010-evidence-chain
010-curated-project-assets -> 011-curated-project-assets
011-search-service        -> 012-search-service
012-streamlit-admin       -> 013-streamlit-admin
```

`009` is the completed `009-quality-report-summary` spec.

---

## 4. Contract Rules for Agents

### 4.1 Spec Selection

Agents must follow this order when selecting a spec:

1. Read `specs/SPEC_INDEX.md`.
2. Use the `Active Spec Directory` listed in this file.
3. Do not select a spec by numeric prefix alone.
4. Do not use deprecated stub directories as implementation contracts.
5. If a directory number conflicts with this index, this index wins.

### 4.2 Current Active Phase

**No spec is currently ACTIVE.**

The most recently completed phase is:

`010 Evidence Chain` — `specs/010-evidence-chain/` — **DONE**

To start new work, read this index and run an explicit Active Spec Selection Review. Do not infer the active spec from directory numbering alone.

### 4.3 Completed 010 Boundary (Reference)

`010-evidence-chain` builds chunk and evidence metadata from parsed artifacts.

It may:

- read `config/app.yaml` (`parsed_root`, `pipeline_version`, mysql for sessions)
- read `parsed_text.md`, `parsed_metadata.json`, `parse_manifest.json` (**read-only**)
- SELECT from `kb_document`, `kb_parse_result`, `kb_file_content`, and related registry tables
- INSERT/UPSERT `kb_document_chunk` and `kb_evidence` with deterministic idempotent UIDs
- write optional JSON build report (`--output`)

It must not:

- read `raw_vault` binary objects (`original.bin`) for text extraction
- modify parsed artifacts or original user files
- call MarkItDown, MinerU, or `magic-pdf` at runtime
- reparse, repair, or auto-fix 008/009 quality findings
- write parse registry during `build-evidence-chain`
- write `curated/`, project cards, vectors, embeddings, or `kb_review_item`
- use LLM chunking or semantic splitting
- introduce schema migration without a separate migration spec

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

010 must not be re-opened for implementation unless a new defect spec is explicitly approved.

### 4.4 Completed 009 Boundary (Reference)

`009-quality-report-summary` is a completed read-only report consumption phase.

It may:

- read `config/app.yaml` for `reports_root` and default input discovery
- read an existing 008 `parse_quality_report.json` file (`--input` or latest under `reports_root`)
- write a Markdown or JSON summary file under `reports_root` or `--output`
- classify issues in the input report into noise buckets (`TEST_STALE_PATH`, `STALE_VAULT_PATH`, `REAL_DEFECT`)
- filter and aggregate issue data already present in the 008 report

It must not:

- read `raw_vault`
- read `parsed`
- connect to MySQL
- write DB records
- call MarkItDown, MinerU, or `magic-pdf`
- invoke `check-parse-quality` to rescan the project
- repair, reparse, delete, move, or rename files
- clean pytest dirty DB records
- write curated assets, vectors, embeddings, or project cards
- use LLM semantic judgment

Default output should be a summary under `reports_root`, for example:

`parse_quality_summary_{UTC}.md`

If a future design proposes DB writes or filesystem reads beyond the 008 JSON report, the workflow must STOP and enter TL + DB Review first.

009 must not be re-opened for implementation unless a new defect spec is explicitly approved.

### 4.5 Completed 008 Boundary (Reference)

`008-parse-quality-checker` remains a completed read-only checker. It must not be re-opened for implementation unless a new defect spec is explicitly approved.

---

## 5. Parser Output Contract

The active parsed artifact contract is:

`parsed/by_hash/{sha256[:2]}/{sha256[2:4]}/{sha256}/`

Standard files:

- `parsed_text.md`
- `parsed_metadata.json`
- `parse_manifest.json`

`parser_profile` and `parser_adapter_version` are metadata fields in `parse_manifest.json`.

They are not path segments.

---

## 6. Known Caveat from 007

007 MinerU PDF Parser Adapter has completed:

- mock subprocess validation
- real `ParseRegistryService.register_parse_report()` ingest validation
- CLI dry-run validation
- dependency-missing guard validation
- full pytest regression

But real `magic-pdf` / MinerU E2E was not completed because:

1. `magic-pdf` was not installed on PATH.
2. The available COPIED PDF database sample pointed to a stale `/tmp/p5_reqa_*` vault path.
3. There was no COPIED non-PDF live sample for CLI ROUTE_MISMATCH validation.

This caveat does not change the 007 implementation contract. 008 detects stale vault path and parsed/registry consistency issues in its JSON report; 009 may summarize those findings but must not fix them.

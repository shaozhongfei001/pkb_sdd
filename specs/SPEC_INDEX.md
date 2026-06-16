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
| 008 | `specs/008-parse-quality-checker/` | ACTIVE / PLANNED | Parse quality checker |

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
| `specs/008-review-workflow/` | FUTURE STUB / NOT CURRENT | Human review workflow. This is not the current 008 parse quality checker. |
| `specs/009-evidence-chain/` | FUTURE | Evidence chain |
| `specs/010-curated-project-assets/` | FUTURE | Curated assets / project cards |
| `specs/011-search-service/` | FUTURE | Search service |
| `specs/012-streamlit-admin/` | FUTURE | Streamlit admin UI |
| `specs/901-docker-compose-deployment/` | SUPPORT / FUTURE | Deployment support |
| `specs/902-test-dataset/` | SUPPORT / FUTURE | Test dataset support |

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

The current active/planned phase is:

`008 Parse Quality Checker`

Spec directory:

`specs/008-parse-quality-checker/`

Branch:

`feature/008-parse-quality-checker`

### 4.3 008 Boundary

`008-parse-quality-checker` is a read-only quality checking phase.

It may check:

- `raw_vault` original file existence
- `parsed_text.md` existence
- `parsed_metadata.json` existence
- `parse_manifest.json` existence
- manifest / registry consistency
- registry / parsed artifact consistency
- stale `vault_path`, especially `/tmp/...` paths
- `MISSING_MANIFEST`, `EMPTY`, `FAILED`, and skipped parse result aggregation
- parser name / parser adapter version validity

It must not:

- re-parse files
- call MarkItDown
- call MinerU / `magic-pdf`
- modify `raw_vault`
- modify `parsed`
- modify registry tables
- delete files
- move files
- rename files
- write curated assets
- write vectors / embeddings
- create project cards
- use LLM semantic judgment

Default output should be a report under `reports_root`, for example:

`parse_quality_report_{UTC}.json`

If a future design proposes DB writes, the workflow must STOP and enter DB Review first.

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

This caveat does not change the 007 implementation contract, but 008 should detect stale vault path and parsed/registry consistency issues.

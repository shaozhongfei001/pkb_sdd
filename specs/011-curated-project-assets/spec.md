# 011 Curated Project Assets — spec.md

> Project: `pkb_sdd`  
> Spec Directory: `specs/011-curated-project-assets/`  
> Branch: `feature/011-curated-project-assets`  
> Phase: `P1 Tech Lead Plan — COMPLETE (awaiting user review)`  
> Status: `ACTIVE SPEC / NOT IMPLEMENTED`  
> Authority: `specs/SPEC_INDEX.md`  
> Scope: Read evidence/chunk/document/registry metadata; write curated project assets + project/curated DB records (P4+).

---

## 1. Background

The completed SDD chain through 010 is:

```text
001-file-inventory
002-file-content-vault
003-duplicate-governance
004-parser-router
005-markitdown-parser
006-parse-job-registry
007-mineru-pdf-parser-adapter
008-parse-quality-checker
009-quality-report-summary
010-evidence-chain
```

010 produces `kb_document_chunk` and `kb_evidence` from **read-only** parsed artifacts and registry metadata.

011 introduces the **curated project assets layer**: deterministic, rule/template-based project knowledge files under `curated/projects/{project_code}/`, registered in MySQL with traceability to `evidence_uid`, `content_uid`, and `document_uid`.

The current active spec is:

```text
specs/011-curated-project-assets/
```

The following directories are **not** current implementation sources:

```text
specs/006-mineru-parser/           # deprecated stub
specs/007-quality-checker/         # deprecated stub
specs/008-review-workflow/         # future stub; NOT current 008 checker
specs/012-search-service/          # future; depends on curated/evidence stack
specs/013-streamlit-admin/         # future; UI layer
```

---

## 2. Problem Statement

Without curated project assets:

```text
1. Evidence rows exist but are not organized into project-level knowledge artifacts.
2. Search (012) and admin UI (013) lack stable curated content anchors.
3. Future review workflow lacks distilled/target objects to review.
4. Knowledge conclusions cannot be packaged as reusable project cards with evidence backlinks.
```

011 solves this by consuming **010 evidence + registry metadata** and writing **curated Markdown files + project/curated DB rows**, without LLM distillation, parsers, or review workflow.

---

## 3. Goals

### 3.1 Functional Goals (MVP — P4 target)

```text
G001 Read config (curated_root, mysql, pipeline_version).
G002 SELECT kb_document, kb_document_chunk, kb_evidence, kb_file_content, kb_parse_result (as needed).
G003 Upsert kb_project with stable project_uid from project_code.
G004 Upsert kb_project_document mappings (project ↔ document ↔ content).
G005 Generate curated/projects/{project_code}/ rule/template Markdown files (MVP subset).
G006 Register kb_curated_asset rows with curated_path and related_*_uids JSON.
G007 Every curated artifact must reference evidence_uid / content_uid / document_uid for traceability.
G008 CLI build-curated-project with --config, --project-code, --manifest, --content-uid, --limit, --dry-run, --force.
G009 Batch tolerate per-project / per-file failure; log and continue.
G010 Support Chinese project names, paths, and UTF-8 file content.
G011 Idempotent re-run: same input => no duplicate primary records without --force.
G012 Optional JSON build report (--output).
```

### 3.2 MVP Curated Files (P4 target)

Under `curated/projects/{project_code}/`:

| File | asset_type | Source |
|---|---|---|
| `00_project_card.md` | `project_card` | kb_project fields + document/evidence counts |
| `10_evidence_index.md` | `evidence_index` | kb_evidence + chunk locators |
| `source_documents.md` | `source_documents` | kb_document + registry path metadata |

MVP does **not** generate `01_background.md` … `06_lessons_learned.md` (future phase).

### 3.3 Safety Goals

```text
S001 Original user files remain read-only.
S002 raw_vault binary objects are not read (path metadata only if needed).
S003 parsed artifact files are read-only if accessed; never modified.
S004 No parser re-invocation (MarkItDown / MinerU / magic-pdf).
S005 No automatic repair of 008/009 quality findings.
S006 No LLM distillation or semantic summarization in MVP.
S007 Deterministic curated output for same input (except updated_at on --force).
S008 generation_method = TEMPLATE_RULE for MVP assets.
```

---

## 4. Non-goals

011 explicitly must not (MVP / P1 lock):

```text
NG001 LLM distillation, semantic summarization, or AI-generated requirements/solution text.
NG002 Vector DB / kb_embedding_ref writes.
NG003 Review workflow (kb_review_item / kb_manual_correction).
NG004 Reparse, repair, auto-fix, or cleanup of pytest dirty records.
NG005 Consumption of 008/009 reports to auto-skip/fix issues (optional future spec).
NG006 Read raw_vault original.bin for content extraction.
NG007 Call MarkItDown, MinerU, or magic-pdf.
NG008 Modify sealed 001/002 services or parse registry write behavior.
NG009 Move, delete, rename, or overwrite original user files.
NG010 Upload private documents to external cloud services.
NG011 MySQL FULLTEXT search service (012 scope).
NG012 Streamlit / FastAPI admin UI (013 scope).
NG013 Introduce schema migration in P4 without P2 DB Review approval.
NG014 Automatic project discovery via LLM or semantic clustering.
```

---

## 5. In-scope Data Sources

### 5.1 Read-only filesystem

```text
config/app.yaml
config/projects/*.yaml          # optional project manifest (P3 lock path)
curated_root                    # write target only (P4+)
```

Parsed files may be read **read-only** only when registry/evidence metadata is insufficient (P3 lock). Default MVP uses DB metadata from 010.

### 5.2 Read-only MySQL (SELECT)

Expected tables (P2 must verify ORM + schema):

```text
kb_file_content
kb_document
kb_parse_result
kb_document_chunk          # from 010
kb_evidence                # from 010
kb_project                 # may be empty pre-011
kb_project_document      # may be empty pre-011
```

**Do not read raw_vault binaries.**

### 5.3 Write MySQL (P4 — gated by P2 DB Review)

Expected tables (P2 must verify existence, columns, unique keys, ORM):

```text
kb_project
kb_project_document
kb_curated_asset
```

**P1 does not pre-judge migration necessity.** P2 must confirm init schema + ORM alignment. If insufficient → STOP at P2; migration spec required before P4.

### 5.4 Write filesystem (P4)

```text
{curated_root}/projects/{project_code}/00_project_card.md
{curated_root}/projects/{project_code}/10_evidence_index.md
{curated_root}/projects/{project_code}/source_documents.md
```

`curated/` stores **distilled project knowledge**, not original file copies.

---

## 6. Project Input Model (MVP)

MVP does **not** auto-discover projects via LLM. Primary input:

```text
CLI --project-code <code>
  + optional --manifest config/projects/{code}.yaml
  + optional --content-uid / document filters
```

Manifest minimum fields (P3 finalizes schema):

```yaml
project_code: DEMO-2024
project_name: 示例项目
description: 规则模板生成的项目卡片
documents:
  - content_uid: <sha256>
    document_uid: <uid>   # optional if inferable from registry
```

Fallback: existing `kb_project` / `kb_project_document` seed rows.

---

## 7. Curated Asset Contract (Planned)

### 7.1 kb_curated_asset fields (align with init SQL)

```text
curated_uid          # deterministic (P2 confirm formula)
project_uid
asset_type           # project_card | evidence_index | source_documents
asset_title
curated_path         # relative or absolute path under curated_root
related_content_uids JSON
related_document_uids JSON
related_evidence_uids JSON
generation_method    # TEMPLATE_RULE (MVP)
generation_status    # SUCCESS | SKIPPED | FAILED
version_no           # default 1; --force may bump updated_at only (P3 lock)
metadata JSON        # optional build stats
```

### 7.2 Traceability requirement

Each generated Markdown file must include a section listing:

```text
content_uid
document_uid
evidence_uid (where applicable)
source_sha256 (from evidence rows)
```

No knowledge statement in MVP curated files without at least one backing UID reference.

### 7.3 Idempotency keys (P2 must confirm against schema)

```text
project:     project_uid UNIQUE; project_code UNIQUE
mapping:     uk_project_document (project_uid, document_uid)
curated:     curated_uid UNIQUE
```

Proposed UID formulas (P2 must validate):

```text
project_uid  = SHA256("project:" + normalized_project_code)
curated_uid  = SHA256("curated:" + project_code + ":" + asset_type + ":" + str(version_no))
```

---

## 8. Relationship with 010

```text
010 evidence   ->  kb_document_chunk + kb_evidence
011 curated    ->  curated/*.md + kb_project* + kb_curated_asset
```

011 never replaces 010. It consumes 010 outputs. Re-running `build-evidence-chain` is out of 011 scope.

---

## 9. CLI Contract (Planned — P4)

Proposed command:

```bash
PYTHONPATH=backend python -m app.cli.main build-curated-project \
  --config config/app.yaml \
  --project-code DEMO-2024 \
  --manifest config/projects/DEMO-2024.yaml \
  --content-uid <uid> \
  --limit 100 \
  --dry-run \
  --force \
  --output /path/to/curated_build_report.json
```

Parameters (P3 final):

```text
--config
--project-code
--manifest
--content-uid
--document-uid
--limit
--dry-run
--force
--output
```

Forbidden parameters:

```text
--fix --repair --reparse --markitdown --mineru --magic-pdf
--llm --embed --search --streamlit --review
```

**Note:** CLI is P4. P1 creates specs only.

---

## 10. P2 DB Review Gate (Mandatory)

P2 must verify:

```text
kb_project table exists in sql/001_init_schema_v1_1.sql
kb_project_document table exists in sql/001_init_schema_v1_1.sql
kb_curated_asset table exists in sql/001_init_schema_v1_1.sql
ORM models exist or are planned with field-level mapping
Unique keys support idempotent insert/upsert
curated_root configured in config/app.yaml
No undocumented fields invented by Dev
If gap found -> migration script + DB Review before P4
```

P1 **does not** assert "no migration required."

If schema / ORM / unique keys are insufficient → **STOP**; P4 blocked.

---

## 11. Role Boundaries

| Role | 011 Responsibility |
|---|---|
| Tech Lead | P1 spec, P2/P3 gates, P7 final review |
| DB & Data | P2 schema/ORM/idempotency/curated_root review |
| Dev | P4 implementation within whitelist |
| QA | P5 tests + regression |
| E2E | P6 evidence → curated build validation |

---

## 12. P1 STOP Condition

P1 ends after:

```text
specs/011-curated-project-assets/spec.md
specs/011-curated-project-assets/plan.md
specs/011-curated-project-assets/tasks.md
specs/011-curated-project-assets/acceptance.md
specs/011-curated-project-assets/test_cases.md
specs/SPEC_INDEX.md aligned (011 ACTIVE / PLANNED)
README.md 011 active sync
docs/feature_index.md numbering drift fixed
```

After P1, STOP. No P2/P3/P4 until user approves.

No `backend/**` code in P1.

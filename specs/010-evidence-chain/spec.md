# 010 Evidence Chain — spec.md

> Project: `pkb_sdd`  
> Spec Directory: `specs/010-evidence-chain/`  
> Branch: `feature/010-evidence-chain`  
> Phase: `P1 Tech Lead Plan — COMPLETE (awaiting user review)`  
> Status: `ACTIVE SPEC / NOT IMPLEMENTED`  
> Authority: `specs/SPEC_INDEX.md`  
> Scope: Read parsed artifacts + registry/document metadata; build chunk/evidence DB records (P4+).

---

## 1. Background

The completed SDD chain through 009 is:

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
```

005/007 produce parsed artifacts under:

```text
parsed/by_hash/{sha256[:2]}/{sha256[2:4]}/{sha256}/
  parsed_text.md
  parsed_metadata.json
  parse_manifest.json
```

006 maintains `kb_document` and parse registry records for successful parses.

Downstream specs (011 curated, 012 search, 008-review-workflow) require **source-backed evidence** — locators such as page, slide, char offsets, heading path, quote text, and optional bbox.

010 introduces the **evidence foundation layer**: deterministic chunking from parsed text and evidence rows linked to content/document identity.

The current active spec is:

```text
specs/010-evidence-chain/
```

The following directories are **not** current implementation sources:

```text
specs/006-mineru-parser/           # deprecated stub
specs/007-quality-checker/         # deprecated stub
specs/008-review-workflow/         # future stub; NOT current 008 checker
specs/011-curated-project-assets/  # future; depends on 010
```

---

## 2. Problem Statement

Without evidence chain records:

```text
1. Parsed text exists but cannot be cited back to source positions.
2. Curated assets and search cannot reference stable evidence_uid values.
3. Human review lacks fine-grained locators beyond file-level content_uid.
4. Knowledge conclusions cannot satisfy "must trace to evidence" rule.
```

010 solves this by ingesting **read-only parsed artifacts** and writing **chunk + evidence metadata** to MySQL (P4+), without re-parsing or mutating originals.

---

## 3. Goals

### 3.1 Functional Goals (MVP — P4 target)

```text
G001 Read parsed_text.md / parsed_metadata.json / parse_manifest.json (read-only).
G002 Read kb_document + parse registry metadata (SELECT) for target content.
G003 Produce kb_document_chunk rows with stable chunk_uid and chunk_index.
G004 Produce kb_evidence rows with quote_text, source_location, offsets, page/slide when available.
G005 Link evidence to content_uid, document_uid, chunk_uid, source_sha256.
G006 Idempotent re-run: same input => no duplicate primary records.
G007 CLI build-evidence-chain with --config, --content-uid, --sha256, --limit filters.
G008 Batch tolerate per-file failure; log and continue.
G009 Support Chinese paths and UTF-8 parsed text.
G010 Optional manifest-driven bbox / page_no when parser metadata provides them.
```

### 3.2 Safety Goals

```text
S001 Original user files remain read-only.
S002 raw_vault binary objects are not read for chunking (path metadata only if needed).
S003 parsed artifact files are read-only; never modified.
S004 No parser re-invocation (MarkItDown / MinerU / magic-pdf).
S005 No automatic repair of 008/009 quality findings.
S006 No LLM-based chunking or summarization in MVP.
S007 Deterministic chunk/evidence output for same parsed input (except created_at if not upserted).
```

---

## 4. Non-goals

010 explicitly must not (MVP / P1 lock):

```text
NG001 LLM chunking, semantic splitting, or embedding generation.
NG002 Vector DB / kb_embedding_ref writes.
NG003 curated/ filesystem writes or project_card generation.
NG004 review workflow (kb_review_item / kb_manual_correction).
NG005 Reparse, repair, auto-fix, or cleanup of pytest dirty records.
NG006 Consumption of 008/009 reports to auto-skip/fix issues (optional future spec).
NG007 Read raw_vault original.bin for content extraction.
NG008 Call MarkItDown, MinerU, or magic-pdf.
NG009 Modify sealed 001/002 services or parse registry write behavior.
NG010 Move, delete, rename, or overwrite original user files.
NG011 Upload private documents to external cloud services.
NG012 Introduce schema migration in P4 without P2 DB Review approval.
```

---

## 5. In-scope Data Sources

### 5.1 Read-only filesystem

```text
config/app.yaml
parsed/by_hash/.../parsed_text.md
parsed/by_hash/.../parsed_metadata.json
parsed/by_hash/.../parse_manifest.json
```

### 5.2 Read-only MySQL (SELECT)

Expected tables (P2 must verify ORM + schema):

```text
kb_file_content
kb_document          # populated by 006 parse registry ingest
kb_parse_result
kb_parsed_artifact   # optional locator hints
```

Path fields on registry/document rows may be used to locate parsed files. **Do not read raw_vault binaries.**

### 5.3 Write MySQL (P4 — gated by P2 DB Review)

Expected tables (P2 must verify existence, columns, unique keys, ORM):

```text
kb_document_chunk
kb_evidence
```

**P1 does not pre-judge migration necessity.** P2 must confirm init schema + ORM alignment. If insufficient → STOP at P2; migration spec required before P4.

---

## 6. Chunk & Evidence Contract (Planned)

### 6.1 Chunk levels (MVP proposal — P3 may refine)

| chunk_level | Source | Notes |
|---|---|---|
| `document` | whole parsed_text.md | optional root chunk |
| `section` | markdown headings | primary MVP for MarkItDown |
| `page` | parsed_metadata page boundaries | when MinerU/PDF metadata exists |

### 6.2 Evidence fields (align with init SQL)

Minimum evidence row:

```text
evidence_uid
document_uid
content_uid
chunk_uid (nullable for document-level evidence)
source_sha256
quote_text
source_location
source_char_start / source_char_end
page_no / slide_no (nullable)
heading_path (nullable)
bbox JSON (nullable)
confidence (nullable)
metadata JSON (nullable)
```

Idempotency keys (P2 must confirm against schema):

```text
chunk: (document_uid, chunk_index) or chunk_uid
evidence: evidence_uid or (chunk_uid, evidence_type, source_char_start)
```

---

## 7. Relationship with 005/006/007

```text
005/007 parse  ->  parsed artifacts
006 registry   ->  kb_document + kb_parse_result
010 evidence   ->  kb_document_chunk + kb_evidence
```

010 never replaces parsers or registry. It consumes their outputs.

---

## 8. CLI Contract (Planned — P4)

Proposed command:

```bash
PYTHONPATH=backend python -m app.cli.main build-evidence-chain \
  --config config/app.yaml \
  --content-uid <uid> \
  --limit 100
```

Parameters (P3 final):

```text
--config
--content-uid
--sha256
--parser-name
--limit
--dry-run          # optional: plan only, no DB write
```

Forbidden parameters:

```text
--fix --repair --reparse --markitdown --mineru --magic-pdf
--write-curated --llm --embed
```

**Note:** CLI is P4. P1 creates specs only.

---

## 9. P2 DB Review Gate (Mandatory)

P2 must verify:

```text
kb_document_chunk table exists in sql/001_init_schema_v1_1.sql
kb_evidence table exists in sql/001_init_schema_v1_1.sql
ORM models exist or are planned with field-level mapping
Unique keys support idempotent insert/upsert
No undocumented fields invented by Dev
If gap found -> migration script + DB Review before P4
```

P1 **does not** assert "no migration required."

---

## 10. Role Boundaries

| Role | 010 Responsibility |
|---|---|
| Tech Lead | P1 spec, P2/P3 gates, P7 final review |
| DB & Data | P2 schema/ORM/idempotency review |
| Dev | P4 implementation within whitelist |
| QA | P5 tests + regression |
| E2E | P6 real parsed → evidence build |

---

## 11. P1 STOP Condition

P1 ends after:

```text
specs/010-evidence-chain/spec.md
specs/010-evidence-chain/plan.md
specs/010-evidence-chain/tasks.md
specs/010-evidence-chain/acceptance.md
specs/010-evidence-chain/test_cases.md
specs/SPEC_INDEX.md aligned (010 ACTIVE / PLANNED)
README.md drift fixed (009 DONE, 010 active)
```

After P1, STOP. No P2/P3/P4 until user approves.

No `backend/**` code in P1.

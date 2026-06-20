# 012 Search Service — spec.md

> Project: `pkb_sdd`  
> Spec Directory: `specs/012-search-service/`  
> Branch: `feature/012-search-service`  
> Phase: `P1 Tech Lead Plan — COMPLETE (awaiting user review)`  
> Status: `ACTIVE SPEC / NOT IMPLEMENTED`  
> Authority: `specs/SPEC_INDEX.md`  
> Scope: Read-only MySQL FULLTEXT search over evidence/chunk/document/project/curated metadata (P4+).

---

## 1. Background

The completed SDD chain through 011 is:

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
011-curated-project-assets
```

010 produces `kb_document_chunk` and `kb_evidence` with searchable text in MySQL.

011 produces `kb_project`, `kb_project_document`, and `kb_curated_asset` with project-level curated anchors.

012 introduces the **search service layer**: unified keyword retrieval over existing MySQL FULLTEXT indexes, returning traceable `evidence_uid` / `document_uid` / `content_uid` hits for CLI and optional FastAPI consumers.

The current active spec is:

```text
specs/012-search-service/
```

The following directories are **not** current implementation sources:

```text
specs/006-mineru-parser/           # deprecated stub
specs/007-quality-checker/         # deprecated stub
specs/008-review-workflow/         # future stub; NOT current 008 checker
specs/013-streamlit-admin/         # future; UI layer depends on 012 contract
```

---

## 2. Problem Statement

Without a search service:

```text
1. Evidence and curated assets exist in MySQL but cannot be discovered by keyword.
2. Admin UI (013) lacks a stable query API instead of ad-hoc SQL in the UI layer.
3. Users cannot navigate from a search hit back to evidence_uid / document identity.
4. Knowledge conclusions cannot be explored through the existing DB text indexes built by 010/011.
```

012 solves this by providing **read-only MySQL FULLTEXT search** over documented tables, without embeddings, parsers, raw_vault reads, or parsed file reads.

---

## 3. Goals

### 3.1 Functional Goals (MVP — P4 target)

```text
G001 Read config (mysql, pipeline_version; no new required config keys unless P2 approves).
G002 SELECT-only search over MySQL FULLTEXT indexes (ngram parser).
G003 Support search scopes (MVP):
     - document   -> kb_document.title (ftx_document_title)
     - chunk      -> kb_document_chunk.content (ftx_chunk_content)
     - evidence   -> kb_evidence.quote_text / normalized_text (ftx_evidence_text)
     - project    -> kb_project.project_name / description (ftx_project_name_desc)
     - curated    -> kb_curated_asset.asset_title (ftx_curated_asset_title)
     - all        -> union of MVP scopes above
G004 Unified SearchHit DTO:
     hit_type, matched_field, snippet, relevance_score,
     evidence_uid, document_uid, content_uid, chunk_uid (nullable),
     project_uid (nullable), project_code (nullable), curated_uid (nullable)
G005 CLI search-kb:
     --config, --query, --scope, --project-code, --limit, --offset, --format json|table
G006 Optional FastAPI GET /api/v1/search sharing SearchService (P4; P3 locks if MVP).
G007 Chinese query strings and Chinese indexed content (UTF-8).
G008 Empty query rejected with clear error; no SQL executed with blank query.
G009 No hits => empty result set with zero total; not an error.
G010 SQL / connection errors logged with context; CLI returns non-zero exit where appropriate.
G011 Read-only MVP: no INSERT/UPDATE/DELETE (P2 must confirm).
G012 Every evidence/chunk hit must include document_uid and content_uid for traceability.
G013 Optional --project-code filter via kb_project_document join (not via kb_evidence.project_uid backfill).
G014 Optional --content-uid / --document-uid filters (P3 lock exact CLI flags).
G015 001–010 regression unaffected; 011 curated rows readable as search targets.
```

### 3.2 MVP Search Scopes

| scope | Table | FULLTEXT index (init SQL) | Primary UIDs returned |
|---|---|---|---|
| `document` | `kb_document` | `ftx_document_title` | `document_uid`, `content_uid` |
| `chunk` | `kb_document_chunk` | `ftx_chunk_content` | `chunk_uid`, `document_uid`, `content_uid` |
| `evidence` | `kb_evidence` | `ftx_evidence_text` | `evidence_uid`, `document_uid`, `content_uid`, `chunk_uid` |
| `project` | `kb_project` | `ftx_project_name_desc` | `project_uid`, `project_code` |
| `curated` | `kb_curated_asset` | `ftx_curated_asset_title` | `curated_uid`, `project_uid` |
| `all` | union of above | per-row scope tag | per hit_type |

MVP does **not** search `kb_file_instance.file_name` FULLTEXT (future phase).

### 3.3 Safety Goals

```text
S001 Original user files remain read-only.
S002 raw_vault binary objects are not read.
S003 parsed artifact files are not read (search uses 010 DB text).
S004 No parser re-invocation (MarkItDown / MinerU / magic-pdf).
S005 No automatic repair of 008/009 quality findings.
S006 No LLM query expansion, semantic rerank, or embedding generation.
S007 Deterministic ranking for same query + same DB snapshot (MySQL FULLTEXT score).
S008 No writes to kb_review_item, kb_embedding_ref, parse registry, chunk/evidence, or curated tables.
```

---

## 4. Non-goals

012 explicitly must not (MVP / P1 lock):

```text
NG001 Vector DB / embedding generation / kb_embedding_ref writes.
NG002 Semantic similarity search or LLM reranking.
NG003 Review workflow (kb_review_item / kb_manual_correction).
NG004 Reparse, repair, auto-fix, or cleanup of pytest dirty records.
NG005 Consumption of 008/009 reports to auto-skip/filter issues.
NG006 Read raw_vault original.bin for content extraction.
NG007 Read parsed_text.md / parsed_metadata.json / parse_manifest.json.
NG008 Call MarkItDown, MinerU, or magic-pdf.
NG009 Modify sealed 001/002 services or parse registry write behavior.
NG010 Move, delete, rename, or overwrite original user files.
NG011 Write curated Markdown files or mutate curated/ runtime tree.
NG012 Streamlit admin UI (013 scope).
NG013 Introduce schema migration in P4 without P2 DB Review approval.
NG014 Automatic query understanding via LLM.
NG015 Search audit / kb_search_log table writes in MVP (defer to future spec unless P2 mandates).
```

---

## 5. In-scope Data Sources

### 5.1 Read-only filesystem

```text
config/app.yaml
```

No `raw_vault/`, `parsed/`, or `curated/` filesystem reads in MVP.

### 5.2 Read-only MySQL (SELECT)

Expected tables (P2 must verify ORM + FULLTEXT indexes):

```text
kb_document
kb_document_chunk
kb_evidence
kb_project
kb_project_document        # for --project-code filter joins
kb_curated_asset
```

Optional read for enrichment (SELECT only, P3 lock):

```text
kb_file_content            # sha256 / size metadata in hit payload
kb_parse_result            # parser_profile in document hits
```

**Do not read raw_vault binaries.**

### 5.3 Write MySQL (MVP default)

```text
None — SELECT-only MVP.
```

If P2 identifies mandatory audit logging requiring new tables → STOP at P2; migration spec required before P4.

### 5.4 Write filesystem (MVP)

```text
None.
Optional CLI --output JSON file is operator-provided path (search results only).
```

---

## 6. Project Filter Model (MVP)

011 MVP does **not** backfill `kb_evidence.project_uid` (011 C8).

Therefore `--project-code` filtering must use:

```text
kb_project.project_code
  -> kb_project.project_uid
  -> kb_project_document (project_uid, document_uid)
  -> restrict document/chunk/evidence hits to mapped document_uid set
```

For `scope=project`, filter is inherent.

For `scope=curated`, filter via `kb_curated_asset.project_uid`.

P2 must validate JOIN strategy and index use.

---

## 7. Search Result Contract (Planned)

### 7.1 SearchHit fields (P3 finalizes)

```text
hit_type            # document | chunk | evidence | project | curated
matched_field       # e.g. title | content | quote_text | project_name | asset_title
snippet             # short excerpt around match (server-side truncation)
relevance_score     # MySQL FULLTEXT relevance (P2 confirm column alias)
document_uid        # nullable for project-only hits
content_uid         # nullable for project-only hits
chunk_uid           # nullable
evidence_uid        # nullable
project_uid         # nullable
project_code        # nullable
curated_uid         # nullable
metadata            # optional JSON: page_no, heading_path, asset_type, parser_profile
```

### 7.2 Traceability requirement

Hits from `chunk` or `evidence` scopes must include `document_uid` and `content_uid`.

Hits from `evidence` scope must include `evidence_uid`.

No fabricated UIDs; only DB-backed values.

### 7.3 Pagination

```text
--limit   default 20, max 100 (P3 lock)
--offset  default 0
Response includes total_count or has_more (P3 lock exact shape)
```

---

## 8. Relationship with 010 / 011

```text
010 evidence   ->  searchable chunk/evidence text in MySQL
011 curated    ->  searchable project/curated metadata in MySQL
012 search     ->  read-only FULLTEXT queries; no rebuild of 010/011 data
```

012 never replaces 010 or 011. Re-running `build-evidence-chain` or `build-curated-project` is out of 012 scope.

---

## 9. CLI Contract (Planned — P4)

Proposed command:

```bash
PYTHONPATH=backend python -m app.cli.main search-kb \
  --config config/app.yaml \
  --query "银行 信贷" \
  --scope all \
  --project-code DEMO-2024 \
  --content-uid <uid> \
  --document-uid <uid> \
  --limit 20 \
  --offset 0 \
  --format json \
  --output /path/to/search_results.json
```

Parameters (P3 final):

```text
--config
--query            # required; non-empty
--scope            # all | document | chunk | evidence | project | curated
--project-code
--content-uid
--document-uid
--limit
--offset
--format           # json | table
--output           # optional JSON file path
```

Forbidden parameters:

```text
--fix --repair --reparse --markitdown --mineru --magic-pdf
--llm --embed --semantic --streamlit --review --vector
```

**Note:** CLI is P4. P1 creates specs only.

---

## 10. API Contract (Optional MVP — P3 lock)

Proposed endpoint (shares `SearchService` with CLI):

```text
GET /api/v1/search?q=<query>&scope=all&project_code=&limit=20&offset=0
```

Response: JSON array of SearchHit + pagination meta.

If FastAPI route is deferred, CLI-only MVP is acceptable (P3 gate documents decision).

---

## 11. P2 DB Review Gate (Mandatory)

P2 must verify:

```text
FULLTEXT indexes exist in sql/001_init_schema_v1_1.sql for MVP scopes
ngram parser behavior for Chinese queries (MATCH ... AGAINST syntax)
ORM models exist for all queried tables (document, evidence, project, curated)
--project-code filter JOIN path without kb_evidence.project_uid backfill
No undocumented fields invented by Dev
SELECT-only MVP — confirm zero DML
If audit table or new index required -> migration script + STOP before P4
```

P1 **does not** assert "no migration required."

If schema / ORM / FULLTEXT coverage insufficient → **STOP**; P4 blocked.

---

## 12. Role Boundaries

| Role | 012 Responsibility |
|---|---|
| Tech Lead | P1 spec, P2/P3 gates, P7 final review |
| DB & Data | P2 FULLTEXT/ORM/read-only scope review |
| Dev | P4 implementation within whitelist |
| QA | P5 tests + regression |
| E2E | P6 real MySQL search validation |

---

## 13. P1 STOP Condition

P1 ends after:

```text
specs/012-search-service/spec.md
specs/012-search-service/plan.md
specs/012-search-service/tasks.md
specs/012-search-service/acceptance.md
specs/012-search-service/test_cases.md
specs/SPEC_INDEX.md aligned (012 ACTIVE / NOT IMPLEMENTED)
README.md 012 active sync
docs/feature_index.md 012 ACTIVE sync
```

After P1, STOP. No P2/P3/P4 until user approves.

No `backend/**` code in P1.

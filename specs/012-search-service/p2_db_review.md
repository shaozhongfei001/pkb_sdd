# 012 Search Service — P2 DB & Data Review

> Role: Tech Lead Agent + DB & Data Review  
> Spec: `specs/012-search-service/`  
> Branch: `feature/012-search-service` (not created yet — create on P3/P4 entry)  
> Stage: P2 DB & Data Read Review  
> Base commit: local `f698e26` (clean working tree at P2 start)  
> Remote: **SSH verification unavailable / pending external confirmation** (`git ls-remote origin refs/heads/main` failed — Host key verification failed)

---

## 1. Gate Conclusion

**P2-GATE: PASS WITH CONSTRAINTS**

012 Search Service may enter **P3 Implementation Gate** after user confirmation.

Constraints (locked for P3/P4):

```text
C1  No schema migration required for MVP — reuse init SQL FULLTEXT indexes as-is.
C2  No new ORM models required for MVP — all six queried tables already mapped.
C3  MVP is SELECT-only — zero INSERT/UPDATE/DELETE on any MySQL table.
C4  No kb_search_log / audit table in MVP — defer to future spec if needed.
C5  Primary search mechanism: MATCH ... AGAINST with ngram FULLTEXT indexes (NATURAL LANGUAGE MODE default).
C6  LIKE fallback NOT required for MVP — only consider if P6 E2E documents FULLTEXT miss on real data.
C7  --project-code filter MUST use kb_project.project_code → kb_project_document JOIN — NOT kb_evidence.project_uid.
C8  kb_evidence.project_uid is nullable and NOT backfilled by 011 MVP (011 C8) — do not use for project scoping.
C9  scope=all: execute per-scope FULLTEXT queries, tag hit_type, merge-sort by relevance_score DESC (P3 lock pagination/total_count).
C10 ngram_token_size default 2 — single-character Chinese queries may return no hits; document in P6, not auto-LIKE.
C11 Nullable indexed columns (title, quote_text, asset_title) — NULL rows excluded from FULLTEXT matches.
C12 Optional enrichment JOIN kb_document for parser_profile/title on chunk/evidence hits — SELECT only.
C13 Optional enrichment KbFileContent / KbParseResult — SELECT only if P3 locks; not required for MVP hits.
C14 Do not read raw_vault, parsed filesystem, curated filesystem, or kb_file_instance.file_name scope in MVP.
C15 Do not write kb_review_item, kb_manual_correction, kb_embedding_ref, chunk/evidence, project/curated, or parse registry.
C16 MySQL 8.0+ required (per init SQL header); ngram FULLTEXT must be validated in P6 on target instance.
C17 Do not modify init SQL, migrations, or existing ORM model files in P4 (read-only use only).
```

**Migration:** NOT required for MVP.

**P4 DB access:** APPROVED **SELECT only** on documented tables (after P3 whitelist).

**P4 filesystem access:** APPROVED only for operator `--output` JSON path (not DB, not curated/raw_vault/parsed reads).

---

## 2. Mandatory Questionnaire

| # | Question | Answer |
|---|----------|--------|
| 1 | Init schema supports 012 MVP? | **YES** — all MVP tables + FULLTEXT indexes exist |
| 2 | Fields / keys / logical links sufficient? | **YES WITH CONSTRAINTS** — see §3–§5 |
| 3 | FULLTEXT indexes exist for MVP scopes? | **YES** — six indexes on five MVP tables (see §4) |
| 4 | Migration required for MVP? | **NO** — indexes present in `sql/001_init_schema_v1_1.sql` |
| 5 | Chinese ngram FULLTEXT viable? | **YES WITH CONSTRAINTS** — MySQL 8.0+ ngram parser; P6 must confirm on live instance (§6) |
| 6 | MATCH ... AGAINST suitable for MVP? | **YES** — primary path; LIKE not required for MVP (§7) |
| 7 | scope mapping clear? | **YES** — see §8 |
| 8 | --project-code via kb_project_document? | **YES** — required; not via evidence.project_uid (§9) |
| 9 | MVP SELECT-only? | **YES** — no DB writes, no runtime asset dirs (§10) |
| 10 | New ORM needed? | **NO** for MVP — all models exist (§11) |
| 11 | raw_vault / parsed / parser / embed / review / UI creep? | **NONE in design** — denylist enforced (§12) |
| 12 | P4 file whitelist preview? | **YES** — see §13 |

---

## 3. Schema Verification — MVP Tables

Source: `sql/001_init_schema_v1_1.sql` (MySQL 8.0+, `utf8mb4` / `utf8mb4_0900_ai_ci`).

No formal FOREIGN KEY constraints — relationships are logical via `*_uid` columns and JOINs.

### 3.1 `kb_document` (scope: `document`)

| Column | Type | Search / hit use |
|--------|------|----------------|
| `document_uid` | VARCHAR(64) UNIQUE | Hit identity |
| `content_uid` | VARCHAR(64) | Hit identity |
| `title` | VARCHAR(1024) NULL | FULLTEXT indexed; snippet source |
| `parser_profile` | VARCHAR(128) | Optional metadata enrichment |
| `parser_name` / `parser_version` | VARCHAR | Optional metadata enrichment |
| `parse_status` | VARCHAR(64) | Optional filter (P3 lock — not required MVP) |

Indexes: `idx_content_uid`, `uk_document_profile (content_uid, parser_profile, pipeline_version)`.

**FULLTEXT:** `ftx_document_title (title) WITH PARSER ngram` — L192.

**Gap:** `title` nullable — documents without title will not FULLTEXT-match on document scope.

### 3.2 `kb_document_chunk` (scope: `chunk`)

| Column | Type | Search / hit use |
|--------|------|----------------|
| `chunk_uid` | VARCHAR(64) UNIQUE | Hit identity |
| `document_uid` | VARCHAR(64) | Hit identity; project filter JOIN key |
| `content_uid` | VARCHAR(64) | Hit identity |
| `content` | MEDIUMTEXT NOT NULL | FULLTEXT indexed; snippet source |
| `page_no` | INT NULL | metadata |
| `heading_path` | TEXT | metadata |
| `chunk_index` | INT | sort tie-breaker (P3) |

Indexes: `idx_document_uid`, `idx_content_uid`, FULLTEXT on `content`.

**FULLTEXT:** `ftx_chunk_content (content) WITH PARSER ngram` — L222.

**ORM note:** `KbDocumentChunk.content` mapped as SQLAlchemy `Text` — acceptable; 010 already inserts chunk rows.

### 3.3 `kb_evidence` (scope: `evidence`)

| Column | Type | Search / hit use |
|--------|------|----------------|
| `evidence_uid` | VARCHAR(64) UNIQUE | Hit identity |
| `document_uid` | VARCHAR(64) | Hit identity; project filter JOIN key |
| `content_uid` | VARCHAR(64) | Hit identity |
| `chunk_uid` | VARCHAR(64) NULL | Hit metadata |
| `project_uid` | VARCHAR(64) NULL | **Do NOT use for MVP project filter** (011 C8) |
| `quote_text` | MEDIUMTEXT NULL | FULLTEXT indexed |
| `normalized_text` | MEDIUMTEXT NULL | FULLTEXT indexed |
| `page_no` / `heading_path` | various | metadata |

Indexes: `idx_document_uid`, `idx_content_uid`, `idx_project_uid` (unused for filter), FULLTEXT on `(quote_text, normalized_text)`.

**FULLTEXT:** `ftx_evidence_text (quote_text, normalized_text) WITH PARSER ngram` — L253.

### 3.4 `kb_project` (scope: `project`)

| Column | Type | Search / hit use |
|--------|------|----------------|
| `project_uid` | VARCHAR(64) UNIQUE | Hit identity |
| `project_code` | VARCHAR(128) UNIQUE | CLI `--project-code` resolution |
| `project_name` | VARCHAR(512) NOT NULL | FULLTEXT indexed |
| `description` | TEXT NULL | FULLTEXT indexed |

Indexes: `idx_project_code`, FULLTEXT on `(project_name, description)`.

**FULLTEXT:** `ftx_project_name_desc (project_name, description) WITH PARSER ngram` — L318.

### 3.5 `kb_project_document` (project filter bridge — not a search scope table)

| Column | Type | Filter use |
|--------|------|------------|
| `project_uid` | VARCHAR(64) | Join to `kb_project` |
| `document_uid` | VARCHAR(64) | Restrict document/chunk/evidence hits |
| `content_uid` | VARCHAR(64) | Optional direct filter |

Unique: `uk_project_document (project_uid, document_uid)` — L335.

Indexes: `idx_project_uid`, `idx_document_uid`, `idx_content_uid`.

**Role:** Bridge for `--project-code` on `document` / `chunk` / `evidence` scopes without `kb_evidence.project_uid`.

### 3.6 `kb_curated_asset` (scope: `curated`)

| Column | Type | Search / hit use |
|--------|------|----------------|
| `curated_uid` | VARCHAR(64) UNIQUE | Hit identity |
| `project_uid` | VARCHAR(64) NULL | Hit metadata; project filter for curated scope |
| `asset_type` | VARCHAR(64) | metadata |
| `asset_title` | VARCHAR(1024) NULL | FULLTEXT indexed; snippet source |
| `curated_path` | TEXT | metadata (DB path only — no filesystem read in MVP) |
| `related_*_uids` | JSON | optional display (P3) |

Indexes: `idx_project_uid`, `idx_asset_type`, FULLTEXT on `asset_title`.

**FULLTEXT:** `ftx_curated_asset_title (asset_title) WITH PARSER ngram` — L360.

### 3.7 Out of MVP scope (indexed but excluded)

| Table | FULLTEXT | Notes |
|-------|----------|-------|
| `kb_file_instance` | `ftx_file_name (file_name)` | P1 NG — file inventory scope; future spec |

### 3.8 Migration assessment

```text
All MVP FULLTEXT indexes exist in init SQL.
No kb_search_log or search-specific tables in schema.
SELECT-only MVP => no new UNIQUE/idempotency keys needed.
=> Migration NOT required for 012 MVP.
```

If P4 proposes search audit logging or new indexes → STOP → separate migration spec.

---

## 4. FULLTEXT Index Inventory (MVP)

| scope | Table | Index name | Columns | Parser |
|-------|-------|------------|---------|--------|
| `document` | `kb_document` | `ftx_document_title` | `title` | ngram |
| `chunk` | `kb_document_chunk` | `ftx_chunk_content` | `content` | ngram |
| `evidence` | `kb_evidence` | `ftx_evidence_text` | `quote_text`, `normalized_text` | ngram |
| `project` | `kb_project` | `ftx_project_name_desc` | `project_name`, `description` | ngram |
| `curated` | `kb_curated_asset` | `ftx_curated_asset_title` | `asset_title` | ngram |

All use `WITH PARSER ngram` — appropriate for Chinese + mixed UTF-8 content.

---

## 5. Logical Relationship Map

```text
kb_file_content.content_uid
    └── kb_document.content_uid
            ├── kb_document_chunk.document_uid
            ├── kb_evidence.document_uid
            └── kb_project_document.document_uid
                    └── kb_project.project_uid / project_code

kb_project.project_uid
    ├── kb_project_document.project_uid
    └── kb_curated_asset.project_uid

kb_document_chunk.chunk_uid ──optional── kb_evidence.chunk_uid
```

**Sufficient for MVP** — no missing join keys for search hits or project filter.

---

## 6. Chinese ngram FULLTEXT Constraints

### 6.1 Platform requirements

| Item | Requirement | Source |
|------|-------------|--------|
| MySQL version | **8.0+** | `sql/001_init_schema_v1_1.sql` L4 |
| Charset | `utf8mb4` | init SQL |
| FULLTEXT parser | `ngram` on all MVP indexes | init SQL |

### 6.2 Server variables (operational — P6 must verify on target instance)

| Variable | Relevance to 012 |
|----------|------------------|
| `ngram_token_size` | Default **2** for InnoDB ngram FULLTEXT. Chinese text tokenized as 2-character grams. **Single-character queries may not match.** |
| `innodb_ft_min_token_size` | Applies to **built-in** parser, **not** ngram parser — do not use as ngram tuning knob. |
| `innodb_ft_enable_stopword` | ngram parser uses its own stopword handling — P6 note if unexpected misses. |

P2 cannot execute `SHOW VARIABLES` in this review environment — **P6 E2E must record** `ngram_token_size` and sample Chinese hit tests.

### 6.3 Query mode recommendation (P3 lock)

```sql
MATCH(col) AGAINST(:query IN NATURAL LANGUAGE MODE)
```

Optional future: `IN BOOLEAN MODE` for explicit `+token` queries — not required MVP.

Relevance score:

```sql
MATCH(col) AGAINST(:query IN NATURAL LANGUAGE MODE) AS relevance_score
```

Use MySQL-computed relevance for ordering; cross-table scores are comparable enough for MVP merge-sort (not normalized across scopes — acceptable for MVP per C9).

---

## 7. MATCH ... AGAINST vs LIKE Fallback

| Approach | MVP verdict |
|----------|-------------|
| `MATCH ... AGAINST` (ngram) | **PRIMARY** — aligned with init schema and README design |
| `LIKE '%query%'` on MEDIUMTEXT | **NOT required MVP** — full table scan risk; poor scale; bypasses FULLTEXT indexes |
| Hybrid fallback | **DEFER** — only if P6 documents systematic FULLTEXT miss on real Chinese samples |

**P3/P4 rule:** Implement FULLTEXT path first. If P6 finds gaps (e.g. single-char query), document as known limitation or add explicit `--mode boolean` in future — not silent LIKE fallback on large tables.

Empty query: reject before SQL (spec G008) — prevents accidental `LIKE '%%'` or invalid MATCH.

---

## 8. Scope → Data Source Mapping

| scope | Primary table | FULLTEXT index | Hit UIDs (required) | Snippet field |
|-------|---------------|----------------|---------------------|---------------|
| `document` | `kb_document` | `ftx_document_title` | `document_uid`, `content_uid` | `title` |
| `chunk` | `kb_document_chunk` | `ftx_chunk_content` | `chunk_uid`, `document_uid`, `content_uid` | truncated `content` |
| `evidence` | `kb_evidence` | `ftx_evidence_text` | `evidence_uid`, `document_uid`, `content_uid`, `chunk_uid` if present | `quote_text` or `normalized_text` |
| `project` | `kb_project` | `ftx_project_name_desc` | `project_uid`, `project_code` | `project_name` / `description` |
| `curated` | `kb_curated_asset` | `ftx_curated_asset_title` | `curated_uid`, `project_uid` | `asset_title` |
| `all` | union of above | per-row | per `hit_type` | per scope |

**`scope=all` implementation note (P3 lock):**

```text
1. Run per-scope SELECT with MATCH ... AGAINST (optionally parallel).
2. Tag each row with hit_type.
3. Merge all hits; sort by relevance_score DESC.
4. Apply global limit/offset on merged list.
5. total_count = sum of per-scope counts OR count merged pre-pagination (P3 pick one — both SELECT-only).
```

Do not use one SQL UNION across heterogeneous FULLTEXT column sets without careful column alignment — per-scope queries are clearer and safer for MVP.

---

## 9. `--project-code` Filter Strategy

### 9.1 Required path (MVP)

```text
--project-code <code>
  → SELECT project_uid FROM kb_project WHERE project_code = :code
  → IF NOT FOUND: empty results or explicit error (P3 lock)
  → allowed_document_uids FROM kb_project_document WHERE project_uid = :project_uid
```

Apply restriction:

| scope | Filter SQL pattern |
|-------|-------------------|
| `document` | `kb_document.document_uid IN (:allowed_document_uids)` OR JOIN `kb_project_document` |
| `chunk` | `kb_document_chunk.document_uid IN (...)` |
| `evidence` | `kb_evidence.document_uid IN (...)` |
| `project` | `kb_project.project_code = :code` directly |
| `curated` | `kb_curated_asset.project_uid = :project_uid` |

### 9.2 Forbidden path

```text
kb_evidence.project_uid = :project_uid   -- DO NOT USE (nullable, not backfilled in 011 MVP)
```

Evidence: 011 P2 constraint C8; 011 runtime does not backfill `kb_evidence.project_uid`.

### 9.3 Index use

`kb_project.idx_project_code` + `kb_project_document.idx_project_uid` / `idx_document_uid` support efficient filter — no migration needed.

---

## 10. SELECT-only MVP & Runtime Filesystem

### 10.1 DB write denylist (MVP — absolute)

```text
kb_document_chunk
kb_evidence
kb_document
kb_project
kb_project_document
kb_curated_asset
kb_parse_job / kb_parse_result / kb_parsed_artifact / kb_parse_run
kb_file_instance / kb_file_content
kb_raw_vault_object
kb_duplicate_group
kb_review_item
kb_manual_correction
kb_embedding_ref
kb_task_log
kb_schema_version
```

No `INSERT`, `UPDATE`, `DELETE`, `REPLACE`, or DDL from 012 service.

### 10.2 Filesystem denylist (MVP)

```text
raw_vault/**           — no read of original.bin or vault tree for search text
parsed/**              — no read of parsed_text.md / metadata / manifest
curated/**             — search curated scope uses kb_curated_asset.asset_title in DB only
source_registry/**     — not in MVP scope
```

**Allowed filesystem write:** operator-provided `--output` JSON path only (search results export).

### 10.3 Config read

```text
config/app.yaml — mysql connection block (required)
pipeline_version — optional logging only
```

No new config keys required for MVP. `curated_root`, `parsed_root`, `raw_vault_root` are **not** read by search MVP.

---

## 11. ORM Status

| Model | File | Status | 012 role |
|-------|------|--------|----------|
| `KbDocument` | `document.py` | **Exists** | Read / FULLTEXT document scope |
| `KbDocumentChunk` | `evidence.py` | **Exists** | Read / FULLTEXT chunk scope |
| `KbEvidence` | `evidence.py` | **Exists** | Read / FULLTEXT evidence scope |
| `KbProject` | `project.py` | **Exists** (011) | Read / FULLTEXT project scope + code resolution |
| `KbProjectDocument` | `project.py` | **Exists** (011) | Read / project filter JOIN |
| `KbCuratedAsset` | `project.py` | **Exists** (011) | Read / FULLTEXT curated scope |

Optional enrichment (SELECT only — P3 lock):

| Model | File | Use |
|-------|------|-----|
| `KbFileContent` | `file.py` | sha256 / vault_status in hit metadata |
| `KbParseResult` | `parse_registry.py` | only if join path needed beyond `kb_document` |

**New ORM models:** **NOT required** for MVP.

**P4 must NOT modify:**

```text
backend/app/models/document.py
backend/app/models/evidence.py
backend/app/models/project.py
backend/app/models/file.py
backend/app/models/parse_registry.py
backend/app/models/vault.py
backend/app/models/duplicate.py
sql/**
```

---

## 12. Boundary / Creep Review

| Risk area | 012 MVP | Verdict |
|-----------|---------|---------|
| raw_vault `original.bin` read | Forbidden | **NO creep** |
| parsed filesystem read | Forbidden | **NO creep** |
| Parser invocation | Forbidden | **NO creep** |
| LLM query expansion | Forbidden | **NO creep** |
| embedding / vector / `kb_embedding_ref` | Forbidden | **NO creep** |
| `kb_review_item` / review workflow | Forbidden | **NO creep** |
| Streamlit / admin UI | 013 scope | **NO creep** |
| Curated file generation | 011 scope | **NO creep** |
| Evidence/chunk rebuild | 010 scope | **NO creep** |
| `kb_file_instance` filename search | Future spec | **Deferred** — index exists but out of MVP |

---

## 13. P4 File Whitelist Preview (P3 must finalize)

### 13.1 Allowed (anticipated)

```text
backend/app/services/search_service.py       # NEW
backend/app/schemas/search.py                # NEW — SearchHit, SearchResponse (if API MVP)
backend/app/api/routes/search.py             # NEW — only if P3 locks FastAPI MVP
backend/app/main.py or api router entry      # register route — if API MVP
backend/app/cli/main.py                      # register search-kb
backend/tests/test_search_service.py         # NEW
backend/tests/fixtures/search/               # synthetic DB seed data
```

### 13.2 Forbidden

```text
backend/app/services/inventory_scanner.py
backend/app/services/file_content_vault.py
backend/app/services/evidence_chain.py
backend/app/services/curated_project_assets.py
backend/app/services/markitdown_parser.py
backend/app/services/mineru_pdf_parser.py
backend/app/services/parse_registry.py
backend/app/services/parse_quality_checker.py
backend/app/services/parse_quality_report_summarizer.py
backend/app/models/**                      # read-only — no edits
sql/**
migrations/**
streamlit/**
raw_vault/**
parsed/**
curated/**                                 # no runtime reads/writes
```

---

## 14. Illustrative SQL (P3 reference — not implemented in P2)

### 14.1 Evidence scope with project filter

```sql
SELECT
  e.evidence_uid,
  e.document_uid,
  e.content_uid,
  e.chunk_uid,
  e.quote_text,
  MATCH(e.quote_text, e.normalized_text) AGAINST (:q IN NATURAL LANGUAGE MODE) AS relevance_score
FROM kb_evidence e
INNER JOIN kb_project_document pd ON pd.document_uid = e.document_uid
INNER JOIN kb_project p ON p.project_uid = pd.project_uid
WHERE p.project_code = :project_code
  AND MATCH(e.quote_text, e.normalized_text) AGAINST (:q IN NATURAL LANGUAGE MODE)
ORDER BY relevance_score DESC
LIMIT :limit OFFSET :offset;
```

### 14.2 Chunk scope (no project filter)

```sql
SELECT
  c.chunk_uid,
  c.document_uid,
  c.content_uid,
  c.content,
  c.page_no,
  MATCH(c.content) AGAINST (:q IN NATURAL LANGUAGE MODE) AS relevance_score
FROM kb_document_chunk c
WHERE MATCH(c.content) AGAINST (:q IN NATURAL LANGUAGE MODE)
ORDER BY relevance_score DESC
LIMIT :limit OFFSET :offset;
```

P4 may use SQLAlchemy `text()` or dialect-specific constructs — P3 locks approach.

---

## 15. P2 Checklist

```text
[x] MVP tables exist in init SQL
[x] FULLTEXT indexes documented per scope
[x] Field / UID traceability sufficient
[x] Migration need assessed — NOT required MVP
[x] ORM coverage confirmed — no new models required
[x] SELECT-only MVP confirmed
[x] Project filter JOIN path documented (not evidence.project_uid)
[x] scope=all mapping documented
[x] ngram / MySQL 8.0 constraints documented — P6 validation pending
[x] MATCH primary; LIKE fallback not required MVP
[x] Boundary creep review — no parser/raw_vault/parsed/embed/review/UI
[x] P4 whitelist preview documented
[x] Remote SSH note recorded
[ ] User confirmation → P3 Implementation Gate
```

---

## 16. P2 STOP

**Do not enter P3** until user confirms.

**Do not enter P4 Dev.**

No `backend/**` changes in P2.

No `sql/**` changes in P2.

---

## 17. Next Step

On user approval:

```text
Tech Lead Agent → P3 Implementation Gate
Deliverable: specs/012-search-service/p3_implementation_gate.md
```

P3 must lock: Dev whitelist, CLI contract, optional API decision, scope=all pagination, SearchHit DTO, FULLTEXT query implementation strategy, P6 Chinese ngram test plan.

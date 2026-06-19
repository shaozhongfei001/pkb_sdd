# 010 Evidence Chain — P2 DB & Data Review

> Role: Tech Lead Agent + DB & Data Review  
> Spec: `specs/010-evidence-chain/`  
> Branch: `feature/010-evidence-chain`  
> Stage: P2 DB & Data Read Review  
> Base commit: `4ec9cf0` (P1 approved)

---

## 1. Gate Conclusion

**P2-GATE: PASS WITH CONSTRAINTS**

010 Evidence Chain may enter **P3 Implementation Gate** after user confirmation.

Constraints (locked for P3/P4):

```text
C1  No schema migration required for MVP — reuse init SQL tables as-is.
C2  New ORM models required — KbDocumentChunk + KbEvidence (not present today).
C3  Idempotency via deterministic chunk_uid / evidence_uid UNIQUE upsert — not composite DB unique on (document_uid, chunk_index).
C4  parser_name / parser_adapter_version — join kb_document or read parse_manifest; do NOT add columns to chunk/evidence tables in MVP.
C5  Field name mapping in service layer — content/start_offset/end_offset (chunk), source_char_* (evidence).
C6  kb_document is read-only for 010 — no writes, no parse_registry.py changes.
C7  MinerU page_no / bbox — best-effort nullable; MarkItDown MVP may leave null.
C8  Do not modify KbDocument ORM columns in 010 scope.
```

**Migration:** NOT required for MVP. If future composite uniqueness is desired → separate migration spec.

**P4 DB write:** APPROVED for `kb_document_chunk` and `kb_evidence` only (after P3 whitelist).

---

## 2. Mandatory Questionnaire

| # | Question | Answer |
|---|----------|--------|
| 1 | `kb_document_chunk` exists? | **YES** — `sql/001_init_schema_v1_1.sql` L195–223 |
| 2 | `kb_evidence` exists? | **YES** — `sql/001_init_schema_v1_1.sql` L225–254 |
| 3 | ORM models exist? | **PARTIAL** — `KbDocument` yes; `KbDocumentChunk` / `KbEvidence` **NO** |
| 4 | If ORM missing, P3/P4 may add models? | **YES** — new file e.g. `backend/app/models/evidence.py` (P3 whitelist) |
| 5 | Table fields sufficient for MVP? | **YES WITH MAPPING** — see §4 |
| 6 | Unique / idempotent keys exist? | **YES** — `chunk_uid UNIQUE`, `evidence_uid UNIQUE`; see §5 |
| 7 | Missing unique → migration required? | **NO for MVP** — deterministic UID upsert sufficient |
| 8 | Missing fields → shrink MVP? | **NO shrink** — use mapping + metadata JSON + kb_document join |
| 9 | P4 may write DB? | **YES** — chunk + evidence tables only |
| 10 | P4 may add ORM models? | **YES** |
| 11 | P4 may modify existing ORM? | **NO** — `KbDocument` read-only; no `parse_registry` model changes |
| 12 | P4 may modify migration/sql? | **NO** — MVP blocked on schema change; separate spec if needed later |

---

## 3. Schema Verification

### 3.1 `kb_document_chunk` (exists)

Source: `sql/001_init_schema_v1_1.sql`

| Column | Type | MVP use |
|--------|------|---------|
| `chunk_uid` | VARCHAR(64) UNIQUE | Primary idempotency key |
| `document_uid` | VARCHAR(64) | Link to kb_document |
| `content_uid` | VARCHAR(64) | Content identity |
| `chunk_index` | INT | Stable ordering |
| `chunk_level` | VARCHAR(32) | section / page / document |
| `heading_path` | TEXT | Section path |
| `page_no` | INT NULL | PDF page when known |
| `slide_no` | INT NULL | Slide when known |
| `start_offset` | INT | char_start equivalent |
| `end_offset` | INT | char_end equivalent |
| `bbox` | JSON | Optional locator |
| `content` | MEDIUMTEXT | Chunk text (`text` in P1 spec) |
| `content_hash` | CHAR(64) | Change detection / UID input |
| `metadata` | JSON | parser extras if needed |
| `created_at` | DATETIME | Audit |

Indexes: `idx_document_uid`, `idx_content_uid`, FULLTEXT on `content`.

**Not present:** `parser_name`, `parser_adapter_version` — obtain via `kb_document` join or manifest.

### 3.2 `kb_evidence` (exists)

| Column | Type | MVP use |
|--------|------|---------|
| `evidence_uid` | VARCHAR(64) UNIQUE | Primary idempotency key |
| `document_uid` | VARCHAR(64) | Required |
| `content_uid` | VARCHAR(64) | Required |
| `chunk_uid` | VARCHAR(64) NULL | Link to chunk |
| `source_sha256` | CHAR(64) | Content hash |
| `source_char_start` | INT | char_start |
| `source_char_end` | INT | char_end |
| `page_no` / `slide_no` | INT NULL | Locators |
| `heading_path` | TEXT | Locator |
| `bbox` | JSON | Optional |
| `quote_text` | MEDIUMTEXT | Evidence quote |
| `source_location` | VARCHAR(512) | Human-readable locator |
| `source_file_path` | TEXT | Optional path ref (not raw_vault bin read) |
| `metadata` | JSON | parser_name/version overflow |
| `created_at` | DATETIME | Audit |

**Not present:** `parser_name`, `parser_adapter_version` as columns — join or metadata.

### 3.3 Migration assessment

```text
Init schema tables exist and cover MVP field semantics.
No missing columns block MVP chunk/evidence insert.
No new UNIQUE constraints required if UID strategy is deterministic.
=> Migration NOT required for 010 MVP.
```

If P4 discovers need for `UNIQUE(document_uid, chunk_index)` → STOP → migration spec (out of 010 MVP).

---

## 4. P1 Field Mapping Matrix

| P1 / MVP field | Storage | Status |
|----------------|---------|--------|
| `content_uid` | chunk + evidence columns | OK |
| `document_uid` | chunk + evidence columns | OK |
| `chunk_uid` | chunk.chunk_uid | OK |
| `chunk_index` | chunk.chunk_index | OK |
| `text` | chunk.**content** | Map in service |
| `char_start` | chunk.**start_offset** / evidence.source_char_start | OK |
| `char_end` | chunk.**end_offset** / evidence.source_char_end | OK |
| `heading_path` | chunk + evidence | OK |
| `page_no` | chunk + evidence | OK (nullable) |
| `slide_no` | chunk + evidence | OK (nullable) |
| `bbox` | chunk + evidence JSON | OK (nullable) |
| `evidence_uid` | evidence.evidence_uid | OK |
| `quote_text` | evidence.quote_text | OK |
| `source_location` | evidence.source_location | OK |
| `parser_name` | kb_document.parser_name OR manifest | Join/read — not on chunk table |
| `parser_adapter_version` | kb_document.parser_version OR manifest | Join/read |
| `created_at` | both tables | OK |

---

## 5. Idempotency Strategy (P3 lock)

### 5.1 Existing constraints

```text
kb_document_chunk.chunk_uid        UNIQUE
kb_evidence.evidence_uid           UNIQUE
```

No UNIQUE on `(document_uid, chunk_index)`.

### 5.2 Recommended deterministic keys (P3)

```text
chunk_uid    = hash(content_uid, document_uid, chunk_index, content_hash_or_parser_profile)
evidence_uid = hash(chunk_uid, source_char_start, source_char_end, evidence_type_or_quote_hash)
```

P4 behavior:

```text
INSERT ... ON DUPLICATE KEY UPDATE   (MySQL upsert on chunk_uid / evidence_uid)
OR SELECT existing by UID before insert
```

Re-run same parsed input → same UIDs → no duplicate rows.

### 5.3 Migration for idempotency?

**NOT required** for MVP given UNIQUE on UID columns.

---

## 6. ORM Status

| Model | File | Status |
|-------|------|--------|
| `KbDocument` | `backend/app/models/document.py` | **Exists** — 006 registry writes |
| `KbDocumentChunk` | — | **Missing** — P4 add |
| `KbEvidence` | — | **Missing** — P4 add |

P3 whitelist preview:

```text
backend/app/models/evidence.py   # NEW: KbDocumentChunk, KbEvidence
```

**P4 must NOT modify:**

```text
backend/app/models/parse_registry.py
backend/app/models/file.py
backend/app/models/vault.py
backend/app/models/duplicate.py
```

**KbDocument:** read-only SELECT in 010; no column additions.

---

## 7. `kb_document` Contract Impact (006)

006 `ParseRegistryService._upsert_document()` writes `kb_document` on registry ingest.

010 requirements:

```text
SELECT kb_document for: document_uid, content_uid, source_sha256, parser_name,
                      parser_version, markdown_path, manifest_path, output_dir
Must NOT call _upsert_document or mutate kb_document rows.
```

Observed 006 behavior (informational — **not fixed in 010**):

```text
_upsert_document filters parser_profile == PARSER_PROFILE_MARKITDOWN hardcoded.
MinerU registry rows may still have kb_document rows but profile filter is MarkItDown-centric.
```

**P3 constraint for 010:** Resolve documents via:

```text
1. kb_parse_result (manifest_path, text_path, parser_name from run)
2. parse_manifest.json on disk
3. kb_document as secondary hint — not sole source for MinerU profile filter
```

No 010 change to `parse_registry.py`.

---

## 8. Parsed Artifacts & Registry Sufficiency

### 8.1 Path contract (001–007)

```text
parsed/by_hash/{sha256[:2]}/{sha256[2:4]}/{sha256}/
  parsed_text.md
  parsed_metadata.json
  parse_manifest.json
```

Helper: `backend/app/core/parsed_paths.py` — `build_parsed_content_dir`, `build_parsed_artifact_paths`.

### 8.2 Manifest fields (005 MarkItDown)

```text
content_uid, sha256, parser_name, parser_adapter_version,
parsed_text_path, parsed_metadata_path, generated_at, status
```

Sufficient for: section-level chunking from `parsed_text.md`; page/bbox typically null.

### 8.3 Manifest fields (007 MinerU)

```text
parser_name, parser_profile, parser_adapter_version,
parsed_text_path, parsed_metadata_path, assets_dir (optional)
```

Sufficient for: document/section chunks; page/bbox best-effort from metadata/assets when present.

### 8.4 Registry metadata

`kb_parse_result`: `content_uid`, `sha256`, `parsed_dir`, `manifest_path`, `text_path`, `status`.

**Sufficient** to locate parsed artifacts for evidence build when parse SUCCESS and files exist.

### 8.5 Gaps (non-blocking for MVP)

| Gap | Mitigation |
|-----|------------|
| No pre-built page map in MarkItDown metadata | Section/document chunks only; page_no null |
| MinerU bbox in asset files not standardized in P1 | Store bbox null or parse assets_dir in P4 if manifest lists assets |
| 008 stale/test paths | Skip content with missing parsed files; log error; no repair |
| kb_document MinerU profile filter quirk | Prefer manifest + kb_parse_result |

---

## 9. Write Surface Approval (P4 preview)

| Surface | P4 allowed? |
|---------|-------------|
| INSERT/UPSERT `kb_document_chunk` | **YES** |
| INSERT/UPSERT `kb_evidence` | **YES** |
| SELECT `kb_document`, `kb_parse_result`, `kb_file_content` | **YES** |
| UPDATE/INSERT `kb_document` | **NO** |
| Other tables | **NO** |
| `sql/**`, migrations | **NO** (MVP) |
| raw_vault binary read | **NO** |
| parsed file write | **NO** |

---

## 10. Conflict Review vs 001–009

| Completed spec | Conflict? | Notes |
|----------------|-----------|-------|
| 001–002 | None | Read content identity; sealed services untouched |
| 003 | None | Read-only |
| 004–007 | None | Read parsed outputs; no re-parse |
| 006 registry | None if read-only | Must not alter registry writes |
| 008–009 | None | Do not auto-consume quality reports in MVP |

---

## 11. P3 Entry Checklist (for next stage)

```text
[ ] Lock chunk_uid / evidence_uid generation algorithm
[ ] Lock parser-specific chunk strategy (markitdown section vs mineru page)
[ ] Lock Dev whitelist: evidence_chain.py, models/evidence.py, cli, tests
[ ] Lock kb_document read-only
[ ] Lock no migration / no sql changes
[ ] Lock idempotent upsert pattern
[ ] Document MinerU document resolution via manifest + kb_parse_result
```

---

## 12. STOP

P2 DB & Data Review completed.

**Do not enter P3** until user confirms.

No `backend/**`, `sql/**`, or migration changes in P2.

Deliverable: this file only (`specs/010-evidence-chain/p2_db_review.md`).

# 011 Curated Project Assets — P2 DB & Data Review

> Role: Tech Lead Agent + DB & Data Review  
> Spec: `specs/011-curated-project-assets/`  
> Branch: `feature/011-curated-project-assets`  
> Stage: P2 DB & Data Read Review  
> Base commit: `1e4c87e` (P1 approved)

---

## 1. Gate Conclusion

**P2-GATE: PASS WITH CONSTRAINTS**

011 Curated Project Assets may enter **P3 Implementation Gate** after user confirmation.

Constraints (locked for P3/P4):

```text
C1  No schema migration required for MVP — reuse init SQL tables as-is.
C2  New ORM models required — KbProject, KbProjectDocument, KbCuratedAsset (not present today).
C3  Idempotency via deterministic project_uid / curated_uid UNIQUE upsert — not composite DB unique on (project_uid, asset_type).
C4  related_content_uids / related_document_uids / related_evidence_uids — use native JSON columns (not TEXT).
C5  generation_method locked to TEMPLATE_RULE for MVP; generation_status SUCCESS | SKIPPED | FAILED.
C6  version_no MVP default = 1; --force updates file + kb_curated_asset.updated_at without bumping version_no (P3 lock).
C7  kb_document / kb_document_chunk / kb_evidence — read-only SELECT; no writes from 011.
C8  kb_evidence.project_uid column exists but 011 must NOT backfill evidence rows in MVP.
C9  kb_project_document has created_at only (no updated_at) — acceptable for MVP mapping rows.
C10 curated_path stores resolved path string (prefer relative to curated_root in DB; absolute OK if documented in P3).
C11 kb_project.document_count may be updated denormalized on build; other completeness flags remain default/NULL in MVP.
C12 mapping_method MVP values: MANIFEST | CLI | SEED (P3 lock enum).
C13 Do not modify init SQL, existing migrations, or existing ORM model files except read-only imports.
```

**Migration:** NOT required for MVP.

**P4 DB write:** APPROVED for `kb_project`, `kb_project_document`, and `kb_curated_asset` only (after P3 whitelist).

**P4 filesystem write:** APPROVED under `{curated_root}/projects/{project_code}/` for MVP asset files only.

---

## 2. Mandatory Questionnaire

| # | Question | Answer |
|---|----------|--------|
| 1 | `kb_project` exists? | **YES** — `sql/001_init_schema_v1_1.sql` L290–319 |
| 2 | `kb_project_document` exists? | **YES** — L321–340 |
| 3 | `kb_curated_asset` exists? | **YES** — L342–361 |
| 4 | ORM models exist? | **NO** — `KbProject` / `KbProjectDocument` / `KbCuratedAsset` **missing** |
| 5 | Read ORM for 010 tables exists? | **YES** — `KbDocument`, `KbDocumentChunk`, `KbEvidence` in `document.py` / `evidence.py` |
| 6 | `curated_root` in config? | **YES** — `StorageConfig.curated_root`; `app.example.yaml` L10; `app.yaml` L10 |
| 7 | Table fields sufficient for MVP? | **YES WITH CONSTRAINTS** — see §4 |
| 8 | Unique / idempotent keys exist? | **YES** — see §5 |
| 9 | Missing unique → migration required? | **NO for MVP** — deterministic UID upsert sufficient |
| 10 | Missing fields → shrink MVP? | **NO shrink** — use JSON arrays + optional metadata JSON |
| 11 | P4 may write DB? | **YES** — three project/curated tables only |
| 12 | P4 may write curated files? | **YES** — under `curated/projects/{project_code}/` |
| 13 | P4 may add ORM models? | **YES** — new `backend/app/models/project.py` (P3 whitelist) |
| 14 | P4 may modify existing ORM? | **NO** — existing models read-only; no column additions |
| 15 | P4 may modify migration/sql? | **NO** |
| 16 | Schema/ORM gap → STOP? | **YES** — if init tables missing or P4 needs new columns → migration spec before P4 |

---

## 3. Schema Verification

### 3.1 `kb_project` (exists)

Source: `sql/001_init_schema_v1_1.sql` L290–319

| Column | Type | MVP use |
|--------|------|---------|
| `project_uid` | VARCHAR(64) UNIQUE | Primary idempotency key |
| `project_code` | VARCHAR(128) UNIQUE | CLI `--project-code`; manifest key |
| `project_name` | VARCHAR(512) NOT NULL | Manifest / template |
| `description` | TEXT | Manifest / template |
| `document_count` | INT DEFAULT 0 | Denormalized count on build (optional update) |
| `status` | VARCHAR(64) DEFAULT 'ACTIVE' | MVP default ACTIVE |
| `created_at` | DATETIME | Audit |
| `updated_at` | DATETIME ON UPDATE | Audit; changes on upsert / --force |
| Other columns | various | **Out of MVP** — leave NULL/default |

Indexes: `project_uid` UNIQUE, `project_code` UNIQUE, FULLTEXT on `(project_name, description)`.

### 3.2 `kb_project_document` (exists)

Source: L321–340

| Column | Type | MVP use |
|--------|------|---------|
| `project_uid` | VARCHAR(64) | FK logical link to kb_project |
| `document_uid` | VARCHAR(64) | Required mapping |
| `content_uid` | VARCHAR(64) NOT NULL | Required mapping |
| `mapping_method` | VARCHAR(64) | MANIFEST / CLI / SEED |
| `confirmed_project_code` | VARCHAR(128) | Set to project_code on confirm |
| `is_primary` | TINYINT DEFAULT 1 | MVP default 1 |
| `created_at` | DATETIME | Audit |

**Not present:** `updated_at` — acceptable; re-upsert same `(project_uid, document_uid)` is no-op via UNIQUE.

Unique: `uk_project_document (project_uid, document_uid)`.

### 3.3 `kb_curated_asset` (exists)

Source: L342–361

| Column | Type | MVP use |
|--------|------|---------|
| `curated_uid` | VARCHAR(64) UNIQUE | Primary idempotency key |
| `project_uid` | VARCHAR(64) NULL | Populate always in MVP |
| `asset_type` | VARCHAR(64) NOT NULL | `project_card` \| `evidence_index` \| `source_documents` |
| `asset_title` | VARCHAR(1024) | Human title from template |
| `curated_path` | TEXT NOT NULL | Asset locator under curated_root |
| `related_content_uids` | JSON | Array of content_uid strings |
| `related_document_uids` | JSON | Array of document_uid strings |
| `related_evidence_uids` | JSON | Array of evidence_uid strings |
| `generation_method` | VARCHAR(64) | **TEMPLATE_RULE** (MVP lock) |
| `generation_status` | VARCHAR(64) | SUCCESS / SKIPPED / FAILED |
| `version_no` | INT DEFAULT 1 | MVP fixed at 1 |
| `metadata` | JSON | Build stats optional |
| `created_at` | DATETIME | Audit |
| `updated_at` | DATETIME ON UPDATE | Changes on --force rewrite |

**Not present:** UNIQUE on `(project_uid, asset_type, version_no)` — rely on `curated_uid` deterministic hash.

Indexes: `curated_uid` UNIQUE; `idx_project_uid`; `idx_asset_type`.

### 3.4 Read-only tables (010 — no 011 writes)

| Table | ORM | 011 access |
|-------|-----|------------|
| `kb_document` | `KbDocument` | SELECT |
| `kb_document_chunk` | `KbDocumentChunk` | SELECT |
| `kb_evidence` | `KbEvidence` | SELECT |
| `kb_file_content` | `KbFileContent` | SELECT (optional path metadata) |
| `kb_parse_result` | via parse_registry models | SELECT (optional) |

### 3.5 Migration assessment

```text
Init schema defines all three write targets with MVP-required columns.
related_* fields are JSON type — matches 011 traceability design.
No missing NOT NULL columns block MVP insert (project_name required on kb_project — manifest must supply).
No new UNIQUE constraints required if UID strategy is deterministic.
backend/migrations/** — empty / none present; no migration files to modify.
=> Migration NOT required for 011 MVP.
```

If P4 discovers need for `UNIQUE(project_uid, asset_type, version_no)` or new columns → **STOP** → migration spec.

---

## 4. P1 MVP Field Mapping Matrix

| MVP / P1 field | Storage | Status |
|----------------|---------|--------|
| `project_uid` | `kb_project.project_uid` | OK — UNIQUE |
| `project_code` | `kb_project.project_code` | OK — UNIQUE |
| `project_name` | `kb_project.project_name` | OK — NOT NULL |
| `document_uid` | `kb_project_document.document_uid` | OK |
| `content_uid` | `kb_project_document.content_uid` | OK — NOT NULL |
| `curated_uid` | `kb_curated_asset.curated_uid` | OK — UNIQUE |
| `asset_type` | `kb_curated_asset.asset_type` | OK |
| `curated_path` | `kb_curated_asset.curated_path` | OK — TEXT NOT NULL |
| `related_evidence_uids` | `kb_curated_asset.related_evidence_uids` | OK — **JSON array** |
| `related_content_uids` | `kb_curated_asset.related_content_uids` | OK — **JSON array** |
| `related_document_uids` | `kb_curated_asset.related_document_uids` | OK — **JSON array** (P1 also requires) |
| `generation_method` | `kb_curated_asset.generation_method` | OK — lock `TEMPLATE_RULE` |
| `version_no` | `kb_curated_asset.version_no` | OK — MVP = 1 |
| `created_at` | all write tables | OK |
| `updated_at` | `kb_project`, `kb_curated_asset` | OK |
| `updated_at` (mapping) | — | N/A — `kb_project_document` has `created_at` only |
| Evidence locators | `kb_evidence.*` | Read-only — not written by 011 |
| Parser metadata | `kb_document.parser_name` etc. | Read-only join |

---

## 5. Idempotency Strategy (P3 lock)

### 5.1 Existing SQL constraints

```text
kb_project.project_uid              UNIQUE
kb_project.project_code             UNIQUE
kb_project_document                 UNIQUE (project_uid, document_uid)
kb_curated_asset.curated_uid        UNIQUE
```

### 5.2 Recommended deterministic keys (align with 010 evidence_chain style)

```text
normalized_code = project_code.strip()   # P3 may add case policy; default exact strip

project_uid = SHA256("project|v1|" + normalized_code)

curated_uid = SHA256("curated|v1|" + normalized_code + "|" + asset_type + "|" + str(version_no))
```

P4 upsert behavior:

```text
kb_project:           INSERT ... ON DUPLICATE KEY UPDATE (project_uid or project_code key)
kb_project_document:  INSERT ... ON DUPLICATE KEY UPDATE (uk_project_document)
kb_curated_asset:     INSERT ... ON DUPLICATE KEY UPDATE (curated_uid)
```

Re-run without `--force`:

```text
Skip filesystem overwrite if kb_curated_asset row exists and generation_status = SUCCESS
OR compare file mtime/hash (P3 lock one policy)
```

Re-run with `--force`:

```text
Rewrite curated Markdown files
UPDATE kb_curated_asset.updated_at + related_* JSON if evidence set changed
Do NOT change curated_uid or version_no in MVP
```

### 5.3 Migration for idempotency?

**NOT required** for MVP given UNIQUE on `project_uid`, `project_code`, `uk_project_document`, and `curated_uid`.

---

## 6. ORM Status

| Model | File | Status | 011 role |
|-------|------|--------|----------|
| `KbProject` | — | **Missing** | P4 write |
| `KbProjectDocument` | — | **Missing** | P4 write |
| `KbCuratedAsset` | — | **Missing** | P4 write |
| `KbDocument` | `document.py` | Exists | Read-only |
| `KbDocumentChunk` | `evidence.py` | Exists | Read-only |
| `KbEvidence` | `evidence.py` | Exists | Read-only |
| `KbFileContent` | `file.py` | Exists | Read-only optional |

P3 whitelist preview:

```text
backend/app/models/project.py   # NEW: KbProject, KbProjectDocument, KbCuratedAsset
```

**P4 must NOT modify:**

```text
backend/app/models/evidence.py      # no write-path changes
backend/app/models/document.py      # read-only
backend/app/models/parse_registry.py
backend/app/models/file.py
backend/app/models/vault.py
backend/app/models/duplicate.py
backend/app/core/config.py          # curated_root already defined
sql/**
backend/migrations/**
```

---

## 7. Config Verification

### 7.1 `curated_root`

| Source | Value | Readable by service |
|--------|-------|---------------------|
| `config/app.example.yaml` | `./curated` | YES via `load_config()` |
| `config/app.yaml` | `./curated` | YES |
| `AppConfig.storage.curated_root` | `Path` resolved relative to project root | YES |

P4 service must resolve output paths as:

```text
{config.storage.curated_root}/projects/{project_code}/00_project_card.md
{config.storage.curated_root}/projects/{project_code}/10_evidence_index.md
{config.storage.curated_root}/projects/{project_code}/source_documents.md
```

Service may `mkdir(parents=True, exist_ok=True)` on curated_root — **not** raw_vault/parsed.

---

## 8. P2 Mandatory Rulings

| # | Ruling | Decision |
|---|--------|----------|
| 1 | MVP reuse init SQL? | **YES** — no migration |
| 2 | P4 add `project.py` ORM? | **YES** — after P3 whitelist |
| 3 | Modify existing sql/migration? | **NO** |
| 4 | `kb_project` idempotency key | **`project_uid` UNIQUE** (deterministic hash); secondary **`project_code` UNIQUE** |
| 5 | `kb_project_document` idempotency key | **`uk_project_document (project_uid, document_uid)`** |
| 6 | `kb_curated_asset` idempotency key | **`curated_uid` UNIQUE** (deterministic hash includes asset_type + version_no) |
| 7 | `related_*` storage | **JSON columns** — Python `list[str]` serialized to JSON array; **not TEXT** |
| 8 | `curated_path` as asset locator? | **YES** — primary filesystem pointer; pair with `curated_uid` in DB |
| 9 | `generation_method` lock? | **YES** — `TEMPLATE_RULE` only in MVP |
| 10 | P4 write curated filesystem? | **YES** — MVP three files under `projects/{project_code}/` |
| 11 | P4 DB write allowlist | **ONLY** `kb_project`, `kb_project_document`, `kb_curated_asset` |
| 12 | P4 DB write denylist | **YES** — no `kb_document_chunk`, `kb_evidence`, `kb_review_item`, `kb_embedding_ref`, parse registry tables |
| 13 | P4 forbid parser/LLM/embed/search/UI? | **YES** |
| 14 | Schema/ORM insufficient → STOP? | **YES** — migration spec before P4 |

---

## 9. P3 / P4 Scope Preview (for P3 gate — not active)

### 9.1 P4 allowed (pending P3)

```text
backend/app/services/curated_project_assets.py
backend/app/models/project.py
backend/app/cli/main.py                    # build-curated-project only
backend/tests/test_curated_project_assets.py
backend/tests/fixtures/curated_project/
config/projects/*.yaml                     # sample manifests only
{curated_root}/projects/**                 # runtime output
kb_project / kb_project_document / kb_curated_asset DML
```

### 9.2 P4 forbidden

```text
Parser services (markitdown, mineru, magic-pdf)
LLM / embedding / vector / search / Streamlit
kb_review_item / kb_manual_correction / kb_embedding_ref writes
kb_document_chunk / kb_evidence writes
parse registry writes
raw_vault original.bin reads
parsed artifact mutation
sql/** / migrations/** changes
sealed inventory_scanner / file_content_vault
evidence_chain.py write-path changes
```

---

## 10. Risks & Non-blocking Notes

| ID | Note | Severity |
|----|------|----------|
| N1 | `kb_curated_asset.project_uid` nullable in SQL — P4 should always populate | Low — constraint C10 |
| N2 | No DB FK from `kb_project_document.project_uid` → `kb_project.project_uid` | Low — app-level integrity |
| N3 | `kb_evidence.project_uid` unused in 010 — 011 must not bulk-update evidence | Low — constraint C8 |
| N4 | Duplicate `project_code` case variants not normalized in SQL — P4 must normalize before hash | Low — P3 policy |
| N5 | `document_count` denormalization optional — template may compute from JOIN instead | Low |

None block P3 entry.

---

## 11. P2 Exit Checklist

```text
[x] kb_project verified in init SQL
[x] kb_project_document verified in init SQL
[x] kb_curated_asset verified in init SQL
[x] Write ORM missing — P4 add project.py approved
[x] Read ORM for 010 tables confirmed
[x] curated_root verified in AppConfig + yaml
[x] MVP field mapping documented
[x] Idempotency keys ruled
[x] Migration NOT required
[x] P4 write scope ruled (DB + curated filesystem)
[x] P4 forbidden scope ruled
[x] PASS WITH CONSTRAINTS issued
[ ] User P2 approval
[ ] STOP — no P3 until user confirms
```

---

## 12. STOP

P2 DB Review complete. **Do not enter P3** until user confirms.

P3/P4 remain **BLOCKED**.

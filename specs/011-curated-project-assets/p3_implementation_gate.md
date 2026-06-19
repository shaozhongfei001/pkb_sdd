# 011 Curated Project Assets — P3 Implementation Gate

> Role: Tech Lead Agent  
> Spec: `specs/011-curated-project-assets/`  
> Branch: `feature/011-curated-project-assets`  
> Stage: P3 Implementation Gate  
> P2 base: `2d4f8d7` (PASS WITH CONSTRAINTS)  
> Status: **P3-GATE PASS — P4 BLOCKED until user confirms**

---

## 1. Gate Conclusion

P3 Implementation Gate: **PASS**

011 Curated Project Assets is approved to enter **P4 Dev Implementation** after explicit user confirmation.

P2 constraints C1–C13 remain locked. No schema migration for MVP.

If P4 discovers need for new columns, composite UNIQUE keys, or migration → **STOP** and return to TL + DB Review. Dev must not expand scope.

---

## 2. P4 Dev File Whitelist

Dev Agent may **create or modify only**:

```text
backend/app/models/project.py                             # NEW — KbProject, KbProjectDocument, KbCuratedAsset
backend/app/services/curated_project_assets.py            # NEW — core builder
backend/app/cli/main.py                                   # register build-curated-project
backend/tests/test_curated_project_assets.py              # NEW
backend/tests/fixtures/curated_project/**                 # NEW — test fixtures only
```

### 2.1 Fixture / manifest paths (P4)

**Allowed fixture locations** (tests only — do not commit runtime curated output):

```text
backend/tests/fixtures/curated_project/
  demo_project.manifest.yaml.fixture          # sample project manifest
  chinese_project.manifest.yaml.fixture     # Chinese project_name test
  db_seed.py or conftest helpers              # optional inline DB seed in test file preferred
```

**Naming rules:**

```text
- Use .fixture suffix for YAML/manifest files (NOT .yaml alone under repo root scan paths).
- Do NOT add .txt / .pdf / .json document files under backend/tests/fixtures/ that inventory scanner would ingest.
- Synthetic parsed trees are NOT required for 011 MVP — tests seed kb_document / chunk / evidence via SQLAlchemy.
- If sample manifest needed outside tests: config/projects/*.yaml.fixture in test tmp_path copies only.
```

**Do NOT create or modify:**

```text
curated/**                          # repo working tree — runtime output via CLI only
config/projects/*.yaml              # unless copied into tmp_path in tests; no committed prod manifests in P4 unless TL adds later
backend/app/models/__init__.py      # repo has no models/__init__.py — import directly
```

**Model import note:**

```python
from app.models.project import KbProject, KbProjectDocument, KbCuratedAsset
from app.models.document import KbDocument          # read-only
from app.models.evidence import KbDocumentChunk, KbEvidence  # read-only
```

If P4 discovers hard blocker requiring `models/__init__.py` or existing ORM edits → **STOP**.

**Read-only reference (do not modify):**

```text
backend/app/core/config.py
backend/app/core/database.py
backend/app/models/document.py
backend/app/models/evidence.py
backend/app/models/file.py
backend/app/models/parse_registry.py
backend/app/services/evidence_chain.py
```

---

## 3. P4 Forbidden Files (Black List)

Dev Agent must **not** modify:

```text
backend/app/services/evidence_chain.py
backend/app/models/evidence.py
backend/app/models/document.py
backend/app/services/parse_registry.py
backend/app/services/parse_quality_checker.py
backend/app/services/parse_quality_report_summarizer.py
backend/app/services/markitdown_parser.py
backend/app/services/mineru_pdf_parser.py
backend/app/services/parser_router.py
backend/app/services/file_content_vault.py
backend/app/services/inventory_scanner.py
backend/app/services/duplicate_governance.py
backend/app/adapters/**
backend/app/models/parse_registry.py
backend/app/models/file.py
backend/app/models/vault.py
backend/app/models/duplicate.py
backend/app/api/**
streamlit/**
sql/**
backend/migrations/**
config/app.yaml
config/parser_rules.yaml
raw_vault/**
parsed/**
curated/**                          # except runtime output under configured curated_root during test tmp workspace
specs/SPEC_INDEX.md
docs/handoff-*.md
README.md
```

### 3.1 Forbidden Behavior

```text
- Invoke MarkItDown / MinerU / magic-pdf / subprocess parse
- Read raw_vault original.bin for text extraction
- Modify parsed artifact files or original user files
- UPDATE/INSERT/DELETE kb_document
- UPDATE/INSERT/DELETE kb_document_chunk
- UPDATE/INSERT/DELETE kb_evidence (including kb_evidence.project_uid backfill)
- Write parse registry tables (kb_parse_run, kb_parse_result, kb_parsed_artifact)
- Write kb_review_item, kb_manual_correction, kb_embedding_ref
- LLM distillation / semantic summarization / embedding / vector / search / Streamlit
- Consume or auto-fix 008/009 quality reports
- Schema migration or sql/**
- Automatic project discovery via LLM or path semantic inference
- Move/delete/rename original user files
- Commit files under repo curated/ directory
```

---

## 4. CLI Contract (Final — P4)

### 4.1 Command

```bash
PYTHONPATH=backend python -m app.cli.main build-curated-project \
  --config config/app.yaml \
  --project-code DEMO-2024 \
  --project-name "示例项目" \
  --content-uid <sha256-or-content-uid> \
  --manifest backend/tests/fixtures/curated_project/demo_project.manifest.yaml.fixture \
  --limit 100 \
  --dry-run \
  --force \
  --output /path/to/curated_build_report.json
```

### 4.2 Parameters

| Flag | Required | Default | Behavior |
|---|---|---|---|
| `--config` | No | `config/app.yaml` | Load `curated_root`, `pipeline_version`, mysql |
| `--project-code` | **Yes** | — | Normalized project key; drives `project_uid` |
| `--project-name` | No* | null | Project display name; required if kb_project row new and no manifest |
| `--content-uid` | No* | null | Single content filter; repeatable logic via manifest preferred |
| `--manifest` | No | null | YAML manifest path (see §6) |
| `--limit` | No | null | Max documents to include when multi-document (≥1) |
| `--dry-run` | No | false | **Zero DB write, zero curated file write** |
| `--force` | No | false | Overwrite existing curated files + upsert metadata; **same UIDs** |
| `--output` | No | null | JSON build report path |

\* **Input rule (MVP):**

```text
--project-code is always required.

Document set resolution order:
1. If --manifest provided → use manifest.documents[] (primary for multi-doc tests/E2E).
2. Else if --content-uid provided → single-doc mode; resolve document_uid via kb_document SELECT.
3. Else if kb_project_document rows exist for project → use existing mappings (SEED mode).
4. Else exit 1 with clear error: no documents to curate.

--project-name required when creating new kb_project and manifest omits project_name.
```

### 4.3 `--dry-run` contract

```text
- May SELECT kb_project, kb_project_document, kb_curated_asset, kb_document, kb_document_chunk, kb_evidence, kb_file_content.
- Must NOT INSERT/UPDATE/DELETE any MySQL table.
- Must NOT create/write files under curated_root.
- Must NOT mkdir curated output tree for write (read config paths OK).
- Output: stdout summary + optional --output JSON with planned asset paths and UID list.
```

### 4.4 `--force` contract

```text
- Re-write all three MVP curated Markdown files even when kb_curated_asset exists with generation_status=SUCCESS.
- Upsert kb_project / kb_project_document / kb_curated_asset with SAME project_uid / curated_uid (deterministic).
- Update kb_curated_asset.updated_at and related_* JSON if evidence set changed.
- Must NOT increment version_no in MVP (locked at 1).
- Must NOT create duplicate rows on UNIQUE keys.
```

### 4.5 No-force re-run contract

```text
If kb_curated_asset row exists for curated_uid AND generation_status=SUCCESS AND file exists on disk:
  skip file write for that asset_type
  skip DB upsert (or no-op SELECT-only)
Else:
  write file + upsert row
```

P4 implements one consistent policy; P5 tests both paths.

### 4.6 `--output` report schema

```json
{
  "report_type": "curated_build_report",
  "schema_version": "1.0",
  "mode": "build",
  "generated_at": "<ISO8601 Z>",
  "dry_run": false,
  "project_code": "DEMO-2024",
  "project_uid": "<64-char hex>",
  "filters": {
    "content_uid": null,
    "manifest": null,
    "limit": null
  },
  "summary": {
    "documents_mapped": 0,
    "evidence_rows_read": 0,
    "assets_planned": 3,
    "assets_written": 0,
    "assets_skipped": 0,
    "files_written": 0,
    "db_projects_upserted": 0,
    "db_mappings_upserted": 0,
    "db_assets_upserted": 0,
    "warnings": 0,
    "errors": 0
  },
  "assets": [
    {
      "asset_type": "project_card",
      "curated_uid": "<hex>",
      "curated_path": "projects/DEMO-2024/00_project_card.md",
      "generation_method": "TEMPLATE_RULE",
      "generation_status": "SUCCESS",
      "related_content_uids": [],
      "related_document_uids": [],
      "related_evidence_uids": []
    }
  ],
  "warnings": [],
  "errors": []
}
```

Report file write is allowed; not a DB write. Report must not mutate parsed/raw_vault/originals.

### 4.7 Exit codes

| Code | Condition |
|---|---|
| **0** | Completed (possibly with per-item skips/warnings logged) |
| **1** | Config error, missing project_code, no documents, invalid args, DB connection failure, fatal runtime error |
| **2** | Reserved — not used in MVP unless P4 documents partial-failure policy |

### 4.8 Forbidden CLI flags

```text
--fix  --repair  --reparse
--markitdown  --mineru  --magic-pdf
--build-evidence-chain  --check-parse-quality  --summarize-parse-quality
--llm  --embed  --semantic  --search  --streamlit  --review
--write-chunk  --write-evidence  --write-registry
```

### 4.9 CLI help text (required)

```text
Build curated project assets from evidence and registry metadata.
Writes curated Markdown under curated_root and kb_project / kb_project_document / kb_curated_asset only.
Does not call parsers, read raw_vault binaries, LLM-distill, or modify parsed artifacts.
Use --dry-run for zero DB and zero curated file writes.
```

### 4.10 Default runtime guarantees

```text
- Does NOT call parsers by default or ever in MVP.
- Does NOT read raw_vault original.bin.
- Does NOT modify parsed/ artifacts.
- Does NOT run LLM / embedding / search / review workflow.
- Non-dry-run writes ONLY: three curated Markdown files + three allowed DB tables.
```

---

## 5. DB Write Contract (Final)

### 5.1 Allowed writes

| Table | Operations | Notes |
|---|---|---|
| `kb_project` | INSERT … ON DUPLICATE KEY UPDATE | Upsert on `project_uid` or `project_code` UNIQUE |
| `kb_project_document` | INSERT … ON DUPLICATE KEY UPDATE | Upsert on `uk_project_document (project_uid, document_uid)` |
| `kb_curated_asset` | INSERT … ON DUPLICATE KEY UPDATE | Upsert on `curated_uid` UNIQUE |

### 5.2 Forbidden writes

```text
kb_document                 — SELECT only
kb_document_chunk           — SELECT only
kb_evidence                 — SELECT only; NO project_uid backfill
kb_parse_run                — no write
kb_parse_result             — no write
kb_parsed_artifact          — no write
kb_file_content             — SELECT only (optional)
kb_review_item              — no write
kb_manual_correction        — no write
kb_embedding_ref            — no write
Any other table             — no write
sql/** / migrations         — no change
```

### 5.3 Idempotency (locked)

**Normalization:**

```python
normalized_project_code = project_code.strip()
# Case preserved — do NOT lower() unless future spec changes
```

**Deterministic UID generation:**

```python
project_uid = sha256(f"project|v1|{normalized_project_code}".encode("utf-8")).hexdigest()

version_no = 1  # MVP fixed

curated_uid = sha256(
    f"curated|v1|{normalized_project_code}|{asset_type}|{version_no}".encode("utf-8")
).hexdigest()
```

**asset_type values (MVP lock):**

```text
project_card       → file 00_project_card.md
evidence_index     → file 10_evidence_index.md
source_documents   → file source_documents.md
```

**kb_project_document upsert:**

```text
UNIQUE (project_uid, document_uid)
mapping_method: MANIFEST | CLI | SEED
confirmed_project_code = normalized_project_code on insert
```

**kb_curated_asset field locks:**

```text
generation_method = "TEMPLATE_RULE"     # always in MVP
generation_status = SUCCESS | SKIPPED | FAILED
version_no = 1                          # always in MVP; --force does not bump
related_content_uids   → JSON array of strings
related_document_uids  → JSON array of strings
related_evidence_uids  → JSON array of strings
curated_path           → prefer relative path from curated_root, e.g.
                         projects/{project_code}/00_project_card.md
```

**Upsert policy:**

```text
ON DUPLICATE KEY UPDATE mutable fields (project_name, description, document_count,
  asset_title, curated_path, related_* JSON, generation_status, metadata, updated_at)
preserve project_uid / curated_uid / version_no
do not create second row
```

**Migration:** If P4 needs new columns or UNIQUE constraints → **STOP**.

---

## 6. Curated File Contract (Final)

### 6.1 MVP output paths only

```text
{curated_root}/projects/{project_code}/00_project_card.md
{curated_root}/projects/{project_code}/10_evidence_index.md
{curated_root}/projects/{project_code}/source_documents.md
```

**Explicitly NOT generated in MVP:**

```text
01_background.md
02_requirements.md
03_solution.md
04_delivery_assets.md
05_reusable_assets.md
06_lessons_learned.md
```

Future spec required before any expansion.

### 6.2 File content rules

```text
1. UTF-8 encoding.
2. Rule/template generation only — no LLM calls.
3. Must include project_code and project_name in 00_project_card.md header.
4. Must reference evidence_uid / content_uid / document_uid in tables or bullet lists.
5. No LLM-generated conclusions, requirements, solution, or lessons learned prose.
6. generation_method metadata in DB = TEMPLATE_RULE; files may include HTML comment footer:
   <!-- generated_by: build-curated-project; generation_method: TEMPLATE_RULE; project_uid: ... -->
   (optional — P4 choice; P5 verifies UID presence in body regardless)
```

### 6.3 Template outline (P4 implement)

**00_project_card.md**

```markdown
# Project Card: {project_name}

- project_code: `{project_code}`
- project_uid: `{project_uid}`
- document_count: {n}
- generation_method: TEMPLATE_RULE

## Linked content_uids
- `{content_uid}` ...

## Linked document_uids
- `{document_uid}` ...
```

**10_evidence_index.md**

```markdown
# Evidence Index: {project_code}

| evidence_uid | document_uid | content_uid | page_no | quote_snippet |
|---|---|---|---|---|
| ... | ... | ... | ... | ... |
```

**source_documents.md**

```markdown
# Source Documents: {project_code}

| document_uid | content_uid | parser_name | title |
|---|---|---|---|
| ... | ... | ... | ... |
```

Truncate `quote_snippet` (e.g. 120 chars) for readability; full quote remains in DB.

---

## 7. Project Input Model (Final — MVP)

### 7.1 Primary path (CLI)

```text
--project-code <code>            # required
--project-name <name>            # required when new project without manifest project_name
--content-uid <uid>              # single-document mode without manifest
```

### 7.2 Optional manifest

Path via `--manifest`. Schema (YAML):

```yaml
project_code: DEMO-2024
project_name: 示例项目
description: Optional description for project card
documents:
  - content_uid: "<64-char sha256>"
    document_uid: "<optional; resolved from kb_document if omitted>"
    is_primary: 1
```

**Resolution rules:**

```text
1. manifest.project_code must match --project-code or exit 1.
2. For each document entry:
   - Require content_uid.
   - If document_uid omitted: SELECT kb_document WHERE content_uid = ? LIMIT 1 (most recent OK for MVP).
   - If no kb_document row: log warning, skip document, continue.
3. mapping_method = MANIFEST when from manifest; CLI when --content-uid only; SEED when from existing kb_project_document only.
```

### 7.3 Explicitly out of MVP

```text
LLM project classification
Automatic project discovery from file paths
Semantic clustering of documents
Bulk scan of source_registry for project inference
```

---

## 8. ORM Contract (Final)

### 8.1 New file: `backend/app/models/project.py`

```python
class KbProject(Base):
    __tablename__ = "kb_project"
    # Map 1:1 to sql/001_init_schema_v1_1.sql — all columns typed
    # aliases / keywords → JSON columns

class KbProjectDocument(Base):
    __tablename__ = "kb_project_document"
    # No updated_at column in SQL — do not invent

class KbCuratedAsset(Base):
    __tablename__ = "kb_curated_asset"
    # related_* → JSON columns as list[str] via SQLAlchemy JSON type
    # metadata → metadata JSON column (map as metadata_json if needed for ORM reserved word)
```

### 8.2 Rules

```text
1. Add KbProject, KbProjectDocument, KbCuratedAsset only in project.py.
2. Do NOT modify evidence.py, document.py, or any existing model file.
3. Do NOT invent undocumented columns.
4. Read KbDocument / KbDocumentChunk / KbEvidence via existing models — SELECT only.
```

---

## 9. Service Contract (Final — P4)

```python
@dataclass
class CuratedProjectBuildResult:
    project_code: str
    project_uid: str
    documents_mapped: int
    evidence_rows_read: int
    assets_written: int
    assets_skipped: int
    files_written: int
    warnings: list[str]
    errors: list[str]
    report_path: Path | None = None

class CuratedProjectAssetsService:
    def __init__(self, config: AppConfig, session_factory) -> None: ...

    def build(
        self,
        *,
        project_code: str,
        project_name: str | None = None,
        content_uid: str | None = None,
        manifest_path: Path | None = None,
        limit: int | None = None,
        dry_run: bool = False,
        force: bool = False,
        output: Path | None = None,
    ) -> CuratedProjectBuildResult:
        ...
```

Internal flow:

```text
normalize project_code → resolve document set → upsert kb_project
→ upsert kb_project_document rows → SELECT evidence/chunk/document
→ render three templates → if dry_run: return plan
→ else: write files under curated_root → upsert kb_curated_asset rows
→ optional JSON report
```

**No evidence rows:**

```text
Log warning "no evidence for content_uid=..."
Still write source_documents.md and 00_project_card.md if documents mapped
evidence_index may be empty table with header only — generation_status SUCCESS or SKIPPED per asset (P4: index=SKIPPED if zero evidence, card/docs=SUCCESS)
Do not crash batch
```

---

## 10. Test Plan (P4 / P5)

Test file: `backend/tests/test_curated_project_assets.py`

Use `tmp_path` workspace with isolated `curated_root` from generated app.yaml — **never** write repo `curated/`.

Seed data via SQLAlchemy in fixtures (KbDocument, KbDocumentChunk, KbEvidence) — no inventory scan of new `.txt` files.

| ID | Test | Phase | User req |
|---|---|---|---|
| T1 | `--dry-run` → **zero** DB rows in kb_project* / kb_curated_asset; **zero** files under curated_root | P5 | #1 |
| T2 | First run → 3 curated files + upserts in 3 tables | P5 | #2 |
| T3 | Second run no-force → assets_skipped / files unchanged | P5 | #3 |
| T4 | `--force` rerun → files overwritten; same row counts; same UIDs | P5 | #4 |
| T5 | related_* JSON arrays match document/evidence set | P5 | #5 |
| T6 | Chinese project_name + UTF-8 curated content | P5 | #6 |
| T7 | No evidence rows → warning; no crash; partial files | P5 | #7 |
| T8 | Spy raw_vault `original.bin` open → not called | P5 | #8 |
| T9 | parsed dir mtime unchanged (if parsed exists in workspace) | P5 | #9 |
| T10 | Patch parser services → not called | P5 | #10 |
| T11 | kb_document_chunk / kb_evidence / review / embedding / registry counts unchanged | P5 | #11 |
| T12 | No LLM/embed/search/streamlit imports or calls | P5 | #12 |
| T13 | `test_scan_project_fixtures` / inventory not picking up new fixtures | P5 | #13 |
| T14 | Full `backend/tests` regression | P5 | #14 |
| T15 | `--output` JSON schema valid | P5 | — |
| T16 | generation_method always TEMPLATE_RULE | P5 | — |
| T17 | version_no always 1 even with --force | P5 | — |
| T18 | manifest + --project-code mismatch → exit 1 | P5 | — |
| T19 | Markdown files contain evidence_uid / content_uid / document_uid strings | P5 | — |
| T20 | kb_evidence.project_uid remains NULL/unchanged after build | P5 | C8 |

Regression command:

```bash
PYTHONPATH=backend pytest \
  backend/tests/test_curated_project_assets.py \
  backend/tests/test_evidence_chain.py \
  backend/tests/test_inventory_scanner.py \
  backend/tests/test_file_content_vault.py \
  backend/tests/test_duplicate_governance.py \
  backend/tests/test_parser_router.py \
  backend/tests/test_markitdown_parser.py \
  backend/tests/test_parse_job_registry.py \
  backend/tests/test_mineru_pdf_parser.py \
  backend/tests/test_parse_quality_checker.py \
  backend/tests/test_parse_quality_report_summarizer.py
```

E2E (P6): `build-evidence-chain` on dev sample → `build-curated-project` → curated files + 3-table rows + UID traceability.

---

## 11. Dev Agent Handoff Template

```text
Role: Dev Agent
Spec: specs/011-curated-project-assets/
Branch: feature/011-curated-project-assets
Read first:
  specs/011-curated-project-assets/p3_implementation_gate.md
  specs/011-curated-project-assets/p2_db_review.md
  specs/011-curated-project-assets/tasks.md (P4 section)

Whitelist: §2 of p3_implementation_gate.md
Blacklist: §3
Implement P4 tasks only.
If schema/UID/migration gap found → STOP, do not expand scope.
After P4 STOP → QA Agent. Do not self-approve.
```

---

## 12. P3 Gate Summary

| Item | Decision |
|---|---|
| P3-GATE | **PASS** |
| Migration | **NOT required** (MVP) |
| P4 new ORM | `project.py` only |
| P4 modify existing ORM | **NO** |
| P4 DB write | kb_project, kb_project_document, kb_curated_asset only |
| P4 filesystem write | 3 MVP Markdown files under curated_root |
| dry-run | Zero DB + zero curated file write |
| Idempotency | Deterministic project_uid / curated_uid + UNIQUE upsert |
| generation_method | **TEMPLATE_RULE** |
| version_no | **1** (fixed) |
| related_* | **JSON arrays** |

---

## 13. STOP

P3 completed. **Do not enter P4** until user confirms.

No `backend/**` changes in P3.

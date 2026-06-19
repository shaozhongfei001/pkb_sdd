# 011 Curated Project Assets — plan.md

> Project: `pkb_sdd`  
> Phase: `P1 Tech Lead Plan — COMPLETE (awaiting user review)`  
> Status: `ACTIVE SPEC / NOT IMPLEMENTED`  
> Implementation status: `NOT STARTED (P4 blocked until P1–P3 approved)`

---

## 1. Architecture Overview

011 adds a curated project assets builder that consumes evidence and registry metadata:

```text
kb_document + kb_document_chunk + kb_evidence (SELECT)
        +
optional project manifest (config/projects/*.yaml)
        |
        v
CuratedProjectAssetsService               [P4]
        |
        +--> curated/projects/{project_code}/*.md   (write, idempotent)
        |
        +--> kb_project / kb_project_document       (UPSERT)
        |
        +--> kb_curated_asset                       (UPSERT)
```

Proposed component (P4 — not implemented in P1):

```text
backend/app/services/curated_project_assets.py
```

Proposed ORM (P2/P4 — verify in P2):

```text
backend/app/models/project.py             # KbProject, KbProjectDocument, KbCuratedAsset (new)
backend/app/models/evidence.py            # KbDocumentChunk, KbEvidence (read-only)
backend/app/models/document.py            # KbDocument (read-only)
```

Proposed CLI (P4):

```text
backend/app/cli/main.py                   # register build-curated-project
```

Proposed tests (P5):

```text
backend/tests/test_curated_project_assets.py
backend/tests/fixtures/curated_project/
```

---

## 2. Logical Flow

```text
1. Load config (curated_root, mysql, pipeline_version).
2. Resolve project by --project-code and optional --manifest YAML.
3. Upsert kb_project (project_uid from normalized project_code).
4. Resolve document set:
     a) from manifest documents[] list, or
     b) from existing kb_project_document rows, or
     c) from --content-uid / --document-uid filters.
5. Upsert kb_project_document for each mapping.
6. SELECT kb_evidence + kb_document_chunk for mapped content_uids.
7. Render template Markdown:
     - 00_project_card.md
     - 10_evidence_index.md
     - source_documents.md
8. Write files under curated/projects/{project_code}/ (UTF-8).
9. Upsert kb_curated_asset per file with related_*_uids JSON.
10. Log per-project success/failure; continue batch on single failure.
11. Return summary counts; optional --output JSON report.
```

No step may invoke parsers, read raw_vault binaries, modify parsed files, or write review/embedding records.

---

## 3. Service Design (Planned — P4)

### 3.1 Proposed Class

```python
class CuratedProjectAssetsService:
    def __init__(self, config: AppConfig, session_factory) -> None: ...

    def build(
        self,
        *,
        project_code: str,
        manifest_path: Path | None = None,
        content_uid: str | None = None,
        document_uid: str | None = None,
        limit: int | None = None,
        dry_run: bool = False,
        force: bool = False,
    ) -> CuratedProjectBuildResult:
        ...
```

P3 finalizes signatures.

### 3.2 Internal Concepts

```text
CuratedProjectBuildResult
  projects_processed, assets_written, files_written, errors[]

ProjectManifest
  project_code, project_name, description, documents[]

CuratedAssetPlan
  asset_type, asset_title, curated_path, related_uids, markdown_body
```

---

## 4. Template Strategy (MVP — P3 lock)

| asset_type | Template source | UID references |
|---|---|---|
| `project_card` | kb_project + counts from mappings/evidence | content_uid list in appendix |
| `evidence_index` | kb_evidence rows sorted by chunk_index | evidence_uid, document_uid, content_uid per row |
| `source_documents` | kb_document + kb_file_content metadata | document_uid, content_uid, parser_profile |

Templates are **rule-based Markdown** — no LLM prompts.

Example evidence_index row (illustrative):

```markdown
| evidence_uid | document_uid | content_uid | page_no | quote_snippet |
|---|---|---|---|---|
| ev_abc... | doc_xyz... | sha256... | 3 | 示例引用文本… |
```

---

## 5. Config Usage

011 reads:

```text
config.storage.curated_root
config.pipeline_version
config.mysql (connection via standard session factory — P4)
```

Optional:

```text
config/projects/{project_code}.yaml   # via --manifest
```

011 must not read/write for feature purposes:

```text
raw_vault binaries
reports_root for 008/009 auto-consumption (MVP)
parsed/ for text re-extraction (default: use 010 DB rows)
```

P2 must confirm `curated_root` exists in `config/app.example.yaml` and `AppConfig`.

---

## 6. Idempotency (Planned — P2 must confirm keys)

Design intent:

```text
Re-run build-curated-project on same project_code + same evidence set
=> same curated_uid set OR upsert without duplicate rows
=> skip file overwrite unless --force
```

P2 must map design to actual SQL unique keys:

```text
kb_project.project_uid UNIQUE
kb_project.project_code UNIQUE
kb_project_document.uk_project_document (project_uid, document_uid)
kb_curated_asset.curated_uid UNIQUE
```

If init schema lacks required uniqueness for idempotent upsert, P2 stops for migration design.

---

## 7. Dev File Whitelist Preview (P3 reference)

**Allowed (P4):**

```text
backend/app/services/curated_project_assets.py       # new
backend/app/models/project.py                        # new if P2 approves
backend/app/cli/main.py
backend/tests/test_curated_project_assets.py         # new
backend/tests/fixtures/curated_project/              # synthetic; non-inventory suffix
config/projects/*.yaml                               # optional sample manifests (P4/P6)
```

**Forbidden:**

```text
backend/app/services/inventory_scanner.py
backend/app/services/file_content_vault.py
backend/app/services/evidence_chain.py               # no write-path changes
backend/app/services/markitdown_parser.py
backend/app/services/mineru_pdf_parser.py
backend/app/services/parse_registry.py               # no write-path changes
backend/app/services/parse_quality_checker.py
backend/app/services/parse_quality_report_summarizer.py
backend/app/api/**                                   # 013 scope
streamlit/**                                         # 013 scope
sql/** without approved migration
raw_vault/** parsed/** (no mutation)
```

---

## 8. Exception Handling

| Scenario | Handling |
|---|---|
| manifest missing required fields | Fail project with clear error; continue batch |
| no evidence rows for content_uid | Write source_documents; evidence_index partial/empty with warning |
| kb_document missing | Skip mapping; log error |
| curated_root not writable | Fail early with clear error |
| DB constraint violation | Fail transaction for that project; continue batch |
| Chinese path / UTF-8 content | Must succeed |
| existing curated file without --force | Skip file write; skip or no-op kb_curated_asset update (P3 lock) |

---

## 9. P2 DB Review Checklist (Mandatory before P4)

```text
[ ] kb_project exists in init SQL — column list documented
[ ] kb_project_document exists in init SQL — column list documented
[ ] kb_curated_asset exists in init SQL — column list documented
[ ] ORM models exist or approved new models with field mapping table
[ ] Idempotency keys identified and testable
[ ] curated_root present in AppConfig / app.example.yaml
[ ] No invented columns vs sql/001_init_schema_v1_1.sql
[ ] Migration need assessed — if yes, STOP P4 until migration merged
[ ] DB write scope limited to kb_project / kb_project_document / kb_curated_asset (MVP)
[ ] kb_document_chunk / kb_evidence read-only from 011 (no writes)
```

If schema / ORM / unique keys insufficient → **STOP** at P2.

---

## 10. P1 Deliverables Checklist

```text
[x] spec.md
[x] plan.md
[x] tasks.md
[x] acceptance.md
[x] test_cases.md
[x] SPEC_INDEX.md updated (011 ACTIVE / PLANNED)
[x] README.md 011 active sync
[x] docs/feature_index.md drift fixed
[ ] backend/** implementation        # out of P1 scope
[ ] STOP — await user P1 review
```

---

## 11. P1 STOP

No P2/P3/P4 until user approves P1.

No `backend/**` changes in P1.

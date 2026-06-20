# 013 Streamlit Admin — P3 Implementation Gate

> Role: Tech Lead Agent  
> Spec: `specs/013-streamlit-admin/`  
> Branch: `feature/013-streamlit-admin`  
> Stage: P3 Implementation Gate  
> P2 base: `p2_db_review.md` (**PASS WITH CONSTRAINTS**)  
> Local base: `1fb0947` (012 merge on main line) + uncommitted P1/P2 spec artifacts  
> Status: **PASS WITH CONSTRAINTS — P4 BLOCKED until user confirms**

---

## 1. Repository State Verification

### 1.1 Branch switch (P3 prerequisite — completed)

```bash
cd /home/szf/dev/pyws/pkb_sdd
git branch --show-current   # was: main
git switch -c feature/013-streamlit-admin   # created and switched
git branch --show-current   # now: feature/013-streamlit-admin
git status --short
```

| Check | Expected | Actual | Verdict |
|---|---|---|---|
| Branch | `feature/013-streamlit-admin` | `feature/013-streamlit-admin` | **OK** |
| P1/P2 artifacts preserved | not discarded | P1 five-piece + SPEC_INDEX + README + feature_index + `p2_db_review.md` intact | **OK** |
| Destructive git ops | none | none performed | **OK** |
| Working tree | may be dirty | dirty — P1/P2 spec edits uncommitted | **OK** (commit before merge; not blocking P3) |

**Dirty files (expected, uncommitted):**

```text
M  README.md
M  docs/feature_index.md
M  specs/013-streamlit-admin/{spec,plan,tasks,acceptance,test_cases}.md
M  specs/SPEC_INDEX.md
?? specs/013-streamlit-admin/p2_db_review.md
?? specs/013-streamlit-admin/p3_implementation_gate.md  (this file)
```

P3 work continues on **`feature/013-streamlit-admin`**, not `main`.

---

## 2. P1/P2 Contract Readback

### 2.1 P1 MVP scope (locked)

013 MVP = **read-only Streamlit admin** consuming 001–012 contracts:

| Page | Data path | Write |
|---|---|---|
| KB Search | `SearchService` (012) in-process | None |
| Evidence Explorer | SELECT `kb_evidence`, `kb_document_chunk`, `kb_document` | None |
| Projects & Curated | SELECT project tables + read `storage.curated_root` Markdown | None |
| Parse Registry | SELECT `kb_parse_run`, `kb_parse_result`, `kb_parsed_artifact` | None |
| Quality Reports | Read `storage.reports_root` 008/009 artifacts | None |
| Inventory Snapshot | SELECT `kb_file_instance`, `kb_file_content`, optional `kb_raw_vault_object` metadata | None |

### 2.2 P2 decision

**PASS WITH CONSTRAINTS** — SELECT-only MVP feasible; **no migration**; existing ORM + `SearchService` + filesystem roots sufficient.

### 2.3 P2 constraints inherited (C1–C18 → locked for P4)

| ID | Constraint |
|---|---|
| C1 | SELECT-only MVP — zero DML on all KB tables; no migration |
| C2 | Search: in-process `SearchService` only; no UI FULLTEXT SQL; no default `search-kb` subprocess |
| C3 | Config: `load_config()` → `config.storage.curated_root`, `config.storage.reports_root` |
| C4 | Curated files: `curated_root / KbCuratedAsset.curated_path` (not `file_path`) |
| C5 | Inventory: display `KbFileInstance.source_path` as metadata; never `open()` user paths |
| C6 | Parse Registry: `kb_parse_run` / result / artifact only (not `kb_parse_job`) |
| C7 | Quality Reports glob: `parse_quality_report_*.json`, `parse_quality_summary_*.md`, `parse_quality_summary_*.json` |
| C8 | Path traversal guard on all curated + reports filesystem reads |
| C9 | Session: `st.cache_resource` for engine/factory; short-lived sessions; **no `session_scope()`** in lib |
| C10 | `st.cache_data` optional with TTL; stale reads acceptable for browse UI |
| C11 | DB errors → `st.error`; app remains navigable |
| C12 | Inventory Snapshot **IN MVP**; `kb_duplicate_group` summary **OUT** |
| C13 | Denylist writes on all registry/inventory/evidence/project/review/embedding tables |
| C14 | No raw_vault binary, no parsed primary reads, no parser/CLI triggers, no review workflow |
| C15 | pytest `test_batch_content_uid_filter` — resolve/waive before P5 full-green |
| C16 | Branch hygiene: work on `feature/013-streamlit-admin` |
| C17 | `project_code` filter via `kb_project → kb_project_document` (012 contract) |
| C18 | Optional `content_uid` / `document_uid` search filters per `SearchQuery.validate_and_build` |

### 2.4 Backend contract verification (read-only, P3)

Verified on `main@1fb0947` working tree:

```text
SearchService     backend/app/services/search_service.py  — MATCH...AGAINST internal; _assert_select_only()
SearchQuery       backend/app/schemas/search.py           — VALID_SCOPES = all|document|chunk|evidence|project|curated
Config            backend/app/core/config.py            — AppConfig.storage: StorageConfig with curated_root, reports_root
Database          backend/app/core/database.py          — create_db_engine, create_session_factory, session_scope (commits!)
ORM               KbCuratedAsset.curated_path, KbFileInstance.source_path, KbParseRun/Result/Artifact
Dependencies      backend/requirements.txt              — streamlit NOT present; P4 adds here only
Sealed services   inventory_scanner, file_content_vault, parsers, evidence_chain, curated_project_assets, parse_registry, quality_*, duplicate_governance
```

---

## 3. Gate Decision

### Status: **PASS WITH CONSTRAINTS**

013 Streamlit Admin is approved to enter **P4 Dev Implementation** after explicit user confirmation.

**Reason for PASS WITH CONSTRAINTS (not plain PASS):**

```text
1. P2 field-name corrections must be enforced in P4 (storage.*, curated_path, source_path, kb_parse_run).
2. Path traversal protection must be implemented and tested in P4/P5.
3. session_scope() must not be used in Streamlit lib (implicit commit risk).
4. Known pytest baseline failure must be resolved/waived before P5 full-green.
5. streamlit dependency not yet in requirements — P4 must add minimally.
6. P1/P2 spec artifacts still uncommitted — commit hygiene before merge.
```

**FAIL triggers (none met):**

```text
✗ Not on feature branch        — resolved
✗ P1/P2 missing                — present
✗ P2 not PASS                  — PASS WITH CONSTRAINTS
✗ P4 needs migration           — NO
✗ P4 needs DB writes           — NO
✗ P4 needs parser/CLI          — NO
✗ P4 needs raw_vault binary    — NO
✗ Enters 008-review-workflow   — NO
✗ Whitelist/blacklist unclear  — defined below
```

If P4 discovers need for new columns, indexes, audit tables, DML, or migration → **STOP** and return to TL + DB Review.

---

## 4. P4 Implementation Scope

P4 delivers a **local operator Streamlit app** under `frontend/streamlit_admin/` with six read-only pages and supporting `lib/` modules.

**In scope:**

```text
- Streamlit multipage app (st.navigation or pages/ directory)
- lib modules: config, db session, search_client, repositories, report/curated readers, path guard, formatters
- Unit tests for lib layer (backend/tests/test_streamlit_admin_*.py)
- Add streamlit to backend/requirements.txt (single dependency file — verified location)
```

**Out of scope:**

```text
- Any backend/app/services/** modification (import only)
- FastAPI routes (012 deferred API remains deferred)
- Pipeline CLI triggers, parser calls, review workflow
- DB writes, migrations, new tables
- raw_vault / parsed primary reads
- curated/reports/original file mutation
```

**Launch command (P4 must document in app header/README snippet):**

```bash
cd /path/to/pkb_sdd
PYTHONPATH=backend streamlit run frontend/streamlit_admin/app.py \
  --server.headless true
```

Config override env (P4 lock): `PKB_CONFIG` → path to `app.yaml`; default `config/app.yaml`.

---

## 5. P4 Whitelist

Dev Agent may **create or modify only**:

```text
frontend/streamlit_admin/**
  app.py
  pages/*.py                    # or equivalent st.navigation modules
  lib/*.py

backend/tests/test_streamlit_admin_*.py
backend/tests/fixtures/streamlit_admin/**     # .fixture metadata; no inventory-ingestible docs

backend/requirements.txt                      # add streamlit pin only (verify no duplicate requirements files)
```

### 5.1 Dependency rule

Before editing dependencies, Dev Agent must verify:

```bash
find . -maxdepth 2 -name 'requirements*.txt' -o -name 'pyproject.toml'
```

**Current project:** only `backend/requirements.txt` exists. **Do not create** root `requirements.txt` or `pyproject.toml` for streamlit unless TL approves.

Suggested pin (P4 finalizes exact version):

```text
streamlit>=1.28,<2.0
```

### 5.2 Read-only import allowlist (no modification)

Dev Agent may **import** but **must not modify**:

```text
backend/app/services/search_service.py
backend/app/schemas/search.py
backend/app/core/config.py
backend/app/core/database.py
backend/app/models/document.py
backend/app/models/evidence.py
backend/app/models/project.py
backend/app/models/parse_registry.py
backend/app/models/file.py
backend/app/models/vault.py
```

Import pattern:

```python
# PYTHONPATH=backend required
from app.core.config import load_config, AppConfig
from app.core.database import create_db_engine, create_session_factory
from app.services.search_service import SearchService
from app.schemas.search import SearchQuery, SearchValidationError, SearchProjectNotFoundError
from app.models.evidence import KbEvidence, KbDocumentChunk
from app.models.document import KbDocument
from app.models.project import KbProject, KbProjectDocument, KbCuratedAsset
from app.models.parse_registry import KbParseRun, KbParseResult, KbParsedArtifact
from app.models.file import KbFileInstance, KbFileContent
from app.models.vault import KbRawVaultObject
```

### 5.3 Fixture rules (P4/P5)

```text
- Use .fixture suffix for JSON/YAML under fixtures/streamlit_admin/.
- Do NOT add .txt/.pdf/.md document files that inventory scanner would ingest.
- Seed DB via SQLAlchemy in tests; do not read raw_vault/parsed for seeds.
- Lib tests may mock SearchService; must not duplicate FULLTEXT SQL in tests either.
```

---

## 6. P4 Blacklist

Dev Agent must **not** create or modify:

```text
backend/app/services/inventory_scanner.py
backend/app/services/file_content_vault.py
backend/app/services/markitdown_parser.py
backend/app/services/mineru_pdf_parser.py
backend/app/services/parser_router.py
backend/app/services/parse_registry.py
backend/app/services/evidence_chain.py
backend/app/services/curated_project_assets.py
backend/app/services/parse_quality_checker.py
backend/app/services/parse_quality_report_summarizer.py
backend/app/services/duplicate_governance.py
backend/app/services/search_service.py          # import only — 012 sealed
backend/app/cli/main.py
backend/app/api/**
backend/app/main.py
backend/app/models/**
backend/app/core/vault_paths.py
backend/app/core/parsed_paths.py
sql/**
backend/migrations/**
config/app.yaml
config/parser_rules.yaml
raw_vault/**
parsed/**
curated/**
reports/**
streamlit/**                                    # legacy path if exists — use frontend/streamlit_admin/
specs/SPEC_INDEX.md
docs/handoff-*.md
README.md
docs/feature_index.md
```

### 6.1 Forbidden behavior

```text
- Invoke MarkItDown / MinerU / magic-pdf / subprocess parse
- Subprocess pipeline CLIs (scan-inventory, copy-to-vault, parse-*, build-*, check-parse-quality, summarize-quality-report, search-kb as default)
- Hand-write MATCH ... AGAINST or FULLTEXT SQL in frontend/lib/**
- Bypass SearchService for any search scope query
- Read raw_vault/**/original.bin or display binary vault content
- Read parsed/** as primary view source (parsed_text.md, parsed_metadata.json, parse_manifest.json)
- open() on kb_file_instance.source_path for content preview
- INSERT / UPDATE / DELETE / REPLACE / DDL on any MySQL table
- session.add / session.commit / session.flush in Streamlit lib
- Use session_scope() in Streamlit lib (commits on success — forbidden)
- Write kb_review_item / kb_manual_correction / kb_embedding_ref / kb_task_log
- Write registry, evidence, project, curated, inventory, vault tables
- LLM UI / semantic search / embedding / vector stores
- Review queue / manual correction / repair / reparse UI
- Move/delete/rename originals; auto-delete duplicates; quarantine actions
- Accept arbitrary user-typed filesystem paths for read
- Path traversal (..) or symlink escape on curated/reports reads
- Schema migration or sql/**
```

---

## 7. MVP Page Contract

All six pages are **IN MVP**. Dev must not add Review/Repair/Pipeline pages.

### 7.1 KB Search

| Element | Contract |
|---|---|
| Data | `SearchService.search(SearchQuery)` |
| Inputs | `query` (required), `scope`, optional `project_code`, `content_uid`, `document_uid`, `limit`, `offset` |
| Scope enum | `document`, `chunk`, `evidence`, `project`, `curated`, `all` only |
| Display | `hit_type`, `snippet`, `relevance_score`, traceability UIDs per hit_type |
| Drill-down | Evidence hits → navigate Evidence Explorer filtered by `evidence_uid` |
| Errors | Empty query → validation message before service call; `SearchValidationError` / `SearchProjectNotFoundError` → user message |

### 7.2 Evidence Explorer

| Element | Contract |
|---|---|
| Tables | SELECT `kb_evidence`, optional JOIN `kb_document`, `kb_document_chunk` |
| Filters | `evidence_uid`, `document_uid`, `content_uid`, `chunk_uid` |
| Display | `evidence_uid`, `document_uid`, `content_uid`, `chunk_uid`, `quote_text`, `normalized_text`, `source_location`, `page_no`, `heading_path`, `created_at` |
| Forbidden | Edit/save; parsed file read; raw_vault read |

### 7.3 Projects & Curated

| Element | Contract |
|---|---|
| Tables | SELECT `kb_project`, `kb_project_document`, `kb_curated_asset` |
| File read | `(config.storage.curated_root / curated_path).resolve()` with traversal guard |
| Display | project list, document mapping, asset list, Markdown render read-only |
| Forbidden | Save/edit Markdown; write curated/** |

### 7.4 Parse Registry

| Element | Contract |
|---|---|
| Tables | SELECT `kb_parse_run`, `kb_parse_result`, `kb_parsed_artifact` |
| Legacy | **Do not** query `kb_parse_job` (no ORM) |
| Display | run summary → expand results/artifacts |
| Forbidden | Re-parse button; registry writes |

### 7.5 Quality Reports

| Element | Contract |
|---|---|
| Source | `config.storage.reports_root` filesystem only |
| Glob | `parse_quality_report_*.json`, `parse_quality_summary_*.md`, `parse_quality_summary_*.json` |
| Sort | mtime descending |
| Display | file list, JSON structure, Markdown render, issue_count/metadata when present |
| Forbidden | Run 008/009 CLIs; write/delete reports/** |

### 7.6 Inventory Snapshot

| Element | Contract |
|---|---|
| Tables | SELECT `kb_file_instance`, `kb_file_content`; optional `kb_raw_vault_object` metadata |
| Display | counts, paginated metadata: `file_instance_uid`, `source_path`, `file_name`, `sha256`, `content_uid`, `status`, `vault_status`, `parse_status`, `quality_status`, extension/mime if available |
| Forbidden | Open `source_path` or vault binaries; duplicate delete/move/rename; `kb_duplicate_group` UI (OUT) |

### 7.7 Explicitly forbidden pages / features

```text
Review Queue
Manual Correction
Repair Workflow
Reparse Trigger
Parser Trigger
Pipeline Run Button
Duplicate Delete / Move / Rename
raw_vault file preview / binary viewer
parsed artifact editor
LLM Summary
Semantic Search
Embedding / Vector Search
```

---

## 8. SearchService Integration Contract

### 8.1 Required call path

```text
Streamlit page
  → frontend/streamlit_admin/lib/search_client.py
  → app.services.search_service.SearchService
  → app.schemas.search.SearchQuery.validate_and_build(...)
  → SearchService.search(query)
```

### 8.2 Hard rules

```text
R-SEARCH-1  UI/lib MUST NOT contain MATCH ... AGAINST or FULLTEXT SQL strings.
R-SEARCH-2  UI/lib MUST NOT query search-scope tables directly for keyword search.
R-SEARCH-3  SearchService is the sole search entry point.
R-SEARCH-4  project_code filter MUST use kb_project → kb_project_document bridge (012 C7/C8).
            MUST NOT filter search via kb_evidence.project_uid.
R-SEARCH-5  scope MUST be one of: document, chunk, evidence, project, curated, all.
R-SEARCH-6  Empty/whitespace query MUST be rejected before SearchService call.
R-SEARCH-7  limit clamped 1–100; offset ≥ 0 — delegate to SearchQuery.validate_and_build.
R-SEARCH-8  subprocess search-kb is NOT MVP default; only if TL documents fallback in defect note.
```

### 8.3 Recommended search_client.py sketch (P4)

```python
def search_kb(
    config: AppConfig,
    *,
    query: str,
    scope: str = "all",
    project_code: str | None = None,
    content_uid: str | None = None,
    document_uid: str | None = None,
    limit: int = 20,
    offset: int = 0,
    session_factory=None,
) -> SearchResponse:
    sq = SearchQuery.validate_and_build(
        scope=scope,
        project_code=project_code,
        content_uid=content_uid,
        document_uid=document_uid,
        limit=limit,
        offset=offset,
        query=query,
    )
    service = SearchService(config, session_factory=session_factory)
    return service.search(sq)
```

(P4 aligns exact `validate_and_build` parameter order with `backend/app/schemas/search.py`.)

---

## 9. DB SELECT-only Contract

### 9.1 MVP DML posture

```text
Zero INSERT / UPDATE / DELETE / REPLACE / TRUNCATE / DDL on any KB table.
No kb_task_log writes.
No Streamlit-side audit table creation.
```

### 9.2 Allowed SELECT tables

| Table | Page |
|---|---|
| `kb_document` | Evidence JOIN; Search via SearchService |
| `kb_document_chunk` | Evidence Explorer |
| `kb_evidence` | Evidence Explorer; Search via SearchService |
| `kb_project` | Projects; Search via SearchService |
| `kb_project_document` | Projects; indirect search filter |
| `kb_curated_asset` | Projects; Search via SearchService |
| `kb_parse_run` | Parse Registry |
| `kb_parse_result` | Parse Registry |
| `kb_parsed_artifact` | Parse Registry |
| `kb_file_instance` | Inventory Snapshot |
| `kb_file_content` | Inventory Snapshot |
| `kb_raw_vault_object` | Inventory Snapshot — metadata columns only |

### 9.3 Forbidden tables (no SELECT required; no writes ever)

```text
kb_review_item, kb_manual_correction, kb_embedding_ref, kb_parse_job
```

### 9.4 Repository SQL style

```text
Prefer SQLAlchemy 2.x select() / session.execute(select(...)).
Raw SQL strings in frontend/lib FORBIDDEN unless SELECT-only and reviewed — prefer ORM.
If raw SQL used: must start with SELECT; no DML/DDL keywords.
```

### 9.5 P5 verification

Before/after UI/lib test session: row counts on denylist tables unchanged (TC018–TC021).

---

## 10. SQLAlchemy Session Contract

### 10.1 Factory reuse

```python
@st.cache_resource
def get_db_resources(config_path: str):
    config = load_config(config_path)
    engine = create_db_engine(config)
    factory = create_session_factory(engine)
    return config, factory
```

One engine + session_factory per Streamlit process.

### 10.2 Per-query lifecycle

```python
_, session_factory = get_db_resources(...)
with session_factory() as session:
    rows = session.execute(select(KbEvidence).where(...)).scalars().all()
# session closed — no lingering global Session
```

### 10.3 Forbidden patterns

```text
F-SESSION-1  Module-level Session object surviving Streamlit reruns
F-SESSION-2  session_scope() in frontend/streamlit_admin/lib/** (implicit commit on exit)
F-SESSION-3  session.add / session.commit / session.flush anywhere in frontend/**
F-SESSION-4  Long-lived transaction held open across st.button reruns
```

### 10.4 SearchService internal sessions

`SearchService.search()` opens its own `with self._session_factory() as session`. Acceptable — do not nest conflicting commits. Prefer injecting shared cached `session_factory` from `get_db_resources`.

### 10.5 Error handling

| Exception | UI behavior |
|---|---|
| `sqlalchemy.exc.OperationalError` | `st.error("无法连接 MySQL …")` |
| `SearchValidationError` | validation message |
| `SearchProjectNotFoundError` | project not found message |
| Other DB errors | logged + operator-readable `st.error`; sidebar navigation still works |

### 10.6 P6 check

TC033: repeated Streamlit reruns on Search page — no connection pool exhaustion (manual `SHOW PROCESSLIST` or observation).

---

## 11. Config / ORM Field Mapping Contract

### 11.1 Config paths (LOCKED — use these only)

| Concept | Correct access | Forbidden (P1 drift) |
|---|---|---|
| Curated root | `config.storage.curated_root` | `config.curated_root` |
| Reports root | `config.storage.reports_root` | `config.reports_root` |
| Load | `load_config(path)` → `AppConfig` | ad-hoc YAML parse |

`app.example.yaml` structure:

```yaml
storage:
  curated_root: ./curated
  reports_root: ./reports
```

### 11.2 ORM field names (LOCKED)

| Concept | Correct field | Forbidden |
|---|---|---|
| Curated file relative path | `KbCuratedAsset.curated_path` | `file_path` |
| Instance path metadata | `KbFileInstance.source_path` | `absolute_path` |
| Parse run entity | `KbParseRun` / `kb_parse_run` | `KbParseJob`, `kb_parse_job` |

### 11.3 Curated path join

```text
full_path = (config.storage.curated_root.resolve() / curated_path_from_db).resolve()
# curated_path example: "projects/DEMO/00_project_card.md"
# NOT: curated_root / "projects" / curated_path  (double projects prefix)
```

### 11.4 Parse Registry columns (UI minimum)

**KbParseRun:** `run_uid`, `parser_name`, `parser_adapter_version`, `parser_family`, `status`, `total_candidates`, `parsed_count`, `failed_count`, `started_at`, `finished_at`, `created_at`

**KbParseResult:** `result_uid`, `run_uid`, `content_uid`, `sha256`, `status`, `parser_name`, `error_code`, `created_at`

**KbParsedArtifact:** `artifact_uid`, `run_uid`, `content_uid`, `artifact_type`, `artifact_path`, `status`

---

## 12. Path Traversal Protection Contract

P4 **must** implement shared helper e.g. `lib/path_guard.py`:

```python
def resolve_under_root(root: Path, relative: str) -> Path:
    allowed = root.resolve()
    if ".." in Path(relative).parts:
        raise PathTraversalError("path must not contain ..")
    candidate = (allowed / relative).resolve()
    if not candidate.is_relative_to(allowed):
        raise PathTraversalError("path escapes allowed root")
    if candidate.is_symlink():
        raise PathTraversalError("symlinks not allowed")  # P4: reject symlinks
    return candidate
```

### 12.1 Rules

```text
PT-1  Curated reads: only under config.storage.curated_root
PT-2  Reports reads: only under config.storage.reports_root
PT-3  Relative paths from DB (curated_path) or glob results must pass resolve_under_root
PT-4  Never accept operator free-text absolute paths for file open
PT-5  Reject .. components in untrusted relative paths
PT-6  Reject symlinks; if platform cannot detect reliably, document and fail closed
PT-7  Allowed file types: UTF-8 text, Markdown, JSON — no binary reads
PT-8  Forbidden roots for open(): raw_vault/**, parsed/**, arbitrary source_path
```

### 12.2 Reports glob safety

```text
1. Glob only within reports_root.resolve()
2. For each match: re-verify resolved path.is_relative_to(reports_root)
3. Do not follow symlinks outside root
```

### 12.3 P5 tests

Lib tests must include traversal rejection cases (TC curated_reader / report_reader equivalents).

---

## 13. Quality Reports Contract

### 13.1 Allowed

```text
Read-only glob under config.storage.reports_root:
  parse_quality_report_*.json
  parse_quality_summary_*.md
  parse_quality_summary_*.json
List sorted by st_mtime DESC
Display: filename, mtime, issue_count / issue codes / metadata from JSON
Render Markdown summaries with st.markdown
Parse JSON for structured display (st.json or custom table)
```

### 13.2 Forbidden

```text
Run check-parse-quality CLI
Run summarize-quality-report / summarize-parse-quality CLI
Auto-fix quality issues
Write reports/**
Delete or rename reports/**
Read reports outside reports_root
```

---

## 14. Inventory Snapshot Contract

### 14.1 Allowed

```text
SELECT kb_file_instance — paginated metadata table
SELECT kb_file_content — sha256, vault_status, parse_status, quality_status, instance_count
SELECT kb_raw_vault_object — vault_uid, content_uid, sha256, vault_path, copy_status (strings only)
Aggregate counts (st.metric) for instances / contents / vault objects
Display source_path as read-only text (Chinese paths UTF-8)
```

### 14.2 Forbidden

```text
Read raw_vault binary / open vault_path bytes
open(kb_file_instance.source_path)
Delete duplicate files / move / rename / quarantine
kb_duplicate_group summary page (OUT of MVP)
Trigger inventory scan or vault copy
```

---

## 15. Explicit Non-goals

Carried from P1/P2 — P4 must not implement:

```text
NG001  Pipeline CLI triggers from UI
NG002  008-review-workflow (review_item / manual_correction)
NG003  Embedding / vector / semantic / LLM features
NG004  Parser invocation
NG005  raw_vault binary preview
NG006  parsed artifact editor / primary parsed reads
NG007  Original file mutation / auto dedup execution
NG008  MySQL migration or schema change
NG009  FastAPI GET /api/v1/search (012 deferred)
NG010  kb_duplicate_group UI
NG011  subprocess search-kb as default search path
NG012  UI-layer FULLTEXT SQL
```

---

## 16. Test Plan for P4/P5

### 16.1 P4 Dev self-check (before QA handoff)

```text
[ ] frontend/streamlit_admin/app.py launches without import error
[ ] All six pages render (empty state acceptable)
[ ] search_client calls SearchService — grep frontend for MATCH/AGAINST returns zero
[ ] path_guard used for curated + reports reads
[ ] no session.commit / session_scope in frontend/**
[ ] config uses config.storage.* paths only
[ ] ORM uses curated_path and source_path field names
[ ] Parse Registry queries KbParseRun not kb_parse_job
```

### 16.2 P5 QA entry (QA Agent)

**Required automated tests:** `backend/tests/test_streamlit_admin_*.py`

| Area | Test IDs (from test_cases.md) |
|---|---|
| config_loader | TC001 |
| search_client | TC002, TC003, TC013 |
| evidence_repository | TC004, TC005 |
| project_repository | TC006 |
| curated_reader | TC007, TC008 + traversal |
| registry_repository | TC009 |
| report_reader | TC010, TC011 |
| inventory | TC012 |
| formatters | TC014 |
| no side effects | TC015–TC022 |
| regression | TC023–TC024 |

**Manual UI checklist (P5/P6):** TC025–TC034

### 16.3 P5 exit criteria

```text
All lib unit tests pass
001–012 regression pass (see §17 for baseline exception process)
No MATCH...AGAINST in frontend/**
Row counts unchanged on denylist tables after test session
p5_qa_report.md produced
```

---

## 17. Known Baseline Risk

### 17.1 Current failure

```text
FAILED backend/tests/test_mineru_pdf_parser.py::test_batch_content_uid_filter
RuntimeError: No file instances found for sha256=fea22a...
```

### 17.2 P3 decision

| Stage | Blocked? |
|---|---|
| P3 gate | **No** |
| P4 start | **No** — Dev may proceed |
| P5 full-green / P6 sign-off | **Yes** — must resolve before P5 PASS |

### 17.3 Required resolution before P5 PASS (one of)

```text
Option A — Fix root cause in test_mineru_pdf_parser.py / fixture setup (preferred if in scope)
Option B — Document as environment/order-sensitive defect with reproduction note; TL waives temporarily
Option C — TL explicit temporary waiver in p5_qa_report.md with expiry condition
```

**P4 Dev Agent action:** run `PYTHONPATH=backend backend/.venv/bin/pytest backend/tests -q` early in P4; record result in PR notes. Do not ignore failure at P5.

---

## 18. Required Evidence from Dev Agent

At P4 completion, Dev must provide:

```text
E1   File list diff ⊆ P4 whitelist
E2   grep proof: no MATCH/AGAINST in frontend/streamlit_admin/
E3   grep proof: no session.commit / session_scope in frontend/streamlit_admin/
E4   Launch command verified manually once
E5   Screenshot or log snippet of each page empty/populated state
E6   pytest backend/tests/test_streamlit_admin_*.py -q PASS
E7   Full pytest baseline status documented (pass or known fail per §17)
E8   No modifications outside whitelist (especially backend/services, sql, cli)
```

---

## 19. STOP

P3 Implementation Gate **complete**.

```text
Gate status:     PASS WITH CONSTRAINTS
Branch:          feature/013-streamlit-admin
Next stage:      P4 Dev Implementation — BLOCKED until user explicitly confirms
Do NOT:          create frontend/streamlit_admin code in this session
Do NOT:          modify backend/** beyond future P4 whitelist
Do NOT:          commit unless user requests
```

**User confirmation required before dispatching Dev Agent:**

```text
"确认进入 013 P4 Dev"
```

After confirmation, Dev Agent reads this file + P2 + spec five-piece; implements only within §5 whitelist.

---

*End of P3 Implementation Gate — 013 Streamlit Admin*

# 013 Streamlit Admin — P2 DB / Data Review

> Role: DB & Data Agent  
> Spec: `specs/013-streamlit-admin/`  
> Branch: `feature/013-streamlit-admin` (expected) — **actual: `main`**  
> Stage: P2 DB / Data Review  
> Status: **PASS WITH CONSTRAINTS**

---

## 1. Repository State Verification

### 1.1 Commands executed

```bash
cd /home/szf/dev/pyws/pkb_sdd
git branch --show-current
git status --short
git log --oneline --decorate -12
# + spec reads, find models/services/sql
```

### 1.2 Results

| Check | Expected | Actual | Verdict |
|---|---|---|---|
| Branch | `feature/013-streamlit-admin` | `main` | **WARN** |
| Working tree | clean | dirty — modified `README.md`, `docs/feature_index.md`, `specs/013-streamlit-admin/*` (5 files), `specs/SPEC_INDEX.md` | **WARN** |
| HEAD | on 013 work line | `1fb0947` merge: feature/012-search-service into main | OK (012 base) |
| P1 five-piece set | present | `spec.md`, `plan.md`, `tasks.md`, `acceptance.md`, `test_cases.md` all exist | OK |
| `p2_db_review.md` | this file | created in P2 | OK |

**WARN notes (non-blocking for P2 technical review):**

- P2 did **not** switch branches or clean the worktree (per stage rules).
- P1 spec edits appear uncommitted on `main`; Tech Lead should create/checkout `feature/013-streamlit-admin` and commit P1 artifacts before P4.
- P2 review is based on **current working-tree P1 content** plus **main@1fb0947 backend ORM/schema**.

### 1.3 Backend inventory snapshot (read-only)

**ORM models (`backend/app/models/`):**

```text
document.py       → KbDocument
evidence.py       → KbDocumentChunk, KbEvidence
project.py        → KbProject, KbProjectDocument, KbCuratedAsset
parse_registry.py → KbParseRun, KbParseResult, KbParsedArtifact
file.py           → KbFileInstance, KbFileContent
vault.py          → KbRawVaultObject
duplicate.py      → KbDuplicateGroup
```

**Services (013 consumes read-only; does not modify):**

```text
search_service.py                 # 012 — in-process import for KB Search
+ sealed pipeline services (inventory, vault, parsers, evidence, curated, quality, registry)
```

**Config / DB layer:**

```text
backend/app/core/config.py        # AppConfig, load_config, StorageConfig
backend/app/core/database.py      # create_db_engine, create_session_factory, session_scope
```

**SQL / migrations:**

```text
sql/001_init_schema_v1_1.sql
sql/migrations/006_parse_registry_v1.sql (+ down)
```

No additional migration files beyond 006 parse registry.

---

## 2. P1 Contract Readback

### 2.1 MVP scope (locked)

013 MVP = **read-only Streamlit admin** over 001–012 contracts:

| Page | Data path | Write |
|---|---|---|
| KB Search | `SearchService` (012) | None |
| Evidence Explorer | SELECT `kb_evidence`, `kb_document_chunk`, `kb_document` | None |
| Projects & Curated | SELECT project tables + read `curated_root` Markdown | None |
| Parse Registry | SELECT `kb_parse_run`, `kb_parse_result`, `kb_parsed_artifact` | None |
| Quality Reports | Read `reports_root` 008/009 artifacts | None |
| Inventory Snapshot (optional) | SELECT `kb_file_instance`, `kb_file_content` metadata | None |

### 2.2 P1 safety locks

```text
SELECT-only MySQL (G011)
Search via SearchService only — no UI-layer MATCH ... AGAINST (S008)
No parser / pipeline CLI triggers (NG001)
No raw_vault binary read (S002, NG006)
No parsed filesystem for primary views (S003, NG007)
No review / embedding writes (S007, NG002, NG003)
No curated / reports mutation (S009, S010, NG011)
P2 must confirm migration need — P1 does not pre-judge (spec §10)
```

### 2.3 P1 naming vs implementation reality (P3 must align)

| P1 text | Actual backend contract | P3 action |
|---|---|---|
| `config.reports_root`, `config.curated_root` | `config.storage.reports_root`, `config.storage.curated_root` via `AppConfig.storage` | Use `load_config()` + `StorageConfig` |
| `kb_curated_asset.file_path` | Column + ORM field: **`curated_path`** (relative under `curated_root`) | Map in `curated_reader.py` |
| Inventory `absolute_path` | `kb_file_instance.source_path` | Display metadata column name |
| Parse Registry `kb_parse_job` (denylist template) | Active registry: **`kb_parse_run`** (+ result/artifact); `kb_parse_job` is legacy init table, no ORM | SELECT `kb_parse_run` only |

---

## 3. SELECT-only Feasibility Review

### 3.1 DML / DDL / migration questionnaire

| # | Question | Answer |
|---|---|---|
| 1 | New tables required? | **NO** |
| 2 | New columns required? | **NO** |
| 3 | New indexes required? | **NO** — existing PK/idx + 012 FULLTEXT sufficient |
| 4 | Migration required? | **NO** |
| 5 | Any INSERT/UPDATE/DELETE/DDL in MVP? | **NO** — deny all KB table DML |
| 6 | Hidden write needs? | **NONE mandatory** — see §3.2 |

### 3.2 Implicit write demand scan

| Potential write | MVP need? | Verdict |
|---|---|---|
| UI access / audit log | Not in P1 goals | **Defer** — no `kb_task_log` writes |
| Recent query history | Not in P1 | **Defer** — use Streamlit `st.session_state` only |
| Favorites / annotations | Not in P1 | **Forbidden** — would need new tables |
| Manual repair / review queue | Explicit NG002 | **Forbidden** |
| Cache table | Not required | **Forbidden** — use `st.cache_data` optionally |
| DB session table | Not required | **Forbidden** |
| Streamlit server-side file cache | Optional | **Allowed** — not KB DB; no `raw_vault`/`parsed` paths |

**Conclusion:** 013 MVP is **SELECT-only** for MySQL. No migration. No KB table writes.

### 3.3 Filesystem write scope

```text
Allowed: Streamlit browser session / optional st.cache_data (in-process)
Forbidden: curated/**, reports/**, raw_vault/**, parsed/**, original user files
```

---

## 4. Table / ORM Coverage Review

### 4.1 Search Page

**Requirement:** Must use `SearchService`; no UI-layer FULLTEXT SQL.

**SearchService coverage (verified `backend/app/services/search_service.py`):**

| Scope | Table(s) | FULLTEXT field(s) | Status |
|---|---|---|---|
| `document` | `kb_document` | `title` | Covered |
| `chunk` | `kb_document_chunk` | `content` | Covered |
| `evidence` | `kb_evidence` | `quote_text`, `normalized_text` | Covered |
| `project` | `kb_project` | `project_name`, `description` | Covered |
| `curated` | `kb_curated_asset` | `asset_title` | Covered |
| `all` | All five scopes merged | — | Covered |

**Filters aligned with 012:**

- `project_code` → `kb_project` + `kb_project_document` bridge (not `kb_evidence.project_uid`)
- `content_uid`, `document_uid` on document/chunk/evidence scopes
- `limit` 1–100, `offset` ≥ 0 via `SearchQuery.validate_and_build`

**DML guard:** `_assert_select_only()` blocks non-SELECT and DML/DDL keywords before execution.

**ORM:** SearchService uses raw `text()` SELECTs; target tables already have ORM models if enrichment needed elsewhere.

**Migration:** **Not required.**

**P3 constraints:**

- UI → `search_client.py` → `SearchService.search()` only.
- Validate empty query before service call (mirror `SearchQuery.validate_and_build`).
- Do not subprocess `search-kb` as default path.

### 4.2 Evidence Explorer

**Tables:** `kb_evidence`, `kb_document_chunk`, `kb_document` — all ORM-mapped.

**P1 display fields → SQL columns:**

| UI field | Source |
|---|---|
| `evidence_uid` | `kb_evidence.evidence_uid` |
| `document_uid` | `kb_evidence.document_uid` |
| `content_uid` | `kb_evidence.content_uid` |
| `chunk_uid` | `kb_evidence.chunk_uid` (nullable) |
| `quote_text` | `kb_evidence.quote_text` |
| `normalized_text` | `kb_evidence.normalized_text` |
| `source_location` | `kb_evidence.source_location` |
| `page_no` | `kb_evidence.page_no` |
| `heading_path` | `kb_evidence.heading_path` |
| `created_at` | `kb_evidence.created_at` |
| Document title (optional) | `kb_document.title` via JOIN |

**Filters:** `evidence_uid`, `document_uid`, `content_uid`, `chunk_uid` — all indexed columns.

**Forbidden:**

- Read `raw_vault/**/original.bin`
- Rebuild evidence from `parsed/**` files

**Migration:** **Not required.**

### 4.3 Projects & Curated

**Tables:** `kb_project`, `kb_project_document`, `kb_curated_asset` — all ORM-mapped.

**Curated filesystem alignment (011 contract):**

```text
DB:   kb_curated_asset.curated_path  e.g. "projects/DEMO/00_project_card.md"
Root: config.storage.curated_root    e.g. ./curated
Full: curated_root / curated_path    → ./curated/projects/DEMO/00_project_card.md
```

011 `CuratedProjectAssetsService` writes with the same relative pattern (`projects/{project_code}/{filename}`). **No extra `projects/` prefix** when joining — `curated_path` already includes it.

**Display fields:**

| UI field | Source |
|---|---|
| `curated_uid` | `kb_curated_asset.curated_uid` |
| `project_uid` | `kb_curated_asset.project_uid` |
| `project_code` | `kb_project.project_code` (JOIN) |
| `asset_type` | `kb_curated_asset.asset_type` |
| `asset_title` | `kb_curated_asset.asset_title` |
| Relative path | `kb_curated_asset.curated_path` |
| Markdown body | Read file at resolved path under `curated_root` |

**Migration:** **Not required.**

**P3 constraints:**

- Read-only `st.markdown`; no save/edit.
- Path join + traversal guard (§8).

### 4.4 Parse Registry

**Tables (006 contract):** `kb_parse_run`, `kb_parse_result`, `kb_parsed_artifact` — ORM-mapped with relationships.

**Note:** Denylist template lists `kb_parse_job`; that is **legacy init schema** (`sql/001_init_schema_v1_1.sql` L129). 006 registry UI must use **`kb_parse_run`** (`run_uid`, `parser_name`, `status`, counts, timestamps). No `KbParseJob` ORM exists.

**SELECT fields (plan-aligned):**

| Entity | Key columns for UI |
|---|---|
| `kb_parse_run` | `run_uid`, `parser_name`, `parser_adapter_version`, `parser_family`, `status`, `total_candidates`, `parsed_count`, `failed_count`, `started_at`, `finished_at`, `created_at` |
| `kb_parse_result` | `result_uid`, `run_uid`, `content_uid`, `sha256`, `status`, `parser_name`, `error_code`, `created_at` |
| `kb_parsed_artifact` | `artifact_uid`, `run_uid`, `content_uid`, `artifact_type`, `artifact_path`, `status` |

**Forbidden:** UPDATE parse status; trigger `register-parse-report`; invoke parsers.

**Migration:** **Not required** — 006 migration already applied in chain.

### 4.5 Quality Reports

**Data source:** Filesystem only under `config.storage.reports_root` — **no MySQL**.

**Discovered naming (008 / 009 services):**

| Artifact | Pattern | Producer |
|---|---|---|
| 008 quality report | `parse_quality_report_{YYYYMMDD}T{HHMMSS}Z.json` | `parse_quality_checker.py` |
| 009 summary MD | `parse_quality_summary_{timestamp}.md` | `parse_quality_report_summarizer.py` |
| 009 summary JSON | `parse_quality_summary_{timestamp}.json` | same |

009 input discovery uses `reports_root.glob("parse_quality_report_*.json")` with regex `^parse_quality_report_(\d{8}T\d{6}Z)\.json$`.

**Forbidden:** Invoke `check-parse-quality` or `summarize-quality-report`; auto-fix issues.

**Migration:** **Not required.**

### 4.6 Inventory Snapshot

**Tables:** `kb_file_instance`, `kb_file_content` — ORM-mapped. Optional: `kb_raw_vault_object` for vault metadata (no binary).

**Metadata-only columns:**

| Entity | Safe display columns |
|---|---|
| `kb_file_instance` | `file_instance_uid`, `source_path`, `file_name`, `sha256`, `content_uid`, `status`, `is_available`, `duplicate_group_uid`, timestamps |
| `kb_file_content` | `content_uid`, `sha256`, `vault_status`, `instance_count`, `master_file_instance_uid`, `parse_status`, `quality_status` |
| `kb_raw_vault_object` (optional) | `vault_uid`, `content_uid`, `sha256`, `vault_path`, `copy_status` — **path strings only** |

**Forbidden:**

- Open `vault_path` / `raw_vault/**/original.bin`
- Display binary content
- Move/delete/rename originals or trigger vault copy

**Migration:** **Not required.**

**P3 lock:** Include Inventory Snapshot **IN MVP** — data is available via existing ORM; no schema gap. Mark optional duplicate summary (`kb_duplicate_group`) as **OUT** unless P3 explicitly adds read-only counts.

---

## 5. Denylist / Write Boundary Review

### 5.1 Write denylist (MVP — all forbidden)

```text
kb_review_item          — NO WRITE (008-review-workflow scope)
kb_manual_correction      — NO WRITE
kb_embedding_ref          — NO WRITE
kb_task_log               — NO WRITE
kb_parse_job              — NO WRITE (legacy table; avoid entirely)
kb_parse_run              — NO WRITE
kb_parse_result           — NO WRITE
kb_parsed_artifact        — NO WRITE
kb_project                — NO WRITE
kb_project_document       — NO WRITE
kb_curated_asset          — NO WRITE
kb_document_chunk         — NO WRITE
kb_evidence               — NO WRITE
kb_file_instance          — NO WRITE
kb_file_content           — NO WRITE
kb_raw_vault_object       — NO WRITE
kb_document               — NO WRITE
```

Any MVP feature requiring INSERT/UPDATE/DELETE on the above → **P2 FAIL** → return to Tech Lead.

### 5.2 SELECT allowance by table (013 MVP)

| Table | SELECT in MVP? | Page / purpose |
|---|---|---|
| `kb_document` | Yes | Evidence JOIN; Search via SearchService |
| `kb_document_chunk` | Yes | Evidence Explorer |
| `kb_evidence` | Yes | Evidence Explorer; Search via SearchService |
| `kb_project` | Yes | Projects page; Search via SearchService |
| `kb_project_document` | Yes | Projects page; Search project filter (indirect) |
| `kb_curated_asset` | Yes | Projects page; Search via SearchService |
| `kb_parse_run` | Yes | Parse Registry |
| `kb_parse_result` | Yes | Parse Registry |
| `kb_parsed_artifact` | Yes | Parse Registry |
| `kb_file_instance` | Yes (optional page) | Inventory Snapshot |
| `kb_file_content` | Yes (optional page) | Inventory Snapshot |
| `kb_raw_vault_object` | Optional SELECT metadata | Inventory Snapshot — paths/status only |
| `kb_duplicate_group` | Optional | Not in P1 MVP pages — defer |
| `kb_review_item` | **No** | Not needed |
| `kb_manual_correction` | **No** | Not needed |
| `kb_embedding_ref` | **No** | Not needed |
| `kb_task_log` | **No** | Not needed |
| `kb_parse_job` | **No** | Legacy — use `kb_parse_run` |

---

## 6. SearchService Integration Review

### 6.1 Import path

```text
PYTHONPATH=backend
from app.services.search_service import SearchService
from app.core.config import load_config
from app.schemas.search import SearchQuery
```

Verified: module exists; `SearchService(config)` creates engine + session factory internally or accepts injected factory.

### 6.2 Recommended search path

```text
013 MVP search path = Streamlit UI → search_client.py → SearchService → existing DB/session layer
UI layer must not write MATCH ... AGAINST SQL directly.
```

### 6.3 Subprocess `search-kb`

**Not MVP default.** In-process import shares validation, DML guard, and 012 contract. Subprocess only as documented fallback if P3 approves.

### 6.4 New read-only adapter?

**Not strictly required.** Thin `search_client.py` wrapper is sufficient. Repository modules may use ORM `session.query()` / `select()` for non-search pages.

**No new backend repository service in `backend/app/services/**`** — 013 lib lives under `frontend/streamlit_admin/lib/` per plan.

### 6.5 SQL DML denylist guard

Present in `SearchService._assert_select_only()`. Non-search repositories must still use ORM SELECT or guarded read patterns — **P3 must forbid raw DML strings in frontend lib.**

---

## 7. SQLAlchemy Session Lifecycle Review

### 7.1 Reuse backend factories

```text
load_config() → AppConfig
create_db_engine(config) → Engine (pool_pre_ping=True)
create_session_factory(engine) → sessionmaker
```

Share **one engine / session factory** per Streamlit process via `st.cache_resource` (recommended) or app bootstrap singleton.

### 7.2 Streamlit rerun model

Streamlit reruns the script on interaction → **short-lived sessions per operation**:

```python
with session_factory() as session:
    rows = session.execute(select(...)).all()
# session closed on context exit — no global long-lived Session
```

**Do not** hold a module-level `Session` across reruns.

### 7.3 Avoid `session_scope` for read-only UI

`backend/app/core/database.py` `session_scope()` **commits on success**. For SELECT-only pages, prefer:

- `with session_factory() as session:` (SearchService pattern), or
- explicit `session.close()` without commit

Commits on read-only SELECT are unnecessary and violate mental model of SELECT-only MVP.

### 7.4 Caching

| Mechanism | Recommendation |
|---|---|
| `st.cache_resource` | Cache `AppConfig`, engine, session_factory — OK |
| `st.cache_data` | Cache query results with `ttl=` (e.g. 30–120s); key on query params |
| Sensitive paths | Do not cache raw `source_path` lists in shared multi-user deployment; local operator console is low risk |

Cached data may be **stale relative to DB** — acceptable for read-only browse; document in UI footer optional.

### 7.5 Error handling

Wrap DB access in page-level try/except:

- `sqlalchemy.exc.OperationalError` → operator message ("无法连接 MySQL …")
- `SearchValidationError` / `SearchProjectNotFoundError` → validation messages
- Do not crash entire app — `st.error()` + allow sidebar navigation (P1 G010)

### 7.6 P3 session constraints (locked)

```text
C-SESSION-1  One engine/session_factory per process (cache_resource).
C-SESSION-2  Per-interaction short-lived sessions; no global Session.
C-SESSION-3  Do not use session_scope() in Streamlit lib (avoid implicit commit).
C-SESSION-4  SearchService may own internal session; repositories use injected factory.
C-SESSION-5  P6 manual check: no connection pool exhaustion after repeated reruns (TC033).
```

---

## 8. curated_root / reports_root Path Review

### 8.1 Config contract (`config/app.yaml` / `app.example.yaml`)

```yaml
storage:
  curated_root: ./curated
  reports_root: ./reports
```

Loaded as absolute-resolved `Path` on `AppConfig.storage` via `load_config()`.

**P1 shorthand `config.reports_root` is incorrect** — must use `config.storage.reports_root`.

### 8.2 Curated path join rule

```text
allowed_root = config.storage.curated_root.resolve()
candidate = (allowed_root / curated_path_from_db).resolve()
require candidate.is_relative_to(allowed_root)  # Py3.11+
```

011 stores `curated_path` like `projects/{code}/00_project_card.md` — join is **`curated_root / curated_path`**, not `curated_root / projects / file` twice.

### 8.3 Reports discovery

```text
reports_root.glob("parse_quality_report_*.json")
reports_root.glob("parse_quality_summary_*.md")
reports_root.glob("parse_quality_summary_*.json")
```

Sort by `st_mtime` descending for "latest" picker.

Only open files whose resolved path is under `reports_root.resolve()`.

### 8.4 Path traversal protection (mandatory P3)

```text
1. Resolve allowed root to absolute Path.
2. Resolve candidate = (root / relative_from_db_or_glob).resolve()
3. Reject if not candidate.is_relative_to(root)
4. Reject if ".." in untrusted input
5. Never open arbitrary user-typed filesystem paths
```

### 8.5 Forbidden primary paths

```text
raw_vault/**/original.bin
parsed/**  (parsed_text.md, parsed_metadata.json, parse_manifest.json)
Arbitrary paths outside curated_root / reports_root
```

`kb_file_instance.source_path` may point anywhere on disk — **display as text only**; do not `open()` for preview in MVP.

---

## 9. Migration Requirement Assessment

| MVP item | Migration needed? | Reason |
|---|---|---|
| Search page | **NO** | Reuses 012 FULLTEXT indexes from `001_init_schema_v1_1.sql` |
| Evidence Explorer | **NO** | All columns exist on `kb_evidence` / chunk / document |
| Projects & Curated | **NO** | Project + curated tables complete; filesystem via config |
| Parse Registry | **NO** | `006_parse_registry_v1.sql` already defines run/result/artifact |
| Quality Reports | **NO** | Filesystem-only |
| Inventory Snapshot | **NO** | Instance/content/vault metadata columns exist |
| Streamlit session/cache/prefs | **NO** | Browser/session_state or in-process cache — not DB |
| Audit / search log table | **NO** | Explicitly deferred (NG017, 012 C4) |

**P2 migration verdict: NOT REQUIRED for 013 MVP.**

---

## 10. Global Hard Constraint Review

| Constraint | 013 MVP compliant? | Notes |
|---|---|---|
| No source-code KB analysis | Yes | Browse only existing KB tables/files |
| No move/delete/rename originals | Yes | No file actions in P1 |
| No auto-delete duplicates | Yes | No 003 execution |
| No raw_vault deletion | Yes | No vault writes |
| No semantic similarity / LLM | Yes | Keyword search via SearchService only |
| No vector / embedding writes | Yes | `kb_embedding_ref` denylisted |
| No parser calls | Yes | No parse buttons |
| No DB writes | Yes | SELECT-only |
| No pipeline CLI triggers | Yes | NG001 |
| Not 008-review-workflow | Yes | No review tables |
| No `kb_review_item` / `kb_manual_correction` writes | Yes | Denylisted |
| No parsed/curated/reports mutation | Yes | Read-only filesystem |

**No global hard constraint violations identified in P1 design.**

---

## 11. Known Test Baseline Risk

```text
FAILED backend/tests/test_mineru_pdf_parser.py::test_batch_content_uid_filter
RuntimeError: No file instances found for sha256=fea22a...
```

| Question | Assessment |
|---|---|
| Blocks P2 DB Review? | **No** — environment/fixture sensitivity in 007 MinerU tests; unrelated to 013 ORM/schema |
| Blocks P3 Implementation Gate? | **No** — P3 is spec/whitelist only |
| Blocks P4 implementation? | **Yes unless resolved** — acceptance A016 requires 001–012 regression pass |

**Recommendation:**

```text
Not blocking P2.
Must be resolved, quarantined, or explicitly waived before P4 implementation.
```

---

## 12. P2 Decision

### Status: **PASS WITH CONSTRAINTS**

013 MVP can be implemented as **SELECT-only** with existing schema, ORM models, `SearchService`, and read-only `curated_root` / `reports_root` access. **No migration.**

Repository state WARN (branch `main`, dirty worktree) does not invalidate the technical PASS but must be corrected before P4 merge hygiene.

---

## 13. Constraints Required for P3 Gate

Tech Lead must lock the following in `p3_implementation_gate.md`:

```text
C1   SELECT-only MVP — zero DML on all KB tables; no migration.
C2   Search path: in-process SearchService only; no UI FULLTEXT SQL; no default search-kb subprocess.
C3   Config: load_config(); use config.storage.curated_root and config.storage.reports_root.
C4   Curated files: resolve curated_root / kb_curated_asset.curated_path (not file_path column).
C5   Inventory paths: display kb_file_instance.source_path as metadata; never open file bytes.
C6   Parse Registry: kb_parse_run / kb_parse_result / kb_parsed_artifact only (not kb_parse_job).
C7   Quality Reports: glob parse_quality_report_*.json, parse_quality_summary_*.md/json under reports_root only.
C8   Path traversal guard on all filesystem reads (curated + reports).
C9   Session: cache_resource for engine/factory; short-lived sessions; no session_scope in lib.
C10  st.cache_data optional with TTL; document stale-read acceptable for browse UI.
C11  DB errors → st.error; app remains navigable.
C12  Inventory Snapshot: IN MVP (ORM sufficient); kb_duplicate_group summary OUT unless added explicitly.
C13  Denylist writes: kb_review_item, kb_manual_correction, kb_embedding_ref, kb_task_log, all registry/inventory/evidence/project tables.
C14  No raw_vault binary, no parsed primary reads, no parser/CLI triggers, no review workflow.
C15  pytest mineru batch_content_uid_filter: resolve/waive before P4.
C16  Branch hygiene: work on feature/013-streamlit-admin; commit P1 + P2 artifacts before P4.
C17  project_code filter: kb_project_document bridge (012 C7/C8) — do not use kb_evidence.project_uid.
C18  Optional content_uid / document_uid search filters: expose per 012 SearchQuery (P3 UI contract).
```

---

## 14. STOP

P2 DB / Data Review **complete**.

- **Do not enter P3** from this agent session.
- **Do not create** Streamlit code or modify `backend/**`.
- **Wait** for Tech Lead Agent to run P3 Implementation Gate after user confirmation.

---

*End of P2 DB Review — 013 Streamlit Admin*

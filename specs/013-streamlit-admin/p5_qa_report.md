# 013 Streamlit Admin — P5 QA Report

> Role: QA Agent  
> Spec: specs/013-streamlit-admin/  
> Branch: feature/013-streamlit-admin  
> Stage: P5 QA  
> Status: **FAIL**

---

## 1. Repository State

| Check | Expected | Actual | Verdict |
|---|---|---|---|
| Branch | `feature/013-streamlit-admin` | `feature/013-streamlit-admin` | **OK** |
| Working tree | clean | clean (no unstaged/untracked) | **OK** |
| P1–P3 commit | `482de65` | `482de65 spec(013): add streamlit admin P1-P3 gates` | **OK** |
| P4 commit | exists | `34b6695 feat(013): implement read-only streamlit admin MVP` | **OK** |
| Base | `main@1fb0947` | merge 012 on main | **OK** |

```text
34b6695 (HEAD -> feature/013-streamlit-admin) feat(013): implement read-only streamlit admin MVP
482de65 spec(013): add streamlit admin P1-P3 gates
1fb0947 (origin/main, main) merge: feature/012-search-service into main
```

---

## 2. P4 Whitelist / Blacklist Verification

**Command:** `git diff --name-only main..HEAD`

**Changed paths (28 files):**

```text
README.md
backend/requirements.txt
backend/tests/test_streamlit_admin_lib.py
docs/feature_index.md
frontend/streamlit_admin/**  (app, bootstrap, lib/*, pages/*)
specs/013-streamlit-admin/**  (P1 five-piece + p2 + p3)
specs/SPEC_INDEX.md
```

| Rule | Verdict |
|---|---|
| Only allowed paths touched | **OK** |
| No `backend/app/**` | **OK** |
| No `sql/**` / `backend/migrations/**` | **OK** |
| No `raw_vault/**` / `parsed/**` / `curated/**` / `reports/**` | **OK** |
| P1–P3 docs from `482de65` | **OK** |
| P4 implementation from `34b6695` | **OK** |

**P5 edits (this QA pass):**

```text
specs/013-streamlit-admin/p5_qa_report.md  (new)
backend/tests/test_streamlit_admin_lib.py  (+1 symlink escape test)
```

---

## 3. Static Boundary Scan

| Scan | Hits in implementation | Verdict |
|---|---|---|
| `MATCH ... AGAINST` / `AGAINST` | none | **OK** |
| subprocess / pipeline CLI (`search-kb`, `parse-*`, `check-parse-quality`, etc.) | none | **OK** |
| `session.add` / `commit` / `flush` / `session_scope` | none in `frontend/streamlit_admin/**`; test file only (assertion patterns) | **OK** |
| DML/DDL keywords (`INSERT`, `UPDATE`, …) | none in implementation; test file only (negative-assert patterns) | **OK** |
| `raw_vault` / `parsed/` as read paths | none | **OK** |
| `kb_review_item` / `kb_manual_correction` / `embedding` / `vector` | none | **OK** |
| Forbidden fields (`file_path`, `absolute_path`, `config.curated_root`, `config.reports_root`, `kb_parse_job`) | none in implementation; test asserts `kb_parse_job` absent | **OK** |

**Notes:**

- `db.py` uses `create_session_factory` only; pages use `with session_factory() as session:` — no implicit commit via `session_scope()`.
- Inventory displays `source_path` metadata only; no `open()` on user paths.
- Parse registry uses `KbParseRun` / `KbParseResult` / `KbParsedArtifact` only.

---

## 4. SearchService Integration Verification

| Check | Evidence | Verdict |
|---|---|---|
| `search_client.py` calls `SearchService` | `SearchService(config, session_factory=...)` → `service.search(sq)` | **OK** |
| UI uses `search_client` | `pages/search.py` imports `search_kb` | **OK** |
| `SearchQuery.validate_and_build` used | `search_client.py` L23–31 | **OK** |
| No UI FULLTEXT SQL | grep clean; test asserts `"MATCH" not in inspect.getsource(search_kb)` | **OK** |
| No `search-kb` subprocess | grep clean | **OK** |
| `search_service.py` unmodified | not in diff vs main | **OK** |

**Call path confirmed:**

```text
pages/search.py → lib/search_client.py → SearchService.search(SearchQuery)
```

---

## 5. DB SELECT-only Verification

| Layer | Method | Verdict |
|---|---|---|
| Repositories | SQLAlchemy `select()` only; no `session.add/commit/flush` | **OK** |
| Search | Delegated to sealed `SearchService` (012 `_assert_select_only`) | **OK** |
| DB bootstrap | `create_db_engine` + `create_session_factory`; no `session_scope()` | **OK** |
| Pages | Read via repositories / search_client; SQLAlchemyError → `st.error` | **OK** |

Static test coverage:

- `test_repository_module_has_no_write_patterns`
- `test_search_client_module_has_no_write_patterns`
- `test_page_modules_do_not_contain_db_writes`

---

## 6. Path Traversal Verification

**Implementation:** `lib/safe_paths.py`

| Scenario | Behavior | Test |
|---|---|---|
| Normal relative path under root | allowed | `test_resolve_under_root_accepts_relative_path` |
| `..` traversal | rejected | `test_resolve_under_root_rejects_dotdot` |
| Absolute path | rejected | `test_resolve_under_root_rejects_absolute_path` |
| Symlink pointing outside root | rejected via `resolve()` + `relative_to` (`path escapes root`) | `test_resolve_under_root_rejects_symlink` (P5 added) |
| Symlink inside root | rejected via explicit `is_symlink()` check | code present; no dedicated test |
| Curated markdown read | `read_text_under_root(config.storage.curated_root, curated_path)` | `test_curated_markdown_read_uses_safe_path` |
| Reports JSON/MD read | `read_text_under_root(reports_root, filename)` | via glob + reader tests |

**Note:** Symlink-to-outside is blocked before explicit symlink check because `.resolve()` follows the link and fails `relative_to(resolved_root)`. Security outcome is acceptable; error message differs from `"symlinks are not allowed"`.

**Suffix allowlist:** `.md`, `.json`, `.txt`, `.markdown` only for text reads.

---

## 7. Config / ORM Field Verification

| Required (P2/P3 lock) | Usage | Verdict |
|---|---|---|
| `config.storage.curated_root` | `repositories.read_curated_markdown`, `projects.py` error path | **OK** |
| `config.storage.reports_root` | `quality_reports.py`, report readers | **OK** |
| `KbCuratedAsset.curated_path` | `list_curated_assets`, `read_curated_markdown` | **OK** |
| `KbFileInstance.source_path` | `list_file_instances` display column | **OK** |
| `KbParseRun` (+ Result/Artifact) | `list_parse_runs`, `get_parse_run_detail` | **OK** |

| Forbidden | Found | Verdict |
|---|---|---|
| `config.curated_root` / `config.reports_root` | no | **OK** |
| `file_path` / `absolute_path` | no | **OK** |
| `kb_parse_job` ORM | no | **OK** |

---

## 8. MVP Page Verification

**Files under `frontend/streamlit_admin/pages/`:**

```text
evidence.py
inventory.py
parse_registry.py
projects.py
quality_reports.py
search.py
```

**Navigation in `app.py` (`st.navigation`):**

| MVP Page | Streamlit title | Module | Verdict |
|---|---|---|---|
| KB Search | KB 搜索 | `pages/search.py` | **OK** |
| Evidence Explorer | 证据浏览器 | `pages/evidence.py` | **OK** |
| Projects & Curated | 项目与 Curated | `pages/projects.py` | **OK** |
| Parse Registry | Parse Registry | `pages/parse_registry.py` | **OK** |
| Quality Reports | 质量报告 | `pages/quality_reports.py` | **OK** |
| Inventory Snapshot | Inventory Snapshot | `pages/inventory.py` | **OK** |

Additional UX:

- Search → Evidence drill-down via `st.switch_page("pages/evidence.py")` with `evidence_uid_filter` session state.
- App header shows read-only caption; init errors surfaced via `st.error`.

---

## 9. Tests Run

### 9.1 013 targeted tests

```bash
PYTHONPATH=backend backend/.venv/bin/pytest backend/tests/test_streamlit_admin_*.py -q
```

| Expected (P4) | Actual (P5) | Verdict |
|---|---|---|
| 13 passed | **14 passed** | **OK** (+1 symlink test) |

### 9.2 012 search regression

```bash
PYTHONPATH=backend backend/.venv/bin/pytest backend/tests/test_search_service.py -q
```

| Expected | Actual | Verdict |
|---|---|---|
| 32 passed | **32 passed** | **OK** |

### 9.3 Full backend suite

```bash
PYTHONPATH=backend backend/.venv/bin/pytest backend/tests -q
```

| Expected | Actual | Verdict |
|---|---|---|
| 291 passed | **291 passed** | **OK** |

**Historical risk `test_batch_content_uid_filter`:** not observed; full suite green.

### 9.4 P5 test delta

Added `test_resolve_under_root_rejects_symlink` — documents that symlink escape to outside root is rejected (via path-escape guard after `resolve()`).

---

## 10. Streamlit Smoke Result

### 10.1 Dependency check

```bash
backend/.venv/bin/pip show streamlit
# Version: 1.41.1

backend/.venv/bin/python -c "import streamlit; print(streamlit.__version__)"
# ImportError: cannot import name 'DEFAULT_EXCLUDED_CONTENT_TYPES'
#   from 'starlette.middleware.gzip'
```

Co-installed: `starlette==0.41.3` (via `fastapi==0.115.6`).

**Root cause:** `streamlit>=1.28,<1.42` resolves to 1.41.x which imports Starlette middleware symbols absent in starlette 0.41.3. Streamlit cannot import; CLI cannot start.

### 10.2 Smoke launch

```bash
PYTHONPATH=backend backend/.venv/bin/streamlit run frontend/streamlit_admin/app.py \
  --server.headless true --server.port 18501
```

**Result:** **FAIL** — process exits immediately with same `ImportError`. HTTP probe to `:18501` returned no response.

| Smoke criterion | Result |
|---|---|
| App starts | **FAIL** |
| 6-page navigation visible | **NOT REACHED** |
| MySQL error graceful degradation | **NOT REACHED** (import fails before runtime) |
| Normal config no crash | **NOT REACHED** |

Lib/module layer imports succeed in pytest (streamlit not imported in lib tests). Runtime launch blocked solely by dependency conflict.

---

## 11. Findings

### F1 — BLOCKER: Streamlit cannot start (dependency conflict)

- **Severity:** Blocker (P5 FAIL trigger)
- **Location:** `backend/requirements.txt` — `streamlit>=1.28,<1.42`
- **Detail:** Installed streamlit 1.41.1 incompatible with pinned starlette 0.41.3 from FastAPI.
- **Impact:** Documented launch command fails; operator cannot run admin UI.

### F2 — Non-blocker: Symlink error message inconsistency

- **Severity:** Low
- **Detail:** External symlink rejected via `"path escapes root"` rather than explicit `"symlinks are not allowed"`. Security outcome OK.
- **Action:** Optional UX/clarity improvement in P6+.

### F3 — Non-blocker: Smoke / E2E scope

- Full MySQL-connected page E2E intentionally deferred to P6 per stage rules.
- Once F1 fixed, P6 should verify navigation, DB pages, and error paths with real config.

### F4 — Positive: Implementation boundary compliance

- P4 whitelist/blacklist fully respected.
- SELECT-only, SearchService-only, path guards, and six MVP pages implemented as specified.
- All automated tests green (291 full + 14 targeted).

---

## 12. Required Fixes Before P6

| ID | Fix | Owner |
|---|---|---|
| R1 | **Resolve streamlit ↔ starlette pin conflict** so `streamlit run frontend/streamlit_admin/app.py` starts. Options: pin `streamlit<1.41` (pre-Starlette-integration), or add compatible `starlette` lower bound compatible with both FastAPI and Streamlit, then re-verify smoke. | Dev (fix pass) |
| R2 | Re-run P5 smoke after R1: headless start, 6 pages in sidebar, init error display when MySQL unavailable. | QA (re-run) |

No other P6 blockers identified in static review or unit tests.

---

## 13. QA Decision

**Decision: FAIL**

**Rationale:**

Implementation and test coverage meet P3/P4 contracts for read-only scope, SearchService integration, SELECT-only DB access, path traversal guards, config/ORM field usage, and six MVP pages. Full pytest suite (291) and 012 regression (32) pass.

**However**, P5 explicit FAIL criterion triggered:

> Streamlit app 无法启动

Smoke launch fails with `ImportError` (streamlit 1.41.1 vs starlette 0.41.3). This is a dependency specification defect introduced in P4 (`backend/requirements.txt`) and must be fixed before P6.

**After R1 fix:** expect re-run P5 smoke → likely **PASS WITH NOTES** (full DB E2E still P6).

---

## 14. STOP

P5 QA complete. **Do not proceed to P6/E2E/P7/P8.**

- No handoff written  
- No SPEC_INDEX update  
- No merge  
- No Streamlit implementation changes (fix pass requires user authorization)

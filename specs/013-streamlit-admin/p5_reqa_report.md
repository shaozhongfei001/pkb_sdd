# 013 Streamlit Admin — P5 Re-QA Report

> Role: QA Agent  
> Spec: specs/013-streamlit-admin/  
> Branch: feature/013-streamlit-admin  
> Stage: P5 Re-QA  
> Status: **PASS WITH NOTES**

---

## 1. Repository State

| Check | Expected | Actual | Verdict |
|---|---|---|---|
| Branch | `feature/013-streamlit-admin` | `feature/013-streamlit-admin` | **OK** |
| Working tree | clean | clean | **OK** |
| Fix commit | `9606167` | `9606167 fix(013): pin streamlit for smoke compatibility` (HEAD) | **OK** |
| Prior P5 | `5b6903b` | `5b6903b test(013): add P5 QA report FAIL` | **OK** |

```text
9606167 (HEAD -> feature/013-streamlit-admin) fix(013): pin streamlit for smoke compatibility
5b6903b test(013): add P5 QA report FAIL
34b6695 feat(013): implement read-only streamlit admin MVP
482de65 spec(013): add streamlit admin P1-P3 gates
```

---

## 2. Prior P5 Failure Recap

**Original blocker (P5 `p5_qa_report.md` — FAIL):**

```text
streamlit 1.41.1 + starlette 0.41.3
ImportError: cannot import name DEFAULT_EXCLUDED_CONTENT_TYPES from starlette.middleware.gzip
```

Streamlit CLI could not start; HTTP smoke unreachable. Implementation and unit tests were otherwise compliant.

---

## 3. P4 Fix Verification

**Fix commit `9606167` files:**

```text
backend/requirements.txt
specs/013-streamlit-admin/p4_fix_dependency_smoke_report.md
```

**Range `5b6903b..HEAD`:**

```text
backend/requirements.txt
specs/013-streamlit-admin/p4_fix_dependency_smoke_report.md
```

| Rule | Verdict |
|---|---|
| Only allowed fix paths | **OK** |
| No `frontend/streamlit_admin/**` | **OK** |
| No `backend/app/**` | **OK** |
| No `sql/**` / vault / parsed / curated / reports | **OK** |

**Pin change:**

```diff
-streamlit>=1.28,<1.42
+streamlit>=1.28,<1.41
```

Functional Streamlit code unchanged — dependency-only fix.

---

## 4. Dependency Version Verification

**Commands:**

```bash
backend/.venv/bin/pip install -r backend/requirements.txt
backend/.venv/bin/python -c "import streamlit, starlette; print(...)"
```

| Package | Version | Requirement | Verdict |
|---|---|---|---|
| streamlit | **1.40.2** | `>=1.28,<1.41` | **OK** |
| starlette | **0.41.3** | (via fastapi==0.115.6) | **OK** |
| click | **8.4.1** | (transitive via streamlit) | **NOTE** |

**Import check:**

```text
streamlit 1.40.2
starlette 0.41.3
streamlit pin check PASS
```

- `import streamlit` succeeds — no `DEFAULT_EXCLUDED_CONTENT_TYPES` ImportError.
- `Version(streamlit.__version__) < Version("1.41")` — **PASS**.

---

## 5. Streamlit Smoke Re-Test

**Launch:**

```bash
PYTHONPATH=backend backend/.venv/bin/streamlit run frontend/streamlit_admin/app.py \
  --server.headless true --server.port 18501
```

**Startup log:**

```text
You can now view your Streamlit app in your browser.
Local URL: http://localhost:18501
Network URL: http://192.168.71.5:18501
```

**HTTP probe:**

```bash
curl -I http://localhost:18501
# HTTP/1.1 200 OK
# Server: TornadoServer/6.5.7
# Content-Type: text/html
```

**Body:** Valid Streamlit HTML shell (`<title>Streamlit</title>`, `#root` div).

| Criterion | Result |
|---|---|
| No `DEFAULT_EXCLUDED_CONTENT_TYPES` ImportError | **PASS** |
| Process starts and stays running | **PASS** |
| HTTP 200 response | **PASS** |
| 6-page navigation / MySQL E2E | **NOT IN SCOPE** (P6) |

Process stopped after verification.

**Verdict: Smoke PASS** — P5 primary blocker resolved.

---

## 6. Whitelist / Blacklist Verification

Full branch diff vs `main` unchanged in scope from prior P5 except fix commit adds only `requirements.txt` pin tightening.

P5 Re-QA edits:

```text
specs/013-streamlit-admin/p5_reqa_report.md  (this file)
```

No implementation or dependency pin modifications by QA.

---

## 7. Static Boundary Scan

Re-run greps on `frontend/streamlit_admin/**` and `backend/tests/test_streamlit_admin_*.py`:

| Scan | Implementation hits | Verdict |
|---|---|---|
| `MATCH ... AGAINST` | none | **OK** |
| subprocess / pipeline CLI | none | **OK** |
| `session.add/commit/flush/session_scope` | none in app; test assertion strings only | **OK** |
| DML/DDL keywords | none in app; test negative-assert patterns only | **OK** |
| `raw_vault` / `parsed/` reads | none | **OK** |
| review / embedding / vector | none | **OK** |
| forbidden fields (`file_path`, `absolute_path`, `config.curated_root`, `kb_parse_job`) | none in app; test asserts `kb_parse_job` absent | **OK** |

**No new boundary violations** compared to initial P5. Dependency fix did not alter read-only contract.

---

## 8. SearchService Integration Verification

| Check | Verdict |
|---|---|
| `search_client.py` → `SearchService.search()` | **OK** |
| `SearchQuery.validate_and_build` | **OK** |
| `pages/search.py` → `search_kb` | **OK** |
| UI FULLTEXT SQL (`MATCH`/`AGAINST`) | none | **OK** |
| `search-kb` subprocess | none | **OK** |

Call path unchanged:

```text
pages/search.py → lib/search_client.py → SearchService.search(SearchQuery)
```

---

## 9. DB SELECT-only Verification

Unchanged from initial P5 (still compliant):

- Repositories use SQLAlchemy `select()` only.
- No `session_scope()` in Streamlit lib.
- Pages use `with session_factory() as session:` — read-only sessions.
- Static tests: `test_repository_module_has_no_write_patterns`, `test_page_modules_do_not_contain_db_writes`.

---

## 10. Path Traversal Verification

**`safe_paths.py`:** `resolve_under_root()` + `read_text_under_root()` unchanged.

| Read path | Guard | Verdict |
|---|---|---|
| Curated markdown | `read_text_under_root(config.storage.curated_root, curated_path)` | **OK** |
| Reports JSON/MD | `read_text_under_root(reports_root, filename)` | **OK** |
| User arbitrary paths | rejected (relative only; no absolute/`..`) | **OK** |

**Symlink test:** `test_resolve_under_root_rejects_symlink` present and passing (rejects via `symlink|escapes root`).

---

## 11. Tests Run

After `pip install -r backend/requirements.txt`:

### 11.1 013 targeted

```bash
PYTHONPATH=backend backend/.venv/bin/pytest backend/tests/test_streamlit_admin_*.py -q
```

| Expected | Actual | Verdict |
|---|---|---|
| 14 passed | **14 passed** | **OK** |

### 11.2 012 search regression

```bash
PYTHONPATH=backend backend/.venv/bin/pytest backend/tests/test_search_service.py -q
```

| Expected | Actual | Verdict |
|---|---|---|
| 32 passed | **31 passed, 1 failed** | **NOTE** |

**Failure:** `test_cli_help_documents_contract` — `Typer/Click` `Parameter.make_metavar()` TypeError on `search-kb --help`. SearchService functional tests (31 others) all pass. Excluding CLI help: **31 passed**.

### 11.3 Full backend suite

```bash
PYTHONPATH=backend backend/.venv/bin/pytest backend/tests -q
```

| Expected (Dev fix report) | Actual (Re-QA) | Verdict |
|---|---|---|
| 292 passed | **288 passed, 4 failed** | **NOTE** |

**Failures (all same root cause — CLI `--help` invocation):**

| Test | Module |
|---|---|
| `test_cli_help_documents_contract` | `test_evidence_chain.py` |
| `test_cli_parse_markitdown_help` | `test_markitdown_parser.py` |
| `test_cli_route_parsers_help` | `test_parser_router.py` |
| `test_cli_help_documents_contract` | `test_search_service.py` |

**Error:**

```text
TypeError: Parameter.make_metavar() missing 1 required positional argument: 'ctx'
```

**Root cause analysis:** `pip install -r backend/requirements.txt` resolves `click==8.4.1` (transitive from streamlit 1.40.2). `typer==0.15.1` (pinned) is incompatible with click 8.4.x for `--help` rendering. This is a **transitive dependency collision** from co-installing streamlit + typer, not a regression in Streamlit admin read-only code or SearchService logic.

**013-specific tests:** all green. **SearchService core:** all green except CLI help wrapper.

---

## 12. Findings

### F1 — RESOLVED: Streamlit startup blocker

- P5 FAIL trigger (`ImportError` / app cannot start) **no longer reproduces**.
- Smoke HTTP 200 confirmed independently.

### F2 — NOTE: typer ↔ click collision after fresh pip install

- **Severity:** Non-blocking for P6 Streamlit E2E entry (013 scope).
- **Detail:** 4 CLI `--help` contract tests fail when click 8.4.1 coexists with typer 0.15.1.
- **Impact:** Full suite 288/292; 013 targeted 14/14; SearchService logic 31/31.
- **Relation to 013:** Indirect — streamlit install pulls newer click; not Streamlit UI boundary regression.
- **Suggested P6 prep (optional fix pass):** pin `click>=8.0,<8.2` or upgrade typer to a click-8.4-compatible release; re-run full pytest.

### F3 — NOTE: P6 scope unchanged

- Real MySQL page navigation, DB error paths, and row-count idempotency remain P6 E2E.
- P5 Re-QA smoke confirms process launch only.

### F4 — Positive: Fix pass minimal and effective

- Single-line pin change; no implementation drift; boundaries intact.

---

## 13. Required Fixes Before P6

| ID | Item | Blocking P6? |
|---|---|---|
| — | Streamlit startup (`DEFAULT_EXCLUDED_CONTENT_TYPES`) | **Resolved** |
| N1 | Optional: resolve typer/click `--help` test failures for full 292-green CI | **No** — Streamlit E2E can proceed; recommend fix before merge if CI enforces full suite |
| — | P6 E2E: 6-page navigation, MySQL-connected pages, error degradation | **P6 scope** |

No P6 blockers from 013 read-only implementation or smoke.

---

## 14. QA Decision

**Decision: PASS WITH NOTES**

**Rationale:**

| Criterion | Result |
|---|---|
| Streamlit smoke passes | **YES** — HTTP 200, no ImportError |
| `DEFAULT_EXCLUDED_CONTENT_TYPES` gone | **YES** |
| Fix scope compliant | **YES** — only `requirements.txt` + fix report |
| SearchService-only unchanged | **YES** |
| SELECT-only unchanged | **YES** |
| Path traversal unchanged | **YES** — symlink test passes |
| 013 targeted tests | **YES** — 14/14 |
| Search regression (functional) | **YES** — 31/31 non-CLI tests |
| Full pytest | **NOTE** — 288/292 (4 CLI help; typer/click collision) |

Primary P5 FAIL condition is **resolved**. Remaining test gap is a transitive dependency ecosystem issue, not a 013 read-only boundary regression. **P6 E2E may proceed.**

---

## 15. STOP

P5 Re-QA complete. **Awaiting P6 E2E.**

- Do not enter P6 from this pass  
- No handoff  
- No SPEC_INDEX update  
- No merge  
- No implementation or dependency changes

# 013 Streamlit Admin — test_cases.md

> Project: `pkb_sdd`  
> Spec: `specs/013-streamlit-admin/`  
> Test owner: QA Agent (P5), E2E Agent (P6)  
> Current phase: P1 planning only — no tests implemented yet.

---

## 1. Test Strategy

013 tests must prove:

```text
1. Streamlit lib modules load config and perform read-only DB/filesystem operations.
2. KB Search page path calls SearchService with same semantics as CLI search-kb.
3. Evidence, project, registry repositories return traceable UIDs.
4. Curated and quality report readers are read-only.
5. Chinese query strings, Chinese content, and Chinese paths display correctly.
6. No parser invocation from UI or lib layer.
7. No raw_vault binary reads.
8. No parsed filesystem reads for MVP primary views.
9. No DB writes (row counts unchanged after UI/lib operations).
10. No review/embedding/registry/inventory writes.
11. 001–012 regression pass.
```

Recommended test file (P4/P5):

```text
backend/tests/test_streamlit_admin_lib.py
```

Fixtures:

```text
backend/tests/fixtures/streamlit_admin/
```

Lib tests import `frontend/streamlit_admin/lib/*` with PYTHONPATH including project root and backend. Fixture files must not pollute inventory scanner (non-document suffix, e.g. `.fixture`).

Streamlit page rendering: manual checklist in P5/P6 (automation optional if P3 approves).

---

## 2. Lib Unit Test Cases

### TC001 — config_loader loads app.yaml

Setup: temp config with mysql, reports_root, curated_root.

Expected: AppConfig fields populated; missing file raises clear error.

### TC002 — search_client delegates to SearchService

Setup: mock SearchService or fake session with seeded FULLTEXT row.

Expected: search_client returns SearchResponse; does not construct raw MATCH SQL.

### TC003 — search_client empty query

Expected: validation error before SearchService call.

### TC004 — evidence_repository list by document_uid

Setup: seeded kb_evidence + kb_document_chunk rows.

Expected: rows include evidence_uid, document_uid, content_uid, quote_text.

### TC005 — evidence_repository filter by evidence_uid

Expected: single row returned.

### TC006 — project_repository list projects

Setup: kb_project + kb_project_document rows.

Expected: project_code, project_name, document count metadata.

### TC007 — curated_reader renders Markdown file

Setup: temp curated_root/projects/DEMO/00_project_card.md.

Expected: file content read; path joined via kb_curated_asset.file_path rule (P3 lock).

### TC008 — curated_reader missing file

Expected: clear error dict/message; no write attempt.

### TC009 — registry_repository list parse runs

Setup: seeded kb_parse_run / kb_parse_result.

Expected: run_uid, status, parser_profile fields from DB columns only.

### TC010 — report_reader lists reports_root

Setup: temp reports_root with parse_quality_report.json and summary.md.

Expected: sorted file list by mtime; JSON/MD distinguishable.

### TC011 — report_reader malformed JSON

Expected: parse error surfaced; no CLI subprocess to regenerate.

### TC012 — inventory_repository metadata only

Setup: kb_file_instance with Chinese absolute_path.

Expected: path displayed; no open on raw_vault/original.bin.

### TC013 — Chinese search query via search_client

Query: Chinese tokens.

Expected: non-empty hits when fixture data exists; UTF-8 preserved.

### TC014 — formatters snippet truncation

Expected: long quote_text truncated for display without mutation.

---

## 3. No-side-effect Test Cases

### TC015 — No parser invocation

Monitor subprocess during lib calls and simulated page handlers.

Expected: no markitdown, mineru, magic_pdf, pipeline CLI subprocess.

### TC016 — No raw_vault read

Expected: no open on `raw_vault/**/original.bin`.

### TC017 — No parsed filesystem read (MVP lib paths)

Expected: no read of `parsed/**` artifact files from lib modules.

### TC018 — No DB writes

Count rows in chunk/evidence/project/curated/review/embedding/registry before and after lib test session.

Expected: counts unchanged.

### TC019 — No review_item write

Expected: `kb_review_item` count unchanged.

### TC020 — No embedding_ref write

Expected: `kb_embedding_ref` count unchanged.

### TC021 — No curated filesystem write

Expected: curated Markdown mtime/content unchanged after lib/UI session.

### TC022 — Original file protection

Expected: user original files unchanged (mtime/content).

---

## 4. Regression Test Cases

### TC023 — 001–012 pytest regression

Run full backend test suite with 013 changes.

Expected: all prior tests pass.

### TC024 — SearchService unchanged behavior

Run existing test_search_service.py.

Expected: pass without modification to search_service.py.

---

## 5. UI Manual / E2E Test Cases (P6)

### TC025 — Streamlit app launch

Command: `PYTHONPATH=backend streamlit run frontend/streamlit_admin/app.py`

Expected: app loads; sidebar shows MVP pages; no import error.

### TC026 — KB Search page E2E

Environment: MySQL with 010/011/012 sample data.

Action: enter Chinese query, scope=all, submit.

Expected: hits table with hit_type, snippet, UIDs.

### TC027 — Search to Evidence drill-down

Action: click evidence hit -> Evidence Explorer.

Expected: filtered evidence detail with matching evidence_uid.

### TC028 — Projects & Curated E2E

Action: select project; open curated asset.

Expected: Markdown rendered read-only; no save button.

### TC029 — Parse Registry E2E

Expected: recent parse runs listed; expanding shows result/artifact metadata.

### TC030 — Quality Reports E2E

Expected: latest 008 JSON and 009 summary listed and displayed; no CLI re-run.

### TC031 — Empty search query UI

Expected: warning message; no crash.

### TC032 — MySQL down graceful degradation

Expected: st.error on DB pages; app remains navigable.

### TC033 — Session rerun connection leak check (P6 note)

Action: multiple Streamlit reruns on Search page.

Expected: no connection pool exhaustion (manual observation / mysql processlist).

### TC034 — Inventory Snapshot optional page

If in MVP: counts and paginated instance table display.

If out of MVP: page absent or hidden per P3 gate.

---

## 6. P5 / P6 Exit Criteria

```text
Lib unit tests TC001–TC024 pass.
No-side-effect tests TC015–TC022 pass.
UI manual/E2E TC025–TC034 pass or documented BLOCKED with reason.
Regression TC023–TC024 pass.
p5_qa_report.md and p6_e2e_report.md produced.
```

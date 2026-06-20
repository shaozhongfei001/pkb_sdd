# 012 Search Service — test_cases.md

> Project: `pkb_sdd`  
> Spec: `specs/012-search-service/`  
> Test owner: QA Agent (P5), E2E Agent (P6)  
> Current phase: P1 planning only — no tests implemented yet.

---

## 1. Test Strategy

012 tests must prove:

```text
1. MySQL FULLTEXT keyword search returns traceable hits per scope.
2. scope=all merges tagged hits with pagination.
3. --project-code filter via kb_project_document (not evidence.project_uid).
4. Chinese query strings and Chinese indexed content.
5. Empty query rejected; no hits => empty list (not error).
6. No parser invocation.
7. No raw_vault / parsed / curated filesystem reads.
8. No DB writes (row counts unchanged after search).
9. No chunk/evidence/curated/review/embedding writes.
10. 001–011 regression pass.
```

Recommended test file (P4/P5):

```text
backend/tests/test_search_service.py
```

Fixtures:

```text
backend/tests/fixtures/search/
```

Fixtures use synthetic DB rows seeded in test MySQL (reuse 010/011 fixture patterns). Fixture files must not pollute inventory scanner (non-document suffix, e.g. `.fixture`).

---

## 2. Unit Test Cases

### TC001 — document scope title hit

Setup: `kb_document` row with Chinese title containing query token.

Query: `scope=document`, `--query` matching title.

Expected: hit with `hit_type=document`, `document_uid`, `content_uid`, snippet from title.

### TC002 — chunk scope content hit

Setup: `kb_document_chunk` with searchable `content`.

Expected: `hit_type=chunk`, `chunk_uid`, `document_uid`, `content_uid`.

### TC003 — evidence scope quote hit

Setup: `kb_evidence` with `quote_text` / `normalized_text`.

Expected: `hit_type=evidence`, `evidence_uid`, `document_uid`, `content_uid`.

### TC004 — project scope name hit

Setup: `kb_project` with Chinese `project_name`.

Expected: `hit_type=project`, `project_uid`, `project_code`.

### TC005 — curated scope asset_title hit

Setup: `kb_curated_asset` linked to project.

Expected: `hit_type=curated`, `curated_uid`, `project_uid`.

### TC006 — scope=all merge

Setup: rows in multiple scopes matching same query.

Expected: multiple hits with distinct `hit_type`; sorted by relevance.

### TC007 — empty query rejected

Query: `--query ""` or whitespace only.

Expected: validation error; no SQL executed; non-zero exit (CLI).

### TC008 — no matches

Query: token not present in any indexed row.

Expected: empty hits; `total_count=0`; success exit.

### TC009 — pagination limit/offset

Setup: many matching chunk rows.

Expected: first page size = limit; offset skips rows.

### TC010 — --project-code filter

Setup: two projects with documents; query matches both; filter one `project_code`.

Expected: only hits for documents in `kb_project_document` for that project.

### TC011 — project filter without evidence.project_uid

Setup: `kb_evidence.project_uid` NULL; mapping via `kb_project_document` only.

Expected: project filter still works for chunk/evidence hits.

### TC011b — --content-uid filter

Expected: only hits for specified `content_uid`.

### TC011c — --document-uid filter

Expected: only hits for specified `document_uid`.

### TC012 — Chinese query 中文检索

Query: Chinese tokens against Chinese indexed content.

Expected: non-empty hits when data exists; UTF-8 preserved in snippets.

### TC013 — JSON output format

`--format json`

Expected: valid JSON with hits array and pagination meta.

### TC014 — table output format

`--format table`

Expected: human-readable table; no crash on wide snippets.

### TC015 — optional --output file

Expected: JSON written to operator path; search still read-only.

---

## 3. No-side-effect Test Cases

### TC016 — No parser invocation

Monitor subprocess / imports during search.

Expected: no markitdown, mineru, magic_pdf, subprocess parse calls.

### TC017 — No raw_vault read

Expected: no open on `raw_vault/**/original.bin`.

### TC018 — No parsed filesystem read

Expected: no read of `parsed/**` artifact files.

### TC019 — No curated filesystem read (MVP)

Expected: no read of `curated/**` Markdown files for search text.

### TC020 — No DB writes

Count rows in chunk/evidence/project/curated/review/embedding before and after search.

Expected: counts unchanged.

### TC021 — No review_item write

Expected: `kb_review_item` count unchanged.

### TC022 — No embedding_ref write

Expected: `kb_embedding_ref` count unchanged.

### TC023 — Original file protection

Expected: user original files unchanged (mtime/content).

---

## 4. Regression Test Cases

### TC024 — 001–011 pytest regression

Run full backend test suite with 012 changes.

Expected: all prior tests pass.

### TC025 — 011 curated rows searchable

After `build-curated-project` fixture data, `scope=curated` finds asset_title.

Expected: curated hit with `curated_uid`.

### TC026 — 010 evidence rows searchable

After evidence fixture data, `scope=evidence` finds quote_text.

Expected: evidence hit with `evidence_uid`.

---

## 5. E2E Test Cases (P6)

### TC027 — Real MySQL FULLTEXT E2E

Environment: test MySQL with ngram FULLTEXT indexes applied.

Chain: existing 010/011 sample data → `search-kb` CLI.

Expected: documented scopes return hits; UIDs valid in DB.

### TC028 — Chinese E2E path

Query against real Chinese document title / evidence quote.

Expected: hit returned; snippet readable.

### TC029 — Project-scoped E2E

`--project-code` on real project with multiple documents.

Expected: filtered hits only from mapped documents.

### TC030 — Optional API E2E (if P3 locks API)

`GET /api/v1/search?q=...`

Expected: same hits as CLI for equivalent parameters.

---

## 6. P5 / P6 Exit Criteria

```text
All unit tests TC001–TC026 pass (API tests if applicable).
E2E TC027–TC030 pass or documented BLOCKED with reason.
No side-effect tests TC016–TC023 pass.
Regression TC024 pass.
p5_qa_report.md and p6_e2e_report.md produced.
```

# 011 Curated Project Assets — test_cases.md

> Project: `pkb_sdd`  
> Spec: `specs/011-curated-project-assets/`  
> Test owner: QA Agent (P5), E2E Agent (P6)  
> Current phase: P1 planning only — no tests implemented yet.

---

## 1. Test Strategy

011 tests must prove:

```text
1. Evidence + registry metadata → curated Markdown files + DB rows.
2. kb_project / kb_project_document / kb_curated_asset upsert idempotency.
3. UID traceability in every MVP curated file.
4. Chinese project names / paths / UTF-8 content.
5. Missing evidence → partial output with warning, batch continues.
6. No parser invocation.
7. No raw_vault binary read.
8. parsed files not modified (if read).
9. No chunk/evidence/review/embedding writes.
10. 001–010 regression pass.
```

Recommended test file (P4/P5):

```text
backend/tests/test_curated_project_assets.py
```

Fixtures:

```text
backend/tests/fixtures/curated_project/
```

Fixtures use synthetic DB rows + optional manifest YAML; reuse 010 evidence fixture patterns where possible. Fixture files must not pollute inventory scanner (non-document suffix, e.g. `.fixture`).

---

## 2. Unit Test Cases

### TC001 — Manifest project → kb_project upsert

Setup: manifest YAML with project_code, project_name.

Expected: kb_project row with stable project_uid; project_code UNIQUE respected.

### TC002 — Document mapping → kb_project_document

Setup: manifest documents[] with content_uid + document_uid.

Expected: mapping rows with uk_project_document idempotency.

### TC003 — Evidence index file generation

Setup: kb_evidence + kb_document_chunk rows for mapped content.

Expected: `10_evidence_index.md` lists evidence_uid, document_uid, content_uid, locators.

### TC004 — Project card generation

Expected: `00_project_card.md` contains project metadata and document/evidence counts.

### TC005 — Source documents generation

Expected: `source_documents.md` lists document_uid, content_uid, parser metadata from registry.

### TC006 — kb_curated_asset registration

Expected: one row per MVP asset_type with curated_path and related_*_uids JSON.

### TC007 — Idempotent re-run

Run build twice without --force.

Expected: same row counts; curated files not overwritten (or updated_at unchanged per P3 policy).

### TC008 — --force overwrite

Expected: files rewritten; kb_curated_asset updated_at changes; no duplicate curated_uid.

### TC009 — Chinese project_name and paths

project_name and curated_path under Chinese directory segments.

Expected: read + write success (UTF-8).

### TC010 — Missing evidence for content_uid

Expected: source_documents written; evidence_index partial/empty with logged warning; batch continues.

### TC011 — Missing kb_document

Expected: skip mapping; error logged; batch continues.

### TC012 — dry-run mode

Expected: no curated files written; no DB rows written; plan counts returned.

### TC013 — filter --content-uid

Expected: only matching documents in curated output.

### TC014 — filter --limit

Expected: at most N documents processed.

### TC015 — generation_method

Expected: kb_curated_asset.generation_method = TEMPLATE_RULE.

---

## 3. No-side-effect Test Cases

### TC016 — No parser invocation

Patch MarkItDownParserService, MineruPdfParserService.

Expected: not called.

### TC017 — No raw_vault binary read

Spy open/read on paths containing `original.bin` under raw_vault.

Expected: not called for text extraction.

### TC018 — parsed artifacts not modified

If parsed read occurs, capture mtime/hash before/after.

Expected: unchanged.

### TC019 — Original user files unchanged

Expected: no touch outside curated write + DB write.

### TC020 — No chunk/evidence write

Expected: kb_document_chunk and kb_evidence row counts unchanged by 011 build.

### TC021 — No review_item write

Expected: kb_review_item not inserted.

### TC022 — No embedding_ref write

Expected: kb_embedding_ref not inserted.

### TC023 — UID traceability in Markdown

Parse generated files; every knowledge table row must include at least one of evidence_uid / document_uid / content_uid.

Expected: pass for MVP assets.

---

## 4. DB / Idempotency Tests

### TC024 — project_uid uniqueness enforced

Duplicate project_code handled by upsert policy.

### TC025 — curated_uid uniqueness enforced

Duplicate asset_type + version handled by upsert/skip policy.

### TC026 — uk_project_document enforced

Re-mapping same document to same project does not duplicate rows.

### TC027 — ORM field mapping

Inserted row columns match P2 approved mapping.

---

## 5. Integration Tests (P5)

### TC028 — build after build-evidence-chain fixture

Setup: run evidence chain on MarkItDown fixture, then curated build.

Expected: evidence_index references fixture evidence_uid values.

### TC029 — MinerU evidence fixture (optional)

Expected: page_no appears in evidence_index when 010 populated page_no.

### TC030 — Multi-document project

Manifest with 2+ content_uids.

Expected: all documents in source_documents; evidence_index aggregated.

---

## 6. E2E Test Cases (P6)

### TC031 — Full chain E2E (dev sample)

```text
scan → copy-to-vault → parse → register → build-evidence-chain → build-curated-project
```

Expected: curated files under curated_root; kb_curated_asset rows; UID traceability verified.

### TC032 — dry-run E2E

Expected: 0 curated files; 0 new DB rows.

### TC033 — Re-run idempotency E2E

Expected: second run without --force skips or no-ops cleanly.

---

## 7. Regression Scope

```text
backend/tests/test_inventory_scanner.py
backend/tests/test_file_content_vault.py
backend/tests/test_duplicate_governance.py
backend/tests/test_parser_router.py
backend/tests/test_markitdown_parser.py
backend/tests/test_parse_job_registry.py
backend/tests/test_mineru_pdf_parser.py
backend/tests/test_parse_quality_checker.py
backend/tests/test_parse_quality_report_summarizer.py
backend/tests/test_evidence_chain.py
```

All must pass after 011 P4 merge.

---

## 8. P5 Exit Criteria

```text
All TC001–TC030 automated in pytest (or documented manual E2E for TC031–TC033)
001–010 regression green
P5 report written to specs/011-curated-project-assets/p5_qa_report.md
```

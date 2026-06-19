# 010 Evidence Chain — test_cases.md

> Project: `pkb_sdd`  
> Spec: `specs/010-evidence-chain/`  
> Test owner: QA Agent (P5), E2E Agent (P6)  
> Current phase: P1 planning only — no tests implemented yet.

---

## 1. Test Strategy

010 tests must prove:

```text
1. Parsed artifact ingestion → chunk + evidence DB rows.
2. Idempotent re-run.
3. MarkItDown section chunking path.
4. MinerU page/bbox path when metadata present (fixture).
5. Chinese paths and UTF-8 content.
6. Missing parsed file → skip with error, batch continues.
7. No parser invocation.
8. No raw_vault binary read.
9. parsed files not modified.
10. 001–009 regression pass.
```

Recommended test file (P4/P5):

```text
backend/tests/test_evidence_chain.py
```

Fixtures:

```text
backend/tests/fixtures/parsed_evidence_markitdown/
backend/tests/fixtures/parsed_evidence_mineru/
```

Fixtures use synthetic parsed trees; must not require live MinerU subprocess.

---

## 2. Unit Test Cases

### TC001 — MarkItDown parsed → chunks

Setup: fixture with headings in parsed_text.md, kb_document row.

Expected: kb_document_chunk rows with chunk_level=section; chunk_index stable.

### TC002 — Evidence rows linked to chunks

Expected: kb_evidence rows with quote_text, source_char_start/end, content_uid, document_uid.

### TC003 — Idempotent re-run

Run build twice on same fixture.

Expected: same row counts; no duplicate chunk_uid/evidence_uid.

### TC004 — Chinese path

Path contains `/资料/项目/文档/parsed_text.md`.

Expected: read + write success.

### TC005 — Missing parsed_text.md

Expected: error logged; batch continues; no partial corrupt rows.

### TC006 — Invalid parsed_metadata.json

Expected: handled per P3 policy (skip or fallback); no crash.

### TC007 — MinerU page metadata fixture

Expected: page_no populated when metadata provides pages.

### TC008 — bbox JSON when present

Expected: evidence.metadata or bbox column populated from manifest/metadata.

### TC009 — dry-run mode (if implemented)

Expected: no DB rows written; plan counts returned.

### TC010 — filter --content-uid

Expected: only matching document processed.

### TC011 — filter --sha256

Expected: only matching content processed.

### TC012 — filter --limit

Expected: at most N documents processed.

---

## 3. No-side-effect Test Cases

### TC013 — No parser invocation

Patch MarkItDownParserService, MineruPdfParserService.

Expected: not called.

### TC014 — No raw_vault binary read

Spy open/read on paths containing `original.bin` under raw_vault.

Expected: not called for text extraction.

### TC015 — parsed artifacts not modified

Capture parsed file mtime/hash before/after.

Expected: unchanged.

### TC016 — Original user files unchanged

Expected: no touch outside parsed read + DB write.

### TC017 — No curated write

Spy writes under curated_root.

Expected: none in MVP.

### TC018 — No review_item write

Expected: kb_review_item not inserted.

---

## 4. DB / Idempotency Tests

### TC019 — chunk_uid uniqueness enforced

Duplicate insert attempt handled by upsert/skip policy.

### TC020 — evidence_uid uniqueness enforced

Same as TC019 for evidence.

### TC021 — ORM field mapping

Inserted row columns match P2 approved mapping.

---

## 5. Regression Test Cases

### TC022 — 001–009 regression

```bash
PYTHONPATH=backend pytest backend/tests/test_inventory_scanner.py \
  backend/tests/test_file_content_vault.py \
  backend/tests/test_duplicate_governance.py \
  backend/tests/test_parser_router.py \
  backend/tests/test_markitdown_parser.py \
  backend/tests/test_parse_job_registry.py \
  backend/tests/test_mineru_pdf_parser.py \
  backend/tests/test_parse_quality_checker.py \
  backend/tests/test_parse_quality_report_summarizer.py
```

Expected: pass.

---

## 6. E2E Test Cases (P6)

### TC023 — Real parsed sample → evidence

Setup: COPIED content with valid parsed artifacts in real environment.

Command:

```bash
PYTHONPATH=backend python -m app.cli.main build-evidence-chain \
  --config config/app.yaml \
  --content-uid <uid>
```

Expected:

```text
chunk rows created
evidence rows created
parsed mtimes unchanged
DB row counts for non-target tables unchanged (sanity)
```

---

## 7. Minimum P5 QA Evidence

```text
010 targeted tests: N passed
001–009 regression: N passed
idempotency test: passed
no parser test: passed
parsed immutability test: passed
```

---

## 8. Minimum P6 E2E Evidence

```text
CLI command used
content_uid / sha256 tested
chunk count / evidence count
parsed mtime check
optional DB sanity for sealed tables
```

# 010 Evidence Chain — plan.md

> Project: `pkb_sdd`  
> Phase: `P1 Tech Lead Plan — COMPLETE (awaiting user review)`  
> Status: `ACTIVE SPEC / NOT IMPLEMENTED`  
> Implementation status: `NOT STARTED (P4 blocked until P1–P3 approved)`

---

## 1. Architecture Overview

010 adds an evidence builder that consumes parsed outputs and registry metadata:

```text
parsed_text.md + parsed_metadata.json + parse_manifest.json
        +
kb_document / kb_parse_result (SELECT)
        |
        v
EvidenceChainService                    [P4]
        |
        v
kb_document_chunk + kb_evidence (INSERT/UPSERT idempotent)
```

Proposed component (P4 — not implemented in P1):

```text
backend/app/services/evidence_chain.py
```

Proposed ORM (P2/P4 — verify in P2):

```text
backend/app/models/document.py          # KbDocument exists
backend/app/models/evidence.py          # KbDocumentChunk, KbEvidence (new, if missing)
```

Proposed CLI (P4):

```text
backend/app/cli/main.py                 # register build-evidence-chain
```

Proposed tests (P5):

```text
backend/tests/test_evidence_chain.py
```

---

## 2. Logical Flow

```text
1. Load config (parsed_root, pipeline_version).
2. Select candidate documents from kb_document (+ optional filters).
3. Resolve parsed artifact paths from manifest / kb_document paths.
4. Read parsed_text.md (UTF-8) and parsed_metadata.json.
5. Build chunk plan (section/page levels per parser metadata).
6. For each chunk, compute char offsets, heading_path, page_no/slide_no if known.
7. Insert or upsert kb_document_chunk rows (idempotent).
8. Insert or upsert kb_evidence rows linked to chunks (idempotent).
9. Log per-content success/failure; continue batch on single failure.
10. Return summary counts.
```

No step may invoke parsers, read raw_vault binaries, write curated/, or modify parsed files.

---

## 3. Service Design (Planned — P4)

### 3.1 Proposed Class

```python
class EvidenceChainService:
    def __init__(self, config: AppConfig, session_factory) -> None: ...

    def build(
        self,
        *,
        content_uid: str | None = None,
        sha256: str | None = None,
        parser_name: str | None = None,
        limit: int | None = None,
        dry_run: bool = False,
    ) -> EvidenceChainBuildResult:
        ...
```

P3 finalizes signatures.

### 3.2 Internal Concepts

```text
EvidenceChainBuildResult
  documents_processed, chunks_written, evidence_written, errors[]

ChunkPlan
  chunk_uid, chunk_index, chunk_level, heading_path, start_offset, end_offset, content

EvidencePlan
  evidence_uid, chunk_uid, quote_text, source_location, page_no, bbox, ...
```

---

## 4. Parser-specific Chunk Strategy (P3 lock)

| parser_name | Primary strategy | page_no / bbox |
|---|---|---|
| `markitdown` | Markdown heading sections + optional document chunk | Usually null page/bbox |
| `mineru` | Page-level chunks when parsed_metadata exposes pages | bbox/page when manifest/metadata provides |

MVP does **not** require OCR-quality bbox for MarkItDown office files.

---

## 5. Config Usage

010 reads:

```text
config.storage.parsed_root
config.pipeline_version
config.mysql (connection via standard session factory — P4)
```

010 must not read/write:

```text
curated_root for feature output (MVP)
raw_vault binaries
reports_root for 008/009 auto-consumption (MVP)
```

---

## 6. Idempotency (Planned — P2 must confirm keys)

Design intent:

```text
Re-run build-evidence-chain on same content_uid + same parsed hash
=> same chunk_uid / evidence_uid set OR upsert without duplicate rows
```

P2 must map design to actual SQL unique keys:

```text
kb_document_chunk.chunk_uid UNIQUE
kb_evidence.evidence_uid UNIQUE
kb_document.uk_document_profile (content_uid, parser_profile, pipeline_version)
```

If init schema lacks required uniqueness for idempotent upsert, P2 stops for migration design.

---

## 7. Dev File Whitelist Preview (P3 reference)

**Allowed (P4):**

```text
backend/app/services/evidence_chain.py              # new
backend/app/models/evidence.py                      # new if P2 approves
backend/app/models/document.py                      # extend only if P2 approves
backend/app/cli/main.py
backend/tests/test_evidence_chain.py                # new
backend/tests/fixtures/parsed_evidence_*/            # synthetic parsed samples
```

**Forbidden:**

```text
backend/app/services/inventory_scanner.py
backend/app/services/file_content_vault.py
backend/app/services/markitdown_parser.py
backend/app/services/mineru_pdf_parser.py
backend/app/services/parse_registry.py              # no write-path changes
backend/app/services/parse_quality_checker.py
backend/app/services/parse_quality_report_summarizer.py
sql/** without approved migration
raw_vault/** parsed/** curated/** (no mutation)
```

---

## 8. Exception Handling

| Scenario | Handling |
|---|---|
| parsed_text.md missing | Log error; skip content; continue batch |
| Invalid JSON metadata | Log error; skip or partial chunk fallback (P3 lock) |
| kb_document missing | Skip with clear error |
| DB constraint violation | Fail transaction for that content; continue batch |
| Chinese path read | Must succeed (UTF-8) |

---

## 9. P2 DB Review Checklist (Mandatory before P4)

```text
[ ] kb_document_chunk exists in init SQL — column list documented
[ ] kb_evidence exists in init SQL — column list documented
[ ] ORM models exist or approved new models with field mapping table
[ ] Idempotency keys identified and testable
[ ] No invented columns vs sql/001_init_schema_v1_1.sql
[ ] Migration need assessed — if yes, STOP P4 until migration merged
[ ] DB write scope limited to chunk/evidence tables (MVP)
```

---

## 10. P1 Deliverables Checklist

```text
[x] spec.md
[x] plan.md
[x] tasks.md
[x] acceptance.md
[x] test_cases.md
[x] SPEC_INDEX.md updated (010 ACTIVE / PLANNED)
[x] README.md drift fixed
[ ] backend/** implementation        # out of P1 scope
[ ] STOP — await user P1 review
```

---

## 11. P1 STOP

No P2/P3/P4 until user approves P1.

No `backend/**` changes in P1.

# 010 Evidence Chain — P3 Implementation Gate

> Role: Tech Lead Agent  
> Spec: `specs/010-evidence-chain/`  
> Branch: `feature/010-evidence-chain`  
> Stage: P3 Implementation Gate  
> P2 base: `a48b25e` (PASS WITH CONSTRAINTS)  
> Status: **P3-GATE PASS — P4 BLOCKED until user confirms**

---

## 1. Gate Conclusion

P3 Implementation Gate: **PASS**

010 Evidence Chain is approved to enter **P4 Dev Implementation** after explicit user confirmation.

P2 constraints C1–C8 remain locked. No schema migration for MVP.

---

## 2. P4 Dev File Whitelist

Dev Agent may **create or modify only**:

```text
backend/app/services/evidence_chain.py                    # NEW — core builder
backend/app/models/evidence.py                            # NEW — KbDocumentChunk, KbEvidence
backend/app/cli/main.py                                   # register build-evidence-chain
backend/tests/test_evidence_chain.py                      # NEW
backend/tests/fixtures/evidence_chain_markitdown/         # NEW — synthetic parsed tree (optional dir)
backend/tests/fixtures/evidence_chain_mineru/             # NEW — synthetic parsed tree (optional dir)
```

**Model import note:** This repo has **no** `backend/app/models/__init__.py`. Import new models directly:

```python
from app.models.evidence import KbDocumentChunk, KbEvidence
```

Do **not** create `models/__init__.py` unless P4 discovers a hard blocker — if so, STOP and return to TL.

**Read-only reference (do not modify):**

```text
backend/app/core/parsed_paths.py
backend/app/models/document.py                            # KbDocument SELECT only
backend/app/models/parse_registry.py                      # SELECT only
backend/app/models/file.py
```

---

## 3. P4 Forbidden Files (Black List)

Dev Agent must **not** modify:

```text
backend/app/services/parse_registry.py
backend/app/services/parse_quality_checker.py
backend/app/services/parse_quality_report_summarizer.py
backend/app/services/markitdown_parser.py
backend/app/services/mineru_pdf_parser.py
backend/app/services/parser_router.py
backend/app/services/file_content_vault.py
backend/app/services/inventory_scanner.py
backend/app/services/duplicate_governance.py
backend/app/adapters/**
backend/app/models/document.py                            # KbDocument — no column changes
backend/app/models/parse_registry.py
backend/app/models/file.py
backend/app/models/vault.py
backend/app/models/duplicate.py
backend/app/core/database.py                              # no change unless TL approves (default: no)
backend/app/core/vault_paths.py
sql/**
backend/migrations/**
config/app.yaml
config/parser_rules.yaml
raw_vault/**
parsed/**
curated/**
specs/SPEC_INDEX.md
docs/handoff-*.md
README.md
```

### 3.1 Forbidden Behavior

```text
- Invoke MarkItDown / MinerU / magic-pdf / subprocess parse
- Read raw_vault original.bin for text extraction
- Modify parsed artifact files
- UPDATE/INSERT/DELETE kb_document
- Write parse registry tables (kb_parse_run, kb_parse_result, kb_parsed_artifact)
- Write kb_review_item, kb_curated_asset, kb_embedding_ref
- Consume or auto-fix 008/009 quality reports
- LLM / semantic chunking / embedding / summarization
- Schema migration or sql/**
- Move/delete/rename original user files
```

---

## 4. CLI Contract (Final — P4)

### 4.1 Command

```bash
PYTHONPATH=backend python -m app.cli.main build-evidence-chain \
  --config config/app.yaml \
  --content-uid <uid> \
  --sha256 <hash> \
  --limit 100 \
  --dry-run \
  --force \
  --output /path/to/evidence_build_report.json
```

### 4.2 Parameters

| Flag | Required | Default | Behavior |
|---|---|---|---|
| `--config` | No | `config/app.yaml` | Load `parsed_root`, `pipeline_version`, mysql |
| `--content-uid` | No | null | Process single content |
| `--sha256` | No | null | Process single content by hash |
| `--limit` | No | null | Max documents/candidates to process (≥1) |
| `--dry-run` | No | false | **Zero DB write**; plan + counts only |
| `--force` | No | false | Re-process even when chunk UIDs exist; still upsert idempotently |
| `--output` | No | null | Optional JSON build report path |

**Filter rule:** If both `--content-uid` and `--sha256` set, both must match same content or exit 1.

**Candidate selection (P4):**

```text
1. Query kb_parse_result (+ join kb_document when helpful) for SUCCESS/EMPTY with manifest_path.
2. Prefer manifest + on-disk parsed artifacts over kb_document profile filter alone (P2 C7).
3. Skip rows with missing parsed_text.md — log warning, continue batch.
```

### 4.3 `--dry-run` contract

```text
- May SELECT kb_document, kb_parse_result, kb_file_content.
- May READ parsed_text.md, parsed_metadata.json, parse_manifest.json.
- Must NOT INSERT/UPDATE/DELETE any table.
- Must NOT open write session.commit() for feature writes.
- Output: stdout summary + optional --output JSON report with planned counts.
```

### 4.4 `--output` report schema (when provided)

```json
{
  "report_type": "evidence_build_report",
  "schema_version": "1.0",
  "mode": "build",
  "generated_at": "<ISO8601 Z>",
  "dry_run": false,
  "filters": {
    "content_uid": null,
    "sha256": null,
    "limit": null
  },
  "summary": {
    "candidates_selected": 0,
    "documents_processed": 0,
    "documents_skipped": 0,
    "chunks_planned": 0,
    "chunks_upserted": 0,
    "evidence_planned": 0,
    "evidence_upserted": 0,
    "errors": 0
  },
  "errors": []
}
```

Default report path (if `--output` omitted but report requested in P4 — optional):

```text
{reports_root}/evidence_build_report_{YYYYMMDDTHHMMSSZ}.json
```

P3 lock: **report file write is allowed**; it is not a DB write. Report must not mutate parsed/raw_vault.

### 4.5 Exit codes

| Code | Condition |
|---|---|
| **0** | Completed (possibly with per-item skips logged) |
| **1** | Config error, invalid args, DB connection failure, fatal runtime error |
| **2** | Reserved — not used in MVP unless P4 documents partial-failure policy |

### 4.6 Forbidden CLI flags

```text
--fix  --repair  --reparse  --write-db  --write-curated
--markitdown  --mineru  --magic-pdf
--check-parse-quality  --summarize-parse-quality
--llm  --embed  --semantic-chunk
```

### 4.7 CLI help text (required)

```text
Build evidence chain records from parsed artifacts.
Reads parsed_text.md / metadata / manifest (read-only).
Writes kb_document_chunk and kb_evidence only.
Does not call parsers, read raw_vault binaries, or repair quality issues.
Use --dry-run for zero DB writes.
```

---

## 5. DB Write Contract (Final)

### 5.1 Allowed writes

| Table | Operations | Notes |
|---|---|---|
| `kb_document_chunk` | INSERT … ON DUPLICATE KEY UPDATE | Upsert on `chunk_uid` UNIQUE |
| `kb_evidence` | INSERT … ON DUPLICATE KEY UPDATE | Upsert on `evidence_uid` UNIQUE |

### 5.2 Forbidden writes

```text
kb_document                 — SELECT only; no UPDATE/INSERT/DELETE
kb_parse_run                — no write
kb_parse_result             — no write
kb_parsed_artifact          — no write
kb_file_content             — no write
kb_review_item              — no write
kb_curated_asset            — no write
kb_embedding_ref            — no write
Any other table             — no write
sql/** / migrations         — no change
```

### 5.3 Idempotency (locked)

**Deterministic UID generation:**

```python
# chunk_uid — CHAR(64) hex sha256
payload = f"chunk|v1|{content_uid}|{document_uid}|{chunk_index}|{content_hash}"
chunk_uid = sha256(payload.encode("utf-8")).hexdigest()

# evidence_uid
payload = f"evidence|v1|{chunk_uid}|{source_char_start}|{source_char_end}|{evidence_type}"
evidence_uid = sha256(payload.encode("utf-8")).hexdigest()
```

**content_hash** = SHA256 of chunk text UTF-8 bytes (or parsed_text slice).

**Upsert policy:**

```text
ON DUPLICATE KEY UPDATE
  update mutable fields (content, offsets, heading_path, page_no, bbox, metadata, quote_text)
  preserve chunk_uid / evidence_uid
  do not create second row
```

**Re-run test:** Same parsed input → same row count; same UIDs.

**`--force`:** Recompute and upsert-overwrite; still no duplicate UID rows.

---

## 6. ORM Contract (Final)

### 6.1 New file: `backend/app/models/evidence.py`

```python
class KbDocumentChunk(Base):
    __tablename__ = "kb_document_chunk"
    # Map 1:1 to sql/001_init_schema_v1_1.sql columns
    # content column maps Python attribute `content` -> DB `content`
    # metadata -> metadata JSON column

class KbEvidence(Base):
    __tablename__ = "kb_evidence"
    # Map 1:1 to init SQL; metadata JSON column
```

### 6.2 Rules

```text
1. Add KbDocumentChunk + KbEvidence only.
2. Do NOT modify KbDocument class or table mapping.
3. Do NOT modify KbParseRun / KbParseResult / KbParsedArtifact.
4. Do NOT invent undocumented columns — map exactly to init SQL.
5. parser_name / parser_adapter_version NOT stored on chunk/evidence columns;
   store in metadata JSON if needed, or join kb_document at read time.
```

### 6.3 Column mapping reminders

| Python / service | DB column |
|---|---|
| chunk text | `kb_document_chunk.content` |
| char offsets (chunk) | `start_offset`, `end_offset` |
| char offsets (evidence) | `source_char_start`, `source_char_end` |
| parser adapter version | `kb_document.parser_version` (read) or manifest |

---

## 7. Service Contract (Final — P4)

```python
@dataclass
class EvidenceChainBuildResult:
    candidates_selected: int
    documents_processed: int
    documents_skipped: int
    chunks_upserted: int
    evidence_upserted: int
    errors: list[str]
    report_path: Path | None = None

class EvidenceChainService:
    def __init__(self, config: AppConfig, session_factory) -> None: ...

    def build(
        self,
        *,
        content_uid: str | None = None,
        sha256: str | None = None,
        limit: int | None = None,
        dry_run: bool = False,
        force: bool = False,
        output: Path | None = None,
    ) -> EvidenceChainBuildResult:
        ...
```

Internal flow:

```text
resolve candidates -> read manifest/parsed -> chunk plan -> evidence plan
-> if dry_run: return counts
-> else: upsert chunks then evidence in transaction per content (or batch with per-content savepoint)
```

---

## 8. Chunk / Evidence MVP Strategy (Locked)

### 8.1 MarkItDown (`parser_name == "markitdown"`)

```text
chunk_level = "section" (primary)
Split parsed_text.md on markdown headings (^#{1,6} )
chunk_index = 0..N in document order
start_offset / end_offset = char offsets in full parsed_text.md (UTF-8 codepoint or byte — P4 pick one, P5 test; recommend Python str index)
page_no = null
slide_no = null
bbox = null
parent_chunk_uid = optional document-level root chunk (chunk_level=document, index=0) — P4 may omit root if YAGNI
evidence_type = "section_quote"
quote_text = chunk content truncated (e.g. first 2000 chars) or full if smaller
source_location = heading_path or "parsed_text.md:{start}-{end}"
```

### 8.2 MinerU (`parser_name == "mineru"`)

```text
Primary: chunk_level = "page" when parsed_metadata or manifest exposes page boundaries
Fallback: section split same as MarkItDown if no page map
page_no = set when page chunking applies
bbox = best-effort from metadata JSON or asset sidecar when present; else null
slide_no = null unless metadata provides
Do not fail when bbox missing
```

### 8.3 Explicitly out of MVP

```text
LLM chunking
Semantic / embedding-based splitting
Summarization
Vector writes
Curated asset generation
Review queue writes
```

### 8.4 Missing parsed artifacts

```text
If parsed_text.md or parse_manifest.json missing:
  log warning with content_uid/sha256
  increment documents_skipped
  continue batch — no repair, no reparse
```

---

## 9. Test Plan (P4 / P5)

Test file: `backend/tests/test_evidence_chain.py`

| ID | Test | Phase |
|---|---|---|
| T1 | `--dry-run` produces plan; **zero** chunk/evidence DB rows | P5 |
| T2 | Second run same fixture → same row counts (idempotent) | P5 |
| T3 | Missing parsed_text.md → skip + error list; batch continues | P5 |
| T4 | MarkItDown fixture → section chunks; page_no/bbox null OK | P5 |
| T5 | MinerU fixture → page_no set when metadata present; bbox optional | P5 |
| T6 | Spy raw_vault `original.bin` open → not called | P5 |
| T7 | Patch parser services → not called | P5 |
| T8 | No writes under curated_root | P5 |
| T9 | kb_parse_result / kb_document row counts unchanged except chunk/evidence | P5 |
| T10 | parsed file mtime unchanged | P5 |
| T11 | Chinese path + UTF-8 content | P5 |
| T12 | `--force` upserts without duplicate UID rows | P5 |
| T13 | `--output` JSON report schema valid | P5 |
| T14 | 001–009 regression pytest suite | P5 |

Regression command:

```bash
PYTHONPATH=backend pytest \
  backend/tests/test_evidence_chain.py \
  backend/tests/test_inventory_scanner.py \
  backend/tests/test_file_content_vault.py \
  backend/tests/test_duplicate_governance.py \
  backend/tests/test_parser_router.py \
  backend/tests/test_markitdown_parser.py \
  backend/tests/test_parse_job_registry.py \
  backend/tests/test_mineru_pdf_parser.py \
  backend/tests/test_parse_quality_checker.py \
  backend/tests/test_parse_quality_report_summarizer.py
```

E2E (P6): real COPIED parsed sample → `build-evidence-chain` → chunk/evidence rows + parsed mtime unchanged.

---

## 10. Dev Agent Handoff Template

```text
Role: Dev Agent
Spec: specs/010-evidence-chain/
Branch: feature/010-evidence-chain
Read first:
  specs/010-evidence-chain/p3_implementation_gate.md
  specs/010-evidence-chain/p2_db_review.md
  specs/010-evidence-chain/tasks.md (P4 section)

Whitelist: §2 of p3_implementation_gate.md
Blacklist: §3
Implement P4 tasks only.
After P4 STOP → QA Agent. Do not self-approve.
```

---

## 11. P3 Gate Summary

| Item | Decision |
|---|---|
| P3-GATE | **PASS** |
| Migration | **NOT required** (MVP) |
| P4 DB write | chunk + evidence only |
| P4 new ORM | `evidence.py` only |
| P4 modify KbDocument | **NO** |
| dry-run | Zero DB write |
| Idempotency | Deterministic UID + UNIQUE upsert |

---

## 12. STOP

P3 completed. **Do not enter P4** until user confirms.

No `backend/**` changes in P3.

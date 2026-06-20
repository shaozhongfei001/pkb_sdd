# 012 Search Service — P3 Implementation Gate

> Role: Tech Lead Agent  
> Spec: `specs/012-search-service/`  
> Branch: `feature/012-search-service` (create on P4 entry)  
> Stage: P3 Implementation Gate  
> P2 base: `p2_db_review.md` (PASS WITH CONSTRAINTS)  
> Local base: `f698e26`  
> Remote: **SSH verification unavailable / pending external confirmation**  
> Status: **P3-GATE PASS — P4 BLOCKED until user confirms**

---

## 1. Gate Conclusion

P3 Implementation Gate: **PASS**

012 Search Service is approved to enter **P4 Dev Implementation** after explicit user confirmation.

P2 constraints **C1–C17** remain locked. **No schema migration** for MVP.

**P4 MVP delivery mode:** **CLI-only** (`search-kb`). FastAPI `GET /api/v1/search` is **DEFERRED** (not in P4 whitelist).

If P4 discovers need for new columns, indexes, audit tables, or migration → **STOP** and return to TL + DB Review. Dev must not expand scope.

---

## 2. Inherited P2 Constraints (Locked)

| ID | Constraint | P4 enforcement |
|----|------------|----------------|
| C1 | Zero migration; reuse existing FULLTEXT indexes | No `sql/**`; use init SQL indexes only |
| C3 | SELECT-only; full DML denylist | No INSERT/UPDATE/DELETE; P5 row-count guard |
| C5 | `MATCH ... AGAINST` NATURAL LANGUAGE MODE primary | No default LIKE fallback |
| C6 | LIKE fallback not required MVP | Do not implement silent LIKE on MEDIUMTEXT |
| C7–C8 | Project filter via `kb_project_document`; not `kb_evidence.project_uid` | JOIN path locked in §8 |
| C9 | `scope=all` = per-scope query → merge-sort | Algorithm locked in §7 |
| C10 | Single-char Chinese may miss (`ngram_token_size=2`) | Document in CLI help; P6 must record |
| C14 | No raw_vault / parsed / curated filesystem reads | Static denylist + P5 guards |
| C15–C17 | No review/embedding writes; no ORM/sql edits | Blacklist §3 |

---

## 3. P4 Dev File Whitelist

Dev Agent may **create or modify only**:

```text
backend/app/services/search_service.py            # NEW — SearchService core
backend/app/schemas/search.py                     # NEW — SearchQuery, SearchHit, SearchResponse DTOs
backend/app/cli/main.py                           # register search-kb command
backend/tests/test_search_service.py              # NEW
backend/tests/fixtures/search/**                  # NEW — DB seed helpers / .fixture metadata only
```

### 3.1 Fixture paths (P4)

**Allowed:**

```text
backend/tests/fixtures/search/
  seed_helpers.py                    # optional — inline SQLAlchemy seed in test file preferred
  chinese_evidence.fixture.json      # metadata only — NOT ingested by inventory scanner
```

**Naming rules:**

```text
- Use .fixture suffix for any JSON/YAML under fixtures/search/.
- Do NOT add .txt / .pdf / .md document files that inventory scanner would ingest.
- Seed kb_document / kb_document_chunk / kb_evidence / kb_project* via SQLAlchemy in tests.
- Do NOT seed by reading parsed/ or raw_vault/ files.
```

**Do NOT create or modify:**

```text
backend/app/api/**                  # DEFERRED — no FastAPI search route in P4 MVP
backend/app/main.py                 # health-only — no search route registration in P4 MVP
backend/app/models/**               # read-only imports only
backend/app/schemas/** (except search.py)
curated/** raw_vault/** parsed/**
config/app.yaml
```

**Read-only reference (do not modify):**

```text
backend/app/core/config.py
backend/app/core/database.py
backend/app/models/document.py
backend/app/models/evidence.py
backend/app/models/project.py
backend/app/models/file.py
backend/app/models/parse_registry.py
backend/app/services/evidence_chain.py
backend/app/services/curated_project_assets.py
```

**Import pattern:**

```python
from app.models.document import KbDocument
from app.models.evidence import KbDocumentChunk, KbEvidence
from app.models.project import KbProject, KbProjectDocument, KbCuratedAsset
from app.schemas.search import SearchQuery, SearchHit, SearchResponse
from app.services.search_service import SearchService
```

If P4 requires ORM or `sql/**` changes → **STOP**.

---

## 4. P4 Forbidden Files (Black List)

Dev Agent must **not** modify:

```text
backend/app/services/inventory_scanner.py
backend/app/services/file_content_vault.py
backend/app/services/evidence_chain.py
backend/app/services/curated_project_assets.py
backend/app/services/parse_registry.py
backend/app/services/parse_quality_checker.py
backend/app/services/parse_quality_report_summarizer.py
backend/app/services/markitdown_parser.py
backend/app/services/mineru_pdf_parser.py
backend/app/services/parser_router.py
backend/app/services/duplicate_governance.py
backend/app/adapters/**
backend/app/models/**
backend/app/core/vault_paths.py
backend/app/core/parsed_paths.py
backend/app/main.py
backend/app/api/**
streamlit/**
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

### 4.1 Forbidden behavior

```text
- Invoke MarkItDown / MinerU / magic-pdf / subprocess parse
- Read raw_vault original.bin or raw_vault/** for search text
- Read parsed_text.md / parsed_metadata.json / parse_manifest.json
- Read curated/**/*.md for search text (use kb_curated_asset.asset_title only)
- INSERT / UPDATE / DELETE / REPLACE on any MySQL table
- Write kb_review_item / kb_manual_correction / kb_embedding_ref
- Write kb_document_chunk / kb_evidence / kb_project / kb_curated_asset / parse registry
- LLM query expansion / semantic rerank / embedding / vector stores
- Streamlit or admin UI
- LIKE '%query%' fallback on MEDIUMTEXT as default path
- kb_evidence.project_uid for --project-code filtering
- Schema migration or sql/**
- Move/delete/rename original user files
```

---

## 5. CLI Contract (Final — P4)

### 5.1 Command

```bash
PYTHONPATH=backend python -m app.cli.main search-kb \
  --config config/app.yaml \
  --query "银行 信贷" \
  --scope all \
  --project-code DEMO-2024 \
  --content-uid <uid> \
  --document-uid <uid> \
  --limit 20 \
  --offset 0 \
  --format json \
  --output /path/to/search_results.json
```

### 5.2 Parameters

| Flag | Required | Default | Behavior |
|------|----------|---------|----------|
| `--config` | No | `config/app.yaml` | Load mysql + `pipeline_version` (logging) |
| `--query` | **Yes** | — | Non-empty UTF-8 search string; trimmed |
| `--scope` | No | `all` | `all` \| `document` \| `chunk` \| `evidence` \| `project` \| `curated` |
| `--project-code` | No | null | Restrict hits to project mapping (see §8) |
| `--content-uid` | No | null | Filter hits to single `content_uid` |
| `--document-uid` | No | null | Filter hits to single `document_uid` |
| `--limit` | No | `20` | Page size; clamped **1–100** |
| `--offset` | No | `0` | Skip hits; must be **≥ 0** |
| `--format` | No | `json` | `json` \| `table` |
| `--output` | No | null | Write same JSON as stdout to operator path |

**Validation rules:**

```text
--query: after strip(), length >= 1 else exit 1 (SEARCH_EMPTY_QUERY)
--scope: case-insensitive; unknown → exit 1 (SEARCH_INVALID_SCOPE)
--limit: int 1..100 else exit 1 (SEARCH_INVALID_LIMIT)
--offset: int >= 0 else exit 1 (SEARCH_INVALID_OFFSET)
--format: json|table else exit 1 (SEARCH_INVALID_FORMAT)
--project-code: if set, must resolve kb_project row else exit 1 (SEARCH_PROJECT_NOT_FOUND)
--content-uid + --document-uid: both may be set; AND filter when both present
```

**Empty hits:** exit **0** with `total_count=0` and empty `hits[]` (not an error).

### 5.3 CLI help text (required)

```text
Search knowledge base via read-only MySQL FULLTEXT (ngram).
Queries kb_document, kb_document_chunk, kb_evidence, kb_project, kb_curated_asset only.
Does not read raw_vault, parsed files, or call parsers.
Single-character Chinese queries may return no hits (ngram_token_size=2).
Project filter uses kb_project_document mapping, not kb_evidence.project_uid.
```

### 5.4 Exit codes

| Code | Condition | Error code (JSON/logs) |
|------|-----------|------------------------|
| **0** | Search completed (including zero hits) | — |
| **1** | Config load failure, DB connection failure, validation error, unknown `--project-code`, fatal runtime error | see table above |
| **2** | **Not used** in MVP | — |

### 5.5 `--format table` contract

Human-readable table to stdout: columns `hit_type`, `relevance_score`, `document_uid`, `evidence_uid`, `snippet` (truncated). No DB write. JSON structure identical when `--output` set.

### 5.6 Forbidden CLI flags

```text
--fix --repair --reparse
--markitdown --mineru --magic-pdf
--build-evidence-chain --build-curated-project
--check-parse-quality --summarize-parse-quality
--llm --embed --semantic --vector --streamlit --review
--like-mode --write-chunk --write-evidence
```

---

## 6. Output JSON Schema (Final)

### 6.1 Success response (`--format json` / `--output`)

```json
{
  "report_type": "search_results",
  "schema_version": "1.0",
  "generated_at": "<ISO8601 UTC Z>",
  "pipeline_version": "v1.1",
  "query": {
    "text": "银行 信贷",
    "scope": "all",
    "project_code": "DEMO-2024",
    "content_uid": null,
    "document_uid": null,
    "limit": 20,
    "offset": 0
  },
  "summary": {
    "total_count": 3,
    "returned_count": 3,
    "scopes_executed": ["document", "chunk", "evidence", "project", "curated"],
    "duration_ms": 42
  },
  "hits": [
    {
      "hit_type": "evidence",
      "matched_field": "quote_text",
      "snippet": "…银行信贷…",
      "relevance_score": 12.45,
      "document_uid": "doc_abc…",
      "content_uid": "sha256…",
      "chunk_uid": "chunk_…",
      "evidence_uid": "ev_…",
      "project_uid": null,
      "project_code": null,
      "curated_uid": null,
      "metadata": {
        "page_no": 3,
        "heading_path": "第一章/背景",
        "parser_profile": "default_v1",
        "document_title": "示例文档标题"
      }
    }
  ],
  "errors": []
}
```

### 6.2 Error response (stdout JSON on exit 1 when `--format json`)

```json
{
  "report_type": "search_error",
  "schema_version": "1.0",
  "generated_at": "<ISO8601 UTC Z>",
  "error_code": "SEARCH_PROJECT_NOT_FOUND",
  "message": "project_code not found: UNKNOWN",
  "query": { "text": "test", "scope": "all", "project_code": "UNKNOWN" }
}
```

### 6.3 Field rules

```text
hit_type:     document | chunk | evidence | project | curated
matched_field: title | content | quote_text | normalized_text | project_name | description | asset_title
snippet:      max 200 chars UTF-8; ellipsis if truncated (SNIPPET_MAX=200)
relevance_score: float from MATCH ... AGAINST (MySQL natural language relevance)
UID fields:    null when not applicable to hit_type; never fabricated
metadata:      optional enrichment only; may include page_no, heading_path, parser_profile, document_title, asset_type
errors:        empty array on success; fatal CLI errors use search_error envelope
```

---

## 7. Service Contract (Final)

### 7.1 `SearchService`

```python
class SearchService:
    def __init__(self, config: AppConfig, session_factory: sessionmaker) -> None: ...

    def search(self, query: SearchQuery) -> SearchResponse:
        """Execute read-only FULLTEXT search. Raises SearchValidationError on invalid query."""
```

### 7.2 `SearchQuery` (schemas/search.py)

```python
@dataclass(frozen=True)
class SearchQuery:
    text: str                    # stripped, non-empty
    scope: str = "all"           # all|document|chunk|evidence|project|curated
    project_code: str | None = None
    content_uid: str | None = None
    document_uid: str | None = None
    limit: int = 20              # 1..100
    offset: int = 0              # >= 0
```

### 7.3 `SearchHit`

```python
@dataclass
class SearchHit:
    hit_type: str
    matched_field: str
    snippet: str
    relevance_score: float
    document_uid: str | None = None
    content_uid: str | None = None
    chunk_uid: str | None = None
    evidence_uid: str | None = None
    project_uid: str | None = None
    project_code: str | None = None
    curated_uid: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
```

### 7.4 `SearchResponse`

```python
@dataclass
class SearchResponse:
    query: SearchQuery
    hits: list[SearchHit]
    total_count: int
    returned_count: int
    scopes_executed: list[str]
    duration_ms: int
```

### 7.5 Exceptions

```python
class SearchValidationError(ValueError):
    error_code: str  # SEARCH_EMPTY_QUERY, SEARCH_INVALID_SCOPE, etc.

class SearchProjectNotFoundError(SearchValidationError):
    error_code = "SEARCH_PROJECT_NOT_FOUND"
```

DB connection errors: propagate to CLI → exit 1, message logged.

### 7.6 Ranking model (locked)

**Primary sort:** `relevance_score` DESC (MySQL `MATCH ... AGAINST` in NATURAL LANGUAGE MODE).

**Tie-breakers (stable ordering):**

```text
1. relevance_score DESC
2. hit_type order: evidence > chunk > document > curated > project  (only for scope=all merge)
3. primary uid ASC: evidence_uid | chunk_uid | document_uid | curated_uid | project_uid
```

**No LLM rerank. No embedding similarity. No manual score tuning in MVP.**

### 7.7 Snippet generation

```text
SNIPPET_MAX = 200 characters
Source column per hit_type (see §9)
If content longer than SNIPPET_MAX: truncate with "…" (U+2026 or "...")
Do not HTML-escape; preserve UTF-8
```

### 7.8 Optional enrichment (MVP — allowed)

For `chunk` / `evidence` hits: optional LEFT JOIN `kb_document` on `document_uid` to populate `metadata.document_title`, `metadata.parser_profile`.

**Not required** for search to function; omit metadata keys if join row missing.

**Forbidden enrichment:** reading `markdown_path` / `parsed/` files to load title.

---

## 8. DB Contract (Final)

### 8.1 Access mode

```text
SELECT only — zero DML on all tables.
Zero migration — use sql/001_init_schema_v1_1.sql as-is.
```

### 8.2 Allowed SELECT tables

| Table | MVP use |
|-------|---------|
| `kb_document` | `document` scope + enrichment |
| `kb_document_chunk` | `chunk` scope |
| `kb_evidence` | `evidence` scope |
| `kb_project` | `project` scope + `--project-code` resolution |
| `kb_project_document` | project filter JOIN |
| `kb_curated_asset` | `curated` scope |

### 8.3 FULLTEXT indexes (reuse — no new indexes)

| Index | Table | Columns |
|-------|-------|---------|
| `ftx_document_title` | `kb_document` | `title` |
| `ftx_chunk_content` | `kb_document_chunk` | `content` |
| `ftx_evidence_text` | `kb_evidence` | `quote_text`, `normalized_text` |
| `ftx_project_name_desc` | `kb_project` | `project_name`, `description` |
| `ftx_curated_asset_title` | `kb_curated_asset` | `asset_title` |

**Query mode (locked):**

```sql
MATCH(col...) AGAINST(:q IN NATURAL LANGUAGE MODE)
```

### 8.4 Forbidden SELECT sources (MVP)

```text
kb_file_instance (filename scope deferred)
kb_raw_vault_object
kb_parse_job / kb_parse_run (unless enrichment explicitly dropped)
Filesystem paths in kb_document.markdown_path — do not open files
```

### 8.5 DML denylist (absolute)

```text
All tables — no INSERT, UPDATE, DELETE, REPLACE, TRUNCATE, DDL
```

P5 must verify row counts unchanged on all denylist tables after search tests.

---

## 9. Scope Contract — Query Paths

### 9.1 Per-scope SQL path

| scope | Table | FULLTEXT | WHERE extras | Required hit UIDs |
|-------|-------|----------|--------------|-------------------|
| `document` | `kb_document` | `MATCH(title)` | content/document filter; project JOIN | `document_uid`, `content_uid` |
| `chunk` | `kb_document_chunk` | `MATCH(content)` | filters; project JOIN on `document_uid` | `chunk_uid`, `document_uid`, `content_uid` |
| `evidence` | `kb_evidence` | `MATCH(quote_text, normalized_text)` | filters; project JOIN on `document_uid` | `evidence_uid`, `document_uid`, `content_uid`, `chunk_uid` if present |
| `project` | `kb_project` | `MATCH(project_name, description)` | `project_code` if `--project-code` | `project_uid`, `project_code` |
| `curated` | `kb_curated_asset` | `MATCH(asset_title)` | `project_uid` if `--project-code` | `curated_uid`, `project_uid` |

Each scope query includes:

```sql
MATCH(...) AGAINST(:q IN NATURAL LANGUAGE MODE) AS relevance_score
WHERE MATCH(...) AGAINST(:q IN NATURAL LANGUAGE MODE)
```

### 9.2 Filter application

| Filter | Applies to |
|--------|------------|
| `--content-uid` | `document`, `chunk`, `evidence` scopes (column `content_uid`) |
| `--document-uid` | `document`, `chunk`, `evidence` scopes (column `document_uid`) |
| `--project-code` | see §10 |

`project` scope with `--project-code`: equivalent to filtering `kb_project.project_code = :code` (may return single project row if name/desc matches).

`curated` scope with `--project-code`: `kb_curated_asset.project_uid = resolved project_uid`.

---

## 10. `--project-code` Filter Strategy (Locked)

### 10.1 Resolution

```text
1. SELECT project_uid FROM kb_project WHERE project_code = :project_code
2. IF no row → SearchProjectNotFoundError (CLI exit 1)
3. SELECT document_uid FROM kb_project_document WHERE project_uid = :project_uid
4. allowed_document_uids = result set (may be empty)
```

### 10.2 Application by scope

| scope | Filter mechanism |
|-------|------------------|
| `document` | `kb_document.document_uid IN (:allowed_document_uids)` |
| `chunk` | `kb_document_chunk.document_uid IN (:allowed_document_uids)` |
| `evidence` | `kb_evidence.document_uid IN (:allowed_document_uids)` |
| `project` | `kb_project.project_code = :project_code` |
| `curated` | `kb_curated_asset.project_uid = :project_uid` |

If `allowed_document_uids` is **empty** for document/chunk/evidence: return **zero hits**, exit **0** (not an error).

### 10.3 Forbidden

```text
kb_evidence.project_uid = :project_uid
kb_evidence.project_uid IS NOT NULL as project filter
Any backfill of kb_evidence.project_uid in 012
```

---

## 11. `scope=all` Strategy (Locked — C9)

### 11.1 Algorithm

```text
scopes_to_run = [document, chunk, evidence, project, curated]

For each scope in scopes_to_run:
  1. Run COUNT query with same MATCH + filters → scope_total
  2. Run SELECT with MATCH + filters
     ORDER BY relevance_score DESC, uid ASC
     LIMIT (limit + offset)   # per-scope cap for merge buffer
  3. Tag each row with hit_type

merged = concatenate all scope hit lists
merged.sort(key=lambda h: (-h.relevance_score, hit_type_rank, uid))

total_count = sum(scope_totals)   # hits may overlap conceptually across scopes — OK for MVP

page_hits = merged[offset : offset + limit]
returned_count = len(page_hits)
```

### 11.2 Pagination rules

| Parameter | Rule |
|-----------|------|
| `limit` | Default 20; min 1; max 100 |
| `offset` | Default 0; applied **after** global merge-sort |
| `total_count` | Sum of per-scope COUNTs (may count same logical content in multiple scopes) |
| `returned_count` | `len(page_hits)` ≤ `limit` |

**Single scope (`scope != all`):** one COUNT + one SELECT with `LIMIT :limit OFFSET :offset` on that scope only; no merge.

### 11.3 Performance note (MVP acceptable)

Per-scope `LIMIT (limit + offset)` may over-fetch for large offset — acceptable for MVP dataset sizes. Do not add new indexes in P4.

---

## 12. Chinese Query Constraints (C10 — P6 mandatory)

| Topic | Locked behavior |
|-------|-----------------|
| Parser | InnoDB FULLTEXT with `WITH PARSER ngram` |
| `ngram_token_size` | Default **2** on MySQL 8.0 — P6 must `SHOW VARIABLES LIKE 'ngram_token_size'` |
| Single-character query | May return **zero hits** — not a bug; document in help text |
| P4 implementation | Do **not** auto-fallback to LIKE when FULLTEXT returns empty |
| P6 E2E | Must test multi-char Chinese query + single-char query; record outcomes in `p6_e2e_report.md` |

---

## 13. Forbidden Runtime (Locked)

| Layer | Forbidden |
|-------|-----------|
| Filesystem | `raw_vault/**`, `parsed/**`, `curated/**` reads for search text |
| Parser | MarkItDown, MinerU, magic-pdf, subprocess parse |
| LLM | Any cloud/local LLM for query expansion or rerank |
| Vector | embedding generation, vector DB, `kb_embedding_ref` |
| Review | `kb_review_item`, `kb_manual_correction` |
| UI | Streamlit, new FastAPI routes (P4 MVP) |
| DB | Any DML |

**Allowed filesystem write:** operator `--output` JSON path only.

---

## 14. Test Plan (P5 preview — Dev implements in P4)

### 14.1 Unit tests (`test_search_service.py`)

| ID | Test | Maps to test_cases |
|----|------|-------------------|
| T01 | document scope title hit | TC001 |
| T02 | chunk scope content hit | TC002 |
| T03 | evidence scope quote hit | TC003 |
| T04 | project scope name hit | TC004 |
| T05 | curated scope asset_title hit | TC005 |
| T06 | scope=all merge + sort | TC006 |
| T07 | empty query rejected | TC007 |
| T08 | no matches → empty list exit 0 | TC008 |
| T09 | limit/offset pagination | TC009 |
| T10 | --project-code filter via mapping | TC010, TC011 |
| T11 | content_uid / document_uid filters | TC011b, TC011c |
| T12 | Chinese query UTF-8 | TC012 |
| T13 | JSON output shape | TC013 |
| T14 | table format smoke | TC014 |
| T15 | --output file write | TC015 |

### 14.2 No-side-effect guards

| ID | Test | Maps to |
|----|------|---------|
| T16 | no parser subprocess | TC016 |
| T17 | no raw_vault read | TC017 |
| T18 | no parsed filesystem read | TC018 |
| T19 | no curated filesystem read | TC019 |
| T20 | DB row counts unchanged (denylist tables) | TC020 |
| T21 | kb_review_item count unchanged | TC021 |
| T22 | kb_embedding_ref count unchanged | TC022 |

### 14.3 CLI smoke (P5)

```bash
PYTHONPATH=backend python -m app.cli.main search-kb --query "测试" --scope all --format json
PYTHONPATH=backend python -m app.cli.main search-kb --query ""   # expect exit 1
```

### 14.4 Regression

Full `backend/tests` suite — 001–011 tests must pass (TC024).

### 14.5 P6 E2E (not P4/P5)

Real MySQL ngram FULLTEXT, Chinese samples, `ngram_token_size` recorded (TC027–TC029).

---

## 15. P4 Dev Agent Handoff Checklist

```text
[ ] Create SearchService + schemas per §7
[ ] Register search-kb in cli/main.py per §5
[ ] Implement per-scope FULLTEXT SELECT per §9
[ ] Implement scope=all merge per §11
[ ] Implement project filter per §10 (NOT evidence.project_uid)
[ ] JSON output per §6
[ ] SNIPPET_MAX=200, ranking per §7.6
[ ] No DML; no forbidden filesystem reads
[ ] No FastAPI route (deferred)
[ ] Unit tests per §14.1–14.2
[ ] Do NOT run full QA sign-off or E2E in P4
[ ] STOP after P4 — await P5 QA assignment
```

---

## 16. P4 STOP Condition

```text
P4 ends when:
  - Whitelist files implemented
  - test_search_service.py passes locally (Dev smoke)
  - No blacklisted files touched
  - No sql/** / models/** changes

P4 must NOT:
  - Produce p5_qa_report.md or claim QA PASS
  - Run E2E against production MySQL without QA charter
  - Self-advance to P5 or P6
  - Merge feature branch

After P4: STOP — user confirms → QA Agent P5.
```

---

## 17. P3 Checklist

```text
[x] P4 whitelist finalized
[x] P4 blacklist finalized
[x] CLI contract (params, defaults, exit codes, JSON schema)
[x] Service / query / hit / response models
[x] DB SELECT-only + FULLTEXT + zero migration
[x] Scope query paths documented
[x] scope=all merge + pagination locked
[x] --project-code JOIN strategy locked
[x] Chinese ngram constraints documented for P6
[x] Forbidden runtime enumerated
[x] Test plan for P5/P6
[x] P4 STOP condition
[x] P2 constraints inherited
[ ] User confirmation → P4 Dev
```

---

## 18. P3 STOP

**Do not enter P4 Dev** until user confirms.

No `backend/**` implementation in P3.

No `sql/**` changes in P3.

---

## 19. Next Step

On user approval:

```text
Role: Dev Agent
Branch: feature/012-search-service (create if not exists)
Deliverable: P4 implementation within §3 whitelist only
Then: STOP — hand off to QA Agent for P5
```

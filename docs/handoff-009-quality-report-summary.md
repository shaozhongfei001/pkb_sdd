# 009 Parse Quality Report Summary — Handoff

> Spec: `specs/009-quality-report-summary/`  
> Branch: `feature/009-quality-report-summary`  
> Stage: P8 Handoff & Final Commit  
> Status: DONE

---

## 1. Completion Summary

009 Parse Quality Report Summary has been completed.

The feature provides a read-only summarizer that consumes 008 `parse_quality_report.json` and outputs:

- Markdown summary (default)
- JSON summary (`--format json`)
- noise classification (`TEST_STALE_PATH`, `STALE_VAULT_PATH`, `REAL_DEFECT`)
- filtered aggregations without re-scanning the project

The summarizer reports and triages 008 findings only. It does not repair data.

---

## 2. Implemented Scope

Implemented command:

```bash
PYTHONPATH=backend python -m app.cli.main summarize-parse-quality \
  --config config/app.yaml \
  --input /path/to/parse_quality_report.json \
  --output /path/to/parse_quality_summary.md
```

Supported options:

- `--config`
- `--input`
- `--output`
- `--format` (`markdown` | `json`)
- `--severity`
- `--issue-code` (repeatable)
- `--parser-name`
- `--top`
- `--fail-on-issue`

Implemented files:

- `backend/app/services/parse_quality_report_summarizer.py`
- `backend/app/cli/main.py` (registers `summarize-parse-quality`)
- `backend/tests/test_parse_quality_report_summarizer.py`
- `backend/tests/fixtures/parse_quality_report_*.json`

Spec / review / QA / E2E files:

- `specs/009-quality-report-summary/spec.md`
- `specs/009-quality-report-summary/plan.md`
- `specs/009-quality-report-summary/tasks.md`
- `specs/009-quality-report-summary/acceptance.md`
- `specs/009-quality-report-summary/test_cases.md`
- `specs/009-quality-report-summary/p2_p3_review.md`
- `specs/009-quality-report-summary/p5_qa_report.md`
- `specs/009-quality-report-summary/p6_e2e_report.md`
- `specs/009-quality-report-summary/p7_final_review.md`

---

## 3. Summary Output Contract

Default summary path:

```text
{reports_root}/parse_quality_summary_{YYYYMMDDTHHMMSSZ}.md
```

JSON summary:

```text
report_type = parse_quality_summary
schema_version = 1.0
mode = summarize
```

Key fields:

- `issue_counts` — copy of input 008 counts (all 18 codes)
- `filtered_issue_counts` — recomputed from filtered issues
- `noise_breakdown` — TEST / STALE / REAL buckets
- `sample_issues` — truncated by `--top`
- `recommendations` — non-mutating triage notes

---

## 4. Input Contract

009 accepts only 008 reports with:

```text
report_type = parse_quality_report
schema_version = 1.0
mode = check
```

Input may come from:

- explicit `--input`
- latest `parse_quality_report_*.json` under `reports_root`

---

## 5. Read-only Contract

009 is a pure report pipeline.

Allowed reads:

- `config/app.yaml` (`reports_root` only at runtime)
- 008 JSON report file

Allowed writes:

- summary Markdown or JSON only

Forbidden behavior:

- no MySQL connection
- no ORM / DB write
- no raw_vault read
- no parsed read
- no registry read
- no MarkItDown / MinerU / magic-pdf call
- no `check-parse-quality` re-invocation
- no repair / reparse / cleanup
- no `--fix` / `--repair` / `--reparse` / `--write-db`
- no review workflow implementation

P5 and P6 verified zero DB / raw_vault / parsed access.

---

## 6. Test Results

P5 QA:

```text
009 specialized tests: 31 passed
004–008 regression:     157 passed
No implementation defects
```

P6 E2E (real 008 report):

```text
Input:  /tmp/pkb_sdd_008_p6/parse_quality_report.json
Output: /tmp/pkb_sdd_009_p6/parse_quality_summary.md | .json
Input SHA256 unchanged
noise_breakdown: TEST_STALE_PATH=836, STALE_VAULT_PATH=152, REAL_DEFECT=0
Result: PASS
```

---

## 7. Completed Stage Chain

Relevant commits on `feature/009-quality-report-summary`:

```text
e1cfac3 spec(009): add quality report summary P1 plan and align SPEC_INDEX
938bf99 review(009): add P2 P3 implementation gate
86e3d55 feat(009): implement parse quality report summarizer
9e0d18d test(009): add parse quality report summarizer QA report
49ab89c test(009): add parse quality report summarizer E2E report
b7e1dfa review(009): add parse quality report summarizer final review
docs(009): add quality report summary handoff
merge: feature/009-quality-report-summary into main
```

---

## 8. Residual Caveats

- Real 008 datasets may be dominated by pytest / stale-path noise; `REAL_DEFECT` may be zero even when issue_count is high.
- 009 classifies noise but does not clean pytest DB records or repair vault/parsed paths.
- 007 MinerU real E2E caveat remains separately documented in `SPEC_INDEX.md` §6.
- `load_config()` parses mysql settings but 009 does not connect.

---

## 9. Next Stage

**Do not auto-start the next spec.**

After merge to `main`, select the next active spec only by reading `specs/SPEC_INDEX.md` after an explicit index update.

Potential future specs (not active until index says so):

- `specs/010-evidence-chain/`
- `specs/008-review-workflow/` (future stub — not the completed 008 checker)
- repair / human review planning specs

Do not infer the next stage from directory numbering alone.

---

## 10. Final Status

009 Parse Quality Report Summary: **DONE**

`specs/SPEC_INDEX.md` updated: phase 009 marked DONE; no new ACTIVE phase declared.

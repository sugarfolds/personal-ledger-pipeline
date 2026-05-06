---
name: personal-ledger-pipeline
description: Use when working with this repo's local-first personal ledger workflow: importing private bill exports, choosing source-specific parsers, running the cleaned ledger pipeline, reviewing ambiguous rows, generating annual reports, and checking privacy before GitHub-facing output.
---

# Personal Ledger Pipeline Skill

Use this skill when helping a user import private bill exports, run the local ledger pipeline, review ambiguous rows, generate personal annual reports, or prepare a GitHub-safe demo.

## Boundaries

- Never upload private bill exports.
- Never copy real raw files or private generated outputs into public examples.
- Before any GitHub-facing action, inspect for real names, account hints, transaction IDs, merchant names, balances, and screenshots that reveal private data.
- Public demo outputs must be synthetic.

## Workflow

1. Inspect the workspace.
   - Run `git status --short`.
   - Run `find raw parsed processed final examples docs scripts web skills -type f 2>/dev/null`.
   - Confirm whether the task concerns synthetic demo data or private local data.

2. Identify sources.
   - Expected folders: `raw/alipay/`, `raw/wechat/`, `raw/meituan/`, `raw/douyin/`, `raw/bank/<boc|cmb|icbc|abc>/`.
   - Prefer source-specific parsing over generic spreadsheet guessing.
   - For PDF or legacy XLS in v1, suggest CSV export or local conversion unless a source branch already exists. XLSX is supported by the CLI when `openpyxl` is installed.

3. Import raw exports.
   - Run `python3 scripts/import_raw.py <raw_dir> --out parsed`.
   - Read warnings. Unknown folders and unsupported extensions require action.
   - Inspect `parsed/normalized_input.csv` before cleaning when source confidence is low.

4. Run the pipeline.
   - Run `python3 scripts/run_pipeline.py <raw_dir>`.
   - Check:
     - `processed/normalized/`
     - `processed/cleaned/`
     - `final/summary/`
     - `final/review/`
     - `final/ledger/`

5. Review classification controls.
   - Credit repayment rows should be excluded from new consumption.
   - Internal transfers should be excluded from spend and income views.
   - Refund rows should deduct original consumption when `related_transaction_id` is available.
   - Bank app-shadow rows should be excluded when an app-side row gives richer detail.
   - Ambiguous wallet flows should enter the manual review queue.

6. Generate or inspect the annual report.
   - For the static sample, run `make demo`.
   - For browser-only exploration, open `web/annual-report/index.html` and upload a cleaned CSV or normalized JSON.
   - Keep the tone deterministic and template-based unless the user explicitly asks for a model-backed writing pass.

7. Privacy check before public output.
   - Run `rg -n "<private names or account hints>" raw processed final examples docs README.md`.
   - Inspect generated HTML and screenshots manually.
   - Push only synthetic examples.

## Useful Commands

```bash
make clean && make demo
python3 scripts/import_raw.py raw --out parsed
python3 scripts/run_pipeline.py raw
python3 -m py_compile scripts/run_sample_pipeline.py scripts/import_raw.py scripts/run_pipeline.py scripts/core/ledger.py scripts/parsers/registry.py
node --check web/annual-report/src/app.js
```

# Use Your Own Data Locally

This repository can process private exports on your own machine. Do not commit private raw files, generated private reports, account names, transaction IDs, account tails, or balances.

## Folder Layout

Place files under a local raw directory with source-specific folders:

```text
raw/
  alipay/
  wechat/
  meituan/
  douyin/
  bank/
    boc/
    cmb/
    icbc/
    abc/
```

The public `raw/` folder in this repo contains synthetic examples. For real usage, keep a private copy outside any public Git workflow.

## Import Only

```bash
python3 scripts/import_raw.py raw --out parsed
```

This creates:

```text
parsed/normalized_input.csv
```

Use this step when you want to inspect parser output before running cleaning rules.

## Run The Local Pipeline

```bash
python3 scripts/run_pipeline.py raw
```

Generated files:

```text
processed/normalized/current_ledger_<period>.csv
processed/cleaned/current_ledger_<period>.cleaned.csv
final/summary/summary_<period>.md
final/review/manual_review_queue_<period>.csv
final/ledger/gross_ledger_<period>.csv
```

Review `final/review/` before treating the summary as final. Ambiguous wallet flows and uncertain source rows are intentionally separated for a second pass.

## What The Cleaner Does

- Credit repayments are excluded from new-consumption views.
- Internal transfers are excluded from spend and income views.
- Matched refunds deduct the original consumption when `related_transaction_id` exists.
- Bank charges that duplicate app-side payments are excluded from the cleaned ledger.
- Ambiguous rows remain visible in the manual review queue.

## Browser Annual Report

Open:

```text
web/annual-report/index.html
```

Upload a CSV or normalized JSON file. Parsing and report generation run in the browser. No login, server, or API is required.

For best results, upload a cleaned ledger exported from the CLI. Browser-side raw parsing is deliberately conservative because payment exports vary by source and language.

## Dependencies

The synthetic demo uses only Python's standard library. XLSX intake requires:

```bash
python3 -m pip install -r requirements.txt
```

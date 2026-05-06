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
final/review/review_decisions_<period>.template.csv
final/ledger/gross_ledger_<period>.csv
```

Review `final/review/` before treating the summary as final. Ambiguous wallet flows and uncertain source rows are intentionally separated for a second pass.

## Manual Review Decisions

The first run writes two review files:

```text
final/review/manual_review_queue_<period>.csv
final/review/review_decisions_<period>.template.csv
```

Edit the template file locally. Supported `action` values:

| Action | Meaning |
| --- | --- |
| `include` | Include the row in the cleaned ledger after applying any direction/type/scope edits |
| `exclude` | Exclude the row and mark the decision as reviewed |
| `keep_review` | Leave the row in the review queue |

Then rerun:

```bash
python3 scripts/run_pipeline.py raw --review-decisions final/review/review_decisions_<period>.template.csv
```

The summary and cleaned ledger will reflect the manual decisions.

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

## Codex Skill

This repo includes a local Codex workflow at `skills/personal-ledger-pipeline/`.

Install it from the repo root:

```bash
mkdir -p ~/.codex/skills
cp -R skills/personal-ledger-pipeline ~/.codex/skills/
```

Then invoke `$personal-ledger-pipeline` when you want Codex to guide a private local run from raw files to cleaned ledger, manual review, report generation, and privacy checks.

See [Codex skill usage](codex_skill.md).

## Dependencies

The synthetic demo uses only Python's standard library. XLSX intake requires:

```bash
python3 -m pip install -r requirements.txt
```

## Validation

Run the synthetic fixture checks before changing parser or cleaning rules:

```bash
make test
```

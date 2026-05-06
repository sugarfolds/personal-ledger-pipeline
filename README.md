# Personal Ledger Pipeline

A local-first, source-first data pipeline for messy personal finance exports.

This repository is a **portfolio-safe demo**. It contains only synthetic sample transactions and does not include real bank statements, account balances, merchants, transaction IDs, or counterparties.

## Why This Exists

Consumer finance exports are not clean analytics data. A single real-world payment can appear across multiple systems:

- an app-side purchase,
- a bank-side card charge,
- a later monthly repayment,
- a partial or full refund,
- an internal wallet transfer,
- or an item that needs manual review.

This project demonstrates how to turn messy exports into a traceable ledger pipeline without handing credentials to a third party.

## Pipeline

```text
raw/
  -> processed/normalized/
  -> processed/cleaned/
  -> final/summary/
  -> final/review/
  -> final/ledger/
  -> final/visual/
```

Key design principles:

- **Local-first**: works from exported files, no bank login or cloud sync.
- **Source-first**: raw files are preserved; every derived row keeps source and row number.
- **Rule-based but reviewable**: deterministic rules handle stable cases; ambiguous rows go to a review queue.
- **No direct edits to final outputs**: fix rules or review decisions, then rerun.

## What The Sample Covers

The synthetic sample data includes:

- app payments paid by wallet or monthly credit,
- monthly repayments that should not be counted as new consumption,
- full and partial refunds,
- a bank charge shadowed by an app-side payment,
- an internal transfer between bank and wallet,
- an ambiguous record sent to manual review.

## Run The Demo

```bash
python3 scripts/run_sample_pipeline.py
```

or:

```bash
make demo
```

Generated outputs:

- `processed/normalized/current_ledger_2026-04-01_to_2026-04-30.csv`
- `processed/cleaned/current_ledger_2026-04-01_to_2026-04-30.cleaned.csv`
- `final/summary/summary_2026-04-01_to_2026-04-30.md`
- `final/review/manual_review_queue_2026-04-01_to_2026-04-30.csv`
- `final/ledger/gross_ledger_2026-04-01_to_2026-04-30.csv`
- `final/visual/dashboard_2026-04-01_to_2026-04-30.html`

Generated outputs are ignored by git. Recreate them locally with `make demo`.

## Core Fields

| Field | Purpose |
| --- | --- |
| `source` / `source_file` / `raw_row_number` | Evidence trail back to the original export |
| `direction` | Normalized cash direction: `expense`, `income`, or `neutral` |
| `normalized_type` | Business type such as `merchant_payment`, `refund_in`, `credit_repayment`, `internal_transfer` |
| `transfer_scope` | Separates external spending from internal account flow or debt repayment |
| `include_in_ledger` | Whether the row contributes to the main ledger view |
| `clean_status` / `clean_rule` | Explainable cleaning decision |
| `needs_review` | Flags rows that require human confirmation |

## Privacy Model

This public repository is designed around a hard boundary:

- Real exports belong in a private working directory.
- Public demo data must be synthetic.
- IDs, names, merchants, account hints, and balances must be fake.
- `.gitignore` blocks generated outputs and private raw data by default.

See [SECURITY.md](SECURITY.md) for the publishing checklist.

## Portfolio Framing

This is not a full personal finance app. It is a data pipeline demo focused on:

- schema design,
- reconciliation logic,
- refund and repayment handling,
- manual-review workflow,
- reproducible outputs,
- and privacy-safe project packaging.

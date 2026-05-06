# Security and Privacy

This repository is intended to be public and portfolio-safe.

## Data Boundary

Do not commit:

- real bank statements,
- payment app exports,
- account balances,
- transaction IDs,
- card tails,
- counterparties,
- merchant names from real life,
- review decision exports from a real run.

Use `raw/private/` for any local-only private test files. That path is ignored by git.

## Public Demo Data

The tracked files under `raw/` are synthetic. They are designed only to exercise the pipeline logic:

- app-side purchases,
- monthly repayments,
- matched refunds,
- internal transfers,
- duplicate bank charges,
- manual-review rows.

## Before Publishing

Run:

```bash
make clean
make demo
git status --short --ignored
```

Only source code, docs, schema files, and synthetic raw files should be staged.

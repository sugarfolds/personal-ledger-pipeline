# Portfolio Notes

## Positioning

This project should be described as:

> A local-first personal finance data pipeline that normalizes messy payment exports into a traceable ledger with reviewable cleaning rules.

Avoid describing it as a production-grade accounting app.

## Good Interview Details

- Monthly repayment is not the same as new consumption. The pipeline excludes repayment rows while keeping the original purchases.
- Refunds are split into matched full refunds and partial refund deductions.
- Bank charges can duplicate app-side payments; the demo marks bank-side mirrors as shadowed duplicates.
- Manual review is a workflow, not a direct edit: queue first, decision later, then rule consolidation.

## Public Boundary

Never publish real:

- raw statements,
- account balances,
- counterparty names,
- merchant names,
- transaction IDs,
- bank card tails,
- browser localStorage exports.

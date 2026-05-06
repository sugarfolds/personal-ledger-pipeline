# Portfolio Notes

## Positioning

This project should be described as:

> A local-first personal finance data pipeline that normalizes messy payment exports into a traceable ledger with reviewable cleaning rules.

When discussing the annual-report layer, use:

> A portfolio-safe web demo that turns the cleaned ledger into a bilingual personal annual report with simplified statements, risk factors, segment analysis, and deterministic narrative commentary.

Avoid describing it as a production-grade accounting app.

## Good Interview Details

- Monthly repayment is not the same as new consumption. The pipeline excludes repayment rows while keeping the original purchases.
- Refunds are split into matched full refunds and partial refund deductions.
- Bank charges can duplicate app-side payments; the demo marks bank-side mirrors as shadowed duplicates.
- Manual review is a workflow, not a direct edit: queue first, decision later, then rule consolidation.
- The annual report is an application layer on top of the cleaned ledger. It does not read raw exports directly and does not call an LLM, so the demo is reproducible in GitHub Actions.

## Public Boundary

Never publish real:

- raw statements,
- account balances,
- counterparty names,
- merchant names,
- transaction IDs,
- bank card tails,
- browser localStorage exports.

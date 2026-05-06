# Codex Skill

This repository includes a repo-distributed Codex skill at:

```text
skills/personal-ledger-pipeline/
```

It is not a GitHub App, GitHub Action, or marketplace-published skill. It is a portable workflow bundled with the repo so users and agents can reuse the same local ledger process.

## What It Does

Use `$personal-ledger-pipeline` to guide Codex through:

- inspecting raw export folders,
- choosing source-specific parsers,
- importing local bill exports,
- running the cleaned ledger pipeline,
- reviewing manual review rows,
- generating annual reports,
- checking privacy before publishing anything to GitHub.

## Install Locally

From the repo root:

```bash
mkdir -p ~/.codex/skills
cp -R skills/personal-ledger-pipeline ~/.codex/skills/
```

Restart Codex if the skill list does not refresh automatically.

## Use In Codex

Example prompt:

```text
Use $personal-ledger-pipeline to inspect my local raw exports, run the ledger pipeline, review ambiguous rows, and prepare a privacy-safe annual report.
```

The skill expects the repo workflow and folder layout:

```text
raw/
parsed/
processed/
final/
scripts/
skills/
```

## Privacy Boundary

The skill is workflow metadata only. It does not contain private exports or generated private reports.

Before any public-facing action, it instructs Codex to check for:

- real names,
- account hints,
- transaction IDs,
- merchant names,
- balances,
- screenshots or HTML exports that reveal private data.

Public examples should remain synthetic.

#!/usr/bin/env python3

from __future__ import annotations

import argparse
import sys
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts.core.ledger import (
    build_refunds_by_original,
    build_summary,
    clean,
    read_csv,
    write_csv,
)
from scripts.parsers.registry import IntakeError, parse_raw_dir, source_counts


def money_text(value: Decimal) -> str:
    return f"{value:,.2f}"


def infer_period(rows: list[dict[str, str]]) -> str:
    if not rows:
        return "empty"
    dates = sorted(row["transaction_time"][:10] for row in rows if row.get("transaction_time"))
    return f"{dates[0]}_to_{dates[-1]}" if dates else "unknown"


def write_summary(path: Path, rows: list[dict[str, str]], warnings: list[str]) -> None:
    refunds = build_refunds_by_original(rows)
    summary = build_summary(rows, refunds)
    review_rows = [row for row in rows if row["needs_review"] == "true" or row["clean_status"] == "needs_review"]
    excluded_repayment = sum(Decimal(row["amount"]) for row in rows if row["transfer_scope"] == "debt_repayment")
    excluded_internal = sum(Decimal(row["amount"]) for row in rows if row["transfer_scope"] == "internal")
    duplicate_bank = sum(Decimal(row["amount"]) for row in rows if row["clean_status"] == "excluded_duplicate_payment")

    lines = [
        "# Local Ledger Summary",
        "",
        "Generated from local raw exports. Keep this file private if it came from real bills.",
        "",
        "## Financial View",
        "",
        f"- Rows: {len(rows)}",
        f"- Included rows: {sum(1 for row in rows if row['include_in_ledger'] == 'true')}",
        f"- Gross income: {money_text(summary['gross_income'])}",
        f"- Gross expense: {money_text(summary['gross_expense'])}",
        f"- Refund deduction: {money_text(summary['refund_deduction'])}",
        f"- Net consumption: {money_text(summary['net_consumption'])}",
        f"- Net cashflow view: {money_text(summary['net_cashflow'])}",
        "",
        "## Cleaning Controls",
        "",
        f"- Credit or personal repayments excluded from new consumption: {money_text(excluded_repayment)}",
        f"- Internal transfers excluded from spend views: {money_text(excluded_internal)}",
        f"- Duplicate bank app-shadow rows excluded: {money_text(duplicate_bank)}",
        f"- Manual review rows: {len(review_rows)}",
    ]
    if warnings:
        lines.extend(["", "## Import Warnings", ""])
        lines.extend(f"- {warning}" for warning in warnings)

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the local personal ledger pipeline on private raw exports.")
    parser.add_argument("raw_dir", type=Path, help="Directory containing raw/<source>/ exports.")
    parser.add_argument("--period", help="Output period label. Defaults to the date span found in the rows.")
    parser.add_argument("--parsed", type=Path, help="Optional normalized CSV created by scripts/import_raw.py.")
    args = parser.parse_args()

    warnings: list[str] = []
    if args.parsed:
        rows = read_csv(args.parsed)
    else:
        try:
            result = parse_raw_dir(args.raw_dir)
        except IntakeError as exc:
            parser.error(str(exc))
        rows = result.rows
        warnings = result.warnings

    period = args.period or infer_period(rows)
    cleaned_rows = clean(rows)
    review_rows = [row for row in cleaned_rows if row["needs_review"] == "true" or row["clean_status"] == "needs_review"]

    normalized_path = ROOT / "processed" / "normalized" / f"current_ledger_{period}.csv"
    cleaned_path = ROOT / "processed" / "cleaned" / f"current_ledger_{period}.cleaned.csv"
    gross_path = ROOT / "final" / "ledger" / f"gross_ledger_{period}.csv"
    review_path = ROOT / "final" / "review" / f"manual_review_queue_{period}.csv"
    summary_path = ROOT / "final" / "summary" / f"summary_{period}.md"

    write_csv(normalized_path, rows)
    write_csv(cleaned_path, cleaned_rows)
    write_csv(gross_path, cleaned_rows)
    write_csv(review_path, review_rows)
    write_summary(summary_path, cleaned_rows, warnings)

    print(f"Pipeline complete for {period}")
    print(f"- normalized: {normalized_path}")
    print(f"- cleaned: {cleaned_path}")
    print(f"- summary: {summary_path}")
    print(f"- review queue: {review_path}")
    for source, count in sorted(source_counts(cleaned_rows).items()):
        print(f"- {source}: {count} rows")
    if warnings:
        print("\nWarnings:")
        for warning in warnings:
            print(f"- {warning}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

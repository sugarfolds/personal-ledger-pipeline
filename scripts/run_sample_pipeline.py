#!/usr/bin/env python3

from __future__ import annotations

import csv
import html
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "raw"
NORMALIZED = ROOT / "processed" / "normalized"
CLEANED = ROOT / "processed" / "cleaned"
FINAL = ROOT / "final"
PERIOD = "2026-04-01_to_2026-04-30"


FIELDS = [
    "source",
    "source_file",
    "raw_row_number",
    "transaction_time",
    "direction",
    "amount",
    "counterparty",
    "item_title",
    "payment_method",
    "transaction_id",
    "related_transaction_id",
    "normalized_type",
    "normalized_status",
    "account_platform",
    "account_name",
    "transfer_scope",
    "include_in_ledger",
    "needs_review",
    "clean_status",
    "clean_rule",
]


def money(value: str | Decimal) -> Decimal:
    return Decimal(str(value or "0")).quantize(Decimal("0.01"))


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, rows: list[dict[str, str]], fields: list[str] = FIELDS) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def base_row(source: str, path: Path, raw_index: int, row: dict[str, str]) -> dict[str, str]:
    return {
        "source": source,
        "source_file": str(path.relative_to(ROOT)),
        "raw_row_number": str(raw_index),
        "transaction_time": row["transaction_time"],
        "amount": f"{money(row.get('amount') or row.get('debit') or row.get('credit')):.2f}",
        "counterparty": row.get("counterparty", ""),
        "item_title": row.get("item_title", row.get("description", "")),
        "payment_method": row.get("payment_method", ""),
        "transaction_id": row.get("transaction_id", ""),
        "related_transaction_id": row.get("related_transaction_id", ""),
        "account_platform": source,
        "account_name": row.get("account_name", row.get("payment_method", "")),
        "include_in_ledger": "true",
        "needs_review": "false",
        "clean_status": "active",
        "clean_rule": "",
    }


def parse_alipay() -> list[dict[str, str]]:
    rows = []
    for path in sorted((RAW / "alipay").glob("*.csv")):
        for idx, row in enumerate(read_csv(path), start=1):
            out = base_row("alipay", path, idx, row)
            raw_direction = row["raw_direction"]
            status = row["status"]
            title = f"{row.get('counterparty', '')} {row.get('item_title', '')} {row.get('payment_method', '')}"
            if raw_direction == "收入":
                out["direction"] = "income"
                out["normalized_type"] = "refund_in" if "退款" in status or "refund" in title.lower() else "income"
            elif raw_direction == "其他":
                out["direction"] = "neutral"
                out["normalized_type"] = "unknown_wallet_flow"
                out["needs_review"] = "true"
            elif "repayment" in title.lower() or "PayLater April repayment" in title:
                out["direction"] = "expense"
                out["normalized_type"] = "credit_repayment"
            elif "top-up" in title.lower() or "topup" in title.lower():
                out["direction"] = "expense"
                out["normalized_type"] = "wallet_topup"
            else:
                out["direction"] = "expense"
                out["normalized_type"] = "merchant_payment"
            out["normalized_status"] = "refund" if "退款" in status else "success"
            rows.append(out)
    return rows


def parse_wechat() -> list[dict[str, str]]:
    rows = []
    for path in sorted((RAW / "wechat").glob("*.csv")):
        for idx, row in enumerate(read_csv(path), start=1):
            out = base_row("wechat", path, idx, row)
            if row["income_expense"] == "收入":
                out["direction"] = "income"
                out["normalized_type"] = "refund_in"
                out["normalized_status"] = "refund"
            elif "repayment" in row.get("item_title", "").lower():
                out["direction"] = "expense"
                out["normalized_type"] = "personal_repayment"
                out["normalized_status"] = "success"
            else:
                out["direction"] = "expense"
                out["normalized_type"] = "merchant_payment"
                out["normalized_status"] = "success"
            rows.append(out)
    return rows


def parse_bank() -> list[dict[str, str]]:
    rows = []
    for path in sorted((RAW / "bank" / "boc").glob("*.csv")):
        for idx, row in enumerate(read_csv(path), start=1):
            out = base_row("boc", path, idx, row)
            if row.get("credit"):
                out["direction"] = "income"
                out["amount"] = f"{money(row['credit']):.2f}"
                out["normalized_type"] = "salary" if "salary" in row.get("description", "").lower() else "bank_income"
            else:
                out["direction"] = "expense"
                out["amount"] = f"{money(row['debit']):.2f}"
                out["normalized_type"] = "bank_payment"
            out["normalized_status"] = "success"
            rows.append(out)
    return rows


def parse_douyin() -> list[dict[str, str]]:
    rows = []
    for path in sorted((RAW / "douyin").glob("*.csv")):
        for idx, row in enumerate(read_csv(path), start=1):
            out = base_row("douyin", path, idx, row)
            title = f"{row.get('payment_method', '')} {row.get('counterparty', '')} {row.get('item_title', '')}"
            if row["direction"] == "收入":
                out["direction"] = "income"
                out["normalized_type"] = "platform_reward" if "Reward" in title or "Campaign" in title else "refund_in"
                out["normalized_status"] = "refund" if out["normalized_type"] == "refund_in" else "success"
            elif "repayment" in title.lower():
                out["direction"] = "expense"
                out["normalized_type"] = "credit_repayment"
                out["normalized_status"] = "success"
            else:
                out["direction"] = "expense"
                out["normalized_type"] = "merchant_payment"
                out["normalized_status"] = "success"
            rows.append(out)
    return rows


def parse_meituan() -> list[dict[str, str]]:
    rows = []
    for path in sorted((RAW / "meituan").glob("*.csv")):
        for idx, row in enumerate(read_csv(path), start=1):
            out = base_row("meituan", path, idx, row)
            out["direction"] = "expense"
            out["normalized_status"] = "success"
            out["normalized_type"] = "credit_repayment" if row["kind"] == "还款" else "merchant_payment"
            rows.append(out)
    return rows


def normalize() -> list[dict[str, str]]:
    rows = parse_alipay() + parse_wechat() + parse_bank() + parse_douyin() + parse_meituan()
    rows.sort(key=lambda row: (row["transaction_time"], row["source"], row["raw_row_number"]))
    return rows


def clean(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    by_transaction = {row["transaction_id"]: row for row in rows if row["transaction_id"]}
    app_expenses = [
        row for row in rows
        if row["source"] in {"alipay", "wechat", "douyin", "meituan"}
        and row["direction"] == "expense"
        and row["normalized_type"] == "merchant_payment"
    ]
    for row in rows:
        ntype = row["normalized_type"]
        if ntype in {"credit_repayment", "personal_repayment"}:
            row["transfer_scope"] = "debt_repayment"
            row["include_in_ledger"] = "false"
            row["clean_status"] = "excluded_credit_repayment"
            row["clean_rule"] = "repayment_excluded_under_consumption_basis"
        elif ntype == "wallet_topup":
            row["transfer_scope"] = "internal"
            row["include_in_ledger"] = "false"
            row["clean_status"] = "excluded_internal_transfer"
            row["clean_rule"] = "wallet_topup_excluded"
        elif ntype == "unknown_wallet_flow":
            row["transfer_scope"] = "unknown"
            row["include_in_ledger"] = "false"
            row["clean_status"] = "needs_review"
            row["clean_rule"] = "ambiguous_wallet_flow"
        else:
            row["transfer_scope"] = "external"

        if row["source"] == "boc" and row["normalized_type"] == "bank_payment":
            bank_time = datetime.fromisoformat(row["transaction_time"])
            for app_row in app_expenses:
                if money(app_row["amount"]) != money(row["amount"]):
                    continue
                app_time = datetime.fromisoformat(app_row["transaction_time"])
                if abs((bank_time - app_time).total_seconds()) <= 120:
                    row["include_in_ledger"] = "false"
                    row["clean_status"] = "excluded_duplicate_payment"
                    row["clean_rule"] = "bank_charge_shadowed_by_app_detail"
                    row["transfer_scope"] = "external"
                    break

        if row["normalized_type"] == "refund_in" and row["related_transaction_id"]:
            original = by_transaction.get(row["related_transaction_id"])
            if original:
                row["clean_rule"] = "refund_matched_to_original_transaction"
                row["needs_review"] = "false"

    return rows


def net_contribution(row: dict[str, str], refunds_by_original: dict[str, Decimal]) -> dict[str, Decimal]:
    amount = money(row["amount"])
    result = {
        "gross_expense": Decimal("0.00"),
        "gross_income": Decimal("0.00"),
        "refund_deduction": Decimal("0.00"),
        "net_consumption": Decimal("0.00"),
    }
    if row["include_in_ledger"] != "true":
        return result
    if row["direction"] == "expense":
        result["gross_expense"] = amount
        result["refund_deduction"] = refunds_by_original.get(row["transaction_id"], Decimal("0.00"))
        result["net_consumption"] = amount - result["refund_deduction"]
    elif row["direction"] == "income" and row["normalized_type"] != "refund_in":
        result["gross_income"] = amount
    return result


def generate_outputs(rows: list[dict[str, str]]) -> None:
    refunds_by_original: dict[str, Decimal] = defaultdict(lambda: Decimal("0.00"))
    for row in rows:
        if row["normalized_type"] == "refund_in" and row["related_transaction_id"]:
            refunds_by_original[row["related_transaction_id"]] += money(row["amount"])

    summary = defaultdict(lambda: Decimal("0.00"))
    for row in rows:
        contrib = net_contribution(row, refunds_by_original)
        for key, value in contrib.items():
            summary[key] += value

    summary["net_cashflow"] = summary["gross_income"] - summary["gross_expense"]

    lines = [
        f"# Summary {PERIOD}",
        "",
        f"- Rows: {len(rows)}",
        f"- Included rows: {sum(1 for row in rows if row['include_in_ledger'] == 'true')}",
        f"- Gross expense: {summary['gross_expense']:.2f}",
        f"- Gross income: {summary['gross_income']:.2f}",
        f"- Refund deduction: {summary['refund_deduction']:.2f}",
        f"- Net consumption: {summary['net_consumption']:.2f}",
        f"- Net cashflow view: {summary['net_cashflow']:.2f}",
        "",
        "## Notes",
        "",
        "- Credit repayments and internal transfers are excluded from the main ledger.",
        "- Matched refunds reduce net consumption instead of being treated as ordinary income.",
        "- Ambiguous wallet flows are sent to manual review.",
    ]
    (FINAL / "summary").mkdir(parents=True, exist_ok=True)
    (FINAL / "summary" / f"summary_{PERIOD}.md").write_text("\n".join(lines), encoding="utf-8")

    review_rows = [
        row for row in rows
        if row["needs_review"] == "true" or row["clean_status"] == "needs_review"
    ]
    write_csv(FINAL / "review" / f"manual_review_queue_{PERIOD}.csv", review_rows)
    write_csv(FINAL / "ledger" / f"gross_ledger_{PERIOD}.csv", rows)

    html_rows = "\n".join(
        "<tr>"
        f"<td>{html.escape(row['transaction_time'])}</td>"
        f"<td>{html.escape(row['source'])}</td>"
        f"<td>{html.escape(row['direction'])}</td>"
        f"<td>{html.escape(row['amount'])}</td>"
        f"<td>{html.escape(row['normalized_type'])}</td>"
        f"<td>{html.escape(row['include_in_ledger'])}</td>"
        f"<td>{html.escape(row['clean_rule'])}</td>"
        "</tr>"
        for row in rows
    )
    page = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Personal Ledger Pipeline Demo</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; margin: 32px; color: #1f2933; }}
    table {{ border-collapse: collapse; width: 100%; font-size: 14px; }}
    th, td {{ border-bottom: 1px solid #d9e2ec; padding: 8px; text-align: left; }}
    th {{ background: #f0f4f8; }}
    .metric {{ display: inline-block; margin: 0 16px 16px 0; padding: 12px 16px; background: #f8fafc; border: 1px solid #d9e2ec; }}
  </style>
</head>
<body>
  <h1>Personal Ledger Pipeline Demo</h1>
  <div class="metric"><strong>Net consumption</strong><br>{summary['net_consumption']:.2f}</div>
  <div class="metric"><strong>Review rows</strong><br>{len(review_rows)}</div>
  <table>
    <thead><tr><th>Time</th><th>Source</th><th>Direction</th><th>Amount</th><th>Type</th><th>Included</th><th>Rule</th></tr></thead>
    <tbody>{html_rows}</tbody>
  </table>
</body>
</html>
"""
    (FINAL / "visual").mkdir(parents=True, exist_ok=True)
    (FINAL / "visual" / f"dashboard_{PERIOD}.html").write_text(page, encoding="utf-8")


def main() -> int:
    rows = normalize()
    write_csv(NORMALIZED / f"current_ledger_{PERIOD}.csv", rows)
    cleaned = clean(rows)
    write_csv(CLEANED / f"current_ledger_{PERIOD}.cleaned.csv", cleaned)
    generate_outputs(cleaned)
    print(f"Generated demo ledger for {PERIOD}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

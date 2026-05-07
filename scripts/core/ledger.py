from __future__ import annotations

import csv
from collections import defaultdict
from datetime import datetime
from decimal import Decimal
from pathlib import Path


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

REVIEW_DECISION_FIELDS = [
    "transaction_id",
    "source",
    "raw_row_number",
    "action",
    "direction",
    "normalized_type",
    "transfer_scope",
    "notes",
]


def money(value: str | Decimal) -> Decimal:
    return Decimal(str(value or "0")).quantize(Decimal("0.01"))


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, rows: list[dict[str, str]], fields: list[str] = FIELDS) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def review_decision_template(review_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    return [
        {
            "transaction_id": row.get("transaction_id", ""),
            "source": row.get("source", ""),
            "raw_row_number": row.get("raw_row_number", ""),
            "action": "",
            "direction": row.get("direction", ""),
            "normalized_type": row.get("normalized_type", ""),
            "transfer_scope": row.get("transfer_scope", ""),
            "notes": "",
        }
        for row in review_rows
    ]


def apply_review_decisions(rows: list[dict[str, str]], decisions: list[dict[str, str]]) -> list[dict[str, str]]:
    by_key = {
        _review_key(row): row
        for row in rows
        if row.get("transaction_id") or (row.get("source") and row.get("raw_row_number"))
    }
    for decision in decisions:
        action = decision.get("action", "").strip().lower()
        if not action:
            continue
        row = by_key.get(_review_key(decision))
        if row is None:
            continue
        if action == "include":
            _copy_review_fields(row, decision)
            row["include_in_ledger"] = "true"
            row["needs_review"] = "false"
            row["clean_status"] = "review_included"
            row["clean_rule"] = "manual_review_decision_include"
        elif action == "exclude":
            _copy_review_fields(row, decision)
            row["include_in_ledger"] = "false"
            row["needs_review"] = "false"
            row["clean_status"] = "review_excluded"
            row["clean_rule"] = "manual_review_decision_exclude"
        elif action in {"keep_review", "review"}:
            row["include_in_ledger"] = "false"
            row["needs_review"] = "true"
            row["clean_status"] = "needs_review"
            row["clean_rule"] = "manual_review_deferred"
        else:
            row["include_in_ledger"] = "false"
            row["needs_review"] = "true"
            row["clean_status"] = "needs_review"
            row["clean_rule"] = f"unknown_review_action:{action}"
    return rows


def _review_key(row: dict[str, str]) -> str:
    transaction_id = row.get("transaction_id", "")
    if transaction_id:
        return f"id:{transaction_id}"
    return f"row:{row.get('source', '')}:{row.get('raw_row_number', '')}"


def _copy_review_fields(row: dict[str, str], decision: dict[str, str]) -> None:
    for field in ("direction", "normalized_type", "transfer_scope"):
        value = decision.get(field, "").strip()
        if value:
            row[field] = value


def base_row(source: str, root: Path, path: Path, raw_index: int, row: dict[str, str]) -> dict[str, str]:
    amount = row.get("amount") or row.get("debit") or row.get("credit") or "0"
    return {
        "source": source,
        "source_file": str(path.relative_to(root)),
        "raw_row_number": str(raw_index),
        "transaction_time": row["transaction_time"],
        "amount": f"{money(amount):.2f}",
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
            if row["direction"] == "expense":
                row["transfer_scope"] = "debt_repayment"
                row["include_in_ledger"] = "false"
                row["clean_status"] = "excluded_credit_repayment"
                row["clean_rule"] = "repayment_excluded_under_consumption_basis"
            else:
                row["transfer_scope"] = "repayment_review"
                row["include_in_ledger"] = "false"
                row["needs_review"] = "true"
                row["clean_status"] = "needs_review"
                row["clean_rule"] = "repayment_candidate_failed_direction_check"
        elif ntype == "repayment_candidate_review":
            row["transfer_scope"] = "repayment_review"
            row["include_in_ledger"] = "false"
            row["needs_review"] = "true"
            row["clean_status"] = "needs_review"
            row["clean_rule"] = "repayment_candidate_failed_adjustment_check"
        elif ntype in {"wallet_topup", "internal_transfer"}:
            row["transfer_scope"] = "internal"
            row["include_in_ledger"] = "false"
            row["clean_status"] = "excluded_internal_transfer"
            row["clean_rule"] = "internal_transfer_excluded"
        elif ntype == "unknown_wallet_flow":
            row["transfer_scope"] = "unknown"
            row["include_in_ledger"] = "false"
            row["clean_status"] = "needs_review"
            row["clean_rule"] = "ambiguous_wallet_flow"
        else:
            row["transfer_scope"] = row.get("transfer_scope") or "external"

        if row["source"] in {"boc", "cmb", "icbc", "abc"} and row["normalized_type"] == "bank_payment":
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


def build_refunds_by_original(rows: list[dict[str, str]]) -> dict[str, Decimal]:
    refunds_by_original: dict[str, Decimal] = defaultdict(lambda: Decimal("0.00"))
    for row in rows:
        if row["normalized_type"] == "refund_in" and row["related_transaction_id"]:
            refunds_by_original[row["related_transaction_id"]] += money(row["amount"])
    return refunds_by_original


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


def build_summary(rows: list[dict[str, str]], refunds_by_original: dict[str, Decimal]) -> dict[str, Decimal]:
    summary = defaultdict(lambda: Decimal("0.00"))
    for row in rows:
        contrib = net_contribution(row, refunds_by_original)
        for key, value in contrib.items():
            summary[key] += value

    summary["net_cashflow"] = summary["gross_income"] - summary["gross_expense"]
    return summary


def row_net_consumption(row: dict[str, str], refunds_by_original: dict[str, Decimal]) -> Decimal:
    return net_contribution(row, refunds_by_original)["net_consumption"]

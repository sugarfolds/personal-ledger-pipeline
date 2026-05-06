#!/usr/bin/env python3

from __future__ import annotations

import csv
import html
import json
from collections import defaultdict
from datetime import datetime
from decimal import Decimal
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "raw"
NORMALIZED = ROOT / "processed" / "normalized"
CLEANED = ROOT / "processed" / "cleaned"
FINAL = ROOT / "final"
EXAMPLES = ROOT / "examples"
PERIOD = "2026-04-01_to_2026-04-30"
REPORT_YEAR = "2026"


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


def build_refunds_by_original(rows: list[dict[str, str]]) -> dict[str, Decimal]:
    refunds_by_original: dict[str, Decimal] = defaultdict(lambda: Decimal("0.00"))
    for row in rows:
        if row["normalized_type"] == "refund_in" and row["related_transaction_id"]:
            refunds_by_original[row["related_transaction_id"]] += money(row["amount"])
    return refunds_by_original


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


def money_text(value: Decimal) -> str:
    return f"{value:,.2f}"


def percent_text(value: Decimal) -> str:
    return f"{value:.2%}"


def safe_json_for_script(payload: object) -> str:
    return (
        json.dumps(payload, ensure_ascii=False)
        .replace("&", "\\u0026")
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
        .replace("</", "<\\/")
    )


def clean_output_text(value: str) -> str:
    return "\n".join(line.rstrip() for line in value.splitlines()) + "\n"


def build_annual_report_context(
    rows: list[dict[str, str]],
    summary: dict[str, Decimal],
    refunds_by_original: dict[str, Decimal],
    review_rows: list[dict[str, str]],
) -> dict[str, object]:
    repayment_total = sum(
        money(row["amount"])
        for row in rows
        if row["transfer_scope"] == "debt_repayment"
    )
    internal_transfer_total = sum(
        money(row["amount"])
        for row in rows
        if row["transfer_scope"] == "internal"
    )
    duplicate_total = sum(
        money(row["amount"])
        for row in rows
        if row["clean_status"] == "excluded_duplicate_payment"
    )

    by_source: dict[str, Decimal] = defaultdict(lambda: Decimal("0.00"))
    for row in rows:
        if row["include_in_ledger"] == "true" and row["direction"] == "expense":
            by_source[row["source"]] += row_net_consumption(row, refunds_by_original)

    top_source = max(by_source.items(), key=lambda item: item[1], default=("n/a", Decimal("0.00")))
    review_ratio = Decimal(len(review_rows)) / Decimal(len(rows)) if rows else Decimal("0.00")
    repayment_pressure = repayment_total / summary["net_consumption"] if summary["net_consumption"] else Decimal("0.00")
    refund_ratio = summary["refund_deduction"] / summary["gross_expense"] if summary["gross_expense"] else Decimal("0.00")

    if summary["net_consumption"] == 0:
        persona = "Zero-Spend CFO"
        persona_roast = "Operations were so quiet that even the audit committee had to check whether the company had launched."
        metaphor = "A pre-revenue company with unusually disciplined procurement."
    elif repayment_total > summary["net_consumption"] / 2:
        persona = "Debt-Service Maximalist"
        persona_roast = "This period did not spend wildly; it merely let past spending return with an invoice and a calendar invite."
        metaphor = "A small company whose liabilities have better follow-up habits than its management team."
    elif review_ratio > Decimal("0.10"):
        persona = "Audit-Committee Frequent Flyer"
        persona_roast = "The books are not messy enough to be scandalous, just messy enough to deserve a second meeting."
        metaphor = "A business that keeps finding footnotes in places where normal people keep receipts."
    elif top_source[1] > summary["net_consumption"] / 2:
        persona = "Single-Segment Enthusiast"
        persona_roast = f"Diversification was available, but {top_source[0]} apparently won the board vote by acclamation."
        metaphor = f"A focused single-segment company with {top_source[0]} acting as both revenue engine and personality test."
    else:
        persona = "Diversified Small-Cap Household"
        persona_roast = "No one category ruined the period. This is called diversification, or in personal finance, plausible deniability."
        metaphor = "A small, diversified company where every department is small enough to deny responsibility."

    cashflow_operating = summary["gross_income"] - summary["net_consumption"]
    cashflow_investing = Decimal("0.00")
    cashflow_financing = -repayment_total
    cashflow_net_movement = cashflow_operating + cashflow_investing + cashflow_financing

    segment_rows = sorted(by_source.items(), key=lambda item: item[1], reverse=True)
    return {
        "summary": summary,
        "rows_count": len(rows),
        "included_rows_count": sum(1 for row in rows if row["include_in_ledger"] == "true"),
        "review_rows_count": len(review_rows),
        "repayment_total": repayment_total,
        "internal_transfer_total": internal_transfer_total,
        "duplicate_total": duplicate_total,
        "top_source": top_source,
        "repayment_pressure": repayment_pressure,
        "refund_ratio": refund_ratio,
        "persona": persona,
        "persona_roast": persona_roast,
        "metaphor": metaphor,
        "cashflow_operating": cashflow_operating,
        "cashflow_investing": cashflow_investing,
        "cashflow_financing": cashflow_financing,
        "cashflow_net_movement": cashflow_net_movement,
        "segment_rows": segment_rows,
    }


def build_annual_report(
    rows: list[dict[str, str]],
    summary: dict[str, Decimal],
    refunds_by_original: dict[str, Decimal],
    review_rows: list[dict[str, str]],
) -> str:
    context = build_annual_report_context(rows, summary, refunds_by_original, review_rows)
    repayment_total = context["repayment_total"]
    internal_transfer_total = context["internal_transfer_total"]
    duplicate_total = context["duplicate_total"]
    top_source = context["top_source"]
    repayment_pressure = context["repayment_pressure"]
    refund_ratio = context["refund_ratio"]
    persona = context["persona"]
    persona_roast = context["persona_roast"]
    metaphor = context["metaphor"]
    cashflow_operating = context["cashflow_operating"]
    cashflow_investing = context["cashflow_investing"]
    cashflow_financing = context["cashflow_financing"]
    cashflow_net_movement = context["cashflow_net_movement"]

    segment_lines = [
        f"- `{source}`: {amount:.2f} net consumption"
        for source, amount in context["segment_rows"]
    ] or ["- No included consumption segment in this demo period."]

    annual_report_lines = [
        f"# Personal Annual Report {REPORT_YEAR}",
        "",
        f"Demo period: `{PERIOD}`",
        "",
        "This report is generated from the cleaned ledger only. It is a portfolio-safe synthetic demo, not a production accounting statement. It is serious about the math and mildly judgmental about the behavior.",
        "",
        "## Letter to Shareholders",
        "",
        "Dear shareholders, creditors, future selves, and anyone still pretending that a transaction export is a personality-neutral object:",
        "",
        f"Management reports net consumption of {summary['net_consumption']:.2f} after refund deductions. "
        f"The company remained cash-flow positive in the ledger view, mostly because income did the heavy lifting while spending tried to look strategic in a quarter-end deck.",
        "",
        f"The headline risk is not extravagance. It is timing. Repayments totaled {repayment_total:.2f}, which means earlier consumption came back wearing a suit and calling itself financial discipline.",
        "",
        "## Financial Highlights",
        "",
        f"- Rows reviewed: {len(rows)}",
        f"- Included ledger rows: {sum(1 for row in rows if row['include_in_ledger'] == 'true')}",
        f"- Gross income: {summary['gross_income']:.2f}",
        f"- Gross expense before refund deduction: {summary['gross_expense']:.2f}",
        f"- Refund deduction: {summary['refund_deduction']:.2f}",
        f"- Net consumption: {summary['net_consumption']:.2f}",
        f"- Ledger-view net cashflow: {summary['net_cashflow']:.2f}",
        f"- Manual review rows: {len(review_rows)}",
        f"- Repayment pressure: {repayment_pressure:.2%}",
        f"- Refund recovery rate: {refund_ratio:.2%}",
        "",
        "## Personal Income Statement",
        "",
        "| Line item | Amount |",
        "| --- | ---: |",
        f"| Income | {summary['gross_income']:.2f} |",
        f"| Gross expense | {summary['gross_expense']:.2f} |",
        f"| Refund deduction | {summary['refund_deduction']:.2f} |",
        f"| Net consumption | {summary['net_consumption']:.2f} |",
        f"| Net cashflow view | {summary['net_cashflow']:.2f} |",
        "",
        "## Personal Cash Flow Statement",
        "",
        "| Cash flow class | Amount | Rule |",
        "| --- | ---: | --- |",
        f"| Operating cash flow | {cashflow_operating:.2f} | Included income minus net consumption |",
        f"| Investing cash flow | {cashflow_investing:.2f} | No investment transaction type in the v1 synthetic sample |",
        f"| Financing / repayment cash flow | {cashflow_financing:.2f} | Debt repayment rows are excluded from consumption but shown here as repayment timing |",
        f"| Net cash movement view | {cashflow_net_movement:.2f} | Operating + investing + financing |",
        "",
        "## Personal Balance Sheet",
        "",
        "Balance sheet is not available in the ledger-only v1 demo. The pipeline does not invent assets, liabilities, or account balances without a balance snapshot input.",
        "",
        "## Management Discussion and Analysis",
        "",
        f"During the demo period, the ledger generated {summary['net_consumption']:.2f} of net consumption after matched refund deductions. "
        f"Credit repayments of {repayment_total:.2f} were kept out of new consumption, which is the correct accounting treatment and also a polite way of saying the past cannot be deleted, only classified.",
        "",
        f"Refunds recovered {summary['refund_deduction']:.2f}. Management would like credit for this; the audit committee notes that buying something and returning it is not the same as earning money.",
        "",
        "## Risk Factors",
        "",
        f"- Manual review risk: {len(review_rows)} row(s) require human confirmation. The machine is honest enough to admit confusion, which already puts it ahead of many dashboards.",
        f"- Repayment matching risk: {repayment_total:.2f} of debt repayment flow is excluded from consumption. Counting it again would be double counting, also known as budgeting by jump scare.",
        f"- Internal transfer risk: {internal_transfer_total:.2f} of wallet or account movement is excluded from spend views. Moving money between pockets is not revenue, despite what optimism may imply.",
        f"- Duplicate-source risk: {duplicate_total:.2f} of bank-side charges were treated as app-side shadows. One purchase appearing twice is a data problem, not a lifestyle escalation.",
        "",
        "## Segment Performance",
        "",
        *segment_lines,
        "",
        "Management congratulates the leading segment while reminding it that dominance in a synthetic dataset is not a moat.",
        "",
        "## Capital Allocation Review",
        "",
        f"- Consumption allocated to visible operating activity: {summary['net_consumption']:.2f}.",
        f"- Cash tied to repayment timing: {repayment_total:.2f}. The board recommends fewer surprise sequels.",
        f"- Refunds recovered: {summary['refund_deduction']:.2f}. Useful, but not a business model.",
        f"- Manual review queue: {len(review_rows)} item(s). This is where ambiguity goes before it becomes a bad chart.",
        "",
        "## Auditor Notes",
        "",
        "- The annual report uses cleaned rows, not raw exports.",
        "- Refunds reduce original consumption when `related_transaction_id` is available.",
        "- Ambiguous wallet flows stay in the manual review queue instead of being silently guessed.",
        "- Douyin and other platform bills are treated as source-specific inputs because rewards, refunds, repayment labels, and merchant payments can share similar export shapes.",
        "",
        "## Consumption Persona",
        "",
        f"- Persona: {persona}",
        f"- Roast: {persona_roast}",
        f"- Annual metaphor: {metaphor}",
        f"- Annual keyword: `{top_source[0]}`",
        f"- Annual line: The best margin improvement still came from expenses that never made it past the idea stage.",
        "",
        "## Board Verdict",
        "",
        "The board finds the household entity solvent, traceable, and occasionally overconfident. The finance function has improved. The strategy function is invited to stop calling every purchase an investment.",
        "",
    ]
    return "\n".join(annual_report_lines)


def build_annual_report_html(
    rows: list[dict[str, str]],
    summary: dict[str, Decimal],
    refunds_by_original: dict[str, Decimal],
    review_rows: list[dict[str, str]],
    *,
    dashboard_href: str | None = None,
) -> str:
    context = build_annual_report_context(rows, summary, refunds_by_original, review_rows)
    repayment_total = context["repayment_total"]
    internal_transfer_total = context["internal_transfer_total"]
    duplicate_total = context["duplicate_total"]
    top_source = context["top_source"]
    repayment_pressure = context["repayment_pressure"]
    refund_ratio = context["refund_ratio"]
    persona = context["persona"]
    persona_roast = context["persona_roast"]
    metaphor = context["metaphor"]
    cashflow_operating = context["cashflow_operating"]
    cashflow_investing = context["cashflow_investing"]
    cashflow_financing = context["cashflow_financing"]
    cashflow_net_movement = context["cashflow_net_movement"]
    segment_rows = context["segment_rows"]
    max_segment = max((amount for _, amount in segment_rows), default=Decimal("0.00"))

    zh_persona = {
        "Zero-Spend CFO": "零支出 CFO",
        "Debt-Service Maximalist": "还款优先型 CFO",
        "Audit-Committee Frequent Flyer": "审计委员会常驻嘉宾",
        "Single-Segment Enthusiast": "单一分部信仰者",
        "Diversified Small-Cap Household": "分散型小市值家庭公司",
    }.get(str(persona), str(persona))

    def metric(label_en: str, label_zh: str, value: str, note_en: str, note_zh: str) -> str:
        return f"""
        <article class="metric">
          <span class="label lang lang-en">{html.escape(label_en)}</span>
          <span class="label lang lang-zh">{html.escape(label_zh)}</span>
          <strong>{html.escape(value)}</strong>
          <small class="lang lang-en">{html.escape(note_en)}</small>
          <small class="lang lang-zh">{html.escape(note_zh)}</small>
        </article>"""

    def table_row(label_en: str, label_zh: str, value: Decimal, rule_en: str = "", rule_zh: str = "") -> str:
        rule_cell = ""
        if rule_en or rule_zh:
            rule_cell = (
                f"<td><span class=\"lang lang-en\">{html.escape(rule_en)}</span>"
                f"<span class=\"lang lang-zh\">{html.escape(rule_zh)}</span></td>"
            )
        return (
            "<tr>"
            f"<th><span class=\"lang lang-en\">{html.escape(label_en)}</span>"
            f"<span class=\"lang lang-zh\">{html.escape(label_zh)}</span></th>"
            f"<td>{money_text(value)}</td>"
            f"{rule_cell}"
            "</tr>"
        )

    segment_html = "\n".join(
        f"""
        <div class="segment-row">
          <div class="segment-top">
            <strong>{html.escape(source)}</strong>
            <span>{money_text(amount)}</span>
          </div>
          <div class="bar"><span style="width: {int((amount / max_segment) * 100) if max_segment else 0}%"></span></div>
        </div>"""
        for source, amount in segment_rows
    ) or """
        <div class="segment-row">
          <div class="segment-top">
            <strong>n/a</strong>
            <span>0.00</span>
          </div>
          <div class="bar"><span style="width: 0%"></span></div>
        </div>"""

    income_statement_rows = "\n".join([
        table_row("Income", "收入", summary["gross_income"]),
        table_row("Gross expense", "退款前总支出", summary["gross_expense"]),
        table_row("Refund deduction", "退款抵扣", summary["refund_deduction"]),
        table_row("Net consumption", "净消费", summary["net_consumption"]),
        table_row("Net cashflow view", "账本视角净现金流", summary["net_cashflow"]),
    ])
    cashflow_rows = "\n".join([
        table_row("Operating cash flow", "经营性现金流", cashflow_operating, "Included income minus net consumption", "纳入收入减去净消费"),
        table_row("Investing cash flow", "投资性现金流", cashflow_investing, "No investment transaction type in the v1 sample", "v1 样本暂无投资交易类型"),
        table_row("Financing / repayment cash flow", "融资 / 还款现金流", cashflow_financing, "Debt repayments shown as timing, not new consumption", "还款作为时点展示，不计入新消费"),
        table_row("Net cash movement view", "净现金变动视角", cashflow_net_movement, "Operating + investing + financing", "经营性 + 投资性 + 融资性现金流"),
    ])
    chart_payload = {
        "segments": {
            "summaryEn": "Included net consumption by source after refund and repayment handling.",
            "summaryZh": "按来源查看已纳入消费口径的净消费，已处理退款和还款排除。",
            "items": [
                {"labelEn": source, "labelZh": source, "value": float(amount), "display": money_text(amount)}
                for source, amount in segment_rows
            ],
        },
        "cashflow": {
            "summaryEn": "A simplified cash-flow bridge built from cleaned ledger rules.",
            "summaryZh": "用 cleaned ledger 规则生成的简化现金流桥。",
            "items": [
                {"labelEn": "Operating", "labelZh": "经营性", "value": float(cashflow_operating.copy_abs()), "display": money_text(cashflow_operating)},
                {"labelEn": "Investing", "labelZh": "投资性", "value": float(cashflow_investing.copy_abs()), "display": money_text(cashflow_investing)},
                {"labelEn": "Financing / repayment", "labelZh": "融资 / 还款", "value": float(cashflow_financing.copy_abs()), "display": money_text(cashflow_financing)},
                {"labelEn": "Net movement", "labelZh": "净现金变动", "value": float(cashflow_net_movement.copy_abs()), "display": money_text(cashflow_net_movement)},
            ],
        },
        "governance": {
            "summaryEn": "Rows excluded from new-consumption math but still shown for traceability.",
            "summaryZh": "这些项目不计入新消费，但保留在治理和追溯视图中。",
            "items": [
                {"labelEn": "Repayments", "labelZh": "还款", "value": float(repayment_total), "display": money_text(repayment_total)},
                {"labelEn": "Internal transfers", "labelZh": "内部转账", "value": float(internal_transfer_total), "display": money_text(internal_transfer_total)},
                {"labelEn": "Duplicate app shadows", "labelZh": "重复来源影子记录", "value": float(duplicate_total), "display": money_text(duplicate_total)},
                {"labelEn": "Manual review rows", "labelZh": "人工复核行数", "value": float(context["review_rows_count"]), "display": str(context["review_rows_count"])},
            ],
        },
    }
    chart_json = safe_json_for_script(chart_payload)
    back_link_html = ""
    if dashboard_href:
        back_link_html = (
            f'<a class="back-link" href="{html.escape(dashboard_href)}">'
            '<span class="lang lang-en">Back to dashboard</span>'
            '<span class="lang lang-zh">回到总览页</span>'
            '</a>'
        )

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Personal Annual Report {REPORT_YEAR}</title>
  <style>
    :root {{
      --paper: #f7f8f3;
      --ink: #151716;
      --muted: #626b65;
      --line: #d8ddd4;
      --panel: #ffffff;
      --green: #2f6f4e;
      --blue: #315f8c;
      --red: #a33d3d;
      --gold: #9a6a16;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      background: var(--paper);
      color: var(--ink);
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      line-height: 1.55;
    }}
    body[data-lang="en"] .lang-zh,
    body[data-lang="zh"] .lang-en {{ display: none; }}
    .report-header {{
      border-bottom: 1px solid var(--line);
      background: #fbfcf8;
    }}
    .wrap {{ width: min(1120px, calc(100% - 32px)); margin: 0 auto; }}
    .topbar {{
      min-height: 56px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 16px;
      border-bottom: 1px solid var(--line);
    }}
    .brand {{ font-size: 13px; color: var(--muted); text-transform: uppercase; letter-spacing: 0; }}
    .top-actions {{ display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }}
    .back-link {{
      color: var(--green);
      text-decoration: none;
      border-bottom: 1px solid rgba(47, 111, 78, 0.35);
      font-size: 13px;
    }}
    .toggle {{ display: flex; gap: 6px; }}
    .toggle button {{
      border: 1px solid var(--line);
      background: var(--panel);
      color: var(--ink);
      padding: 7px 10px;
      border-radius: 6px;
      cursor: pointer;
      font: inherit;
      font-size: 13px;
    }}
    .toggle button[aria-pressed="true"] {{
      background: var(--ink);
      border-color: var(--ink);
      color: #fff;
    }}
    .hero {{
      padding: 44px 0 36px;
      display: grid;
      grid-template-columns: minmax(0, 1.35fr) minmax(260px, 0.65fr);
      gap: 32px;
      align-items: end;
    }}
    h1 {{
      margin: 0 0 16px;
      font-size: clamp(38px, 6vw, 76px);
      line-height: 0.95;
      letter-spacing: 0;
    }}
    .subtitle {{ max-width: 760px; color: #3f4742; font-size: 18px; margin: 0; }}
    .stamp {{
      border-left: 4px solid var(--red);
      padding: 12px 0 12px 18px;
      color: var(--muted);
      font-size: 14px;
    }}
    main {{ padding: 28px 0 64px; }}
    .metrics {{
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 12px;
      margin-bottom: 28px;
    }}
    .metric {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 16px;
      min-height: 132px;
    }}
    .metric .label {{ display: block; color: var(--muted); font-size: 13px; }}
    .metric strong {{ display: block; margin: 10px 0 8px; font-size: 26px; line-height: 1; }}
    .metric small {{ color: var(--muted); }}
    .band {{
      padding: 28px 0;
      border-top: 1px solid var(--line);
    }}
    .band h2 {{ margin: 0 0 14px; font-size: 24px; letter-spacing: 0; }}
    .two-col {{
      display: grid;
      grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
      gap: 20px;
    }}
    .note {{
      background: #fff;
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 18px;
    }}
    .note strong {{ color: var(--red); }}
    table {{
      width: 100%;
      border-collapse: collapse;
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      overflow: hidden;
    }}
    th, td {{ padding: 12px 14px; border-bottom: 1px solid var(--line); text-align: left; vertical-align: top; }}
    td:nth-child(2) {{ text-align: right; font-variant-numeric: tabular-nums; }}
    tr:last-child th, tr:last-child td {{ border-bottom: 0; }}
    th {{ width: 34%; font-weight: 600; }}
    .risk-grid {{
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 12px;
    }}
    .risk {{
      border: 1px solid var(--line);
      border-left: 4px solid var(--red);
      background: var(--panel);
      border-radius: 8px;
      padding: 16px;
    }}
    .risk h3 {{ margin: 0 0 8px; font-size: 16px; }}
    .risk p {{ margin: 0; color: var(--muted); }}
    .segment-row {{ margin: 0 0 14px; }}
    .segment-top {{ display: flex; justify-content: space-between; gap: 12px; margin-bottom: 6px; }}
    .bar {{ height: 10px; background: #e8ebe4; border-radius: 999px; overflow: hidden; }}
    .bar span {{ display: block; height: 100%; background: var(--blue); }}
    .chart-shell {{
      display: grid;
      grid-template-columns: 260px minmax(0, 1fr);
      gap: 20px;
      align-items: start;
    }}
    .chart-controls {{ display: grid; gap: 8px; }}
    .chart-button {{
      width: 100%;
      border: 1px solid var(--line);
      background: var(--panel);
      border-radius: 8px;
      padding: 12px 14px;
      color: var(--ink);
      cursor: pointer;
      font: inherit;
      text-align: left;
    }}
    .chart-button[aria-pressed="true"] {{ background: var(--ink); color: #fff; border-color: var(--ink); }}
    .chart-explorer {{ background: var(--panel); border: 1px solid var(--line); border-radius: 8px; padding: 18px; }}
    .chart-summary {{ color: var(--muted); margin: 0 0 16px; }}
    .chart-list {{ display: grid; gap: 12px; }}
    .chart-item {{
      display: grid;
      grid-template-columns: minmax(120px, .38fr) minmax(0, 1fr) 92px;
      gap: 12px;
      align-items: center;
    }}
    .chart-label {{ font-weight: 700; }}
    .chart-value {{ color: var(--muted); font-variant-numeric: tabular-nums; text-align: right; }}
    .persona {{
      display: grid;
      grid-template-columns: minmax(0, 0.55fr) minmax(0, 1fr);
      gap: 20px;
      align-items: stretch;
    }}
    .persona-badge {{
      background: var(--ink);
      color: #fff;
      border-radius: 8px;
      padding: 22px;
    }}
    .persona-badge span {{ display: block; color: #c8d1ca; font-size: 13px; margin-bottom: 8px; }}
    .persona-badge strong {{ font-size: 26px; line-height: 1.1; }}
    .verdict {{
      border-top: 3px solid var(--gold);
      background: #fff;
      padding: 22px;
      font-size: 18px;
    }}
    .footnote {{ color: var(--muted); font-size: 13px; margin-top: 30px; }}
    @media (max-width: 820px) {{
      .hero, .two-col, .persona, .chart-shell {{ grid-template-columns: 1fr; }}
      .metrics, .risk-grid {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
    }}
    @media (max-width: 560px) {{
      .wrap {{ width: min(100% - 20px, 1120px); }}
      .topbar {{ align-items: flex-start; flex-direction: column; padding: 12px 0; }}
      .top-actions {{ align-items: flex-start; }}
      .metrics, .risk-grid {{ grid-template-columns: 1fr; }}
      .chart-item {{ grid-template-columns: 1fr; gap: 6px; }}
      .chart-value {{ text-align: left; }}
      th, td {{ display: block; width: 100%; }}
      td:nth-child(2) {{ text-align: left; }}
    }}
  </style>
</head>
<body data-lang="en">
  <header class="report-header">
    <div class="wrap">
      <div class="topbar">
        <div class="brand">personal-ledger-pipeline / annual report demo</div>
        <div class="top-actions">
          {back_link_html}
          <div class="toggle" aria-label="Language">
            <button type="button" data-set-lang="en" aria-pressed="true">EN</button>
            <button type="button" data-set-lang="zh" aria-pressed="false">中文</button>
          </div>
        </div>
      </div>
      <section class="hero">
        <div>
          <h1 class="lang lang-en">Personal Annual Report {REPORT_YEAR}</h1>
          <h1 class="lang lang-zh">个人年度报告 {REPORT_YEAR}</h1>
          <p class="subtitle lang lang-en">A traceable ledger report with financial statements, audit notes, and just enough judgment to keep the budget honest.</p>
          <p class="subtitle lang lang-zh">一份从清洗后账本生成的网页年报：有财务三表、审计说明，也有一点让预算无法装睡的锐评。</p>
        </div>
        <aside class="stamp">
          <span class="lang lang-en">Demo period</span><span class="lang lang-zh">演示期间</span><br>
          <strong>{html.escape(PERIOD)}</strong><br>
          <span class="lang lang-en">Synthetic data only. No real account balances.</span>
          <span class="lang lang-zh">仅使用合成数据，不包含真实账户余额。</span>
        </aside>
      </section>
    </div>
  </header>
  <main class="wrap">
    <section class="metrics" aria-label="Financial highlights">
      {metric("Net consumption", "净消费", money_text(summary["net_consumption"]), "After matched refund deductions", "已扣除可匹配退款")}
      {metric("Ledger cashflow", "账本净现金流", money_text(summary["net_cashflow"]), "Income minus gross expense", "收入减退款前总支出")}
      {metric("Repayment pressure", "还款压力", percent_text(repayment_pressure), "Past spending came back on schedule", "历史消费按时回来敲门")}
      {metric("Manual review", "人工复核", str(context["review_rows_count"]), "Rows the system refused to guess", "系统拒绝硬猜的流水")}
    </section>

    <section class="band">
      <h2 class="lang lang-en">Letter to Shareholders</h2>
      <h2 class="lang lang-zh">致股东信</h2>
      <div class="note">
        <p class="lang lang-en">Dear shareholders, creditors, future selves, and anyone still pretending that a transaction export is a personality-neutral object:</p>
        <p class="lang lang-zh">致各位股东、债权人、未来的自己，以及仍然相信账单导出不暴露性格的朋友：</p>
        <p class="lang lang-en">Management reports net consumption of <strong>{money_text(summary["net_consumption"])}</strong> after refund deductions. The company remained cash-flow positive mostly because income did the heavy lifting while spending tried to look strategic in a quarter-end deck.</p>
        <p class="lang lang-zh">管理层报告，本期退款抵扣后的净消费为 <strong>{money_text(summary["net_consumption"])}</strong>。公司维持账本口径现金流为正，主要原因是收入承担了大部分体力活，而支出负责在季末汇报里假装自己很有战略意义。</p>
        <p class="lang lang-en">The headline risk is not extravagance. It is timing. Repayments totaled <strong>{money_text(repayment_total)}</strong>, which means earlier consumption came back wearing a suit and calling itself financial discipline.</p>
        <p class="lang lang-zh">本期最大风险来自时点，而非挥霍。还款合计 <strong>{money_text(repayment_total)}</strong>，说明早先的消费换了身西装回来，并自称财务纪律。</p>
      </div>
    </section>

    <section class="band two-col">
      <div>
        <h2 class="lang lang-en">Income Statement</h2>
        <h2 class="lang lang-zh">个人利润表</h2>
        <table>{income_statement_rows}</table>
      </div>
      <div>
        <h2 class="lang lang-en">Cash Flow Statement</h2>
        <h2 class="lang lang-zh">个人现金流量表</h2>
        <table>{cashflow_rows}</table>
      </div>
    </section>

    <section class="band">
      <h2 class="lang lang-en">Balance Sheet</h2>
      <h2 class="lang lang-zh">个人资产负债表</h2>
      <div class="note">
        <p class="lang lang-en">Not available in the ledger-only v1 demo. The pipeline does not invent assets, liabilities, or account balances without a balance snapshot input.</p>
        <p class="lang lang-zh">v1 账本演示暂不生成资产负债表。仅凭交易流水不能可靠推断资产、负债或账户余额；没有余额快照输入时，系统不会虚构这些数据。</p>
      </div>
    </section>

    <section class="band">
      <h2 class="lang lang-en">Management Discussion and Analysis</h2>
      <h2 class="lang lang-zh">管理层讨论与分析</h2>
      <div class="two-col">
        <p class="lang lang-en">The ledger generated <strong>{money_text(summary["net_consumption"])}</strong> of net consumption after matched refund deductions. Credit repayments of <strong>{money_text(repayment_total)}</strong> were kept out of new consumption, which is the correct accounting treatment and also a polite way of saying the past cannot be deleted, only classified.</p>
        <p class="lang lang-zh">账本在匹配退款抵扣后形成 <strong>{money_text(summary["net_consumption"])}</strong> 的净消费。<strong>{money_text(repayment_total)}</strong> 的信用还款未计入新消费，这是正确的会计处理，也是一种比较体面的说法：过去不能删除，只能分类。</p>
        <p class="lang lang-en">Refunds recovered <strong>{money_text(summary["refund_deduction"])}</strong>. Management would like credit for this; the audit committee notes that buying something and returning it is not the same as earning money.</p>
        <p class="lang lang-zh">本期退款回收 <strong>{money_text(summary["refund_deduction"])}</strong>。管理层希望对此邀功；审计委员会提醒，买了又退不等于创造收入。</p>
      </div>
    </section>

    <section class="band">
      <h2 class="lang lang-en">Risk Factors</h2>
      <h2 class="lang lang-zh">风险因素</h2>
      <div class="risk-grid">
        <article class="risk"><h3 class="lang lang-en">Manual review risk</h3><h3 class="lang lang-zh">人工复核风险</h3><p class="lang lang-en">{context["review_rows_count"]} row(s) require human confirmation. The machine is honest enough to admit confusion, which already puts it ahead of many dashboards.</p><p class="lang lang-zh">{context["review_rows_count"]} 行流水需要人工确认。机器至少承认自己看不懂，这已经比很多仪表盘诚实。</p></article>
        <article class="risk"><h3 class="lang lang-en">Repayment matching risk</h3><h3 class="lang lang-zh">还款匹配风险</h3><p class="lang lang-en">{money_text(repayment_total)} of repayment flow is excluded from consumption. Counting it again would be budgeting by jump scare.</p><p class="lang lang-zh">{money_text(repayment_total)} 的还款流量已从消费口径剔除。再算一次，就是用惊吓法做预算。</p></article>
        <article class="risk"><h3 class="lang lang-en">Internal transfer risk</h3><h3 class="lang lang-zh">内部转账风险</h3><p class="lang lang-en">{money_text(internal_transfer_total)} moved between pockets. Moving money around is not revenue, despite what optimism may imply.</p><p class="lang lang-zh">{money_text(internal_transfer_total)} 属于账户间流动。钱从左口袋到右口袋，不会因为路径变长就变成收入。</p></article>
        <article class="risk"><h3 class="lang lang-en">Duplicate-source risk</h3><h3 class="lang lang-zh">多来源重复风险</h3><p class="lang lang-en">{money_text(duplicate_total)} of bank-side charges were treated as app-side shadows. One purchase appearing twice is a data problem, not lifestyle escalation.</p><p class="lang lang-zh">{money_text(duplicate_total)} 的银行卡侧扣款被识别为 app 支付影子记录。一笔消费出现两次，属于数据问题，不该升级成生活方式检讨。</p></article>
      </div>
    </section>

    <section class="band">
      <h2 class="lang lang-en">Chart Explorer</h2>
      <h2 class="lang lang-zh">图表查看器</h2>
      <div class="chart-shell">
        <div class="chart-controls" aria-label="Chart datasets">
          <button class="chart-button" type="button" data-chart="segments" aria-pressed="true">
            <span class="lang lang-en">Source Segments</span><span class="lang lang-zh">来源分部</span>
          </button>
          <button class="chart-button" type="button" data-chart="cashflow" aria-pressed="false">
            <span class="lang lang-en">Cash Flow Bridge</span><span class="lang lang-zh">现金流桥</span>
          </button>
          <button class="chart-button" type="button" data-chart="governance" aria-pressed="false">
            <span class="lang lang-en">Governance Items</span><span class="lang lang-zh">治理项目</span>
          </button>
        </div>
        <div class="chart-explorer">
          <p class="chart-summary" data-chart-summary></p>
          <div class="chart-list" data-chart-list></div>
        </div>
      </div>
    </section>

    <section class="band two-col">
      <div>
        <h2 class="lang lang-en">Segment Performance</h2>
        <h2 class="lang lang-zh">分部表现</h2>
        {segment_html}
        <p class="lang lang-en">Management congratulates the leading segment while reminding it that dominance in a synthetic dataset is not a moat.</p>
        <p class="lang lang-zh">管理层祝贺领先分部，同时提醒它：在合成数据里领先，不构成护城河。</p>
      </div>
      <div>
        <h2 class="lang lang-en">Capital Allocation Review</h2>
        <h2 class="lang lang-zh">资本配置回顾</h2>
        <div class="note">
          <p class="lang lang-en">Consumption allocated to visible operations: <strong>{money_text(summary["net_consumption"])}</strong>.</p>
          <p class="lang lang-zh">分配至可见经营活动的消费：<strong>{money_text(summary["net_consumption"])}</strong>。</p>
          <p class="lang lang-en">Cash tied to repayment timing: <strong>{money_text(repayment_total)}</strong>. The board recommends fewer surprise sequels.</p>
          <p class="lang lang-zh">被还款时点占用的现金：<strong>{money_text(repayment_total)}</strong>。董事会建议减少这种突袭式续集。</p>
          <p class="lang lang-en">Refunds recovered: <strong>{money_text(summary["refund_deduction"])}</strong>. Useful, but not a business model.</p>
          <p class="lang lang-zh">退款回收：<strong>{money_text(summary["refund_deduction"])}</strong>。有用，但还撑不起一个商业模式。</p>
        </div>
      </div>
    </section>

    <section class="band persona">
      <div class="persona-badge">
        <span class="lang lang-en">Consumption persona</span>
        <span class="lang lang-zh">消费人格画像</span>
        <strong class="lang lang-en">{html.escape(str(persona))}</strong>
        <strong class="lang lang-zh">{html.escape(zh_persona)}</strong>
      </div>
      <div class="note">
        <p class="lang lang-en"><strong>Roast:</strong> {html.escape(str(persona_roast))}</p>
        <p class="lang lang-zh"><strong>锐评：</strong>本期没有真的挥霍，只是让过去的消费带着账单和日程提醒重新登场。</p>
        <p class="lang lang-en"><strong>Metaphor:</strong> {html.escape(str(metaphor))}</p>
        <p class="lang lang-zh"><strong>年度比喻：</strong>像一家小公司，负债管理比管理层本人更会 follow up。</p>
        <p class="lang lang-en"><strong>Keyword:</strong> {html.escape(str(top_source[0]))}</p>
        <p class="lang lang-zh"><strong>年度关键词：</strong>{html.escape(str(top_source[0]))}</p>
      </div>
    </section>

    <section class="band">
      <h2 class="lang lang-en">Auditor Notes</h2>
      <h2 class="lang lang-zh">审计说明</h2>
      <div class="note">
        <p class="lang lang-en">The annual report uses cleaned rows, not raw exports. Refunds reduce original consumption when a related transaction exists. Ambiguous wallet flows stay in the manual review queue instead of being silently guessed.</p>
        <p class="lang lang-zh">年报只使用清洗后的账本，不直接读取原始账单。存在关联交易时，退款回冲原始消费；含义不明的钱包流水进入人工复核队列，不静默猜测。</p>
        <p class="lang lang-en">Douyin and other platform bills are treated as source-specific inputs because rewards, refunds, repayment labels, and merchant payments can share similar export shapes.</p>
        <p class="lang lang-zh">抖音等平台账单按特殊来源处理，因为奖励、退款、还款标签和商户消费在导出格式上可能长得很像。</p>
      </div>
    </section>

    <section class="band">
      <h2 class="lang lang-en">Board Verdict</h2>
      <h2 class="lang lang-zh">董事会结论</h2>
      <div class="verdict">
        <p class="lang lang-en">The board finds the household entity solvent, traceable, and occasionally overconfident. The finance function has improved. The strategy function is invited to stop calling every purchase an investment.</p>
        <p class="lang lang-zh">董事会认为，本家庭实体具备偿付能力、可追溯性，以及偶发性过度自信。财务职能已有进步，战略职能请停止把每一笔消费都称为投资。</p>
      </div>
      <p class="footnote lang lang-en">Generated locally from synthetic cleaned ledger rows. Public demo only.</p>
      <p class="footnote lang lang-zh">由本地合成 cleaned ledger 生成。仅用于公开演示。</p>
    </section>
  </main>
  <script>
    const chartData = {chart_json};
    const buttons = document.querySelectorAll("[data-set-lang]");
    buttons.forEach((button) => {{
      button.addEventListener("click", () => {{
        const lang = button.dataset.setLang;
        document.body.dataset.lang = lang;
        document.documentElement.lang = lang === "zh" ? "zh-CN" : "en";
        buttons.forEach((item) => item.setAttribute("aria-pressed", String(item === button)));
        renderChart(document.querySelector("[data-chart][aria-pressed='true']").dataset.chart);
      }});
    }});
    const chartButtons = document.querySelectorAll("[data-chart]");
    const chartSummary = document.querySelector("[data-chart-summary]");
    const chartList = document.querySelector("[data-chart-list]");
    function activeLang() {{
      return document.body.dataset.lang === "zh" ? "Zh" : "En";
    }}
    function escapeHTML(value) {{
      return String(value).replace(/[&<>"']/g, (char) => ({{
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&#39;",
      }}[char]));
    }}
    function renderChart(key) {{
      const dataset = chartData[key];
      const suffix = activeLang();
      const max = Math.max(...dataset.items.map((item) => Number(item.value || 0)), 0);
      chartSummary.textContent = dataset["summary" + suffix];
      chartList.innerHTML = dataset.items.map((item) => {{
        const numericValue = Number(item.value || 0);
        const width = max > 0 ? Math.max(3, Math.round((numericValue / max) * 100)) : 0;
        return `<div class="chart-item">
          <div class="chart-label">${{escapeHTML(item["label" + suffix])}}</div>
          <div class="bar" aria-hidden="true"><span style="width: ${{width}}%"></span></div>
          <div class="chart-value">${{escapeHTML(item.display)}}</div>
        </div>`;
      }}).join("");
    }}
    chartButtons.forEach((button) => {{
      button.addEventListener("click", () => {{
        chartButtons.forEach((item) => item.setAttribute("aria-pressed", String(item === button)));
        renderChart(button.dataset.chart);
      }});
    }});
    renderChart("segments");
  </script>
</body>
</html>
"""


def generate_outputs(rows: list[dict[str, str]]) -> None:
    refunds_by_original = build_refunds_by_original(rows)
    summary = build_summary(rows, refunds_by_original)

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
    (FINAL / "summary" / f"summary_{PERIOD}.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

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
    annual_report_path = f"../annual_report/annual_report_{REPORT_YEAR}.html"
    page = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Personal Ledger Pipeline Demo</title>
  <style>
    :root {{
      --paper: #f7f8f3;
      --panel: #fff;
      --ink: #151716;
      --muted: #626b65;
      --line: #d8ddd4;
      --green: #2f6f4e;
      --blue: #315f8c;
      --red: #a33d3d;
      --shadow: 0 12px 28px rgba(40, 44, 40, 0.07);
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      background: var(--paper);
      color: var(--ink);
      font-family: Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      line-height: 1.55;
    }}
    body[data-lang="en"] .lang-zh,
    body[data-lang="zh"] .lang-en {{ display: none; }}
    main {{ width: min(1120px, calc(100% - 32px)); margin: 0 auto; padding: 34px 0 54px; }}
    header {{ border-bottom: 1px solid var(--line); padding-bottom: 24px; margin-bottom: 22px; }}
    .topline {{
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      gap: 16px;
    }}
    .toggle {{ display: flex; gap: 6px; }}
    .toggle button {{
      border: 1px solid var(--line);
      background: var(--panel);
      color: var(--ink);
      padding: 7px 10px;
      border-radius: 6px;
      cursor: pointer;
      font: inherit;
      font-size: 13px;
    }}
    .toggle button[aria-pressed="true"] {{ background: var(--ink); color: #fff; border-color: var(--ink); }}
    h1 {{ margin: 0 0 10px; font-size: clamp(34px, 5vw, 60px); line-height: 1; letter-spacing: 0; }}
    p {{ margin: 0; }}
    .meta {{ color: var(--muted); }}
    .metrics {{ display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px; margin: 22px 0; }}
    .metric {{
      padding: 16px;
      min-height: 118px;
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      box-shadow: var(--shadow);
    }}
    .metric span {{ display: block; color: var(--muted); font-size: 13px; }}
    .metric strong {{ display: block; margin-top: 10px; font-size: 26px; font-variant-numeric: tabular-nums; }}
    .callout {{
      display: grid;
      grid-template-columns: minmax(0, 1fr) auto;
      gap: 16px;
      align-items: center;
      margin: 0 0 22px;
      padding: 18px;
      background: var(--panel);
      border: 1px solid var(--line);
      border-left: 4px solid var(--green);
      border-radius: 8px;
      box-shadow: var(--shadow);
    }}
    .callout h2 {{ margin: 0 0 6px; font-size: 20px; }}
    .callout p {{ color: var(--muted); max-width: 760px; }}
    .button {{
      display: inline-flex;
      align-items: center;
      justify-content: center;
      min-height: 40px;
      padding: 9px 14px;
      border-radius: 8px;
      background: var(--green);
      color: #fff;
      text-decoration: none;
      white-space: nowrap;
    }}
    .panel {{ background: var(--panel); border: 1px solid var(--line); border-radius: 8px; box-shadow: var(--shadow); padding: 18px; }}
    .panel h2 {{ margin: 0 0 12px; font-size: 20px; }}
    table {{ border-collapse: collapse; width: 100%; font-size: 14px; }}
    th, td {{ border-bottom: 1px solid var(--line); padding: 9px 8px; text-align: left; }}
    th {{ background: #fafbf7; color: var(--muted); }}
    tr:last-child td {{ border-bottom: 0; }}
    @media (max-width: 800px) {{
      .metrics {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
      .callout {{ grid-template-columns: 1fr; }}
    }}
    @media (max-width: 560px) {{
      main {{ width: min(100% - 20px, 1120px); }}
      .topline {{ flex-direction: column; }}
      .metrics {{ grid-template-columns: 1fr; }}
      th, td {{ display: block; }}
    }}
  </style>
</head>
<body data-lang="en">
  <main>
    <header>
      <div class="topline">
        <div>
          <h1><span class="lang lang-en">Personal Ledger Pipeline Demo</span><span class="lang lang-zh">个人账本流水线演示</span></h1>
          <p class="meta">
            <span class="lang lang-en">{PERIOD} · synthetic data · generated from cleaned ledger rows</span>
            <span class="lang lang-zh">{PERIOD} · 合成数据 · 由 cleaned ledger 生成</span>
          </p>
        </div>
        <div class="toggle" aria-label="Language">
          <button type="button" data-set-lang="en" aria-pressed="true">EN</button>
          <button type="button" data-set-lang="zh" aria-pressed="false">中文</button>
        </div>
      </div>
    </header>
    <section class="metrics">
      <article class="metric"><span class="lang lang-en">Net consumption</span><span class="lang lang-zh">净消费</span><strong>{money_text(summary['net_consumption'])}</strong></article>
      <article class="metric"><span class="lang lang-en">Ledger cashflow</span><span class="lang lang-zh">账本净现金流</span><strong>{money_text(summary['net_cashflow'])}</strong></article>
      <article class="metric"><span class="lang lang-en">Refund deduction</span><span class="lang lang-zh">退款抵扣</span><strong>{money_text(summary['refund_deduction'])}</strong></article>
      <article class="metric"><span class="lang lang-en">Review rows</span><span class="lang lang-zh">复核行数</span><strong>{len(review_rows)}</strong></article>
    </section>
    <section class="callout">
      <div>
        <h2><span class="lang lang-en">Personal annual report</span><span class="lang lang-zh">个人年度报告</span></h2>
        <p class="lang lang-en">The annual-report layer turns this cleaned ledger into bilingual narrative analysis, risk factors, segment performance, and a local chart explorer.</p>
        <p class="lang lang-zh">年报层把清洗后的账本转成双语叙事分析、风险因素、分部表现和本地图表查看器。</p>
      </div>
      <a class="button" href="{html.escape(annual_report_path)}"><span class="lang lang-en">Open annual report</span><span class="lang lang-zh">打开年度报告</span></a>
    </section>
    <section class="panel">
      <h2><span class="lang lang-en">Cleaned ledger sample</span><span class="lang lang-zh">清洗后账本样例</span></h2>
      <table>
        <thead><tr>
          <th><span class="lang lang-en">Time</span><span class="lang lang-zh">时间</span></th>
          <th><span class="lang lang-en">Source</span><span class="lang lang-zh">来源</span></th>
          <th><span class="lang lang-en">Direction</span><span class="lang lang-zh">方向</span></th>
          <th><span class="lang lang-en">Amount</span><span class="lang lang-zh">金额</span></th>
          <th><span class="lang lang-en">Type</span><span class="lang lang-zh">类型</span></th>
          <th><span class="lang lang-en">Included</span><span class="lang lang-zh">纳入口径</span></th>
          <th><span class="lang lang-en">Rule</span><span class="lang lang-zh">规则</span></th>
        </tr></thead>
        <tbody>{html_rows}</tbody>
      </table>
    </section>
  </main>
  <script>
    const buttons = document.querySelectorAll("[data-set-lang]");
    buttons.forEach((button) => {{
      button.addEventListener("click", () => {{
        const lang = button.dataset.setLang;
        document.body.dataset.lang = lang;
        document.documentElement.lang = lang === "zh" ? "zh-CN" : "en";
        buttons.forEach((item) => item.setAttribute("aria-pressed", String(item === button)));
      }});
    }});
  </script>
</body>
</html>
"""
    (FINAL / "visual").mkdir(parents=True, exist_ok=True)
    (FINAL / "visual" / f"dashboard_{PERIOD}.html").write_text(clean_output_text(page), encoding="utf-8")

    (FINAL / "annual_report").mkdir(parents=True, exist_ok=True)
    annual_report = build_annual_report(rows, summary, refunds_by_original, review_rows)
    (FINAL / "annual_report" / f"annual_report_{REPORT_YEAR}.md").write_text(clean_output_text(annual_report), encoding="utf-8")
    annual_report_html = build_annual_report_html(
        rows,
        summary,
        refunds_by_original,
        review_rows,
        dashboard_href=f"../visual/dashboard_{PERIOD}.html",
    )
    (FINAL / "annual_report" / f"annual_report_{REPORT_YEAR}.html").write_text(clean_output_text(annual_report_html), encoding="utf-8")

    EXAMPLES.mkdir(parents=True, exist_ok=True)
    (EXAMPLES / f"annual_report_{REPORT_YEAR}.md").write_text(clean_output_text(annual_report), encoding="utf-8")
    examples_report_html = build_annual_report_html(rows, summary, refunds_by_original, review_rows)
    (EXAMPLES / f"annual_report_{REPORT_YEAR}.html").write_text(clean_output_text(examples_report_html), encoding="utf-8")


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

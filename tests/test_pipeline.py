from __future__ import annotations

import unittest
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory

from scripts.core.ledger import apply_review_decisions, build_refunds_by_original, build_summary, clean
from scripts.parsers.registry import parse_raw_dir, source_counts


ROOT = Path(__file__).resolve().parent.parent


class PipelineTest(unittest.TestCase):
    def test_source_specific_parsers_cover_synthetic_fixture(self) -> None:
        result = parse_raw_dir(ROOT / "raw")

        self.assertEqual(len(result.rows), 19)
        self.assertEqual(result.warnings, [])
        self.assertEqual(
            source_counts(result.rows),
            {
                "alipay": 6,
                "boc": 3,
                "douyin": 4,
                "meituan": 3,
                "wechat": 3,
            },
        )

    def test_cleaning_rules_exclude_repayments_transfers_and_duplicates(self) -> None:
        rows = clean(parse_raw_dir(ROOT / "raw").rows)
        refunds = build_refunds_by_original(rows)
        summary = build_summary(rows, refunds)

        self.assertEqual(summary["gross_income"], Decimal("5008.88"))
        self.assertEqual(summary["gross_expense"], Decimal("450.80"))
        self.assertEqual(summary["refund_deduction"], Decimal("175.50"))
        self.assertEqual(summary["net_consumption"], Decimal("275.30"))

        by_id = {row["transaction_id"]: row for row in rows}
        self.assertEqual(by_id["ali_4001"]["clean_status"], "excluded_credit_repayment")
        self.assertEqual(by_id["wechat_2001"]["clean_status"], "excluded_credit_repayment")
        self.assertEqual(by_id["mt_3001"]["transfer_scope"], "debt_repayment")
        self.assertEqual(by_id["dy_3001"]["include_in_ledger"], "false")
        self.assertEqual(by_id["ali_3001"]["clean_status"], "excluded_internal_transfer")
        self.assertEqual(by_id["boc_1001"]["clean_status"], "excluded_duplicate_payment")
        self.assertEqual(by_id["ali_9001"]["clean_status"], "needs_review")

    def test_manual_review_decision_can_include_ambiguous_row(self) -> None:
        rows = clean(parse_raw_dir(ROOT / "raw").rows)
        reviewed = apply_review_decisions(
            rows,
            [
                {
                    "transaction_id": "ali_9001",
                    "action": "include",
                    "direction": "expense",
                    "normalized_type": "merchant_payment",
                    "transfer_scope": "external",
                }
            ],
        )
        refunds = build_refunds_by_original(reviewed)
        summary = build_summary(reviewed, refunds)
        row = next(item for item in reviewed if item["transaction_id"] == "ali_9001")

        self.assertEqual(row["include_in_ledger"], "true")
        self.assertEqual(row["needs_review"], "false")
        self.assertEqual(row["clean_status"], "review_included")
        self.assertEqual(summary["net_consumption"], Decimal("364.18"))

    def test_repayment_total_requires_expense_and_no_adjustment_terms(self) -> None:
        with TemporaryDirectory() as temp_dir:
            raw = Path(temp_dir) / "raw"
            alipay = raw / "alipay"
            alipay.mkdir(parents=True)
            (alipay / "alipay.csv").write_text(
                "\n".join(
                    [
                        "transaction_time,raw_direction,amount,counterparty,item_title,payment_method,transaction_id,status",
                        "2026-05-01T10:00:00,支出,1000.00,花呗,花呗主动还款-4月账单,余额,repay_1,交易成功",
                        "2026-05-02T10:00:00,收入,80.00,花呗,花呗还款退款,余额,repay_refund_1,退款成功",
                        "2026-05-03T10:00:00,支出,20.00,花呗,花呗还款立减,余额,repay_discount_1,交易成功",
                        "2026-05-04T10:00:00,不计收支,500.00,花呗,花呗主动还款-5月账单,红包&花呗还款立减,repay_neutral_1,还款成功",
                    ]
                ),
                encoding="utf-8",
            )

            rows = clean(parse_raw_dir(raw).rows)
            by_id = {row["transaction_id"]: row for row in rows}
            repayment_total = sum(
                Decimal(row["amount"])
                for row in rows
                if row["transfer_scope"] == "debt_repayment"
            )

            self.assertEqual(repayment_total, Decimal("1500.00"))
            self.assertEqual(by_id["repay_1"]["clean_status"], "excluded_credit_repayment")
            self.assertEqual(by_id["repay_neutral_1"]["clean_status"], "excluded_credit_repayment")
            self.assertEqual(by_id["repay_refund_1"]["normalized_type"], "refund_in")
            self.assertNotEqual(by_id["repay_refund_1"]["transfer_scope"], "debt_repayment")
            self.assertEqual(by_id["repay_discount_1"]["clean_status"], "needs_review")
            self.assertEqual(by_id["repay_discount_1"]["transfer_scope"], "repayment_review")


if __name__ == "__main__":
    unittest.main()

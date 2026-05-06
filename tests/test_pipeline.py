from __future__ import annotations

import unittest
from decimal import Decimal
from pathlib import Path

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


if __name__ == "__main__":
    unittest.main()

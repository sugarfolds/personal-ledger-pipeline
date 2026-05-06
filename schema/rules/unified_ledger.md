# Unified Ledger Schema

The cleaned ledger is the stable downstream input. Every output should be generated from cleaned rows rather than by editing final CSV files directly.

## Required Fields

| Field | Type | Notes |
| --- | --- | --- |
| `source` | string | Source short code such as `alipay`, `wechat`, `boc`, `douyin`, `meituan` |
| `source_file` | string | Raw input filename |
| `raw_row_number` | integer | 1-based row number in the raw file |
| `transaction_time` | datetime string | ISO-like timestamp |
| `direction` | enum | `expense`, `income`, `neutral` |
| `amount` | decimal string | Positive absolute amount |
| `counterparty` | string | Synthetic or real counterparty, depending on environment |
| `item_title` | string | Transaction title or memo |
| `payment_method` | string | Wallet, card, monthly pay, etc. |
| `transaction_id` | string | Source transaction ID |
| `related_transaction_id` | string | Optional original transaction or refund target |
| `normalized_type` | string | Business type |
| `normalized_status` | string | `success`, `refund`, `closed`, `pending`, etc. |
| `account_platform` | string | Platform or institution |
| `account_name` | string | Account hint |
| `transfer_scope` | string | `external`, `internal`, `debt_repayment`, `unknown` |
| `include_in_ledger` | boolean string | Main ledger inclusion |
| `needs_review` | boolean string | Human review flag |
| `clean_status` | string | Cleaning status |
| `clean_rule` | string | Rule name explaining the decision |

## Review Rule

Rows with unclear direction, unclear account flow, unstable matching, or first-seen transaction types should be sent to `final/review/manual_review_queue_<period>.csv`.

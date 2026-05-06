# Supported Sources

The parser registry is source-specific. The goal is traceable intake, not broad spreadsheet guessing.

| Source | CLI v1 | Browser v1 | Notes |
| --- | --- | --- | --- |
| Alipay CSV/XLSX | Supported | CSV fallback | Uses direction, status, payment method, refund labels, repayment labels |
| WeChat CSV/XLSX | Supported | CSV fallback | Uses income/expense field and repayment/refund labels |
| Meituan CSV/XLSX | Supported | CSV fallback | Treats repayment rows separately from merchant payments |
| Douyin CSV/XLSX | Supported | CSV fallback | Handles merchant payments, refunds, rewards/campaign income, repayment labels |
| BOC CSV/XLSX | Supported | Normalized CSV recommended | Bank-side duplicate detection can shadow app-side details |
| CMB CSV/XLSX | Supported | Normalized CSV recommended | Same bank branch rules as other bank CSV exports |
| ICBC CSV/XLSX | Supported | Normalized CSV recommended | Same bank branch rules as other bank CSV exports |
| ABC CSV/XLSX | Supported | Normalized CSV recommended | Same bank branch rules as other bank CSV exports |
| Text PDF | Planned per source | Later | PDF parsing differs sharply across banks and platforms |
| Scanned PDF | Out of scope for v1 | Out of scope for v1 | Requires OCR and manual validation |

## Source-Specific Edge Cases

- Credit repayment and consumption matching: original monthly-credit purchases remain as consumption; later repayment rows are excluded from new consumption.
- Douyin bills: platform rewards, campaign income, refunds, merchant payments, and repayment labels can appear in similar export shapes, so Douyin is handled as its own branch.
- Bank app shadows: a bank card charge can duplicate an app-side merchant payment. The cleaner matches amount and nearby timestamp, then keeps the richer app-side row.
- Manual review: unclear wallet movement is routed to review rather than guessed into income or expense.

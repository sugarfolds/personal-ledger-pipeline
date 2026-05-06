# Web Mobile Verification

Before publishing the browser-only annual report page, run:

```bash
make verify-web-mobile
```

The verifier opens `web/annual-report/index.html`, uploads the synthetic Alipay sample, and checks four mobile viewports:

- iPhone SE
- iPhone 14
- iPhone 15 Pro Max
- Pixel 7

It verifies that the report renders, the report appears before controls after upload, there is no horizontal overflow, parsing and rendering make no HTTP requests, and long PNG export works. Screenshots, exported PNGs, and the JSON report are written to the system temp directory, not to the repo.

To test a private local export without committing it:

```bash
python3 scripts/verify_annual_report_mobile.py --file /path/to/private/alipay.csv
```

The page should remain browser-only: no login, no API, and no uploaded file contents leaving the browser tab.

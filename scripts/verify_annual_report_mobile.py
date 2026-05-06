#!/usr/bin/env python3
"""Mobile preflight checks for the browser-only annual report page."""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_FILE = ROOT / "raw" / "alipay" / "alipay_2026-04-01_to_2026-04-30.csv"
DEFAULT_PAGE = ROOT / "web" / "annual-report" / "index.html"
DEFAULT_OUT = Path(tempfile.gettempdir()) / "personal-ledger-pipeline-annual-report-mobile"

DEVICES = {
    "iphone-se": {"width": 375, "height": 667, "device_scale_factor": 2, "is_mobile": True},
    "iphone-14": {"width": 390, "height": 844, "device_scale_factor": 3, "is_mobile": True},
    "iphone-15-pro-max": {"width": 430, "height": 932, "device_scale_factor": 3, "is_mobile": True},
    "pixel-7": {"width": 412, "height": 915, "device_scale_factor": 2.625, "is_mobile": True},
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--file", type=Path, default=DEFAULT_FILE, help="CSV/JSON file to upload in the browser.")
    parser.add_argument("--page", type=Path, default=DEFAULT_PAGE, help="Annual report HTML entrypoint.")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT, help="Directory for screenshots and exported PNGs.")
    parser.add_argument("--style", default="board_roast", choices=["board_roast", "serious", "social_share"])
    parser.add_argument("--keep-open", action="store_true", help="Run browser headed for manual inspection.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.file.exists():
      print(f"Upload file not found: {args.file}", file=sys.stderr)
      return 2
    if not args.page.exists():
      print(f"Page not found: {args.page}", file=sys.stderr)
      return 2

    try:
      from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
      from playwright.sync_api import sync_playwright
    except Exception as exc:  # pragma: no cover - local developer preflight
      print("Playwright is required for mobile verification.", file=sys.stderr)
      print("Install with: python3 -m pip install playwright && python3 -m playwright install chromium", file=sys.stderr)
      print(f"Import error: {exc}", file=sys.stderr)
      return 2

    args.out.mkdir(parents=True, exist_ok=True)
    page_url = args.page.resolve().as_uri()
    upload_path = str(args.file.resolve())
    results = []
    failures = []

    with sync_playwright() as playwright:
      browser = playwright.chromium.launch(headless=not args.keep_open)
      for name, viewport in DEVICES.items():
        context = browser.new_context(
            viewport={"width": viewport["width"], "height": viewport["height"]},
            device_scale_factor=viewport["device_scale_factor"],
            is_mobile=viewport["is_mobile"],
            has_touch=True,
        )
        page = context.new_page()
        console_errors: list[str] = []
        network_requests: list[str] = []
        page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)
        page.on("request", lambda req: network_requests.append(req.url) if req.url.startswith(("http://", "https://")) else None)
        device_result = {"device": name, "checks": {}, "screenshots": {}, "downloads": {}}
        try:
          page.goto(page_url, wait_until="load")
          page.set_input_files("#fileInput", upload_path)
          page.wait_for_selector(".annual-stack", timeout=5000)
          page.select_option("#styleSelect", args.style)
          page.wait_for_timeout(100)

          device_result["checks"]["title"] = page.locator(".cover-title").inner_text()
          device_result["checks"]["net_consumption"] = page.locator(".big-number").inner_text()
          device_result["checks"]["segment"] = page.locator(".segment-hero").inner_text()
          device_result["checks"]["discussion"] = page.locator(".discussion-title").inner_text()

          layout = page.evaluate(
              """() => {
                const report = document.querySelector('.report-wrap').getBoundingClientRect();
                const controls = document.querySelector('.controls').getBoundingClientRect();
                return {
                  docWidth: document.documentElement.scrollWidth,
                  viewportWidth: document.documentElement.clientWidth,
                  bodyWidth: document.body.scrollWidth,
                  reportTop: report.top,
                  controlsTop: controls.top,
                };
              }"""
          )
          device_result["checks"]["layout"] = layout
          no_horizontal_overflow = max(layout["docWidth"], layout["bodyWidth"]) <= layout["viewportWidth"] + 2
          report_first = layout["reportTop"] <= layout["controlsTop"]

          viewport_path = args.out / f"{name}-viewport.png"
          full_path = args.out / f"{name}-full.png"
          page.screenshot(path=str(viewport_path), full_page=False)
          page.screenshot(path=str(full_path), full_page=True)
          device_result["screenshots"]["viewport"] = str(viewport_path)
          device_result["screenshots"]["full"] = str(full_path)

          with page.expect_download(timeout=10000) as download_info:
            page.click("#exportPng")
          download = download_info.value
          png_path = args.out / f"{name}-exported-long.png"
          download.save_as(str(png_path))
          device_result["downloads"]["png"] = {
              "path": str(png_path),
              "filename": download.suggested_filename,
              "bytes": png_path.stat().st_size,
          }

          checks = {
              "annual_report_rendered": page.locator(".annual-stack").count() == 1,
              "segment_section_rendered": page.locator(".segment-hero").count() == 1,
              "discussion_section_rendered": page.locator(".discussion-title").count() == 1,
              "no_console_errors": len(console_errors) == 0,
              "no_network_requests": len(network_requests) == 0,
              "no_horizontal_overflow": no_horizontal_overflow,
              "report_before_controls_after_upload": report_first,
              "png_exported": png_path.stat().st_size > 100_000,
          }
          device_result["checks"].update(checks)
          device_result["console_errors"] = console_errors
          device_result["network_requests"] = network_requests
          for check_name, passed in checks.items():
            if not passed:
              failures.append(f"{name}: {check_name}")
        except PlaywrightTimeoutError as exc:
          failures.append(f"{name}: timeout: {exc}")
          device_result["error"] = f"timeout: {exc}"
        except Exception as exc:  # pragma: no cover - local developer preflight
          failures.append(f"{name}: {exc}")
          device_result["error"] = str(exc)
        finally:
          results.append(device_result)
          context.close()
      browser.close()

    report = {
        "page": page_url,
        "upload_file": str(args.file.resolve()),
        "output_dir": str(args.out.resolve()),
        "style": args.style,
        "results": results,
        "failures": failures,
    }
    report_path = args.out / "mobile-verification-report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print(f"Verification artifacts: {args.out}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())

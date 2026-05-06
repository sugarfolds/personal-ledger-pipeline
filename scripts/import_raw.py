#!/usr/bin/env python3

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts.core.ledger import write_csv
from scripts.parsers.registry import IntakeError, parse_raw_dir, source_counts


def main() -> int:
    parser = argparse.ArgumentParser(description="Import local raw exports into the unified normalized ledger schema.")
    parser.add_argument("raw_dir", type=Path, help="Directory containing raw/<source>/ exports.")
    parser.add_argument("--out", type=Path, default=Path("parsed"), help="Output directory for parsed normalized CSV.")
    args = parser.parse_args()

    try:
        result = parse_raw_dir(args.raw_dir)
    except IntakeError as exc:
        parser.error(str(exc))

    output = args.out / "normalized_input.csv"
    write_csv(output, result.rows)

    print(f"Wrote {len(result.rows)} normalized rows to {output}")
    for source, count in sorted(source_counts(result.rows).items()):
        print(f"- {source}: {count}")
    if result.warnings:
        print("\nWarnings:")
        for warning in result.warnings:
            print(f"- {warning}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

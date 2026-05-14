"""Run multiple briefing keywords from a CSV or JSON file."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from seo_pipeline.batch import load_batch_items, run_batch


def main() -> int:
    parser = argparse.ArgumentParser(description="Run SEO briefing pipeline for a batch of keywords.")
    parser.add_argument("input", type=Path, help="CSV or JSON input file. Requires a keyword field.")
    parser.add_argument("--batch-id", default=None, help="Optional stable batch id.")
    parser.add_argument("--output-dir", type=Path, default=None, help="Defaults to runs/batch_<batch_id>.")
    parser.add_argument("--stop-on-error", action="store_true", help="Stop after first failed keyword.")
    parser.add_argument("--resume", action="store_true", help="Skip items already marked done in batch_manifest.json.")
    args = parser.parse_args()

    items = load_batch_items(args.input)
    summary = run_batch(
        items,
        batch_id=args.batch_id,
        output_dir=args.output_dir,
        stop_on_error=args.stop_on_error,
        resume=args.resume,
    )
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 1 if summary["failed"] and args.stop_on_error else 0


if __name__ == "__main__":
    raise SystemExit(main())

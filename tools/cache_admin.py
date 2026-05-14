"""Inspect and clear provider caches safely."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from seo_pipeline.cache_admin import clear_cache, inspect_cache
from seo_pipeline.config import get_config


def main() -> int:
    parser = argparse.ArgumentParser(description="Inspect or clear provider cache files.")
    parser.add_argument("command", choices=["inspect", "clear"])
    parser.add_argument("--cache-dir", type=Path, default=None, help="Defaults to configured cfg.cache_dir.")
    parser.add_argument("--limit", type=int, default=50, help="Maximum files to include in inspect output.")
    parser.add_argument("--yes", action="store_true", help="Required for clear.")
    args = parser.parse_args()

    cache_dir = args.cache_dir or get_config().cache_dir
    if args.command == "inspect":
        summary = inspect_cache(cache_dir, limit=args.limit)
        print(json.dumps(_summary_to_dict(summary), indent=2, ensure_ascii=False))
        return 0

    if not args.yes:
        parser.error("clear requires --yes")
    summary = clear_cache(cache_dir)
    print(json.dumps({"cleared": _summary_to_dict(summary)}, indent=2, ensure_ascii=False))
    return 0


def _summary_to_dict(summary) -> dict:
    return {
        "root": summary.root,
        "file_count": summary.file_count,
        "total_size_bytes": summary.total_size_bytes,
        "oldest_modified_at": summary.oldest_modified_at,
        "newest_modified_at": summary.newest_modified_at,
        "files": [
            {
                "path": item.path,
                "size_bytes": item.size_bytes,
                "modified_at": item.modified_at,
            }
            for item in summary.files
        ],
    }


if __name__ == "__main__":
    raise SystemExit(main())

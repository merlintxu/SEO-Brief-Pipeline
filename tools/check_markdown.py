"""Basic markdown checks for pre-commit."""
from __future__ import annotations

import sys
from pathlib import Path


def main() -> int:
    failures: list[str] = []
    for md in Path(".").rglob("*.md"):
        if ".git" in md.parts:
            continue
        text = md.read_text(encoding="utf-8", errors="strict")
        lines = text.splitlines()
        if not lines:
            failures.append(f"{md}: file is empty")
            continue
        if not lines[0].startswith("# "):
            failures.append(f"{md}: first line must be a level-1 heading")

    if failures:
        print("Markdown guard failures:")
        for failure in failures:
            print(f"- {failure}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

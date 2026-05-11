"""Guard checks mirroring CI constraints for local pre-commit."""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path


SECRET_PATTERN = re.compile(r"sk-proj-[A-Za-z0-9_-]{20,}|[A-Fa-f0-9]{32,}")
EXCLUDED = {".env.example", "HISTORY_REWRITE.md", "SECURITY.md"}


def _run(cmd: list[str]) -> str:
    out = subprocess.check_output(cmd, text=True, encoding="utf-8", errors="ignore")
    return out.strip()


def main() -> int:
    forbidden = _run(["git", "ls-files", ".env", "*__pycache__*", "*.pyc"])
    if forbidden:
        print("Forbidden tracked files detected:")
        print(forbidden)
        return 1

    tracked = _run(["git", "ls-files"])
    failures: list[str] = []
    for rel in tracked.splitlines():
        path = Path(rel)
        if path.name in EXCLUDED or path.suffix == ".md":
            continue
        if not path.exists() or not path.is_file():
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        if SECRET_PATTERN.search(text):
            failures.append(rel)

    if failures:
        print("Potential secret-like values found in tracked source files:")
        for item in failures:
            print(f"- {item}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

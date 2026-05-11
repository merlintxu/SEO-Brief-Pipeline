"""Export FastAPI OpenAPI schema to a versioned JSON contract file."""
from __future__ import annotations

import json
import os
from pathlib import Path


def main() -> None:
    # api.main validates API_KEY at import time.
    os.environ.setdefault("API_KEY", "openapi-export-placeholder-key-2026")

    from api.main import app  # noqa: WPS433

    schema = app.openapi()
    out_path = Path("docs") / "contracts" / "openapi.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(schema, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"OpenAPI contract exported: {out_path}")


if __name__ == "__main__":
    main()

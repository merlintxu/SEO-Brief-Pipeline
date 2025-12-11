"""
Pequeñas utilidades de I/O usadas por el pipeline.
Contiene `ensure_dir`, `save_json`, `load_json` y `save_text`.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from seo_pipeline.utils.logging import logger


def ensure_dir(path: Path) -> Path:
    p = Path(path)
    if p.is_file():
        p = p.parent
    p.mkdir(parents=True, exist_ok=True)
    return p


def save_json(path: Path, data: Any) -> Path:
    path = Path(path)
    ensure_dir(path.parent)
    try:
        with path.open("w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False, indent=2)
        logger.debug("JSON guardado: %s", path)
        return path
    except (OSError, TypeError, ValueError) as e:
        logger.error("Error guardando JSON %s: %s", path, e)
        raise


def load_json(path: Path) -> Any:
    path = Path(path)
    if not path.exists():
        return None
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def save_text(path: Path, text: str) -> Path:
    path = Path(path)
    ensure_dir(path.parent)
    with path.open("w", encoding="utf-8") as fh:
        fh.write(text)
    logger.debug("Texto guardado: %s", path)
    return path

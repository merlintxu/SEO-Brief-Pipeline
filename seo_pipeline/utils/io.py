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
    """
    Asegura que el directorio del path exista.
    Si el path es un archivo, asegura su directorio padre.

    Args:
        path (Path): Ruta a verificar.

    Returns:
        Path: La ruta original.
    """
    p = Path(path)
    if p.is_file():
        p = p.parent
    p.mkdir(parents=True, exist_ok=True)
    return p


def save_json(path: Path, data: Any) -> Path:
    """
    Guarda datos en formato JSON (UTF-8).

    Args:
        path (Path): Ruta de destino.
        data (Any): Datos serializables.

    Returns:
        Path: Ruta del archivo guardado.
    """
    path = Path(path)
    ensure_dir(path.parent)
    try:
        with path.open("w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False, indent=2)
        logger.debug(f"JSON guardado: {path}")
        return path
    except (OSError, TypeError, ValueError) as e:
        logger.error(f"Error guardando JSON {path}: {e}")
        raise


def load_json(path: Path, default: Any = None) -> Any:
    """
    Carga datos desde un archivo JSON.

    Args:
        path (Path): Ruta del archivo.

    Returns:
        Any: Datos cargados o default si no existe.
    """
    path = Path(path)
    if not path.exists():
        return default
    try:
        with path.open("r", encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, json.JSONDecodeError) as e:
        logger.warning(f"No se pudo cargar JSON {path}: {e}")
        return default


def save_text(path: Path, text: str) -> Path:
    """
    Guarda texto en un archivo (UTF-8).

    Args:
        path (Path): Ruta de destino.
        text (str): Contenido de texto.

    Returns:
        Path: Ruta del archivo guardado.
    """
    path = Path(path)
    ensure_dir(path.parent)
    with path.open("w", encoding="utf-8") as fh:
        fh.write(text)
    logger.debug(f"Texto guardado: {path}")
    return path

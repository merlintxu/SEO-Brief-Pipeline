# seo_pipeline/utils/text.py
"""
Utilidades de procesamiento y normalización de texto.
Todas las funciones son puras, deterministas y optimizadas para uso intensivo en SEO.
"""
from __future__ import annotations

import re
import unicodedata
from typing import Iterable, List, Set

# Compilación única de expresiones regulares (mejor rendimiento)
_SLUG_RE = re.compile(r"[^a-z0-9\-]+")
_WS_RE = re.compile(r"\s+")
_TRUNCATE_RE = re.compile(r"\s+")


def slugify(text: str | None) -> str:
    """
    Convierte texto a slug SEO-friendly (kebab-case).

    Args:
        text (str | None): Texto de entrada.

    Returns:
        str: Slug normalizado (ej: "hola-mundo").
    """
    if not text:
        return ""
    # Normalización Unicode + eliminación de acentos
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    text = text.lower().strip()
    text = _WS_RE.sub("-", text)
    text = _SLUG_RE.sub("-", text).strip("-")
    return text


def to_kebab(text: str | None) -> str:
    """Alias de slugify para legibilidad semántica."""
    return slugify(text)


def normalize_ws(text: str | None) -> str:
    """
    Normaliza espacios en blanco a un único espacio y recorta.

    Args:
        text (str | None): Texto de entrada.

    Returns:
        str: Texto normalizado.
    """
    if not text:
        return ""
    return _WS_RE.sub(" ", text.strip())


def truncate_smart(text: str | None, max_len: int, ellipsis: str = "…") -> str:
    """
    Trunca texto de forma inteligente preservando palabras completas.
    Evita cortar a mitad de palabra.

    Args:
        text (str | None): Texto a truncar.
        max_len (int): Longitud máxima.
        ellipsis (str): Sufijo para indicar truncamiento.

    Returns:
        str: Texto truncado.
    """
    if not text or len(text) <= max_len:
        return text or ""
    cut = text[: max_len + 1]
    if len(cut) <= max_len:
        return cut.rstrip() + ellipsis
    # Retrocede hasta el último espacio
    truncated = cut[:cut.rfind(" ")]
    return (truncated.rstrip() if truncated else text[:max_len]) + ellipsis


def is_blank(text: str | None) -> bool:
    """
    Verifica si el texto está vacío o solo contiene espacios.

    Args:
        text (str | None): Texto a verificar.

    Returns:
        bool: True si está vacío o es None.
    """
    return not normalize_ws(text)


def uniq_preserve(seq: Iterable[str]) -> List[str]:
    """
    Elimina duplicados preservando el orden original de aparición.
    Versión optimizada con O(n) y bajo consumo de memoria.

    Args:
        seq (Iterable[str]): Secuencia de entrada.

    Returns:
        List[str]: Lista sin duplicados.
    """
    seen: Set[str] = set()
    result: List[str] = []
    for item in seq:
        normalized = normalize_ws(item)
        if normalized and normalized not in seen:
            seen.add(normalized)
            result.append(item.strip())
    return result


def extract_ngrams(text: str, n: int = 3) -> List[str]:
    """
    Extrae n-grams de palabras (útil para anchors y detección de frases clave).

    Args:
        text (str): Texto fuente.
        n (int): Tamaño del n-gram.

    Returns:
        List[str]: Lista de n-grams.
    """
    words = normalize_ws(text).split()
    if len(words) < n:
        return []
    return [" ".join(words[i:i + n]) for i in range(len(words) - n + 1)]
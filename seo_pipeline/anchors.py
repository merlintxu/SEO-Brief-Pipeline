# seo_pipeline/anchors.py
"""
Generación inteligente de anchor texts – Versión 2025 (sin LLM).
Combina extracción de n-grams, scoring por relevancia, variedad y naturalidad.
Produce anchors mucho más efectivos y realistas que la versión heurística original.
"""
from __future__ import annotations

from typing import List
import re

from .utils.text import normalize_ws, uniq_preserve
from .models import AnchorSet


def _extract_candidate_phrases(
    texts: List[str],
    min_len: int = 15,   # caracteres mínimos para considerar una frase
    max_len: int = 65    # evita anchors demasiado largos
) -> List[str]:
    """
    Extrae frases candidatas (2-6 palabras) de múltiples textos.
    Prioriza combinaciones naturales y evita fragmentos sin sentido.

    Args:
        texts (List[str]): Textos fuente.
        min_len (int): Longitud mínima.
        max_len (int): Longitud máxima.

    Returns:
        List[str]: Lista de frases candidatas.
    """
    candidates: List[str] = []
    seen: Set[str] = set()

    for text in texts:
        if not text:
            continue
        # Divide en oraciones simples (por puntos, exclamación, interrogación)
        sentences = re.split(r"[.!?]\s+", text)
        for sentence in sentences:
            words = normalize_ws(sentence).split()
            if len(words) < 2:
                continue
            # Genera n-grams de 2 a 6 palabras
            for n in range(2, min(7, len(words) + 1)):
                for i in range(len(words) - n + 1):
                    phrase = " ".join(words[i:i + n])
                    if min_len <= len(phrase) <= max_len:
                        norm = normalize_ws(phrase).lower()
                        if norm not in seen:
                            seen.add(norm)
                            candidates.append(phrase)
    return candidates


def _score_phrase(
    phrase: str,
    main_kw: str,
    secondary_kws: List[str],
    h2s: List[str],
    competitor_titles: List[str]
) -> float:
    """
    Sistema de puntuación sofisticado (cuanto mayor, mejor como anchor).

    Args:
        phrase (str): Frase a evaluar.
        main_kw (str): Keyword principal.
        secondary_kws (List[str]): Keywords secundarias.
        h2s (List[str]): H2s de la competencia.
        competitor_titles (List[str]): Títulos de la competencia.

    Returns:
        float: Puntuación calculada.
    """
    norm = normalize_ws(phrase).lower()
    score = 0.0

    # 1. Longitud óptima (prefiere 35-55 caracteres)
    length = len(phrase)
    if 30 <= length <= 60:
        score += 15
    elif length < 30:
        score += 8
    elif length > 60:
        score -= 5

    # 2. Contiene keyword principal (exacta o parcial)
    main_norm = main_kw.lower()
    if main_norm in norm:
        score += 30
    elif any(word in norm for word in main_norm.split()):
        score += 15

    # 3. Contiene keywords secundarias
    for kw in secondary_kws:
        if kw.lower() in norm:
            score += 12
            break

    # 4. Aparece en H2s o títulos competidores (naturalidad)
    reference_texts = " | ".join(h2s + competitor_titles).lower()
    if norm in reference_texts:
        score += 18

    # 5. Comienza con mayúscula (marca, llamada a acción, etc.)
    if phrase[0].isupper() or phrase.split()[0][0].isupper():
        score += 8

    # 6. Es pregunta (conversacional)
    if phrase.lower().startswith(("cómo", "por qué", "cuál", "dónde", "cuándo", "qué")):
        score += 10

    # 7. Variedad léxica (penaliza repetición excesiva de palabras)
    words = norm.split()
    if len(words) > 2 and len(set(words)) / len(words) >= 0.7:
        score += 5

    return score


def generate_anchors(
    title: str,
    h1: str,
    h2_list: List[str],
    main_keyword: str,
    secondary_keywords: List[str],
    competitor_titles: List[str] | None = None,
) -> "AnchorSet":  # Changed from Dict to AnchorSet
    """
    Genera tres categorías de anchors optimizados:
    - primary: 4–5 anchors de alta conversión y exact match
    - secondary: 6–8 anchors naturales y variados
    - internal: 8–12 anchors long-tail para enlazado interno

    Args:
        title (str): Meta title propuesto.
        h1 (str): H1 propuesto.
        h2_list (List[str]): Lista de H2s propuestos.
        main_keyword (str): Keyword principal.
        secondary_keywords (List[str]): Keywords secundarias.
        competitor_titles (List[str] | None): Títulos de competidores.

    Returns:
        AnchorSet: Objeto con listas de anchors por categoría.
    """
    competitor_titles = competitor_titles or []
    all_sources = [title, h1] + h2_list + competitor_titles

    # 1. Pool de candidatos
    candidates = _extract_candidate_phrases(all_sources)
    candidates.extend([title, h1] + h2_list[:4])  # fuerza inclusión de elementos clave

    # 2. Scoring
    scored = []
    for phrase in uniq_preserve(candidates):
        if len(phrase) < 10:
            continue
        score = _score_phrase(
            phrase=phrase,
            main_kw=main_keyword,
            secondary_kws=secondary_keywords,
            h2s=h2_list,
            competitor_titles=competitor_titles
        )
        scored.append((score, phrase))

    # 3. Ordenar y seleccionar con diversidad
    scored.sort(reverse=True, key=lambda x: x[0])

    primary: List[str] = []
    secondary: List[str] = []
    internal: List[str] = []

    used_norm: Set[str] = set()

    for score, phrase in scored:
        norm = normalize_ws(phrase).lower()
        if norm in used_norm:
            continue
        used_norm.add(norm)

        if len(primary) < 5 and score >= 40:
            primary.append(phrase)
        elif len(secondary) < 8 and score >= 25:
            secondary.append(phrase)
        elif len(internal) < 12:
            internal.append(phrase)
            if len(primary) >= 5 and len(secondary) >= 8 and len(internal) >= 12:
                break

    # Import here to avoid circular dependency
    from seo_pipeline.models import AnchorSet
    
    return AnchorSet(
        primary=primary[:5],
        secondary=secondary[:8],
        internal=internal[:12]
    )
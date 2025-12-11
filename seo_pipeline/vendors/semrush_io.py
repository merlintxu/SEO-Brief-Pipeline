# seo_pipeline/vendors/semrush_io.py
"""
Cliente SEMrush optimizado 2025:
- Caché en disco con TTL configurable
- Control estricto de units (lanza excepción si no hay suficientes)
- Manejo automático de ERROR 122
- Logging claro y enmascarado de token
"""
from __future__ import annotations

import logging
import csv
import io
import time
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional

import requests

from seo_pipeline.models import SemrushKeyword, SemrushResults
from seo_pipeline.utils.io import ensure_dir, save_json
from seo_pipeline.constants import DEFAULT_CACHE_TTL_DAYS, DEFAULT_UNITS_MIN_REQUIRED

log = logging.getLogger("semrush")

BASE_URL = "https://api.semrush.com"
UNITS_URL = "https://www.semrush.com/users/countapiunits.html"


class SemrushClient:
    def __init__(
        self,
        token: str,
        cache_dir: Path,
        ttl_days: int = DEFAULT_CACHE_TTL_DAYS,
        min_units_required: int = DEFAULT_UNITS_MIN_REQUIRED
    ):
        self.token = token[-6:]  # solo últimos 6 para logs
        self.full_token = token
        self.cache_dir = cache_dir
        self.ttl_days = ttl_days
        self.min_units = min_units_required
        ensure_dir(self.cache_dir)

    # ===================================================================
    # Caché
    # ===================================================================
    def _cache_path(self, key: str) -> Path:
        safe_key = "".join(c if c.isalnum() else "_" for c in key)[:180]
        return self.cache_dir / f"{safe_key}.csv"

    def _is_fresh(self, path: Path) -> bool:
        if not path.exists():
            return False
        mtime = datetime.fromtimestamp(path.stat().st_mtime)
        return datetime.now() - mtime < timedelta(days=self.ttl_days)

    # ===================================================================
    # Units control
    # ===================================================================
    def _check_units(self) -> int:
        try:
            r = requests.get(UNITS_URL, params={"key": self.full_token}, timeout=10)
            units = int(r.text.strip())
            log.info("SEMrush units restantes: %s", units)
            if units < self.min_units:
                raise RuntimeError(f"SEMrush: solo {units} units (mínimo requerido: {self.min_units})")
            return units
        except requests.exceptions.RequestException as e:
            log.warning("No se pudieron comprobar units SEMrush (error de red): %s", e)
            return -1

    # ===================================================================
    # Core fetchers
    # ===================================================================
    def fetch_related(
        self,
        keyword: str,
        database: str = "es",
        limit: int = 60
    ) -> SemrushResults:
        self._check_units()

        cache_key = f"related_{database}_{keyword}_{limit}"
        cache_path = self._cache_path(cache_key)

        if self._is_fresh(cache_path):
            log.debug("Cache hit SEMrush related: %s", keyword)
            text = cache_path.read_text(encoding="utf-8")
        else:
            params = {
                "type": "phrase_related",
                "key": self.full_token,
                "phrase": keyword,
                "database": database,
                "export_columns": "Ph,Nq",
                "display_limit": str(limit),
                "display_sort": "nq_desc"
            }
            try:
                r = requests.get(BASE_URL, params=params, timeout=30)
            except requests.exceptions.RequestException as e:
                log.error("Error de red llamando SEMrush: %s", e)
                raise

            text = r.text

            if "ERROR 122" in text:
                raise RuntimeError("SEMrush ERROR 122: clave inválida o sin acceso")
            if r.status_code != 200 or not text.strip():
                log.warning("SEMrush related falló (status %s)", r.status_code)
            else:
                cache_path.write_text(text, encoding="utf-8")

        # Parse
        vol_main = 0
        related: list[SemrushKeyword] = []
        reader = csv.DictReader(io.StringIO(text), delimiter=";")
        for i, row in enumerate(reader):
            if i == 0:
                vol_main = int(row.get("Nq", "0").replace(",", "") or 0)
            kw = row.get("Keyword") or row.get("Ph")
            if kw:
                vol = int(row.get("Nq", "0").replace(",", "") or 0)
                related.append(SemrushKeyword(keyword=kw.strip(), search_volume=vol))

        result = SemrushResults(
            keyword_principal=SemrushKeyword(keyword=keyword, search_volume=vol_main),
            keywords_secundarias=related
        )
        return result
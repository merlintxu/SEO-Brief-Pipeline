# seo_pipeline/vendors/dataforseo_serp.py
"""
Cliente DataForSEO SERP API v3 – Google Organic + AI Overview (2025)
Uso opcional como alternativa o fallback automático a SerpAPI
"""
from __future__ import annotations

import time
import requests
from typing import Optional, Dict, List
from pathlib import Path

from seo_pipeline.utils.io import save_json, load_json, ensure_dir
from seo_pipeline.utils.logging import logger
from seo_pipeline.config import get_config

BASE_URL = "https://api.dataforseo.com/v3/serp/google/organic/live/advanced"

def fetch_serp_dataforseo(
    keyword: str,
    location_code: int = 2840,      # España por defecto
    language_code: str = "es",
    device: str = "desktop",
    os: str = "windows",
    limit: int = 12,
    dataforseo_login: Optional[str] = None,
    dataforseo_password: Optional[str] = None,
    cache_dir: Optional[Path] = None
) -> Optional[Dict]:
    """
    Obtiene SERP completa vía DataForSEO (modo live)
    Devuelve estructura compatible con SerpAPI para facilitar fallback
    """
    if not dataforseo_login or not dataforseo_password:
        cfg = get_config()
        client = cfg.active_client
        if not client or not hasattr(client, "dataforseo_login"):
            logger.warning("Credenciales DataForSEO no configuradas")
            return None
        dataforseo_login = client.dataforseo_login
        dataforseo_password = client.dataforseo_password

    # Caché
    if cache_dir:
        ensure_dir(cache_dir)
        cache_key = f"dataforseo_serp_{keyword}_{location_code}_{language_code}.json"
        cache_path = cache_dir / cache_key
        if cache_path.exists() and (time.time() - cache_path.stat().st_mtime) < 30*24*3600:
            logger.debug("Cache hit DataForSEO SERP: %s", keyword)
            return load_json(cache_path, default={})

    payload = [
        {
            "keyword": keyword,
            "location_code": location_code,
            "language_code": language_code,
            "device": device,
            "os": os,
            "depth": limit,
            "include_ai_overview": True,
            "include_clickstream_data": False
        }
    ]

    try:
        response = requests.post(
            BASE_URL,
            auth=(dataforseo_login, dataforseo_password),
            json=payload,
            timeout=120
        )

        if response.status_code != 200:
            logger.error("DataForSEO error %s: %s", response.status_code, response.text)
            return None

        data = response.json()

        if data["status_code"] != 20000 or not data["tasks"]:
            logger.warning("DataForSEO tarea fallida: %s", data.get("status_message"))
            return None

        result = data["tasks"][0]["result"][0]

        # Normalizar a formato similar a SerpAPI
        normalized = {
            "search_parameters": {
                "q": keyword,
                "gl": "es",
                "hl": language_code
            },
            "organic_results": [
                {
                    "position": item["rank_absolute"],
                    "title": item.get("title", ""),
                    "link": item.get("url", ""),
                    "domain": item.get("domain", ""),
                    "snippet": item.get("description", "")
                }
                for item in result.get("items", []) if item["type"] == "organic"
            ],
            "ai_overview": result.get("ai_overview", {}),
            "people_also_ask": result.get("related_searches", []),  # aproximado
            "related_searches": result.get("related_searches", [])
        }

        # Guardar caché
        if cache_dir:
            save_json(cache_path, normalized)

        logger.info("SERP obtenida vía DataForSEO para: %s (%s resultados)", keyword, len(normalized["organic_results"]))
        return normalized

    except (requests.exceptions.RequestException, ValueError) as e:
        logger.error("Excepción DataForSEO SERP: %s", e)
        return None

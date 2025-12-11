# seo_pipeline/vendors/scrapers.py
"""
Capa de scraping resiliente 2025 con failover automático:
1. requests directo
2. Piloterr[](https://www.piloterr.com)
3. DataForSEO Content Generation (fallback final)
"""
import requests
import time
from typing import Optional
from seo_pipeline.utils.logging import logger

def scrape_with_failover(
    url: str,
    piloterr_key: Optional[str] = None,
    dataforseo_login: Optional[str] = None,
    dataforseo_password: Optional[str] = None,
    timeout: int = 20
) -> Optional[str]:
    # 1. Intento directo
    try:
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0 (compatible; SEOAuditBot/2025)"}, timeout=timeout)
        if r.status_code == 200:
            return r.text
    except requests.exceptions.RequestException as e:
        logger.debug("Fallo intento directo %s: %s", url, e)

    # 2. Piloterr
    if piloterr_key:
        try:
            api_url = "https://api.piloterr.com/v1/scrape"
            payload = {"url": url}
            headers = {"x-api-key": piloterr_key}
            r = requests.post(api_url, json=payload, headers=headers, timeout=timeout)
            if r.status_code == 200:
                try:
                    data = r.json()
                except ValueError:
                    data = {}
                if data.get("success"):
                    return data.get("data", {}).get("content")
        except requests.exceptions.RequestException as e:
            logger.debug("Fallo Piloterr %s: %s", url, e)

    # 3. DataForSEO (Content Generation API – modo live)
    if dataforseo_login and dataforseo_password:
        try:
            auth = (dataforseo_login, dataforseo_password)
            post_data = [{"url": url, "enable_javascript": True, "custom_user_agent": "Mozilla/5.0"}]
            r = requests.post(
                "https://api.dataforseo.com/v3/content_generation/text/live",
                auth=auth,
                json=post_data,
                timeout=60
            )
            if r.status_code == 200:
                result = r.json()
                if result["status_code"] == 20000:
                    return result["tasks"][0]["result"][0]["items"][0]["text"]
        except (requests.exceptions.RequestException, ValueError, KeyError) as e:
            logger.warning("Fallo DataForSEO fallback %s: %s", url, e)

    logger.error("Todos los métodos de descarga fallaron para %s", url)
    return None
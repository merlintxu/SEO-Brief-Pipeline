"""Google Analytics 4 Data API helpers.

The pipeline uses GA4 as optional enrichment for existing-page briefings. Tests
mock the Google service; automated tests must not call real Google APIs.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional
from urllib.parse import urlparse

try:
    from google.oauth2.service_account import Credentials
    from googleapiclient.discovery import build

    GA4_LIBS_OK = True
except ImportError:
    Credentials = None  # type: ignore
    build = None  # type: ignore
    GA4_LIBS_OK = False


SCOPES = ["https://www.googleapis.com/auth/analytics.readonly"]


@dataclass(frozen=True)
class Ga4UrlMetrics:
    property_id: str
    page_path: str
    start_date: str
    end_date: str
    sessions: int
    total_users: int
    screen_page_views: int
    conversions: float
    engagement_rate: float | None = None

    def model_dump(self) -> dict:
        return {
            "property_id": self.property_id,
            "page_path": self.page_path,
            "start_date": self.start_date,
            "end_date": self.end_date,
            "sessions": self.sessions,
            "total_users": self.total_users,
            "screen_page_views": self.screen_page_views,
            "conversions": self.conversions,
            "engagement_rate": self.engagement_rate,
        }


def build_service(sa_json_path: str, subject: Optional[str] = None):
    if not GA4_LIBS_OK or Credentials is None or build is None:
        raise RuntimeError("Faltan librerias google-auth / google-api-client")
    try:
        creds = Credentials.from_service_account_file(sa_json_path, scopes=SCOPES)
    except FileNotFoundError as exc:
        raise RuntimeError(f"Archivo de credenciales GA4 no encontrado: {sa_json_path}") from exc
    if subject:
        creds = creds.with_subject(subject)
    return build("analyticsdata", "v1beta", credentials=creds, cache_discovery=False)


def fetch_url_metrics(
    *,
    property_id: str,
    target_url: str,
    sa_json_path: str,
    start_date: str | None = None,
    end_date: str | None = None,
    service: object | None = None,
) -> Ga4UrlMetrics:
    end_date = end_date or datetime.now().strftime("%Y-%m-%d")
    start_date = start_date or (datetime.now() - timedelta(days=90)).strftime("%Y-%m-%d")
    page_path = _url_to_path(target_url)
    analytics = service or build_service(sa_json_path)
    body = {
        "dateRanges": [{"startDate": start_date, "endDate": end_date}],
        "dimensions": [{"name": "pagePath"}],
        "metrics": [
            {"name": "sessions"},
            {"name": "totalUsers"},
            {"name": "screenPageViews"},
            {"name": "conversions"},
            {"name": "engagementRate"},
        ],
        "dimensionFilter": {
            "filter": {
                "fieldName": "pagePath",
                "stringFilter": {"matchType": "EXACT", "value": page_path},
            }
        },
        "limit": 1,
    }
    response = analytics.properties().runReport(property=f"properties/{property_id}", body=body).execute()
    rows = response.get("rows", [])
    values = rows[0].get("metricValues", []) if rows else []
    return Ga4UrlMetrics(
        property_id=property_id,
        page_path=page_path,
        start_date=start_date,
        end_date=end_date,
        sessions=_int_metric(values, 0),
        total_users=_int_metric(values, 1),
        screen_page_views=_int_metric(values, 2),
        conversions=_float_metric(values, 3),
        engagement_rate=_float_metric(values, 4) if values else None,
    )


def _url_to_path(target_url: str) -> str:
    parsed = urlparse(target_url)
    if not parsed.scheme and not parsed.netloc:
        return target_url if target_url.startswith("/") else f"/{target_url}"
    path = parsed.path or "/"
    return path


def _int_metric(values: list[dict], index: int) -> int:
    try:
        return int(float(values[index].get("value", 0)))
    except (IndexError, TypeError, ValueError, AttributeError):
        return 0


def _float_metric(values: list[dict], index: int) -> float:
    try:
        return float(values[index].get("value", 0))
    except (IndexError, TypeError, ValueError, AttributeError):
        return 0.0

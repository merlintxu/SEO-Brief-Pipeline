"""Canonical artifact filenames shared by exporter, pipeline and API."""
from __future__ import annotations

from typing import Final

BRIEFING_JSON: Final = "briefing.json"
BRIEFING_MARKDOWN: Final = "briefing.md"
ROW24_CSV: Final = "row24.csv"
ROW24_XLSX: Final = "row24.xlsx"
STATUS_JSON: Final = "status.json"
AUDIT_REPORT_JSON: Final = "audit_report.json"
SERP_RAW_JSON: Final = "serp_raw.json"
RUN_METRICS_JSON: Final = "run_metrics.json"
TARGET_AUDIT_REPORT_JSON: Final = "target_audit_report.json"
AI_SEARCH_READINESS_JSON: Final = "ai_search_readiness.json"

EXPORT_ARTIFACTS: Final = {
    BRIEFING_JSON,
    BRIEFING_MARKDOWN,
    ROW24_CSV,
    ROW24_XLSX,
}

DOWNLOADABLE_ARTIFACTS: Final = {
    *EXPORT_ARTIFACTS,
    STATUS_JSON,
    AUDIT_REPORT_JSON,
    TARGET_AUDIT_REPORT_JSON,
    AI_SEARCH_READINESS_JSON,
    SERP_RAW_JSON,
    RUN_METRICS_JSON,
}

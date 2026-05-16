"""Google Drive helpers for operator spreadsheet discovery."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

try:
    from google.oauth2.service_account import Credentials
    from googleapiclient.discovery import build

    DRIVE_LIBS_OK = True
except ImportError:
    Credentials = None  # type: ignore
    build = None  # type: ignore
    DRIVE_LIBS_OK = False


SCOPES = ["https://www.googleapis.com/auth/drive.metadata.readonly"]
SHEETS_MIME_TYPE = "application/vnd.google-apps.spreadsheet"


@dataclass(frozen=True)
class DriveSpreadsheet:
    spreadsheet_id: str
    name: str
    web_url: str


def build_service(sa_json_path: str, subject: Optional[str] = None):
    if not DRIVE_LIBS_OK or Credentials is None or build is None:
        raise RuntimeError("Faltan librerias google-auth / google-api-client")
    try:
        creds = Credentials.from_service_account_file(sa_json_path, scopes=SCOPES)
    except FileNotFoundError as exc:
        raise RuntimeError(f"Archivo de credenciales Drive no encontrado: {sa_json_path}") from exc
    if subject:
        creds = creds.with_subject(subject)
    return build("drive", "v3", credentials=creds, cache_discovery=False)


def list_spreadsheets(
    *,
    sa_json_path: str,
    query: str = "",
    limit: int = 20,
    service: object | None = None,
) -> list[DriveSpreadsheet]:
    drive = service or build_service(sa_json_path)
    name_filter = f" and name contains '{_escape_drive_query(query)}'" if query.strip() else ""
    response = (
        drive.files()
        .list(
            q=f"mimeType = '{SHEETS_MIME_TYPE}' and trashed = false{name_filter}",
            pageSize=max(1, min(int(limit), 100)),
            fields="files(id,name,webViewLink)",
            orderBy="modifiedTime desc",
        )
        .execute()
    )
    return [
        DriveSpreadsheet(
            spreadsheet_id=item.get("id", ""),
            name=item.get("name", ""),
            web_url=item.get("webViewLink", ""),
        )
        for item in response.get("files", [])
        if item.get("id")
    ]


def _escape_drive_query(value: str) -> str:
    return value.strip().replace("\\", "\\\\").replace("'", "\\'")

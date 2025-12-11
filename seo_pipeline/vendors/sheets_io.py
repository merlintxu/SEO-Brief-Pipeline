# seo_pipeline/vendors/sheets_io.py
"""
Integración Google Sheets con gspread.
- Upsert idempotente basado en claves compuestas
- Creación automática de pestañas
- Manejo robusto de autenticación vía Service Account
- Logging detallado y tolerancia a fallos
"""
from __future__ import annotations

from typing import List, Dict, Any, Optional
import logging

from seo_pipeline.utils.io import ensure_dir

log = logging.getLogger("sheets_io")

try:
    import gspread
    from gspread.exceptions import WorksheetNotFound, APIError
    GSPREAD_OK = True
except ImportError as e:
    gspread = None  # type: ignore
    GSPREAD_OK = False
    log.warning("gspread no disponible: %s", e)


def _ensure_gspread() -> None:
    if not GSPREAD_OK or gspread is None:
        raise RuntimeError("gspread no instalado. Ejecuta: pip install gspread")


class SheetHandler:
    def __init__(self, spreadsheet_id: str, sa_json_path: str):
        _ensure_gspread()
        self.sa_path = sa_json_path
        self.gc = gspread.service_account(filename=sa_json_path)
        self.sh = self.gc.open_by_key(spreadsheet_id)

    def get_or_create_worksheet(self, title: str, rows: int = 1000, cols: int = 30) -> gspread.Worksheet:
        try:
            ws = self.sh.worksheet(title)
            log.debug("Pestaña existente: %s", title)
            return ws
        except WorksheetNotFound:
            ws = self.sh.add_worksheet(title=title, rows=rows, cols=cols)
            log.info("Pestaña creada: %s", title)
            return ws

    def ensure_headers(self, ws: gspread.Worksheet, headers: List[str]) -> None:
        current = ws.row_values(1)
        if current == headers:
            return
        if current:
            ws.delete_rows(1)
        ws.insert_row(headers, index=1)
        log.debug("Headers asegurados en %s", ws.title)

    def upsert_row(
        self,
        ws: gspread.Worksheet,
        headers: List[str],
        key_columns: List[str],
        row_data: List[Any]
    ) -> Dict[str, Any]:
        """
        Upsert idempotente:
        - Busca coincidencia exacta en key_columns
        - Actualiza fila si existe
        - Appendea si no existe
        """
        col_index = {h: i + 1 for i, h in enumerate(headers)}
        key_values = [row_data[col_index[k] - 1] for k in key_columns]

        # Búsqueda por primera clave (más eficiente)
        try:
            cells = ws.findall(str(key_values[0]), in_column=col_index[key_columns[0]])
        except APIError:
            # Error de la API de Google Sheets → no detener el flujo, tratamos como no encontrado
            cells = []

        for cell in cells:
            row_vals = ws.row_values(cell.row)
            if len(row_vals) < len(headers):
                row_vals += [""] * (len(headers) - len(row_vals))
            match = all(
                str(row_vals[col_index[k] - 1]).strip() == str(key_values[i]).strip()
                for i, k in enumerate(key_columns)
            )
            if match:
                ws.update(f"A{cell.row}", [row_data], value_input_option="USER_ENTERED")
                log.debug("Fila actualizada (row %s)", cell.row)
                return {"status": "updated", "row": cell.row}

        # No existe → append
        ws.append_row(row_data, value_input_option="USER_ENTERED")
        new_row = ws.row_count
        log.info("Fila insertada (row %s)", new_row)
        return {"status": "inserted", "row": new_row}


# Función de alto nivel (uso recomendado)
def upsert_to_sheet(
    spreadsheet_id: str,
    tab_name: str,
    headers: List[str],
    key_columns: List[str],
    row: List[Any],
    sa_json_path: str
) -> Dict[str, Any]:
    handler = SheetHandler(spreadsheet_id, sa_json_path)
    ws = handler.get_or_create_worksheet(tab_name)
    handler.ensure_headers(ws, headers)
    return handler.upsert_row(ws, headers, key_columns, row)
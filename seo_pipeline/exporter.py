# seo_pipeline/exporter.py
"""
Exportación final en todos los formatos requeridos:
- JSON (estructurado completo)
- CSV / XLSX (compatible con fila 24 columnas)
- Markdown (briefing legible para redactor)
Centraliza toda la lógica de escritura para evitar duplicidades.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any
import pandas as pd

from seo_pipeline.models import SheetRow24, SEOBriefing
from seo_pipeline.utils.io import save_json, save_text
from seo_pipeline.blueprint import save_briefing_markdown
from seo_pipeline.constants import HEADERS_24
from seo_pipeline.utils.logging import logger


def export_all_formats(
    run_id: str,
    keyword: str,
    row24: SheetRow24,
    briefing: SEOBriefing,
    output_dir: Path
) -> dict[str, Path]:
    """
    Exporta todos los artefactos de una ejecución en un directorio dedicado.
    Devuelve mapping {formato → Path}.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    exports = {}

    # 1. JSON completo (briefing estructurado)
    json_path = output_dir / f"{run_id}_{keyword}_briefing.json"
    save_json(json_path, briefing.model_dump())
    exports["json"] = json_path

    # 2. Markdown legible
    md_path = output_dir / f"{run_id}_{keyword}_briefing.md"
    save_briefing_markdown(briefing, md_path)
    exports["markdown"] = md_path

    # 3. Fila 24 columnas → CSV y XLSX
    row_data = row24.to_row()

    # CSV
    csv_path = output_dir / f"{run_id}_row24.csv"
    df_csv = pd.DataFrame([row_data], columns=HEADERS_24)
    df_csv.to_csv(csv_path, index=False, encoding="utf-8")
    exports["csv"] = csv_path

    # XLSX
    xlsx_path = output_dir / f"{run_id}_row24.xlsx"
    df_csv.to_excel(xlsx_path, index=False, engine="openpyxl")
    exports["xlsx"] = xlsx_path

    logger.info("Exportación completa para %s → %s artefactos", keyword, len(exports))
    return exports
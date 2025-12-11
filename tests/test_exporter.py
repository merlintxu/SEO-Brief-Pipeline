from pathlib import Path

import pandas as pd

from seo_pipeline.models import SheetRow24
from seo_pipeline.models import SEOBriefing, BriefingSection
from seo_pipeline.exporter import export_all_formats


def make_briefing():
    headings = [BriefingSection(title=f"S{i}", content="Contenido") for i in range(1, 9)]
    briefing = SEOBriefing(
        meta_title="MT",
        meta_description="MD",
        h1="H1",
        tone_style="neutral",
        unique_angle="ángulo",
        headings=headings,
    )
    return briefing


def make_row24():
    return SheetRow24(
        kw_principal="kw",
        sv_principal=100,
        kw_secundarias=["a", "b"],
        url_objetivo="",
        title="t",
        h1="h1",
        meta_desc="md",
        run_id="r1",
    )


def test_export_all_formats(tmp_path: Path):
    briefing = make_briefing()
    row24 = make_row24()
    out = tmp_path / "out"
    out.mkdir()
    exports = export_all_formats(run_id="r1", keyword="kw test", row24=row24, briefing=briefing, output_dir=out)
    # Expect json, markdown, csv, xlsx
    assert "json" in exports and exports["json"].exists()
    assert "markdown" in exports and exports["markdown"].exists()
    assert "csv" in exports and exports["csv"].exists()
    assert "xlsx" in exports and exports["xlsx"].exists()

    # Load CSV and check headers count
    df = pd.read_csv(exports["csv"])
    assert df.shape[0] == 1

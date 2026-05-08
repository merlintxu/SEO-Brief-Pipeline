from seo_pipeline.vendors import gsc_io


class _FakeQuery:
    def __init__(self, rows):
        self.rows = rows

    def execute(self):
        return {"rows": self.rows}


class _FakeSearchAnalytics:
    def __init__(self, rows):
        self.rows = rows

    def query(self, siteUrl, body):
        return _FakeQuery(self.rows)


class _FakeService:
    def __init__(self, rows):
        self.rows = rows

    def searchanalytics(self):
        return _FakeSearchAnalytics(self.rows)


def test_fetch_cannibalization_maps_clicks_field(monkeypatch):
    rows = [
        {"keys": ["kw", "https://example.com/a"], "clicks": 3, "impressions": 30, "position": 2},
        {"keys": ["kw", "https://example.com/b"], "clicks": 1, "impressions": 20, "position": 5},
    ]
    monkeypatch.setattr(gsc_io, "build_service", lambda *args, **kwargs: _FakeService(rows))

    result = gsc_io.fetch_cannibalization(
        site_url="https://example.com/",
        start_date="2026-01-01",
        end_date="2026-01-31",
        sa_json_path="credentials/gsc.json",
        min_impressions=1,
    )

    assert len(result.items) == 1
    assert result.items[0].query == "kw"
    assert result.items[0].pages[0].clicks == 3
    assert result.items[0].pages[1].clicks == 1

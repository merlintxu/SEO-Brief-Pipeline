from seo_pipeline.vendors.ga4_io import fetch_url_metrics


class _FakeAnalytics:
    def properties(self):
        return self

    def runReport(self, *, property, body):
        self.property = property
        self.body = body
        return self

    def execute(self):
        return {
            "rows": [
                {
                    "metricValues": [
                        {"value": "10"},
                        {"value": "8"},
                        {"value": "14"},
                        {"value": "2"},
                        {"value": "0.72"},
                    ]
                }
            ]
        }


def test_fetch_url_metrics_parses_ga4_response():
    service = _FakeAnalytics()

    metrics = fetch_url_metrics(
        property_id="123456",
        target_url="https://example.com/path/?utm=ignored",
        sa_json_path="credentials/ga4.json",
        start_date="2026-01-01",
        end_date="2026-01-31",
        service=service,
    )

    assert service.property == "properties/123456"
    assert service.body["dimensionFilter"]["filter"]["stringFilter"]["value"] == "/path/"
    assert metrics.page_path == "/path/"
    assert metrics.sessions == 10
    assert metrics.total_users == 8
    assert metrics.screen_page_views == 14
    assert metrics.conversions == 2.0
    assert metrics.engagement_rate == 0.72

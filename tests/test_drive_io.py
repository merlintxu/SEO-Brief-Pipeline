from seo_pipeline.vendors.drive_io import list_spreadsheets


class _FakeFiles:
    def list(self, **kwargs):
        self.kwargs = kwargs
        return self

    def execute(self):
        return {
            "files": [
                {
                    "id": "sheet-1",
                    "name": "Briefings",
                    "webViewLink": "https://docs.google.com/spreadsheets/d/sheet-1/edit",
                }
            ]
        }


class _FakeDrive:
    def __init__(self):
        self._files = _FakeFiles()

    def files(self):
        return self._files


def test_list_spreadsheets_maps_drive_files():
    service = _FakeDrive()

    items = list_spreadsheets(sa_json_path="credentials/sheets.json", query="Brief", service=service)

    assert len(items) == 1
    assert items[0].spreadsheet_id == "sheet-1"
    assert items[0].name == "Briefings"
    assert "mimeType" in service._files.kwargs["q"]
    assert "Brief" in service._files.kwargs["q"]

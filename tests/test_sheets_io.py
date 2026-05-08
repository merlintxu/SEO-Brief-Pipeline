import pytest

from seo_pipeline.vendors.sheets_io import normalize_spreadsheet_id


def test_normalize_spreadsheet_id_accepts_raw_id():
    assert normalize_spreadsheet_id("spreadsheet-id-123") == "spreadsheet-id-123"


def test_normalize_spreadsheet_id_extracts_id_from_url():
    url = "https://docs.google.com/spreadsheets/d/spreadsheet-id-123/edit#gid=0"

    assert normalize_spreadsheet_id(url) == "spreadsheet-id-123"


def test_normalize_spreadsheet_id_rejects_malformed_google_url():
    with pytest.raises(ValueError):
        normalize_spreadsheet_id("https://docs.google.com/spreadsheets/edit#gid=0")

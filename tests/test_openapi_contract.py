import json
import os
from pathlib import Path


def test_openapi_contract_file_exists_and_is_valid_json():
    contract_path = Path("docs/contracts/openapi.json")
    assert contract_path.exists()
    data = json.loads(contract_path.read_text(encoding="utf-8"))
    assert data.get("openapi")
    assert data.get("info", {}).get("title") == "SEO Briefing Pipeline API"


def test_openapi_contract_contains_required_paths():
    contract_path = Path("docs/contracts/openapi.json")
    data = json.loads(contract_path.read_text(encoding="utf-8"))
    paths = data.get("paths", {})
    required = {
        "/health",
        "/briefing",
        "/briefing/{run_id}",
        "/jobs",
        "/jobs/{run_id}",
        "/jobs/cleanup",
        "/jobs/{run_id}/retry",
        "/jobs/{run_id}/cancel",
        "/outputs/{run_id}/{filename}",
    }
    assert required.issubset(set(paths.keys()))


def test_openapi_contract_matches_runtime_version():
    os.environ.setdefault("API_KEY", "openapi-contract-test-key-2026")
    from api.main import app

    runtime = app.openapi()
    contract = json.loads(Path("docs/contracts/openapi.json").read_text(encoding="utf-8"))
    assert contract["info"]["version"] == runtime["info"]["version"]

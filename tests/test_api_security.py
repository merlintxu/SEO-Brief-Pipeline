import os
import subprocess
import sys
from pathlib import Path

from fastapi.testclient import TestClient


REPO_ROOT = Path(__file__).resolve().parents[1]


def run_api_import_with_key(api_key: str) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env["API_KEY"] = api_key
    env["PYTHONPATH"] = str(REPO_ROOT)
    return subprocess.run(
        [sys.executable, "-c", "import api.main; print(api.main.app.title)"],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )


def test_api_fails_fast_with_missing_or_short_api_key():
    for value in ("", "too-short"):
        result = run_api_import_with_key(value)

        assert result.returncode != 0
        assert "API_KEY environment variable must be set and >= 20 chars" in result.stderr


def test_api_imports_with_valid_api_key():
    result = run_api_import_with_key("test-token-with-enough-length")

    assert result.returncode == 0
    assert "SEO Briefing Pipeline API" in result.stdout


def test_static_outputs_route_is_not_mounted(monkeypatch):
    monkeypatch.setenv("API_KEY", "test-token-with-enough-length")
    from api.main import app

    assert all(not getattr(route, "path", "").startswith("/static") for route in app.routes)


def test_download_endpoint_rejects_unapproved_filenames(monkeypatch):
    monkeypatch.setenv("API_KEY", "test-token-with-enough-length")
    from api.main import app

    client = TestClient(app)
    response = client.get("/outputs/run123/.env")

    assert response.status_code == 403

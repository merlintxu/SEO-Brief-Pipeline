import json
import os
import time
from pathlib import Path

from fastapi.testclient import TestClient

from seo_pipeline.config import ClientConfig, ProjectConfig, get_config


os.environ["API_KEY"] = "secret-token-2025-test-key-long-enough"


def setup_cfg(tmp_path: Path) -> None:
    cfg = get_config()
    cfg.root_dir = tmp_path
    cfg.active_client = ClientConfig(
        client_id="c1",
        name="c1",
        semrush_token="token",
        serpapi_key="serp",
        openai_key="openai",
        gsc_sa_path=None,
        sheets_sa_path=None,
    )
    cfg.active_project = ProjectConfig(
        project_id="p1",
        client_id="c1",
        name="p1",
        base_domain="example.com",
        gsc_property="https://example.com/",
        sheets_id="",
        output_dir="outputs",
    )


def read_status_with_retries(client: TestClient, run_id: str, attempts: int = 3) -> dict | None:
    for _ in range(attempts):
        response = client.get(f"/briefing/{run_id}")
        if response.status_code == 200:
            data = response.json()
            if data.get("status") in ("done", "failed"):
                return data
        time.sleep(0.2)
    return None


def test_api_smoke_post_poll_and_download(tmp_path, monkeypatch):
    setup_cfg(tmp_path)

    def fake_run_full_pipeline(*, keyword, run_id, status_path, output_dir, **kwargs):
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        status_payload = {"status": "done", "step": "done", "message": "ok", "error_category": None}
        metrics_payload = {
            "run_id": run_id,
            "keyword": keyword,
            "status": "done",
            "stages": {"smoke": {"status": "ok", "provider": "mock", "retries": 0}},
        }
        briefing_payload = {"h1": "Smoke H1"}
        (output_dir / "status.json").write_text(json.dumps(status_payload), encoding="utf-8")
        (output_dir / "run_metrics.json").write_text(json.dumps(metrics_payload), encoding="utf-8")
        (output_dir / "briefing.json").write_text(json.dumps(briefing_payload), encoding="utf-8")
        return {"run_id": run_id, "keyword": keyword, "output_dir": str(output_dir)}

    monkeypatch.setattr("api.main.run_full_pipeline", fake_run_full_pipeline)

    from api.main import app

    client = TestClient(app)

    unauthorized = client.post(
        "/briefing",
        json={"keyword": "smoke", "upload_to_sheets": False, "related_limit": 5, "serp_num": 5},
    )
    assert unauthorized.status_code == 403

    response = client.post(
        "/briefing",
        json={"keyword": "smoke", "upload_to_sheets": False, "related_limit": 5, "serp_num": 5},
        headers={"X-API-Key": "secret-token-2025-test-key-long-enough"},
    )
    assert response.status_code == 200
    run_id = response.json()["run_id"]

    status_data = read_status_with_retries(client, run_id, attempts=3)
    assert status_data is not None
    assert status_data["status"] == "done"

    status_file = client.get(
        f"/outputs/{run_id}/status.json",
        headers={"X-API-Key": "secret-token-2025-test-key-long-enough"},
    )
    assert status_file.status_code == 200
    assert status_file.json()["status"] in ("queued", "running", "done")

    metrics_file = client.get(
        f"/outputs/{run_id}/run_metrics.json",
        headers={"X-API-Key": "secret-token-2025-test-key-long-enough"},
    )
    assert metrics_file.status_code == 200
    assert metrics_file.json()["status"] == "done"

    briefing_file = client.get(
        f"/outputs/{run_id}/briefing.json",
        headers={"X-API-Key": "secret-token-2025-test-key-long-enough"},
    )
    assert briefing_file.status_code == 200
    assert briefing_file.json()["h1"] == "Smoke H1"


def test_briefing_status_falls_back_to_job_store(tmp_path):
    setup_cfg(tmp_path)
    from api.main import app, job_store

    run_id = f"run_job_store_only_{int(time.time() * 1000)}"
    job_store.create_job(run_id=run_id, keyword="kw", output_dir=str(tmp_path / "outputs" / run_id))
    job_store.update_status(run_id, status="failed", step="error", message="provider error", error_category="network")

    client = TestClient(app)
    response = client.get(f"/briefing/{run_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "failed"
    assert data["error_category"] == "network"

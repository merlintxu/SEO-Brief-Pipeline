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


def test_ops_dashboard_route_serves_html(tmp_path):
    setup_cfg(tmp_path)
    from api.main import app

    client = TestClient(app)
    response = client.get("/ops")
    assert response.status_code == 200
    assert "text/html" in response.headers.get("content-type", "")


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


def test_jobs_endpoint_requires_auth_and_lists_items(tmp_path):
    setup_cfg(tmp_path)
    from api.main import app, job_store

    run_id = f"run_jobs_endpoint_{int(time.time() * 1000)}"
    job_store.create_job(run_id=run_id, keyword="kw-jobs", output_dir=str(tmp_path / "outputs" / run_id))
    job_store.update_status(run_id, status="done", step="done", message="ok")

    client = TestClient(app)
    unauthorized = client.get("/jobs")
    assert unauthorized.status_code == 403

    response = client.get("/jobs?limit=5", headers={"X-API-Key": "secret-token-2025-test-key-long-enough"})
    assert response.status_code == 200
    body = response.json()
    assert "items" in body
    assert "count" in body
    assert any(item["run_id"] == run_id for item in body["items"])


def test_jobs_endpoint_supports_status_and_search_filters(tmp_path):
    setup_cfg(tmp_path)
    from api.main import app, job_store

    run_failed = f"run_jobs_failed_{int(time.time() * 1000)}"
    run_done = f"run_jobs_done_{int(time.time() * 1000)}"
    job_store.create_job(run_id=run_failed, keyword="alpha test", output_dir=str(tmp_path / "outputs" / run_failed))
    job_store.create_job(run_id=run_done, keyword="beta test", output_dir=str(tmp_path / "outputs" / run_done))
    job_store.update_status(run_failed, status="failed", step="error", message="failed")
    job_store.update_status(run_done, status="done", step="done", message="ok")

    client = TestClient(app)
    headers = {"X-API-Key": "secret-token-2025-test-key-long-enough"}
    response = client.get("/jobs?limit=20&status=failed&q=alpha", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["count"] >= 1
    assert any(item["run_id"] == run_failed for item in body["items"])
    assert all(item["status"] == "failed" for item in body["items"])


def test_jobs_endpoint_limit_validation(tmp_path):
    setup_cfg(tmp_path)
    from api.main import app

    client = TestClient(app)
    headers = {"X-API-Key": "secret-token-2025-test-key-long-enough"}

    too_low = client.get("/jobs?limit=0", headers=headers)
    assert too_low.status_code == 422

    too_high = client.get("/jobs?limit=201", headers=headers)
    assert too_high.status_code == 422


def test_operator_audit_trail_endpoints_require_auth_and_persist_events(tmp_path):
    setup_cfg(tmp_path)
    from api.main import app

    client = TestClient(app)
    headers = {"X-API-Key": "secret-token-2025-test-key-long-enough"}

    unauthorized = client.get("/ops/audit-trail")
    assert unauthorized.status_code == 403

    created = client.post(
        "/ops/audit-trail",
        headers=headers,
        json={
            "action": "delete_confirm",
            "result": "confirmed",
            "run_id": "run_audit_api",
            "metadata": "run_id=run_audit_api",
        },
    )
    assert created.status_code == 200
    created_body = created.json()
    assert created_body["action"] == "delete_confirm"
    assert created_body["run_id"] == "run_audit_api"

    listed = client.get("/ops/audit-trail?limit=5&cursor=0", headers=headers)
    assert listed.status_code == 200
    body = listed.json()
    assert body["count"] >= 1
    assert any(item["id"] == created_body["id"] for item in body["items"])


def test_ops_slo_endpoint_evaluates_recent_job_metrics(tmp_path):
    setup_cfg(tmp_path)
    from api.main import app, job_store

    run_id = f"run_slo_{int(time.time() * 1000)}"
    output_dir = tmp_path / "outputs" / run_id
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "run_metrics.json").write_text(
        json.dumps(
            {
                "status": "done",
                "stages": {
                    "semrush": {"duration_seconds": 10, "retries": 0},
                    "briefing": {"duration_seconds": 20, "retries": 0},
                },
            }
        ),
        encoding="utf-8",
    )
    job_store.create_job(run_id=run_id, keyword="kw-slo", output_dir=str(output_dir))
    job_store.update_status(run_id, status="done", step="done", message="ok")

    client = TestClient(app)
    headers = {"X-API-Key": "secret-token-2025-test-key-long-enough"}
    unauthorized = client.get("/ops/slo")
    assert unauthorized.status_code == 403

    response = client.get("/ops/slo?limit=10", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["evaluated_run_count"] >= 1
    assert body["summary"]["success_rate"] >= 0
    assert isinstance(body["checks"], list)
    assert {"window", "thresholds", "summary", "checks", "passed"}.issubset(body)


def test_get_and_delete_job_endpoints(tmp_path):
    setup_cfg(tmp_path)
    from api.main import app, job_store

    run_id = f"run_job_detail_{int(time.time() * 1000)}"
    output_dir = tmp_path / "outputs" / run_id
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "status.json").write_text(
        json.dumps({"status": "done", "step": "done", "message": "ok"}),
        encoding="utf-8",
    )
    (output_dir / "run_metrics.json").write_text(
        json.dumps({"costs": {"currency": "USD", "total_estimated_cost_usd": 0.0123, "estimates": []}}),
        encoding="utf-8",
    )
    job_store.create_job(run_id=run_id, keyword="kw-detail", output_dir=str(output_dir))
    job_store.update_status(run_id, status="done", step="done", message="ok")

    client = TestClient(app)
    headers = {"X-API-Key": "secret-token-2025-test-key-long-enough"}
    detail = client.get(f"/jobs/{run_id}", headers=headers)
    assert detail.status_code == 200
    assert detail.json()["job"]["run_id"] == run_id
    assert detail.json()["cost_summary"]["total_estimated_cost_usd"] == 0.0123
    assert isinstance(detail.json().get("events"), list)
    assert len(detail.json()["events"]) >= 2
    assert detail.json()["events"][0]["run_id"] == run_id
    events_resp = client.get(f"/jobs/{run_id}/events?limit=1&cursor=0", headers=headers)
    assert events_resp.status_code == 200
    events_body = events_resp.json()
    assert events_body["count"] == 1
    assert isinstance(events_body["items"], list)
    assert events_body["items"][0]["run_id"] == run_id

    deleted = client.delete(f"/jobs/{run_id}", headers=headers)
    assert deleted.status_code == 200
    assert deleted.json()["deleted"] is True

    missing = client.get(f"/jobs/{run_id}", headers=headers)
    assert missing.status_code == 404


def test_jobs_cleanup_endpoint(tmp_path):
    setup_cfg(tmp_path)
    from api.main import app, job_store

    run_id = f"run_job_cleanup_{int(time.time() * 1000)}"
    output_dir = tmp_path / "outputs" / run_id
    output_dir.mkdir(parents=True, exist_ok=True)
    job_store.create_job(run_id=run_id, keyword="kw-clean", output_dir=str(output_dir))
    job_store.update_status(run_id, status="done", step="done", message="ok")

    client = TestClient(app)
    headers = {"X-API-Key": "secret-token-2025-test-key-long-enough"}
    response = client.post("/jobs/cleanup", headers=headers, json={"max_age_days": 30, "statuses": ["done", "failed"]})
    assert response.status_code == 200
    body = response.json()
    assert "deleted_count" in body
    assert body["max_age_days"] == 30


def test_jobs_cancel_and_retry_endpoints(tmp_path, monkeypatch):
    setup_cfg(tmp_path)
    from api.main import app, job_store

    def fake_run_full_pipeline(*, keyword, run_id, status_path, output_dir, **kwargs):
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        status_payload = {"status": "done", "step": "done", "message": "ok", "error_category": None}
        (output_dir / "status.json").write_text(json.dumps(status_payload), encoding="utf-8")
        return {"run_id": run_id, "keyword": keyword, "output_dir": str(output_dir)}

    monkeypatch.setattr("api.main.run_full_pipeline", fake_run_full_pipeline)

    run_failed = f"run_job_retry_{int(time.time() * 1000)}"
    run_running = f"run_job_cancel_{int(time.time() * 1000)}"
    output_failed = tmp_path / "outputs" / run_failed
    output_running = tmp_path / "outputs" / run_running
    output_failed.mkdir(parents=True, exist_ok=True)
    output_running.mkdir(parents=True, exist_ok=True)
    job_store.create_job(run_id=run_failed, keyword="kw-retry", output_dir=str(output_failed))
    job_store.update_status(run_failed, status="failed", step="error", message="boom", error_category="unknown")
    job_store.create_job(run_id=run_running, keyword="kw-cancel", output_dir=str(output_running))
    job_store.update_status(run_running, status="running", step="serp", message="running")

    client = TestClient(app)
    headers = {"X-API-Key": "secret-token-2025-test-key-long-enough"}

    retry_resp = client.post(f"/jobs/{run_failed}/retry", headers=headers)
    assert retry_resp.status_code == 200
    retry_body = retry_resp.json()
    assert retry_body["source_run_id"] == run_failed
    assert retry_body["status"] == "queued"
    retried_run = job_store.get_job(retry_body["run_id"])
    assert retried_run is not None
    assert retried_run.source_run_id == run_failed

    cancel_resp = client.post(f"/jobs/{run_running}/cancel", headers=headers)
    assert cancel_resp.status_code == 200
    cancel_body = cancel_resp.json()
    assert cancel_body["run_id"] == run_running
    assert cancel_body["step"] == "canceled"

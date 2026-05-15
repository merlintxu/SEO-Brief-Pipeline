import pytest

from seo_pipeline.config import ClientConfig, ProjectConfig
from seo_pipeline.runtime_validation import RuntimeValidationError, validate_runtime_requirements


class DummyConfig:
    active_client = None
    active_project = None


def make_project() -> ProjectConfig:
    return ProjectConfig(
        project_id="p1",
        client_id="c1",
        name="p1",
        base_domain="example.com",
        gsc_property="https://example.com/",
        sheets_id="sheet-id",
    )


def test_validate_runtime_requirements_reports_missing_active_config():
    with pytest.raises(RuntimeValidationError, match="active_client, active_project"):
        validate_runtime_requirements(DummyConfig())


def test_validate_runtime_requirements_reports_missing_required_providers():
    cfg = DummyConfig()
    cfg.active_client = ClientConfig(client_id="c1", name="c1")
    cfg.active_project = make_project()

    with pytest.raises(RuntimeValidationError) as exc:
        validate_runtime_requirements(cfg)

    message = str(exc.value)
    assert "SEMRUSH_TOKEN" in message
    assert "credentials for project.runtime.providers.serp.provider_order" in message
    assert "OPENAI_API_KEY" in message


def test_validate_runtime_requirements_returns_capabilities():
    cfg = DummyConfig()
    cfg.active_client = ClientConfig(
        client_id="c1",
        name="c1",
        semrush_token="semrush",
        serpapi_key="serp",
        openai_key="openai",
        gsc_sa_path="gsc.json",
        sheets_sa_path="sheets.json",
    )
    cfg.active_project = make_project()

    requirements = validate_runtime_requirements(cfg)

    assert requirements.has_serpapi is True
    assert requirements.has_dataforseo is False
    assert requirements.can_run_gsc is True
    assert requirements.can_upload_sheets is True

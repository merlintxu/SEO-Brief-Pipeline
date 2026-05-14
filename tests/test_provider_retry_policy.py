import requests

from seo_pipeline.vendors.retry_policy import classify_provider_error, should_retry_provider_error


def _http_error(status_code: int) -> requests.exceptions.HTTPError:
    response = requests.Response()
    response.status_code = status_code
    error = requests.exceptions.HTTPError(f"{status_code} response")
    error.response = response
    return error


def test_provider_retry_policy_retries_transient_failures():
    assert should_retry_provider_error(requests.exceptions.Timeout("timeout"), provider="serpapi") is True
    assert should_retry_provider_error(requests.exceptions.ConnectionError("network"), provider="semrush") is True
    assert should_retry_provider_error(_http_error(429), provider="serpapi") is True
    assert should_retry_provider_error(_http_error(503), provider="dataforseo") is True
    assert classify_provider_error(_http_error(503)) == "provider_unavailable"


def test_provider_retry_policy_does_not_retry_terminal_failures():
    assert should_retry_provider_error(_http_error(401), provider="serpapi") is False
    assert should_retry_provider_error(RuntimeError("invalid api key"), provider="semrush") is False
    assert should_retry_provider_error(ValueError("bad input"), provider="serpapi") is False

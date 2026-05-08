import requests
from pydantic import ValidationError

from seo_pipeline.models import SemrushKeyword
from seo_pipeline.utils.errors import classify_error


def test_classify_error_auth():
    assert classify_error(PermissionError("forbidden")) == "auth"


def test_classify_error_quota():
    assert classify_error(RuntimeError("insufficient_quota")) == "quota"


def test_classify_error_rate_limit():
    assert classify_error(RuntimeError("rate limit exceeded")) == "rate_limit"


def test_classify_error_timeout():
    assert classify_error(requests.exceptions.Timeout("timed out")) == "timeout"


def test_classify_error_network():
    assert classify_error(requests.exceptions.ConnectionError("network down")) == "network"


def test_classify_error_validation():
    try:
        SemrushKeyword(keyword="", search_volume=10)
    except ValidationError as exc:
        assert classify_error(exc) == "validation"


def test_classify_error_unknown():
    assert classify_error(RuntimeError("unexpected failure")) == "unknown"

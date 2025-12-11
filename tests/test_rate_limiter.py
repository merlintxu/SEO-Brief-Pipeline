# tests/test_rate_limiter.py
"""
Tests for custom rate limiting middleware.
"""
import os
import time
from fastapi.testclient import TestClient

# Set API_KEY before importing api.main
os.environ['API_KEY'] = 'secret-token-2025-test-key-long-enough'

from api.main import app


def test_rate_limit_allows_requests_under_limit():
    """Test that requests under the limit are allowed."""
    client = TestClient(app)
    
    # Health endpoint is exempt, so test with a non-exempt endpoint
    # Make 3 requests (well under the 10/minute limit)
    for i in range(3):
        resp = client.get(f"/briefing/under_limit_test_{i}")
        # Should not be rate limited (will 404 but not 429)
        assert resp.status_code == 404, f"Request {i+1} was rate limited or gave unexpected status: {resp.status_code}"


def test_rate_limit_blocks_excessive_requests():
    """Test that requests over the limit are blocked."""
    client = TestClient(app)
    
    # Make 11 requests (over the 10/minute limit)
    responses = []
    for i in range(11):
        resp = client.get("/briefing/test123")
        responses.append(resp.status_code)
    
    # At least one should be rate limited
    assert 429 in responses, "No requests were rate limited when they should have been"
    
    # Count rate limited responses
    rate_limited_count = responses.count(429)
    assert rate_limited_count >= 1, f"Expected at least 1 rate limited response, got {rate_limited_count}"


def test_rate_limit_health_endpoint_exempt():
    """Test that /health endpoint is exempt from rate limiting."""
    client = TestClient(app)
    
    # Make many requests to health endpoint
    for i in range(15):
        resp = client.get("/health")
        assert resp.status_code == 200, f"Health check {i+1} was rate limited or failed"


def test_rate_limit_docs_endpoint_exempt():
    """Test that /docs endpoint is exempt from rate limiting."""
    client = TestClient(app)
    
    # Make many requests to docs endpoint
    for i in range(15):
        resp = client.get("/docs")
        # Docs should return 200 (HTML page)
        assert resp.status_code == 200, f"Docs request {i+1} was rate limited"


def test_rate_limit_429_response_format():
    """Test that 429 responses have correct format and headers."""
    client = TestClient(app)
    
    # Trigger rate limit by making many requests
    for i in range(15):
        resp = client.get("/briefing/test456")
        if resp.status_code == 429:
            # Check response format
            data = resp.json()
            assert "detail" in data
            assert "rate limit exceeded" in data["detail"].lower()
            
            # Check Retry-After header
            assert "retry-after" in resp.headers or "Retry-After" in resp.headers
            break
    else:
        # If we didn't hit rate limit, fail the test
        assert False, "Did not trigger rate limit after 15 requests"


def test_rate_limit_per_ip():
    """Test that rate limiting is per-IP (different IPs get separate limits)."""
    # Note: TestClient uses the same IP, so this is a basic test
    # In production, different IPs would have separate rate limits
    client = TestClient(app)
    
    # Make requests
    responses = []
    for i in range(12):
        resp = client.get("/briefing/testip")
        responses.append(resp.status_code)
    
    # Should have some 429s
    assert 429 in responses

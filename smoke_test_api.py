#!/usr/bin/env python3
"""
Smoke test for the API endpoints.
Creates mock output files and verifies API can retrieve them.
"""
import json
from pathlib import Path
from datetime import datetime
import requests
import time

API_URL = "http://127.0.0.1:8000"
API_KEY = "T3OsM3Tv2_BVSEELDh-vTrVXwrA404mjemWwGZ8PXys"
HEADERS = {"X-API-Key": API_KEY}

def create_mock_run():
    """Create mock output files for testing"""
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = Path("outputs") / run_id
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Create status file
    status = {
        "status": "done",
        "step": "completed",
        "message": "Pipeline completado",
        "run_id": run_id
    }
    (output_dir / "status.json").write_text(json.dumps(status, indent=2))
    
    # Create run_metrics file
    metrics = {
        "run_id": run_id,
        "keyword": "content marketing",
        "execution_time_seconds": 45.3,
        "stages": {
            "semrush": {"time": 5.2, "status": "success"},
            "serp": {"time": 10.1, "status": "success"},
            "audit": {"time": 25.0, "status": "success"},
            "briefing": {"time": 5.0, "status": "success"}
        },
        "provider_retries": {
            "serpapi": 0,
            "semrush": 0
        }
    }
    (output_dir / "run_metrics.json").write_text(json.dumps(metrics, indent=2))
    
    # Create briefing files for download testing
    briefing = {
        "meta_title": "Test Briefing",
        "meta_description": "Test description",
        "h1": "Test H1",
        "tone_style": "expert",
        "unique_angle": "Test angle",
        "headings": [{"title": f"Section {i}", "content": f"Content {i}"} for i in range(1, 4)]
    }
    (output_dir / "briefing.json").write_text(json.dumps(briefing, indent=2))
    
    # Create markdown file
    markdown = """# Test Briefing

## Meta Information
- **Title**: Test Briefing
- **Description**: Test description

## Content

### Section 1
Content 1

### Section 2
Content 2

### Section 3
Content 3
"""
    (output_dir / "briefing.md").write_text(markdown)
    
    return run_id, output_dir

def test_health():
    """Test GET /health"""
    print("📋 Testing GET /health...")
    resp = requests.get(f"{API_URL}/health")
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
    data = resp.json()
    assert data["status"] == "ok", "Health status is not 'ok'"
    print("✅ Health check passed\n")

def test_status_endpoint(run_id):
    """Test GET /briefing/{run_id}"""
    print(f"📋 Testing GET /briefing/{run_id}...")
    resp = requests.get(f"{API_URL}/briefing/{run_id}")
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
    data = resp.json()
    assert data["status"] == "done", f"Expected status 'done', got {data['status']}"
    assert data["step"] == "completed", f"Expected step 'completed', got {data['step']}"
    print("✅ Status endpoint passed\n")

def test_download_json(run_id):
    """Test GET /outputs/{run_id}/briefing.json"""
    print(f"📋 Testing GET /outputs/{run_id}/briefing.json...")
    resp = requests.get(f"{API_URL}/outputs/{run_id}/briefing.json")
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
    data = resp.json()
    assert data["meta_title"] == "Test Briefing", "Briefing title mismatch"
    print("✅ JSON download passed\n")

def test_download_markdown(run_id):
    """Test GET /outputs/{run_id}/briefing.md"""
    print(f"📋 Testing GET /outputs/{run_id}/briefing.md...")
    resp = requests.get(f"{API_URL}/outputs/{run_id}/briefing.md")
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
    content = resp.text
    assert "Test Briefing" in content, "Markdown content mismatch"
    print("✅ Markdown download passed\n")

def test_download_metrics(run_id):
    """Test GET /outputs/{run_id}/run_metrics.json"""
    print(f"📋 Testing GET /outputs/{run_id}/run_metrics.json...")
    resp = requests.get(f"{API_URL}/outputs/{run_id}/run_metrics.json")
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
    data = resp.json()
    assert "execution_time_seconds" in data, "Metrics missing execution_time_seconds"
    assert "stages" in data, "Metrics missing stages"
    print("✅ Metrics download passed\n")

def test_unauthorized_briefing():
    """Test POST /briefing without API key"""
    print("📋 Testing POST /briefing without API key...")
    resp = requests.post(
        f"{API_URL}/briefing",
        json={"keyword": "test", "target_url": "https://example.com"},
        headers={"Content-Type": "application/json"}
    )
    assert resp.status_code == 403, f"Expected 403, got {resp.status_code}"
    print("✅ Unauthorized briefing test passed\n")

def test_invalid_download():
    """Test forbidden filename protection"""
    print("📋 Testing forbidden filename protection...")
    resp = requests.get(f"{API_URL}/outputs/test_run/.env")
    assert resp.status_code == 403, f"Expected 403, got {resp.status_code}: {resp.text}"
    print("✅ Forbidden filename test passed\n")

def main():
    print("=" * 70)
    print("🚀 SEO Pipeline API Smoke Test")
    print("=" * 70)
    print()
    
    try:
        # Create mock run
        print("Creating mock output files...")
        run_id, output_dir = create_mock_run()
        print(f"✅ Created mock run: {run_id}")
        print(f"   Directory: {output_dir}\n")
        
        # Give server a moment
        time.sleep(1)
        
        # Run tests
        test_health()
        test_status_endpoint(run_id)
        test_download_json(run_id)
        test_download_markdown(run_id)
        test_download_metrics(run_id)
        test_unauthorized_briefing()
        test_invalid_download()
        
        print("=" * 70)
        print("✅ ALL SMOKE TESTS PASSED")
        print("=" * 70)
        print()
        print("Summary:")
        print("  ✓ Health check works")
        print("  ✓ Status polling works")
        print("  ✓ JSON download works")
        print("  ✓ Markdown download works")
        print("  ✓ Metrics download works")
        print("  ✓ API authentication enforced")
        print("  ✓ Forbidden filenames blocked")
        print()
        
    except AssertionError as e:
        print(f"\n❌ Test failed: {e}")
        return 1
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0

if __name__ == "__main__":
    import sys
    sys.exit(main())

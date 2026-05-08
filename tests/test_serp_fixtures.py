"""
Test fixtures for SerpAPI and DataForSEO SERP normalization.
Validates that both providers produce consistent SerpSnapshot contracts.
"""
import pytest
from seo_pipeline.models import SerpSnapshot
from seo_pipeline.vendors.serp_io import (
    normalize_serp_snapshot,
    extract_competitor_domains,
    extract_top_urls,
)


# ============================================================================
# SERPAPI FIXTURES
# ============================================================================

@pytest.fixture
def serpapi_response_with_ai_overview():
    """Realistic SerpAPI response with AI Overview and people also ask."""
    return {
        "search_parameters": {
            "q": "content marketing strategy 2026",
            "gl": "es",
            "hl": "es-es",
            "num": 10,
        },
        "organic_results": [
            {
                "position": 1,
                "title": "Content Marketing Strategy - HubSpot",
                "link": "https://blog.hubspot.com/marketing/content-marketing",
                "snippet": "A comprehensive guide to content marketing...",
            },
            {
                "position": 2,
                "title": "SEO Content Strategy Guide",
                "link": "https://www.semrush.com/blog/content-strategy/",
                "snippet": "Learn how to create content that ranks...",
            },
            {
                "position": 3,
                "title": "Content Strategy Fundamentals",
                "link": "https://www.moz.com/beginners-guide-to-content-marketing/",
                "snippet": "Content marketing best practices...",
            },
        ],
        "people_also_ask": [
            {
                "question": "What is content marketing?",
                "snippet": "Content marketing is a strategic approach...",
                "link": "https://en.wikipedia.org/wiki/Content_marketing",
            },
            {
                "question": "How to create a content marketing strategy?",
                "snippet": "Start by defining your goals...",
                "link": "https://www.hubspot.com/",
            },
        ],
        "related_searches": [
            {"query": "content marketing examples"},
            {"query": "content marketing plan"},
            {"query": "content marketing ROI"},
        ],
        "ai_overview": {
            "type": "answer_box",
            "text": "Content marketing is a strategic marketing approach focused on creating and distributing valuable, relevant content to attract and retain a clearly defined audience.",
            "sources": [
                {"link": "https://blog.hubspot.com/", "source": "HubSpot Blog"},
                {"link": "https://www.semrush.com/", "source": "Semrush"},
            ]
        }
    }


@pytest.fixture
def serpapi_response_minimal():
    """Minimal SerpAPI response with only organic results."""
    return {
        "search_parameters": {
            "q": "python tutorial",
            "gl": "us",
            "hl": "en",
        },
        "organic_results": [
            {
                "position": 1,
                "title": "Learn Python",
                "link": "https://python.org/docs/",
            },
            {
                "position": 2,
                "title": "Python Tutorial",
                "link": "https://w3schools.com/python/",
            },
        ],
    }


def test_normalize_serpapi_response_with_ai_overview(serpapi_response_with_ai_overview):
    """SerpAPI response normalizes correctly with AI Overview."""
    snapshot = normalize_serp_snapshot(serpapi_response_with_ai_overview, provider="serpapi")

    assert snapshot.provider == "serpapi"
    assert snapshot.query == "content marketing strategy 2026"
    assert snapshot.gl == "es"
    assert snapshot.hl == "es-es"
    assert snapshot.organic_results_count == 3
    assert snapshot.people_also_ask_count == 2
    assert snapshot.related_searches_count == 3
    assert snapshot.ai_overview_present is True
    assert len(snapshot.top_urls) >= 3
    assert "https://blog.hubspot.com/marketing/content-marketing" in snapshot.top_urls


def test_normalize_serpapi_response_minimal(serpapi_response_minimal):
    """SerpAPI response with minimal fields."""
    snapshot = normalize_serp_snapshot(serpapi_response_minimal, provider="serpapi")

    assert snapshot.provider == "serpapi"
    assert snapshot.query == "python tutorial"
    assert snapshot.organic_results_count == 2
    assert snapshot.people_also_ask_count == 0
    assert snapshot.related_searches_count == 0
    assert snapshot.ai_overview_present is False
    assert snapshot.top_urls == [
        "https://python.org/docs/",
        "https://w3schools.com/python/",
    ]


def test_serpapi_extract_competitor_domains(serpapi_response_with_ai_overview):
    """Extract competitor domains from SerpAPI response."""
    domains = extract_competitor_domains(
        serpapi_response_with_ai_overview,
        exclude_domain="https://en.wikipedia.org",
        max_domains=5
    )

    assert len(domains) > 0
    assert "blog.hubspot.com" in domains or "hubspot.com" in domains
    assert "en.wikipedia.org" not in domains


# ============================================================================
# DATAFORSEO FIXTURES
# ============================================================================

@pytest.fixture
def dataforseo_response_with_snippets():
    """Realistic DataForSEO response converted to SerpAPI-like format."""
    return {
        "search_parameters": {
            "q": "machine learning basics",
            "gl": "us",
            "hl": "en",
        },
        "organic_results": [
            {
                "position": 1,
                "title": "What is Machine Learning?",
                "link": "https://www.ibm.com/cloud/learn/machine-learning",
                "snippet": "Machine learning is a branch of artificial intelligence...",
                "rank_group": 1,
            },
            {
                "position": 2,
                "title": "Introduction to Machine Learning",
                "link": "https://www.coursera.org/learn/machine-learning",
                "snippet": "Learn Machine Learning from Stanford University...",
                "rank_group": 2,
            },
            {
                "position": 3,
                "title": "Machine Learning Basics",
                "link": "https://www.tensorflow.org/tutorials",
                "snippet": "TensorFlow is an end-to-end open source platform...",
                "rank_group": 3,
            },
        ],
        "people_also_ask": [
            {
                "question": "Is machine learning the same as AI?",
                "snippet": "No, machine learning is a subset of AI...",
                "link": "https://www.ibm.com/cloud/learn/ai",
            },
        ],
        "related_searches": [
            {"query": "machine learning algorithms"},
            {"query": "machine learning examples"},
        ],
    }


@pytest.fixture
def dataforseo_response_no_paa():
    """DataForSEO response without people_also_ask."""
    return {
        "search_parameters": {
            "q": "web development",
            "gl": "uk",
            "hl": "en-gb",
        },
        "organic_results": [
            {
                "position": 1,
                "title": "Web Development",
                "link": "https://mdn.mozilla.org/en-US/docs/Learn/Getting_started_with_the_web",
            },
            {
                "position": 2,
                "title": "Learn Web Development",
                "link": "https://www.freecodecamp.org/learn/responsive-web-design/",
            },
        ],
    }


def test_normalize_dataforseo_response_with_snippets(dataforseo_response_with_snippets):
    """DataForSEO response normalizes correctly."""
    snapshot = normalize_serp_snapshot(dataforseo_response_with_snippets, provider="dataforseo")

    assert snapshot.provider == "dataforseo"
    assert snapshot.query == "machine learning basics"
    assert snapshot.gl == "us"
    assert snapshot.hl == "en"
    assert snapshot.organic_results_count == 3
    assert snapshot.people_also_ask_count == 1
    assert snapshot.related_searches_count == 2
    assert snapshot.ai_overview_present is False
    assert len(snapshot.top_urls) == 3


def test_normalize_dataforseo_response_no_paa(dataforseo_response_no_paa):
    """DataForSEO response without optional fields."""
    snapshot = normalize_serp_snapshot(dataforseo_response_no_paa, provider="dataforseo")

    assert snapshot.provider == "dataforseo"
    assert snapshot.query == "web development"
    assert snapshot.gl == "uk"
    assert snapshot.hl == "en-gb"
    assert snapshot.organic_results_count == 2
    assert snapshot.people_also_ask_count == 0
    assert snapshot.related_searches_count == 0
    assert snapshot.top_urls == [
        "https://mdn.mozilla.org/en-US/docs/Learn/Getting_started_with_the_web",
        "https://www.freecodecamp.org/learn/responsive-web-design/",
    ]


def test_dataforseo_extract_competitor_domains(dataforseo_response_with_snippets):
    """Extract competitor domains from DataForSEO response."""
    domains = extract_competitor_domains(
        dataforseo_response_with_snippets,
        exclude_domain="https://www.coursera.org",
        max_domains=3
    )

    assert len(domains) <= 3
    assert "coursera.org" not in domains


# ============================================================================
# PROVIDER CONSISTENCY TESTS
# ============================================================================

def test_both_providers_normalize_to_same_snapshot_structure(
    serpapi_response_with_ai_overview,
    dataforseo_response_with_snippets
):
    """Both providers produce consistent SerpSnapshot fields."""
    serp_snapshot = normalize_serp_snapshot(
        serpapi_response_with_ai_overview,
        provider="serpapi"
    )
    dfso_snapshot = normalize_serp_snapshot(
        dataforseo_response_with_snippets,
        provider="dataforseo"
    )

    # Both should have the same fields
    assert isinstance(serp_snapshot, SerpSnapshot)
    assert isinstance(dfso_snapshot, SerpSnapshot)

    # All required fields present
    for field in ["provider", "query", "gl", "hl", "organic_results_count", "top_urls"]:
        assert hasattr(serp_snapshot, field)
        assert hasattr(dfso_snapshot, field)


def test_extract_top_urls_preserves_order(serpapi_response_with_ai_overview):
    """Top URLs are extracted in order without duplicates."""
    urls = extract_top_urls(serpapi_response_with_ai_overview, max_urls=12, include_ai_citations=True)

    # No duplicates
    assert len(urls) == len(set(urls))

    # Order preserved from organic results first, then AI citations
    expected_first = "https://blog.hubspot.com/marketing/content-marketing"
    assert urls[0] == expected_first


def test_extract_top_urls_respects_max_limit():
    """max_urls parameter is respected."""
    response = {
        "organic_results": [
            {"link": f"https://example{i}.com/page"} for i in range(20)
        ]
    }
    urls = extract_top_urls(response, max_urls=5)
    assert len(urls) == 5

    urls = extract_top_urls(response, max_urls=15)
    assert len(urls) == 15


def test_normalize_serp_snapshot_handles_empty_response():
    """Empty SERP response normalizes gracefully."""
    empty_response = {}
    snapshot = normalize_serp_snapshot(empty_response, provider="unknown")

    assert snapshot.provider == "unknown"
    assert snapshot.query == ""
    assert snapshot.organic_results_count == 0
    assert snapshot.people_also_ask_count == 0
    assert snapshot.related_searches_count == 0
    assert snapshot.ai_overview_present is False
    assert snapshot.top_urls == []

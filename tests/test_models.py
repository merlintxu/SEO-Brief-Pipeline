"""
Unit tests for Pydantic models - validation and constraints.
Tests ensure that all models enforce their constraints correctly.
"""
import pytest
from pydantic import ValidationError

from seo_pipeline.models import (
    SheetRow24,
    AuditEntry,
    AnchorSet,
    SemrushKeyword,
    SemrushResults,
)


# ============================================================================
# SemrushKeyword Tests
# ============================================================================

def test_semrush_keyword_valid():
    """Valid keyword created successfully."""
    kw = SemrushKeyword(keyword="best practices", search_volume=1200)
    assert kw.keyword == "best practices"
    assert kw.search_volume == 1200


def test_semrush_keyword_sv_non_negative():
    """Search volume cannot be negative."""
    with pytest.raises(ValidationError) as exc_info:
        SemrushKeyword(keyword="test", search_volume=-100)
    assert "greater than or equal to 0" in str(exc_info.value)


def test_semrush_keyword_sv_max():
    """Search volume has reasonable max (999M)."""
    with pytest.raises(ValidationError):
        SemrushKeyword(keyword="test", search_volume=1000000000)


def test_semrush_keyword_requires_keyword():
    """Keyword field is required."""
    with pytest.raises(ValidationError):
        SemrushKeyword(search_volume=100)


def test_semrush_keyword_max_length():
    """Keyword cannot exceed 100 characters."""
    long_kw = "a" * 101
    with pytest.raises(ValidationError) as exc_info:
        SemrushKeyword(keyword=long_kw)
    assert "String should have at most 100 characters" in str(exc_info.value)


# ============================================================================
# SemrushResults Tests
# ============================================================================

def test_semrush_results_valid():
    """Valid results created successfully."""
    principal = SemrushKeyword(keyword="main", search_volume=5000)
    secondary = [
        SemrushKeyword(keyword="related 1", search_volume=1000),
        SemrushKeyword(keyword="related 2", search_volume=800),
    ]
    results = SemrushResults(keyword_principal=principal, keywords_secundarias=secondary)
    assert results.keyword_principal.keyword == "main"
    assert len(results.keywords_secundarias) == 2


def test_semrush_results_max_secundarias():
    """Maximum 100 secondary keywords allowed."""
    principal = SemrushKeyword(keyword="main", search_volume=5000)
    too_many = [
        SemrushKeyword(keyword=f"kw {i}", search_volume=10)
        for i in range(101)
    ]
    with pytest.raises(ValidationError):
        SemrushResults(keyword_principal=principal, keywords_secundarias=too_many)


# ============================================================================
# AuditEntry Tests
# ============================================================================

def test_audit_entry_valid():
    """Valid audit entry created successfully."""
    entry = AuditEntry(
        url="https://example.com/page",
        status_code=200,
        title="Page Title",
        word_count=1500
    )
    assert entry.url == "https://example.com/page"
    assert entry.status_code == 200
    assert entry.word_count == 1500


def test_audit_entry_requires_url():
    """URL is required."""
    with pytest.raises(ValidationError):
        AuditEntry()


def test_audit_entry_url_cannot_be_empty():
    """URL cannot be empty or whitespace-only."""
    with pytest.raises(ValidationError) as exc_info:
        AuditEntry(url="   ")
    assert "URL cannot be empty" in str(exc_info.value)


def test_audit_entry_url_max_length():
    """URL cannot exceed 2048 characters."""
    long_url = "https://example.com/" + "a" * 2030
    with pytest.raises(ValidationError):
        AuditEntry(url=long_url)


def test_audit_entry_status_code_valid_range():
    """Status code must be 0-599."""
    # Valid
    entry = AuditEntry(url="https://example.com", status_code=404)
    assert entry.status_code == 404

    # Invalid - too high
    with pytest.raises(ValidationError):
        AuditEntry(url="https://example.com", status_code=600)

    # Invalid - negative
    with pytest.raises(ValidationError):
        AuditEntry(url="https://example.com", status_code=-1)


def test_audit_entry_word_count_non_negative():
    """Word count cannot be negative."""
    with pytest.raises(ValidationError):
        AuditEntry(url="https://example.com", word_count=-5)


def test_audit_entry_word_count_max():
    """Word count has reasonable max (50k)."""
    with pytest.raises(ValidationError):
        AuditEntry(url="https://example.com", word_count=50001)


def test_audit_entry_title_max_length():
    """Title cannot exceed 100 characters."""
    long_title = "a" * 101
    with pytest.raises(ValidationError):
        AuditEntry(url="https://example.com", title=long_title)


def test_audit_entry_url_whitespace_stripped():
    """URL whitespace should be stripped."""
    entry = AuditEntry(url="  https://example.com  ")
    assert entry.url == "https://example.com"


# ============================================================================
# AnchorSet Tests
# ============================================================================

def test_anchor_set_valid():
    """Valid anchor set created successfully."""
    anchors = AnchorSet(
        primary=["best practices", "guidelines"],
        secondary=["tips", "strategies"],
        internal=["learn more"]
    )
    assert len(anchors.primary) == 2
    assert len(anchors.secondary) == 2
    assert len(anchors.internal) == 1


def test_anchor_set_empty_defaults():
    """Empty anchor set is valid."""
    anchors = AnchorSet()
    assert len(anchors.primary) == 0
    assert len(anchors.secondary) == 0
    assert len(anchors.internal) == 0


def test_anchor_set_primary_max():
    """Primary anchors max length enforced (5)."""
    too_many = [f"anchor {i}" for i in range(6)]
    with pytest.raises(ValidationError):
        AnchorSet(primary=too_many)


def test_anchor_set_secondary_max():
    """Secondary anchors max length enforced (8)."""
    too_many = [f"anchor {i}" for i in range(9)]
    with pytest.raises(ValidationError):
        AnchorSet(secondary=too_many)


def test_anchor_set_internal_max():
    """Internal anchors max length enforced (12)."""
    too_many = [f"anchor {i}" for i in range(13)]
    with pytest.raises(ValidationError):
        AnchorSet(internal=too_many)


# ============================================================================
# SheetRow24 Tests
# ============================================================================

def test_sheetrow24_valid():
    """Valid row created successfully."""
    row = SheetRow24(
        kw_principal="best practices",
        sv_principal=1500,
        title="Best Practices Guide",
        paa_count=5
    )
    assert row.kw_principal == "best practices"
    assert row.sv_principal == 1500
    assert row.paa_count == 5


def test_sheetrow24_requires_keyword():
    """Keyword is required."""
    with pytest.raises(ValidationError):
        SheetRow24()


def test_sheetrow24_keyword_cannot_be_empty():
    """Keyword cannot be empty or whitespace-only."""
    with pytest.raises(ValidationError) as exc_info:
        SheetRow24(kw_principal="   ")
    assert "empty or whitespace" in str(exc_info.value)


def test_sheetrow24_keyword_max_length():
    """Keyword cannot exceed 100 characters."""
    long_kw = "a" * 101
    with pytest.raises(ValidationError):
        SheetRow24(kw_principal=long_kw)


def test_sheetrow24_sv_non_negative():
    """Search volume cannot be negative."""
    with pytest.raises(ValidationError):
        SheetRow24(kw_principal="test", sv_principal=-1)


def test_sheetrow24_sv_max():
    """Search volume has reasonable max."""
    with pytest.raises(ValidationError):
        SheetRow24(kw_principal="test", sv_principal=10000000)


def test_sheetrow24_paa_count_non_negative():
    """PAA count cannot be negative."""
    with pytest.raises(ValidationError):
        SheetRow24(kw_principal="test", paa_count=-1)


def test_sheetrow24_paa_count_max():
    """PAA count has reasonable max (100)."""
    with pytest.raises(ValidationError):
        SheetRow24(kw_principal="test", paa_count=101)


def test_sheetrow24_related_count_max():
    """Related count has reasonable max (1000)."""
    with pytest.raises(ValidationError):
        SheetRow24(kw_principal="test", related_count=1001)


def test_sheetrow24_keywords_list_validation():
    """Secondary keywords list is validated."""
    # Valid
    row = SheetRow24(
        kw_principal="main",
        kw_secundarias=["keyword 1", "keyword 2"]
    )
    assert len(row.kw_secundarias) == 2

    # Invalid - empty keyword in list
    with pytest.raises(ValidationError) as exc_info:
        SheetRow24(
            kw_principal="main",
            kw_secundarias=["valid", ""]
        )
    assert "cannot be empty" in str(exc_info.value)

    # Invalid - keyword too long
    long_kw = "a" * 101
    with pytest.raises(ValidationError) as exc_info:
        SheetRow24(
            kw_principal="main",
            kw_secundarias=[long_kw]
        )
    assert "too long" in str(exc_info.value)


def test_sheetrow24_keywords_list_max_length():
    """Secondary keywords list has max length (20)."""
    too_many = [f"kw {i}" for i in range(21)]
    with pytest.raises(ValidationError):
        SheetRow24(kw_principal="main", kw_secundarias=too_many)


def test_sheetrow24_keyword_whitespace_stripped():
    """Keyword whitespace should be stripped."""
    row = SheetRow24(kw_principal="  best practices  ")
    assert row.kw_principal == "best practices"


def test_sheetrow24_secondary_keywords_stripped():
    """Secondary keywords should be stripped."""
    row = SheetRow24(
        kw_principal="main",
        kw_secundarias=["  keyword 1  ", "  keyword 2  "]
    )
    assert row.kw_secundarias == ["keyword 1", "keyword 2"]


def test_sheetrow24_title_max_length():
    """Title cannot exceed 100 characters."""
    long_title = "a" * 101
    with pytest.raises(ValidationError):
        SheetRow24(kw_principal="test", title=long_title)


def test_sheetrow24_notes_max_length():
    """Notes cannot exceed 1000 characters."""
    long_notes = "a" * 1001
    with pytest.raises(ValidationError):
        SheetRow24(kw_principal="test", notes=long_notes)


def test_sheetrow24_to_row_conversion():
    """to_row() method converts model to list correctly."""
    row = SheetRow24(
        kw_principal="test",
        sv_principal=100,
        anchor_primary=["anchor 1", "anchor 2"],
        kw_secundarias=["secondary 1"]
    )
    result = row.to_row()
    assert isinstance(result, list)
    assert len(result) > 0
    # First column should be the primary keyword
    assert "test" in result


# ============================================================================
# Integration Tests
# ============================================================================

def test_audit_entry_with_schema_signals():
    """Audit entry can include schema signals."""
    entry = AuditEntry(
        url="https://example.com",
        status_code=200,
        schema_signals={
            "has_article": True,
            "has_product": False,
            "schema_types": ["NewsArticle", "BlogPosting"]
        }
    )
    assert entry.schema_signals.has_article is True
    assert "NewsArticle" in entry.schema_signals.schema_types


def test_anchor_set_realistic_scenario():
    """Realistic anchor set with multiple types."""
    anchors = AnchorSet(
        primary=[
            "best practices for SEO",
            "complete SEO guide"
        ],
        secondary=[
            "SEO tips",
            "search engine optimization",
            "on-page SEO",
            "technical SEO"
        ],
        internal=[
            "read our SEO resources",
            "learn SEO basics",
            "SEO checklist",
            "SEO tools"
        ]
    )
    assert len(anchors.primary) == 2
    assert len(anchors.secondary) == 4
    assert len(anchors.internal) == 4


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

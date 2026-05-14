from pathlib import Path

import pytest

from seo_pipeline.cache_admin import clear_cache, inspect_cache


def test_inspect_cache_reports_size_and_oldest_newest(tmp_path: Path):
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    first = cache_dir / "semrush.csv"
    second = cache_dir / "nested" / "dataforseo.json"
    second.parent.mkdir()
    first.write_text("abc", encoding="utf-8")
    second.write_text("12345", encoding="utf-8")

    summary = inspect_cache(cache_dir)

    assert summary.file_count == 2
    assert summary.total_size_bytes == 8
    assert summary.oldest_modified_at is not None
    assert summary.newest_modified_at is not None
    assert {Path(item.path).name for item in summary.files} == {"semrush.csv", "dataforseo.json"}


def test_clear_cache_removes_files_but_keeps_root(tmp_path: Path):
    cache_dir = tmp_path / "cache"
    nested = cache_dir / "nested"
    nested.mkdir(parents=True)
    (nested / "cached.json").write_text("{}", encoding="utf-8")

    before = clear_cache(cache_dir)

    assert before.file_count == 1
    assert cache_dir.exists()
    assert list(cache_dir.rglob("*")) == []


def test_inspect_cache_rejects_invalid_limit(tmp_path: Path):
    with pytest.raises(ValueError, match="limit"):
        inspect_cache(tmp_path / "cache", limit=0)

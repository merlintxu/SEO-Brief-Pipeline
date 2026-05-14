"""Safe provider cache inspection and cleanup helpers."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class CacheFileInfo:
    path: str
    size_bytes: int
    modified_at: str


@dataclass(frozen=True)
class CacheSummary:
    root: str
    file_count: int
    total_size_bytes: int
    oldest_modified_at: str | None
    newest_modified_at: str | None
    files: list[CacheFileInfo]


def inspect_cache(cache_dir: Path, *, limit: int = 50) -> CacheSummary:
    if limit < 1:
        raise ValueError("limit must be >= 1")
    root = _resolve_cache_root(cache_dir)
    files = [path for path in root.rglob("*") if path.is_file()]
    entries = [_file_info(path) for path in sorted(files, key=lambda item: item.stat().st_mtime)]
    total_size = sum(item.size_bytes for item in entries)
    return CacheSummary(
        root=str(root),
        file_count=len(entries),
        total_size_bytes=total_size,
        oldest_modified_at=entries[0].modified_at if entries else None,
        newest_modified_at=entries[-1].modified_at if entries else None,
        files=entries[:limit],
    )


def clear_cache(cache_dir: Path) -> CacheSummary:
    root = _resolve_cache_root(cache_dir)
    before = inspect_cache(root, limit=10_000)
    for path in sorted(root.rglob("*"), reverse=True):
        resolved = path.resolve()
        if not _is_relative_to(resolved, root):
            raise RuntimeError(f"Refusing to delete outside cache root: {resolved}")
        if path.is_file():
            path.unlink()
        elif path.is_dir() and path != root:
            try:
                path.rmdir()
            except OSError:
                pass
    return before


def _resolve_cache_root(cache_dir: Path) -> Path:
    root = Path(cache_dir).resolve()
    root.mkdir(parents=True, exist_ok=True)
    if root.anchor == str(root):
        raise RuntimeError("Refusing to use filesystem root as cache directory")
    return root


def _file_info(path: Path) -> CacheFileInfo:
    stat = path.stat()
    return CacheFileInfo(
        path=str(path),
        size_bytes=stat.st_size,
        modified_at=_format_timestamp(stat.st_mtime),
    )


def _format_timestamp(epoch_seconds: float) -> str:
    from datetime import datetime

    return datetime.fromtimestamp(epoch_seconds).isoformat(timespec="seconds")


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False

"""Batch keyword runner with isolated per-keyword runs."""
from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from seo_pipeline.input_validation import PipelineInput
from seo_pipeline.pipeline import run_full_pipeline
from seo_pipeline.utils.io import save_json


@dataclass(frozen=True)
class BatchItem:
    keyword: str
    target_url: str | None = None
    upload_to_sheets: bool = False
    related_limit: int = 30
    serp_num: int = 10
    top_competitors_count: int = 3
    gsc_months_back: int = 11


def load_batch_items(path: Path) -> list[BatchItem]:
    source = Path(path)
    if source.suffix.lower() == ".csv":
        return _load_csv(source)
    if source.suffix.lower() == ".json":
        return _load_json(source)
    raise ValueError("Batch input must be a .csv or .json file")


def run_batch(
    items: list[BatchItem],
    *,
    batch_id: str | None = None,
    output_dir: Path | None = None,
    stop_on_error: bool = False,
    resume: bool = False,
    pipeline_func: Callable[..., dict] = run_full_pipeline,
) -> dict[str, Any]:
    batch_id = batch_id or datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    batch_output_dir = Path(output_dir or Path("runs") / f"batch_{batch_id}")
    batch_output_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = batch_output_dir / "batch_manifest.json"
    previous_items = _manifest_items_by_run_id(manifest_path) if resume else {}

    results: list[dict[str, Any]] = []
    for index, item in enumerate(items, start=1):
        run_id = f"{batch_id}_{index:03d}"
        run_dir = batch_output_dir / run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        status_path = run_dir / "status.json"
        previous = previous_items.get(run_id)
        if resume and previous and previous.get("status") == "done":
            results.append(
                {
                    "run_id": run_id,
                    "keyword": previous.get("keyword", item.keyword),
                    "status": "skipped",
                    "output_dir": str(run_dir),
                    "result_output_dir": previous.get("result_output_dir", str(run_dir)),
                    "started_at": None,
                    "finished_at": previous.get("finished_at"),
                    "error_summary": None,
                    "resume_reason": "previously_done",
                }
            )
            _write_batch_manifest(manifest_path, batch_id, batch_output_dir, results)
            continue

        started_at = datetime.now().isoformat(timespec="seconds")
        try:
            validated = PipelineInput(
                keyword=item.keyword,
                target_url=item.target_url,
                related_limit=item.related_limit,
                serp_num=item.serp_num,
                top_competitors_count=item.top_competitors_count,
                gsc_months_back=item.gsc_months_back,
            )
            result = pipeline_func(
                keyword=validated.keyword,
                target_url=str(validated.target_url) if validated.target_url else None,
                run_id=run_id,
                related_limit=validated.related_limit,
                serp_num=validated.serp_num,
                top_competitors_count=validated.top_competitors_count,
                upload_to_sheets=item.upload_to_sheets,
                status_path=status_path,
                output_dir=run_dir,
                gsc_months_back=validated.gsc_months_back,
            )
            results.append(
                {
                    "run_id": run_id,
                    "keyword": validated.keyword,
                    "status": "done",
                    "output_dir": str(run_dir),
                    "result_output_dir": str(result.get("output_dir", run_dir)),
                    "started_at": started_at,
                    "finished_at": datetime.now().isoformat(timespec="seconds"),
                    "error_summary": None,
                }
            )
        except Exception as exc:
            failure = {
                "run_id": run_id,
                "keyword": item.keyword,
                "status": "failed",
                "output_dir": str(run_dir),
                "error": str(exc),
                "started_at": started_at,
                "finished_at": datetime.now().isoformat(timespec="seconds"),
                "error_summary": str(exc),
            }
            results.append(failure)
            save_json(status_path, {"status": "failed", "step": "batch", "message": str(exc)})
            _write_batch_manifest(manifest_path, batch_id, batch_output_dir, results)
            if stop_on_error:
                break
        else:
            _write_batch_manifest(manifest_path, batch_id, batch_output_dir, results)

    summary = {
        "batch_id": batch_id,
        "output_dir": str(batch_output_dir),
        "total": len(results),
        "done": sum(1 for item in results if item["status"] == "done"),
        "failed": sum(1 for item in results if item["status"] == "failed"),
        "skipped": sum(1 for item in results if item["status"] == "skipped"),
        "resume": resume,
        "manifest_path": str(manifest_path),
        "stopped_on_error": stop_on_error and any(item["status"] == "failed" for item in results),
        "items": results,
    }
    save_json(batch_output_dir / "batch_summary.json", summary)
    save_json(manifest_path, summary)
    return summary


def _load_csv(path: Path) -> list[BatchItem]:
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        return [_item_from_mapping(row) for row in reader]


def _load_json(path: Path) -> list[BatchItem]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, dict):
        payload = payload.get("items", [])
    if not isinstance(payload, list):
        raise ValueError("JSON batch input must be a list or an object with an items list")
    return [_item_from_mapping(item) for item in payload]


def _item_from_mapping(raw: dict[str, Any]) -> BatchItem:
    return BatchItem(
        keyword=str(raw.get("keyword", "")).strip(),
        target_url=_optional_text(raw.get("target_url")),
        upload_to_sheets=_as_bool(raw.get("upload_to_sheets", False)),
        related_limit=_as_int(raw.get("related_limit"), 30),
        serp_num=_as_int(raw.get("serp_num"), 10),
        top_competitors_count=_as_int(raw.get("top_competitors_count"), 3),
        gsc_months_back=_as_int(raw.get("gsc_months_back"), 11),
    )


def _optional_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _as_int(value: Any, default: int) -> int:
    if value in (None, ""):
        return default
    return int(value)


def _manifest_items_by_run_id(path: Path) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    items = payload.get("items", []) if isinstance(payload, dict) else []
    if not isinstance(items, list):
        return {}
    return {
        str(item["run_id"]): item
        for item in items
        if isinstance(item, dict) and item.get("run_id")
    }


def _write_batch_manifest(path: Path, batch_id: str, output_dir: Path, items: list[dict[str, Any]]) -> None:
    payload = {
        "batch_id": batch_id,
        "output_dir": str(output_dir),
        "total": len(items),
        "done": sum(1 for item in items if item["status"] == "done"),
        "failed": sum(1 for item in items if item["status"] == "failed"),
        "skipped": sum(1 for item in items if item["status"] == "skipped"),
        "items": items,
    }
    save_json(path, payload)


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "y", "s", "si", "sí"}

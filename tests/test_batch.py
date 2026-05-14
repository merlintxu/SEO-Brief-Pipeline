import json
from pathlib import Path

from seo_pipeline.batch import BatchItem, load_batch_items, run_batch


def test_load_batch_items_from_csv(tmp_path: Path):
    path = tmp_path / "batch.csv"
    path.write_text(
        "keyword,target_url,upload_to_sheets,related_limit,serp_num\n"
        "kw one,https://example.com/a,true,15,5\n",
        encoding="utf-8",
    )

    items = load_batch_items(path)

    assert len(items) == 1
    assert items[0].keyword == "kw one"
    assert items[0].target_url == "https://example.com/a"
    assert items[0].upload_to_sheets is True
    assert items[0].related_limit == 15
    assert items[0].serp_num == 5


def test_load_batch_items_from_json_object(tmp_path: Path):
    path = tmp_path / "batch.json"
    path.write_text(json.dumps({"items": [{"keyword": "kw json"}]}), encoding="utf-8")

    items = load_batch_items(path)

    assert items == [BatchItem(keyword="kw json")]


def test_run_batch_isolates_runs_and_continues_after_failure(tmp_path: Path):
    calls = []

    def fake_pipeline(**kwargs):
        calls.append(kwargs)
        if kwargs["keyword"] == "fail kw":
            raise RuntimeError("boom")
        return {"output_dir": str(kwargs["output_dir"])}

    summary = run_batch(
        [BatchItem(keyword="ok kw"), BatchItem(keyword="fail kw"), BatchItem(keyword="next kw")],
        batch_id="batch_test",
        output_dir=tmp_path / "batch",
        pipeline_func=fake_pipeline,
    )

    assert summary["total"] == 3
    assert summary["done"] == 2
    assert summary["failed"] == 1
    assert summary["skipped"] == 0
    assert [item["run_id"] for item in summary["items"]] == ["batch_test_001", "batch_test_002", "batch_test_003"]
    assert (tmp_path / "batch" / "batch_summary.json").exists()
    assert (tmp_path / "batch" / "batch_manifest.json").exists()
    assert (tmp_path / "batch" / "batch_test_002" / "status.json").exists()
    assert summary["items"][0]["started_at"]
    assert summary["items"][0]["finished_at"]
    assert summary["items"][1]["error_summary"] == "boom"
    assert len(calls) == 3


def test_run_batch_can_stop_on_first_error(tmp_path: Path):
    def fake_pipeline(**kwargs):
        raise RuntimeError("boom")

    summary = run_batch(
        [BatchItem(keyword="fail kw"), BatchItem(keyword="skipped kw")],
        batch_id="batch_stop",
        output_dir=tmp_path / "batch",
        stop_on_error=True,
        pipeline_func=fake_pipeline,
    )

    assert summary["total"] == 1
    assert summary["done"] == 0
    assert summary["failed"] == 1
    assert summary["stopped_on_error"] is True


def test_run_batch_resume_skips_previously_done_items(tmp_path: Path):
    calls = []

    def first_pipeline(**kwargs):
        calls.append(("first", kwargs["keyword"]))
        if kwargs["keyword"] == "retry kw":
            raise RuntimeError("temporary")
        return {"output_dir": str(kwargs["output_dir"])}

    output_dir = tmp_path / "batch"
    first = run_batch(
        [BatchItem(keyword="done kw"), BatchItem(keyword="retry kw")],
        batch_id="batch_resume",
        output_dir=output_dir,
        pipeline_func=first_pipeline,
    )
    assert first["done"] == 1
    assert first["failed"] == 1

    def second_pipeline(**kwargs):
        calls.append(("second", kwargs["keyword"]))
        return {"output_dir": str(kwargs["output_dir"])}

    resumed = run_batch(
        [BatchItem(keyword="done kw"), BatchItem(keyword="retry kw")],
        batch_id="batch_resume",
        output_dir=output_dir,
        resume=True,
        pipeline_func=second_pipeline,
    )

    assert resumed["resume"] is True
    assert resumed["done"] == 1
    assert resumed["failed"] == 0
    assert resumed["skipped"] == 1
    assert [item["status"] for item in resumed["items"]] == ["skipped", "done"]
    assert calls == [
        ("first", "done kw"),
        ("first", "retry kw"),
        ("second", "retry kw"),
    ]

    manifest = json.loads((output_dir / "batch_manifest.json").read_text(encoding="utf-8"))
    assert manifest["skipped"] == 1
    assert manifest["items"][0]["resume_reason"] == "previously_done"

import json
from pathlib import Path

from seo_pipeline.utils.io import save_json, load_json, save_text


def test_save_and_load_json(tmp_path: Path):
    p = tmp_path / "subdir"
    out = p / "test.json"
    data = {"a": 1, "b": [1, 2, 3]}
    saved = save_json(out, data)
    assert saved.exists()
    loaded = load_json(out)
    assert loaded == data


def test_save_text(tmp_path: Path):
    p = tmp_path / "f.txt"
    txt = "Hola mundo"
    saved = save_text(p, txt)
    assert saved.exists()
    assert p.read_text(encoding="utf-8") == txt

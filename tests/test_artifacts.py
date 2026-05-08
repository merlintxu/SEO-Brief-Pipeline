import os

from seo_pipeline.artifacts import DOWNLOADABLE_ARTIFACTS, RUN_METRICS_JSON


def test_api_allowed_files_share_artifact_contract():
    os.environ["API_KEY"] = "test-token-with-enough-length"
    import api.main as api_main

    assert api_main.ALLOWED_FILES == DOWNLOADABLE_ARTIFACTS
    assert RUN_METRICS_JSON in api_main.ALLOWED_FILES

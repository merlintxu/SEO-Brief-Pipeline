import pytest
from pydantic import ValidationError

from seo_pipeline.input_validation import PipelineInput


def test_pipeline_input_trims_keyword():
    payload = PipelineInput(keyword="  seo automation  ")
    assert payload.keyword == "seo automation"


def test_pipeline_input_rejects_invalid_limits():
    with pytest.raises(ValidationError):
        PipelineInput(keyword="kw", serp_num=0)

    with pytest.raises(ValidationError):
        PipelineInput(keyword="kw", related_limit=101)


def test_pipeline_input_rejects_invalid_url():
    with pytest.raises(ValidationError):
        PipelineInput(keyword="kw", target_url="not a url")

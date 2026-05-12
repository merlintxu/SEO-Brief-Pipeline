from seo_pipeline.prompt_registry import resolve_prompt_bundle


def test_resolve_prompt_bundle_known_version():
    bundle = resolve_prompt_bundle("brief_generator", "v1")
    assert bundle.key == "brief_generator"
    assert bundle.version == "v1"
    assert bundle.model


def test_resolve_prompt_bundle_fallback_to_v1():
    bundle = resolve_prompt_bundle("brief_generator", "v-does-not-exist")
    assert bundle.version == "v1"

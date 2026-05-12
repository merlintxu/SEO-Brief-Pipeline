from __future__ import annotations

from dataclasses import dataclass

from seo_pipeline.constants import BRIEFING_SYSTEM_PROMPT


@dataclass(frozen=True)
class PromptBundle:
    key: str
    version: str
    system_prompt: str
    model: str
    temperature: float


_PROMPT_REGISTRY: dict[str, dict[str, PromptBundle]] = {
    "brief_generator": {
        "v1": PromptBundle(
            key="brief_generator",
            version="v1",
            system_prompt=BRIEFING_SYSTEM_PROMPT,
            model="gpt-4o-2024-11-20",
            temperature=0.7,
        )
    }
}


def resolve_prompt_bundle(key: str, version: str = "v1") -> PromptBundle:
    family = _PROMPT_REGISTRY.get(key, {})
    if version in family:
        return family[version]
    if "v1" in family:
        return family["v1"]
    raise KeyError(f"Prompt key not found: {key}")

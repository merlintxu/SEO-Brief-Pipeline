# seo_pipeline/blueprint.py
"""
Generación del briefing SEO definitivo mediante OpenAI + Instructor (2025).
Utiliza structured outputs 100 % fiables (Pydantic → JSON Schema automático).
Incluye todo lo necesario para superar a la competencia actual en el SERP.
"""
from __future__ import annotations

from typing import List, Dict, Any, Optional
from pathlib import Path
import json
from openai import OpenAI, RateLimitError, OpenAIError
from pydantic import BaseModel, Field

from seo_pipeline.models import AnchorSet, BriefingPlan, SEOBriefing, SerpSnapshot
from seo_pipeline.utils.text import normalize_ws
from seo_pipeline.prompt_registry import resolve_prompt_bundle
from seo_pipeline.utils.logging import logger




def build_briefing_plan_artifact(
    *,
    keyword: str,
    serp_snapshot: SerpSnapshot,
    audit_report: Dict,
    prompt_version: str,
) -> BriefingPlan:
    required_sections = [entry.get("h1", "").strip() for entry in audit_report.get("entries", []) if entry.get("h1")]
    evidence_points = [entry.get("url", "") for entry in audit_report.get("entries", [])[:10] if entry.get("url")]
    constraints = [
        "Return strictly valid JSON for SEOBriefing schema",
        "Cover SERP intent and competitor gaps",
    ]
    if serp_snapshot.people_also_ask_count > 0:
        constraints.append("Address People Also Ask questions explicitly")
    return BriefingPlan(
        keyword=keyword,
        intent_summary=f"SERP organic={serp_snapshot.organic_results_count}, PAA={serp_snapshot.people_also_ask_count}, related={serp_snapshot.related_searches_count}",
        required_sections=required_sections[:12],
        evidence_points=evidence_points,
        constraints=constraints,
        prompt_version=prompt_version,
        planner_version="v1",
    )


def generate_briefing(
    keyword: str,
    search_volume: int,
    semrush_data: Dict,
    serp_snapshot: SerpSnapshot,
    audit_report: Dict,
    anchors: AnchorSet,
    openai_api_key: str,
    cannibalization_notes: str = "",
    model: str | None = None,
    temperature: float | None = None,
    prompt_version: str = "v1",
    planner_artifact: Dict[str, Any] | None = None,
) -> SEOBriefing:
    """
    Genera el briefing completo utilizando OpenAI structured outputs nativos.
    Garantiza 100 % parseo correcto del JSON sin necesidad de instructor.
    Ahora usa SerpSnapshot normalizado en lugar de raw SERP JSON.
    """
    client = OpenAI(api_key=openai_api_key)
    prompt_bundle = resolve_prompt_bundle("brief_generator", prompt_version)
    resolved_model = model or prompt_bundle.model
    resolved_temperature = temperature if temperature is not None else prompt_bundle.temperature

    # Construcción del prompt de usuario (contextual y extremadamente rico)
    user_prompt = f"""
## TAREA
Redacta un briefing SEO completo y ultra-detallado para crear un artículo que posicione en el Top-3 de Google para la keyword principal:

**Keyword principal**: {keyword} ({search_volume:,} búsquedas/mes)

## Datos de mercado (SEMrush)
- Volumen de búsqueda: {search_volume:,}
- Keywords secundarias más relevantes (top 15 por volumen):
{chr(10).join([f"- {k['keyword']} ({k['search_volume']:,} búsquedas/mes)" for k in semrush_data.get('keywords_secundarias', [])[:15]])}

## SERP actual (Google {serp_snapshot.hl} {serp_snapshot.gl})
- Resultados orgánicos: {serp_snapshot.organic_results_count}
- AI Overview presente: {"Sí" if serp_snapshot.ai_overview_present else "No"}
- People Also Ask: {serp_snapshot.people_also_ask_count} preguntas
- Related searches: {serp_snapshot.related_searches_count} términos
- Provider: {serp_snapshot.provider}

## Análisis de la competencia (Top-10 auditado)
{chr(10).join([f"- {e['url']} → {e['word_count']} palabras | H1: {e.get('h1', '')[:80]}..." for e in audit_report.get('entries', [])[:8]])}

## Anchors recomendados (generados automáticamente)
Primarios: {", ".join(anchors.primary)}
Secundarios: {", ".join(anchors.secondary)}

{"## Notas de canibalización" + cannibalization_notes if cannibalization_notes else ""}

## Planificador (paso 1)
{json.dumps(planner_artifact, ensure_ascii=False, indent=2) if planner_artifact else "No planner artifact provided."}

Instrucciones estrictas:
1. El artículo debe superar claramente a todos los resultados actuales en profundidad, actualización, estructura y valor para el usuario.
2. Incluye obligatoriamente secciones que respondan a todas las preguntas del PAA y related searches.
3. Propón un ángulo único y diferenciador realista.
4. Sugiere enlaces internos y externos que refuercen E-E-A-T.
5. Devuelve exclusivamente el JSON según el esquema definido, sin texto adicional.
"""

    try:
        logger.info(f"Generando briefing con {resolved_model} ({prompt_bundle.version}) para: {keyword}")
        
        # Usar structured outputs nativo de OpenAI (beta)
        completion = client.beta.chat.completions.parse(
            model=resolved_model,
            temperature=resolved_temperature,
            messages=[
                {"role": "system", "content": prompt_bundle.system_prompt},
                {"role": "user", "content": user_prompt.strip()}
            ],
            response_format=SEOBriefing
        )
        
        briefing = completion.choices[0].message.parsed
        logger.info(f"Briefing generado correctamente para: {keyword}")
        return briefing

    except RateLimitError:
        logger.error("Rate limit alcanzado con OpenAI")
        raise
    except OpenAIError as e:
        logger.error(f"OpenAI error generando briefing para {keyword}: {e}")
        raise
    except Exception as e:
        logger.error(f"Error generando briefing para {keyword}: {e}")
        raise


def save_briefing_markdown(briefing: SEOBriefing, output_path: Path) -> Path:
    lines = [
        f"# Briefing SEO – {briefing.h1}\n",
        f"**Keyword principal**: {briefing.meta_title}\n",
        f"**Meta Title**: {briefing.meta_title}",
        f"**Meta Description**: {briefing.meta_description}",
        f"**H1**: {briefing.h1}",
        f"**Tono y estilo**: {briefing.tone_style}",
        f"**Ángulo único**: {briefing.unique_angle}",
        f"**Longitud recomendada**: {briefing.longitud_recomendada}\n",
        "## Estructura de contenidos propuesta\n",
    ]

    for i, section in enumerate(briefing.headings, 1):
        lines.append(f"### {i}. {section.title}\n{section.content}\n")

    if briefing.faqs:
        lines.append("## FAQs (Schema FAQPage)\n")
        for faq in briefing.faqs:
            lines.append(f"**{faq.question}**\n{faq.answer}\n")

    if briefing.external_links:
        lines.append("## Enlaces externos de autoridad recomendados\n")
        for link in briefing.external_links:
            lines.append(f"- [{link.anchor}]({link.url}) – {link.authority}")

    if briefing.multimedia_suggestions:
        lines.append("## Sugerencias multimedia\n" + "\n".join(f"- {s}" for s in briefing.multimedia_suggestions))

    text = "\n".join(lines)
    output_path.write_text(text, encoding="utf-8")
    logger.info(f"Markdown del briefing guardado en: {output_path}")
    return output_path

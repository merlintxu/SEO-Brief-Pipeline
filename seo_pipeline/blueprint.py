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

from seo_pipeline.models import AnchorSet, SEOBriefing
from seo_pipeline.utils.text import normalize_ws
from seo_pipeline.constants import BRIEFING_SYSTEM_PROMPT
from seo_pipeline.utils.logging import logger




def generate_briefing(
    keyword: str,
    search_volume: int,
    semrush_data: Dict,
    serp_raw: Dict,
    audit_report: Dict,
    anchors: AnchorSet,
    openai_api_key: str,
    cannibalization_notes: str = "",
    model: str = "gpt-4o-2024-11-20",  # modelo más reciente y barato con structured outputs
    temperature: float = 0.7
) -> SEOBriefing:
    """
    Genera el briefing completo utilizando OpenAI structured outputs nativos.
    Garantiza 100 % parseo correcto del JSON sin necesidad de instructor.
    """
    client = OpenAI(api_key=openai_api_key)

    # Construcción del prompt de usuario (contextual y extremadamente rico)
    user_prompt = f"""
## TAREA
Redacta un briefing SEO completo y ultra-detallado para crear un artículo que posicione en el Top-3 de Google para la keyword principal:

**Keyword principal**: {keyword} ({search_volume:,} búsquedas/mes)

## Datos de mercado (SEMrush)
- Volumen de búsqueda: {search_volume:,}
- Keywords secundarias más relevantes (top 15 por volumen):
{chr(10).join([f"- {k['keyword']} ({k['search_volume']:,} búsquedas/mes)" for k in semrush_data.get('keywords_secundarias', [])[:15]])}

## SERP actual (Google {serp_raw.get('search_parameters', {}).get('hl', 'es')} {serp_raw.get('search_parameters', {}).get('gl', 'es')})
- AI Overview presente: {"Sí" if serp_raw.get("ai_overview") else "No"}
- People Also Ask: {len(serp_raw.get("people_also_ask", []))} preguntas
- Related searches: {len(serp_raw.get("related_searches", []))} términos

## Análisis de la competencia (Top-10 auditado)
{chr(10).join([f"- {e['url']} → {e['word_count']} palabras | H1: {e.get('h1', '')[:80]}..." for e in audit_report.get('entries', [])[:8]])}

## Anchors recomendados (generados automáticamente)
Primarios: {", ".join(anchors.primary)}
Secundarios: {", ".join(anchors.secondary)}

{"## Notas de canibalización" + cannibalization_notes if cannibalization_notes else ""}

Instrucciones estrictas:
1. El artículo debe superar claramente a todos los resultados actuales en profundidad, actualización, estructura y valor para el usuario.
2. Incluye obligatoriamente secciones que respondan a todas las preguntas del PAA y related searches.
3. Propón un ángulo único y diferenciador realista.
4. Sugiere enlaces internos y externos que refuercen E-E-A-T.
5. Devuelve exclusivamente el JSON según el esquema definido, sin texto adicional.
"""

    try:
        logger.info(f"Generando briefing con {model} para: {keyword}")
        
        # Usar structured outputs nativo de OpenAI (beta)
        completion = client.beta.chat.completions.parse(
            model=model,
            temperature=temperature,
            messages=[
                {"role": "system", "content": BRIEFING_SYSTEM_PROMPT},
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
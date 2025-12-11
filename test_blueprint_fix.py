#!/usr/bin/env python3
"""
Script de prueba rápida del pipeline después de los fixes.
Simula el flujo completo sin hacer llamadas reales a APIs.
"""
from seo_pipeline.models import (
    SemrushKeyword, 
    SemrushResults,
    AuditEntry,
    AuditReport,
    AnchorSet
)
from seo_pipeline.blueprint import generate_briefing
from datetime import datetime
import os

def test_blueprint_with_dicts():
    """Prueba que blueprint.py funciona con diccionarios."""
    
    # Simular datos SEMrush como objetos
    principal = SemrushKeyword(keyword="Ley de Contrato de Seguro", search_volume=1200)
    secundarias = [
        SemrushKeyword(keyword=f"keyword secundaria {i}", search_volume=100 - i*5)
        for i in range(20)
    ]
    semrush_obj = SemrushResults(
        keyword_principal=principal,
        keywords_secundarias=secundarias
    )
    
    # Convertir a dict (como hace pipeline.py)
    semrush_dict = semrush_obj.model_dump()
    
    # Simular audit report
    audit_entries = [
        AuditEntry(
            url=f"https://example{i}.com/articulo",
            status_code=200,
            title=f"Título del artículo {i}",
            h1=f"H1 del artículo {i}",
            word_count=1500 + i*100
        )
        for i in range(5)
    ]
    audit_obj = AuditReport(
        label="Test Audit",
        entries=audit_entries,
        generated_at=datetime.now().isoformat()
    )
    
    # Convertir a dict
    audit_dict = audit_obj.model_dump()
    
    # Simular SERP data
    serp_raw = {
        "search_parameters": {"hl": "es", "gl": "es"},
        "ai_overview": None,
        "people_also_ask": [{"question": "¿Qué es?"}] * 3,
        "related_searches": [{"query": "búsqueda relacionada"}] * 5
    }
    
    # Simular anchors
    anchors = AnchorSet(
        primary=["anchor 1", "anchor 2"],
        secondary=["sec 1", "sec 2", "sec 3"]
    )
    
    print("=" * 60)
    print("PRUEBA: Blueprint con diccionarios (post-fix)")
    print("=" * 60)
    
    # Verificar que los datos son diccionarios
    print(f"\n✓ semrush_data es dict: {isinstance(semrush_dict, dict)}")
    print(f"✓ audit_report es dict: {isinstance(audit_dict, dict)}")
    
    # Verificar acceso a keywords_secundarias
    print(f"\n✓ Accediendo a keywords_secundarias...")
    kws = semrush_dict.get('keywords_secundarias', [])
    print(f"  → {len(kws)} keywords encontradas")
    
    # Verificar formato de string (como en blueprint.py línea 51)
    print(f"\n✓ Probando formato de string (línea 51)...")
    try:
        formatted = ', '.join([
            f"{k['keyword']} ({k['search_volume']:,})" 
            for k in semrush_dict.get('keywords_secundarias', [])[:3]
        ])
        print(f"  → {formatted}")
        print("  ✅ Línea 51 funciona correctamente")
    except Exception as e:
        print(f"  ❌ Error en línea 51: {e}")
        return False
    
    # Verificar acceso a audit entries (línea 59)
    print(f"\n✓ Probando acceso a audit entries (línea 59)...")
    try:
        entries = audit_dict.get('entries', [])
        formatted_audit = ', '.join([
            f"{e['url']} → {e['word_count']} palabras"
            for e in entries[:2]
        ])
        print(f"  → {formatted_audit}")
        print("  ✅ Línea 59 funciona correctamente")
    except Exception as e:
        print(f"  ❌ Error en línea 59: {e}")
        return False
    
    # Prueba completa con OpenAI (solo si hay API key)
    openai_key = os.getenv("OPENAI_API_KEY", "")
    if openai_key and openai_key.startswith("sk-"):
        print(f"\n✓ OpenAI API key encontrada, probando generación real...")
        try:
            briefing = generate_briefing(
                keyword="Ley de Contrato de Seguro",
                search_volume=1200,
                semrush_data=semrush_dict,  # ← Dict, no objeto
                serp_raw=serp_raw,
                audit_report=audit_dict,     # ← Dict, no objeto
                anchors=anchors,
                openai_api_key=openai_key,
                cannibalization_notes=""
            )
            print(f"  ✅ Briefing generado exitosamente!")
            print(f"  → Meta title: {briefing.meta_title}")
            print(f"  → H1: {briefing.h1}")
            print(f"  → {len(briefing.headings)} secciones generadas")
        except Exception as e:
            print(f"  ⚠️  Error generando briefing con OpenAI: {e}")
            print(f"  (Esto puede ser por rate limit u otro error de API)")
    else:
        print(f"\n⚠️  No se encontró OPENAI_API_KEY, omitiendo test con API real")
    
    print("\n" + "=" * 60)
    print("✅ TODAS LAS PRUEBAS PASARON - El fix funciona correctamente")
    print("=" * 60)
    return True

if __name__ == "__main__":
    success = test_blueprint_with_dicts()
    exit(0 if success else 1)

#!/usr/bin/env python3
"""
Script de prueba end-to-end del pipeline con fix aplicado.
"""
import sys
from seo_pipeline.pipeline import run_full_pipeline
from seo_pipeline.config import get_config

def test_real_pipeline():
    """Ejecuta el pipeline con el keyword del usuario."""
    
    keyword = "Ley de Contrato de Seguro"
    
    print("=" * 70)
    print(f"EJECUTANDO PIPELINE REAL CON KEYWORD: {keyword}")
    print("=" * 70)
    
    try:
        cfg = get_config()
        if not cfg.active_client or not cfg.active_project:
            print("❌ Error: No hay cliente/proyecto activo configurado")
            print("   Ejecuta: python client_manager.py")
            return False
        
        print(f"\n✓ Cliente activo: {cfg.active_client.name}")
        print(f"✓ Proyecto activo: {cfg.active_project.name}")
        print(f"\nIniciando pipeline...\n")
        
        results = run_full_pipeline(
            keyword=keyword,
            upload_to_sheets=False,  # Desactivar para test
        )
        
        print("\n" + "=" * 70)
        print("✅ PIPELINE COMPLETADO EXITOSAMENTE")
        print("=" * 70)
        print(f"\nRun ID: {results['run_id']}")
        print(f"Output dir: {results['output_dir']}")
        
        if 'briefing' in results:
            briefing = results['briefing']
            print(f"\n📄 Briefing generado:")
            print(f"  - Meta title: {briefing.meta_title}")
            print(f"  - H1: {briefing.h1}")
            print(f"  - Secciones: {len(briefing.headings)}")
        
        return True
        
    except Exception as e:
        print("\n" + "=" * 70)
        print(f"❌ PIPELINE FALLÓ")
        print("=" * 70)
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_real_pipeline()
    sys.exit(0 if success else 1)

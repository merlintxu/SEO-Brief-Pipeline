# client_manager.py
"""
Gestor interactivo de clientes y proyectos para el SEO Pipeline 2025.
Uso local o en terminal → python client_manager.py
Funcionalidades:
  1. Crear nuevo cliente
  2. Crear nuevo proyecto
  3. Listar clientes/proyectos
  4. Activar cliente + proyecto
  5. Ver configuración actual
  6. Ejecutar pipeline directamente
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from getpass import getpass
from dotenv import load_dotenv
load_dotenv()  # Carga .env automáticamente

# Luego, al crear cliente, puedes pre-rellenar si existen en .env
import os
defaults = {
    "semrush_token": os.getenv("SEMRUSH_TOKEN"),
    "serpapi_key": os.getenv("SERPAPI_KEY"),
    "openai_key": os.getenv("OPENAI_API_KEY"),
    "piloterr_key": os.getenv("PILOTERR_API_KEY"),
    "dataforseo_login": os.getenv("DFSP_USERNAME"),
    "dataforseo_password": os.getenv("DFSP_PASSWORD"),
}

# Añadir paquete al path
ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT / "seo_pipeline"))

from seo_pipeline.config import get_config, ClientConfig, ProjectConfig
from seo_pipeline.pipeline import run_full_pipeline
from seo_pipeline.utils.logging import setup_logging, logger

setup_logging(level="INFO")
cfg = get_config()

from rich.console import Console
from rich.prompt import Prompt, Confirm
from rich.panel import Panel
from rich.table import Table

console = Console()

def clear_screen():
    console.clear()

def crear_cliente():
    console.print(Panel("CREAR NUEVO CLIENTE", style="bold blue"))
    client_id = input("ID único (sin espacios, ej: acme_es): ").strip()
    if client_id in cfg.clients:
        console.print("[bold red]¡Error: Ya existe un cliente con ese ID![/bold red]")
        return

    new_client = ClientConfig(
        client_id=client_id,
        name=input("Nombre del cliente: ").strip(),
        semrush_token=getpass("SEMrush API token (Enter = ninguno): ") or None,
        serpapi_key=getpass("SerpAPI key (Enter = ninguno): ") or None,
        openai_key=getpass("OpenAI API key (Enter = ninguno): ") or None,
        gsc_sa_path=input("Ruta relativa al JSON Service Account GSC (ej: credentials/gsc.json): ").strip() or None,
        sheets_sa_path=input("Ruta relativa al JSON Service Account Sheets (ej: credentials/sheets.json): ").strip() or None,
        default_database=input("Database SEMrush por defecto (es/uk/de...): ").strip() or "es",
        default_gl=input("Google gl por defecto (es/uk/de...): ").strip() or "es",
        default_hl=input("Google hl por defecto (es-es/uk...): ").strip() or "es-es",
    )

    cfg.clients[client_id] = new_client
    cfg.save_clients()
    cfg.save_clients()
    console.print(f"[bold green]Cliente '{new_client.name}' creado correctamente.[/bold green]")

def crear_proyecto():
    if not cfg.clients:
        logger.warning("No hay clientes. Crea primero un cliente.")
        return

    logger.info("Clientes disponibles:")
    for cid, c in cfg.clients.items():
        logger.info("  • %s → %s", cid, c.name)

    client_id = input("\nID del cliente propietario: ").strip()
    if client_id not in cfg.clients:
        logger.error("Cliente no encontrado")
        return

    project_id = input("ID único del proyecto (ej: blog_es): ").strip()
    if project_id in cfg.projects:
        logger.error("¡Error: Proyecto ya existe!")
        return

    new_project = ProjectConfig(
        project_id=project_id,
        client_id=client_id,
        name=input("Nombre del proyecto: ").strip(),
        base_domain=input("Dominio principal (ej: ejemplo.com): ").strip(),
        gsc_property=input("Propiedad GSC completa[](https://ejemplo.com/): ").strip(),
        sheets_id=input("ID o URL completa de Google Sheets: ").strip(),
        output_dir="runs"
    )

    cfg.projects[project_id] = new_project
    cfg.save_projects()
    logger.info("Proyecto '%s' creado y vinculado.", new_project.name)

def activar():
    if not cfg.clients:
        logger.warning("No hay clientes registrados")
        return

    logger.info("=== ACTIVAR CLIENTE ===")
    for cid, c in cfg.clients.items():
        status = " (ACTIVO)" if cfg.active_client and cfg.active_client.client_id == cid else ""
        logger.info("  • %s → %s%s", cid, c.name, status)

    client_id = input("\nID del cliente a activar: ").strip()
    if cfg.set_active_client(client_id):
        logger.info("Cliente activado: %s", cfg.active_client.name)
    else:
        logger.error("Cliente no encontrado")
        return

    # Proyectos del cliente
    proyectos = [p for p in cfg.projects.values() if p.client_id == client_id]
    if not proyectos:
        logger.warning("Este cliente no tiene proyectos")
        return

    logger.info("Proyectos disponibles:")
    for p in proyectos:
        status = " (ACTIVO)" if cfg.active_project and cfg.active_project.project_id == p.project_id else ""
        logger.info("  • %s → %s%s", p.project_id, p.name, status)

    proj_id = input("\nID del proyecto a activar: ").strip()
    if cfg.set_active_project(proj_id):
        logger.info("Proyecto activado: %s", cfg.active_project.name)
        logger.info("   Dominio: %s", cfg.active_project.base_domain)
    else:
        logger.error("Proyecto no encontrado")

def estado():
    logger.info("=== ESTADO ACTUAL ===")
    if cfg.active_client:
        c = cfg.active_client
        logger.info("Cliente : %s (%s)", c.name, c.client_id)
        logger.info("    SEMrush : %s", 'Configurado' if c.semrush_token else 'No configurado')
        logger.info("    SerpAPI : %s", 'Configurado' if c.serpapi_key else 'No configurado')
        logger.info("    OpenAI  : %s", 'Configurado' if c.openai_key else 'No configurado')
    else:
        logger.info("  Ningún cliente activo")

    if cfg.active_project:
        p = cfg.active_project
        logger.info("Proyecto: %s (%s)", p.name, p.project_id)
        logger.info("    Dominio : %s", p.base_domain)
        logger.info("    Sheets  : %s", p.sheets_id)
    else:
        logger.info("  Ningún proyecto activo")

def ejecutar_pipeline():
    if not cfg.active_client or not cfg.active_project:
        logger.error("Debes activar primero cliente + proyecto")
        return

    kw = input("\nKeyword principal: ").strip()
    if not kw:
        logger.error("Keyword obligatoria")
        return

    target = input("URL objetivo (Enter = ninguna): ").strip() or None
    upload = input("Subir fila a Google Sheets? (s/N): ").strip().lower() == "s"

    logger.info("Lanzando pipeline para: %s", kw)
    try:
        resultados = run_full_pipeline(
            keyword=kw,
            target_url=target,
            upload_to_sheets=upload
        )
        logger.info("Pipeline completado")
        logger.info("Archivos generados en: %s", resultados['output_dir'])
    except Exception as e:
        logger.error("Error: %s", e)

def menu():
    opciones = {
        "1": ("Crear nuevo cliente", crear_cliente),
        "2": ("Crear nuevo proyecto", crear_proyecto),
        "3": ("Activar cliente + proyecto", activar),
        "4": ("Ver estado actual", estado),
        "5": ("Ejecutar pipeline ahora", ejecutar_pipeline),
        "6": ("Salir", lambda: sys.exit(0)),
    }

    while True:
        clear_screen()
        console.print(Panel("[bold cyan]SEO Briefing Pipeline 2025[/bold cyan]\nGestor Local", expand=False))
        
        table = Table(show_header=False, box=None)
        for k, (txt, _) in opciones.items():
            table.add_row(f"[bold yellow]{k}[/bold yellow]", txt)
        console.print(table)
        console.print("")
        choice = input("Elige una opción: ").strip()
        if choice in opciones:
            opciones[choice][1]()
            input("\nPulsa Enter para continuar...")
        else:
            logger.error("Opción no válida")
            input()

if __name__ == "__main__":
    # Crear carpetas necesarias
    for d in ("config", "runs", "credentials"):
        (ROOT / d).mkdir(exist_ok=True)
    menu()
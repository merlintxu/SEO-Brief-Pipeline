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
from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

# Carga .env automáticamente
load_dotenv()

# Añadir paquete al path
ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT / "seo_pipeline"))

from seo_pipeline.config import get_config, ClientConfig, ProjectConfig
from seo_pipeline.pipeline import run_full_pipeline
from seo_pipeline.utils.logging import setup_logging, logger

# Configuración inicial
setup_logging(level="INFO")

class ClientManagerCLI:
    def __init__(self):
        self.cfg = get_config()
        self.console = Console()
        self.defaults = {
            "semrush_token": os.getenv("SEMRUSH_TOKEN"),
            "serpapi_key": os.getenv("SERPAPI_KEY"),
            "openai_key": os.getenv("OPENAI_API_KEY"),
            "piloterr_key": os.getenv("PILOTERR_API_KEY"),
            "dataforseo_login": os.getenv("DFSP_USERNAME"),
            "dataforseo_password": os.getenv("DFSP_PASSWORD"),
        }

    def clear_screen(self):
        self.console.clear()

    def crear_cliente(self):
        self.console.print(Panel("CREAR NUEVO CLIENTE", style="bold blue"))
        client_id = input("ID único (sin espacios, ej: acme_es): ").strip()
        if client_id in self.cfg.clients:
            self.console.print("[bold red]¡Error: Ya existe un cliente con ese ID![/bold red]")
            return

        # Mostrar valores de .env si existen
        if self.defaults.get("semrush_token"):
            self.console.print(f"[dim]SEMrush token encontrado en .env: {self.defaults['semrush_token'][-6:]}...[/dim]")
        if self.defaults.get("serpapi_key"):
            self.console.print(f"[dim]SerpAPI key encontrada en .env: {self.defaults['serpapi_key'][-6:]}...[/dim]")
        if self.defaults.get("openai_key"):
            self.console.print(f"[dim]OpenAI key encontrada en .env: {self.defaults['openai_key'][-20:]}...[/dim]")
        
        # Usar valores de .env como default o pedir al usuario
        semrush = input(f"SEMrush API token (Enter = usar .env): ").strip()
        serpapi = input(f"SerpAPI key (Enter = usar .env): ").strip()
        openai = input(f"OpenAI API key (Enter = usar .env): ").strip()
        
        # DataForSEO como fallback
        self.console.print("\n[bold cyan]DataForSEO (opcional - fallback para SERP)[/bold cyan]")
        dataforseo_login = input(f"DataForSEO login (Enter = usar .env o ninguno): ").strip()
        dataforseo_pwd = input(f"DataForSEO password (Enter = usar .env o ninguno): ").strip()

        new_client = ClientConfig(
            client_id=client_id,
            name=input("Nombre del cliente: ").strip(),
            semrush_token=semrush or self.defaults.get("semrush_token") or None,
            serpapi_key=serpapi or self.defaults.get("serpapi_key") or None,
            openai_key=openai or self.defaults.get("openai_key") or None,
            dataforseo_login=dataforseo_login or self.defaults.get("dataforseo_login") or None,
            dataforseo_password=dataforseo_pwd or self.defaults.get("dataforseo_password") or None,
            gsc_sa_path=input("Ruta relativa al JSON Service Account GSC (ej: credentials/gsc.json): ").strip() or None,
            sheets_sa_path=input("Ruta relativa al JSON Service Account Sheets (ej: credentials/sheets.json): ").strip() or None,
            default_database=input("Database SEMrush por defecto (es/uk/de...): ").strip() or "es",
            default_gl=input("Google gl por defecto (es/uk/de...): ").strip() or "es",
            default_hl=input("Google hl por defecto (es/uk/de...): ").strip() or "es",
        )

        self.cfg.clients[client_id] = new_client
        self.cfg.save_clients()
        self.console.print(f"[bold green]Cliente '{new_client.name}' creado correctamente.[/bold green]")

    def crear_proyecto(self):
        if not self.cfg.clients:
            logger.warning("No hay clientes. Crea primero un cliente.")
            return

        self.console.print("\n[bold]Clientes disponibles:[/bold]")
        for cid, c in self.cfg.clients.items():
            self.console.print(f"  • [cyan]{cid}[/cyan] → {c.name}")

        client_id = input("\nID del cliente propietario: ").strip()
        if client_id not in self.cfg.clients:
            logger.error("Cliente no encontrado")
            return

        project_id = input("ID único del proyecto (ej: blog_es): ").strip()
        if project_id in self.cfg.projects:
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

        self.cfg.projects[project_id] = new_project
        self.cfg.save_projects()
        logger.info("Proyecto '%s' creado y vinculado.", new_project.name)

    def activar(self):
        if not self.cfg.clients:
            logger.warning("No hay clientes registrados")
            return

        self.console.print("\n[bold]=== ACTIVAR CLIENTE ===[/bold]")
        for cid, c in self.cfg.clients.items():
            status = " [green](ACTIVO)[/green]" if self.cfg.active_client and self.cfg.active_client.client_id == cid else ""
            self.console.print(f"  • [cyan]{cid}[/cyan] → {c.name}{status}")

        client_id = input("\nID del cliente a activar: ").strip()
        if self.cfg.set_active_client(client_id):
            self.console.print(f"[green]✓ Cliente activado:[/green] {self.cfg.active_client.name}")
        else:
            logger.error("Cliente no encontrado")
            return

        # Proyectos del cliente
        proyectos = [p for p in self.cfg.projects.values() if p.client_id == client_id]
        if not proyectos:
            logger.warning("Este cliente no tiene proyectos")
            return

        self.console.print("\n[bold]Proyectos disponibles:[/bold]")
        for p in proyectos:
            status = " [green](ACTIVO)[/green]" if self.cfg.active_project and self.cfg.active_project.project_id == p.project_id else ""
            self.console.print(f"  • [cyan]{p.project_id}[/cyan] → {p.name}{status}")

        proj_id = input("\nID del proyecto a activar: ").strip()
        if self.cfg.set_active_project(proj_id):
            self.console.print(f"[green]✓ Proyecto activado:[/green] {self.cfg.active_project.name}")
            self.console.print(f"   Dominio: {self.cfg.active_project.base_domain}")
        else:
            logger.error("Proyecto no encontrado")

    def estado(self):
        self.console.print("\n[bold]=== ESTADO ACTUAL ===[/bold]")
        if self.cfg.active_client:
            c = self.cfg.active_client
            self.console.print(f"[bold]Cliente:[/bold] {c.name} [dim]({c.client_id})[/dim]")
            self.console.print(f"    SEMrush : {'[green]Configurado[/green]' if c.semrush_token else '[red]No configurado[/red]'}")
            self.console.print(f"    SerpAPI : {'[green]Configurado[/green]' if c.serpapi_key else '[red]No configurado[/red]'}")
            self.console.print(f"    OpenAI  : {'[green]Configurado[/green]' if c.openai_key else '[red]No configurado[/red]'}")
        else:
            self.console.print("  [yellow]Ningún cliente activo[/yellow]")

        if self.cfg.active_project:
            p = self.cfg.active_project
            self.console.print(f"\n[bold]Proyecto:[/bold] {p.name} [dim]({p.project_id})[/dim]")
            self.console.print(f"    Dominio : {p.base_domain}")
            self.console.print(f"    Sheets  : {p.sheets_id}")
        else:
            self.console.print("  [yellow]Ningún proyecto activo[/yellow]")

    def ejecutar_pipeline(self):
        if not self.cfg.active_client or not self.cfg.active_project:
            logger.error("Debes activar primero cliente + proyecto")
            return

        kw = input("\nKeyword principal: ").strip()
        if not kw:
            logger.error("Keyword obligatoria")
            return

        target = input("URL objetivo (Enter = ninguna): ").strip() or None
        upload = input("Subir fila a Google Sheets? (s/N): ").strip().lower() == "s"

        self.console.print(f"\n[bold cyan]Lanzando pipeline para:[/bold cyan] {kw}")
        try:
            resultados = run_full_pipeline(
                keyword=kw,
                target_url=target,
                upload_to_sheets=upload
            )
            self.console.print("\n[bold green]✓ Pipeline completado[/bold green]")
            self.console.print(f"Archivos generados en: [cyan]{resultados['output_dir']}[/cyan]")
        except Exception as e:
            self.console.print(f"[bold red]✗ Error:[/bold red] {e}")

    def menu(self):
        opciones = {
            "1": ("Crear nuevo cliente", self.crear_cliente),
            "2": ("Crear nuevo proyecto", self.crear_proyecto),
            "3": ("Activar cliente + proyecto", self.activar),
            "4": ("Ver estado actual", self.estado),
            "5": ("Ejecutar pipeline ahora", self.ejecutar_pipeline),
            "6": ("Salir", lambda: sys.exit(0)),
        }

        while True:
            self.clear_screen()
            self.console.print(Panel("[bold cyan]SEO Briefing Pipeline 2025[/bold cyan]\nGestor Local", expand=False))
            
            table = Table(show_header=False, box=None)
            for k, (txt, _) in opciones.items():
                table.add_row(f"[bold yellow]{k}[/bold yellow]", txt)
            self.console.print(table)
            self.console.print("")
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
    
    cli = ClientManagerCLI()
    cli.menu()
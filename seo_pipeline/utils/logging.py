# seo_pipeline/utils/logging.py
"""
Configuración centralizada y unificada de logging.
Evita duplicados en Colab y permite control total desde un único punto.
"""
from __future__ import annotations
import logging
import sys
from loguru import logger
from pathlib import Path

def setup_logging(
    level: str = "INFO",
    logfile: Path | None = None,
    rich_tracebacks: bool = True
) -> None:
    """
    Configura Loguru como logger principal (mejor que logging estándar).
    Única llamada recomendada al inicio del notebook o script.
    """
    logger.remove()  # Elimina handler por defecto

    # Handler para consola (Colab / terminal)
    logger.add(
        sys.stderr,
        level=level.upper(),
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan> - <level>{message}</level>",
        colorize=True,
        backtrace=True,
        diagnose=True,
    )

    # Handler para archivo: por defecto escribe a PIPELINE_LOGFILE o PIPELINE_ROOT/logs/pipeline.log
    if logfile is None:
        from os import getenv
        root = Path(getenv("PIPELINE_ROOT", Path.cwd()))
        logfile = Path(getenv("PIPELINE_LOGFILE", str(root / "logs" / "pipeline.log")))

    try:
        logfile = Path(logfile)
        logfile.parent.mkdir(parents=True, exist_ok=True)
        logger.add(
            str(logfile),
            level=level.upper(),
            rotation="10 MB",
            retention="30 days",
            compression="zip",
            encoding="utf-8",
        )
    except Exception:
        # Si por alguna razón no se puede crear el archivo de logs, seguir sin fallo
        pass

    # Opcional: rich tracebacks (muy útil en Colab)
    if rich_tracebacks:
        try:
            from rich.logging import RichHandler
            logger.add(RichHandler(rich_tracebacks=True, tracebacks_show_locals=True))
        except Exception:
            pass  # rich no instalado → se ignora silenciosamente

# Configuración automática al importar el módulo (conveniente en notebooks)
setup_logging(level="INFO")
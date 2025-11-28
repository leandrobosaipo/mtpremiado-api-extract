"""Inicialização de diretórios necessários para a aplicação."""

import os
from pathlib import Path
from src.core.logger import get_logger

logger = get_logger()


def ensure_directories():
    """Cria todos os diretórios necessários para a aplicação."""
    directories = [
        "data",
        "data/exports",
        "debug",
        "debug/html",
        "debug/screenshots",
    ]
    
    for directory in directories:
        try:
            Path(directory).mkdir(parents=True, exist_ok=True)
            logger.debug("directory_ensured", directory=directory)
        except Exception as e:
            logger.error("directory_creation_failed", directory=directory, error=str(e))
            raise


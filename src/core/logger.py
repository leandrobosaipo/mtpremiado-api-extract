"""Configuração de logging estruturado."""

import logging
import sys
from datetime import datetime
from typing import Any, Dict
import json


class StructuredLogger:
    """Logger estruturado para eventos do sistema."""
    
    def __init__(self, name: str, level: str = "INFO"):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(getattr(logging, level.upper()))
        
        if not self.logger.handlers:
            handler = logging.StreamHandler(sys.stdout)
            handler.setFormatter(StructuredFormatter())
            self.logger.addHandler(handler)
    
    def _log(self, level: str, event: str, **kwargs):
        """Log estruturado com evento e contexto."""
        extra = {
            "event": event,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            **kwargs
        }
        getattr(self.logger, level.lower())(json.dumps(extra, ensure_ascii=False))
    
    def info(self, event: str, **kwargs):
        """Log de informação."""
        self._log("INFO", event, **kwargs)
    
    def error(self, event: str, **kwargs):
        """Log de erro."""
        self._log("ERROR", event, **kwargs)
    
    def warning(self, event: str, **kwargs):
        """Log de aviso."""
        self._log("WARNING", event, **kwargs)
    
    def debug(self, event: str, **kwargs):
        """Log de debug."""
        self._log("DEBUG", event, **kwargs)


class StructuredFormatter(logging.Formatter):
    """Formatter que estrutura logs em JSON."""
    
    def format(self, record: logging.LogRecord) -> str:
        """Formata o log como JSON."""
        try:
            log_data = json.loads(record.getMessage())
            return json.dumps(log_data, ensure_ascii=False)
        except (json.JSONDecodeError, AttributeError):
            return json.dumps({
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "level": record.levelname,
                "message": record.getMessage(),
            }, ensure_ascii=False)


def get_logger(name: str = "mtpremiado_api") -> StructuredLogger:
    """Retorna uma instância do logger estruturado."""
    from src.core.settings import settings
    return StructuredLogger(name, settings.LOG_LEVEL)


"""Helper para debug e diagnóstico de scraping."""

import os
import time
import uuid
from datetime import datetime
from typing import Optional, Dict, List, Any
from pathlib import Path

from playwright.async_api import Page
from bs4 import BeautifulSoup

from src.core.settings import settings
from src.core.logger import get_logger

logger = get_logger()

# Armazena informações de debug da sessão atual
_debug_session_data: Dict[str, Any] = {}


class DebugHelper:
    """Helper para operações de debug."""
    
    @staticmethod
    def _get_debug_dir() -> Path:
        """Retorna o diretório de debug, criando se necessário."""
        debug_dir = Path(settings.DEBUG_DIR)
        debug_dir.mkdir(exist_ok=True)
        return debug_dir
    
    @staticmethod
    def _get_session_id() -> str:
        """Gera ou retorna ID da sessão atual."""
        if "session_id" not in _debug_session_data:
            _debug_session_data["session_id"] = str(uuid.uuid4())[:8]
            _debug_session_data["steps"] = []
            _debug_session_data["timings"] = []
            _debug_session_data["screenshots"] = []
            _debug_session_data["html_files"] = []
        return _debug_session_data["session_id"]
    
    @staticmethod
    def log_step(step_name: str, details: Optional[Dict[str, Any]] = None) -> None:
        """Log estruturado de cada etapa."""
        if not settings.DEBUG_MODE:
            return
        
        step_data = {
            "step": step_name,
            "timestamp": datetime.utcnow().isoformat(),
            "details": details or {}
        }
        
        _debug_session_data.setdefault("steps", []).append(step_data)
        
        details_str = ""
        if details:
            details_str = " | " + " | ".join(f"{k}={v}" for k, v in details.items())
        
        logger.info(f"debug_step_{step_name}", step=step_name, **details or {})
    
    @staticmethod
    async def take_screenshot(page: Page, step_name: str, description: str = "") -> Optional[str]:
        """Tira screenshot com nome descritivo."""
        if not settings.DEBUG_SCREENSHOTS or not page:
            return None
        
        try:
            session_id = DebugHelper._get_session_id()
            debug_dir = DebugHelper._get_debug_dir()
            screenshots_dir = debug_dir / "screenshots"
            screenshots_dir.mkdir(exist_ok=True)
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{session_id}_{step_name}_{timestamp}.png"
            if description:
                filename = f"{session_id}_{step_name}_{description}_{timestamp}.png"
            
            filepath = screenshots_dir / filename
            
            await page.screenshot(path=str(filepath), full_page=True)
            
            screenshot_info = {
                "step": step_name,
                "filename": filename,
                "path": str(filepath),
                "timestamp": timestamp
            }
            _debug_session_data.setdefault("screenshots", []).append(screenshot_info)
            
            logger.info("debug_screenshot_saved", step=step_name, filename=filename)
            return str(filepath)
        except Exception as e:
            logger.warning("debug_screenshot_failed", step=step_name, error=str(e))
            return None
    
    @staticmethod
    async def check_element_exists(page: Page, selector: str, description: str = "") -> Dict[str, Any]:
        """Verifica e loga se elemento existe."""
        if not settings.DEBUG_MODE or not page:
            return {"exists": False, "count": 0}
        
        try:
            count = await page.locator(selector).count()
            exists = count > 0
            
            result = {
                "exists": exists,
                "count": count,
                "selector": selector,
                "description": description or selector
            }
            
            if settings.DEBUG_SELECTORS:
                logger.info(
                    "debug_element_check",
                    selector=selector,
                    exists=exists,
                    count=count,
                    description=description
                )
            
            return result
        except Exception as e:
            logger.warning("debug_element_check_error", selector=selector, error=str(e))
            return {"exists": False, "count": 0, "error": str(e)}
    
    @staticmethod
    def log_timing(operation: str, duration: float, details: Optional[Dict[str, Any]] = None) -> None:
        """Loga tempo de operação."""
        if not settings.DEBUG_TIMING:
            return
        
        timing_data = {
            "operation": operation,
            "duration_ms": round(duration * 1000, 2),
            "duration_sec": round(duration, 2),
            "timestamp": datetime.utcnow().isoformat(),
            "details": details or {}
        }
        
        _debug_session_data.setdefault("timings", []).append(timing_data)
        
        logger.info(
            "debug_timing",
            operation=operation,
            duration_ms=timing_data["duration_ms"],
            duration_sec=timing_data["duration_sec"],
            **details or {}
        )
    
    @staticmethod
    async def save_html(page: Page, filename: str, description: str = "") -> Optional[str]:
        """Salva HTML com timestamp."""
        if not settings.DEBUG_SAVE_HTML or not page:
            return None
        
        try:
            session_id = DebugHelper._get_session_id()
            debug_dir = DebugHelper._get_debug_dir()
            html_dir = debug_dir / "html"
            html_dir.mkdir(exist_ok=True)
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            safe_filename = filename.replace("/", "_").replace("\\", "_")
            full_filename = f"{session_id}_{safe_filename}_{timestamp}.html"
            
            filepath = html_dir / full_filename
            
            html_content = await page.content()
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(html_content)
            
            html_info = {
                "filename": full_filename,
                "path": str(filepath),
                "description": description,
                "size": len(html_content),
                "timestamp": timestamp
            }
            _debug_session_data.setdefault("html_files", []).append(html_info)
            
            logger.info("debug_html_saved", filename=full_filename, size=len(html_content))
            return str(filepath)
        except Exception as e:
            logger.warning("debug_html_save_failed", filename=filename, error=str(e))
            return None
    
    @staticmethod
    def start_timer(operation: str) -> float:
        """Inicia timer para uma operação."""
        return time.time()
    
    @staticmethod
    def end_timer(start_time: float, operation: str, details: Optional[Dict[str, Any]] = None) -> float:
        """Finaliza timer e loga duração."""
        duration = time.time() - start_time
        DebugHelper.log_timing(operation, duration, details)
        return duration
    
    @staticmethod
    async def wait_and_log(page: Page, wait_type: str, timeout: int, description: str = "") -> Dict[str, Any]:
        """Aguarda condição e loga tempo de espera."""
        if not settings.DEBUG_WAIT_TIMES or not page:
            return {"success": True}
        
        start_time = time.time()
        result = {"success": False, "wait_type": wait_type, "timeout": timeout}
        
        try:
            if wait_type == "load_state":
                await page.wait_for_load_state("domcontentloaded", timeout=timeout)
            elif wait_type == "networkidle":
                await page.wait_for_load_state("networkidle", timeout=timeout)
            elif wait_type == "selector":
                # Precisa de selector passado em details
                pass
            
            duration = time.time() - start_time
            result["success"] = True
            result["duration_ms"] = round(duration * 1000, 2)
            
            logger.info(
                "debug_wait_completed",
                wait_type=wait_type,
                duration_ms=result["duration_ms"],
                timeout=timeout,
                description=description
            )
        except Exception as e:
            duration = time.time() - start_time
            result["duration_ms"] = round(duration * 1000, 2)
            result["error"] = str(e)
            
            logger.warning(
                "debug_wait_timeout",
                wait_type=wait_type,
                duration_ms=result["duration_ms"],
                timeout=timeout,
                error=str(e),
                description=description
            )
        
        return result
    
    @staticmethod
    def create_diagnostic_report() -> Dict[str, Any]:
        """Cria relatório de diagnóstico completo."""
        session_id = _debug_session_data.get("session_id", "unknown")
        
        report = {
            "session_id": session_id,
            "timestamp": datetime.utcnow().isoformat(),
            "steps": _debug_session_data.get("steps", []),
            "timings": _debug_session_data.get("timings", []),
            "screenshots": _debug_session_data.get("screenshots", []),
            "html_files": _debug_session_data.get("html_files", []),
            "summary": {
                "total_steps": len(_debug_session_data.get("steps", [])),
                "total_timings": len(_debug_session_data.get("timings", [])),
                "total_screenshots": len(_debug_session_data.get("screenshots", [])),
                "total_html_files": len(_debug_session_data.get("html_files", []))
            }
        }
        
        # Calcula tempo total
        timings = _debug_session_data.get("timings", [])
        if timings:
            total_duration = sum(t.get("duration_ms", 0) for t in timings)
            report["summary"]["total_duration_ms"] = round(total_duration, 2)
            report["summary"]["total_duration_sec"] = round(total_duration / 1000, 2)
        
        return report
    
    @staticmethod
    def reset_session() -> None:
        """Reseta dados da sessão de debug."""
        global _debug_session_data
        _debug_session_data = {}
    
    @staticmethod
    def get_session_data() -> Dict[str, Any]:
        """Retorna dados da sessão atual."""
        return _debug_session_data.copy()


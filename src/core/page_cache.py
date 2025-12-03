"""Gerenciador de cache de páginas para paginação eficiente."""

import json
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, List
from src.core.settings import settings
from src.core.logger import get_logger

logger = get_logger()


class PageCache:
    """Gerencia cache de páginas de pedidos em arquivo JSON."""
    
    def __init__(self):
        """Inicializa o gerenciador de cache."""
        self.cache_file = Path(settings.DATA_DIR) / "pages_cache.json"
        self._ensure_cache_dir()
    
    def _ensure_cache_dir(self):
        """Garante que o diretório do cache existe."""
        self.cache_file.parent.mkdir(parents=True, exist_ok=True)
    
    def _load_cache(self) -> Dict:
        """Carrega o cache do arquivo JSON."""
        if not self.cache_file.exists():
            return {
                "last_updated": None,
                "total_pages_cached": 0,
                "pages": {}
            }
        
        try:
            with open(self.cache_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data
        except json.JSONDecodeError as e:
            logger.warning("cache_file_invalid_json", file=str(self.cache_file), error=str(e))
            return {
                "last_updated": None,
                "total_pages_cached": 0,
                "pages": {}
            }
        except Exception as e:
            logger.error("cache_file_read_error", file=str(self.cache_file), error=str(e))
            return {
                "last_updated": None,
                "total_pages_cached": 0,
                "pages": {}
            }
    
    def _save_cache(self, cache_data: Dict) -> bool:
        """Salva o cache no arquivo JSON."""
        try:
            cache_data["last_updated"] = datetime.utcnow().isoformat() + "Z"
            cache_data["total_pages_cached"] = len(cache_data.get("pages", {}))
            
            with open(self.cache_file, "w", encoding="utf-8") as f:
                json.dump(cache_data, f, indent=2, ensure_ascii=False)
            
            logger.debug("cache_saved", total_pages=cache_data["total_pages_cached"])
            return True
        except Exception as e:
            logger.error("cache_file_write_error", file=str(self.cache_file), error=str(e))
            return False
    
    def get_page(self, page_num: int) -> Optional[List[Dict]]:
        """Retorna uma página do cache se existir.
        
        Args:
            page_num: Número da página (1-indexed)
            
        Returns:
            Lista de pedidos da página ou None se não estiver em cache
        """
        cache_data = self._load_cache()
        pages = cache_data.get("pages", {})
        
        page_key = str(page_num)
        if page_key in pages:
            page_data = pages[page_key]
            logger.debug("cache_hit", page=page_num, fetched_at=page_data.get("fetched_at"))
            return page_data.get("pedidos", [])
        
        logger.debug("cache_miss", page=page_num)
        return None
    
    def save_page(self, page_num: int, pedidos: List[Dict]) -> bool:
        """Salva uma página no cache.
        
        Args:
            page_num: Número da página (1-indexed)
            pedidos: Lista de pedidos da página
            
        Returns:
            True se salvou com sucesso, False caso contrário
        """
        cache_data = self._load_cache()
        
        if "pages" not in cache_data:
            cache_data["pages"] = {}
        
        page_key = str(page_num)
        cache_data["pages"][page_key] = {
            "fetched_at": datetime.utcnow().isoformat() + "Z",
            "pedidos": pedidos
        }
        
        return self._save_cache(cache_data)
    
    def has_page(self, page_num: int) -> bool:
        """Verifica se uma página está em cache.
        
        Args:
            page_num: Número da página (1-indexed)
            
        Returns:
            True se a página está em cache, False caso contrário
        """
        cache_data = self._load_cache()
        pages = cache_data.get("pages", {})
        return str(page_num) in pages
    
    def get_total_pages_cached(self) -> int:
        """Retorna o número total de páginas em cache.
        
        Returns:
            Número de páginas cacheadas
        """
        cache_data = self._load_cache()
        return cache_data.get("total_pages_cached", 0)
    
    def invalidate(self, page_num: Optional[int] = None) -> bool:
        """Invalida o cache de uma página específica ou de todas as páginas.
        
        Args:
            page_num: Número da página a invalidar. Se None, invalida todo o cache.
            
        Returns:
            True se invalidou com sucesso, False caso contrário
        """
        if page_num is None:
            # Invalida todo o cache
            if self.cache_file.exists():
                try:
                    self.cache_file.unlink()
                    logger.info("cache_invalidated_all")
                    return True
                except Exception as e:
                    logger.error("cache_invalidation_error", error=str(e))
                    return False
            return True
        
        # Invalida página específica
        cache_data = self._load_cache()
        pages = cache_data.get("pages", {})
        page_key = str(page_num)
        
        if page_key in pages:
            del pages[page_key]
            cache_data["pages"] = pages
            logger.info("cache_invalidated_page", page=page_num)
            return self._save_cache(cache_data)
        
        return True
    
    def get_cache_info(self) -> Dict:
        """Retorna informações sobre o cache.
        
        Returns:
            Dicionário com informações do cache
        """
        cache_data = self._load_cache()
        return {
            "last_updated": cache_data.get("last_updated"),
            "total_pages_cached": cache_data.get("total_pages_cached", 0),
            "cache_file": str(self.cache_file)
        }


"""Gerenciador de estado para rastrear último pedido processado."""

import json
import os
from pathlib import Path
from typing import Optional
from src.core.settings import settings
from src.core.logger import get_logger

logger = get_logger()


class StateManager:
    """Gerencia estado do último pedido processado."""
    
    @staticmethod
    def get_last_order_id() -> Optional[int]:
        """Retorna o último ID de pedido processado."""
        state_file = Path(settings.STATE_FILE)
        
        if not state_file.exists():
            logger.debug("state_file_not_found", file=str(state_file))
            return None
        
        try:
            with open(state_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                last_id = data.get("last_order_id")
                
                if last_id is not None:
                    return int(last_id)
                return None
                
        except json.JSONDecodeError as e:
            logger.warning("state_file_invalid_json", file=str(state_file), error=str(e))
            return None
        except Exception as e:
            logger.error("state_file_read_error", file=str(state_file), error=str(e))
            return None
    
    @staticmethod
    def save_last_order_id(order_id: int) -> bool:
        """Salva o último ID de pedido processado."""
        state_file = Path(settings.STATE_FILE)
        
        # Garante que o diretório existe
        state_file.parent.mkdir(parents=True, exist_ok=True)
        
        try:
            from datetime import datetime
            data = {
                "last_order_id": order_id,
                "updated_at": datetime.utcnow().isoformat() + "Z"
            }
            
            with open(state_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            logger.info("state_saved", last_order_id=order_id, file=str(state_file))
            return True
            
        except Exception as e:
            logger.error("state_file_write_error", file=str(state_file), error=str(e))
            return False


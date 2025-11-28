"""Configurações da aplicação usando variáveis de ambiente."""

from pydantic_settings import BaseSettings
from typing import Optional
from dotenv import load_dotenv

# Carrega variáveis de ambiente do arquivo .env
load_dotenv()


class Settings(BaseSettings):
    """Configurações da aplicação."""
    
    # Credenciais de autenticação
    MT_PREMIADO_EMAIL: str
    MT_PREMIADO_SENHA: str
    
    # URLs
    MT_PREMIADO_BASE_URL: str = "https://omtpremiado.com.br"
    MT_PREMIADO_LOGIN_URL: str = "https://omtpremiado.com.br/login"
    MT_PREMIADO_PEDIDOS_URL: str = "https://omtpremiado.com.br/pedidos"
    
    # Configurações de requisição
    REQUEST_TIMEOUT: int = 30
    MAX_RETRIES: int = 3
    RETRY_DELAY: int = 2
    
    # Configurações da API
    API_TITLE: str = "MT Premiado API Extract"
    API_VERSION: str = "1.0.0"
    API_DESCRIPTION: str = "API para extração de pedidos detalhados do MT Premiado"
    
    # Logging
    LOG_LEVEL: str = "INFO"
    
    # Debug
    DEBUG_HTML: bool = False
    DEBUG_SAVE_HTML: bool = False
    DEBUG_MODE: bool = False  # Ativa modo debug completo
    DEBUG_SCREENSHOTS: bool = False  # Salva screenshots
    DEBUG_TIMING: bool = False  # Loga tempos de operações
    DEBUG_SELECTORS: bool = False  # Loga cada seletor testado
    DEBUG_WAIT_TIMES: bool = False  # Loga tempos de espera
    DEBUG_DIR: str = "debug"  # Diretório para arquivos de debug
    
    # Playwright
    USE_PLAYWRIGHT: bool = False
    PLAYWRIGHT_HEADLESS: bool = True
    PLAYWRIGHT_TIMEOUT: int = 30000  # 30 segundos
    PLAYWRIGHT_WAIT_FOR_SELECTOR: str = ".nk-tb-item"  # Seletor para aguardar carregamento
    
    # Exportação e Estado
    EXPORT_JSON: bool = True  # Salva JSON de retorno em arquivo
    DATA_DIR: str = "data"  # Diretório para dados
    EXPORTS_DIR: str = "data/exports"  # Diretório para JSONs exportados
    STATE_FILE: str = "data/last_order_state.json"  # Arquivo de estado
    
    # CORS
    CORS_ORIGINS: str = "*"  # Origens permitidas. Use "*" para todas ou separe múltiplas por vírgula: "https://app1.com,https://app2.com"
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True


settings = Settings()


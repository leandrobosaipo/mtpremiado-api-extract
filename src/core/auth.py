"""Módulo de autenticação com sessão."""

import re
from typing import Optional
from requests import Session
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from src.core.settings import settings
from src.core.logger import get_logger
from src.core.exceptions import AuthenticationError, NetworkError

logger = get_logger()


class AuthenticatedSession:
    """Gerencia sessão autenticada com o MT Premiado."""
    
    def __init__(self):
        self.session: Optional[Session] = None
        self._csrf_token: Optional[str] = None
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(NetworkError)
    )
    def _get_csrf_token(self) -> str:
        """Obtém o token CSRF da página de login."""
        try:
            response = self.session.get(
                settings.MT_PREMIADO_LOGIN_URL,
                timeout=settings.REQUEST_TIMEOUT
            )
            response.raise_for_status()
            
            # Busca o token CSRF no HTML
            csrf_match = re.search(
                r'name=["\']_token["\']\s+value=["\']([^"\']+)["\']',
                response.text
            )
            
            if not csrf_match:
                # Tenta outro padrão comum
                csrf_match = re.search(
                    r'csrf-token["\']\s+content=["\']([^"\']+)["\']',
                    response.text
                )
            
            if not csrf_match:
                raise AuthenticationError("Token CSRF não encontrado")
            
            self._csrf_token = csrf_match.group(1)
            return self._csrf_token
            
        except Exception as e:
            logger.error("network_error", error=str(e), step="get_csrf_token")
            raise NetworkError(f"Erro ao obter CSRF token: {str(e)}")
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((NetworkError, AuthenticationError))
    )
    def login(self) -> Session:
        """Realiza login e retorna sessão autenticada."""
        self.session = Session()
        
        try:
            # Obtém CSRF token
            csrf_token = self._get_csrf_token()
            
            # Prepara dados do login
            login_data = {
                "_token": csrf_token,
                "email": settings.MT_PREMIADO_EMAIL,
                "password": settings.MT_PREMIADO_SENHA,
            }
            
            # Faz login
            response = self.session.post(
                settings.MT_PREMIADO_LOGIN_URL,
                data=login_data,
                timeout=settings.REQUEST_TIMEOUT,
                allow_redirects=True
            )
            
            # Verifica se login foi bem-sucedido
            if response.status_code != 200 or "login" in response.url.lower():
                logger.error(
                    "login_failed",
                    status_code=response.status_code,
                    url=response.url
                )
                raise AuthenticationError("Falha ao autenticar")
            
            logger.info("login_success", email=settings.MT_PREMIADO_EMAIL)
            return self.session
            
        except AuthenticationError:
            raise
        except Exception as e:
            logger.error("login_failed", error=str(e))
            raise AuthenticationError(f"Erro durante login: {str(e)}")
    
    def get_session(self) -> Session:
        """Retorna a sessão autenticada."""
        if self.session is None:
            self.login()
        return self.session
    
    def close(self):
        """Fecha a sessão."""
        if self.session:
            self.session.close()
            self.session = None


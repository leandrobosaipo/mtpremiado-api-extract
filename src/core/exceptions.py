"""Exceções customizadas da aplicação."""

from fastapi import HTTPException, status


class AuthenticationError(HTTPException):
    """Erro de autenticação."""
    
    def __init__(self, detail: str = "Falha ao autenticar"):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail
        )


class ScrapingError(Exception):
    """Erro durante o scraping."""
    pass


class NetworkError(Exception):
    """Erro de rede."""
    pass


class ParsingError(Exception):
    """Erro ao fazer parse dos dados."""
    pass


"""Gerenciamento de sessão para scraping."""

from contextlib import contextmanager
from typing import Generator
from requests import Session

from src.core.auth import AuthenticatedSession
from src.core.logger import get_logger

logger = get_logger()


@contextmanager
def get_authenticated_session() -> Generator[Session, None, None]:
    """Context manager para sessão autenticada."""
    auth_session = AuthenticatedSession()
    try:
        session = auth_session.get_session()
        yield session
    finally:
        auth_session.close()
        logger.debug("session_closed")


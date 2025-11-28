"""Testes para scraper de listagem."""

import pytest
from unittest.mock import Mock, patch
from bs4 import BeautifulSoup

from src.scraper.listagem import ListagemScraper
from src.core.exceptions import NetworkError


@pytest.fixture
def mock_session():
    """Mock de sessão."""
    session = Mock()
    return session


@pytest.fixture
def scraper(mock_session):
    """Instância do scraper."""
    return ListagemScraper(mock_session)


def test_extract_pedido_from_row(scraper):
    """Testa extração de pedido de uma linha."""
    html = """
    <tr>
        <td>1308</td>
        <td>1 hora atrás</td>
        <td>Aprovado</td>
        <td>BIZ 0KM</td>
        <td>10000000 bilhetes</td>
        <td>Nome Cliente</td>
        <td>+55 66 99999-9999</td>
        <td>100 bilhetes</td>
        <td>R$ 10,00</td>
        <td><a href="/pedidos/1308">Detalhes</a></td>
    </tr>
    """
    soup = BeautifulSoup(html, "html.parser")
    row = soup.select_one("tr")
    
    pedido = scraper._extract_pedido_from_row(row)
    
    assert pedido is not None
    assert pedido["id"] is not None


def test_has_more_pages(scraper):
    """Testa verificação de mais páginas."""
    html_with_next = """
    <div class="pagination">
        <a class="next" href="?page=2">Próxima</a>
    </div>
    """
    soup = BeautifulSoup(html_with_next, "html.parser")
    
    assert scraper._has_more_pages(soup) is True


def test_fetch_page_network_error(scraper):
    """Testa tratamento de erro de rede."""
    scraper.session.get.side_effect = Exception("Network error")
    
    with pytest.raises(NetworkError):
        scraper._fetch_page(1)


"""Testes para scraper de detalhes."""

import pytest
from unittest.mock import Mock
from bs4 import BeautifulSoup

from src.scraper.detalhes import DetalhesScraper
from src.core.exceptions import NetworkError


@pytest.fixture
def mock_session():
    """Mock de sessão."""
    session = Mock()
    return session


@pytest.fixture
def scraper(mock_session):
    """Instância do scraper."""
    return DetalhesScraper(mock_session)


def test_extract_detalhes_success(scraper):
    """Testa extração de detalhes com sucesso."""
    html = """
    <html>
        <body>
            <div class="pedido-detalhes">
                <p>Data: 21/11/2025 21:15:25</p>
                <p>Email: [email protected]</p>
                <p>Telefone: +55 66 99999-9999</p>
                <p>CPF: 026.750.491-82</p>
                <p>Nascimento: 24/07/1994</p>
                <p>Subtotal: R$ 0,10</p>
                <p>Total: R$ 0,10</p>
            </div>
        </body>
    </html>
    """
    
    scraper.session.get.return_value.status_code = 200
    scraper.session.get.return_value.text = html
    scraper.session.get.return_value.raise_for_status = Mock()
    
    detalhes = scraper.extract_detalhes("https://omtpremiado.com.br/pedidos/1308")
    
    assert detalhes is not None
    assert "detalhe_email" in detalhes
    assert "detalhe_cpf" in detalhes


def test_extract_detalhes_error(scraper):
    """Testa tratamento de erro ao extrair detalhes."""
    scraper.session.get.side_effect = Exception("Network error")
    
    detalhes = scraper.extract_detalhes("https://omtpremiado.com.br/pedidos/1308")
    
    # Deve retornar detalhes vazios, não lançar exceção
    assert detalhes is not None
    assert detalhes["detalhe_email"] == ""


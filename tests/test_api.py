"""Testes para API."""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, Mock

from src.main import app
from src.core.exceptions import AuthenticationError

client = TestClient(app)


def test_root():
    """Testa endpoint raiz."""
    response = client.get("/")
    assert response.status_code == 200
    assert "name" in response.json()
    assert "version" in response.json()


def test_health():
    """Testa endpoint de health check."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


@patch("src.api.routes.pedidos_routes.PedidosController")
def test_get_pedidos_full_success(mock_controller):
    """Testa endpoint de pedidos com sucesso."""
    mock_response = Mock()
    mock_response.total = 1
    mock_response.gerado_em = "2025-11-22T04:12:55Z"
    mock_response.pedidos = []
    
    mock_controller.return_value.extract_all_pedidos_full.return_value = mock_response
    
    response = client.get("/api/pedidos/full")
    
    assert response.status_code == 200
    assert "total" in response.json()
    assert "pedidos" in response.json()


@patch("src.api.routes.pedidos_routes.PedidosController")
def test_get_pedidos_full_authentication_error(mock_controller):
    """Testa endpoint com erro de autenticação."""
    mock_controller.return_value.extract_all_pedidos_full.side_effect = AuthenticationError()
    
    response = client.get("/api/pedidos/full")
    
    assert response.status_code == 401
    assert "Falha ao autenticar" in response.json()["detail"]


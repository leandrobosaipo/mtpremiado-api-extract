"""Schemas para pedidos."""

from typing import Optional
from pydantic import BaseModel, Field
from datetime import datetime


class PedidoDetalhesSchema(BaseModel):
    """Schema para detalhes de um pedido."""
    
    id: Optional[int] = None
    criado: Optional[str] = ""
    status: Optional[str] = ""
    sorteio: Optional[str] = ""
    bilhetes_totais_sorteio: Optional[str] = ""
    cliente: Optional[str] = ""
    telefone: Optional[str] = ""
    qtd_bilhetes: Optional[str] = ""
    valor: Optional[str] = ""
    detalhes_url: Optional[str] = ""
    detalhe_data_hora: Optional[str] = ""
    detalhe_email: Optional[str] = ""
    detalhe_telefone: Optional[str] = ""
    detalhe_cpf: Optional[str] = ""
    detalhe_nascimento: Optional[str] = ""
    detalhe_data_compra: Optional[str] = ""
    detalhe_pagamento_id: Optional[str] = ""
    detalhe_subtotal: Optional[str] = ""
    detalhe_descontos: Optional[str] = ""
    detalhe_total: Optional[str] = ""
    
    class Config:
        json_schema_extra = {
            "example": {
                "id": 1308,
                "criado": "1 hora atrás",
                "status": "Aprovado",
                "sorteio": "BIZ 0KM",
                "bilhetes_totais_sorteio": "10000000 bilhetes",
                "cliente": "Nome",
                "telefone": "+55 66 99999-9999",
                "qtd_bilhetes": "100 bilhetes",
                "valor": "R$ 10,00",
                "detalhes_url": "https://omtpremiado.com.br/pedidos/1308",
                "detalhe_data_hora": "21/11/2025 21:15:25",
                "detalhe_email": "[email protected]",
                "detalhe_telefone": "+55 66 99999-9999",
                "detalhe_cpf": "026.750.491-82",
                "detalhe_nascimento": "24/07/1994",
                "detalhe_data_compra": "21/11/2025",
                "detalhe_pagamento_id": "ABC123",
                "detalhe_subtotal": "R$ 0,10",
                "detalhe_descontos": "R$ 0,00",
                "detalhe_total": "R$ 0,10"
            }
        }


class PedidosResponseSchema(BaseModel):
    """Schema de resposta com todos os pedidos."""
    
    total: int = Field(..., description="Total de pedidos extraídos")
    gerado_em: str = Field(..., description="Data e hora da geração em ISO 8601")
    pedidos: list[PedidoDetalhesSchema] = Field(..., description="Lista de pedidos")
    
    class Config:
        json_schema_extra = {
            "example": {
                "total": 1306,
                "gerado_em": "2025-11-22T04:12:55Z",
                "pedidos": [
                    {
                        "id": 1308,
                        "criado": "1 hora atrás",
                        "status": "Aprovado",
                        "sorteio": "BIZ 0KM",
                        "bilhetes_totais_sorteio": "10000000 bilhetes",
                        "cliente": "Nome",
                        "telefone": "+55 66 99999-9999",
                        "qtd_bilhetes": "100 bilhetes",
                        "valor": "R$ 10,00",
                        "detalhes_url": "https://omtpremiado.com.br/pedidos/1308",
                        "detalhe_data_hora": "21/11/2025 21:15:25",
                        "detalhe_email": "[email protected]",
                        "detalhe_telefone": "+55 66 99999-9999",
                        "detalhe_cpf": "026.750.491-82",
                        "detalhe_nascimento": "24/07/1994",
                        "detalhe_data_compra": "21/11/2025",
                        "detalhe_pagamento_id": "ABC123",
                        "detalhe_subtotal": "R$ 0,10",
                        "detalhe_descontos": "R$ 0,00",
                        "detalhe_total": "R$ 0,10"
                    }
                ]
            }
        }


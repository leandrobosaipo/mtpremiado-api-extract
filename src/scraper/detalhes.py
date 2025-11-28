"""Scraper para detalhes de um pedido."""

from typing import Dict, Optional
from requests import Session
from bs4 import BeautifulSoup
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from src.core.settings import settings
from src.core.logger import get_logger
from src.core.exceptions import NetworkError, ParsingError
from src.scraper.parser import HTMLParser

logger = get_logger()
parser = HTMLParser()


class DetalhesScraper:
    """Scraper para extrair detalhes de um pedido."""
    
    def __init__(self, session: Session):
        self.session = session
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(NetworkError)
    )
    def extract_detalhes(self, detalhes_url: str) -> Dict:
        """Extrai detalhes completos de um pedido."""
        try:
            response = self.session.get(
                detalhes_url,
                timeout=settings.REQUEST_TIMEOUT
            )
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, "html.parser")
            
            # Extrai campos de detalhes (ajustar seletores conforme HTML real)
            detalhes = {
                "detalhe_data_hora": self._extract_data_hora(soup),
                "detalhe_email": self._extract_email(soup),
                "detalhe_telefone": self._extract_telefone(soup),
                "detalhe_cpf": self._extract_cpf(soup),
                "detalhe_nascimento": self._extract_nascimento(soup),
                "detalhe_data_compra": self._extract_data_compra(soup),
                "detalhe_pagamento_id": self._extract_pagamento_id(soup),
                "detalhe_subtotal": self._extract_subtotal(soup),
                "detalhe_descontos": self._extract_descontos(soup),
                "detalhe_total": self._extract_total(soup),
            }
            
            logger.info("order_detail_success", url=detalhes_url)
            return detalhes
            
        except Exception as e:
            logger.error("order_detail_failed", error=str(e), url=detalhes_url)
            # Retorna detalhes vazios em caso de erro
            return {
                "detalhe_data_hora": "",
                "detalhe_email": "",
                "detalhe_telefone": "",
                "detalhe_cpf": "",
                "detalhe_nascimento": "",
                "detalhe_data_compra": "",
                "detalhe_pagamento_id": "",
                "detalhe_subtotal": "",
                "detalhe_descontos": "",
                "detalhe_total": "",
            }
    
    def _extract_data_hora(self, soup: BeautifulSoup) -> str:
        """Extrai data e hora do pedido."""
        # Tenta vários seletores comuns
        selectors = [
            "[data-field='data_hora']",
            ".data-hora",
            ".pedido-data",
        ]
        for selector in selectors:
            text = parser.extract_text(soup, selector)
            if text:
                return parser.extract_datetime(text) or parser.extract_date(text)
        
        # Tenta encontrar por texto que contenha "Data"
        text = soup.get_text()
        return parser.extract_datetime(text) or parser.extract_date(text)
    
    def _extract_email(self, soup: BeautifulSoup) -> str:
        """Extrai email do cliente."""
        # Email está em .invoice-contact-info ul.list-plain li:first-child span
        email_elem = soup.select_one(".invoice-contact-info ul.list-plain li:first-child span")
        if email_elem:
            email_text = email_elem.get_text(strip=True)
            email = parser.extract_email(email_text)
            if email:
                return email
        
        # Fallback: tenta sem ul.list-plain
        email_elem = soup.select_one(".invoice-contact-info li:first-child span")
        if email_elem:
            email_text = email_elem.get_text(strip=True)
            email = parser.extract_email(email_text)
            if email:
                return email
        
        # Fallback: busca em todo o texto
        text = soup.get_text()
        return parser.extract_email(text) or ""
    
    def _extract_telefone(self, soup: BeautifulSoup) -> str:
        """Extrai telefone do cliente."""
        text = soup.get_text()
        phone = parser.extract_phone(text)
        if not phone:
            phone = parser.extract_text(soup, ".telefone, [data-field='telefone']")
        return phone
    
    def _extract_cpf(self, soup: BeautifulSoup) -> str:
        """Extrai CPF do cliente."""
        text = soup.get_text()
        cpf = parser.extract_cpf(text)
        if not cpf:
            cpf = parser.extract_text(soup, ".cpf, [data-field='cpf']")
        return cpf
    
    def _extract_nascimento(self, soup: BeautifulSoup) -> str:
        """Extrai data de nascimento."""
        text = soup.get_text()
        nascimento = parser.extract_date(text)
        if not nascimento:
            nascimento = parser.extract_text(soup, ".nascimento, [data-field='nascimento']")
        return nascimento
    
    def _extract_data_compra(self, soup: BeautifulSoup) -> str:
        """Extrai data de compra."""
        text = soup.get_text()
        data = parser.extract_date(text)
        if not data:
            data = parser.extract_text(soup, ".data-compra, [data-field='data_compra']")
        return data
    
    def _extract_pagamento_id(self, soup: BeautifulSoup) -> str:
        """Extrai ID do pagamento."""
        return parser.extract_text(
            soup,
            ".pagamento-id, [data-field='pagamento_id'], .transaction-id"
        )
    
    def _extract_subtotal(self, soup: BeautifulSoup) -> str:
        """Extrai subtotal."""
        # table.invoice-bills table tfoot tr:first-child td:last-child
        subtotal_elem = soup.select_one("table.invoice-bills table tfoot tr:first-child td:last-child")
        if not subtotal_elem:
            # Fallback: tenta sem .invoice-bills
            subtotal_elem = soup.select_one("table tfoot tr:first-child td:last-child")
        
        if subtotal_elem:
            return subtotal_elem.get_text(strip=True)
        
        # Fallback
        text = soup.get_text()
        return parser.extract_money(text) or ""
    
    def _extract_descontos(self, soup: BeautifulSoup) -> str:
        """Extrai descontos."""
        # table.invoice-bills table tfoot tr:nth-child(2) td:last-child
        descontos_elem = soup.select_one("table.invoice-bills table tfoot tr:nth-child(2) td:last-child")
        if not descontos_elem:
            # Fallback: tenta sem .invoice-bills
            descontos_elem = soup.select_one("table tfoot tr:nth-child(2) td:last-child")
        
        if descontos_elem:
            return descontos_elem.get_text(strip=True) or "R$ 0,00"
        
        return "R$ 0,00"
    
    def _extract_total(self, soup: BeautifulSoup) -> str:
        """Extrai total."""
        # table.invoice-bills table tfoot tr:last-child td:last-child
        total_elem = soup.select_one("table.invoice-bills table tfoot tr:last-child td:last-child")
        if not total_elem:
            # Fallback: tenta sem .invoice-bills
            total_elem = soup.select_one("table tfoot tr:last-child td:last-child")
        
        if total_elem:
            return total_elem.get_text(strip=True)
        
        # Fallback
        text = soup.get_text()
        return parser.extract_money(text) or ""


"""Parser para extrair dados do HTML."""

import re
from typing import Dict, Optional
from bs4 import BeautifulSoup

from src.core.logger import get_logger
from src.core.exceptions import ParsingError

logger = get_logger()


class HTMLParser:
    """Parser para extrair dados do HTML."""
    
    @staticmethod
    def extract_text(soup: BeautifulSoup, selector: str, default: str = "") -> str:
        """Extrai texto de um seletor CSS."""
        try:
            element = soup.select_one(selector)
            return element.get_text(strip=True) if element else default
        except Exception:
            return default
    
    @staticmethod
    def extract_attribute(
        soup: BeautifulSoup,
        selector: str,
        attribute: str,
        default: str = ""
    ) -> str:
        """Extrai atributo de um elemento."""
        try:
            element = soup.select_one(selector)
            return element.get(attribute, default) if element else default
        except Exception:
            return default
    
    @staticmethod
    def clean_text(text: str) -> str:
        """Limpa texto removendo espaços extras."""
        return " ".join(text.split()) if text else ""
    
    @staticmethod
    def extract_cpf(text: str) -> str:
        """Extrai CPF formatado do texto."""
        cpf_match = re.search(r'\d{3}\.\d{3}\.\d{3}-\d{2}', text)
        return cpf_match.group(0) if cpf_match else ""
    
    @staticmethod
    def extract_phone(text: str) -> str:
        """Extrai telefone formatado do texto."""
        phone_match = re.search(r'\+?\d{2}[\s.-]?\d{4,5}[\s.-]?\d{4}', text)
        return phone_match.group(0) if phone_match else ""
    
    @staticmethod
    def extract_email(text: str) -> str:
        """Extrai email do texto."""
        email_match = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', text)
        return email_match.group(0) if email_match else ""
    
    @staticmethod
    def extract_date(text: str) -> str:
        """Extrai data formatada do texto."""
        date_match = re.search(r'\d{2}/\d{2}/\d{4}', text)
        return date_match.group(0) if date_match else ""
    
    @staticmethod
    def extract_datetime(text: str) -> str:
        """Extrai data e hora formatada do texto."""
        datetime_match = re.search(r'\d{2}/\d{2}/\d{4}\s+\d{2}:\d{2}:\d{2}', text)
        return datetime_match.group(0) if datetime_match else ""
    
    @staticmethod
    def extract_money(text: str) -> str:
        """Extrai valor monetário formatado do texto."""
        money_match = re.search(r'R\$\s*[\d.,]+', text)
        return money_match.group(0) if money_match else ""


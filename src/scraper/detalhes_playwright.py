"""Scraper para detalhes de um pedido usando Playwright."""

from typing import Dict
from playwright.async_api import Page, TimeoutError as PlaywrightTimeoutError
from bs4 import BeautifulSoup

from src.core.settings import settings
from src.core.logger import get_logger
from src.core.exceptions import NetworkError, ParsingError
from src.scraper.parser import HTMLParser
from src.scraper.debug_helper import DebugHelper

logger = get_logger()
parser = HTMLParser()


class DetalhesScraperPlaywright:
    """Scraper para extrair detalhes de um pedido usando Playwright."""
    
    def __init__(self, page: Page):
        self.page = page
    
    async def extract_detalhes(self, detalhes_url: str) -> Dict:
        """Extrai detalhes completos de um pedido."""
        start_time = DebugHelper.start_timer("extract_detalhes")
        
        try:
            DebugHelper.log_step("extract_detalhes_start", {"url": detalhes_url})
            logger.debug("navigating_to_details", url=detalhes_url)
            
            await self.page.goto(
                detalhes_url,
                wait_until="domcontentloaded",
                timeout=settings.PLAYWRIGHT_TIMEOUT
            )
            
            DebugHelper.log_step("extract_detalhes_goto_complete", {"url": self.page.url})
            
            # Screenshot após carregar página
            await DebugHelper.take_screenshot(self.page, "extract_detalhes_after_goto", "after_goto")
            
            # Aguarda elementos principais carregarem
            invoice_head_found = False
            try:
                await self.page.wait_for_selector(
                    ".invoice-head",
                    timeout=10000,
                    state="visible"
                )
                invoice_head_found = True
                DebugHelper.log_step("extract_detalhes_selector_found", {"selector": ".invoice-head"})
            except PlaywrightTimeoutError:
                DebugHelper.log_step("extract_detalhes_selector_timeout", {"selector": ".invoice-head"})
                logger.warning("wait_selector_timeout", selector=".invoice-head")
            
            # Verifica elementos esperados
            invoice_head_check = await DebugHelper.check_element_exists(self.page, ".invoice-head", "invoice_head")
            invoice_contact_check = await DebugHelper.check_element_exists(self.page, ".invoice-contact-info", "invoice_contact")
            table_check = await DebugHelper.check_element_exists(self.page, "table tfoot", "table_footer")
            
            DebugHelper.log_step("extract_detalhes_elements_check", {
                "invoice_head_exists": invoice_head_check.get("exists", False),
                "invoice_contact_exists": invoice_contact_check.get("exists", False),
                "table_footer_exists": table_check.get("exists", False)
            })
            
            # Aguarda um pouco mais para garantir que Livewire carregou
            await self.page.wait_for_timeout(2000)  # 2 segundos
            
            # Screenshot após esperar por elementos
            await DebugHelper.take_screenshot(self.page, "extract_detalhes_after_wait", "after_wait")
            
            soup = BeautifulSoup(await self.page.content(), "html.parser")
            
            DebugHelper.log_step("extract_detalhes_html_parsed", {"html_size": len(str(soup))})
            
            # Extrai campos de detalhes com seletores corretos
            detalhes = {}
            
            DebugHelper.log_step("extract_detalhes_extracting_fields")
            detalhes["detalhe_data_hora"] = self._extract_data_hora(soup)
            DebugHelper.log_step("extract_detalhes_field_extracted", {"field": "data_hora", "value": detalhes["detalhe_data_hora"]})
            
            detalhes["detalhe_email"] = self._extract_email(soup)
            DebugHelper.log_step("extract_detalhes_field_extracted", {"field": "email", "value": detalhes["detalhe_email"]})
            
            detalhes["detalhe_telefone"] = self._extract_telefone(soup)
            DebugHelper.log_step("extract_detalhes_field_extracted", {"field": "telefone", "value": detalhes["detalhe_telefone"]})
            
            detalhes["detalhe_cpf"] = self._extract_cpf(soup)
            DebugHelper.log_step("extract_detalhes_field_extracted", {"field": "cpf", "value": detalhes["detalhe_cpf"]})
            
            detalhes["detalhe_nascimento"] = self._extract_nascimento(soup)
            DebugHelper.log_step("extract_detalhes_field_extracted", {"field": "nascimento", "value": detalhes["detalhe_nascimento"]})
            
            detalhes["detalhe_data_compra"] = self._extract_data_compra(soup)
            DebugHelper.log_step("extract_detalhes_field_extracted", {"field": "data_compra", "value": detalhes["detalhe_data_compra"]})
            
            detalhes["detalhe_pagamento_id"] = self._extract_pagamento_id(soup)
            DebugHelper.log_step("extract_detalhes_field_extracted", {"field": "pagamento_id", "value": detalhes["detalhe_pagamento_id"]})
            
            detalhes["detalhe_subtotal"] = self._extract_subtotal(soup)
            DebugHelper.log_step("extract_detalhes_field_extracted", {"field": "subtotal", "value": detalhes["detalhe_subtotal"]})
            
            detalhes["detalhe_descontos"] = self._extract_descontos(soup)
            DebugHelper.log_step("extract_detalhes_field_extracted", {"field": "descontos", "value": detalhes["detalhe_descontos"]})
            
            detalhes["detalhe_total"] = self._extract_total(soup)
            DebugHelper.log_step("extract_detalhes_field_extracted", {"field": "total", "value": detalhes["detalhe_total"]})
            
            DebugHelper.log_step("extract_detalhes_complete", {"fields_extracted": len(detalhes)})
            DebugHelper.end_timer(start_time, "extract_detalhes", {"success": True, "url": detalhes_url})
            
            logger.info("order_detail_success", url=detalhes_url)
            return detalhes
            
        except PlaywrightTimeoutError as e:
            DebugHelper.end_timer(start_time, "extract_detalhes", {"success": False, "error": str(e)})
            await DebugHelper.take_screenshot(self.page, "extract_detalhes_timeout", "timeout")
            await DebugHelper.save_html(self.page, "extract_detalhes_timeout", "timeout")
            logger.error("order_detail_timeout", error=str(e), url=detalhes_url)
            return self._empty_detalhes()
        except Exception as e:
            DebugHelper.end_timer(start_time, "extract_detalhes", {"success": False, "error": str(e)})
            await DebugHelper.take_screenshot(self.page, "extract_detalhes_error", "error")
            await DebugHelper.save_html(self.page, "extract_detalhes_error", "error")
            logger.error("order_detail_failed", error=str(e), url=detalhes_url)
            return self._empty_detalhes()
    
    def _empty_detalhes(self) -> Dict:
        """Retorna detalhes vazios em caso de erro."""
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
        # .nk-block-des .list-inline li span
        data_elem = soup.select_one(".nk-block-des .list-inline li span.text-base")
        if data_elem:
            return parser.extract_datetime(data_elem.get_text()) or parser.extract_date(data_elem.get_text()) or data_elem.get_text(strip=True)
        
        # Fallback: busca em todo o texto
        text = soup.get_text()
        return parser.extract_datetime(text) or parser.extract_date(text) or ""
    
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
        # #customer-phone
        phone_elem = soup.select_one("#customer-phone")
        if phone_elem:
            phone_text = phone_elem.get_text(strip=True)
            return parser.extract_phone(phone_text) or phone_text
        
        # Fallback: busca em todo o texto
        text = soup.get_text()
        return parser.extract_phone(text) or ""
    
    def _extract_cpf(self, soup: BeautifulSoup) -> str:
        """Extrai CPF do cliente."""
        # #customer-cpf
        cpf_elem = soup.select_one("#customer-cpf")
        if cpf_elem:
            cpf_text = cpf_elem.get_text(strip=True)
            return parser.extract_cpf(cpf_text) or cpf_text
        
        # Fallback: busca em todo o texto
        text = soup.get_text()
        return parser.extract_cpf(text) or ""
    
    def _extract_nascimento(self, soup: BeautifulSoup) -> str:
        """Extrai data de nascimento."""
        # #customer-birth
        birth_elem = soup.select_one("#customer-birth")
        if birth_elem:
            birth_text = birth_elem.get_text(strip=True)
            return parser.extract_date(birth_text) or birth_text
        
        # Fallback: busca em todo o texto
        text = soup.get_text()
        return parser.extract_date(text) or ""
    
    def _extract_data_compra(self, soup: BeautifulSoup) -> str:
        """Extrai data de compra."""
        # .invoice-desc .invoice-date span:last-child
        date_elem = soup.select_one(".invoice-desc .invoice-date span:last-child")
        if date_elem:
            date_text = date_elem.get_text(strip=True)
            return parser.extract_date(date_text) or date_text
        
        # Fallback: busca em todo o texto
        text = soup.get_text()
        return parser.extract_date(text) or ""
    
    def _extract_pagamento_id(self, soup: BeautifulSoup) -> str:
        """Extrai ID do pagamento."""
        # .invoice-desc .invoice-id span:last-child
        payment_elem = soup.select_one(".invoice-desc .invoice-id span:last-child")
        if payment_elem:
            return payment_elem.get_text(strip=True)
        
        return ""
    
    def _extract_subtotal(self, soup: BeautifulSoup) -> str:
        """Extrai subtotal."""
        # table.invoice-bills table tfoot tr:first-child td:last-child - pega texto completo do td
        subtotal_elem = soup.select_one("table.invoice-bills table tfoot tr:first-child td:last-child")
        if not subtotal_elem:
            # Fallback: tenta sem .invoice-bills
            subtotal_elem = soup.select_one("table tfoot tr:first-child td:last-child")
        
        if subtotal_elem:
            # Pega todo o texto do td (inclui "R$ 10,00")
            subtotal_text = subtotal_elem.get_text(strip=True)
            # Remove espaços extras e retorna
            return subtotal_text
        
        # Fallback: busca "Subtotal" no texto
        text = soup.get_text()
        return parser.extract_money(text) or ""
    
    def _extract_descontos(self, soup: BeautifulSoup) -> str:
        """Extrai descontos."""
        # table.invoice-bills table tfoot tr:nth-child(2) td:last-child - pega texto completo do td
        descontos_elem = soup.select_one("table.invoice-bills table tfoot tr:nth-child(2) td:last-child")
        if not descontos_elem:
            # Fallback: tenta sem .invoice-bills
            descontos_elem = soup.select_one("table tfoot tr:nth-child(2) td:last-child")
        
        if descontos_elem:
            descontos_text = descontos_elem.get_text(strip=True)
            return descontos_text or "R$ 0,00"
        
        return "R$ 0,00"
    
    def _extract_total(self, soup: BeautifulSoup) -> str:
        """Extrai total."""
        # table.invoice-bills table tfoot tr:last-child td:last-child - pega texto completo do td
        total_elem = soup.select_one("table.invoice-bills table tfoot tr:last-child td:last-child")
        if not total_elem:
            # Fallback: tenta sem .invoice-bills
            total_elem = soup.select_one("table tfoot tr:last-child td:last-child")
        
        if total_elem:
            total_text = total_elem.get_text(strip=True)
            return total_text
        
        # Fallback: busca "Grand Total" ou "Total" no texto
        text = soup.get_text()
        return parser.extract_money(text) or ""

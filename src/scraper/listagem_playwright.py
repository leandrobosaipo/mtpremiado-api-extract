"""Scraper para listagem de pedidos usando Playwright."""

import re
from typing import List, Dict, Optional
from playwright.async_api import Page, TimeoutError as PlaywrightTimeoutError
from bs4 import BeautifulSoup

from src.core.settings import settings
from src.core.logger import get_logger
from src.core.exceptions import NetworkError, ParsingError
from src.scraper.parser import HTMLParser
from src.scraper.debug_helper import DebugHelper

logger = get_logger()
parser = HTMLParser()


class ListagemScraperPlaywright:
    """Scraper para extrair listagem de pedidos usando Playwright."""
    
    def __init__(self, page: Page):
        self.page = page
        self.base_url = settings.MT_PREMIADO_PEDIDOS_URL
    
    async def _fetch_page(self, page_num: int) -> BeautifulSoup:
        """Busca uma página de pedidos e retorna BeautifulSoup."""
        start_time = DebugHelper.start_timer(f"fetch_page_{page_num}")
        
        try:
            url = f"{self.base_url}?page={page_num}"
            DebugHelper.log_step("fetch_page_start", {"page": page_num, "url": url})
            logger.debug("navigating_to_page", page=page_num, url=url)
            
            await self.page.goto(
                url,
                wait_until="domcontentloaded",
                timeout=settings.PLAYWRIGHT_TIMEOUT
            )
            
            DebugHelper.log_step("fetch_page_goto_complete", {"page": page_num, "url": self.page.url})
            
            # Screenshot após goto
            await DebugHelper.take_screenshot(self.page, f"fetch_page_{page_num}_after_goto", "after_goto")
            
            # Aguarda elementos de pedidos carregarem
            selector_found = False
            try:
                await self.page.wait_for_selector(
                    ".nk-tb-item:not(.nk-tb-head)",
                    timeout=10000,  # 10 segundos
                    state="visible"
                )
                selector_found = True
                DebugHelper.log_step("fetch_page_selector_found", {"page": page_num, "selector": ".nk-tb-item"})
            except PlaywrightTimeoutError:
                DebugHelper.log_step("fetch_page_selector_timeout", {"page": page_num, "selector": ".nk-tb-item"})
                logger.warning("wait_selector_timeout", selector=".nk-tb-item")
                # Continua mesmo se timeout - pode não haver pedidos
            
            # Verifica múltiplos elementos esperados
            sidebar_check = await DebugHelper.check_element_exists(self.page, ".nk-sidebar", "sidebar")
            menu_check = await DebugHelper.check_element_exists(self.page, ".nk-menu", "menu")
            table_check = await DebugHelper.check_element_exists(self.page, ".nk-tb-item", "table_items")
            
            DebugHelper.log_step("fetch_page_elements_check", {
                "page": page_num,
                "sidebar_exists": sidebar_check.get("exists", False),
                "menu_exists": menu_check.get("exists", False),
                "table_items_exists": table_check.get("exists", False),
                "table_items_count": table_check.get("count", 0)
            })
            
            # Aguarda um pouco mais para garantir que Livewire carregou
            await self.page.wait_for_timeout(2000)  # 2 segundos
            
            # Screenshot após esperar por elementos
            await DebugHelper.take_screenshot(self.page, f"fetch_page_{page_num}_after_wait", "after_wait")
            
            html_content = await self.page.content()
            html_size = len(html_content)
            
            DebugHelper.log_step("fetch_page_html_fetched", {"page": page_num, "html_size": html_size})
            logger.debug("html_fetched", page=page_num, html_size=html_size, url=url)
            
            if settings.DEBUG_HTML:
                preview = html_content[:500].replace("\n", " ").replace("\r", "")
                logger.info("html_preview", page=page_num, preview=preview)
            
            # Salva HTML usando DebugHelper
            await DebugHelper.save_html(self.page, f"page_{page_num}", f"page_{page_num}")
            
            DebugHelper.end_timer(start_time, f"fetch_page_{page_num}", {
                "success": True,
                "html_size": html_size,
                "selector_found": selector_found
            })
            
            return BeautifulSoup(html_content, "html.parser")
            
        except PlaywrightTimeoutError as e:
            DebugHelper.end_timer(start_time, f"fetch_page_{page_num}", {"success": False, "error": str(e)})
            await DebugHelper.take_screenshot(self.page, f"fetch_page_{page_num}_timeout", "timeout")
            await DebugHelper.save_html(self.page, f"fetch_page_{page_num}_timeout", "timeout")
            logger.error("network_error", error=str(e), page=page_num)
            raise NetworkError(f"Timeout ao buscar página {page_num}: {str(e)}")
        except Exception as e:
            DebugHelper.end_timer(start_time, f"fetch_page_{page_num}", {"success": False, "error": str(e)})
            await DebugHelper.take_screenshot(self.page, f"fetch_page_{page_num}_error", "error")
            await DebugHelper.save_html(self.page, f"fetch_page_{page_num}_error", "error")
            logger.error("network_error", error=str(e), page=page_num)
            raise NetworkError(f"Erro ao buscar página {page_num}: {str(e)}")
    
    def _extract_pedido_from_row(self, row) -> Optional[Dict]:
        """Extrai dados de um pedido de uma linha da tabela."""
        try:
            # ID do pedido - múltiplas tentativas
            pedido_id = None
            
            # 1. Tenta checkbox com value
            checkbox = row.select_one("input.model-id-checkbox")
            if checkbox:
                pedido_id = checkbox.get("value")
                if pedido_id:
                    try:
                        pedido_id = int(pedido_id)
                        if settings.DEBUG_HTML:
                            print(f"[DEBUG] Extraído ID {pedido_id} do checkbox")
                    except:
                        pass
            
            # 2. Tenta link com texto #1313
            if not pedido_id:
                link = row.select_one(".nk-tb-col:first-child .tb-lead a")
                if link:
                    link_text = link.get_text(strip=True)
                    id_match = re.search(r'#?(\d+)', link_text)
                    if id_match:
                        try:
                            pedido_id = int(id_match.group(1))
                            if settings.DEBUG_HTML:
                                print(f"[DEBUG] Extraído ID {pedido_id} do link")
                        except:
                            pedido_id = id_match.group(1)
                            if settings.DEBUG_HTML:
                                print(f"[DEBUG] Extraído ID {pedido_id} do link (string)")
            
            # Data - pega do data-original-title do tooltip
            data_elem = row.select_one(".nk-tb-col.tb-col-md .tb-lead[data-original-title]")
            data_criado = ""
            if data_elem:
                data_criado = data_elem.get("data-original-title", "").strip()
                if not data_criado:
                    data_criado = data_elem.get_text(strip=True)
            
            # Status - texto do badge ou classe do dot
            status = ""
            badge = row.select_one(".nk-tb-col.tb-col-xl .badge")
            if badge:
                status = badge.get_text(strip=True)
            else:
                dot = row.select_one(".nk-tb-col.tb-col-xl .dot")
                if dot:
                    status_classes = dot.get("class", [])
                    if "bg-success" in status_classes:
                        status = "Aprovado"
                    elif "bg-danger" in status_classes:
                        status = "Cancelado"
                    elif "bg-warning" in status_classes:
                        status = "Pendente"
            
            # Sorteio - primeiro .tb-lead dentro de .user-info na coluna de sorteio
            sorteio_col = row.select_one(".nk-tb-col .user-card .user-info")
            sorteio = ""
            if sorteio_col:
                sorteio_elem = sorteio_col.select_one(".tb-lead")
                if sorteio_elem:
                    sorteio = sorteio_elem.get_text(strip=True)
            
            # Cliente - primeiro .tb-lead dentro de .user-info na coluna de cliente
            cliente_cols = row.select(".nk-tb-col .user-card .user-info")
            cliente = ""
            if len(cliente_cols) > 1:  # Segundo user-info é o cliente
                cliente_elem = cliente_cols[1].select_one(".tb-lead")
                if cliente_elem:
                    cliente = cliente_elem.get_text(strip=True)
            
            # Telefone - texto do .whatsapp-message-link
            telefone = ""
            whatsapp_link = row.select_one(".whatsapp-message-link")
            if whatsapp_link:
                telefone = whatsapp_link.get_text(strip=True)
                # Remove ícone e espaços extras
                telefone = re.sub(r'^\+?\s*', '', telefone).strip()
            
            # Bilhetes - texto do .tb-sub.text-primary
            bilhetes_elem = row.select_one(".nk-tb-col.tb-col-md .tb-sub.text-primary")
            qtd_bilhetes = ""
            if bilhetes_elem:
                qtd_bilhetes = bilhetes_elem.get_text(strip=True)
            
            # Valor - último .tb-lead em .tb-col-sm
            valor_elem = row.select_one(".nk-tb-col.tb-col-sm .tb-lead")
            valor = ""
            if valor_elem:
                valor_text = valor_elem.get_text(strip=True)
                valor = parser.extract_money(valor_text) or valor_text
            
            # URL detalhes - href do link "Ver detalhes"
            detalhes_url = ""
            detalhes_link = row.select_one('a[href*="detalhes"]')
            if detalhes_link:
                href = detalhes_link.get("href", "")
                if href:
                    if href.startswith("/"):
                        detalhes_url = f"{settings.MT_PREMIADO_BASE_URL}{href}"
                    elif href.startswith("http"):
                        detalhes_url = href
                    else:
                        detalhes_url = f"{settings.MT_PREMIADO_BASE_URL}/{href}"
            
            pedido = {
                "id": pedido_id,
                "criado": data_criado,
                "status": status,
                "sorteio": sorteio,
                "bilhetes_totais_sorteio": "",  # Não está claro no HTML fornecido
                "cliente": cliente,
                "telefone": telefone,
                "qtd_bilhetes": qtd_bilhetes,
                "valor": valor,
                "detalhes_url": detalhes_url,
            }
            
            if not pedido_id:
                print(f"[WARNING] Não foi possível extrair ID do pedido")
                if settings.DEBUG_HTML:
                    logger.warning(
                        "pedido_id_not_found",
                        row_preview=str(row)[:300]
                    )
            
            # Retorna pedido se pelo menos ID foi encontrado
            if pedido_id:
                if not settings.DEBUG_HTML:  # Log simples quando não está em debug
                    print(f"[INFO] Extraído ID {pedido_id} do pedido")
                return pedido
            else:
                if settings.DEBUG_HTML:
                    logger.warning("pedido_invalid", row_preview=str(row)[:200])
                return None
            
        except Exception as e:
            logger.warning("parsing_error", error=str(e), row=str(row)[:200])
            return None
    
    def _find_pedidos_rows(self, soup: BeautifulSoup, page_num: int) -> List:
        """Encontra linhas de pedidos testando múltiplos seletores."""
        selectors_to_try = [
            ".nk-tb-item:not(.nk-tb-head)",
            ".nk-tb-item",
            "tr.nk-tb-item",
            "[data-pedido-id]",
            ".table-row",
            "tbody tr",
            ".pedido-row",
            "[class*='pedido']",
            "[class*='order']",
            ".order-item",
            "div[class*='item']",
            ".list-item",
            "[data-id]"
        ]
        
        rows_found = []
        working_selector = None
        
        for selector in selectors_to_try:
            try:
                rows = soup.select(selector)
                # Filtra cabeçalhos se necessário
                if selector == ".nk-tb-item":
                    rows = [r for r in rows if "nk-tb-head" not in r.get("class", [])]
                
                count = len(rows)
                
                if settings.DEBUG_SELECTORS:
                    DebugHelper.log_step("selector_tested", {
                        "page": page_num,
                        "selector": selector,
                        "count": count
                    })
                
                if count > 0:
                    rows_found = rows
                    working_selector = selector
                    
                    if settings.DEBUG_SELECTORS:
                        DebugHelper.log_step("selector_worked", {
                            "page": page_num,
                            "selector": selector,
                            "count": count
                        })
                    
                    # Screenshot quando seletor funciona
                    if settings.DEBUG_SCREENSHOTS and self.page:
                        DebugHelper.take_screenshot(
                            self.page,
                            f"selector_worked_{page_num}",
                            selector.replace(".", "_").replace(":", "_")
                        )
                    
                    break
            except Exception as e:
                if settings.DEBUG_SELECTORS:
                    DebugHelper.log_step("selector_error", {
                        "page": page_num,
                        "selector": selector,
                        "error": str(e)
                    })
                continue
        
        if not rows_found and settings.DEBUG_SELECTORS:
            DebugHelper.log_step("no_selectors_worked", {
                "page": page_num,
                "tested": len(selectors_to_try)
            })
        
        return rows_found, working_selector
    
    def _has_more_pages(self, soup: BeautifulSoup) -> bool:
        """Verifica se há mais páginas."""
        # Procura por botão "Próxima" ou link para próxima página
        next_button = soup.select_one('a[href*="page="]:has-text("Próxima"), a[rel="next"]')
        if next_button and "disabled" not in next_button.get("class", []):
            return True
        
        # Verifica se há itens na página atual
        rows = soup.select(".nk-tb-item:not(.nk-tb-head)")
        return len(rows) > 0
    
    async def extract_all_pedidos(self, last_order_id: Optional[int] = None, limit: Optional[int] = None) -> List[Dict]:
        """Extrai todos os pedidos de todas as páginas.
        
        Args:
            last_order_id: Se fornecido, retorna apenas pedidos com ID > last_order_id.
                          A filtragem é aplicada após coletar todos os pedidos.
            limit: O número máximo de pedidos a retornar.
        """
        start_time = DebugHelper.start_timer("extract_all_pedidos")
        all_pedidos = []
        page = 1
        
        DebugHelper.log_step("extract_all_pedidos_start", {"last_order_id": last_order_id, "limit": limit})
        logger.info("scraping_page_start", page=page, last_order_id=last_order_id, limit=limit)
        
        while True:
            try:
                page_start_time = DebugHelper.start_timer(f"extract_page_{page}")
                DebugHelper.log_step("extract_page_start", {"page": page})
                
                soup = await self._fetch_page(page)
                
                # Encontra linhas de pedidos testando múltiplos seletores
                rows, working_selector = self._find_pedidos_rows(soup, page)
                
                if not rows:
                    DebugHelper.log_step("extract_page_no_rows", {"page": page})
                    DebugHelper.end_timer(page_start_time, f"extract_page_{page}", {"pedidos": 0})
                    logger.info("scraping_page_complete", page=page, pedidos=0, selector=working_selector or "none")
                    break
                
                DebugHelper.log_step("extract_page_rows_found", {
                    "page": page,
                    "count": len(rows),
                    "selector": working_selector or "unknown"
                })
                logger.info("rows_found", page=page, count=len(rows))
                print(f"[INFO] Processando página {page}...")
                
                page_pedidos = []
                found_last_order = False
                for i, row in enumerate(rows):
                    pedido = self._extract_pedido_from_row(row)
                    if pedido:
                        pedido_id = pedido.get("id")
                        
                        # Otimização: Se last_order_id fornecido, para quando encontrar ID <= last_order_id
                        # Isso evita processar páginas desnecessárias (performance crítica com 153+ páginas)
                        if last_order_id is not None and pedido_id is not None:
                            try:
                                pedido_id_int = int(pedido_id) if isinstance(pedido_id, str) and pedido_id.isdigit() else pedido_id
                                if isinstance(pedido_id_int, int) and pedido_id_int <= last_order_id:
                                    found_last_order = True
                                    logger.info("found_last_order_stopping", pedido_id=pedido_id_int, last_order_id=last_order_id, page=page)
                                    print(f"[INFO] Encontrado pedido {pedido_id_int} <= {last_order_id}, parando coleta desta página")
                                    break  # Para de coletar desta página
                            except (ValueError, TypeError):
                                pass  # Continua se não conseguir converter ID
                        
                        # Adiciona pedido encontrado
                        # A filtragem final será aplicada depois para garantir correção
                        page_pedidos.append(pedido)
                    elif settings.DEBUG_HTML:
                        logger.debug("row_skipped", page=page, row_index=i)
                
                # Adiciona pedidos da página
                all_pedidos.extend(page_pedidos)
                print(f"[INFO] Página {page} processada: {len(page_pedidos)} pedidos encontrados")
                
                # Se encontrou último pedido conhecido, para de buscar mais páginas
                # Otimização crítica: evita processar 153 páginas desnecessariamente
                if found_last_order:
                    logger.info("stopping_because_found_last_order", page=page, last_order_id=last_order_id)
                    print(f"[INFO] Parando busca de páginas: encontrado pedido com ID <= {last_order_id}")
                    DebugHelper.log_step("extract_all_pedidos_stopped_found_last_order", {
                        "page": page,
                        "last_order_id": last_order_id,
                        "total_collected": len(all_pedidos)
                    })
                    break
                
                # Verifica se atingiu o limite (antes da filtragem final)
                # Se limit foi fornecido e já coletamos pedidos suficientes, para de buscar
                if limit is not None and len(all_pedidos) >= limit:
                    logger.info("limit_reached_before_filtering", current_pedidos=len(all_pedidos), limit=limit)
                    print(f"[INFO] Parando busca: coletados {len(all_pedidos)} pedidos (limite: {limit})")
                    DebugHelper.log_step("extract_all_pedidos_stopped_limit_reached", {
                        "page": page,
                        "limit": limit,
                        "total_collected": len(all_pedidos)
                    })
                    break
                
                DebugHelper.log_step("extract_page_complete", {
                    "page": page,
                    "pedidos_found": len(page_pedidos),
                    "total_pedidos": len(all_pedidos),
                    "selector": working_selector or "unknown"
                })
                DebugHelper.end_timer(page_start_time, f"extract_page_{page}", {
                    "pedidos": len(page_pedidos),
                    "selector": working_selector or "unknown"
                })
                
                logger.info(
                    "scraping_page_complete",
                    page=page,
                    pedidos=len(page_pedidos),
                    total=len(all_pedidos),
                    selector=working_selector or ".nk-tb-item"
                )
                
                # Verifica se há próxima página
                if not self._has_more_pages(soup):
                    DebugHelper.log_step("extract_all_pedidos_no_more_pages", {"last_page": page})
                    break
                
                page += 1
                
            except NetworkError:
                DebugHelper.end_timer(start_time, "extract_all_pedidos", {"success": False, "error": "NetworkError"})
                raise
            except Exception as e:
                DebugHelper.log_step("extract_page_error", {"page": page, "error": str(e)})
                DebugHelper.end_timer(start_time, "extract_all_pedidos", {"success": False, "error": str(e)})
                logger.error("scraping_error", error=str(e), page=page)
                break
        
        # Filtra pedidos finais para garantir que apenas ID > last_order_id sejam retornados
        # E aplica o limite final
        final_pedidos = []
        for pedido in all_pedidos:
            pedido_id = pedido.get("id")
            if last_order_id is not None:
                if pedido_id is not None:
                    try:
                        pedido_id_int = int(pedido_id) if isinstance(pedido_id, str) and pedido_id.isdigit() else pedido_id
                        if isinstance(pedido_id_int, int) and pedido_id_int > last_order_id:
                            final_pedidos.append(pedido)
                    except (ValueError, TypeError):
                        final_pedidos.append(pedido)
                else:
                    final_pedidos.append(pedido)
            else:
                final_pedidos.append(pedido)
        
        # Aplica limite final se fornecido
        if limit is not None:
            final_pedidos = final_pedidos[:limit]
        
        all_pedidos = final_pedidos
        
        DebugHelper.log_step("extract_all_pedidos_complete", {"total_pedidos": len(all_pedidos), "total_pages": page - 1})
        DebugHelper.end_timer(start_time, "extract_all_pedidos", {
            "success": True,
            "total_pedidos": len(all_pedidos),
            "total_pages": page - 1
        })
        
        logger.info("scraping_finished", total_pedidos=len(all_pedidos))
        return all_pedidos

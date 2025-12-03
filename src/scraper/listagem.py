"""Scraper para listagem de pedidos."""

import os
import re
from typing import List, Dict, Optional, Tuple
from requests import Session
from bs4 import BeautifulSoup
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from src.core.settings import settings
from src.core.logger import get_logger
from src.core.exceptions import NetworkError, ParsingError
from src.scraper.parser import HTMLParser
from src.scraper.debug_helper import DebugHelper

logger = get_logger()
parser = HTMLParser()


class ListagemScraper:
    """Scraper para extrair listagem de pedidos."""
    
    def __init__(self, session: Session):
        self.session = session
        self.base_url = settings.MT_PREMIADO_PEDIDOS_URL
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(NetworkError)
    )
    def _fetch_page(self, page: int) -> BeautifulSoup:
        """Busca uma página de pedidos."""
        start_time = DebugHelper.start_timer(f"fetch_page_{page}_requests")
        
        try:
            url = f"{self.base_url}?page={page}"
            DebugHelper.log_step("fetch_page_start_requests", {"page": page, "url": url})
            
            response = self.session.get(url, timeout=settings.REQUEST_TIMEOUT)
            response.raise_for_status()
            
            html_text = response.text
            html_size = len(html_text)
            
            DebugHelper.log_step("fetch_page_html_fetched_requests", {"page": page, "html_size": html_size})
            
            # Log tamanho do HTML
            logger.debug("html_fetched", page=page, html_size=html_size, url=url)
            
            # Log preview do HTML se DEBUG_HTML estiver ativo
            if settings.DEBUG_HTML:
                preview = html_text[:500].replace("\n", " ").replace("\r", "")
                logger.info("html_preview", page=page, preview=preview)
            
            # Salvar HTML usando DebugHelper
            if settings.DEBUG_SAVE_HTML:
                import tempfile
                from pathlib import Path
                debug_dir = Path(settings.DEBUG_DIR) / "html"
                debug_dir.mkdir(parents=True, exist_ok=True)
                filename = debug_dir / f"page_{page}_requests.html"
                with open(filename, "w", encoding="utf-8") as f:
                    f.write(html_text)
                DebugHelper.log_step("fetch_page_html_saved_requests", {"page": page, "filename": str(filename)})
                logger.info("html_saved", page=page, filename=str(filename))
            
            DebugHelper.end_timer(start_time, f"fetch_page_{page}_requests", {"success": True, "html_size": html_size})
            
            return BeautifulSoup(html_text, "html.parser")
        except Exception as e:
            DebugHelper.end_timer(start_time, f"fetch_page_{page}_requests", {"success": False, "error": str(e)})
            logger.error("network_error", error=str(e), page=page)
            raise NetworkError(f"Erro ao buscar página {page}: {str(e)}")
    
    def _extract_pedido_from_row(self, row: BeautifulSoup) -> Optional[Dict]:
        """Extrai dados de um pedido de uma linha da tabela."""
        try:
            # ID do pedido - múltiplas tentativas
            pedido_id = None
            
            # 1. Tenta checkbox com value (mais confiável)
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
    
    def _analyze_html_structure(self, soup: BeautifulSoup) -> Dict:
        """Analisa a estrutura HTML da página para identificar elementos relevantes."""
        analysis = {
            "tables": [],
            "pedido_classes": [],
            "order_classes": [],
            "pagination_elements": [],
            "data_attributes": [],
        }
        
        # Encontra todas as tabelas
        tables = soup.find_all("table")
        for i, table in enumerate(tables):
            # Garante que class seja lista de strings serializável
            table_classes = table.get("class", [])
            if table_classes:
                # Converte para lista de strings se necessário
                table_classes = [str(c) for c in table_classes] if isinstance(table_classes, list) else [str(table_classes)]
            else:
                table_classes = []
            
            table_info = {
                "index": i,
                "class": table_classes,
                "id": str(table.get("id", "")),
                "tbody_rows": len(table.select("tbody tr")),
                "all_rows": len(table.find_all("tr")),
            }
            analysis["tables"].append(table_info)
        
        # Encontra elementos com classes relacionadas a pedido
        pedido_elements = soup.find_all(class_=re.compile(r"pedido|order|compra", re.I))
        for elem in pedido_elements[:20]:  # Limita a 20 para não sobrecarregar
            classes = elem.get("class", [])
            if classes:
                # Garante que sejam strings
                if isinstance(classes, list):
                    analysis["pedido_classes"].extend([str(c) for c in classes])
                else:
                    analysis["pedido_classes"].append(str(classes))
        
        # Remove duplicatas e garante que sejam strings
        analysis["pedido_classes"] = [str(c) for c in list(set(analysis["pedido_classes"]))]
        
        # Encontra elementos com atributos data-*
        # Corrige lambda para verificar se x é dict antes de chamar .keys()
        def has_data_attr(attrs):
            """Verifica se o elemento tem atributos data-*."""
            if not attrs:
                return False
            # Se attrs é dict, verifica keys
            if isinstance(attrs, dict):
                return any(k.startswith("data-") for k in attrs.keys())
            # Se attrs é string ou outro tipo, retorna False
            return False
        
        data_attrs = soup.find_all(attrs=has_data_attr)
        for elem in data_attrs[:20]:
            # elem.attrs é um dict-like object, itera sobre as chaves
            if hasattr(elem, 'attrs') and elem.attrs:
                for attr in elem.attrs.keys():
                    if attr.startswith("data-"):
                        analysis["data_attributes"].append(str(attr))
        
        analysis["data_attributes"] = [str(a) for a in list(set(analysis["data_attributes"]))]
        
        # Encontra elementos de paginação
        pagination = soup.find_all(class_=re.compile(r"pagination|page|next|prev", re.I))
        for elem in pagination:
            classes = elem.get("class", [])
            if classes:
                # Garante que sejam strings
                if isinstance(classes, list):
                    analysis["pagination_elements"].extend([str(c) for c in classes])
                else:
                    analysis["pagination_elements"].append(str(classes))
        
        analysis["pagination_elements"] = [str(c) for c in list(set(analysis["pagination_elements"]))]
        
        return analysis
    
    def _find_pedidos_rows(self, soup: BeautifulSoup) -> Tuple[List, str]:
        """Tenta múltiplos seletores CSS para encontrar as linhas de pedidos."""
        selectors = [
            (".nk-tb-item:not(.nk-tb-head)", "Classe .nk-tb-item excluindo cabeçalho"),
            (".nk-tb-item", "Classe .nk-tb-item (todos)"),
            ("div.nk-tb-item:not(.nk-tb-head)", "div.nk-tb-item excluindo cabeçalho"),
            ("table tbody tr", "Tabela tbody tr"),
            (".table tbody tr", "Classe .table tbody tr"),
            ("tbody tr", "tbody tr"),
            ("table tr", "table tr"),
            ("[data-pedido]", "Atributo data-pedido"),
            ("[data-order]", "Atributo data-order"),
            (".pedido-row", "Classe .pedido-row"),
            (".pedido-item", "Classe .pedido-item"),
            (".order-row", "Classe .order-row"),
            (".order-item", "Classe .order-item"),
            ("tr[data-id]", "tr com data-id"),
            (".row-pedido", "Classe .row-pedido"),
            ("div[data-pedido-id]", "div com data-pedido-id"),
        ]
        
        for selector, description in selectors:
            try:
                rows = soup.select(selector)
                
                if settings.DEBUG_SELECTORS:
                    DebugHelper.log_step("selector_tested_requests", {
                        "selector": selector,
                        "description": description,
                        "count": len(rows)
                    })
                
                if rows:
                    # Filtra linhas vazias ou de cabeçalho
                    # Para seletores .nk-tb-item, filtra explicitamente .nk-tb-head
                    if ".nk-tb-item" in selector:
                        filtered_rows = [
                            row for row in rows 
                            if row.get_text(strip=True) and 
                            "nk-tb-head" not in row.get("class", [])
                        ]
                    else:
                        # Para outros seletores, filtra th
                        filtered_rows = [
                            row for row in rows 
                            if row.get_text(strip=True) and 
                            not any(th in row.find_all(["th"]) for th in [True])
                        ]
                    if filtered_rows:
                        if settings.DEBUG_SELECTORS:
                            DebugHelper.log_step("selector_worked_requests", {
                                "selector": selector,
                                "description": description,
                                "count": len(filtered_rows)
                            })
                        
                        logger.info(
                            "selector_found",
                            selector=selector,
                            description=description,
                            count=len(filtered_rows)
                        )
                        return filtered_rows, selector
                    else:
                        logger.debug(
                            "selector_empty",
                            selector=selector,
                            description=description,
                            total_found=len(rows)
                        )
                else:
                    logger.debug("selector_not_found", selector=selector, description=description)
            except Exception as e:
                logger.warning("selector_error", selector=selector, error=str(e))
        
        # Se nenhum seletor funcionou, retorna lista vazia
        if settings.DEBUG_SELECTORS:
            DebugHelper.log_step("no_selectors_worked_requests", {"tested": len(selectors)})
        
        logger.warning("no_selectors_worked", tested=len(selectors))
        return [], ""
    
    def _has_more_pages(self, soup: BeautifulSoup) -> bool:
        """Verifica se há mais páginas."""
        # Procura por indicadores de paginação
        next_button = soup.select_one("a[rel='next'], .pagination .next, .page-next")
        if next_button and "disabled" not in next_button.get("class", []):
            return True
        
        # Verifica se há itens na página atual
        rows = soup.select("tbody tr, .pedido-item, .order-row")
        return len(rows) > 0
    
    def extract_all_pedidos(self, last_order_id: Optional[int] = None, limit: Optional[int] = None) -> List[Dict]:
        """Extrai todos os pedidos de todas as páginas.
        
        Args:
            last_order_id: Se fornecido, retorna apenas pedidos com ID > last_order_id.
                          A filtragem é aplicada após coletar todos os pedidos.
            limit: O número máximo de pedidos a retornar.
        """
        start_time = DebugHelper.start_timer("extract_all_pedidos_requests")
        all_pedidos = []
        page = 1
        
        DebugHelper.log_step("extract_all_pedidos_start_requests", {"last_order_id": last_order_id, "limit": limit})
        logger.info("scraping_page_start", page=page, last_order_id=last_order_id, limit=limit)
        
        while True:
            try:
                soup = self._fetch_page(page)
                
                # Analisa estrutura HTML se DEBUG_HTML estiver ativo
                if settings.DEBUG_HTML:
                    analysis = self._analyze_html_structure(soup)
                    # Converte analysis para formato JSON-safe antes de logar
                    analysis_summary = {
                        "tables_count": len(analysis.get("tables", [])),
                        "pedido_classes_count": len(analysis.get("pedido_classes", [])),
                        "data_attributes_count": len(analysis.get("data_attributes", [])),
                        "pagination_elements_count": len(analysis.get("pagination_elements", [])),
                    }
                    logger.info("html_structure_analysis", page=page, **analysis_summary)
                
                # Tenta encontrar pedidos usando múltiplos seletores
                rows, working_selector = self._find_pedidos_rows(soup)
                
                if not rows:
                    logger.info("scraping_page_complete", page=page, pedidos=0, selector="none")
                    # Se DEBUG_HTML, analisa estrutura para ajudar no debug
                    if settings.DEBUG_HTML:
                        analysis = self._analyze_html_structure(soup)
                        analysis_summary = {
                            "tables_count": len(analysis.get("tables", [])),
                            "pedido_classes_count": len(analysis.get("pedido_classes", [])),
                            "data_attributes_count": len(analysis.get("data_attributes", [])),
                            "pagination_elements_count": len(analysis.get("pagination_elements", [])),
                        }
                        logger.warning("no_rows_found", page=page, **analysis_summary)
                    break
                
                logger.info("rows_found", page=page, count=len(rows), selector=working_selector)
                print(f"[INFO] Processando página {page}...")
                
                page_pedidos = []
                for i, row in enumerate(rows):
                    pedido = self._extract_pedido_from_row(row)
                    if pedido:
                        # Adiciona todos os pedidos encontrados
                        # A filtragem por last_order_id será aplicada no final
                        page_pedidos.append(pedido)
                    elif settings.DEBUG_HTML:
                        logger.debug("row_skipped", page=page, row_index=i)
                
                # Adiciona pedidos da página
                all_pedidos.extend(page_pedidos)
                print(f"[INFO] Página {page} processada: {len(page_pedidos)} pedidos encontrados")
                
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
                
                DebugHelper.log_step("extract_page_complete_requests", {
                    "page": page,
                    "pedidos_found": len(page_pedidos),
                    "total_pedidos": len(all_pedidos),
                    "selector": working_selector
                })
                
                logger.info(
                    "scraping_page_complete",
                    page=page,
                    pedidos=len(page_pedidos),
                    total=len(all_pedidos),
                    selector=working_selector
                )
                
                # Verifica se há próxima página
                if not self._has_more_pages(soup):
                    DebugHelper.log_step("extract_all_pedidos_no_more_pages_requests", {"last_page": page})
                    break
                
                page += 1
                
            except NetworkError:
                DebugHelper.end_timer(start_time, "extract_all_pedidos_requests", {"success": False, "error": "NetworkError"})
                raise
            except Exception as e:
                DebugHelper.log_step("extract_page_error_requests", {"page": page, "error": str(e)})
                DebugHelper.end_timer(start_time, "extract_all_pedidos_requests", {"success": False, "error": str(e)})
                logger.error("scraping_error", error=str(e), page=page)
                # Continua para próxima página mesmo com erro
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
        
        DebugHelper.log_step("extract_all_pedidos_complete_requests", {"total_pedidos": len(all_pedidos), "total_pages": page - 1})
        DebugHelper.end_timer(start_time, "extract_all_pedidos_requests", {
            "success": True,
            "total_pedidos": len(all_pedidos),
            "total_pages": page - 1
        })
        
        logger.info("scraping_finished", total_pedidos=len(all_pedidos))
        return all_pedidos


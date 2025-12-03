"""Controller para pedidos."""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional

from src.scraper.session import get_authenticated_session
from src.scraper.listagem import ListagemScraper
from src.scraper.detalhes import DetalhesScraper
from src.scraper.session_playwright import PlaywrightSession
from src.scraper.listagem_playwright import ListagemScraperPlaywright
from src.scraper.detalhes_playwright import DetalhesScraperPlaywright
from src.core.settings import settings
from src.core.logger import get_logger
from src.core.state_manager import StateManager
from src.api.schemas.pedido_schema import PedidosResponseSchema, PedidoDetalhesSchema, PaginationMetadata

logger = get_logger()


class PedidosController:
    """Controller para gerenciar extração de pedidos."""
    
    @staticmethod
    async def extract_all_pedidos_full(
        last_id: Optional[int] = None,
        limit: Optional[int] = None
    ) -> PedidosResponseSchema:
        """Extrai pedidos com detalhes completos, com suporte a paginação.
        
        Args:
            last_id: Último ID conhecido. Retorna apenas pedidos com ID > last_id.
            limit: Limite de pedidos a retornar. Se não fornecido, retorna todos.
        """
        if settings.USE_PLAYWRIGHT:
            response = await PedidosController._extract_with_playwright(last_id=last_id, limit=limit)
        else:
            response = PedidosController._extract_with_requests(last_id=last_id, limit=limit)
        
        # Calcula metadados de paginação se limit foi usado
        if limit is not None:
            # Encontra o último ID processado
            last_id_processed = None
            if response.pedidos:
                pedido_ids = [
                    p.id for p in response.pedidos 
                    if p.id is not None
                ]
                if pedido_ids:
                    # Converte para int se necessário
                    int_ids = []
                    for pid in pedido_ids:
                        try:
                            pid_int = int(pid) if isinstance(pid, str) and pid.isdigit() else pid
                            if isinstance(pid_int, int):
                                int_ids.append(pid_int)
                        except (ValueError, TypeError):
                            continue
                    if int_ids:
                        # Usa o MENOR ID para permitir continuar paginação corretamente
                        # Os pedidos vêm ordenados do mais recente (maior ID) para o mais antigo (menor ID)
                        # Então precisamos do menor ID para buscar os próximos pedidos
                        last_id_processed = min(int_ids)
            
            # Determina se há mais pedidos
            # Se retornou exatamente 'limit' pedidos, pode haver mais
            has_more = len(response.pedidos) == limit
            
            pagination = PaginationMetadata(
                last_id_processed=last_id_processed,
                has_more=has_more,
                total_available=None,  # Não sabemos sem contar tudo
                limit=limit,
                last_id_requested=last_id
            )
            response.pagination = pagination
        
        # Salva maior ID encontrado apenas se NÃO estiver usando paginação
        # (comportamento original do /full quando não há limit)
        # Não salvar estado automaticamente quando usar paginação (diferente do /incremental)
        if limit is None and response.pedidos:
            max_id = None
            for pedido in response.pedidos:
                pedido_id = pedido.id
                if pedido_id is not None:
                    try:
                        pedido_id_int = int(pedido_id) if isinstance(pedido_id, str) and pedido_id.isdigit() else pedido_id
                        if isinstance(pedido_id_int, int):
                            if max_id is None or pedido_id_int > max_id:
                                max_id = pedido_id_int
                    except (ValueError, TypeError):
                        continue
            
            if max_id:
                StateManager.save_last_order_id(max_id)
                logger.info("saved_last_order_id_from_full", last_order_id=max_id)
        
        # Salva JSON se configurado
        if settings.EXPORT_JSON:
            PedidosController._save_json_response(response)
        
        return response
    
    @staticmethod
    def _extract_with_requests(
        last_id: Optional[int] = None,
        limit: Optional[int] = None
    ) -> PedidosResponseSchema:
        """Extrai usando requests (método original).
        
        Args:
            last_id: Último ID conhecido. Retorna apenas pedidos com ID > last_id.
            limit: Limite de pedidos a retornar. Se não fornecido, retorna todos.
        """
        try:
            with get_authenticated_session() as session:
                # Extrai listagem
                listagem_scraper = ListagemScraper(session)
                pedidos_listagem = listagem_scraper.extract_all_pedidos(last_order_id=last_id, limit=limit)
                
                # Extrai detalhes de cada pedido
                detalhes_scraper = DetalhesScraper(session)
                pedidos_completos = []
                
                for pedido in pedidos_listagem:
                    try:
                        if pedido.get("detalhes_url"):
                            detalhes = detalhes_scraper.extract_detalhes(
                                pedido["detalhes_url"]
                            )
                            # Mescla listagem com detalhes
                            pedido_completo = {**pedido, **detalhes}
                        else:
                            pedido_completo = pedido
                        
                        pedidos_completos.append(pedido_completo)
                        
                    except Exception as e:
                        logger.warning(
                            "order_detail_skipped",
                            error=str(e),
                            pedido_id=pedido.get("id")
                        )
                        # Adiciona pedido sem detalhes
                        pedidos_completos.append(pedido)
                
                return PedidosController._build_response(pedidos_completos)
                
        except Exception as e:
            logger.error("extraction_error", error=str(e), method="requests")
            raise
    
    @staticmethod
    async def _extract_with_playwright(
        last_id: Optional[int] = None,
        limit: Optional[int] = None
    ) -> PedidosResponseSchema:
        """Extrai usando Playwright.
        
        Args:
            last_id: Último ID conhecido. Retorna apenas pedidos com ID > last_id.
            limit: Limite de pedidos a retornar. Se não fornecido, retorna todos.
        """
        try:
            async with PlaywrightSession() as playwright_session:
                # Faz login
                page = await playwright_session.login()
                
                # Extrai listagem
                listagem_scraper = ListagemScraperPlaywright(page)
                pedidos_listagem = await listagem_scraper.extract_all_pedidos(last_order_id=last_id, limit=limit)
                
                # Extrai detalhes de cada pedido
                detalhes_scraper = DetalhesScraperPlaywright(page)
                pedidos_completos = []
                
                for pedido in pedidos_listagem:
                    try:
                        if pedido.get("detalhes_url"):
                            detalhes = await detalhes_scraper.extract_detalhes(
                                pedido["detalhes_url"]
                            )
                            # Mescla listagem com detalhes
                            pedido_completo = {**pedido, **detalhes}
                        else:
                            pedido_completo = pedido
                        
                        pedidos_completos.append(pedido_completo)
                        
                    except Exception as e:
                        logger.warning(
                            "order_detail_skipped",
                            error=str(e),
                            pedido_id=pedido.get("id")
                        )
                        # Adiciona pedido sem detalhes
                        pedidos_completos.append(pedido)
                
                return PedidosController._build_response(pedidos_completos)
                
        except Exception as e:
            logger.error("extraction_error", error=str(e), method="playwright")
            # Fallback para requests se Playwright falhar
            logger.warning("playwright_failed_fallback_to_requests")
            try:
                return PedidosController._extract_with_requests(last_id=last_id, limit=limit)
            except Exception as e2:
                logger.error("fallback_also_failed", error=str(e2))
                raise
    
    @staticmethod
    async def extract_incremental_pedidos(last_order_id: Optional[int] = None) -> PedidosResponseSchema:
        """Extrai apenas pedidos novos a partir do último ID conhecido.
        
        Args:
            last_order_id: ID do último pedido processado. Se None, usa StateManager para obter.
        """
        # Obtém last_order_id do estado se não fornecido
        if last_order_id is None:
            last_order_id = StateManager.get_last_order_id()
            if last_order_id:
                logger.info("using_saved_last_order_id", last_order_id=last_order_id)
            else:
                logger.info("no_saved_state_found_extracting_all")
        
        # Log humanizado: início
        if last_order_id:
            print(f"[INFO] Iniciando extração incremental...")
            print(f"[INFO] Buscando pedidos com ID maior que {last_order_id}...")
        else:
            print(f"[INFO] Iniciando extração incremental...")
            print(f"[INFO] Buscando todos os pedidos (sem filtro de ID)...")
        
        # Extrai pedidos usando método apropriado
        if settings.USE_PLAYWRIGHT:
            pedidos_completos = await PedidosController._extract_incremental_with_playwright(last_order_id)
        else:
            pedidos_completos = PedidosController._extract_incremental_with_requests(last_order_id)
        
        # Inicializa max_id antes de usar
        max_id = None
        
        # Salva maior ID encontrado
        if pedidos_completos:
            for pedido in pedidos_completos:
                pedido_id = pedido.get("id")
                if pedido_id is not None:
                    try:
                        pedido_id_int = int(pedido_id) if isinstance(pedido_id, str) and pedido_id.isdigit() else pedido_id
                        if isinstance(pedido_id_int, int):
                            if max_id is None or pedido_id_int > max_id:
                                max_id = pedido_id_int
                    except (ValueError, TypeError):
                        continue
            
            if max_id:
                StateManager.save_last_order_id(max_id)
                logger.info("saved_last_order_id", last_order_id=max_id)
                print(f"[INFO] Salvando último ID processado: {max_id}")
        
        # Log humanizado: resultado
        total_pedidos = len(pedidos_completos) if pedidos_completos else 0
        if total_pedidos > 0:
            print(f"[INFO] Encontrados {total_pedidos} pedidos novos")
        else:
            print(f"[INFO] Nenhum pedido novo encontrado")
        
        # Constrói resposta
        response = PedidosController._build_response(pedidos_completos, incremental=True, last_order_id_processed=max_id)
        
        # Salva JSON se configurado
        if settings.EXPORT_JSON:
            PedidosController._save_json_response(response)
        
        return response
    
    @staticmethod
    def _extract_incremental_with_requests(last_order_id: Optional[int]) -> List[Dict]:
        """Extrai pedidos incrementais usando requests."""
        try:
            with get_authenticated_session() as session:
                # Extrai listagem
                listagem_scraper = ListagemScraper(session)
                pedidos_listagem = listagem_scraper.extract_all_pedidos(last_order_id=last_order_id)
                
                # Extrai detalhes de cada pedido
                detalhes_scraper = DetalhesScraper(session)
                pedidos_completos = []
                
                for pedido in pedidos_listagem:
                    try:
                        if pedido.get("detalhes_url"):
                            detalhes = detalhes_scraper.extract_detalhes(
                                pedido["detalhes_url"]
                            )
                            pedido_completo = {**pedido, **detalhes}
                        else:
                            pedido_completo = pedido
                        
                        pedidos_completos.append(pedido_completo)
                        
                    except Exception as e:
                        logger.warning(
                            "order_detail_skipped",
                            error=str(e),
                            pedido_id=pedido.get("id")
                        )
                        pedidos_completos.append(pedido)
                
                return pedidos_completos
                
        except Exception as e:
            logger.error("extraction_error", error=str(e), method="requests")
            raise
    
    @staticmethod
    async def _extract_incremental_with_playwright(last_order_id: Optional[int]) -> List[Dict]:
        """Extrai pedidos incrementais usando Playwright."""
        try:
            async with PlaywrightSession() as playwright_session:
                page = await playwright_session.login()
                
                # Extrai listagem
                listagem_scraper = ListagemScraperPlaywright(page)
                pedidos_listagem = await listagem_scraper.extract_all_pedidos(last_order_id=last_order_id)
                
                # Extrai detalhes de cada pedido
                detalhes_scraper = DetalhesScraperPlaywright(page)
                pedidos_completos = []
                
                for pedido in pedidos_listagem:
                    try:
                        if pedido.get("detalhes_url"):
                            detalhes = await detalhes_scraper.extract_detalhes(
                                pedido["detalhes_url"]
                            )
                            pedido_completo = {**pedido, **detalhes}
                        else:
                            pedido_completo = pedido
                        
                        pedidos_completos.append(pedido_completo)
                        
                    except Exception as e:
                        logger.warning(
                            "order_detail_skipped",
                            error=str(e),
                            pedido_id=pedido.get("id")
                        )
                        pedidos_completos.append(pedido)
                
                return pedidos_completos
                
        except Exception as e:
            logger.error("extraction_error", error=str(e), method="playwright")
            logger.warning("playwright_failed_fallback_to_requests")
            try:
                return PedidosController._extract_incremental_with_requests(last_order_id)
            except Exception as e2:
                logger.error("fallback_also_failed", error=str(e2))
                raise
    
    @staticmethod
    def _build_response(pedidos_completos: List[Dict], incremental: bool = False, last_order_id_processed: Optional[int] = None) -> PedidosResponseSchema:
        """Constrói resposta a partir da lista de pedidos."""
        # Converte para schema, tratando valores None
        pedidos_schema = []
        for pedido in pedidos_completos:
            try:
                # Garante que todos os campos existam
                pedido_dict = {
                    "id": pedido.get("id"),
                    "criado": pedido.get("criado", ""),
                    "status": pedido.get("status", ""),
                    "sorteio": pedido.get("sorteio", ""),
                    "bilhetes_totais_sorteio": pedido.get("bilhetes_totais_sorteio", ""),
                    "cliente": pedido.get("cliente", ""),
                    "telefone": pedido.get("telefone", ""),
                    "qtd_bilhetes": pedido.get("qtd_bilhetes", ""),
                    "valor": pedido.get("valor", ""),
                    "detalhes_url": pedido.get("detalhes_url", ""),
                    "detalhe_data_hora": pedido.get("detalhe_data_hora", ""),
                    "detalhe_email": pedido.get("detalhe_email", ""),
                    "detalhe_telefone": pedido.get("detalhe_telefone", ""),
                    "detalhe_cpf": pedido.get("detalhe_cpf", ""),
                    "detalhe_nascimento": pedido.get("detalhe_nascimento", ""),
                    "detalhe_data_compra": pedido.get("detalhe_data_compra", ""),
                    "detalhe_pagamento_id": pedido.get("detalhe_pagamento_id", ""),
                    "detalhe_subtotal": pedido.get("detalhe_subtotal", ""),
                    "detalhe_descontos": pedido.get("detalhe_descontos", ""),
                    "detalhe_total": pedido.get("detalhe_total", ""),
                }
                pedidos_schema.append(PedidoDetalhesSchema(**pedido_dict))
            except Exception as e:
                logger.warning("schema_conversion_error", error=str(e), pedido_id=pedido.get("id"))
                # Adiciona pedido com valores padrão em caso de erro
                pedidos_schema.append(PedidoDetalhesSchema())
        
        response = PedidosResponseSchema(
            total=len(pedidos_schema),
            gerado_em=datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
            pedidos=pedidos_schema
        )
        
        logger.info("emitted_response", total=response.total, incremental=incremental)
        return response
    
    @staticmethod
    def _save_json_response(response: PedidosResponseSchema) -> Optional[str]:
        """Salva resposta JSON em arquivo."""
        try:
            # Garante que diretório existe
            exports_dir = Path(settings.EXPORTS_DIR)
            exports_dir.mkdir(parents=True, exist_ok=True)
            
            # Gera nome do arquivo com timestamp
            timestamp = datetime.utcnow().strftime("%Y-%m-%dT%H-%M-%S")
            filename = exports_dir / f"pedidos_{timestamp}.json"
            
            # Converte response para dict
            response_dict = {
                "total": response.total,
                "gerado_em": response.gerado_em,
                "pedidos": [
                    {
                        "id": p.id,
                        "criado": p.criado,
                        "status": p.status,
                        "sorteio": p.sorteio,
                        "bilhetes_totais_sorteio": p.bilhetes_totais_sorteio,
                        "cliente": p.cliente,
                        "telefone": p.telefone,
                        "qtd_bilhetes": p.qtd_bilhetes,
                        "valor": p.valor,
                        "detalhes_url": p.detalhes_url,
                        "detalhe_data_hora": p.detalhe_data_hora,
                        "detalhe_email": p.detalhe_email,
                        "detalhe_telefone": p.detalhe_telefone,
                        "detalhe_cpf": p.detalhe_cpf,
                        "detalhe_nascimento": p.detalhe_nascimento,
                        "detalhe_data_compra": p.detalhe_data_compra,
                        "detalhe_pagamento_id": p.detalhe_pagamento_id,
                        "detalhe_subtotal": p.detalhe_subtotal,
                        "detalhe_descontos": p.detalhe_descontos,
                        "detalhe_total": p.detalhe_total,
                    }
                    for p in response.pedidos
                ]
            }
            
            # Salva JSON indentado
            with open(filename, "w", encoding="utf-8") as f:
                json.dump(response_dict, f, indent=2, ensure_ascii=False)
            
            logger.info("json_exported", filename=str(filename), total=response.total)
            return str(filename)
            
        except Exception as e:
            logger.error("json_export_failed", error=str(e))
            return None

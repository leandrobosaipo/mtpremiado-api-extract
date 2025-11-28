"""Rotas para pedidos."""

from fastapi import APIRouter, HTTPException, status, Query
from fastapi.responses import JSONResponse
from typing import Dict, Any, Optional

from src.api.controllers.pedidos_controller import PedidosController
from src.api.schemas.pedido_schema import PedidosResponseSchema
from src.core.exceptions import AuthenticationError
from src.core.logger import get_logger
from src.core.settings import settings
from src.scraper.session import get_authenticated_session
from src.scraper.listagem import ListagemScraper
from src.scraper.session_playwright import PlaywrightSession
from src.scraper.listagem_playwright import ListagemScraperPlaywright
from src.scraper.debug_helper import DebugHelper

logger = get_logger()

router = APIRouter(prefix="/api/pedidos", tags=["pedidos"])
debug_router = APIRouter(prefix="/api/debug", tags=["debug"])


@router.get(
    "/full",
    response_model=PedidosResponseSchema,
    summary="Extrai todos os pedidos com detalhes completos",
    description="Realiza login, extrai todos os pedidos de todas as páginas e busca detalhes completos de cada um."
)
async def get_pedidos_full() -> PedidosResponseSchema:
    """Endpoint para extrair todos os pedidos com detalhes completos."""
    try:
        controller = PedidosController()
        return await controller.extract_all_pedidos_full()
        
    except AuthenticationError as e:
        logger.error("api_authentication_error", detail=str(e.detail))
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Falha ao autenticar"
        )
    except Exception as e:
        logger.error("api_error", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao processar requisição: {str(e)}"
        )


@router.get(
    "/incremental",
    response_model=PedidosResponseSchema,
    summary="Extrai apenas pedidos novos (incremental)",
    description="Extrai apenas pedidos com ID maior que o último processado. Ideal para uso com n8n em intervalos regulares."
)
async def get_pedidos_incremental(
    last_order_id: Optional[int] = Query(None, description="ID do último pedido processado. Se não fornecido, usa estado salvo.")
) -> PedidosResponseSchema:
    """Endpoint para extrair apenas pedidos novos a partir do último ID conhecido."""
    try:
        controller = PedidosController()
        return await controller.extract_incremental_pedidos(last_order_id=last_order_id)
        
    except AuthenticationError as e:
        logger.error("api_authentication_error", detail=str(e.detail))
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Falha ao autenticar"
        )
    except Exception as e:
        logger.error("api_error", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao processar requisição: {str(e)}"
        )


@debug_router.get(
    "/html",
    summary="Endpoint de debug para inspecionar HTML da página de pedidos",
    description="Retorna HTML da página e análise de estrutura. Disponível apenas em desenvolvimento."
)
async def debug_html(page: int = 1, use_playwright: bool = False) -> Dict[str, Any]:
    """Endpoint de debug para inspecionar HTML retornado."""
    try:
        if use_playwright:
            # Usa Playwright
            async with PlaywrightSession() as playwright_session:
                page_obj = await playwright_session.login()
                scraper = ListagemScraperPlaywright(page_obj)
                soup = await scraper._fetch_page(page)
                
                # Encontra pedidos
                rows = soup.select(".nk-tb-item:not(.nk-tb-head)")
                working_selector = ".nk-tb-item:not(.nk-tb-head)" if rows else ""
                
                # Prepara resposta
                html_text = str(soup)
                html_preview = html_text[:2000]
                
                response = {
                    "page": page,
                    "method": "playwright",
                    "html_size": len(html_text),
                    "html_preview": html_preview,
                    "selectors_tested": {
                        "working_selector": working_selector,
                        "rows_found": len(rows),
                    },
                }
                
                # Se encontrou rows, adiciona exemplo
                if rows:
                    first_row_preview = str(rows[0])[:500]
                    response["first_row_preview"] = first_row_preview
                    
                    try:
                        example_pedido = scraper._extract_pedido_from_row(rows[0])
                        response["example_pedido"] = example_pedido
                    except Exception as e:
                        response["example_pedido_error"] = str(e)
                
                return response
        else:
            # Usa requests (método original)
            with get_authenticated_session() as session:
                scraper = ListagemScraper(session)
                soup = scraper._fetch_page(page)
                
                # Análise da estrutura
                analysis = scraper._analyze_html_structure(soup)
                
                # Tenta encontrar pedidos
                rows, working_selector = scraper._find_pedidos_rows(soup)
                
                # Prepara resposta
                html_text = str(soup)
                html_preview = html_text[:2000]
                
                response = {
                    "page": page,
                    "method": "requests",
                    "html_size": len(html_text),
                    "html_preview": html_preview,
                    "structure_analysis": analysis,
                    "selectors_tested": {
                        "working_selector": working_selector,
                        "rows_found": len(rows),
                    },
                    "selectors_to_try": [
                        "table tbody tr",
                        ".table tbody tr",
                        "tbody tr",
                        "table tr",
                        "[data-pedido]",
                        "[data-order]",
                        ".pedido-row",
                        ".pedido-item",
                        ".order-row",
                        ".order-item",
                        "tr[data-id]",
                    ],
                }
                
                # Se encontrou rows, adiciona exemplo de primeira row
                if rows:
                    first_row_preview = str(rows[0])[:500]
                    response["first_row_preview"] = first_row_preview
                    
                    # Tenta extrair um pedido de exemplo
                    try:
                        example_pedido = scraper._extract_pedido_from_row(rows[0])
                        response["example_pedido"] = example_pedido
                    except Exception as e:
                        response["example_pedido_error"] = str(e)
                
                return response
            
    except AuthenticationError as e:
        logger.error("debug_authentication_error", detail=str(e.detail))
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Falha ao autenticar"
        )
    except Exception as e:
        logger.error("debug_error", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao processar requisição de debug: {str(e)}"
        )


@debug_router.get(
    "/detailed",
    summary="Endpoint de debug detalhado com relatório completo",
    description="Retorna relatório completo de debug incluindo steps, timings, screenshots e HTMLs salvos."
)
async def debug_detailed(use_playwright: bool = False) -> Dict[str, Any]:
    """Endpoint de debug detalhado que retorna relatório completo."""
    try:
        # Reseta sessão de debug antes de começar
        DebugHelper.reset_session()
        
        if use_playwright:
            # Usa Playwright para gerar dados de debug
            async with PlaywrightSession() as playwright_session:
                try:
                    await playwright_session.login()
                    page_obj = playwright_session.get_page()
                    scraper = ListagemScraperPlaywright(page_obj)
                    
                    # Tenta extrair pelo menos uma página para gerar dados de debug
                    await scraper._fetch_page(1)
                    
                except Exception as e:
                    logger.warning("debug_detailed_error_during_execution", error=str(e))
        else:
            # Usa requests para gerar dados de debug
            with get_authenticated_session() as session:
                scraper = ListagemScraper(session)
                try:
                    soup = scraper._fetch_page(1)
                    scraper._find_pedidos_rows(soup)
                except Exception as e:
                    logger.warning("debug_detailed_error_during_execution", error=str(e))
        
        # Gera relatório de diagnóstico
        report = DebugHelper.create_diagnostic_report()
        
        return {
            "method": "playwright" if use_playwright else "requests",
            "report": report
        }
        
    except AuthenticationError as e:
        logger.error("debug_detailed_authentication_error", detail=str(e.detail))
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Falha ao autenticar"
        )
    except Exception as e:
        logger.error("debug_detailed_error", error=str(e))
        # Retorna relatório mesmo em caso de erro parcial
        try:
            report = DebugHelper.create_diagnostic_report()
            return {
                "method": "playwright" if use_playwright else "requests",
                "report": report,
                "error": str(e)
            }
        except:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Erro ao processar requisição de debug detalhado: {str(e)}"
            )

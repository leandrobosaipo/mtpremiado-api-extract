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
    summary="Extrai pedidos com detalhes completos",
    description="""
## O que faz
Extrai pedidos com todos os detalhes usando paginação baseada em páginas com cache inteligente.

## Quando usar
- **Sem parâmetros**: Retorna página 1 (padrão)
- **Com `page`**: Especifica qual página você quer (ex: página 1, 2, 3...)
- **Com `limit`**: Limita quantos pedidos retornar da página (ex: apenas 100 da página)

## Parâmetros
- **`page`** (opcional, padrão: 1): Número da página a retornar (1-indexed).
  - Exemplo: `?page=1` → Retorna primeira página
  - Exemplo: `?page=2` → Retorna segunda página
- **`limit`** (opcional): Quantos pedidos retornar da página.
  - Exemplo: `?limit=100` → Retorna no máximo 100 pedidos da página
  - Se não usar, retorna TODOS os pedidos da página

## Como Funciona o Cache

O sistema cacheia automaticamente as páginas conforme são buscadas:
- **Primeira vez**: Busca página do site e salva no cache
- **Próximas vezes**: Retorna página do cache (muito mais rápido!)
- **Cache persiste**: Páginas ficam salvas em `data/pages_cache.json`

## Teste Primeiro
1. Teste página 1: `GET {{BASE_URL}}/api/pedidos/full?page=1`
   - Deve retornar pedidos da primeira página
   - Verifique se `pagination.current_page` é 1
   - Verifique se `pagination.total_pages_cached` mostra quantas páginas estão em cache

2. Teste página 2: `GET {{BASE_URL}}/api/pedidos/full?page=2`
   - Deve retornar pedidos da segunda página
   - Se já estava em cache, retorna instantaneamente

## Teste Depois
1. Teste paginação completa:
   - Primeira chamada: `GET {{BASE_URL}}/api/pedidos/full?page=1&limit=100`
   - Segunda chamada: `GET {{BASE_URL}}/api/pedidos/full?page=2&limit=100`
   - Terceira chamada: `GET {{BASE_URL}}/api/pedidos/full?page=3&limit=100`
   - Continue até que `pagination.has_more` seja `false`

2. Teste quando não há mais pedidos:
   - Use um `page` muito alto (ex: 999)
   - Deve retornar lista vazia
   - `pagination.has_more` deve ser `false`

## Como saber que terminou
- Se `pagination.has_more` é `false`, não há mais pedidos
- Se a lista de `pedidos` está vazia, não há mais pedidos
- Continue incrementando `page` até não retornar mais pedidos

## Exemplos Curl

```bash
# Exemplo 1: Buscar primeira página (padrão)
curl -X GET '{{BASE_URL}}/api/pedidos/full'

# Exemplo 2: Buscar página 1 explicitamente
curl -X GET '{{BASE_URL}}/api/pedidos/full?page=1'

# Exemplo 3: Buscar página 2
curl -X GET '{{BASE_URL}}/api/pedidos/full?page=2'

# Exemplo 4: Buscar página 1 com limite de 100 pedidos
curl -X GET '{{BASE_URL}}/api/pedidos/full?page=1&limit=100'

# Exemplo 5: Buscar página 2 com limite de 100 pedidos
curl -X GET '{{BASE_URL}}/api/pedidos/full?page=2&limit=100'
```
"""
)
async def get_pedidos_full(
    page: Optional[int] = Query(None, description="Número da página a retornar (1-indexed). Se não fornecido, retorna página 1. Exemplo: ?page=1"),
    limit: Optional[int] = Query(None, description="Limite de pedidos a retornar da página. Se não fornecido, retorna todos os pedidos da página. Exemplo: ?limit=100")
) -> PedidosResponseSchema:
    """Endpoint para extrair pedidos com detalhes completos, com suporte a paginação baseada em páginas."""
    try:
        # Validação de page se fornecido
        if page is not None and page < 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="O parâmetro 'page' deve ser maior ou igual a 1"
            )
        
        # Validação de limit se fornecido
        if limit is not None and limit <= 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="O parâmetro 'limit' deve ser maior que 0"
            )
        
        controller = PedidosController()
        return await controller.extract_all_pedidos_full(page=page, limit=limit)
        
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
    description="""
## O que faz
Extrai apenas pedidos NOVOS que ainda não foram processados. Ideal para rodar de tempos em tempos (ex: a cada hora) e pegar só o que é novo.

## Quando usar
- Quando quer pegar apenas pedidos que ainda não processou
- Para usar com automação (n8n, cron, etc) que roda de tempos em tempos
- Quando não quer processar tudo de novo, só o que mudou

## Parâmetros
- **`last_order_id`** (opcional): ID do último pedido que você já processou.
  - Se não fornecer, usa o último ID salvo automaticamente
  - Exemplo: `?last_order_id=1200` → Retorna apenas pedidos com ID > 1200

## Teste Primeiro
1. Teste sem parâmetros: `GET {{BASE_URL}}/api/pedidos/incremental`
   - Se for a primeira vez, retorna todos os pedidos
   - Se já rodou antes, retorna apenas os novos
   - Verifique o `total` na resposta
2. Teste com um ID específico: `GET {{BASE_URL}}/api/pedidos/incremental?last_order_id=1300`
   - Deve retornar apenas pedidos com ID maior que 1300
   - Se não houver pedidos novos, retorna lista vazia

## Teste Depois
1. Teste o fluxo completo:
   - Primeira chamada: `GET {{BASE_URL}}/api/pedidos/incremental`
   - Anote o maior ID retornado
   - Segunda chamada (depois de alguns minutos): `GET {{BASE_URL}}/api/pedidos/incremental`
   - Deve retornar apenas pedidos novos desde a última chamada
2. Teste com ID muito alto:
   - Use `?last_order_id=999999`
   - Deve retornar lista vazia (não há pedidos com ID maior)

## Como saber que terminou
- Se `total` é 0, não há pedidos novos
- Se a lista de `pedidos` está vazia, está tudo atualizado
- O sistema salva automaticamente o último ID processado

## Exemplos Curl

```bash
# Exemplo 1: Buscar pedidos novos (usa último ID salvo automaticamente)
curl -X GET '{{BASE_URL}}/api/pedidos/incremental'

# Exemplo 2: Buscar pedidos novos a partir de um ID específico
curl -X GET '{{BASE_URL}}/api/pedidos/incremental?last_order_id=1200'
```
"""
)
async def get_pedidos_incremental(
    last_order_id: Optional[int] = Query(None, description="ID do último pedido processado. Se não fornecido, usa estado salvo automaticamente. Exemplo: ?last_order_id=1200")
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
    description="""
## O que faz
Mostra o HTML da página de pedidos e informações sobre a estrutura. Útil para entender como a página funciona ou debugar problemas.

## Quando usar
- Quando quer ver o HTML que está sendo extraído
- Para debugar problemas de extração
- Para entender a estrutura da página

## Parâmetros
- **`page`** (padrão: 1): Qual página você quer ver.
  - Exemplo: `?page=2` → Mostra HTML da página 2
- **`use_playwright`** (padrão: false): Se deve usar Playwright ou requests.
  - `false` (padrão): Usa método requests (mais rápido)
  - `true`: Usa Playwright (melhor para JavaScript)

## Teste Primeiro
1. Teste básico: `GET {{BASE_URL}}/api/debug/html`
   - Deve retornar HTML da primeira página
   - Verifique se `html_size` mostra o tamanho
   - Verifique se `rows_found` mostra quantos pedidos foram encontrados
2. Teste com Playwright: `GET {{BASE_URL}}/api/debug/html?use_playwright=true`
   - Deve usar Playwright para carregar a página
   - Pode demorar mais, mas mostra conteúdo JavaScript

## Teste Depois
1. Teste diferentes páginas: `GET {{BASE_URL}}/api/debug/html?page=2`
   - Deve mostrar HTML da página 2
2. Compare métodos: Teste com e sem `use_playwright`
   - Veja qual encontra mais pedidos (`rows_found`)

## Como saber que funcionou
- Se `html_size` é maior que 0, o HTML foi carregado
- Se `rows_found` é maior que 0, pedidos foram encontrados
- Se `working_selector` não está vazio, um seletor funcionou

## Exemplos Curl

```bash
# Exemplo 1: Ver HTML da primeira página (método requests)
curl -X GET '{{BASE_URL}}/api/debug/html'

# Exemplo 2: Ver HTML da página 2
curl -X GET '{{BASE_URL}}/api/debug/html?page=2'

# Exemplo 3: Ver HTML usando Playwright
curl -X GET '{{BASE_URL}}/api/debug/html?use_playwright=true'

# Exemplo 4: Ver página 3 com Playwright
curl -X GET '{{BASE_URL}}/api/debug/html?page=3&use_playwright=true'
```
"""
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
    description="""
## O que faz
Gera um relatório completo de debug com todos os detalhes: passos executados, tempo gasto, screenshots (se habilitado) e HTMLs salvos.

## Quando usar
- Quando precisa de informações detalhadas para debugar um problema
- Para entender o que aconteceu durante a extração
- Para ver screenshots e logs de cada passo

## Parâmetros
- **`use_playwright`** (padrão: false): Se deve usar Playwright ou requests.
  - `false` (padrão): Usa método requests
  - `true`: Usa Playwright (gera mais informações de debug)

## Teste Primeiro
1. Teste básico: `GET {{BASE_URL}}/api/debug/detailed`
   - Deve retornar relatório completo
   - Verifique se `report` contém informações
   - Verifique se `report.steps` mostra os passos executados
2. Teste com Playwright: `GET {{BASE_URL}}/api/debug/detailed?use_playwright=true`
   - Deve gerar relatório mais completo
   - Pode incluir screenshots se configurado

## Teste Depois
1. Compare os dois métodos (com e sem Playwright)
   - Veja qual gera mais informações
   - Verifique timings para ver qual é mais rápido

## Como saber que funcionou
- Se `report` não está vazio, o relatório foi gerado
- Se `report.steps` tem itens, os passos foram registrados
- Se `report.timings` tem dados, os tempos foram medidos

## Exemplos Curl

```bash
# Exemplo 1: Gerar relatório completo (método requests)
curl -X GET '{{BASE_URL}}/api/debug/detailed'

# Exemplo 2: Gerar relatório completo com Playwright
curl -X GET '{{BASE_URL}}/api/debug/detailed?use_playwright=true'
```
"""
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

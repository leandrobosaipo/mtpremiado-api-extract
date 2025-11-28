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
Extrai todos os pedidos com todos os detalhes. Você pode pedir todos de uma vez ou usar paginação para pegar em lotes.

## Quando usar
- **Sem parâmetros**: Quando quer TODOS os pedidos de uma vez (pode demorar se houver muitos)
- **Com `limit`**: Quando quer pegar apenas alguns pedidos por vez (ex: 100 por vez)
- **Com `last_id` e `limit`**: Quando quer continuar de onde parou (para pegar os próximos 100 depois dos primeiros 100)

## Parâmetros
- **`last_id`** (opcional): Último ID que você já tem. Retorna apenas pedidos com ID maior que este.
  - Exemplo: `?last_id=1200` → Retorna apenas pedidos com ID > 1200
- **`limit`** (opcional): Quantos pedidos você quer receber.
  - Exemplo: `?limit=100` → Retorna no máximo 100 pedidos
  - Se não usar, retorna TODOS os pedidos

## Teste Primeiro
1. Teste sem parâmetros: `GET {{BASE_URL}}/api/pedidos/full`
   - Deve retornar todos os pedidos
   - Verifique se `total` mostra quantos pedidos foram encontrados
2. Teste com limit pequeno: `GET {{BASE_URL}}/api/pedidos/full?limit=5`
   - Deve retornar apenas 5 pedidos
   - Verifique se `pagination` aparece na resposta
   - Verifique se `pagination.has_more` é `true` ou `false`

## Teste Depois
1. Teste paginação completa:
   - Primeira chamada: `GET {{BASE_URL}}/api/pedidos/full?limit=100`
   - Anote o `pagination.last_id_processed` da resposta
   - Segunda chamada: `GET {{BASE_URL}}/api/pedidos/full?last_id={valor_anotado}&limit=100`
   - Deve retornar os próximos 100 pedidos
2. Teste quando não há mais pedidos:
   - Use um `last_id` muito alto (ex: 999999)
   - Deve retornar lista vazia ou poucos pedidos
   - `pagination.has_more` deve ser `false`

## Como saber que terminou
- Se `pagination.has_more` é `false`, não há mais pedidos
- Se `total` é menor que `limit`, você chegou ao fim
- Se a lista de `pedidos` está vazia, não há mais pedidos

## Exemplos Curl

```bash
# Exemplo 1: Buscar todos os pedidos (sem paginação)
curl -X GET '{{BASE_URL}}/api/pedidos/full'

# Exemplo 2: Buscar apenas 100 pedidos (primeira página)
curl -X GET '{{BASE_URL}}/api/pedidos/full?limit=100'

# Exemplo 3: Buscar próximos 100 pedidos (continuando de onde parou)
# Use o last_id_processed da resposta anterior
curl -X GET '{{BASE_URL}}/api/pedidos/full?last_id=1200&limit=100'

# Exemplo 4: Buscar apenas pedidos mais recentes que um ID específico
curl -X GET '{{BASE_URL}}/api/pedidos/full?last_id=1000'
```
"""
)
async def get_pedidos_full(
    last_id: Optional[int] = Query(None, description="Último ID conhecido. Retorna apenas pedidos com ID > last_id. Exemplo: ?last_id=1200"),
    limit: Optional[int] = Query(None, description="Limite de pedidos a retornar. Se não fornecido, retorna todos. Exemplo: ?limit=100")
) -> PedidosResponseSchema:
    """Endpoint para extrair pedidos com detalhes completos, com suporte a paginação."""
    try:
        # Validação de limit se fornecido
        if limit is not None and limit <= 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="O parâmetro 'limit' deve ser maior que 0"
            )
        
        # Validação de last_id se fornecido
        if last_id is not None and last_id < 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="O parâmetro 'last_id' deve ser maior ou igual a 0"
            )
        
        controller = PedidosController()
        return await controller.extract_all_pedidos_full(last_id=last_id, limit=limit)
        
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

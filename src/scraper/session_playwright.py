"""Módulo de autenticação com Playwright."""

import re
import platform
from typing import Optional
from playwright.async_api import Browser, BrowserContext, Page, async_playwright, TimeoutError as PlaywrightTimeoutError

from src.core.settings import settings
from src.core.logger import get_logger
from src.core.exceptions import AuthenticationError, NetworkError
from src.scraper.debug_helper import DebugHelper

logger = get_logger()


class PlaywrightSession:
    """Gerencia sessão autenticada com Playwright."""
    
    def __init__(self):
        self.playwright = None
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        self._csrf_token: Optional[str] = None
        self.session_id = DebugHelper._get_session_id()
    
    def _get_chromium_args(self) -> list:
        """Retorna argumentos específicos para Chromium baseado na plataforma."""
        args = ['--disable-blink-features=AutomationControlled']
        
        # Workaround para macOS ARM (evita segmentation fault)
        if platform.system() == "Darwin" and platform.machine() == "arm64":
            args.extend([
                '--disable-gpu',
                '--single-process',
                '--no-sandbox',
                '--disable-dev-shm-usage',
                '--disable-software-rasterizer',
                '--disable-setuid-sandbox'
            ])
        
        return args
    
    async def __aenter__(self):
        """Context manager entry (async)."""
        self.playwright = await async_playwright().start()
        
        # No macOS ARM, Chromium tem problemas conhecidos (segmentation fault)
        # Usa Firefox diretamente se estiver disponível
        is_macos_arm = platform.system() == "Darwin" and platform.machine() == "arm64"
        
        if is_macos_arm:
            # Tenta Firefox primeiro no macOS ARM
            try:
                self.browser = await self.playwright.firefox.launch(
                    headless=settings.PLAYWRIGHT_HEADLESS
                )
                logger.info("using_firefox_macos_arm")
            except Exception as e:
                logger.warning("firefox_launch_failed_macos_arm", error=str(e))
                # Fallback para Chromium com argumentos especiais
                try:
                    chromium_args = self._get_chromium_args()
                    self.browser = await self.playwright.chromium.launch(
                        headless=settings.PLAYWRIGHT_HEADLESS,
                        args=chromium_args
                    )
                    logger.info("using_chromium_fallback_macos_arm")
                except Exception as e2:
                    logger.error("browser_launch_failed_macos_arm", chromium_error=str(e2))
                    raise RuntimeError(
                        f"Não foi possível iniciar browser no macOS ARM.\n"
                        f"Firefox falhou: {str(e)}\n"
                        f"Chromium falhou: {str(e2)}\n"
                        f"Por favor, reinstale os browsers: playwright install --force"
                    )
        else:
            # Em outras plataformas, tenta Chromium primeiro
            chromium_args = self._get_chromium_args()
            try:
                self.browser = await self.playwright.chromium.launch(
                    headless=settings.PLAYWRIGHT_HEADLESS,
                    args=chromium_args
                )
            except Exception as e:
                logger.warning("chromium_launch_failed", error=str(e))
                # Fallback para firefox se chromium falhar
                try:
                    self.browser = await self.playwright.firefox.launch(
                        headless=settings.PLAYWRIGHT_HEADLESS
                    )
                    logger.info("using_firefox_fallback")
                except Exception as e2:
                    error_msg = str(e2)
                    logger.error("browser_launch_failed", chromium_error=str(e), firefox_error=str(e2))
                    raise RuntimeError(
                        f"Não foi possível iniciar browser.\n"
                        f"Chromium falhou: {str(e)}\n"
                        f"Firefox falhou: {str(e2)}\n"
                        f"Por favor, instale os browsers: playwright install"
                    )
        
        self.context = await self.browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
        )
        self.page = await self.context.new_page()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit (async)."""
        if self.page:
            await self.page.close()
        if self.context:
            await self.context.close()
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()
    
    async def _get_csrf_token(self) -> str:
        """Obtém o token CSRF da página de login."""
        start_time = DebugHelper.start_timer("get_csrf_token")
        
        try:
            DebugHelper.log_step("csrf_token_start", {"url": settings.MT_PREMIADO_LOGIN_URL})
            
            # Navega para página de login
            await self.page.goto(
                settings.MT_PREMIADO_LOGIN_URL,
                wait_until="domcontentloaded",
                timeout=settings.PLAYWRIGHT_TIMEOUT
            )
            
            DebugHelper.log_step("csrf_token_page_loaded", {"url": self.page.url})
            
            # Screenshot após carregar página de login
            await DebugHelper.take_screenshot(self.page, "csrf_token_page", "login_page")
            
            # Aguarda um pouco para garantir que tudo carregou
            await self.page.wait_for_load_state("domcontentloaded")
            
            # Busca o token CSRF no HTML
            html_content = await self.page.content()
            
            DebugHelper.log_step("csrf_token_html_fetched", {"html_size": len(html_content)})
            
            csrf_match = re.search(
                r'name=["\']_token["\']\s+value=["\']([^"\']+)["\']',
                html_content
            )
            
            if not csrf_match:
                # Tenta outro padrão comum
                csrf_match = re.search(
                    r'csrf-token["\']\s+content=["\']([^"\']+)["\']',
                    html_content
                )
            
            if not csrf_match:
                # Salva HTML para debug se não encontrar token
                await DebugHelper.save_html(self.page, "csrf_token_not_found", "token_not_found")
                raise AuthenticationError("Token CSRF não encontrado")
            
            self._csrf_token = csrf_match.group(1)
            
            DebugHelper.log_step("csrf_token_found", {"token_length": len(self._csrf_token)})
            DebugHelper.end_timer(start_time, "get_csrf_token", {"success": True})
            
            return self._csrf_token
            
        except PlaywrightTimeoutError as e:
            DebugHelper.end_timer(start_time, "get_csrf_token", {"success": False, "error": str(e)})
            await DebugHelper.take_screenshot(self.page, "csrf_token_timeout", "timeout")
            await DebugHelper.save_html(self.page, "csrf_token_timeout", "timeout")
            logger.error("network_error", error=str(e), step="get_csrf_token")
            raise NetworkError(f"Timeout ao obter CSRF token: {str(e)}")
        except Exception as e:
            DebugHelper.end_timer(start_time, "get_csrf_token", {"success": False, "error": str(e)})
            await DebugHelper.take_screenshot(self.page, "csrf_token_error", "error")
            await DebugHelper.save_html(self.page, "csrf_token_error", "error")
            logger.error("network_error", error=str(e), step="get_csrf_token")
            raise NetworkError(f"Erro ao obter CSRF token: {str(e)}")
    
    async def login(self) -> Page:
        """Realiza login e retorna página autenticada."""
        start_time = DebugHelper.start_timer("login")
        
        try:
            DebugHelper.log_step("login_start")
            
            # Obtém CSRF token
            csrf_token = await self._get_csrf_token()
            
            DebugHelper.log_step("login_filling_email")
            # Preenche formulário de login
            await self.page.fill('input[name="email"]', settings.MT_PREMIADO_EMAIL)
            DebugHelper.log_step("login_email_filled")
            
            DebugHelper.log_step("login_filling_password")
            await self.page.fill('input[name="password"]', settings.MT_PREMIADO_SENHA)
            DebugHelper.log_step("login_password_filled")
            
            # Screenshot antes de clicar em submit
            await DebugHelper.take_screenshot(self.page, "login_before_submit", "before_submit")
            
            DebugHelper.log_step("login_clicking_submit")
            # Submete formulário
            await self.page.click('button[type="submit"], input[type="submit"]')
            
            # Estratégia melhorada de wait conditions
            # Tenta múltiplas estratégias para evitar timeout desnecessário
            login_success = False
            
            try:
                # Estratégia 1: Aguarda URL mudar (mais rápido)
                await self.page.wait_for_url(
                    lambda url: "login" not in url.lower(),
                    timeout=10000  # 10 segundos
                )
                login_success = True
                DebugHelper.log_step("login_url_changed", {"url": self.page.url})
            except PlaywrightTimeoutError:
                DebugHelper.log_step("login_url_wait_timeout", {"trying_selector": True})
                
                # Estratégia 2: Aguarda elementos específicos que aparecem após login
                try:
                    # Verifica se sidebar (elemento comum após login) aparece
                    await self.page.wait_for_selector(
                        ".nk-sidebar, .sidebar, [data-sidebar], nav",
                        timeout=10000,
                        state="visible"
                    )
                    login_success = True
                    DebugHelper.log_step("login_selector_found", {"selector": ".nk-sidebar"})
                except PlaywrightTimeoutError:
                    DebugHelper.log_step("login_selector_timeout", {"trying_domcontentloaded": True})
                    
                    # Estratégia 3: Fallback para domcontentloaded
                    try:
                        await self.page.wait_for_load_state("domcontentloaded", timeout=5000)
                        login_success = True
                        DebugHelper.log_step("login_domcontentloaded")
                    except PlaywrightTimeoutError:
                        DebugHelper.log_step("login_all_strategies_failed")
            
            # Aguarda um pouco mais para garantir que Livewire carregou
            await self.page.wait_for_timeout(2000)
            
            # Screenshot após tentativa de login
            await DebugHelper.take_screenshot(self.page, "login_after_submit", "after_submit")
            
            # Verifica se login foi bem-sucedido
            current_url = self.page.url
            
            # Verifica elementos esperados após login
            sidebar_check = await DebugHelper.check_element_exists(self.page, ".nk-sidebar", "sidebar")
            menu_check = await DebugHelper.check_element_exists(self.page, ".nk-menu", "menu")
            
            DebugHelper.log_step("login_verification", {
                "url": current_url,
                "sidebar_exists": sidebar_check.get("exists", False),
                "menu_exists": menu_check.get("exists", False)
            })
            
            if "login" in current_url.lower():
                await DebugHelper.save_html(self.page, "login_failed", "still_on_login_page")
                logger.error("login_failed", url=current_url)
                raise AuthenticationError("Falha ao autenticar - ainda na página de login")
            
            DebugHelper.log_step("login_success", {"url": current_url})
            DebugHelper.end_timer(start_time, "login", {"success": True, "url": current_url})
            
            logger.info("login_success", email=settings.MT_PREMIADO_EMAIL)
            return self.page
            
        except AuthenticationError:
            DebugHelper.end_timer(start_time, "login", {"success": False, "error": "AuthenticationError"})
            await DebugHelper.take_screenshot(self.page, "login_auth_error", "auth_error")
            await DebugHelper.save_html(self.page, "login_auth_error", "auth_error")
            raise
        except PlaywrightTimeoutError as e:
            DebugHelper.end_timer(start_time, "login", {"success": False, "error": str(e)})
            await DebugHelper.take_screenshot(self.page, "login_timeout", "timeout")
            await DebugHelper.save_html(self.page, "login_timeout", "timeout")
            logger.error("login_timeout", error=str(e))
            raise AuthenticationError(f"Timeout durante login: {str(e)}")
        except Exception as e:
            DebugHelper.end_timer(start_time, "login", {"success": False, "error": str(e)})
            await DebugHelper.take_screenshot(self.page, "login_error", "error")
            await DebugHelper.save_html(self.page, "login_error", "error")
            logger.error("login_failed", error=str(e))
            raise AuthenticationError(f"Erro durante login: {str(e)}")
    
    def get_page(self) -> Page:
        """Retorna a página autenticada."""
        if self.page is None:
            raise RuntimeError("Sessão não inicializada. Use 'async with PlaywrightSession() as session:'")
        return self.page

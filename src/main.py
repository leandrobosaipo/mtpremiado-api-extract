"""Aplicação principal FastAPI."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from src.core.settings import settings
from src.core.logger import get_logger
from src.core.init_dirs import ensure_directories
from src.api.routes.pedidos_routes import router as pedidos_router, debug_router

logger = get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Gerencia ciclo de vida da aplicação."""
    logger.info("app_startup", version=settings.API_VERSION)
    # Garante que todos os diretórios necessários existam
    ensure_directories()
    yield
    logger.info("app_shutdown")


app = FastAPI(
    title=settings.API_TITLE,
    version=settings.API_VERSION,
    description=settings.API_DESCRIPTION,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan
)

# CORS - Suporta domínios dinâmicos via variável de ambiente
cors_origins = settings.CORS_ORIGINS.split(",") if settings.CORS_ORIGINS != "*" else ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Rotas
app.include_router(pedidos_router)
app.include_router(debug_router)


@app.get("/", tags=["health"])
async def root():
    """Endpoint raiz."""
    return {
        "name": settings.API_TITLE,
        "version": settings.API_VERSION,
        "status": "online"
    }


@app.get("/health", tags=["health"])
async def health():
    """Endpoint de health check."""
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "src.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )


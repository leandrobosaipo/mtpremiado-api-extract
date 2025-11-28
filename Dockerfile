FROM python:3.11-slim

WORKDIR /app

# Variável de ambiente para porta (EasyPanel pode usar portas dinâmicas)
ENV PORT=8000

# Instala dependências do sistema necessárias para Playwright
RUN apt-get update && apt-get install -y \
    gcc \
    wget \
    gnupg \
    libnss3 \
    libnspr4 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libdbus-1-3 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libasound2 \
    libpango-1.0-0 \
    libcairo2 \
    && rm -rf /var/lib/apt/lists/*

# Copia requirements e instala dependências Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Instala Playwright browsers (apenas chromium para produção)
# Para usar Playwright, defina USE_PLAYWRIGHT=true nas variáveis de ambiente
RUN playwright install chromium || true

# Copia o projeto
COPY . .

# Cria diretórios necessários
RUN mkdir -p data/exports debug/html debug/screenshots && \
    chmod -R 755 data debug

# Expõe a porta (padrão 8000, mas pode ser sobrescrita via variável PORT)
EXPOSE 8000

# Healthcheck para EasyPanel
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:${PORT:-8000}/health')" || exit 1

# Comando para rodar a aplicação (usa variável PORT ou padrão 8000)
CMD sh -c "uvicorn src.main:app --host 0.0.0.0 --port ${PORT:-8000}"


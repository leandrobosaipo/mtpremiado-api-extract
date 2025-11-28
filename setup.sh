#!/bin/bash

# Script de setup rápido para macOS

echo "🚀 Configurando MT Premiado API Extract..."

# Criar ambiente virtual
if [ ! -d "venv" ]; then
    echo "📦 Criando ambiente virtual..."
    python3 -m venv venv
fi

# Ativar ambiente virtual
echo "🔧 Ativando ambiente virtual..."
source venv/bin/activate

# Instalar dependências
echo "📥 Instalando dependências..."
pip install --upgrade pip
pip install -r requirements.txt

# Criar .env se não existir
if [ ! -f ".env" ]; then
    echo "📝 Criando arquivo .env..."
    cp .env.example .env
    echo "⚠️  IMPORTANTE: Edite o arquivo .env com suas credenciais!"
fi

echo "✅ Setup concluído!"
echo ""
echo "Para iniciar a aplicação:"
echo "  source venv/bin/activate"
echo "  uvicorn src.main:app --reload --port 8000"
echo ""
echo "Acesse:"
echo "  - API: http://localhost:8000"
echo "  - Swagger: http://localhost:8000/docs"


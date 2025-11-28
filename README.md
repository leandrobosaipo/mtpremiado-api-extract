# 📘 MT Premiado API Extract

API Python (FastAPI) para extração de pedidos detalhados do MT Premiado.

## 🎯 Objetivo

Esta API realiza:

1. Login no painel do MT Premiado usando sessão autenticada
2. Extração de todos os pedidos de todas as páginas (paginação infinita)
3. Extração de detalhes completos de cada pedido
4. Retorno em JSON padronizado

## 🚀 Instalação e Execução

### Pré-requisitos

- Python 3.11+
- pip
- Playwright (instalado automaticamente via pip, mas browsers precisam ser instalados separadamente)

### Instalação Local (macOS)

```bash
# Criar ambiente virtual
python3 -m venv venv

# Ativar ambiente virtual
source venv/bin/activate

# Instalar dependências
pip install -r requirements.txt

# Instalar browsers do Playwright (necessário apenas se usar USE_PLAYWRIGHT=true)
playwright install chromium

# Copiar arquivo de ambiente
cp .env.example .env

# Editar .env com suas credenciais
nano .env

# Executar aplicação
uvicorn src.main:app --reload --port 8000
```

A API estará disponível em:
- **API**: http://localhost:8000
- **Swagger**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

## 🐳 Docker

### Build

```bash
docker build -t mtpremiado-api-extract .
```

### Run

```bash
docker run -p 8000:8000 --env-file .env mtpremiado-api-extract
```

## 📡 Endpoints

### `GET /api/pedidos/full`

Extrai todos os pedidos com detalhes completos.

**Nota:** O método usado (requests ou Playwright) é determinado pela variável `USE_PLAYWRIGHT` no `.env`. Playwright é necessário para sites que carregam conteúdo via JavaScript (como Livewire).

**Comportamento:**
- Busca todos os pedidos de todas as páginas
- Salva automaticamente o maior ID encontrado em `data/last_order_state.json` (mesmo comportamento do endpoint incremental)

**Resposta:** JSON com todos os pedidos encontrados. O JSON também é salvo automaticamente em `data/exports/pedidos_{timestamp}.json` se `EXPORT_JSON=true`.

### `GET /api/pedidos/incremental?last_order_id={id}`

Extrai apenas pedidos novos a partir do último ID conhecido. Ideal para uso com n8n em intervalos regulares.

**Parâmetros:**
- `last_order_id` (opcional): ID do último pedido processado. Se não fornecido, usa estado salvo em `data/last_order_state.json`.

**Sobre o ID do Pedido:**
- O ID usado é o campo `"id"` no JSON retornado (ex: `{"id": 1337, ...}`)
- Este ID vem do checkbox `input.model-id-checkbox` ou do link `#1313` na primeira coluna da tabela
- O sistema salva automaticamente o maior ID encontrado após cada execução bem-sucedida
- Tanto `/full` quanto `/incremental` salvam o estado automaticamente

**Comportamento:**
- Se não há estado salvo, busca todos os pedidos (comportamento inicial)
- Se há estado salvo ou `last_order_id` fornecido, busca apenas pedidos com ID maior que o último conhecido
- Para automaticamente quando encontra um pedido com ID <= `last_order_id`
- Salva automaticamente o maior ID encontrado após a extração

**Resposta:** JSON apenas com pedidos novos. O JSON também é salvo automaticamente em `data/exports/pedidos_{timestamp}.json` se `EXPORT_JSON=true`.

**Exemplo de uso:**
```bash
# Primeira chamada (sem estado)
curl 'http://localhost:8000/api/pedidos/incremental'
# Retorna todos os pedidos e salva estado

# Segunda chamada (com estado salvo)
curl 'http://localhost:8000/api/pedidos/incremental'
# Retorna apenas pedidos novos desde a última execução

# Com last_order_id explícito
curl 'http://localhost:8000/api/pedidos/incremental?last_order_id=100'
# Retorna apenas pedidos com ID > 100
```

### `GET /api/debug/html?page=1&use_playwright=false`

Endpoint de debug para inspecionar HTML retornado. Útil para ajustar seletores CSS.

**Parâmetros:**
- `page`: Número da página (padrão: 1)
- `use_playwright`: Usar Playwright ao invés de requests (padrão: false)

### `GET /api/debug/detailed?use_playwright=false`

Endpoint de debug detalhado que retorna relatório completo incluindo steps, timings, screenshots e HTMLs salvos.

**Parâmetros:**
- `use_playwright`: Usar Playwright ao invés de requests (padrão: false)

**Resposta:**
```json
{
  "method": "playwright",
  "report": {
    "session_id": "abc12345",
    "timestamp": "2025-11-22T15:40:00Z",
    "steps": [...],
    "timings": [...],
    "screenshots": [...],
    "html_files": [...],
    "summary": {
      "total_steps": 10,
      "total_timings": 5,
      "total_screenshots": 3,
      "total_html_files": 2,
      "total_duration_ms": 15000.5
    }
  }
}
```

## 🔍 Modo Debug

O sistema inclui um modo de debug completo que permite acompanhar cada etapa do processo de scraping.

### Configuração

Adicione as seguintes variáveis ao seu `.env`:

```bash
# Ativa modo debug completo
DEBUG_MODE=true

# Salva screenshots em pontos críticos (apenas com Playwright)
DEBUG_SCREENSHOTS=true

# Loga tempos de cada operação
DEBUG_TIMING=true

# Loga cada seletor CSS testado
DEBUG_SELECTORS=true

# Loga tempos de espera
DEBUG_WAIT_TIMES=true

# Diretório para arquivos de debug (padrão: "debug")
DEBUG_DIR=debug
```

### Como Usar

1. **Ative o modo debug** adicionando as variáveis acima ao `.env`

2. **Execute a API** normalmente:
```bash
uvicorn src.main:app --reload --port 8000
```

3. **Os logs detalhados** aparecerão no console com informações sobre:
   - Cada etapa do processo (login, navegação, extração)
   - Tempos de cada operação
   - Seletores testados e quantos elementos foram encontrados
   - Elementos verificados (sidebar, menu, tabelas)

4. **Screenshots** serão salvos em `debug/screenshots/` (se `DEBUG_SCREENSHOTS=true`)

5. **HTMLs** serão salvos em `debug/html/` (se `DEBUG_SAVE_HTML=true`)

6. **Obtenha relatório completo** via endpoint:
```bash
curl 'http://localhost:8000/api/debug/detailed?use_playwright=true'
```

### Interpretando os Logs

- **`debug_step_*`**: Cada etapa do processo (ex: `debug_step_login_start`, `debug_step_fetch_page_start`)
- **`debug_timing`**: Tempo gasto em cada operação (em milissegundos)
- **`debug_element_check`**: Verificação de elementos na página (existe, quantos encontrados)
- **`selector_tested`**: Cada seletor CSS testado e quantos elementos encontrou
- **`selector_worked`**: Seletor que funcionou e encontrou elementos

### Screenshots

Screenshots são salvos automaticamente em pontos críticos:
- Antes e depois do login
- Após carregar cada página
- Quando seletores encontram elementos
- Em caso de erros ou timeouts

### HTMLs Salvos

HTMLs são salvos automaticamente:
- Após carregar cada página
- Quando seletores encontram elementos
- Em caso de erros ou timeouts

### Notas Importantes

- O modo debug pode tornar a execução mais lenta (especialmente com screenshots)
- Use apenas em desenvolvimento
- Screenshots podem ocupar espaço significativo
- Logs detalhados podem ser muito verbosos

**Resposta:**

```json
{
  "total": 1306,
  "gerado_em": "2025-11-22T04:12:55Z",
  "pedidos": [
    {
      "id": 1308,
      "criado": "1 hora atrás",
      "status": "Aprovado",
      "sorteio": "BIZ 0KM",
      "bilhetes_totais_sorteio": "10000000 bilhetes",
      "cliente": "Nome",
      "telefone": "+55 66 99999-9999",
      "qtd_bilhetes": "100 bilhetes",
      "valor": "R$ 10,00",
      "detalhes_url": "https://omtpremiado.com.br/pedidos/1308",
      "detalhe_data_hora": "21/11/2025 21:15:25",
      "detalhe_email": "[email protected]",
      "detalhe_telefone": "+55 66 99999-9999",
      "detalhe_cpf": "026.750.491-82",
      "detalhe_nascimento": "24/07/1994",
      "detalhe_data_compra": "21/11/2025",
      "detalhe_pagamento_id": "ABC123",
      "detalhe_subtotal": "R$ 0,10",
      "detalhe_descontos": "R$ 0,00",
      "detalhe_total": "R$ 0,10"
    }
  ]
}
```

## 🔧 Variáveis de Ambiente

Crie um arquivo `.env` baseado no `.env.example`:

```env
MT_PREMIADO_EMAIL=seu_email@exemplo.com
MT_PREMIADO_SENHA=sua_senha_aqui
```

Variáveis opcionais:

- `MT_PREMIADO_BASE_URL`: URL base (padrão: https://omtpremiado.com.br)
- `MT_PREMIADO_LOGIN_URL`: URL de login
- `MT_PREMIADO_PEDIDOS_URL`: URL de pedidos
- `REQUEST_TIMEOUT`: Timeout de requisições em segundos (padrão: 30)
- `MAX_RETRIES`: Máximo de tentativas (padrão: 3)
- `RETRY_DELAY`: Delay entre tentativas em segundos (padrão: 2)
- `LOG_LEVEL`: Nível de log (padrão: INFO)
- `USE_PLAYWRIGHT`: Usar Playwright para renderização JavaScript (padrão: false)
- `PLAYWRIGHT_HEADLESS`: Executar browser em modo headless (padrão: true)
- `PLAYWRIGHT_TIMEOUT`: Timeout do Playwright em milissegundos (padrão: 30000)
- `PLAYWRIGHT_WAIT_FOR_SELECTOR`: Seletor CSS para aguardar carregamento (padrão: ".nk-tb-item")
- `DEBUG_HTML`: Ativar logs detalhados de HTML (padrão: false)
- `DEBUG_SAVE_HTML`: Salvar HTML em arquivos para debug (padrão: false)
- `EXPORT_JSON`: Salvar JSON de retorno em arquivo (padrão: true)
- `DATA_DIR`: Diretório para dados (padrão: "data")
- `EXPORTS_DIR`: Diretório para JSONs exportados (padrão: "data/exports")
- `STATE_FILE`: Arquivo de estado do último pedido (padrão: "data/last_order_state.json")

## 📁 Estrutura do Projeto

```
project/
├── src/
│   ├── api/
│   │   ├── controllers/
│   │   │   └── pedidos_controller.py
│   │   ├── schemas/
│   │   │   └── pedido_schema.py
│   │   ├── routes/
│   │   │   └── pedidos_routes.py
│   │   └── __init__.py
│   ├── core/
│   │   ├── auth.py
│   │   ├── settings.py
│   │   ├── logger.py
│   │   ├── exceptions.py
│   │   ├── state_manager.py
│   │   └── init_dirs.py
│   ├── scraper/
│   │   ├── listagem.py
│   │   ├── detalhes.py
│   │   ├── listagem_playwright.py
│   │   ├── detalhes_playwright.py
│   │   ├── session_playwright.py
│   │   ├── parser.py
│   │   ├── session.py
│   │   └── debug_helper.py
│   ├── main.py
│   └── __init__.py
├── data/
│   ├── exports/          # JSONs exportados (gitignored)
│   └── last_order_state.json  # Estado do último pedido (gitignored)
├── debug/                # Arquivos de debug (gitignored)
│   ├── html/
│   └── screenshots/
├── tests/
│   ├── test_listagem.py
│   ├── test_detalhes.py
│   └── test_api.py
├── Dockerfile
├── requirements.txt
├── .env.example
├── .gitignore
├── README.md
└── pyproject.toml
```

### Diretórios e Arquivos Importantes

- **`data/exports/`**: JSONs exportados automaticamente após cada execução (se `EXPORT_JSON=true`)
- **`data/last_order_state.json`**: Estado persistente do último pedido processado (usado pelo endpoint incremental)
- **`debug/`**: Arquivos de debug (screenshots, HTMLs) quando modo debug está ativo

## 🧪 Testes

```bash
# Instalar dependências de desenvolvimento
pip install -e ".[dev]"

# Executar testes
pytest
```

## 🔄 Uso com n8n

O endpoint `/api/pedidos/incremental` foi projetado especificamente para uso com n8n em intervalos regulares (ex: a cada 1 hora).

### Configuração no n8n

1. **Criar workflow** com trigger de intervalo (ex: Cron a cada 1 hora)

2. **Adicionar nó HTTP Request**:
   - Método: `GET`
   - URL: `https://seu-dominio.com/api/pedidos/incremental`
   - (Opcional) Query Parameters: `last_order_id` se quiser especificar manualmente

3. **Processar resposta**:
   - O endpoint retorna apenas pedidos novos desde a última execução
   - O estado é salvo automaticamente em `data/last_order_state.json`
   - Não é necessário passar `last_order_id` manualmente após a primeira execução

### Como Funciona

- **Primeira execução**: Busca todos os pedidos e salva o maior ID encontrado
- **Execuções subsequentes**: Busca apenas pedidos com ID maior que o último salvo
- **Otimização**: Para de buscar quando encontra um pedido com ID <= último conhecido

### Arquivos Gerados

- **JSONs exportados**: `data/exports/pedidos_{timestamp}.json`
- **Estado salvo**: `data/last_order_state.json`

## 🚢 Deploy no EasyPanel

Para instruções completas e detalhadas de deploy no EasyPanel, consulte o arquivo **[EASYPANEL.md](./EASYPANEL.md)**.

### Resumo Rápido

1. **Criar novo app via Dockerfile**
   - Selecione "Dockerfile" como método de build
   - Configure o domínio: `api.meudominio.com`

2. **Variáveis de Ambiente Obrigatórias**
   - `MT_PREMIADO_EMAIL`: Email para login
   - `MT_PREMIADO_SENHA`: Senha para login
   - `PORT`: Porta da aplicação (padrão: 8000)

3. **Variáveis de Ambiente Opcionais**
   - `USE_PLAYWRIGHT`: Usar Playwright (padrão: false)
   - `EXPORT_JSON`: Salvar JSONs (padrão: true)
   - `CORS_ORIGINS`: Origens permitidas (padrão: "*")
   - Veja `.env.example` para todas as opções

4. **Volumes Persistentes (Obrigatório)**
   - `/app/data`: Para manter estado e exports (obrigatório para extração incremental)

5. **Build e Deploy**
   - O EasyPanel fará o build automaticamente
   - Monitore os logs para verificar se está funcionando
   - A aplicação roda em `0.0.0.0:8000` para aceitar conexões externas

6. **Acesso ao Swagger**
   - Após deploy, acesse `https://seu-dominio.com/docs` para documentação interativa
   - O Swagger funciona independente do localhost, aceitando domínios dinâmicos

**📖 Para instruções detalhadas, troubleshooting e configurações avançadas, consulte [EASYPANEL.md](./EASYPANEL.md)**

## 📦 Deploy no GitHub

### Preparação

1. **Verificar .gitignore**
   - Certifique-se de que `.env`, `data/exports/*.json`, `data/last_order_state.json` e arquivos de debug estão ignorados
   - A estrutura de diretórios (`data/`, `debug/`) pode ser commitada vazia

2. **Criar repositório**
   ```bash
   git init
   git add .
   git commit -m "Initial commit"
   git remote add origin https://github.com/seu-usuario/mtpremiado-api-extract.git
   git push -u origin main
   ```

3. **Criar .env.example**
   - Documente todas as variáveis necessárias
   - Não inclua valores reais de credenciais

### Estrutura para Commit

- ✅ Código fonte
- ✅ Dockerfile
- ✅ requirements.txt
- ✅ README.md
- ✅ Estrutura de diretórios (`data/`, `debug/`)
- ❌ Arquivo `.env` (deve estar no .gitignore)
- ❌ JSONs exportados (`data/exports/*.json`)
- ❌ Estado (`data/last_order_state.json`)
- ❌ Arquivos de debug (`debug/**/*.png`, `debug/**/*.html`)

## 📊 Logs

A aplicação usa logs estruturados em JSON. Eventos principais:

- `login_success`: Login realizado com sucesso
- `login_failed`: Falha no login
- `scraping_page_start`: Início de scraping de página
- `scraping_page_complete`: Página de scraping concluída
- `order_detail_success`: Detalhes de pedido extraídos com sucesso
- `order_detail_failed`: Falha ao extrair detalhes
- `scraping_finished`: Scraping finalizado
- `emitted_response`: Resposta emitida

## 🔒 Segurança

- ✅ Variáveis de ambiente para credenciais
- ✅ Nunca loga credenciais
- ✅ HTTPS obrigatório em produção
- ✅ Timeout global configurável
- ✅ Retry automático com backoff exponencial

## 📝 Notas Importantes

### Métodos de Extração

A API suporta dois métodos de extração:

1. **Requests (padrão)**: Usa `requests` e `BeautifulSoup` para extrair dados do HTML estático. Mais rápido, mas não funciona com conteúdo carregado via JavaScript.

2. **Playwright**: Usa Playwright para renderizar JavaScript e extrair dados do DOM renderizado. Mais lento, mas necessário para sites que usam Livewire ou outras tecnologias SPA.

Para usar Playwright, defina `USE_PLAYWRIGHT=true` no `.env`. O sistema automaticamente faz fallback para requests se Playwright falhar.

### Ajuste de Seletores CSS

Os seletores CSS foram atualizados baseados na estrutura HTML real do site MT Premiado. Arquivos principais:

- `src/scraper/listagem.py` / `listagem_playwright.py`: Seletores para tabela de pedidos
- `src/scraper/detalhes.py` / `detalhes_playwright.py`: Seletores para página de detalhes
- `src/scraper/parser.py`: Lógica de extração de dados

### Teste Local Primeiro

Antes de fazer deploy, teste localmente com suas credenciais reais:
1. Teste com `USE_PLAYWRIGHT=false` primeiro (método requests)
2. Se não encontrar pedidos, teste com `USE_PLAYWRIGHT=true` (método Playwright)
3. Use o endpoint `/api/debug/html` para inspecionar o HTML retornado

## 📄 Licença

Este projeto é privado e proprietário.

## 👤 Autor

Desenvolvido conforme PRD especificado.


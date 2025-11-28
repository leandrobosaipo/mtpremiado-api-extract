# Guia Completo da API - MT Premiado Extract

Este guia explica como usar cada endpoint da API de forma simples e clara.

## Antes de Começar

### O que você precisa
- URL da API (ex: `http://localhost:8000` ou `https://sua-api.com`)
- Credenciais configuradas no servidor (não precisa enviar nas requisições)

### Como testar
Você pode usar:
- **Swagger UI**: Acesse `{{BASE_URL}}/docs` no navegador
- **curl**: Comandos de linha de comando (exemplos abaixo)
- **Postman**: Importe a especificação OpenAPI de `{{BASE_URL}}/openapi.json`
- **Qualquer cliente HTTP**: Use os exemplos curl como referência

---

## Endpoints de Health Check

### 1. GET / (Raiz)

**O que faz:** Mostra informações básicas da API.

**Quando usar:** Primeiro teste para ver se a API está funcionando.

**Teste Primeiro:**
```bash
curl -X GET '{{BASE_URL}}/'
```

**O que esperar:**
```json
{
  "name": "MT Premiado API Extract",
  "version": "1.0.0",
  "status": "online"
}
```

**Como saber que funcionou:**
- Se `status` é "online", a API está rodando
- Se você recebeu uma resposta, está tudo conectado

---

### 2. GET /health

**O que faz:** Verifica se a API está saudável.

**Quando usar:** Para monitoramento ou verificação rápida.

**Teste Primeiro:**
```bash
curl -X GET '{{BASE_URL}}/health'
```

**O que esperar:**
```json
{
  "status": "healthy"
}
```

**Como saber que funcionou:**
- Se `status` é "healthy", tudo está ok

---

## Endpoints de Pedidos

### 3. GET /api/pedidos/full

**O que faz:** Extrai TODOS os pedidos com todos os detalhes.

**Quando usar:**
- Quando quer TODOS os pedidos de uma vez
- Para fazer backup completo
- Quando não se importa em esperar (pode demorar se houver muitos pedidos)

**Parâmetros:**
- `last_id` (opcional): Último ID que você já tem. Retorna apenas pedidos com ID maior.
  - Exemplo: `?last_id=1200` → Retorna apenas pedidos com ID > 1200
- `limit` (opcional): Quantos pedidos você quer receber.
  - Exemplo: `?limit=100` → Retorna no máximo 100 pedidos
  - Se não usar, retorna TODOS os pedidos

**Teste Primeiro (sem parâmetros):**
```bash
curl -X GET '{{BASE_URL}}/api/pedidos/full'
```

**O que esperar:**
- Lista com TODOS os pedidos
- Campo `total` mostra quantos pedidos foram encontrados
- Campo `pagination` NÃO aparece (só aparece quando usa `limit`)

**Teste Depois (com limit):**
```bash
# Buscar apenas 10 pedidos para testar
curl -X GET '{{BASE_URL}}/api/pedidos/full?limit=10'
```

**O que esperar:**
- Lista com no máximo 10 pedidos
- Campo `pagination` aparece na resposta
- Campo `pagination.has_more` mostra se há mais pedidos
- Campo `pagination.last_id_processed` mostra o último ID retornado

**Teste de Paginação Completa:**

**Passo 1:** Buscar primeira página
```bash
curl -X GET '{{BASE_URL}}/api/pedidos/full?limit=100'
```

**O que fazer:**
1. Anote o valor de `pagination.last_id_processed` da resposta
2. Anote se `pagination.has_more` é `true` ou `false`

**Passo 2:** Se `has_more` for `true`, buscar próxima página
```bash
# Use o last_id_processed do passo anterior
curl -X GET '{{BASE_URL}}/api/pedidos/full?last_id=1200&limit=100'
```

**Repita:** Continue até que `has_more` seja `false`.

**Como saber que terminou:**
- Se `pagination.has_more` é `false`, não há mais pedidos
- Se `total` é menor que `limit`, você chegou ao fim
- Se a lista de `pedidos` está vazia, não há mais pedidos

**Exemplo de Resposta com Paginação:**
```json
{
  "total": 100,
  "gerado_em": "2025-11-22T04:12:55Z",
  "pedidos": [
    {
      "id": 1308,
      "criado": "1 hora atrás",
      "status": "Aprovado",
      ...
    }
  ],
  "pagination": {
    "last_id_processed": 1200,
    "has_more": true,
    "total_available": null,
    "limit": 100,
    "last_id_requested": null
  }
}
```

**Erros Comuns:**
- **400 Bad Request**: `limit` deve ser maior que 0, ou `last_id` deve ser >= 0
- **401 Unauthorized**: Problema de autenticação (verifique credenciais no servidor)
- **500 Internal Server Error**: Erro no servidor (verifique logs)

---

### 4. GET /api/pedidos/incremental

**O que faz:** Extrai apenas pedidos NOVOS que ainda não foram processados.

**Quando usar:**
- Quando quer pegar apenas pedidos que ainda não processou
- Para usar com automação (n8n, cron, etc) que roda de tempos em tempos
- Quando não quer processar tudo de novo, só o que mudou

**Parâmetros:**
- `last_order_id` (opcional): ID do último pedido que você já processou.
  - Se não fornecer, usa o último ID salvo automaticamente
  - Exemplo: `?last_order_id=1200` → Retorna apenas pedidos com ID > 1200

**Teste Primeiro (sem parâmetros):**
```bash
curl -X GET '{{BASE_URL}}/api/pedidos/incremental'
```

**O que esperar:**
- Se for a primeira vez, retorna TODOS os pedidos
- Se já rodou antes, retorna apenas os novos desde a última vez
- O sistema salva automaticamente o último ID processado

**Teste Depois (com ID específico):**
```bash
curl -X GET '{{BASE_URL}}/api/pedidos/incremental?last_order_id=1300'
```

**O que esperar:**
- Apenas pedidos com ID maior que 1300
- Se não houver pedidos novos, retorna lista vazia (`total: 0`)

**Fluxo de Uso Recomendado:**

**Primeira vez:**
```bash
curl -X GET '{{BASE_URL}}/api/pedidos/incremental'
```
- Processa todos os pedidos
- Sistema salva automaticamente o último ID

**Próximas vezes (ex: 1 hora depois):**
```bash
curl -X GET '{{BASE_URL}}/api/pedidos/incremental'
```
- Retorna apenas pedidos novos desde a última chamada
- Sistema atualiza automaticamente o último ID

**Como saber que terminou:**
- Se `total` é 0, não há pedidos novos
- Se a lista de `pedidos` está vazia, está tudo atualizado

**Exemplo de Resposta:**
```json
{
  "total": 5,
  "gerado_em": "2025-11-22T04:12:55Z",
  "pedidos": [
    {
      "id": 1309,
      "criado": "30 minutos atrás",
      "status": "Aprovado",
      ...
    }
  ]
}
```

**Nota:** Este endpoint NÃO inclui `pagination` porque sempre retorna todos os pedidos novos (não há limite).

---

## Endpoints de Debug

### 5. GET /api/debug/html

**O que faz:** Mostra o HTML da página de pedidos e informações sobre a estrutura.

**Quando usar:**
- Para ver o HTML que está sendo extraído
- Para debugar problemas de extração
- Para entender a estrutura da página

**Parâmetros:**
- `page` (padrão: 1): Qual página você quer ver.
  - Exemplo: `?page=2` → Mostra HTML da página 2
- `use_playwright` (padrão: false): Se deve usar Playwright ou requests.
  - `false` (padrão): Usa método requests (mais rápido)
  - `true`: Usa Playwright (melhor para JavaScript)

**Teste Primeiro:**
```bash
curl -X GET '{{BASE_URL}}/api/debug/html'
```

**O que esperar:**
- Campo `html_size` mostra o tamanho do HTML
- Campo `rows_found` mostra quantos pedidos foram encontrados
- Campo `html_preview` mostra um pedaço do HTML
- Campo `working_selector` mostra qual seletor CSS funcionou

**Teste Depois:**
```bash
# Ver página 2
curl -X GET '{{BASE_URL}}/api/debug/html?page=2'

# Ver com Playwright
curl -X GET '{{BASE_URL}}/api/debug/html?use_playwright=true'
```

**Como saber que funcionou:**
- Se `html_size` é maior que 0, o HTML foi carregado
- Se `rows_found` é maior que 0, pedidos foram encontrados
- Se `working_selector` não está vazio, um seletor funcionou

**Exemplo de Resposta:**
```json
{
  "page": 1,
  "method": "requests",
  "html_size": 152340,
  "html_preview": "<html>...",
  "selectors_tested": {
    "working_selector": ".nk-tb-item:not(.nk-tb-head)",
    "rows_found": 25
  },
  "first_row_preview": "<div class=\"nk-tb-item\">...",
  "example_pedido": {
    "id": 1308,
    "criado": "1 hora atrás",
    ...
  }
}
```

---

### 6. GET /api/debug/detailed

**O que faz:** Gera um relatório completo de debug com todos os detalhes.

**Quando usar:**
- Quando precisa de informações detalhadas para debugar um problema
- Para entender o que aconteceu durante a extração
- Para ver screenshots e logs de cada passo

**Parâmetros:**
- `use_playwright` (padrão: false): Se deve usar Playwright ou requests.
  - `false` (padrão): Usa método requests
  - `true`: Usa Playwright (gera mais informações)

**Teste Primeiro:**
```bash
curl -X GET '{{BASE_URL}}/api/debug/detailed'
```

**O que esperar:**
- Campo `report` com informações detalhadas
- Campo `report.steps` mostra os passos executados
- Campo `report.timings` mostra os tempos gastos
- Se configurado, pode incluir screenshots

**Teste Depois:**
```bash
curl -X GET '{{BASE_URL}}/api/debug/detailed?use_playwright=true'
```

**Como saber que funcionou:**
- Se `report` não está vazio, o relatório foi gerado
- Se `report.steps` tem itens, os passos foram registrados
- Se `report.timings` tem dados, os tempos foram medidos

---

## Fluxo de Teste Recomendado

### Para começar a usar a API:

1. **Teste se a API está funcionando:**
   ```bash
   curl -X GET '{{BASE_URL}}/'
   ```

2. **Teste health check:**
   ```bash
   curl -X GET '{{BASE_URL}}/health'
   ```

3. **Teste endpoint básico (sem parâmetros):**
   ```bash
   curl -X GET '{{BASE_URL}}/api/pedidos/full?limit=5'
   ```

4. **Teste paginação:**
   ```bash
   # Primeira página
   curl -X GET '{{BASE_URL}}/api/pedidos/full?limit=100'
   
   # Próxima página (use o last_id_processed da resposta anterior)
   curl -X GET '{{BASE_URL}}/api/pedidos/full?last_id=1200&limit=100'
   ```

5. **Teste incremental:**
   ```bash
   curl -X GET '{{BASE_URL}}/api/pedidos/incremental'
   ```

### Para debugar problemas:

1. **Ver HTML da página:**
   ```bash
   curl -X GET '{{BASE_URL}}/api/debug/html'
   ```

2. **Ver relatório completo:**
   ```bash
   curl -X GET '{{BASE_URL}}/api/debug/detailed'
   ```

---

## Respostas de Erro Comuns

### 400 Bad Request
**Causa:** Parâmetros inválidos
**Solução:** Verifique se `limit` é maior que 0 e `last_id` é >= 0

### 401 Unauthorized
**Causa:** Problema de autenticação
**Solução:** Verifique as credenciais configuradas no servidor

### 500 Internal Server Error
**Causa:** Erro no servidor
**Solução:** Verifique os logs do servidor ou use `/api/debug/detailed` para mais informações

---

## Dicas Importantes

1. **Sempre teste com `limit` pequeno primeiro** (ex: 5 ou 10) antes de buscar todos
2. **Use paginação** quando houver muitos pedidos para não sobrecarregar o servidor
3. **Use incremental** para automações que rodam regularmente
4. **Use debug endpoints** quando algo não estiver funcionando como esperado
5. **Substitua `{{BASE_URL}}`** pelos exemplos curl pela URL real da sua API

---

## Exemplos Completos

### Exemplo 1: Buscar todos os pedidos (sem paginação)
```bash
curl -X GET 'http://localhost:8000/api/pedidos/full'
```

### Exemplo 2: Buscar 100 pedidos por vez (paginação)
```bash
# Primeira página
curl -X GET 'http://localhost:8000/api/pedidos/full?limit=100' > pagina1.json

# Extrair last_id_processed (exemplo com jq)
LAST_ID=$(cat pagina1.json | jq -r '.pagination.last_id_processed')

# Próxima página
curl -X GET "http://localhost:8000/api/pedidos/full?last_id=${LAST_ID}&limit=100" > pagina2.json
```

### Exemplo 3: Buscar apenas pedidos novos
```bash
curl -X GET 'http://localhost:8000/api/pedidos/incremental'
```

### Exemplo 4: Ver HTML da página para debug
```bash
curl -X GET 'http://localhost:8000/api/debug/html?page=1&use_playwright=false'
```

---

## Próximos Passos

Depois de testar todos os endpoints:
1. Integre com seu sistema (n8n, script, etc)
2. Configure automação para rodar incremental regularmente
3. Monitore os logs se houver problemas
4. Use endpoints de debug quando necessário

---

**Lembre-se:** Substitua `{{BASE_URL}}` pela URL real da sua API em todos os exemplos!


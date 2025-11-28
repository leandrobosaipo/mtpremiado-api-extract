# Guia de Deploy no EasyPanel

Este guia fornece instruções passo a passo para fazer o deploy da API MT Premiado Extract no EasyPanel.

## 📋 Pré-requisitos

- Conta no EasyPanel
- Repositório Git configurado (GitHub, GitLab, etc.)
- Credenciais de acesso ao MT Premiado (email e senha)

## 🚀 Passo a Passo

### 1. Configuração do Repositório

1. No painel do EasyPanel, clique em **"New App"** ou **"Add Service"**
2. Selecione **"Git Repository"** como fonte
3. Configure:
   - **Repository URL**: URL do seu repositório Git (ex: `https://github.com/leandrobosaipo/mtpremiado-api-extract`)
   - **Branch**: `main` (ou a branch principal do seu projeto)
   - **Build Context**: `.` (raiz do projeto)

### 2. Configuração de Build

1. **Build Method**: Selecione **"Dockerfile"**
2. **Dockerfile Path**: `./Dockerfile` (ou deixe vazio se estiver na raiz)
3. **Build Command**: Deixe vazio (o Dockerfile já contém o comando necessário)

### 3. Variáveis de Ambiente

Configure as seguintes variáveis de ambiente no EasyPanel:

#### 🔴 Obrigatórias

| Variável | Descrição | Exemplo |
|----------|-----------|---------|
| `MT_PREMIADO_EMAIL` | Email para login no MT Premiado | `seu_email@exemplo.com` |
| `MT_PREMIADO_SENHA` | Senha para login no MT Premiado | `sua_senha_aqui` |

#### 🟡 Opcionais (mas recomendadas)

| Variável | Descrição | Valor Padrão | Exemplo |
|----------|-----------|-------------|---------|
| `PORT` | Porta da aplicação | `8000` | `8000` |
| `USE_PLAYWRIGHT` | Usar Playwright ao invés de requests | `false` | `true` ou `false` |
| `PLAYWRIGHT_HEADLESS` | Executar browser em modo headless | `true` | `true` ou `false` |
| `EXPORT_JSON` | Salvar JSON de retorno em arquivo | `true` | `true` ou `false` |
| `DEBUG_MODE` | Ativar modo debug completo | `false` | `true` ou `false` |
| `CORS_ORIGINS` | Origens permitidas para CORS | `*` | `https://app1.com,https://app2.com` |

#### 🟢 Opcionais (configurações avançadas)

| Variável | Descrição | Valor Padrão |
|----------|-----------|-------------|
| `MT_PREMIADO_BASE_URL` | URL base do MT Premiado | `https://omtpremiado.com.br` |
| `MT_PREMIADO_LOGIN_URL` | URL de login | `https://omtpremiado.com.br/login` |
| `MT_PREMIADO_PEDIDOS_URL` | URL de pedidos | `https://omtpremiado.com.br/pedidos` |
| `REQUEST_TIMEOUT` | Timeout para requisições (segundos) | `30` |
| `MAX_RETRIES` | Máximo de tentativas | `3` |
| `RETRY_DELAY` | Delay entre tentativas (segundos) | `2` |
| `LOG_LEVEL` | Nível de log | `INFO` |
| `DEBUG_HTML` | Logs detalhados de HTML | `false` |
| `DEBUG_SAVE_HTML` | Salvar HTML em arquivos | `false` |
| `DEBUG_SCREENSHOTS` | Salvar screenshots | `false` |
| `DEBUG_TIMING` | Logar tempos de operações | `false` |
| `PLAYWRIGHT_TIMEOUT` | Timeout do Playwright (ms) | `30000` |

### 4. Volumes e Persistência

Configure os seguintes volumes para persistir dados:

| Caminho no Container | Descrição | Obrigatório |
|---------------------|-----------|------------|
| `/app/data` | Armazena `last_order_state.json` e exports JSON | ✅ Sim |
| `/app/debug` | Arquivos de debug (HTML, screenshots) | ❌ Não |

**Nota**: O volume `/app/data` é **obrigatório** para que a funcionalidade de extração incremental funcione corretamente, pois armazena o estado do último pedido processado.

### 5. Rede e Porta

1. **Porta Interna**: `8000` (ou a variável `PORT` se configurada)
2. **Porta Externa**: EasyPanel geralmente mapeia automaticamente
3. **Protocolo**: HTTP/HTTPS

### 6. Domínio e SSL

1. No EasyPanel, configure um domínio personalizado (opcional)
2. O EasyPanel pode fornecer SSL automático via Let's Encrypt
3. Após configurar o domínio, atualize `CORS_ORIGINS` se necessário:
   ```
   CORS_ORIGINS=https://seu-dominio.com,https://www.seu-dominio.com
   ```

### 7. Health Check

O Dockerfile já inclui um healthcheck configurado:

- **Path**: `/health`
- **Interval**: 30 segundos
- **Timeout**: 10 segundos
- **Start Period**: 40 segundos
- **Retries**: 3

O EasyPanel pode usar este healthcheck automaticamente. Se necessário, configure manualmente:
- **Health Check Path**: `/health`
- **Health Check Interval**: `30s`

### 8. Recursos (CPU e RAM)

**Recomendações mínimas:**
- **CPU**: 0.5-1 core
- **RAM**: 512MB-1GB

**Recomendações com Playwright:**
- **CPU**: 1-2 cores
- **RAM**: 1GB-2GB

**Nota**: Playwright requer mais recursos devido ao browser headless.

### 9. Deploy e Verificação

1. Clique em **"Deploy"** ou **"Save"** no EasyPanel
2. Aguarde o build e deploy completarem
3. Verifique os logs para garantir que a aplicação iniciou corretamente
4. Teste o endpoint de health:
   ```bash
   curl https://seu-dominio.com/health
   ```
   Deve retornar: `{"status":"healthy"}`

5. Teste o Swagger:
   - Acesse: `https://seu-dominio.com/docs`
   - Deve exibir a documentação interativa da API

6. Teste um endpoint:
   ```bash
   curl https://seu-dominio.com/api/pedidos/incremental
   ```

## 🔧 Troubleshooting

### Problema: Aplicação não inicia

**Solução:**
1. Verifique os logs no EasyPanel
2. Confirme que todas as variáveis obrigatórias estão configuradas
3. Verifique se a porta está correta (geralmente 8000)
4. Confirme que o Dockerfile está na raiz do projeto

### Problema: Health check falha

**Solução:**
1. Verifique se o endpoint `/health` está acessível
2. Confirme que a aplicação está rodando na porta correta
3. Verifique os logs para erros de inicialização

### Problema: CORS bloqueando requisições

**Solução:**
1. Configure `CORS_ORIGINS` com os domínios permitidos
2. Separe múltiplos domínios por vírgula
3. Use `*` apenas em desenvolvimento

### Problema: Estado não persiste entre restarts

**Solução:**
1. Confirme que o volume `/app/data` está configurado
2. Verifique as permissões do volume
3. Confirme que o arquivo `last_order_state.json` está sendo criado

### Problema: Playwright não funciona

**Solução:**
1. Confirme que `USE_PLAYWRIGHT=true` está configurado
2. Verifique se há recursos suficientes (CPU/RAM)
3. Confirme que o browser Chromium foi instalado (verifique logs do build)

### Problema: Timeout em requisições

**Solução:**
1. Aumente `REQUEST_TIMEOUT` (padrão: 30 segundos)
2. Aumente `PLAYWRIGHT_TIMEOUT` se usar Playwright
3. Verifique a conectividade com o site MT Premiado

## 📊 Monitoramento

### Logs

Os logs estão disponíveis no painel do EasyPanel. A aplicação usa logging estruturado com níveis:
- `DEBUG`: Informações detalhadas (apenas com `DEBUG_MODE=true`)
- `INFO`: Informações gerais
- `WARNING`: Avisos
- `ERROR`: Erros

### Métricas

Monitore:
- **CPU Usage**: Deve estar abaixo de 80% em operação normal
- **RAM Usage**: Deve estar abaixo de 1GB sem Playwright, 2GB com Playwright
- **Response Time**: Endpoints devem responder em menos de 30 segundos

## 🔄 Atualizações

Para atualizar a aplicação:

1. Faça push das alterações para o repositório Git
2. No EasyPanel, clique em **"Redeploy"** ou **"Rebuild"**
3. Aguarde o novo build e deploy

**Nota**: O volume `/app/data` será preservado, mantendo o estado dos pedidos processados.

## 📝 Checklist Final

Antes de considerar o deploy completo, verifique:

- [ ] Todas as variáveis obrigatórias configuradas
- [ ] Volume `/app/data` configurado
- [ ] Health check funcionando (`/health`)
- [ ] Swagger acessível (`/docs`)
- [ ] Endpoint `/api/pedidos/incremental` funcionando
- [ ] CORS configurado corretamente (se necessário)
- [ ] Domínio e SSL configurados (se necessário)
- [ ] Logs sem erros críticos

## 🆘 Suporte

Se encontrar problemas não listados aqui:

1. Verifique os logs detalhados no EasyPanel
2. Ative `DEBUG_MODE=true` temporariamente para mais informações
3. Verifique a documentação do EasyPanel
4. Consulte o `README.md` do projeto para mais detalhes

## 📚 Referências

- [Documentação do EasyPanel](https://easypanel.io/docs)
- [Documentação do FastAPI](https://fastapi.tiangolo.com/)
- [Documentação do Playwright](https://playwright.dev/python/)


# 🔧 Guia de Ajustes dos Seletores CSS

Este documento explica como ajustar os seletores CSS caso a estrutura HTML do site MT Premiado seja diferente do esperado.

## 📍 Arquivos que Precisam de Ajuste

### 1. `src/scraper/listagem.py`

Este arquivo extrai os pedidos da listagem. Ajuste os seletores conforme a estrutura HTML real:

#### Método `_extract_pedido_from_row`

```python
# Linha 67-82: Ajuste os seletores para encontrar a tabela de pedidos
rows = soup.select("tbody tr, .pedido-item, .order-row, table tr[data-id]")

# Linha 71-82: Ajuste o mapeamento dos campos
cells = row.select("td")
pedido = {
    "id": pedido_id or parser.extract_text(row, "td:first-child"),
    "criado": parser.clean_text(cells[1].get_text()) if len(cells) > 1 else "",
    # ... ajuste os índices conforme a ordem das colunas
}
```

**Como descobrir os seletores corretos:**

1. Acesse a página de pedidos no navegador
2. Abra o DevTools (F12)
3. Inspecione a tabela de pedidos
4. Copie o seletor CSS do elemento
5. Substitua no código

**Exemplo:**
- Se a tabela tem classe `.pedidos-table`, use: `soup.select(".pedidos-table tbody tr")`
- Se cada pedido tem `data-pedido-id`, use: `row.get("data-pedido-id")`

#### Método `_has_more_pages`

```python
# Linha 90-99: Ajuste para encontrar o botão "Próxima página"
next_button = soup.select_one("a[rel='next'], .pagination .next, .page-next")
```

**Como descobrir:**
- Inspecione o botão de paginação
- Veja qual classe/atributo ele usa
- Ajuste o seletor

### 2. `src/scraper/detalhes.py`

Este arquivo extrai os detalhes de cada pedido. Ajuste os seletores conforme a página de detalhes:

#### Métodos de extração (linhas 70-157)

Cada método tenta vários seletores. Ajuste conforme necessário:

```python
def _extract_email(self, soup: BeautifulSoup) -> str:
    # Tenta seletores específicos primeiro
    email = parser.extract_text(soup, "[type='email'], .email, [data-field='email']")
    # Se não encontrar, tenta extrair do texto completo
    if not email:
        text = soup.get_text()
        email = parser.extract_email(text)
    return email
```

**Como descobrir:**

1. Acesse uma página de detalhes de pedido
2. Inspecione onde cada informação está:
   - Email: qual classe/atributo?
   - CPF: onde está no HTML?
   - Valores: como estão formatados?
3. Ajuste os seletores nos métodos correspondentes

### 3. `src/scraper/parser.py`

Este arquivo contém funções auxiliares de parsing. Geralmente não precisa de ajuste, mas você pode:

- Ajustar regex se o formato dos dados for diferente
- Adicionar novos métodos de extração se necessário

## 🧪 Como Testar os Ajustes

### 1. Teste Local

```bash
# Ative o ambiente virtual
source venv/bin/activate

# Execute a API
uvicorn src.main:app --reload --port 8000

# Em outro terminal, teste o endpoint
curl http://localhost:8000/api/pedidos/full
```

### 2. Debug com Logs

Os logs mostram o que está sendo extraído. Verifique:

```bash
# Os logs aparecem no console
# Procure por:
# - "scraping_page_complete": mostra quantos pedidos foram encontrados
# - "order_detail_success": confirma que detalhes foram extraídos
# - "parsing_error": indica problemas na extração
```

### 3. Teste com HTML Real

Você pode salvar o HTML de uma página e testar localmente:

```python
# Em um script de teste
from bs4 import BeautifulSoup
from src.scraper.parser import HTMLParser

with open("pagina_pedidos.html", "r") as f:
    html = f.read()

soup = BeautifulSoup(html, "html.parser")
parser = HTMLParser()

# Teste os seletores
rows = soup.select("tbody tr")  # Ajuste conforme necessário
print(f"Encontrados {len(rows)} pedidos")
```

## 📝 Checklist de Ajustes

- [ ] Verificar seletor da tabela de pedidos (`listagem.py`)
- [ ] Verificar mapeamento das colunas (`listagem.py`)
- [ ] Verificar seletor do botão "Próxima página" (`listagem.py`)
- [ ] Verificar seletores de email (`detalhes.py`)
- [ ] Verificar seletores de CPF (`detalhes.py`)
- [ ] Verificar seletores de telefone (`detalhes.py`)
- [ ] Verificar seletores de valores monetários (`detalhes.py`)
- [ ] Verificar seletores de datas (`detalhes.py`)
- [ ] Testar extração de listagem
- [ ] Testar extração de detalhes
- [ ] Verificar logs para erros
- [ ] Validar JSON de resposta

## 🐛 Problemas Comuns

### Nenhum pedido encontrado

**Causa:** Seletor da tabela incorreto

**Solução:** 
1. Inspecione o HTML da página
2. Ajuste `soup.select()` em `_extract_pedido_from_row`

### Detalhes vazios

**Causa:** Seletores de detalhes incorretos

**Solução:**
1. Acesse uma página de detalhes
2. Inspecione onde cada campo está
3. Ajuste os métodos `_extract_*` em `detalhes.py`

### Erro de autenticação

**Causa:** Token CSRF não encontrado ou formato diferente

**Solução:**
1. Verifique o HTML da página de login
2. Ajuste a regex em `_get_csrf_token()` em `auth.py`

### Paginação não funciona

**Causa:** Botão "Próxima" não encontrado

**Solução:**
1. Inspecione o botão de paginação
2. Ajuste `_has_more_pages()` em `listagem.py`

## 💡 Dicas

1. **Use o DevTools do navegador** para inspecionar elementos
2. **Salve HTML de exemplo** para testar localmente
3. **Teste incrementalmente**: ajuste um seletor por vez
4. **Use logs** para entender o que está acontecendo
5. **Valide o JSON** retornado para garantir que os dados estão corretos

## 📚 Recursos

- [BeautifulSoup Documentation](https://www.crummy.com/software/BeautifulSoup/bs4/doc/)
- [CSS Selectors Reference](https://www.w3schools.com/cssref/css_selectors.asp)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)


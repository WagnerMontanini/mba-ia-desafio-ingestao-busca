# Workflows por Arquivo

Passo-a-passo prescritivo. Siga em ordem. Cada workflow termina com um critério de aceitação verificável.

---

## Workflow 0 — `.env.example`

**Objetivo**: documentar todas as envs com valores de referência.

### Passos

1. Abra `.env.example` e adicione:
   - `PROVIDER=openai` (default)
   - `DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/rag`
   - `PG_VECTOR_COLLECTION_NAME=documents`
   - `PDF_PATH=./document.pdf`
2. Preserve chaves existentes: `GOOGLE_API_KEY`, `GOOGLE_EMBEDDING_MODEL`, `OPENAI_API_KEY`, `OPENAI_EMBEDDING_MODEL`.
3. Reorganize para agrupar por contexto: provider → chaves → banco → aplicação.

### Aceitação

```powershell
# Copiar e editar
Copy-Item .env.example .env
# Abrir no editor, preencher OPENAI_API_KEY, salvar

# Validar
python .cursor/skills/ingestao-busca-rag-dev/scripts/check_env.py
# Saída esperada: "OK — env válido para provider=openai"
```

---

## Workflow 1 — `src/settings.py`

**Estado**: ✅ Implementado. **Ação**: revisar e manter.

### Checklist de revisão

- [ ] `load_dotenv()` chamado uma vez no topo.
- [ ] `_require_env(name)` lança `RuntimeError` com mensagem pt-BR.
- [ ] `get_provider()` valida contra `{openai, gemini}`.
- [ ] `get_embeddings()` e `get_llm()` chamam `validate_provider_credentials()`.
- [ ] Modelos: `gpt-5-nano` e `gemini-2.5-flash-lite`, ambos `temperature=0`.
- [ ] `build_vector_store()` passa `use_jsonb=True`.
- [ ] Constantes `CHUNK_SIZE=1000`, `CHUNK_OVERLAP=150`, `TOP_K=10` exportadas.
- [ ] Type hints em todas as funções públicas.

Se todos os itens estão OK, não mexa.

---

## Workflow 2 — `src/ingest.py`

**Objetivo**: PDF → chunks → embeddings → PGVector, de forma idempotente.

### Passos

1. **Imports**:
   - `logging`, `uuid` (stdlib)
   - `from langchain_community.document_loaders import PyPDFLoader`
   - `from langchain_text_splitters import RecursiveCharacterTextSplitter`
   - `from langchain_core.documents import Document`
   - `from settings import CHUNK_OVERLAP, CHUNK_SIZE, build_vector_store, get_pdf_path`

2. **Configurar logger** (no escopo do módulo):
   ```python
   logger = logging.getLogger(__name__)
   ```

3. **Definir helper de ID determinístico**:
   ```python
   _NAMESPACE = uuid.UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")

   def _chunk_id(source: str, page: int, start_index: int) -> str:
       return str(uuid.uuid5(_NAMESPACE, f"{source}|{page}|{start_index}"))
   ```

4. **Implementar `ingest_pdf()`**:
   1. Log `INFO`: "Iniciando ingestão de {PDF_PATH}".
   2. `loader = PyPDFLoader(pdf_path).load()` — lista de `Document` (um por página).
   3. `splitter = RecursiveCharacterTextSplitter(chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP, add_start_index=True)`.
   4. `chunks = splitter.split_documents(raw_docs)`.
   5. Filtrar chunks vazios: `chunks = [c for c in chunks if c.page_content.strip()]`.
   6. Enriquecer metadata — manter apenas `{source, page, start_index}`.
   7. Gerar lista paralela de `ids` com `_chunk_id(...)`.
   8. `store = build_vector_store()`.
   9. `store.add_documents(documents=chunks, ids=ids)`.
   10. Log `INFO`: "Ingestão concluída: {len(chunks)} chunks persistidos na collection {name}".

5. **Entry point**:
   ```python
   if __name__ == "__main__":
       logging.basicConfig(
           level=os.getenv("LOG_LEVEL", "INFO"),
           format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
       )
       ingest_pdf()
   ```

### Aceitação

```powershell
docker compose up -d
python src/ingest.py
# Log esperado: "Ingestão concluída: N chunks persistidos"
# Rodar 2ª vez → mesmo N, sem duplicatas (IDs determinísticos)
```

Verificar no DB:
```sql
-- Conecte via psql ou DBeaver
SELECT COUNT(*) FROM langchain_pg_embedding;
-- Deve ser estável entre runs do mesmo PDF
```

### Anti-padrões

- ❌ Usar `langchain.vectorstores.PGVector` (depreciado). Use `build_vector_store()`.
- ❌ Omitir `ids=` → duplicatas a cada run.
- ❌ Instanciar `OpenAIEmbeddings()` diretamente. Use `build_vector_store()`.
- ❌ `print()` ao invés de `logger`.

---

## Workflow 3 — `src/search.py`

**Objetivo**: busca vetorial + LCEL chain restrita ao contexto.

### Passos

1. **Preservar `PROMPT_TEMPLATE`** — ele é imutável (copiado do enunciado).

2. **Imports adicionais**:
   ```python
   from langchain_core.output_parsers import StrOutputParser
   from langchain_core.prompts import PromptTemplate
   from settings import TOP_K, build_vector_store, get_llm
   ```

3. **Implementar `search_prompt()`** para retornar um **callable** `ask(question) -> str`:

   ```python
   def search_prompt():
       """Constrói o callable de pergunta-resposta sobre o índice vetorial."""
       store = build_vector_store()
       prompt = PromptTemplate(
           template=PROMPT_TEMPLATE,
           input_variables=["contexto", "pergunta"],
       )
       chain = prompt | get_llm() | StrOutputParser()

       def ask(question: str) -> str:
           docs = store.similarity_search_with_score(question, k=TOP_K)
           contexto = "\n\n".join(d.page_content.strip() for d, _ in docs)
           return chain.invoke({"contexto": contexto, "pergunta": question}).strip()

       return ask
   ```

4. **Por que callable?** O REPL invoca várias vezes; precisa manter `store` e `chain` construídos uma vez. Retornar a chain crua obrigaria recuperar contexto manualmente a cada pergunta.

### Aceitação

```python
# Teste manual via python -c
ask = search_prompt()
ask("O que o documento fala sobre X?")  # responde do contexto
ask("Qual é a capital da França?")      # → "Não tenho informações necessárias..."
```

### Anti-padrões

- ❌ Alterar `PROMPT_TEMPLATE`.
- ❌ `k` diferente de 10 (use constante `TOP_K`).
- ❌ Retornar a chain crua — inviabiliza o REPL sem duplicar lógica.
- ❌ Construir `PGVector`/`LLM` dentro da closure `ask` — recria conexão por pergunta.

---

## Workflow 4 — `src/chat.py`

**Objetivo**: REPL limpo com exit graceful.

### Passos

1. **Imports**:
   ```python
   import sys
   import logging
   from search import search_prompt
   ```

2. **Configurar logging em nível WARNING** para não poluir o REPL:
   ```python
   logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")
   ```

3. **Loop REPL**:

   ```python
   BANNER = (
       "Chat RAG iniciado. Digite sua pergunta e pressione Enter.\n"
       "Digite 'exit' ou 'sair' (ou Ctrl+C) para encerrar.\n"
   )
   EXIT_CMDS = {"exit", "sair", "quit"}

   def main() -> int:
       try:
           ask = search_prompt()
       except Exception as exc:
           print(f"Falha ao inicializar o chat: {exc}", file=sys.stderr)
           return 1

       print(BANNER)
       while True:
           try:
               question = input("PERGUNTA: ").strip()
           except (KeyboardInterrupt, EOFError):
               print()
               break
           if not question:
               continue
           if question.lower() in EXIT_CMDS:
               break
           try:
               answer = ask(question)
           except Exception:
               logging.exception("Erro ao processar pergunta")
               continue
           print(f"\nRESPOSTA: {answer}\n")

       print("Até a próxima.")
       return 0

   if __name__ == "__main__":
       sys.exit(main())
   ```

### Aceitação

- `python src/chat.py` abre o banner.
- `Ctrl+C` encerra sem traceback.
- Pergunta vazia é ignorada (não chama LLM).
- `exit`/`sair` encerra com "Até a próxima.".
- Pergunta fora do contexto retorna: "Não tenho informações necessárias para responder sua pergunta.".

### Anti-padrões

- ❌ Sair com `sys.exit(1)` em exceção do `ask` — degrada UX. Logue e continue.
- ❌ Exibir stack trace ao usuário — apenas em `DEBUG`.
- ❌ `while chain:` — a variável é callable, não falsy.

---

## Workflow 5 — `Makefile`

**Objetivo**: alvos práticos para DX. `install` **deve** recusar rodar fora de `.venv`.

```makefile
.PHONY: venv install up down logs ingest chat check verify reset clean

venv:
	python -m venv .venv
	@echo "Ative com:  .\\.venv\\Scripts\\Activate.ps1  (Windows)  ou  source .venv/bin/activate  (Unix)"

install:
	@python -c "import sys, os; sys.exit(0 if os.path.realpath(sys.prefix) != os.path.realpath(sys.base_prefix) else 1)" \
		|| (echo "ERRO: nenhum .venv ativo. Rode 'make venv' e ative antes de 'make install'." && exit 1)
	python -m pip install --upgrade pip
	pip install -r requirements.txt

up:      ; docker compose up -d
down:    ; docker compose down
logs:    ; docker compose logs -f postgres
ingest:  ; python src/ingest.py
chat:    ; python src/chat.py
check:   ; python .cursor/skills/ingestao-busca-rag-dev/scripts/check_env.py
verify:  ; python .cursor/skills/ingestao-busca-rag-dev/scripts/verify_db.py
reset:   ; python .cursor/skills/ingestao-busca-rag-dev/scripts/reset_collection.py
clean:   ; docker compose down -v
```

**Como funciona o guard**: `sys.prefix != sys.base_prefix` só é verdade dentro de um venv. Se o usuário esquecer de ativar o `.venv`, `make install` falha com mensagem clara antes de poluir o Python global.

**Atenção Windows**: `make` nativo não vem com Windows. Orientar no README a usar `choco install make` ou rodar os comandos diretos. Alternativa: criar `tasks.ps1` equivalente — fora do escopo do plano.

### Aceitação

```powershell
# Com venv ativo: sucesso
.\.venv\Scripts\Activate.ps1
make install

# Sem venv: falha clara
deactivate  # se estiver ativo
make install
# ERRO: nenhum .venv ativo. Rode 'make venv' e ative antes de 'make install'.
```

---

## Workflow 6 — `README.md`

### Estrutura obrigatória

```markdown
# Ingestão e Busca Semântica com LangChain e Postgres

## Pré-requisitos
- Python 3.12
- Docker Desktop
- Chave de API do provider escolhido (OpenAI ou Gemini)

## Setup
1. Clone e entre no diretório.
2. **Crie e ative o `.venv`** (obrigatório — jamais instale no Python global):
   - Windows: `python -m venv .venv` → `.\.venv\Scripts\Activate.ps1`
   - Unix: `python -m venv .venv` → `source .venv/bin/activate`
3. Confirme: `python -c "import sys; print(sys.executable)"` deve apontar para `.venv`.
4. `python -m pip install --upgrade pip && pip install -r requirements.txt`
5. `Copy-Item .env.example .env` (ou `cp`) e preencha.

> **Reative o `.venv` a cada novo terminal** antes de rodar `python src/...` ou `make`.

## Providers
- `PROVIDER=openai` → exige `OPENAI_API_KEY`, embed dim 1536.
- `PROVIDER=gemini` → exige `GOOGLE_API_KEY`, embed dim 768.

**Trocar provider depois de ingerir**: rode `python .cursor/skills/ingestao-busca-rag-dev/scripts/reset_collection.py` antes.

## Execução
```powershell
docker compose up -d
python src/ingest.py
python src/chat.py
```

## Troubleshooting
- **"ModuleNotFoundError: No module named 'langchain...'"**: `.venv` não ativo ou deps não instaladas. Ative com `.\.venv\Scripts\Activate.ps1` e rode `pip install -r requirements.txt`.
- **"different vector dimensions"**: você trocou o provider. Reset a collection.
- **"connection refused"**: Docker não está up. `docker compose up -d`.
- **"extension vector does not exist"**: serviço `bootstrap_vector_ext` falhou. `docker compose logs bootstrap_vector_ext`.
- **"RuntimeError: Variável de ambiente obrigatória"**: env incompleto. Rode `make check`.

## Estrutura
- `src/settings.py` — config + factories
- `src/ingest.py` — PDF → embeddings → pgvector
- `src/search.py` — busca + chain LCEL
- `src/chat.py` — REPL
```

### Aceitação

- README cobre pré-requisitos, setup, execução e 4 troubleshootings mínimos.
- Comandos testados no Windows PowerShell (público-alvo do repo).

---

## Ordem recomendada de execução

1. `.env.example` (bloqueia todo o resto)
2. `src/ingest.py`
3. `src/search.py`
4. `src/chat.py`
5. `Makefile`
6. `README.md`

Cada item = 1 branch `feature/*` + 1 PR + 1-2 commits atômicos.

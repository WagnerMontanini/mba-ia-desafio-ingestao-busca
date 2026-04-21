---
name: ingestao-busca-rag-dev
description: Guides development of the MBA challenge "Ingestão e Busca Semântica" — a Python CLI RAG project using LangChain, langchain-postgres PGVector, PostgreSQL + pgvector, and pluggable embeddings/LLMs (OpenAI or Gemini). Use when implementing, reviewing, or debugging src/settings.py, src/ingest.py, src/search.py, src/chat.py, the Makefile, docker-compose.yml, .env.example, or README.md in this repo; when the user mentions RAG, ingestão, chunking, pgvector, PGVector, similarity_search, LCEL chain, PromptTemplate, PyPDFLoader, RecursiveCharacterTextSplitter, provider OpenAI/Gemini, embeddings dimension mismatch, or follows the plan ingestao_busca_langchain_pgvector.
---

# Ingestão e Busca Semântica — Guia de Desenvolvimento

## Propósito

Esta skill concentra o contexto necessário para implementar **a solução descrita no plano `ingestao_busca_langchain_pgvector`** seguindo as melhores práticas de desenvolvimento Python e as convenções do `docs/skill/Prompt_Dev.md`. Aplique-a sempre que trabalhar nos arquivos `src/*.py`, `Makefile`, `docker-compose.yml`, `.env.example` ou `README.md` deste repositório.

> **Importante**: este projeto **não é Django**. É um CLI Python puro. Convenções Django (ORM, views, admin, gettext obrigatório em i18n) **não se aplicam aqui**. As diretrizes que valem são as seções de *Python*, *commits*, *dependências*, *testes* e *tarefas* do `Prompt_Dev.md`.

## Stack (invariantes do projeto)

| Camada | Tecnologia | Observação |
|---|---|---|
| Linguagem | Python = 3.12 | Type hints obrigatórios em funções públicas |
| Orquestração | LangChain 0.3.x (LCEL) | `prompt | llm | StrOutputParser()` |
| Carregamento PDF | `langchain_community.document_loaders.PyPDFLoader` | `pypdf==6.0.0` |
| Chunking | `langchain_text_splitters.RecursiveCharacterTextSplitter` | `chunk_size=1000`, `chunk_overlap=150`, `add_start_index=True` |
| Vetor store | `langchain_postgres.PGVector` | `use_jsonb=True`, `collection_name` via env |
| DB | PostgreSQL 17 + extensão `vector` | Docker Compose já provisiona |
| Driver | `postgresql+psycopg://` (psycopg3) | **Nunca** use `psycopg2` na URL |
| Provider | `openai` ou `gemini` (env `PROVIDER`) | Mesmo provider em ingest e search |
| LLM OpenAI | `ChatOpenAI(model="gpt-5-nano", temperature=0)` | Fixo pelo enunciado |
| LLM Gemini | `ChatGoogleGenerativeAI(model="gemini-2.5-flash-lite", temperature=0)` | Fixo pelo enunciado |
| Embedding OpenAI | `text-embedding-3-small` (1536d) | Default |
| Embedding Gemini | `gemini-embedding-2-preview` (3072d padrão) | Default |
| Top-K | 10 | `similarity_search_with_score(k=10)` |

## Invariantes críticos (NÃO NEGOCIÁVEIS)

1. **`.venv` obrigatório**. Toda instalação (`pip install`) e execução (`python src/...`) ocorre com o venv ativo. Nunca instale no Python global.
2. **Dimensão do embedding é acoplada à collection**. Trocar `PROVIDER` depois de ingerir quebra o índice. Ao trocar: `reset_collection.py` ou `PG_VECTOR_COLLECTION_NAME` distinto por provider.
3. **IDs determinísticos na ingestão** (`uuid5` sobre `source + page + start_index`) — permite `add_documents` idempotente sem duplicar chunks.
4. **`PROMPT_TEMPLATE` em `src/search.py` é imutável** (definido no enunciado). Apenas `{contexto}` e `{pergunta}` são preenchidos.
5. **Factories em `src/settings.py`** são a única porta de criação de `embeddings`, `llm` e `PGVector`. Scripts executáveis não instanciam clientes diretamente.
6. **Fail-fast** em env ausente — `_require_env` já levanta `RuntimeError`. Não silencie.
7. **Logging** com `logging` (nível `INFO` em produção, `DEBUG` em dev). Zero `print()` em código de biblioteca; `print` só no REPL `chat.py`.

## Checklist de progresso (espelha o plano)

```
- [x] settings        src/settings.py (já implementado — revisar coerência)
- [ ] env             .env.example com PROVIDER e modelos de referência
- [ ] ingest          src/ingest.py (loader → split → enrich → uuid5 → add_documents)
- [ ] search          src/search.py (similarity_search_with_score + LCEL chain)
- [ ] chat            src/chat.py (REPL exit/sair, KeyboardInterrupt, validação)
- [ ] makefile        Makefile com alvos up/down/ingest/chat/install/clean
- [ ] readme          README.md com setup, execução e troubleshooting
```

Antes de iniciar cada item, **leia o workflow correspondente** em [WORKFLOWS.md](WORKFLOWS.md).

## Fluxo de trabalho por tarefa

Para CADA item do checklist acima, siga o fluxo abaixo (derivado do `Prompt_Dev.md` §4):

1. **Compreensão** — releia a seção relevante do plano e abra [ARCHITECTURE.md](ARCHITECTURE.md) se precisar de contexto arquitetural.
2. **Investigação** — leia o stub atual (`Read`) para não sobrescrever código funcional. Verifique `src/settings.py` para reusar factories.
3. **Plano local** — liste as sub-etapas no TodoWrite antes de editar.
4. **Implementação** — siga o template em [WORKFLOWS.md](WORKFLOWS.md) para o arquivo-alvo e copie snippets de [examples.md](examples.md) quando aplicável.
5. **Validação** — rode os scripts utilitários:
   - `python .cursor/skills/ingestao-busca-rag-dev/scripts/check_env.py` — valida `.env` contra o provider escolhido.
   - `python .cursor/skills/ingestao-busca-rag-dev/scripts/verify_db.py` — testa conexão e extensão `vector`.
6. **Sanity check manual** — para `ingest` e `chat`, rode e confira na mão.

## Comandos essenciais

### Setup do ambiente virtual (uma vez, obrigatório)

```powershell
# 1) Criar .venv e ativar
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# 2) Confirmar que está no venv (deve apontar para .venv\Scripts\python.exe)
python -c "import sys; print(sys.executable)"

# 3) Instalar dependências DENTRO do venv
python -m pip install --upgrade pip
pip install -r requirements.txt
```

No Linux/macOS, use `source .venv/bin/activate` no passo 1. **Reative a cada novo terminal.**
Jamais `pip install` no Python global — `.venv` está no `.gitignore`.

### Fluxo diário

```powershell
# Reativar venv em novo terminal
.\.venv\Scripts\Activate.ps1

# Subir banco (pgvector já vem configurado via docker-compose)
docker compose up -d

# Checar env e conexão antes de ingerir
python .cursor/skills/ingestao-busca-rag-dev/scripts/check_env.py
python .cursor/skills/ingestao-busca-rag-dev/scripts/verify_db.py

# Ingerir PDF
python src/ingest.py

# Abrir REPL de perguntas
python src/chat.py

# Limpar collection (trocar provider / re-ingerir do zero)
python .cursor/skills/ingestao-busca-rag-dev/scripts/reset_collection.py
```

## Especialidades necessárias (resumo)

| Domínio | O que dominar |
|---|---|
| **LangChain LCEL** | Composição `prompt | llm | parser`, `PromptTemplate.input_variables` |
| **PGVector / langchain-postgres** | `PGVector(embeddings, collection_name, connection, use_jsonb=True)`, `similarity_search_with_score(query, k)` |
| **Chunking** | `RecursiveCharacterTextSplitter` com `add_start_index=True` preserva offset para dedup |
| **Embeddings** | Diferenças de dimensão entre providers — não são intercambiáveis no mesmo índice |
| **Providers** | `ChatOpenAI` vs `ChatGoogleGenerativeAI` — API keys, modelos, `temperature=0` |
| **Docker** | `pgvector/pgvector:pg17` + serviço bootstrap que roda `CREATE EXTENSION vector` |
| **psycopg3** | Driver via URL `postgresql+psycopg://` — NÃO `postgresql://` nem `psycopg2` |
| **CLI / REPL** | `input()` loop, `try/except (KeyboardInterrupt, EOFError)`, comandos `exit`/`sair` |
| **Config 12-Factor** | `.env` com `python-dotenv`, validação explícita com erro legível |
| **Idempotência** | `uuid.uuid5(namespace, f"{source}|{page}|{start_index}")` |

## Guardrails de revisão (antes de commit)

- [ ] Nenhum segredo commitado (`.env`, chaves API). `.gitignore` respeitado.
- [ ] Apenas `postgresql+psycopg://` na `DATABASE_URL` de exemplo.
- [ ] `temperature=0` em ambos os LLMs.
- [ ] `chunk_size=1000`, `chunk_overlap=150`, `add_start_index=True`.
- [ ] `similarity_search_with_score(query, k=10)` — sem alterar o K.
- [ ] `PROMPT_TEMPLATE` intacto.
- [ ] `use_jsonb=True` em todas as instâncias do `PGVector`.
- [ ] Factories em `settings.py` são a única porta de criação de clientes.
- [ ] Type hints em funções públicas.
- [ ] Logging com `logging.getLogger(__name__)`, sem `print()` em `ingest.py`/`search.py`.
- [ ] Mensagens e logs em **pt-BR** (padrão do projeto).

## Commits (padrão Conventional)

Use tipos: `feat`, `fix`, `chore`, `refactor`, `docs`, `test`. Exemplos:

- `feat(ingest): implementa pipeline de ingestão com IDs determinísticos`
- `feat(search): adiciona cadeia LCEL com prompt restrito ao contexto`
- `feat(chat): cria REPL com exit/sair e tratamento de Ctrl+C`
- `docs(readme): documenta setup, providers e troubleshooting`
- `chore(make): adiciona Makefile com alvos up/ingest/chat`

Commits atômicos — um arquivo/funcionalidade por commit.

## Progressive disclosure (leia apenas quando precisar)

- [ARCHITECTURE.md](ARCHITECTURE.md) — diagrama de fluxo, decisões e trade-offs.
- [CONVENTIONS.md](CONVENTIONS.md) — convenções de código, logging, tipagem e segurança **específicas deste stack** (sem referências a Django).
- [WORKFLOWS.md](WORKFLOWS.md) — passo-a-passo prescritivo por arquivo (`settings` → `ingest` → `search` → `chat` → `Makefile` → `README`).
- [examples.md](examples.md) — snippets verificados prontos para colar e adaptar.

## Anti-padrões a evitar

- Instanciar `OpenAIEmbeddings` ou `PGVector` fora de `settings.py`.
- Usar `langchain.PGVector` (depreciado) — use `langchain_postgres.PGVector`.
- Misturar providers (ex.: ingerir com OpenAI e buscar com Gemini) na mesma collection.
- Ignorar `ids=` em `add_documents` (gera duplicatas a cada re-ingest).
- Hard-code de `PDF_PATH`, `DATABASE_URL`, etc. — sempre via env.
- Usar `print()` para logs de pipeline — só no `chat.py` (UX do REPL).
- Remover regras do `PROMPT_TEMPLATE` ("responder só com base no contexto").
- Commit de `.env`, `*.mo`, `document.pdf` modificado.

## Quando esta skill NÃO se aplica

- Adicionar novo tipo de loader (ex.: HTML, DOCX): o plano é PDF-only.
- Construir web UI (Flask/FastAPI/Streamlit): o escopo é CLI.
- Trocar o banco (ex.: Chroma, Qdrant): mantemos pgvector.
- Adicionar agentes/tools LangChain: o escopo é RAG simples.

Se o usuário pedir algo fora deste escopo, confirme antes de implementar.

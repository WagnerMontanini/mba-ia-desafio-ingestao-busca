# Arquitetura da Solução

## Visão geral

Dois pipelines independentes compartilhando a mesma camada de configuração e o mesmo vetor store:

```mermaid
flowchart LR
    subgraph Config["src/settings.py (única fonte de verdade)"]
        E[get_embeddings]
        L[get_llm]
        V[build_vector_store]
        ENV["load_dotenv + _require_env"]
    end

    subgraph Ingest["Pipeline de Ingestão (src/ingest.py)"]
        PDF[document.pdf] --> Loader[PyPDFLoader]
        Loader --> Split["RecursiveCharacterTextSplitter<br/>1000/150 + add_start_index"]
        Split --> Meta["Filtragem de metadata<br/>source, page, start_index"]
        Meta --> IDs["uuid5 determinístico"]
        IDs --> Add["PGVector.add_documents(ids=)"]
    end

    subgraph Query["Pipeline de Busca (src/search.py)"]
        Q[pergunta] --> Sim["similarity_search_with_score(k=10)"]
        Sim --> Ctx["concat page_content"]
        Ctx --> Prompt[PromptTemplate]
        Prompt --> Chain["prompt | llm | StrOutputParser (LCEL)"]
        Chain --> Ans[resposta]
    end

    subgraph CLI["src/chat.py (REPL)"]
        Loop["loop input → ask → print"]
    end

    Config --> Ingest
    Config --> Query
    Query --> CLI
    Add --> PG[("PostgreSQL<br/>pgvector")]
    Sim --> PG
```

## Decisões de design

### 1. Factories centralizadas

`settings.py` expõe `get_embeddings()`, `get_llm()`, `build_vector_store()` — **único ponto** onde o provider é resolvido. Isso garante:

- Consistência entre ingest e search (mesmo provider → mesma dimensão).
- Testabilidade: mockar factories em testes isola escripts sem depender de HTTP real.
- Troca de provider por env, sem mexer em código de negócio.

### 2. IDs determinísticos para idempotência

Motivação: `add_documents` sem `ids` gera UUID aleatório. Re-ingerir o mesmo PDF **duplica** chunks. Solução:

```python
import uuid

NAMESPACE = uuid.UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")  # uuid.NAMESPACE_URL

def chunk_id(source: str, page: int, start_index: int) -> str:
    return str(uuid.uuid5(NAMESPACE, f"{source}|{page}|{start_index}"))
```

Mesmo chunk (mesmo PDF, página e offset) → mesmo ID → `ON CONFLICT DO UPDATE` pelo `langchain_postgres`.

### 3. Metadata enxuta

O `PyPDFLoader` preenche metadata com muitos campos. Mantenha apenas o essencial:

```python
keep = {"source", "page", "start_index"}
enriched = [
    Document(
        page_content=d.page_content,
        metadata={k: v for k, v in d.metadata.items() if k in keep},
    )
    for d in docs
]
```

Benefícios: payload menor em `use_jsonb`, filtros previsíveis, menor custo de embedding storage.

### 4. Busca → Contexto → LCEL

```python
docs = store.similarity_search_with_score(question, k=10)
contexto = "\n\n".join(d.page_content.strip() for d, _ in docs)
answer = chain.invoke({"contexto": contexto, "pergunta": question}).strip()
```

- `similarity_search_with_score` devolve `list[tuple[Document, float]]`. O score não é usado na montagem do contexto mas é útil para logging/debug (threshold futuro).
- `k=10` é o contrato do enunciado — mudar só via ADR.
- `StrOutputParser` garante `str` limpo (sem `AIMessage` wrapper).

### 5. REPL ergonômico

```python
while True:
    try:
        question = input("\nPERGUNTA: ").strip()
    except (KeyboardInterrupt, EOFError):
        print()  # quebra a linha após ^C
        break
    if question.lower() in {"exit", "sair", "quit"}:
        break
    if not question:
        continue
    print(f"\nRESPOSTA: {ask(question)}\n")
```

Saída clara, entradas vazias ignoradas, `Ctrl+C` não derruba com traceback.

### 6. Driver `psycopg3`

`DATABASE_URL=postgresql+psycopg://user:pass@host:port/db` — SQLAlchemy detecta o dialeto e usa `psycopg` (v3) via `psycopg==3.2.9`. Driver `psycopg2-binary` está no `requirements.txt` apenas por dependência transitiva; **não usar na URL**.

### 7. Collection e dimensão

`PGVector` cria automaticamente duas tabelas na primeira escrita:
- `langchain_pg_collection` (metadados da coleção).
- `langchain_pg_embedding` (chunks + vetor + JSONB de metadata).

A coluna `embedding` fixa a dimensão na **primeira** inserção. Trocar provider depois disso causa `ValueError: different vector dimensions`. Remediação:

1. Dropar a collection: `DELETE FROM langchain_pg_collection WHERE name = 'documents';` (cascade apaga embeddings).
2. Ou criar collection nova: `PG_VECTOR_COLLECTION_NAME=documents_gemini`.

O script `reset_collection.py` automatiza (1).

## Trade-offs conhecidos

| Decisão | Alternativa descartada | Motivo |
|---|---|---|
| `PGVector` (langchain-postgres) | `pgvector` (SQL cru) ou Chroma | Integração nativa com LCEL, menos código |
| `k=10` | `k=3..5` (mais focado) | Enunciado fixa `k=10` |
| `temperature=0` | `0.2..0.7` para criatividade | Fidelidade ao contexto; determinismo para avaliação |
| UUIDv5 (determinístico) | UUIDv4 (aleatório) | Idempotência em re-ingest |
| `add_start_index=True` | Offset implícito | Preserva posição para dedup e citação futura |
| CLI puro | Streamlit/FastAPI | Escopo do enunciado é CLI |
| `PyPDFLoader` | `PDFPlumberLoader`, `UnstructuredPDFLoader` | Simples, rápido, suficiente |

## Riscos operacionais

1. **Provider switch sem reset** → erro de dimensão em runtime. Mitigação: script `reset_collection.py` + documentação no README.
2. **PDF muito grande** → `OpenAIEmbeddings` pode estourar rate limit. Mitigação futura: `chunk_size` em batches de `add_documents`. Por ora, aceitar o default do adapter.
3. **Chave API ausente** → `RuntimeError` claro via `_require_env`. Já tratado.
4. **Docker não subiu** → conexão falha com timeout. Mitigação: `verify_db.py` antes de ingerir.
5. **Prompt injection via PDF** → chunk malicioso no contexto pode tentar sobrescrever regras. Mitigação parcial: as regras do `PROMPT_TEMPLATE` são explícitas e em pt-BR. Aceitável para escopo educacional.

## Mapeamento plano → arquivos

| Item do plano | Arquivo | Estado atual |
|---|---|---|
| settings | `src/settings.py` | ✅ Implementado |
| env | `.env.example` | ⚠️ Falta `PROVIDER` |
| ingest | `src/ingest.py` | ❌ Stub vazio |
| search | `src/search.py` | ⚠️ `PROMPT_TEMPLATE` ok, `search_prompt` vazio |
| chat | `src/chat.py` | ❌ Stub vazio |
| makefile | `Makefile` | ❌ Não existe |
| readme | `README.md` | ❌ Esqueleto |

Use este mapa para priorizar — `env` é pré-requisito para `ingest`/`search`/`chat`.
